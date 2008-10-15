#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
import sys
import sets
import re
import cgi
import struct
import gtk
import cairo
import pango
from gettext import gettext as _

# Advene part
import advene.core.config as config

from advene.model.cam.tag import RelationType
from advene.model.cam.annotation import Annotation
from advene.model.cam.relation import Relation
from advene.gui.views import AdhocView
#from advene.gui.edit.create import CreateElementPopup
from advene.gui.util import png_to_pixbuf
from advene.gui.util import decode_drop_parameters
import advene.gui.popup

from advene.gui.views.annotationdisplay import AnnotationDisplay
import advene.util.helper as helper
from advene.gui.util import dialog, name2color, get_small_stock_button, get_pixmap_button
from advene.gui.widget import AnnotationWidget, AnnotationTypeWidget, GenericColorButtonWidget

name="Timeline view plugin"

def register(controller):
    controller.register_viewclass(TimeLine)

parsed_representation = re.compile(r'^here/content/parsed/([\w\d_\.]+)$')

class QuickviewBar(gtk.HBox):
    def __init__(self, controller=None):
        gtk.HBox.__init__(self)
        self.controller=controller
        self.begin=gtk.Label()
        self.end=gtk.Label()
        self.content=gtk.Label()
        self.content.set_single_line_mode(True)
        self.content.set_ellipsize(pango.ELLIPSIZE_MIDDLE)

        self.annotation=None

        self.pack_start(self.content, expand=True)
        self.pack_start(self.begin, expand=False)
        self.pack_start(self.end, expand=False)

    def set_annotation(self, a=None):
        if a is None:
            b=""
            e=""
            c=""
        elif isinstance(a, long) or isinstance(a, int):
            # Only display a time
            b="   " + helper.format_time(a)
            e=""
            c=_("Current time")
        else:
            b="   " + helper.format_time(a.begin)
            e=" - " + helper.format_time(a.end)
            c=self.controller.get_title(a)
            c += " (" + a.id + ")"
        self.annotation=a
        self.begin.set_text(b)
        self.end.set_text(e)
        self.content.set_markup(u"<b>%s</b>" % c)

class TimeLine(AdhocView):
    """Representation of a set of annotations placed on a timeline.

    If l is None, then use controller.package.annotations (and handle
    updates accordingly).

    There are 2 adjustments used to adjust the display scale:

       * self.scale stores how many units does a pixel
         represent. It is an absolute value (and generally integer:
         given that units are milliseconds, we should not need to
         display fractions of ms.

       * self.fraction_adj stores the fraction of the whole stream
         displayed in the window. It thus depends on both the
         self.scale and the widget size.

    and a 3rd one (self.adjustment) which controls the displayed area.
    """
    view_name = _("Timeline")
    view_id = 'timeline'
    tooltip = _("Representation of a set of annotations placed on a timeline.")

    def __init__ (self, elements=None,
                  minimum=None,
                  maximum=None,
                  controller=None,
                  annotationtypes=None,
                  parameters=None):
        super(TimeLine, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            (_("Save view"), self.save_view),
            (_("Save default options"), self.save_default_options),
            (_("Limit display to current area"), self.limit_display),
            (_("Display whole movie"), self.unlimit_display),
            )
        self.options = {
            'highlight': False,
            # Autoscroll: 0: None, 1: continuous, 2: discrete, 3: annotation
            'autoscroll': 2,
            'display-relations': True,
            'display-relation-type': True,
            'display-relation-content': True,
            'goto-on-click': True,
            }
        self.controller=controller

        self.registered_rules=[]

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        ats=[]
        # Default position in ms.
        default_position=None
        default_zoom=1.0
        pane_position=opt.get('pane-position', None)
        for n, v in arg:
            if n == 'annotation-type':
                at=self.controller.package.get(v)
                if at:
                    ats.append(at)
                else:
                    self.log(_("Cannot find annotation type %s") % v)
            elif n == 'source':
                c=self.controller.build_context()
                # Override a potentially existing value of elements
                elements=c.evaluate(v)
            elif n == 'position':
                default_position=int(float(v))
            elif n == 'zoom':
                default_zoom=float(v)
            elif n == 'minimum':
                minimum=long(v)
            elif n == 'maximum':
                maximum=long(v)
        if ats:
            annotationtypes=ats

        self.list = elements
        self.annotationtypes = annotationtypes
        self.tooltips = gtk.Tooltips()

        self.current_marker = None
        self.current_marker_scale = None

        # Now that self.list is initialized, we reuse the l variable
        # for various checks.
        if elements is None:
            elements = controller.package.all.annotations
        # Initialize annotation types if needed
        if self.annotationtypes is None:
            if self.list is None:
                # We display the whole package, so display also
                # empty annotation types
                self.annotationtypes = list(self.controller.package.all.annotation_types)
            else:
                # We specified a list. Display only the annotation
                # types for annotations present in the set
                self.annotationtypes = list(set([ a.type for a in self.list ]))

        if minimum is None and maximum is None and controller is not None:
            # No dimension. Get them from the controller.
            duration = controller.cached_duration
            if duration <= 0:
                if elements:
                    duration = max([a.end for a in elements])
                else:
                    duration = 0
            minimum=0
            maximum=duration

        if minimum is None or maximum is None:
            b, e = self.bounds ()
            if minimum is None:
                minimum = b
            if maximum is None:
                maximum = e
        self.minimum = minimum
        self.maximum = maximum

        # Ensure that self.maximum > self.minimum
        if self.maximum == self.minimum:
            self.maximum = self.minimum + 10000

        if self.minimum > self.maximum:
            self.minimum, self.maximum = self.maximum, self.minimum

        if default_position is None:
            default_position=self.minimum

        self.colors = {
            'active': gtk.gdk.color_parse ('#fdfd4b'),
            'inactive': gtk.Button().get_style().bg[0],
            'background': gtk.gdk.color_parse('red'),
            'relations': gtk.gdk.color_parse('orange'),
            'white': gtk.gdk.color_parse('white'),
            }

        def handle_autoscroll_combo(combo):
            self.options['autoscroll'] = combo.get_current_element()
            return True

        # Scroll the window to display the activated annotations
        self.autoscroll_choice = dialog.list_selector_widget(
            members= ( ( 0, _("No scrolling") ),
                       ( 1, _("Continuous scrolling")),
                       ( 2, _("Discrete scrolling")),
                       ( 3, _("Annotation scrolling")) ),
            preselect= self.options['autoscroll'],
            callback=handle_autoscroll_combo)

        # Create annotation widget style:
        self.annotation_font = pango.FontDescription("sans %d" % config.data.preferences['timeline']['font-size'])
        self.annotation_type_font = self.annotation_font.copy()
        self.annotation_type_font.set_style(pango.STYLE_ITALIC)

        # Maybe we should ask pango the height of 'l' plus margins
        self.button_height = config.data.preferences['timeline']['button-height']

        # Shortcut
        u2p = self.unit2pixel

        # How many units does a pixel represent ?
        # self.scale.value = unit by pixel
        # Unit = ms
        self.scale = gtk.Adjustment (value=(self.maximum - self.minimum) / gtk.gdk.get_default_root_window().get_size()[0],
                                                lower=5,
                                                upper=36000,
                                                step_incr=5,
                                                page_incr=1000)
        self.scale.connect('value-changed', self.scale_event)
        self.scale.connect('changed', self.scale_event)

        # The same value in relative form
        self.fraction_adj = gtk.Adjustment (value=1.0,
                                            lower=0.01,
                                            upper=1.0,
                                            step_incr=.01,
                                            page_incr=.1)
        self.fraction_adj.connect('value-changed', self.fraction_event)
        self.fraction_adj.connect('changed', self.fraction_event)

        # Coordinates of the selected region.
        self.layout_selection=[ [None, None], [None, None] ]

        self.layout = gtk.Layout ()
        self.layout.add_events( gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.BUTTON1_MOTION_MASK )
        self.scale_layout = gtk.Layout()
        self.scale_layout.add_events( gtk.gdk.BUTTON_PRESS_MASK )

        # Memorize the current scale height, so that we can refresh it
        # when it is changed by a given amount (typically 10 or 16
        # pixels)
        self.current_scale_height=0
        # Global pane is the VPaned holding the scale and the layout.
        self.global_pane=None

        self.legend = gtk.Layout ()

        self.layout.connect('key-press-event', self.layout_key_press_cb)
        self.scale_layout.connect('key-press-event', self.layout_key_press_cb)

        self.layout.connect('scroll-event', self.layout_scroll_cb)
        self.scale_layout.connect('scroll-event', self.layout_scroll_cb)

        self.layout.connect('button-press-event', self.layout_button_press_cb)
        self.layout.connect('button-release-event', self.layout_button_release_cb)
        self.layout.connect('motion-notify-event', self.layout_motion_notify_cb)
        self.layout.connect('drag-motion', self.layout_drag_motion_cb)
        self.layout.connect('drag-leave', self.layout_drag_leave_cb)
        self.scale_layout.connect('button-press-event', self.scale_layout_button_press_cb)

        self.layout.connect('size-allocate', self.layout_resize_event)
        self.layout.connect('expose-event', self.draw_background)
        self.layout.connect_after('expose-event', self.draw_relation_lines)
        self.scale_layout.connect_after('expose-event', self.draw_bookmarks)

        # The layout can receive drops
        self.layout.connect('drag-data-received', self.layout_drag_received)
        self.layout.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation']
                                  + config.data.drag_type['annotation-type']
                                  + config.data.drag_type['timestamp'],
                                  gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_ASK )

        self.old_scale_value = self.scale.value

        # Lines to draw in order to indicate related annotations
        self.relations_to_draw = []
        self.bookmarks_to_draw = []

        # Current position in units
        self.current_position = minimum

        # Holds the ref. to a newly created annotation, so that its
        # widget gets focus when it is created (cf  udpate_annotation)
        self.transmuted_annotation = None
        # Adjustment corresponding to the Virtual display
        # The page_size is the really displayed area
        self.adjustment = gtk.Adjustment ()
        self.update_adjustment ()
        self.adjustment.set_value(u2p(minimum, absolute=True))

        # Dictionary holding the vertical position for each type
        self.layer_position = {}

        self.update_layer_position()

        self.populate ()

        self.draw_marks ()

        self.draw_current_mark()
        self.widget = self.get_full_widget()
        self.update_legend_widget(self.legend)

        # Set default parameters (zoom) and refresh the legend widget
        # on the first expose signal
        def set_default_parameters(widget, event, zoom, pos, pane):
            self.fraction_adj.value=zoom
            if pos >= self.minimum and pos <= self.maximum:
                self.adjustment.set_value(u2p(pos, absolute=True))
            self.resize_legend_widget(self.legend)
            # Set annotation inspector width, so that it does not auto-resize
            if pane is None:
                w, h = self.widget.window.get_size()
                pane=w - 160
            self.inspector_pane.set_position(pane)
            self.widget.disconnect(self.expose_signal)
            return False
        # Convert values, that could be strings
        if default_position is not None:
            default_position=long(float(default_position))
        if pane_position is not None:
            pane_position=long(float(pane_position))

        self.expose_signal=self.widget.connect('expose-event', set_default_parameters,
                                               default_zoom, default_position, pane_position)


    def get_save_arguments(self):
        arguments = [ ('annotation-type', at.id) for at in self.annotationtypes ]
        arguments.append( ('minimum', self.minimum ) )
        arguments.append( ('maximum', self.maximum ) )
        arguments.append( ('position', self.pixel2unit(self.adjustment.value, absolute=True) ) )
        arguments.append( ('zoom', self.fraction_adj.value) )
        self.options['pane-position']=self.inspector_pane.get_position()
        return self.options, arguments

    def draw_background(self, layout, event):
        width, height = layout.get_size()
        i=config.data.preferences['timeline']['interline-height']
        drawable=layout.bin_window
        gc=drawable.new_gc(foreground=self.colors['background'], line_style=gtk.gdk.LINE_ON_OFF_DASH)
        for p in sorted(self.layer_position.itervalues()):
            # Draw a different background
            drawable.draw_line(gc, 0, p - i / 2, width, p - i / 2)
        return False

    def update_relation_lines(self):
        self.layout.queue_draw()

    def draw_relation_lines(self, layout, event):
        if self.bookmarks_to_draw:
            self.draw_bookmarks(layout, event)
        if not self.relations_to_draw:
            return False
        context=layout.bin_window.cairo_create()

        for b1, b2, r in self.relations_to_draw:
            r1 = b1.get_allocation()
            r2 = b2.get_allocation()
            x_start = r1.x + 3 * r1.width / 4
            y_start  = r1.y + r1.height / 4
            x_end=r2.x + r2.width / 4
            y_end=r2.y + 3 * r2.height / 4
            context.set_source_rgb(0, 0, 0)
            context.set_line_width(1)
            context.move_to(x_start, y_start)
            context.line_to(x_end, y_end)
            context.stroke()
            # Display the starting mark
            context.rectangle(x_start - 2, y_start - 2,
                              4, 4)
            context.fill()

            t=""
            if self.options['display-relation-type']:
                t = r.type.title
            if self.options['display-relation-content']:
                if r.content.data:
                    if t:
                        t += "\n" + r.content.data
                    else:
                        t = r.content.data
            if t:
                context.select_font_face("Helvetica",
                                         cairo.FONT_SLANT_NORMAL,
                                         cairo.FONT_WEIGHT_NORMAL)
                context.set_font_size(config.data.preferences['timeline']['font-size'])
                ext=context.text_extents(t)

                # We draw the relation type on a white background by default,
                # but this should depend on the active gtk theme
                color=self.get_element_color(r) or self.colors['white']
                context.set_source_rgb(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0)
                context.rectangle((x_start + x_end ) / 2,
                                  (y_start + y_end ) / 2 - ext[3] - 2,
                                  ext[2] + 2,
                                  ext[3] + 6)
                context.fill()

                context.set_source_rgb(0, 0, 0)
                context.move_to((x_start + x_end ) / 2,
                                (y_start + y_end ) / 2)
                context.show_text(t)
            context.stroke()

        return False

    def update_bookmarks(self):
        self.scale_layout.queue_draw()
        self.layout.queue_draw()

    def draw_bookmarks(self, layout, event):
        if not self.bookmarks_to_draw:
            return False
        a=self.adjustment
        begin=long(a.value)
        end=long(a.value + a.page_size)
        context=layout.bin_window.cairo_create()
        h=layout.get_size ()[1]

        context.set_source_rgb(1.0, 0, 0)
        context.set_line_width(2)

        for t in self.bookmarks_to_draw:
            x=self.unit2pixel(t, absolute=True)
            if x < begin:
                # The bookmark is outside. Draw an arrow.
                context.move_to(begin + 16, 2)
                context.line_to(begin + 16, 16)
                context.line_to(begin + 2, 9)
                context.fill()
            elif x > end:
                # The bookmark is outside. Draw an arrow.
                context.move_to(end - 16, 2)
                context.line_to(end - 16, 16)
                context.line_to(end - 2, 9)
                context.fill()
            else:
                context.move_to(x, 0)
                context.line_to(x, h)
                context.stroke()
        return False

    def update_model(self, package=None, partial_update=False):
        """Update the whole model.

        @param package: the package
        @type package: Package
        @param update: it is only an update for the existing package, we do not need to rebuild everything
        @param update: boolean
        """
        if package is None:
            package = self.controller.package

        self.adjustment.value=0
        if not partial_update:
            # It is not just an update, do a full redraw
            oldmax=self.maximum
            self.minimum=0
            self.maximum=0
            try:
                duration=package.cached_duration
            except:
                duration=0
            if duration:
                self.maximum = long(duration)

            if not self.maximum:
                # self.maximum == 0, so try to compute it
                self.maximum = self.bounds()[1]

            if self.maximum != oldmax:
                # Reset to display whole timeline
                (w, h)=self.layout.window.get_size()
                self.scale.set_value( (self.maximum - self.minimum) / float(w) )

            if self.list is None:
                # We display the whole package, so display also
                # empty annotation types
                self.annotationtypes = list(self.controller.package.all.annotation_types)
            else:
                # We specified a list. Display only the annotation
                # types for annotations present in the set
                self.annotationtypes = list(set([ a.type for a in self.list ]))

        # Clear the layouts
        self.layout.foreach(self.layout.remove)
        self.scale_layout.foreach(self.scale_layout.remove)
        self.legend.foreach(self.legend.remove)

        self.layer_position.clear()
        self.update_layer_position()
        self.populate()

        self.draw_marks()

        self.draw_current_mark()

        self.update_legend_widget(self.legend)
        self.legend.show_all()
        self.fraction_event(widget=None)
        #self.layout.show_all()
        return

    def set_autoscroll_mode(self, v):
        """Set the autoscroll value.
        """
        if v not in (0, 1, 2, 3):
            return False
        # Update self.autoscroll_choice
        self.autoscroll_choice.set_active(v)
        return True

    def update_layer_position(self):
        """Update the layer_position attribute

        """
        s = config.data.preferences['timeline']['interline-height']
        h = 0
        for at in self.annotationtypes:
            self.layer_position[at] = h
            h += self.button_height + s

    def refresh(self, *p):
        self.update_model(self.controller.package, partial_update=True)
        return True

    def set_annotation(self, a=None):
        self.quickview.set_annotation(a)
        for v in self._slave_views:
            try:
                v.set_annotation(a)
            except AttributeError:
                pass
        if self.bookmarks_to_draw:
            self.bookmarks_to_draw = []

    def debug_cb (self, widget, data=None):
        print "Debug event."
        if data is not None:
            print "Data: %s" % data
        return False

    def get_widget_for_annotation (self, annotation):
        bs = [ b
               for b in self.layout.get_children()
               if hasattr (b, 'annotation') and b.annotation == annotation ]
        if bs:
            return bs[0]
        else:
            return None

    def scroll_to_annotation(self, annotation):
        """Scroll the view to put the annotation in the middle.
        """
        self.center_on_position(annotation.fragment.begin)
        self.update_position (None)
        return True

    def center_on_position(self, position):
        """Scroll the view to center on the given position.
        """
        alloc = self.layout.get_allocation()
        pos = self.unit2pixel(position, absolute=True) - (alloc.width / 2)
        a = self.adjustment
        if pos < a.lower:
            pos = a.lower
        elif pos >= a.upper - a.page_size:
            pos = a.upper - a.page_size
        if a.value != pos:
            a.set_value (pos)
        return True

    def activate_annotation_handler (self, context, parameters):
        annotation=context.evaluate('annotation')
        if annotation is not None:
            if self.options['autoscroll'] == 3:
                self.scroll_to_annotation(annotation)
            if self.options['highlight']:
                self.activate_annotation (annotation)
            self.update_position (None)
        return True

    def desactivate_annotation_handler (self, context, parameters):
        annotation=context.evaluate('annotation')
        if annotation is not None:
            if self.options['highlight']:
                self.desactivate_annotation (annotation)
        return True

    def duration_update_handler(self, context, parameters):
        if self.maximum != long(context.globals['duration']):
            # Need a refresh
            self.update_model()
        return True

    def register_callback (self, controller=None):
        """Add the activate handler for annotations.
        """
        self.registered_rules.extend(
            (
                controller.event_handler.internal_rule (event="AnnotationBegin",
                                                        method=self.activate_annotation_handler),
                controller.event_handler.internal_rule (event="AnnotationEnd",
                                                        method=self.desactivate_annotation_handler),
                controller.event_handler.internal_rule (event="TagUpdate",
                                                        method=self.tag_update),
                controller.event_handler.internal_rule (event="RestrictType",
                                                        method=self.type_restricted_handler),
                controller.event_handler.internal_rule (event="BookmarkHighlight",
                                                        method=self.bookmark_highlight_handler),
                controller.event_handler.internal_rule (event="BookmarkUnhighlight",
                                                        method=self.bookmark_unhighlight_handler),
                controller.event_handler.internal_rule (event="DurationUpdate",
                                                        method=self.duration_update_handler),
                ))

    def type_restricted_handler(self, context, parameters):
        """Update the display when playing is restricted to a type.
        """
        at=context.globals['annotationtype']
        for w in self.legend.get_children():
            if hasattr(w, 'set_playing'):
                w.set_playing(w.annotationtype == at)
        return True

    def bookmark_highlight_handler(self, context, parameters):
        position=long(context.globals['timestamp'])
        self.bookmarks_to_draw.append(position)
        self.update_bookmarks()
        return True

    def bookmark_unhighlight_handler(self, context, parameters):
        position=long(context.globals['timestamp'])
        try:
            self.bookmarks_to_draw.remove(position)
            self.update_bookmarks()
        except ValueError:
            pass
        return True

    def tag_update(self, context, parameters):
        tag=context.evaluate('tag')
        bs = [ b
               for b in self.layout.get_children()
               if hasattr (b, 'annotation') and b.annotation.has_tag(tag) ]
        for b in bs:
            self.update_button(b)
        return True

    def unregister_callback (self, controller=None):
        for r in self.registered_rules:
            controller.event_handler.remove_rule(r, type_="internal")

    def activate_annotation (self, annotation, buttons=None, color=None):
        """Activate the representation of the given annotation."""
        if buttons is None:
            b=self.get_widget_for_annotation (annotation)
            if b:
                buttons = [ b ]
            else:
                return True
        if color is None:
            color=self.colors['active']
        for b in buttons:
            b.set_active(True)
        self.update_selection_button()
        return True

    def desactivate_annotation (self, annotation, buttons=None):
        """Desactivate the representation of the given annotation."""
        if buttons is None:
            b=self.get_widget_for_annotation (annotation)
            if b:
                buttons = [ b ]
            else:
                return True
        for b in buttons:
            b.set_active(False)
        self.update_selection_button()
        return True

    def toggle_annotation (self, annotation):
        button = self.get_widget_for_annotation (annotation)
        if button:
            if button.active:
                self.desactivate_annotation (annotation, buttons=button)
            else:
                self.activate_annotation (annotation, buttons=button)

    def unit2pixel (self, v, absolute=False):
        if absolute:
            return (long( ( v - self.minimum) / self.scale.value )) or 1
        else:
            return (long(v / self.scale.value)) or 1

    def pixel2unit (self, v, absolute=False):
        if absolute:
            return long((v * self.scale.value) + self.minimum)
        else:
            return long(v * self.scale.value)

    def get_element_color(self, element):
        """Return the gtk color for the given element.
        Return None if no color is defined.
        """
        color=self.controller.get_element_color(element)
        return name2color(color)

    def update_button (self, b):
        """Update the representation for button b.
        """
        b.update_widget()
        a=b.annotation
        tip = _("%(id)s: %(begin)s - %(end)s\n%(content)s") % {
            'content': a.content.data,
            'id': a.id,
            'begin': helper.format_time(a.begin),
            'end': helper.format_time(a.end) }
        self.layout.move(b, self.unit2pixel(a.begin, absolute=True), self.layer_position[a.type])
        return True

    def update_annotation (self, annotation=None, event=None):
        """Update an annotation's representation."""
        if self.list is None:
            l=self.controller.package.all.annotations
        else:
            l=self.list
        if event == 'AnnotationActivate' and annotation in l:
            self.activate_annotation(annotation)
            if self.options['autoscroll'] == 3:
                self.scroll_to_annotation(annotation)
            return True
        if event == 'AnnotationDeactivate' and annotation in l:
            self.desactivate_annotation(annotation)
            return True
        if event == 'AnnotationCreate' and annotation in l:
            b=self.get_widget_for_annotation(annotation)
            if b is not None:
                # It was already created (for instance by the code
                # in update_legend_widget/create_annotation
                b.grab_focus()
                return True
            b=self.create_annotation_widget(annotation)
            b.grab_focus()
            return True

        b = self.get_widget_for_annotation (annotation)
        if event == 'AnnotationEditEnd':
            self.update_button (b)
        elif event == 'AnnotationDelete':
            b.destroy()
        elif event == 'AnnotationCreate':
            pass
        else:
            print "Unknown event %s" % event
        return True

    def update_annotationtype (self, annotationtype=None, event=None):
        """Update an annotationtype's representation.
        """
        if event == 'AnnotationTypeCreate':
            self.annotationtypes.append(annotationtype)
            self.update_model(partial_update=True)
        elif event == 'AnnotationTypeEditEnd':
            self.legend.foreach(self.legend.remove)
            self.update_legend_widget(self.legend)
            self.legend.show_all()
            # Update also its annotations, since representation or
            # color may have changed
            for b in self.layout.get_children():
                if hasattr (b, 'annotation') and b.annotation.type == annotationtype:
                    self.update_button (b)
        elif event == 'AnnotationTypeDelete':
            try:
                self.annotationtypes.remove(annotationtype)
                self.update_model(partial_update=True)
            except ValueError:
                # It was not displayed anyway
                pass
        return True

    def annotation_cb (self, widget, ann, x):
        """Display the popup menu when clicking on annotation.
        """
        if widget.active and len(self.get_selected_annotation_widgets()) > 1:
            # Widget is active, there is a selection. Display the selection menu
            self.selection_menu(popup=True)
            return True

        def split_annotation(menu, widget, ann, p):
            self.controller.split_annotation(ann, p)
            return True

        def center_and_zoom(menu, widget, ann):
            # Deactivate autoscroll...
            self.set_autoscroll_mode(0)

            # Set the zoom
            z=1.0 * ann.duration / (self.maximum - self.minimum)
            if z < 0.05:
                z=0.05
            self.fraction_adj.value=z

            # Center on annotation
            self.center_on_position(ann.begin)
            return True

        p=self.pixel2unit(widget.allocation.x + x, absolute=True)
        menu=advene.gui.popup.Menu(ann, controller=self.controller)
        menu.add_menuitem(menu.menu,
                          _("Split at %s") % helper.format_time(p),
                          split_annotation, widget, ann, p)

        menu.add_menuitem(menu.menu,
                          _("Center and zoom"),
                          center_and_zoom, widget, ann)

        menu.menu.show_all()
        menu.popup()
        return True

    def dump_adjustment (self, a=None):
        if a is None:
            a = self.adjustment
        print ("Lower: %.1f\tUpper: %.1f\tValue: %.1f\tPage size: %.1f"
               % (a.lower, a.upper, a.value, a.page_size))

    def align_annotations(self, source, dest, mode):
        new={
            'begin': source.begin,
            'end': source.end
            }
        if '-' in mode:
            (s, d) = mode.split('-')
            new[s]=getattr(dest, d)
        elif mode == 'align':
            for k in ('begin', 'end'):
                new[k]=getattr(dest, k)
        else:
            print "Unknown drag mode: %s" % mode


        if new['begin'] < new['end']:
            self.controller.notify('ElementEditBegin', element=source, immediate=True)
            for k in ('begin', 'end'):
                setattr(source, k, new[k])
            self.controller.notify("AnnotationEditEnd", annotation=source)
            self.controller.notify('ElementEditCancel', element=source)
        return True

    def annotation_fraction(self, widget):
        """Return the fraction of the cursor position relative to the annotation widget.

        @return: a fraction (float)
        """
        x, y = widget.get_pointer()
        w = widget.allocation.width
        f = 1.0 * x / w
        return f

    def create_relation(self, source, dest, rt):
        """Create the reation of type rt between source and dest.
        """
        # Get the id from the idgenerator
        p=self.controller.package
        id_=self.controller.package._idgenerator.get_id(Relation)
        relation=p.create_relation(id=id_,
                                   members=(source, dest),
                                   type=rt)
        self.controller.notify("RelationCreate", relation=relation)
        return True

    def create_annotation_type(self, *p):
        at=None
        if self.controller.gui:
            at=self.controller.gui.on_create_annotation_type_activate()
        return at

    def create_annotation(self, position, type, duration=None, content=None):
        position=long(position)
        if position > self.controller.cached_duration:
            return None

        id_=self.controller.package._idgenerator.get_id(Annotation)
        if duration is None:
            duration=self.controller.cached_duration / 20
            # Make the end bound not override the screen
            d=long(self.pixel2unit(self.adjustment.value + self.layout.window.get_size()[0], absolute=True) - position)
            if d > 0:
                duration=min(d, duration)
            else:
                # Should not happen
                print "Strange, click outside the timeline"
                return None

        if position + duration > self.controller.cached_duration:
            duration = self.controller.cached_duration - position

        el=self.controller.package.create_annotation(
            id=id_,
            media=self.controller.current_media,
            begin=position,
            end=position+duration,
            type=type,
            mimetype='text/plain', # FIXME
            )
        if content is not None:
            el.content.data=content
        elif el.owner._fieldnames[type.id]:
            el.content.data="\n".join( "%s=" % f for f in sorted(el.owner._fieldnames[type.id]) )
        el.complete=False
        self.controller.notify('AnnotationCreate', annotation=el)
        return el

    def annotation_drag_begin(self, widget, context):
        """Handle drag begin for annotations.
        """
        # Determine in which part of the annotation we clicked.
        widget._drag_fraction = self.annotation_fraction(widget)
        return False

    def annotation_drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source=self.controller.package.get(unicode(selection.data, 'utf8').split('\n')[0])
            dest=widget.annotation

            if source == dest:
                return True

            # Popup a menu to propose the drop options
            menu=gtk.Menu()

            def create_relation(item, s, d, t):
                self.create_relation(s, d, t)
                return True

            def create_relation_type_and_relation(item, s, d):
                if self.controller.gui:
                    sc=self.controller.gui.ask_for_schema(text=_("Select the schema where you want to\ncreate the new relation type."), create=True)
                    if sc is None:
                        return None
                    cr=CreateElementPopup(type_=RelationType,
                                          parent=sc,
                                          controller=self.controller)
                    rt=cr.popup(modal=True)
                    # FIXME: ???
                    if not rt.hackedMemberTypes:
                        # membertypes is empty, the user did not specify any member types.
                        # Create a relationType specific for the 2 annotations.
                        rt.hackedMemberTypes=( '#' + s.type.id, '#' + d.type.id )
                    self.create_relation(s, d, rt)
                return True

            relationtypes=helper.matching_relationtypes(self.controller.package,
                                                        source.type,
                                                        dest.type)
            item=gtk.MenuItem(_("Create a relation"))
            menu.append(item)

            sm=gtk.Menu()
            for rt in relationtypes:
                sitem=gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                sitem.connect('activate', create_relation, source, dest, rt)
                sm.append(sitem)
            if True:
                # Propose to create a new one
                sitem=gtk.MenuItem(_("Create a new relation-type."), use_underline=False)
                sitem.connect('activate', create_relation_type_and_relation, source, dest)
                sm.append(sitem)
            item.set_submenu(sm)

            # Propose to merge annotations of same type, or of
            # different types but with same fragments.
            # In both cases, we will merge the data.
            if source.type == dest.type or (source.begin == dest.begin and source.end == dest.end):
                ok=True
                if source.relations:
                    ok=False
                    #we should maybe accept it and delete relations.
                elif source.type == dest.type:
                    b=min(source.begin, dest.begin)
                    e=max(source.begin, dest.begin)
                    for a in source.type.annotations:
                        if a.begin > b and a.begin < e:
                            # There is at least one annotation between
                            # the merged annotations.
                            ok=False
                            break
                if ok:
                    def merge_annotations(widget, s, d):
                        self.controller.merge_annotations(s, d, extend_bounds=(s.type == d.type))
                        return True
                    item=gtk.MenuItem(_("Merge with this annotation"))
                    item.connect('activate', merge_annotations, source, dest)
                    menu.append(item)

            def align_annotations(item, s, d, m):
                self.align_annotations(s, d, m)
                return True

            for (title, mode, condition) in (
                (_("Align both begin times"), 'begin-begin', dest.begin <= source.end),
                (_("Align both end times"), 'end-end', dest.end >= source.begin),
                (_("Align end time to selected begin time"), 'end-begin', dest.begin >= source.begin),
                (_("Align begin time to selected end time"), 'begin-end', dest.end <= source.end),
                (_("Align all times"), 'align', True),
                ):
                if not condition:
                    continue
                item=gtk.ImageMenuItem(title)
                im=gtk.Image()
                im.set_from_file(config.data.advenefile( ( 'pixmaps', mode + '.png') ))
                item.set_image(im)
                item.connect('activate', align_annotations, source, dest, mode)
                menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        elif targetType == config.data.target_type['tag']:
            tags=unicode(selection.data, 'utf8').split(',')
            a=widget.annotation
            l=[t for t in tags if not a.has_tag(t) ]
            self.controller.notify('ElementEditBegin', element=a, immediate=True)
            for t in l:
                self.controller.package.associate_user_tag(a, t)
            self.controller.notify('AnnotationEditEnd', annotation=a)
            self.controller.notify('ElementEditCancel', element=a)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def type_drag_sent(self, widget, context, selection, targetType, eventTime):
        #print "drag_sent event from %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation-type']:
            selection.set(selection.target, 8, widget.annotationtype.uriref.encode('utf8'))
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def move_or_copy_annotations(self, sources, dest, position=None, action=gtk.gdk.ACTION_ASK):
        """Display a popup menu to move or copy the sources annotation to the dest annotation type.

        If position is given (in ms), then the choice will also be
        offered to move/copy the annotation and change its bounds.

        If action is specified, then the popup menu will be shortcircuited.
        """
        if not sources:
            return True
        source=sources[0]

        def move_annotation(i, an, typ, position=None):
            # FIXME: how to check an.relations?
            if an.relations and an.type != typ:
                dialog.message_dialog(_("Cannot delete the annotation : it has relations."),
                                      icon=gtk.MESSAGE_WARNING)
                return True

            self.transmuted_annotation=self.controller.transmute_annotation(an,
                                                                            typ,
                                                                            delete=True,
                                                                            position=position)
            return self.transmuted_annotation

        def copy_annotation(i, an, typ, position=None, relationtype=None):
            self.transmuted_annotation=self.controller.transmute_annotation(an,
                                                                            typ,
                                                                            delete=False,
                                                                            position=position)
            # Widget creation is done by the event notification,
            # which cannot (except by chance) have executed yet.
            # So store the annotation ref in self.transmuted_annotation,
            # and handle this code in update_annotation()
            # b=self.get_widget_for_annotation(an)
            # b.grab_focus()
            if relationtype is not None:
                # Directly create a relation
                self.create_relation(an, self.transmuted_annotation, relationtype)
            return self.transmuted_annotation

        def copy_selection(i, sel, typ, delete=False):
            for an in sel:
                # FIXME: if sel.typ == an.typ
                self.transmuted_annotation=self.controller.transmute_annotation(an,
                                                                                typ,
                                                                                delete=delete)
            self.unselect_all()
            return self.transmuted_annotation

        # If there are compatible relation-types, propose to directly create a relation
        relationtypes=helper.matching_relationtypes(self.controller.package,
                                                    source.type,
                                                    dest)

        if action == gtk.gdk.ACTION_COPY:
            # Direct copy
            if len(sources) > 1:
                if source.type == dest:
                    return True
                copy_selection(None, sources, dest)
            else:
                if source.type == dest:
                    position=position
                else:
                    position=None
                copy_annotation(None, source, dest, position=position)
            return True
        elif action == gtk.gdk.ACTION_MOVE:
            if len(sources) > 1:
                if source.type == dest:
                    return True
                copy_selection(None, sources, dest, delete=True)
            else:
                if source.type == dest:
                    position=position
                else:
                    position=None
                move_annotation(None, source, dest, position=position)
            return True
        elif action == gtk.gdk.ACTION_LINK:
            # Copy and create a relation. Ignore the selection (?)
            if len(relationtypes) == 1:
                copy_annotation(None, source, dest, relationtype=relationtypes[0])
            elif not relationtypes:
                # Create a new relationtype
                self.log("FIXME: no valid relation type is defined")
            else:
                # Multiple valid relationtypes.
                menu=gtk.Menu()
                item=gtk.MenuItem(_("Select the appropriate relation type"))
                menu.append(item)
                item.set_sensitive(False)
                for rt in relationtypes:
                    sitem=gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                    sitem.connect('activate', copy_annotation, source, dest, None, rt)
                    menu.append(sitem)
                menu.show_all()
                menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True

        # ACTION_ASK: Popup a menu to propose the drop options
        menu=gtk.Menu()

        dest_title=self.controller.get_title(dest)

        if len(sources) > 1:
            if source.type == dest:
                return True
            item=gtk.MenuItem(_("Duplicate selection to type %s") % dest_title, use_underline=False)
            item.connect('activate', copy_selection, sources, dest)
            menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True

        if source.type != dest:
            item=gtk.MenuItem(_("Duplicate annotation to type %s") % dest_title, use_underline=False)
            item.connect('activate', copy_annotation, source, dest)
            menu.append(item)

            item=gtk.MenuItem(_("Move annotation to type %s") % dest_title, use_underline=False)
            item.connect('activate', move_annotation, source, dest)
            menu.append(item)
            if source.relations:
                item.set_sensitive(False)

        if position is not None and abs(position-source.fragment.begin) > 1000:
            item=gtk.MenuItem(_("Duplicate to type %(type)s at %(position)s") % {
                    'type': dest_title,
                    'position': helper.format_time(position) }, use_underline=False)
            item.connect('activate', copy_annotation, source, dest, position)
            menu.append(item)

            item=gtk.MenuItem(_("Move to type %(type)s at %(position)s") % {
                        'type': dest_title,
                        'position': helper.format_time(position) }, use_underline=False)
            item.connect('activate', move_annotation, source, dest, position)
            menu.append(item)
            if source.relations and source.type != dest:
                item.set_sensitive(False)

        if relationtypes:
            if source.type != dest:
                item=gtk.MenuItem(_("Duplicate and create a relation"), use_underline=False)
                # build a submenu
                sm=gtk.Menu()
                for rt in relationtypes:
                    sitem=gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                    sitem.connect('activate', copy_annotation, source, dest, None, rt)
                    sm.append(sitem)
                menu.append(item)
                item.set_submenu(sm)

            if position is not None:
                item=gtk.MenuItem(_("Duplicate at %s and create a relation") % helper.format_time(position), use_underline=False)
                # build a submenu
                sm=gtk.Menu()
                for rt in relationtypes:
                    sitem=gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                    sitem.connect('activate', copy_annotation, source, dest, position, rt)
                    sm.append(sitem)
                menu.append(item)
                item.set_submenu(sm)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())

    def copy_annotation_type(self, source, dest):
        """Display a popup menu to copy the source annotation type to the dest annotation type.
        """
        def copy_annotations(i, at, typ, delete=False):
            # More than 50 annotations takes too much time to notify
            # individually. In this case, deactive individual
            # notifications and notify an UpdateModel at the end
            notify=not len(at.annotations) > 50
            for an in at.annotations:
                self.transmuted_annotation=self.controller.transmute_annotation(an,
                                                                                typ,
                                                                                delete=delete,
                                                                                notify=notify)
            if not notify:
                 self.controller.notify('PackageActivate', package=self.controller.package)
            return self.transmuted_annotation

        def copy_annotations_filtered(i, at, typ, delete=False):
            s=dialog.entry_dialog(title=_("Annotation filter"),
                                  text=_("Enter the searched string"))
            if s:
                for an in at.annotations:
                    if s in an.content.data:
                        self.transmuted_annotation=self.controller.transmute_annotation(an,
                                                                                        typ,
                                                                                        delete=delete)
            return self.transmuted_annotation

        # Popup a menu to propose the drop options
        menu=gtk.Menu()

        if source != dest:
            item=gtk.MenuItem(_("Duplicate all annotations to type %s") % self.controller.get_title(dest), use_underline=False)
            item.connect('activate', copy_annotations, source, dest, False)
            menu.append(item)
            item=gtk.MenuItem(_("Move all annotations to type %s") % self.controller.get_title(dest), use_underline=False)
            item.connect('activate', copy_annotations, source, dest, True)
            menu.append(item)

            item=gtk.MenuItem(_("Duplicate all annotations matching a string to type %s") % self.controller.get_title(dest), use_underline=False)
            item.connect('activate', copy_annotations_filtered, source, dest, False)
            menu.append(item)
            item=gtk.MenuItem(_("Move all annotations matching a string to type %s") % self.controller.get_title(dest), use_underline=False)
            item.connect('activate', copy_annotations_filtered, source, dest, True)
            menu.append(item)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())

    def annotation_type_drag_received_cb(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
            dest=widget.annotationtype
            self.move_or_copy_annotations(sources, dest)
        elif targetType == config.data.target_type['annotation-type']:
            # Copy annotations
            source=self.controller.package.get(unicode(selection.data, 'utf8'))
            if not source:
                return True
            dest=widget.annotationtype
            self.copy_annotation_type(source, dest)
        elif targetType == config.data.target_type['color']:
            # Got a color
            # The structure consists in 4 unsigned shorts: r, g, b, opacity
            (r, g, b, opacity)=struct.unpack('HHHH', selection.data)
            widget.annotationtype.color=u"string:#%04x%04x%04x" % (r, g, b)
            self.controller.notify('AnnotationTypeEditEnd', annotationtype=widget.annotationtype)
        elif targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.data)
            begin=long(data['timestamp'])
            content=data.get('comment', None)
            # Create an annotation with the timestamp as begin
            self.create_annotation(begin, widget.annotationtype, content=content)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def new_annotation_type_drag_received_cb(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
            # Create a type
            dest=self.create_annotation_type()
            if dest is None:
                return True

            self.move_or_copy_annotations(sources, dest)
            return True
        elif targetType == config.data.target_type['timestamp']:
            typ=self.create_annotation_type()
            if typ is not None:
                data=decode_drop_parameters(selection.data)
                begin=long(data['timestamp'])
                content=data.get('comment', None)
                # Create an annotation of type typ with the timestamp as begin
                self.create_annotation(begin, typ, content=content)
        return False

    def legend_drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop from an annotation-type to the legend
        """
        if targetType == config.data.target_type['annotation-type']:
            source=self.controller.package.get(unicode(selection.data, 'utf8'))
            # We received a drop. Determine the location.
            s = config.data.preferences['timeline']['interline-height']

            # Correct y value according to scrollbar position
            y += widget.parent.get_vscrollbar().get_adjustment().get_value()

            f=[ at
                for (at, p) in self.layer_position.iteritems()
                if (y - s >= p and y - s <= p + self.button_height) ]
            t=[ at
                for (at, p) in self.layer_position.iteritems()
                if (y + s >= p and y + s <= p + self.button_height) ]
            if f and t and f[0] != source and t[0] != source:
                if source in self.annotationtypes:
                    self.annotationtypes.remove(source)
                j=self.annotationtypes.index(f[0])
                l=self.annotationtypes[:j+1]
                l.append(source)
                l.extend(self.annotationtypes[j+1:])
                self.annotationtypes=l
                self.update_model(partial_update=True)
            elif y < self.button_height + s:
                # Drop at the beginning of the list.
                if source in self.annotationtypes:
                    if self.annotationtypes.index(source) == 0:
                        return True
                    self.annotationtypes.remove(source)
                l=[ source ]
                l.extend(self.annotationtypes)
                self.annotationtypes=l
                self.update_model(partial_update=True)
            elif y > max(self.layer_position.values() or (0,)):
                # Drop at the end of the list
                if source in self.annotationtypes:
                    if self.annotationtypes.index(source) == len(self.annotationtypes) - 1:
                        return True
                    self.annotationtypes.remove(source)
                self.annotationtypes.append(source)
                self.update_model(partial_update=True)
            return True
        return False

    def annotation_button_release_cb(self, widget, event, annotation):
        """Handle button release on annotation widgets.
        """
        if self.options['goto-on-click'] and event.button == 1 and widget._single_click_guard:
            self.controller.gui.set_current_annotation(annotation)
            # Goto annotation if not already playing it
            p=self.controller.player.current_position_value
            # We do not use 'p in annotation.fragment' since if we are
            # at the end of the annotation, we may want to go back to its beginning
            if p >= annotation.begin and p < annotation.end:
                return True

            c=self.controller
            pos = c.create_position (value=annotation.begin,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            self.controller.update_status (status="set", position=pos)
            if self.loop_toggle_button.get_active():
                self.controller.gui.loop_on_annotation_gui(annotation)
            return True

    def annotation_button_press_cb(self, widget, event, annotation):
        """Handle button presses on annotation widgets.
        """
        widget._single_click_guard=False
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.annotation_cb(widget, annotation, event.x)
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.controller.gui.edit_element(annotation)
            return True
        elif event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS and event.state & gtk.gdk.CONTROL_MASK:
            # Control + click : set annotation begin/end time to current time
            f=self.annotation_fraction(widget)
            if f < .40:
                at='begin'
            elif f > .60:
                at='end'
            else:
                return False
            self.controller.notify('ElementEditBegin', element=annotation, immediate=True)
            setattr(annotation, at, long(self.controller.player.current_position_value))
            if annotation.begin > annotation.end:
                annotation.begin, annotation.end = annotation.end, annotation.begin
            self.controller.notify('AnnotationEditEnd', annotation=annotation)
            self.controller.notify('ElementEditCancel', element=annotation)
            return True
        elif (event.button == 1
              and event.type == gtk.gdk.BUTTON_PRESS
              and event.state & gtk.gdk.SHIFT_MASK):
            # Shift-click: toggle annotation selection/activation
            if widget.active:
                self.desactivate_annotation (annotation, buttons=[ widget ])
            else:
                self.activate_annotation (annotation, buttons=[ widget ])
            return True
        elif event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS:
            widget._single_click_guard=True
            return True
        return False

    def quick_edit(self, annotation, button=None, callback=None, move_cursor=False):
        """Quickly edit a textual annotation

        If defined, the callback method will be called with 'validate'
        or 'cancel' as first parameter and the annotation as second parameter.
        """
        if button is None:
            button=self.get_widget_for_annotation(annotation)
        if button is None:
            return False

        def close_editbox(widget, *p):
            widget.destroy()
            button.grab_focus()
            return True

        e=gtk.Entry()
        # get_title will either return the content data, or the computed representation
        e.set_text(self.controller.get_title(annotation))
        e.set_activates_default(True)

        def get_parsed_content(widget, ann):
            """Return the appropriate data generated from the widget content.
            """
            rep=ann.type.representation
            if rep is None or rep == '' or re.match('^\s+', rep):
                r=widget.get_text()
            else:
                m=parsed_representation.match(rep)
                if m:
                    # We have a simple representation (here/content/parsed/name)
                    # so we can update the name field.
                    name=m.group(1)
                    reg = re.compile('^' + name + '=(.+?)$', re.MULTILINE)
                    if reg.match(ann.content.data):
                        r = reg.sub(name + '=' + widget.get_text().replace('\n', '\\n'), ann.content.data)
                    else:
                        # The key is not present, add it
                        if ann.content.data:
                            r = ann.content.data + "\n%s=%s" % (name,
                                                                widget.get_text().replace('\n', '\\n'))
                        else:
                            r = "%s=%s" % (name,
                                           widget.get_text().replace('\n', '\\n'))
                else:
                    self.controller.log("Cannot update the annotation, its representation is too complex")
                    r=ann.content.data
            return r

        def key_handler(widget, event, ann, cb, controller, close_eb):
            if event.keyval == gtk.keysyms.Return:
                r=get_parsed_content(widget, ann)
                if cb:
                    cb('validate', ann)
                if r != ann.content.data:
                    self.controller.notify('ElementEditBegin', element=ann, immediate=True)
                    ann.content.data = r
                    controller.notify('AnnotationEditEnd', annotation=ann)
                    self.controller.notify('ElementEditCancel', element=ann)
                close_eb(widget)
                return True
            elif event.keyval == gtk.keysyms.Escape:
                # Abort and close the entry
                if cb:
                    cb('cancel', ann)
                close_eb(widget)
                return True
            elif event.keyval == gtk.keysyms.Tab:
                # Validate the current annotation and go to the previous/next one
                r=get_parsed_content(widget, ann)
                if cb:
                    cb('validate', ann)
                if r != ann.content.data:
                    self.controller.notify('ElementEditBegin', element=ann, immediate=True)
                    ann.content.data = r
                    controller.notify('AnnotationEditEnd', annotation=ann)
                    self.controller.notify('ElementEditCancel', element=ann)
                # Navigate
                b=ann.begin
                if event.state & gtk.gdk.SHIFT_MASK:
                    # Previous.
                    l=[a
                       for a in ann.type.annotations
                       if a.end < b ]
                    # Sort in reverse order
                    l.sort(key=lambda a: a.begin, reverse=True)
                else:
                    l=[a
                       for a in ann.type.annotations
                       if a.begin > b ]
                    l.sort(key=lambda a: a.begin)
                if l:
                    # Edit the previous/next one
                    self.quick_edit(l[0], callback=cb, move_cursor=True)
                close_eb(widget)
                return True
            return False
        e.connect('key-press-event', key_handler, annotation, callback, self.controller, close_editbox)
        def grab_focus(widget, event=None, *p):
            widget.grab_focus()
            return False
        e.connect('enter-notify-event', grab_focus)

        e.show()

        # Put the entry on the layout
        al=button.get_allocation()
        button.parent.put(e, al.x, al.y)
        e.connect('size-allocate', grab_focus)
        # Keep the inspector window open on the annotation
        self.set_annotation(annotation)
        if move_cursor:
            d=gtk.gdk.display_get_default()
            x,y=button.window.get_deskrelative_origin()
            d.warp_pointer(d.get_default_screen(), x + 2, y + 2)
        return e

    def annotation_key_press_cb(self, widget, event, annotation):
        """Handle key presses on annotation widgets.
        """
        if widget.keypress(widget, event, annotation):
            return True

        if event.keyval == gtk.keysyms.Return and event.state & gtk.gdk.CONTROL_MASK:
            # Control-return: split at current player position
            self.controller.split_annotation(annotation, self.controller.player.current_position_value)
            return True
        elif event.keyval == gtk.keysyms.p:
            # Play
            f=self.annotation_fraction(widget)
            x, y = widget.get_pointer()
            if (x < 0 or y < 0
                or x > widget.allocation.width
                or y > widget.allocation.height):
                # We are outside the widget. Let the key_pressed_cb
                # callback from layout handle the key
                return False
            if f > .5:
                position=annotation.end
            else:
                position=annotation.begin
            c=self.controller
            pos = c.create_position (value=position,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            c.gui.set_current_annotation(annotation)
            return True
        elif event.keyval == gtk.keysyms.Return:
            # Quick edit
            self.quick_edit(annotation, button=widget)
            return True
        return False

    def deactivate_all(self):
        """Deactivate all annotations.
        """
        def desactivate(widget):
            try:
                if widget.active:
                    widget.set_active(False)
            except AttributeError:
                pass
            return False
        self.layout.foreach(desactivate)
        self.update_selection_button()
        return True

    def create_annotation_widget(self, annotation):
        if not annotation.type in self.layer_position:
            # The annotation is not displayed
            return None
        if annotation.begin > self.maximum or annotation.end < self.minimum:
            # Not displayed
            return None
        b = AnnotationWidget(annotation=annotation, container=self)
        # Put at a default position.
        self.layout.put(b, 0, 0)
        b.show()
        self.update_button(b)

        b.connect('key-press-event', self.annotation_key_press_cb, annotation)
        b.connect('button-press-event', self.annotation_button_press_cb, annotation)
        b.connect('button-release-event', self.annotation_button_release_cb, annotation)

        def deactivate_single_click_guard(wid, ctx):
            # Prevent a drag to generate a single-click event.
            wid._single_click_guard=False
            return False
        b.connect('drag-begin', deactivate_single_click_guard)

        b.connect('enter-notify-event', lambda b, e: b.grab_focus())

        def focus_out(widget, event):
            self.set_annotation(None)
            if self.options['display-relations']:
                self.relations_to_draw = []
                self.update_relation_lines()
            return False
        b.connect('focus-out-event', focus_out)

        def focus_in(button, event):
            self.set_annotation(button.annotation)
            if self.options['display-relations']:
                a=button.annotation
                # FIXME: how to get annotation.relations ?
                for r in []: # FIXMEbutton.annotation.relations:
                    # FIXME: handle more-than-binary relations
                    if r[0] != a:
                        b=self.get_widget_for_annotation(r[0])
                        if b:
                            # b may be None, if the related annotation is not displayed
                            self.relations_to_draw.append( (b, button, r) )
                    elif r[1] != a:
                        b=self.get_widget_for_annotation(r[1])
                        if b:
                            self.relations_to_draw.append( (button, b, r) )
                self.update_relation_lines()

            if (self.options['autoscroll'] and
                self.controller.player.status != self.controller.player.PlayingStatus):
                # Check if the annotation is not already visible
                a = self.adjustment
                start=a.value
                finish=a.value + a.page_size
                begin = self.unit2pixel(annotation.begin, absolute=True)
                if begin >= start and begin <= finish:
                    return False
                end = self.unit2pixel(annotation.end, absolute=True)
                if end >= start and end <= finish:
                    return False
                if begin <= start and end >= finish:
                    # The annotation bounds are off-screen anyway. Do
                    # not move.
                    return False
                self.scroll_to_annotation(button.annotation)
            return False
        b.connect('focus-in-event', focus_in)

        # The button can generate drags
        b.connect('drag-begin', self.annotation_drag_begin)

        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['annotation']
                          + config.data.drag_type['uri-list']
                          + config.data.drag_type['text-plain']
                          + config.data.drag_type['TEXT']
                          + config.data.drag_type['STRING']
                          + config.data.drag_type['timestamp']
                          + config.data.drag_type['tag']
                          ,
                          gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_ASK )
        # The button can receive drops (to create relations)
        b.connect('drag-data-received', self.annotation_drag_received)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation']
                        + config.data.drag_type['tag']
                        , gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_ASK )

        def annotation_drag_motion(widget, drag_context, x, y, timestamp):
            actions=drag_context.actions
            # Dragging an annotation. Set the default action to ASK.
            if (config.data.drag_type['annotation'][0][0] in drag_context.targets
                and not actions in ( gtk.gdk.ACTION_LINK, gtk.gdk.ACTION_COPY, gtk.gdk.ACTION_MOVE )):
                # No single action was selected. Force ASK
                drag_context.drag_status(gtk.gdk.ACTION_ASK, timestamp)
        b.connect('drag-motion', annotation_drag_motion)

        # Handle scroll actions
        def handle_scroll_event(button, event):
            if not (event.state & gtk.gdk.CONTROL_MASK):
                return False
            if event.state & gtk.gdk.SHIFT_MASK:
                i='second-scroll-increment'
            else:
                i='scroll-increment'

            if event.direction == gtk.gdk.SCROLL_DOWN:
                incr=-config.data.preferences[i]
            elif event.direction == gtk.gdk.SCROLL_UP:
                incr=config.data.preferences[i]

            fr=self.annotation_fraction(button)
            a=button.annotation

            self.controller.notify('ElementEditBegin', element=a, immediate=True)

            if event.state & gtk.gdk.SHIFT_MASK:
                a.begin += incr
                a.end += incr
            elif fr < .5:
                a.begin += incr
            elif fr >= .5:
                a.end += incr

            self.controller.notify('AnnotationEditEnd', annotation=a)
            self.controller.notify('ElementEditCancel', element=a)

            self.set_annotation(a)
            button.grab_focus()
            return True

        b.connect('scroll-event', handle_scroll_event)

        b.show_all()
        return b

    def populate (self):
        u2p = self.unit2pixel
        if self.list is None:
            l=self.controller.package.all.annotations
        else:
            l=self.list

        for annotation in l:
            self.create_annotation_widget(annotation)

        self.layout.set_size (u2p (self.maximum - self.minimum),
                              max(self.layer_position.values() or (0,))
                              + self.button_height + config.data.preferences['timeline']['interline-height'])

        self.scale_layout.set_size(u2p (self.maximum - self.minimum), 40)

    def draw_current_mark (self):
        u2p = self.unit2pixel

        red=gtk.gdk.color_parse('red2')
        a = GenericColorButtonWidget('layout_current_mark', container=self)
        a.default_size=(1, max(self.layer_position.values() or (0,)) + self.button_height)
        a.local_color=red
        a.alpha=.5
        self.current_marker = a
        a.mark = self.current_position
        a.pos = 0
        self.layout.put(a, u2p(a.mark, absolute=True), a.pos)
        a.show ()

        a = GenericColorButtonWidget('scale_layout_current_mark', container=self)
        a.default_size=(1, self.button_height)
        a.local_color=red
        a.alpha=.5
        self.current_marker_scale = a
        a.mark = self.current_position
        a.pos = 0
        self.scale_layout.put (a, u2p(a.mark, absolute=True), a.pos)
        a.show ()

    def update_current_mark (self, pos=None):
        u2p = self.unit2pixel
        if pos is None:
            pos = self.current_position
        else:
            self.current_position = pos
        p=u2p(pos, absolute=True)
        a = self.current_marker
        a.mark = pos
        self.layout.move (a, p, a.pos)

        a = self.current_marker_scale
        a.mark = pos
        self.scale_layout.move (a, p, a.pos)

    def update_position (self, pos):
        if pos is None:
            pos = self.current_position
        if (self.options['autoscroll'] == 1
            and self.controller.player.status == self.controller.player.PlayingStatus):
            self.center_on_position(pos)
        elif (self.options['autoscroll'] == 2
              and self.controller.player.status == self.controller.player.PlayingStatus):
            p=self.unit2pixel(pos, absolute=True)
            begin=self.adjustment.value
            end=begin + self.adjustment.page_size
            if p > end or p < begin:
                self.center_on_position(pos)
        self.update_current_mark (pos)
        return True

    def position_reset(self):
        # The position was reset. Deactive active annotations.
        self.deactivate_all()
        self.update_current_mark(self.minimum)
        return True

    def update_scale_screenshots(self, *p):
        """Redraw scale screenshots in case of zoom change or global pane position change.
        """
        if self.global_pane is None:
            return
        # Approximate the available space for screenshots, plus a margin
        height=self.global_pane.get_position() - 16

        # Transform it in the closest power of 2, it should help the image scaling (?)
        n=1
        while n < height:
            n = n << 1
        height=n >> 1

        ic=self.controller.gui.imagecache
        if ic is None:
            return True
        def display_image(widget, event, h, step):
            """Lazy-loading of images
            """
            widget.set_from_pixbuf(png_to_pixbuf (ic.get(widget.mark, epsilon=step/2), height=max(20, h)))
            widget.disconnect(widget.expose_signal)
            widget.expose_signal=None
            return False

        if abs(height - self.current_scale_height) > 10:
            # The position changed significantly. Update the display.
            self.current_scale_height=height
            self.scale_layout.set_size(self.unit2pixel(self.maximum, absolute=True), 25 + height)

            # Remove previous images
            def remove_image(w):
                if isinstance(w, gtk.Image):
                    self.scale_layout.remove(w)
                    return True
            self.scale_layout.foreach(remove_image)

            if height >= 16:
                # Big enough. Let's display screenshots.

                # Evaluate screenshot width.
                width=int(height * 4.0 / 3) + 5
                step = self.pixel2unit(width)
                t = self.minimum

                u2p=self.unit2pixel
                while t <= self.maximum:
                    # Draw screenshots
                    i=gtk.Image()
                    i.mark = t
                    i.expose_signal=i.connect('expose-event', display_image, height, step)
                    i.pos = 20
                    i.show()
                    self.scale_layout.put(i, u2p(i.mark, absolute=True), i.pos)

                    t += step

    def draw_marks (self):
        """Draw marks for stream positioning"""
        u2p = self.unit2pixel
        # We want marks every 110 pixels
        step = self.pixel2unit (110)
        t = self.minimum

        while t <= self.maximum:
            x = u2p(t, absolute=True)

            # Draw label
            l = gtk.Label ("|" + helper.format_time (t))
            l.mark = t
            l.pos = 1
            l.show()
            self.scale_layout.put (l, x, l.pos)
            t += step
        # Reset current_scale_height to force screenshots redraw
        self.current_scale_height=0
        self.update_scale_screenshots()

    def bounds (self):
        """Bounds of the list.

        Return a tuple corresponding to the min and max values of the
        list, in list units.
        """
        minimum=sys.maxint
        maximum=0
        if self.list is None:
            l=self.controller.package.all.annotations
        else:
            l=self.list
        for a in l:
            if a.begin < minimum:
                minimum = a.begin
            if a.end > maximum:
                maximum = a.end
        return minimum, maximum

    def layout_key_press_cb (self, win, event):
        """Handles key presses in the timeline background
        """
        # Process player shortcuts
        if self.controller.gui and self.controller.gui.process_player_shortcuts(win, event):
            return True

        if event.keyval >= 49 and event.keyval <= 57:
            # 1-9 keys set the zoom factor
            pos=self.get_middle_position()
            self.fraction_adj.value=1.0/pow(2, event.keyval-49)
            self.set_middle_position(pos)
            return True
        elif event.keyval == gtk.keysyms.plus and event.state & gtk.gdk.CONTROL_MASK:
            # Zoom in
            a=self.fraction_adj
            pos=self.get_middle_position()
            a.value=min(a.value + a.page_increment, a.upper)
            self.set_middle_position(pos)
        elif event.keyval == gtk.keysyms.plus and event.state & gtk.gdk.CONTROL_MASK:
            # Zoom out
            a=self.fraction_adj
            pos=self.get_middle_position()
            a.value=max(a.value - a.page_increment, a.lower)
            self.set_middle_position(pos)
        elif event.keyval == gtk.keysyms.e:
            if isinstance(self.quickview.annotation, Annotation):
                self.controller.gui.edit_element(self.quickview.annotation)
                return True
        elif event.keyval == gtk.keysyms.c:
            self.center_on_position(self.current_position)
            return True
        elif event.keyval == gtk.keysyms.p:
            # Play at the current position
            x, y = win.get_pointer()
            # Note: x is here relative to the visible portion of the window. Thus we must
            # add self.adjustment.value
            position=self.pixel2unit(self.adjustment.value + x, absolute=True)
            c=self.controller
            pos = c.create_position (value=position,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            return True
        return False

    def layout_drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop from an annotation to the layout.
        """
        if targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
            # We received a drop. Determine the location.

            # Correct y value according to scrollbar position
            y += widget.parent.get_vscrollbar().get_adjustment().get_value()

            a=[ at
                for (at, p) in self.layer_position.iteritems()
                if (y >= p and y <= p + self.button_height) ]
            if a:
                # Copy/Move to a[0]
                self.move_or_copy_annotations(sources, a[0], position=self.pixel2unit(self.adjustment.value + x, absolute=True), action=context.actions)
            else:
                # Maybe we should propose to create a new annotation-type ?
                # Create a type
                dest=self.create_annotation_type()
                if dest is None:
                    return True
                self.move_or_copy_annotations(sources, dest, position=self.pixel2unit(self.adjustment.value + x, absolute=True), action=context.actions)
            return True
        elif targetType == config.data.target_type['annotation-type']:
            source=self.controller.package.get(unicode(selection.data, 'utf8'))
            # We received a drop. Determine the location.
            a=[ at
                for (at, p) in self.layer_position.iteritems()
                if (y >= p and y <= p + self.button_height) ]
            if a:
                # Copy/Move to a[0]
                if source != a[0]:
                    self.copy_annotation_type(source, a[0])
                else:
                    # Create an annotation in the type.
                    self.create_annotation(position=self.pixel2unit(self.adjustment.value + x, absolute=True),
                                           type=source,
                                           duration=self.pixel2unit(context.get_source_widget().get_allocation().width),
                                           )
            else:
                # Maybe we should propose to create a new annotation-type ?
                # Create a type
                dest=self.create_annotation_type()
                if dest is None:
                    return True
                self.copy_annotation_type(source, dest)
            return True
        elif targetType == config.data.target_type['timestamp']:
            # We received a drop. Create an annotation.
            a=[ at
                for (at, p) in self.layer_position.iteritems()
                if (y >= p and y <= p + self.button_height) ]
            if a:
                typ=a[0]
            else:
                typ=self.create_annotation_type()
            if typ is not None:
                data=decode_drop_parameters(selection.data)
                begin=long(data['timestamp'])
                content=data.get('comment', None)
                # Create an annotation of type typ with the timestamp as begin
                self.create_annotation(begin, typ, content=content)
        else:
            print "Unknown target type for drop: %d" % targetType
        return False

    def scale_layout_button_press_cb(self, widget=None, event=None):
        """Handle mouse click in scale window.
        """
        # Note: event.(x|y) may be relative to a child widget, so
        # we must determine the pointer position
        x, y = widget.get_pointer()
        # Convert x, y (relative to the layout allocation) into
        # values relative to the whole layout size
        p=widget.get_parent()
        x=long(p.get_hadjustment().value + x)
        y=long(p.get_vadjustment().value + y)

        if event.button == 3:
            self.context_cb (timel=self, position=self.pixel2unit(x, absolute=True), height=y)
            return True
        elif event.button == 1:
            c=self.controller
            pos = c.create_position (value=self.pixel2unit(x, absolute=True),
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            return True
        return False

    def layout_button_press_cb(self, widget=None, event=None):
        """Handle mouse click in timeline window.
        """
        # Note: event.(x|y) may be relative to a child widget, so
        # we must determine the pointer position
        x, y = widget.get_pointer()
        # Convert x, y (relative to the layout allocation) into
        # values relative to the whole layout size
        p=widget.get_parent()
        x=long(p.get_hadjustment().value + x)
        y=long(p.get_vadjustment().value + y)

        if event.button == 3:
            self.context_cb (timel=self, position=self.pixel2unit(x, absolute=True), height=y)
            return True
        elif event.button == 1:
            if event.type == gtk.gdk._2BUTTON_PRESS:
                # Double click in the layout: in all cases, goto the position
                c=self.controller
                pos = c.create_position (value=self.pixel2unit(x, absolute=True),
                                         key=c.player.MediaTime,
                                         origin=c.player.AbsolutePosition)
                c.update_status (status="set", position=pos)
            else:
                # Store x, y coordinates, to be able to decide upon button release.
                self.layout_selection=[ [x, y], [None, None] ]
            return True
        return False

    def layout_button_release_cb(self, widget=None, event=None):
        """Handle mouse button release in timeline window.
        """
        if event.button == 1:
            # Left click button in the upper part of the layout
            # or double-click anywhere in the background
            # (timescale) will directly move the player.

            # Note: event.(x|y) may be relative to a child widget, so
            # we must determine the pointer position
            x, y = widget.get_pointer()
            # Convert x, y (relative to the layout allocation) into
            # values relative to the whole layout size
            p=widget.get_parent()
            x=long(p.get_hadjustment().value + x)
            y=long(p.get_vadjustment().value + y)

            if self.layout_selection[0][0] is None:
                # Some bug here, should not happen except in the case
                # of random interaction. Just simulate it was a click.
                self.layout_selection=[ [x, y], [x+1, y+1] ]
            # Normalize x1,x2,y1,y2
            x1=min(x, self.layout_selection[0][0])
            x2=max(x, self.layout_selection[0][0])
            y1=min(y, self.layout_selection[0][1])
            y2=max(y, self.layout_selection[0][1])
            # Remove the selection rectangle
            self.draw_selection_rectangle(invert=True)
            self.layout_selection=[ [None, None], [None, None] ]

            if (abs(x2-x1) > 10 and abs(y2-y1) > 5):
                # The cursor has been significantly moved. Consider it is a selection.
                if not (event.state & gtk.gdk.CONTROL_MASK or event.state & gtk.gdk.SHIFT_MASK):
                    # Control or shift was not held: it is a new selection.
                    self.unselect_all()

                res=[]
                for widget in self.layout.get_children():
                    if not isinstance(widget, AnnotationWidget):
                        continue
                    x=self.layout.child_get_property(widget, 'x')
                    y=self.layout.child_get_property(widget, 'y')
                    w,h=widget.window.get_size()
                    if ( x >= x1 and x + w <= x2
                         and y >= y1 and y + h <= y2):
                        self.activate_annotation(widget.annotation, buttons=[ widget ])
                        res.append(widget)

                if not res:
                    # No selected annotations. Propose to create a new one.
                    a=[ at
                        for (at, p) in self.layer_position.iteritems()
                        if (y1 >= p and y1 <= p + self.button_height) ]
                    if not a:
                        return True
                    at=a[0]
                    def create(i):
                        self.create_annotation(position=self.pixel2unit(x1, absolute=True),
                                               type=at,
                                               duration=self.pixel2unit(x2-x1))
                        return True

                    menu=gtk.Menu()
                    i=gtk.MenuItem(_("Create a new annotation"))
                    i.connect('activate', create)
                    menu.append(i)
                    menu.show_all()
                    menu.popup(None, None, None, 0, gtk.get_current_event_time())
                return True
        return False

    def draw_selection_rectangle(self, invert=False):
        drawable=self.layout.bin_window
        gc=drawable.new_gc(line_width=1, line_style=gtk.gdk.LINE_ON_OFF_DASH)

        if self.layout_selection[1][0] is not None:
            # Invert the previous selection
            #col=pixmap.get_colormap().alloc_color(self.color)
            if invert:
                gc.set_function(gtk.gdk.INVERT)
            else:
                gc.set_function(gtk.gdk.COPY)

            x1=min(self.layout_selection[0][0], self.layout_selection[1][0])
            x2=max(self.layout_selection[0][0], self.layout_selection[1][0])
            y1=min(self.layout_selection[0][1], self.layout_selection[1][1])
            y2=max(self.layout_selection[0][1], self.layout_selection[1][1])

            # Display the starting mark
            drawable.draw_rectangle(gc, False, x1, y1, x2-x1, y2-y1)
        return True

    # Draw rectangle during mouse movement
    def layout_motion_notify_cb(self, widget, event):
        if event.is_hint:
            x, y, state = event.window.get_pointer()
        else:
            x = event.x
            y = event.y
            state = event.state

        if state & gtk.gdk.BUTTON1_MASK:
            # Display current time
            self.set_annotation(self.pixel2unit(self.adjustment.value + x, absolute=True))
            if self.layout_selection[0][0] is None:
                return False
            if self.layout_selection[1][0] is not None:
                # Invert the previous selection
                self.draw_selection_rectangle(invert=True)
            self.layout_selection[1][0] = int(x)
            self.layout_selection[1][1] = int(y)
            # Draw the new shape
            self.draw_selection_rectangle(invert=False)
        return True

    def layout_drag_motion_cb(self, widget, drag_context, x, y, timestamp):
        t=self.pixel2unit(self.adjustment.value +  x, absolute=True)
        w=drag_context.get_source_widget()
        try:
            w._icon.set_cursor(t)
        except AttributeError:
            pass
        actions=drag_context.actions
        # Dragging an annotation. Set the default action to ASK.
        if (config.data.drag_type['annotation'][0][0] in drag_context.targets
            and not actions in ( gtk.gdk.ACTION_LINK, gtk.gdk.ACTION_COPY, gtk.gdk.ACTION_MOVE )):
            # No single action was selected. Force ASK
            drag_context.drag_status(gtk.gdk.ACTION_ASK, timestamp)
        return True

    def layout_drag_leave_cb(self, widget, drag_context, timestamp):
        w=drag_context.get_source_widget()
        try:
            w._icon.set_cursor()
        except AttributeError:
            pass
        return True

    def context_cb (self, timel=None, position=None, height=None):
        """Display the context menu for a right-click in the timeline window.
        """
        # This callback is called on a right-mouse-button press
        # in the timeline display. It is called with the
        # current position (in ms)
        menu = gtk.Menu()

        def popup_goto (win, position):
            c=self.controller
            pos = c.create_position (value=position,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            self.controller.update_status (status="set", position=pos)
            return True

        def create_annotation(win, position):
            # Determine annotation type
            at=None
            h=long(height)
            for a, p in self.layer_position.iteritems():
                if h >= p and h < p + self.button_height:
                    at=a
                    break
            if at is None:
                at=self.controller.package.all.annotation_types[0]
            self.create_annotation(position, at)
            return True

        item = gtk.MenuItem(_("Position %s") % helper.format_time(position))
        menu.append(item)

        item = gtk.SeparatorMenuItem()
        menu.append(item)

        item = gtk.MenuItem(_("Go to..."))
        item.connect('activate', popup_goto, position)
        menu.append(item)

        item = gtk.MenuItem(_("Create a new annotation"))
        item.connect('activate', create_annotation, position)
        menu.append(item)

        item = gtk.MenuItem(_("Selection"))
        if self.get_selected_annotation_widgets():
            item.set_submenu(self.selection_menu(popup=False))
        else:
            item.set_sensitive(False)
        menu.append(item)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def update_adjustment (self):
        """Update the adjustment values depending on the current aspect ratio.
        """
        u2p = self.unit2pixel
        a = self.adjustment

        width = self.maximum - self.minimum

        #a.value=u2p(minimum)
        a.lower=float(u2p(self.minimum, absolute=True))
        a.upper=float(u2p(self.maximum, absolute=True))
        a.step_increment=min(float(u2p(width / 100)), 10)
        a.page_increment=float(u2p(width / 10))
        a.page_size=min(a.upper, self.layout.get_allocation().width)
        #print "Update: from %.2f to %.2f" % (a.lower, a.upper)
        a.changed ()

    def scale_event (self, widget=None, data=None):
        self.update_adjustment ()

        # Update the layout and scale_layout dimensions
        width=self.unit2pixel(self.maximum - self.minimum)
        (w, h) = self.layout.get_size ()
        self.layout.set_size (width, h)
        (w, h) = self.scale_layout.get_size ()
        self.scale_layout.set_size (width, h)

        # Update the scale legend
        dur=self.pixel2unit(110) / 1000.0
        self.scale_label.set_text('1mark=\n%dm%.02fs' % (int(dur / 60), dur % 60))
        self.redraw_event ()
        return True

    def layout_resize_event(self, widget=None, event=None, *p):
        """Recompute fraction_adj value when the layout size changes
        """
        parent = self.layout.window
        if not parent:
            return False
        (w, h) = parent.get_size ()
        if self.maximum != self.minimum:
            fraction=self.scale.value * float(w) / (self.maximum - self.minimum)
            #print "Layout resize, reset fraction_adj to ", fraction, w
            self.fraction_adj.value=fraction
            self.zoom_combobox.child.set_text('%d%%' % long(100 * fraction))
        return False

    def limit_display(self, *p):
        """Limit the timeline to the currently displayed area.
        """
        mi=self.pixel2unit(self.adjustment.value, absolute=True)
        ma=self.pixel2unit(self.adjustment.value + self.adjustment.page_size, absolute=True)
        # Cannot do the assignment immediately, since unit2pixel uses self.minimum
        self.minimum = mi
        self.maximum = ma
        self.update_model(partial_update=True)
        self.fraction_adj.value=1.0
        return True

    def unlimit_display(self, *p):
        self.minimum=0
        self.maximum=self.controller.cached_duration
        if not self.maximum:
            # self.maximum == 0, so try to compute it
            self.maximum = self.bounds()[1]
        if not self.maximum:
            # Not valid data either. Use a default value.
            self.maximum=42000
        self.update_model(partial_update=True)
        self.fraction_adj.value=1.0
        return True

    def fraction_event (self, widget=None, *p):
        """Set the zoom factor to display the given fraction of the movie.

        fraction is > 0 and <= 1.
        """
        parent = self.layout.window
        if not parent:
            return True
        (w, h) = parent.get_size ()

        if w < 2:
            return True

        if self.minimum == self.maximum:
            return True

        fraction=self.fraction_adj.value
        v = (self.maximum - self.minimum) / float(w) * fraction
        # New width in pixel
        if v < 5 or (self.maximum - self.minimum) / v > 65535:
            self.log(_("Cannot zoom more"))
            return True

        # Is it worth redrawing the whole timeline ?
        if abs(v - self.scale.value) / float(self.scale.value) > 0.01:
            self.scale.set_value(v)
        self.zoom_combobox.child.set_text('%d%%' % long(100 * fraction))

        return True

    def layout_scroll_cb(self, widget=None, event=None):
        """Handle mouse scrollwheel events.
        """
        zoom=event.state & gtk.gdk.CONTROL_MASK
        if zoom:
            # Control+scroll: zoom in/out
            a = self.fraction_adj
            incr = a.page_increment
            # Memorize mouse position (in units)
            # Get x, y (relative to the layout allocation)
            x,y=widget.get_pointer()
            mouse_position=self.pixel2unit(event.x, absolute=True)
        else:
            # Plain scroll: scroll the timeline
            a = self.adjustment
            incr = a.step_increment

        if event.direction == gtk.gdk.SCROLL_DOWN:
            val = a.value + incr
            if val > a.upper - a.page_size:
                val = a.upper - a.page_size
            if val != a.value:
                a.value = val

        elif event.direction == gtk.gdk.SCROLL_UP:
            val = a.value - incr
            if val < a.lower:
                val = a.lower
            if val != a.value:
                a.value = val

        # Try to preserve the mouse position when zooming
        if zoom:
            self.adjustment.value=self.unit2pixel(mouse_position, absolute=True) - x
        return True

    def redraw_event(self, widget=None, data=None):
        """Redraw the layout according to the new ratio value.
        """
        def move_widget (w=None):
            """Update the annotation widget position.
            """
            if isinstance(w, AnnotationWidget):
                w.update_widget()
                self.layout.move (w,
                                  self.unit2pixel(w.annotation.begin, absolute=True),
                                  self.layer_position[w.annotation.type])
            return True

        if self.old_scale_value != self.scale.value:
            self.old_scale_value = self.scale.value
            # Reposition all buttons
            self.layout.foreach(move_widget)
            self.layout.remove(self.current_marker)
            # Redraw marks
            self.scale_layout.foreach(self.scale_layout.remove)
            self.draw_marks ()
            # Redraw current mark
            self.draw_current_mark ()
            return True
        return False

    def resize_legend_widget(self, layout):
        width=0
        height=0
        for c in layout.get_children():
            if not isinstance(c, AnnotationTypeWidget):
                continue
            width=max(width, c.width)

        def resize(b, w):
            if isinstance(b, AnnotationTypeWidget):
                b.width=w
                b.update_widget()
            return True

        def move_nav(b, w):
            """Move next and prev navigation buttons.
            """
            y=layout.child_get_property(b, 'y')
            if hasattr(b, 'next'):
                layout.move(b, w + 32 , y)
            elif hasattr(b, 'prev'):
                layout.move(b, w + 20, y)
            return True

        # Resize all buttons to fit the largest
        if width > 10:
            layout.foreach(resize, width)
            # Reposition the next, prev buttons
            layout.foreach(move_nav, width)

        layout.get_parent().get_parent().set_position (width + 30)

    def restrict_playing(self, at, widget=None):
        """Restrict playing to the given annotation-type.

        Widget should be the annotation-type widget for at.
        """
        if widget is None:
            l=[ w
                for w in self.legend.get_children()
                if isinstance(w, AnnotationTypeWidget) and w.annotationtype == at ]
            if l:
                widget=l[0]
        # Restrict playing to this annotation-type
        if widget is not None and widget.playing:
            # toggle the playing state
            self.controller.restrict_playing(None)
        else:
            if self.list is None:
                # We are displaying the whole package. Do not further specify annotations.
                self.controller.restrict_playing(at)
            else:
                # We are displaying a subset. Specify the desired annotations.
                self.controller.restrict_playing(at, annotations=[ a for a in self.list if a.type == at ])
        return True

    def update_legend_widget(self, layout):
        """Update the legend widget.

        Its content may have changed.
        """
        width=0
        height=0

        def navigate(b, event, direction, typ):
            p=self.controller.player.current_position_value
            if direction == 'next':
                l=[a.begin
                   for a in typ.annotations
                   if a.begin > p ]
                l.sort()
            else:
                l=[a.begin
                   for a in typ.annotations
                   if a.end < p ]
                # Sort in reverse order
                l.sort(reverse=True)
            if l:
                self.controller.update_status("set", position=l[0])
            return True

        def restrict_playing(m, at, w):
            self.restrict_playing(at, w)
            return True

        def annotationtype_keypress_handler(widget, event, at):
            if widget.keypress(widget, event, at):
                return True
            elif event.keyval == gtk.keysyms.Return:
                def set_end_time(action, an):
                    if action == 'validate':
                        an.fragment.end=self.controller.player.current_position_value
                    elif action == 'cancel':
                        # Delete the annotation
                        self.controller.notify('ElementEditBegin', element=an, immediate=True)
                        self.controller.package.annotations.remove(an)
                        self.controller.notify('AnnotationDelete', annotation=an)
                    return True

                if (self.controller.player.status != self.controller.player.PlayingStatus
                    and self.controller.player.status != self.controller.player.PauseStatus):
                    return True
                # Create a new annotation
                el=self.create_annotation(position=long(self.controller.player.current_position_value),
                                       type=widget.annotationtype,
                                       duration=3000)
                if el is not None:
                    b=self.create_annotation_widget(el)
                    b.show()
                    self.quick_edit(el, button=widget, callback=set_end_time)
                return True
            elif event.keyval == gtk.keysyms.space:
                self.restrict_playing(at, widget)
                return True
            return False

        def annotationtype_buttonpress_handler(widget, event, t):
            """Display the popup menu when right-clicking on annotation type.
            """
            if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
                menu=advene.gui.popup.Menu(t, controller=self.controller)
                menu.popup()
                return True
            return False

        for t in self.annotationtypes:
            b=AnnotationTypeWidget(annotationtype=t, container=self)
            layout.put (b, 20, self.layer_position[t])
            b.update_widget()
            b.show_all()
            b.connect('key-press-event', annotationtype_keypress_handler, t)
            b.connect('button-press-event', annotationtype_buttonpress_handler, t)

            # FIXME: no more schema ?
            #self.tooltips.set_tip(b, _("From schema %s") % self.controller.get_title(t.schema))
            #def focus_in(button, event):
            #    for w in layout.get_children():
            #        if isinstance(w, AnnotationTypeWidget) and w.annotationtype.schema == button.annotationtype.schema:
            #            w.set_highlight(True)
            #    return False
            #
            #def focus_out(button, event):
            #    for w in layout.get_children():
            #        if isinstance(w, AnnotationTypeWidget) and w.highlight:
            #            w.set_highlight(False)
            #    return False
            #
            #b.connect('focus-in-event', focus_in)
            #b.connect('focus-out-event', focus_out)

            # The button can receive drops (to transmute annotations)
            b.connect('drag-data-received', self.annotation_type_drag_received_cb)
            b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                            gtk.DEST_DEFAULT_HIGHLIGHT |
                            gtk.DEST_DEFAULT_ALL,
                            config.data.drag_type['annotation'] +
                            config.data.drag_type['annotation-type'] +
                            config.data.drag_type['timestamp'] +
                            config.data.drag_type['color'],
                            gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE)
            # The button can generate drags (to change annotation type order)
            b.connect('drag-data-get', self.type_drag_sent)
            b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['annotation-type'], gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_LINK)

            height=max (height, self.layer_position[t] + 3 * self.button_height)

            def set_playing(b, v):
                if v:
                    f='noplay.png'
                else:
                    f='play.png'
                b.get_children()[0].set_from_file(config.data.advenefile( ( 'pixmaps', f) ))
                return True

            # At the left of the annotation type : restrict_playing button
            p=get_pixmap_button('play.png', restrict_playing, t, b)
            p.set_playing = set_playing.__get__(p)
            p.annotationtype=t
            p.set_size_request(20, self.button_height)
            self.tooltips.set_tip(p, _('Restrict playing to this annotation-type'))
            layout.put (p, 0, self.layer_position[t])

            # At the right of the annotation type : prev/next buttons
            nav=gtk.Arrow(gtk.ARROW_LEFT, gtk.SHADOW_IN)
            nav.set_size_request(16, self.button_height)
            nav.annotationtype=t
            self.tooltips.set_tip(nav, _('Goto previous annotation'))
            eb=gtk.EventBox()
            eb.connect('button-press-event', navigate, 'prev', t)
            eb.add(nav)
            eb.prev=True
            # Put it in an arbitrary location. It will be moved by resize_legend_widget
            layout.put (eb, 102, self.layer_position[t])

            nav=gtk.Arrow(gtk.ARROW_RIGHT, gtk.SHADOW_IN)
            nav.set_size_request(16, self.button_height)
            nav.annotationtype=t
            self.tooltips.set_tip(nav, _('Goto next annotation'))
            eb=gtk.EventBox()
            eb.connect('button-press-event', navigate, 'next', t)
            eb.add(nav)
            eb.next=True
            # Put it in an arbitrary location. It will be moved by resize_legend_widget
            layout.put (eb, 112, self.layer_position[t])

        # Add the 'New type' button at the end
        b=gtk.Button()
        l=gtk.Label()
        l.set_markup('<b><span style="normal">%s</span></b>' % _('+'))
        l.modify_font(self.annotation_type_font)
        b.add(l)
        self.tooltips.set_tip(b, _('Create a new annotation type'))
        b.set_size_request(-1, self.button_height)
        layout.put (b, 0, height - 2 * self.button_height + config.data.preferences['timeline']['interline-height'])
        b.annotationtype=None
        b.show()

        b.connect('clicked', self.create_annotation_type)
        # The button can receive drops (to create type and transmute annotations)
        b.connect('drag-data-received', self.new_annotation_type_drag_received_cb)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation']
                        + config.data.drag_type['timestamp'],
                        gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE)

        layout.set_size (width + 20, height)
        self.resize_legend_widget(layout)
        return

    def get_full_widget(self):
        """Return the layout with its controllers.
        """
        vbox = gtk.VBox()
        vbox.connect('key-press-event', self.layout_key_press_cb)

        hb=gtk.HBox()
        toolbar = self.get_toolbar()
        hb.add(toolbar)

        self.quickview=QuickviewBar(self.controller)

        # The annotation view button should be placed in the toolbar,
        # but this prevents DND from working correctly.
        def drag_sent(widget, context, selection, targetType, eventTime, name):
            if targetType == config.data.target_type['adhoc-view']:
                selection.set(selection.target, 8,
                              cgi.urllib.urlencode( {
                            'name': name,
                            'master': self.controller.gui.get_adhoc_view_instance_id(self),
                            } ).encode('utf8'))
                return True
            return False

        def open_annotation_display(b, *p):
            v=self.controller.gui.open_adhoc_view('annotationdisplay')
            v.set_master_view(self)
            return True

        def open_slave_montage(b, *p):
            v=self.controller.gui.open_adhoc_view('montage')
            v.set_master_view(self)
            return True

        b=get_small_stock_button(gtk.STOCK_FIND, open_annotation_display)
        self.controller.gui.tooltips.set_tip(b, _('Open an annotation display view'))
        b.connect('drag-data-get', drag_sent, 'annotationdisplay')
        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)
        hb.pack_start(b, expand=False)

        b=get_pixmap_button('montage.png', open_slave_montage)
        self.controller.gui.tooltips.set_tip(b, _('Open a slave montage view (coordinated zoom level)'))
        b.connect('drag-data-get', drag_sent, 'montage')
        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)
        hb.pack_start(b, expand=False)

        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(self.player_toolbar)

        vbox.pack_start(hb, expand=False)

        vbox.add (self.get_packed_widget())

        vbox.pack_start(self.quickview, expand=False)

        return vbox

    def selection_menu(self, button=None, popup=True):
        """Display the menu for the selection.
        """
        def center_and_zoom(m, sel):
            begin=min( [ w.annotation.begin for w in sel ] )
            end=max( [ w.annotation.end for w in sel ] )

            # Deactivate autoscroll...
            self.set_autoscroll_mode(0)

            (w, h) = self.layout.window.get_size ()
            self.scale.value=1.3 * (end - begin) / w

            # Center on annotation
            self.center_on_position( (begin + end) / 2 )
            return True

        def create_static(m, sel):
            v=self.controller.create_static_view([ w.annotation for w in sel])
            if v is not None:
                self.controller.gui.edit_element(v)
            return True

        m=gtk.Menu()
        l=self.get_selected_annotation_widgets()
        n=len(l)
        if n == 0:
            i=gtk.MenuItem(_('No selected annotation'))
            m.append(i)
            i.set_sensitive(False)
        else:
            i=gtk.MenuItem(_('%d selected annotation(s)') % n)
            m.append(i)
            i.set_sensitive(False)
            i=gtk.SeparatorMenuItem()
            m.append(i)

            for (label, action) in (
                (_('Unselect all annotations'), self.unselect_all),
                (_('Create a static view'), create_static),
                (_('Highlight selection in other views'), self.selection_highlight),
                (_('Tag selection'), self.selection_tag),
                (_('Delete selected annotations'), self.selection_delete),
                (_('Display selection in a table'), self.selection_as_table),
                (_('Center and zoom on selection'), center_and_zoom),
                (_('Edit selected annotations'), self.selection_edit),
                (_('Merge annotations'), self.selection_merge),
                ):
                i=gtk.MenuItem(label)
                i.connect('activate', action, l)
                m.append(i)

        m.show_all()
        if popup:
            m.popup(None, None, None, 0, gtk.get_current_event_time())
        return m

    def get_packed_widget (self):
        """Return the widget packed into a scrolledwindow."""
        vbox = gtk.VBox ()

        content_pane = gtk.HPaned ()

        # The layout can receive drops
        self.legend.connect('drag-data-received', self.legend_drag_received)
        self.legend.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation-type'],
                                  gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK)

        sw_legend = gtk.ScrolledWindow ()
        sw_legend.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        sw_legend.set_placement(gtk.CORNER_TOP_RIGHT)
        sw_legend.add (self.legend)
        content_pane.add1 (sw_legend)

        # Vertical auto-scroll when DNDing
        def scroll_on_drag(widget, drag_context, x, y, timestamp, vertical=True):
            adj=widget.get_adjustment()
            v=adj.value
            if vertical:
                pointer=y
                ref=widget.get_allocation().height / 2
            else:
                pointer=x
                ref=widget.get_allocation().width / 2
            if pointer > ref:
                # Try to scroll down
                v += max(adj.step_increment, adj.page_increment / 3)
            else:
                v -= max(adj.step_increment, adj.page_increment / 3)
            if v < 0:
                v = 0
            elif v > adj.upper - adj.page_size:
                v=adj.upper - adj.page_size
            adj.value=v
            return True
        sb=sw_legend.get_vscrollbar()
        sb.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                         gtk.DEST_DEFAULT_HIGHLIGHT |
                         gtk.DEST_DEFAULT_ALL,
                         config.data.drag_type['annotation']
                         + config.data.drag_type['timestamp']
                         + config.data.drag_type['annotation-type']
                         ,
                         gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        sb.connect('drag-motion', scroll_on_drag, True)

        sw_layout = gtk.ScrolledWindow ()
        sw_layout.set_policy (gtk.POLICY_ALWAYS, gtk.POLICY_AUTOMATIC)
        sw_layout.set_hadjustment (self.adjustment)
        sw_layout.set_vadjustment (sw_legend.get_vadjustment())
        sw_layout.add (self.layout)
        content_pane.add2 (sw_layout)

        # Fix step_increment for vadjustment
        sw_layout.get_vadjustment().step_increment=10

        sb=sw_layout.get_hscrollbar()
        sb.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                         gtk.DEST_DEFAULT_HIGHLIGHT |
                         gtk.DEST_DEFAULT_ALL,
                         config.data.drag_type['annotation']
                         + config.data.drag_type['timestamp']
                         + config.data.drag_type['annotation-type']
                         ,
                         gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        sb.connect('drag-motion', scroll_on_drag, False)

        sb=sw_layout.get_vscrollbar()
        sb.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                         gtk.DEST_DEFAULT_HIGHLIGHT |
                         gtk.DEST_DEFAULT_ALL,
                         config.data.drag_type['annotation']
                         + config.data.drag_type['timestamp']
                         + config.data.drag_type['annotation-type']
                         ,
                         gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        sb.connect('drag-motion', scroll_on_drag)

        # Now build the scale_pane
        scale_pane = gtk.HPaned()
        self.scale_label = gtk.Label('Scale')
        scale_pane.add1(self.scale_label)

        sw_scale=gtk.ScrolledWindow()
        sw_scale.set_policy(gtk.POLICY_NEVER, gtk.POLICY_NEVER)
        sw_scale.set_hadjustment (sw_layout.get_hadjustment())
        sw_scale.add(self.scale_layout)
        scale_pane.add2(sw_scale)

        def synchronize_position(w, param):
            scale_pane.set_position(w.props.position)
            return False

        content_pane.connect('notify::position', synchronize_position)

        self.global_pane=gtk.VPaned()

        self.global_pane.add1(scale_pane)
        self.global_pane.add2(content_pane)

        self.global_pane.set_position(50)
        self.global_pane.connect('notify::position', self.update_scale_screenshots)

        vbox.add (self.global_pane)

        (w, h) = self.legend.get_size ()
        content_pane.set_position (max(w, 100))

        self.inspector_pane=gtk.HPaned()
        self.inspector_pane.pack1(vbox, resize=True, shrink=True)
        a=AnnotationDisplay(controller=self.controller)
        f=gtk.Frame(_('Inspector'))
        f.add(a.widget)
        self.inspector_pane.pack2(f, resize=False, shrink=True)
        self.controller.gui.register_view (a)
        a.set_master_view(self)
        a.widget.show_all()

        return self.inspector_pane

    def get_toolbar(self):
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
                if sources:
                    batch_id=object()
                    for a in sources:
                        self.controller.delete_element(a, batch_id=batch_id)
                return True
            return False

        b=gtk.ToolButton(stock_id=gtk.STOCK_DELETE)
        self.controller.gui.tooltips.set_tip(b, _('Delete the selected annotations or drop an annotation here to delete it.'))
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation'],
                        gtk.gdk.ACTION_MOVE )
        b.connect('drag-data-received', remove_drag_received)
        b.connect('clicked', self.selection_delete)
        tb.insert(b, -1)

        # Annotation-type selection button
        def annotationtype_selection_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation-type']:
                source=self.controller.package.get(unicode(selection.data, 'utf8'))
                if source in self.annotationtypes:
                    self.annotationtypes.remove(source)
                    self.update_model(partial_update=True)
            else:
                print 'Unknown target type for drop: %d' % targetType
            return True

        b=gtk.ToolButton(stock_id=gtk.STOCK_SELECT_COLOR)
        b.set_tooltip(self.tooltips, _('Drag an annotation type here to remove it from display.\nClick to edit all displayed types'))
        b.connect('clicked', self.edit_annotation_types)
        b.connect('drag-data-received', annotationtype_selection_drag_received)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation-type'],
                        gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
        tb.insert(b, -1)

        # Selection menu
        b=gtk.ToolButton()
        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'selection.png') ))
        b.set_icon_widget(i)
        b.set_tooltip(self.tooltips, _('Selection actions'))
        b.connect('clicked', self.selection_menu)
        tb.insert(b, -1)
        b.set_sensitive(False)
        self.selection_button=b

        # Relation display toggle
        def handle_toggle(b, option):
            self.options[option]=b.get_active()
            return True

        self.display_relations_toggle=gtk.ToggleToolButton(stock_id=gtk.STOCK_REDO)
        self.display_relations_toggle.set_tooltip(self.tooltips, _('Display relations'))
        self.display_relations_toggle.set_active(self.options['display-relations'])
        self.display_relations_toggle.connect('toggled', handle_toggle, 'display-relations')
        tb.insert(self.display_relations_toggle, -1)

        # Separator
        tb.insert(gtk.SeparatorToolItem(), -1)

        def zoom_entry(entry):
            f=entry.get_text()

            i=re.findall(r'\d+', f)
            if i:
                f=int(i[0])/100.0
            else:
                return True
            pos=self.get_middle_position()
            self.fraction_adj.value=f
            self.set_middle_position(pos)
            return True

        def zoom_change(combo):
            v=combo.get_current_element()
            if isinstance(v, float):
                pos=self.get_middle_position()
                self.fraction_adj.value=v
                self.set_middle_position(pos)
            return True

        def zoom(i, factor):
            pos=self.get_middle_position()
            self.fraction_adj.set_value(self.fraction_adj.value * factor)
            self.set_middle_position(pos)
            return True

        i=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_OUT)
        i.connect('clicked', zoom, 1.3)
        i.set_tooltip(self.tooltips, _('Zoom out'))
        tb.insert(i, -1)

        i=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_IN)
        i.connect('clicked', zoom, .7)
        i.set_tooltip(self.tooltips, _('Zoom in'))
        tb.insert(i, -1)

        self.zoom_combobox=dialog.list_selector_widget(members=[
                ( f, '%d%%' % long(100*f) )
                for f in [
                    (1.0 / pow(1.5, n)) for n in range(0, 10)
                    ]
                ],
                                                                entry=True,
                                                                callback=zoom_change)
        self.zoom_combobox.child.connect('activate', zoom_entry)
        self.zoom_combobox.child.set_width_chars(4)
        i=gtk.ToolItem()
        i.add(self.zoom_combobox)
        tb.insert(i, -1)

        i=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_100)
        i.connect('clicked', lambda i: self.fraction_adj.set_value(1.0))
        tb.insert(i, -1)

        tb.insert(gtk.SeparatorToolItem(), -1)

        i=gtk.ToolItem()
        i.add(self.autoscroll_choice)
        tb.insert(i, -1)

        def center_on_current_position(*p):
            if (self.controller.player.status == self.controller.player.PlayingStatus
                or self.controller.player.status == self.controller.player.PauseStatus):
                self.center_on_position(self.current_position)
            return True

        for tooltip, icon, callback in (
            (_('Preferences'), gtk.STOCK_PREFERENCES, self.edit_preferences),
            (_('Center on current player position.'), gtk.STOCK_JUSTIFY_CENTER, center_on_current_position),
            ):
            b=gtk.ToolButton(stock_id=icon)
            b.set_tooltip(self.tooltips, tooltip)
            b.connect('clicked', callback)
            tb.insert(b, -1)

        def loop_toggle_cb(b):
            if not b.get_active():
                # If we deactivate the locked looping feature, then also
                # disable the player loop toggle.
                self.controller.gui.loop_toggle_button.set_active(False)
            return True

        self.loop_toggle_button=gtk.ToggleToolButton(stock_id=gtk.STOCK_REFRESH)
        self.loop_toggle_button.connect('toggled', loop_toggle_cb)
        self.loop_toggle_button.set_tooltip(self.tooltips, _('Automatically activate loop when clicking on an annotation'))
        tb.insert(self.loop_toggle_button, -1)

        def goto_toggle_cb(b):
            self.options['goto-on-click']=b.get_active()
            return True

        self.goto_on_click_toggle=gtk.ToggleToolButton(stock_id=gtk.STOCK_GO_FORWARD)
        self.goto_on_click_toggle.set_active(self.options['goto-on-click'])
        self.goto_on_click_toggle.connect('toggled', goto_toggle_cb)
        self.goto_on_click_toggle.set_tooltip(self.tooltips, _('Goto annotation when clicking'))
        tb.insert(self.goto_on_click_toggle, -1)

        ti=gtk.SeparatorToolItem()
        ti.set_expand(True)
        ti.set_property('draw', False)
        tb.insert(ti, -1)

        tb.show_all()
        return tb

    def edit_annotation_types(self, *p):
        l=self.annotationtypes
        notselected = [ at
                        for at in self.controller.package.all.annotation_types
                        if at not in l ]
        selected_store, it = dialog.generate_list_model([ (at, self.controller.get_title(at)) for at in l ])
        notselected_store, it = dialog.generate_list_model(
            [ (at, self.controller.get_title(at)) for at in notselected ])

        hbox = gtk.HBox()
        selectedtree = gtk.TreeView(model=selected_store)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Displayed'), cell, text=0)
        selectedtree.append_column(column)

        selectedtree.set_reorderable(True)
        selectedtree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        notselectedtree = gtk.TreeView(model=notselected_store)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Not displayed'), cell, text=0)
        notselectedtree.append_column(column)
        notselectedtree.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

        hbox.add(selectedtree)
        actions = gtk.VBox()

        def transfer(b, source, dest):
            selection = source.get_selection ()
            if not selection:
                return True
            store, paths = selection.get_selected_rows()

            rows = [ gtk.TreeRowReference(store, path) for path in paths ]

            m=dest.get_model()
            for r in rows:
                path=r.get_path()
                if path is None:
                    # Should not happen...
                    print 'Strange...'
                    continue
                it=store.get_iter(path)
                # Add el to dest
                m.append(store[path])
                store.remove(it)
            return True

        def transferall(b, source, dest):
            s=source.get_model()
            d=dest.get_model()
            while True:
                it=s.get_iter_first()
                if it is None:
                    break
                d.append(s[it])
                s.remove(it)
            return True

        def row_activated(treeview, path, view_column, source, dest):
            transfer(None, source, dest)
            return True

        b=gtk.Button('<<<')
        b.connect('clicked', transfer, notselectedtree, selectedtree)
        notselectedtree.connect('row_activated', row_activated, notselectedtree, selectedtree)
        actions.add(b)

        b=gtk.Button(_('< All <'))
        b.connect('clicked', transferall, notselectedtree, selectedtree)
        actions.add(b)

        b=gtk.Button(_('> All >'))
        b.connect('clicked', transferall, selectedtree, notselectedtree)
        actions.add(b)

        b=gtk.Button('>>>')
        b.connect('clicked', transfer, selectedtree, notselectedtree)
        selectedtree.connect('row-activated', row_activated, selectedtree, notselectedtree)
        actions.add(b)

        hbox.add(actions)

        hbox.add(notselectedtree)

        hbox.show_all()

        # The widget is built. Put it in the dialog.
        d = gtk.Dialog(title=_('Displayed annotation types'),
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
                       buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

        d.vbox.add(hbox)

        d.connect('key-press-event', dialog.dialog_keypressed_cb)

        d.show()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == gtk.RESPONSE_OK:
            self.annotationtypes = [ at[1] for at in selected_store ]
            self.update_model(partial_update=True)
        d.destroy()

        return True

    def edit_preferences(self, *p):
        cache=dict(self.options)

        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_('Preferences'))
        ew.add_checkbox(_('Relation type'), 'display-relation-type', _('Display relation types'))
        ew.add_checkbox(_('Relation content'), 'display-relation-content', _('Display relation content'))
        ew.add_checkbox(_('Highlight'), 'highlight', _('Highlight active annotations'))

        res=ew.popup()
        if res:
            self.options.update(cache)
        return True

    def get_middle_position(self):
        """Return the current middle position, in ms.
        """
        a=self.adjustment
        return self.pixel2unit( a.value + a.page_size / 2, absolute=True )

    def set_middle_position(self, pos):
        """Set the current middle position, in ms.
        """
        self.center_on_position(pos)

    def update_selection_button(self):
        b=self.selection_button
        if len(self.get_selected_annotation_widgets()) > 1:
            if not b.props.sensitive:
                b.set_sensitive(True)
        else:
            if b.props.sensitive:
                b.set_sensitive(False)

    def get_selected_annotation_widgets(self):
        """Return the list of currently active annotation widgets.
        """
        return [ w for w in self.layout.get_children() if isinstance(w, AnnotationWidget) and w.active ]

    def unselect_all(self, widget=None, selection=None):
        """Unselect all annotations.
        """
        if selection is None:
            selection=self.get_selected_annotation_widgets()
        for w in selection:
            self.desactivate_annotation(w.annotation, buttons=[w])
        return True

    def selection_delete(self, widget, selection=None):
        if selection is None:
            selection=self.get_selected_annotation_widgets()
        batch_id=object()
        for w in selection:
            self.controller.delete_element(w.annotation, batch_id=batch_id)
        return True

    def selection_as_table(self, widget, selection):
        self.controller.gui.open_adhoc_view('table', elements=[ w.annotation for w in selection ], destination='east')
        return True

    def selection_highlight(self, widget, selection):
        for w in selection:
            self.controller.notify('AnnotationActivate', annotation=w.annotation)
        return True

    def selection_edit(self, widget, selection):
        if not self.controller.gui.edit_accumulator:
            self.controller.gui.open_adhoc_view('editaccumulator', destination='fareast')
        a=self.controller.gui.edit_accumulator
        for w in selection:
            a.edit(w.annotation)
        return True

    def selection_merge(self, widget, selection):
        types=set( w.annotation.type for w in selection )
        for t in list(types):
            l=[ w.annotation for w in selection if w.annotation.type == t ]
            if len(l) > 1:
                batch_id=object()
                # We need at least 2 annotations
                l.sort(key=lambda a: a.begin)
                end=max( a.end for a in l )
                # Resize the first annotation
                self.controller.notify('ElementEditBegin', element=l[0], immediate=True)
                l[0].end=end
                self.controller.notify('AnnotationEditEnd', annotation=l[0], batch=batch_id)
                self.controller.notify('ElementEditCancel', element=l[0])
                # Remove all others
                for a in l[1:]:
                    self.controller.delete_element(a, batch_id=batch_id)
        return True

    def selection_tag(self, widget, selection):
        tag=dialog.entry_dialog(title=_('Tag selection'),
                                text=_('Enter the tag for the selection'),
                                default='',
                                completions=self.controller.get_defined_tags())
        if tag is None:
            return True
        if not re.match('^[\w\d_]+$', tag):
            dialog.message_dialog(_('The tag contains invalid characters'),
                                  icon=gtk.MESSAGE_ERROR)
            return True
        batch_id=object()
        for w in selection:
            self.controller.notify('ElementEditBegin', element=w.annotation, immediate=True)
            self.controller.package.associate_user_tag(w.annotation, tag)
            self.controller.notify('AnnotationEditEnd', annotation=w.annotation, batch=batch_id)
            self.controller.notify('ElementEditCancel', element=w.annotation)
        return True
