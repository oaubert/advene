#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
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

from advene.model.schema import AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.model.fragment import MillisecondFragment
from advene.gui.views import AdhocView
import advene.gui.edit.elements
from advene.gui.edit.create import CreateElementPopup
from advene.gui.util import png_to_pixbuf

from advene.gui.views.annotationdisplay import AnnotationDisplay
import advene.util.helper as helper
from advene.gui.util import dialog, name2color, get_small_stock_button, get_pixmap_button
from advene.gui.widget import AnnotationWidget, AnnotationTypeWidget

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
        else:
            b="   " + helper.format_time(a.fragment.begin)
            e=" - " + helper.format_time(a.fragment.end)
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

    and a 3rd one which controls the displayed area.
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
            )
        self.options = {
            'highlight': False,
            # Autoscroll: 0: None, 1: continuous, 2: discrete
            'autoscroll': 1,
            'display-relations': True,
            'display-relation-type': True,
            'display-relation-content': True,
            # Delay before displaying the annotation tooltip, in ms.
            'annotation-tooltip-delay': 2000,
            'annotation-tooltip-activate': True,
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
        for n, v in arg:
            if n == 'annotation-type':
                at=helper.get_id(self.controller.package.annotationTypes,
                                 v)
                if at:
                    ats.append(at)
                else:
                    self.log(_("Cannot find annotation type %s") % v)
            elif n == 'source':
                c=self.controller.build_context()
                # Override a potentially existing value of elements
                elements=c.evaluateValue(v)
            elif n == 'position':
                default_position=int(float(v))
            elif n == 'zoom':
                default_zoom=float(v)
        if ats:
            annotationtypes=ats

        self.list = elements
        self.annotationtypes = annotationtypes
        self.tooltips = gtk.Tooltips()
        # Annotation-specific tooltips, with a tunable delay
        self.annotation_tips = gtk.Tooltips()
        self.annotation_tips.set_delay(self.options['annotation-tooltip-delay'])
        if self.options['annotation-tooltip-activate']:
            self.annotation_tips.enable()
        else:
            self.annotation_tips.disable()

        self.current_marker = None
        # Now that self.list is initialized, we reuse the l variable
        # for various checks.
        if elements is None:
            elements = controller.package.annotations
        # Initialize annotation types if needed
        if self.annotationtypes is None:
            if self.list is None:
                # We display the whole package, so display also
                # empty annotation types
                self.annotationtypes = list(self.controller.package.annotationTypes)
            else:
                # We specified a list. Display only the annotation
                # types for annotations present in the set
                self.annotationtypes = list(sets.Set([ a.type for a in self.list ]))

        if minimum is None and maximum is None and controller is not None:
            # No dimension. Get them from the controller.
            duration = controller.cached_duration
            if duration <= 0:
                if controller.package.annotations:
                    duration = max([a.fragment.end for a in elements])
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
                       ( 2, _("Discrete scrolling")) ),
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
        self.scale.connect ("value-changed", self.scale_event)
        self.scale.connect ("changed", self.scale_event)

        # The same value in relative form
        self.fraction_adj = gtk.Adjustment (value=1.0,
                                            lower=0.01,
                                            upper=1.0,
                                            step_incr=.01,
                                            page_incr=.1)
        self.fraction_adj.connect ("value-changed", self.fraction_event)
        self.fraction_adj.connect ("changed", self.fraction_event)

        self.layout_size=(None, None)

        self.layout = gtk.Layout ()
        if config.data.os == 'win32':
                self.layout.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        #to catch mouse clicks on win32
        self.layout.connect('scroll_event', self.layout_scroll_cb)
        self.layout.connect('key_press_event', self.layout_key_press_cb)

        # Activate/deactivate annotation tooltips on enter/leave
        def layout_enter_cb(layout, event):
            if self.options['annotation-tooltip-activate']:
                self.annotation_tips.enable()
            else:
                self.annotation_tips.disable()
            return False

        def layout_leave_cb(layout, event):
            self.annotation_tips.disable()
            return False

        self.layout.connect('enter_notify_event', layout_enter_cb)
        self.layout.connect('leave_notify_event', layout_leave_cb)

        self.layout.connect('button_press_event', self.layout_button_press_cb)
        self.layout.connect('size_allocate', self.layout_resize_event)
        self.layout.connect('expose_event', self.draw_background)
        self.layout.connect_after('expose_event', self.draw_relation_lines)

        # The layout can receive drops
        self.layout.connect("drag_data_received", self.layout_drag_received)
        self.layout.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation']
                                  + config.data.drag_type['annotation-type'], 
                                  gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK)

        self.old_scale_value = self.scale.value

        # Lines to draw in order to indicate related annotations
        self.relations_to_draw = []

        # Current position in units
        self.current_position = minimum

        # Used for paste operations
        self.selected_position = 0
        self.selection_marker = None

        # Holds the ref. to a newly created annotation, so that its
        # widget gets focus when it is created (cf  udpate_annotation)
        self.transmuted_annotation = None
        # Adjustment corresponding to the Virtual display
        # The page_size is the really displayed area
        self.adjustment = gtk.Adjustment ()
        self.update_adjustment ()
        self.adjustment.set_value (u2p(minimum))

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
        def set_default_parameters(widget, *p):
            self.fraction_adj.value=default_zoom
            self.adjustment.set_value(u2p(default_position))
            self.resize_legend_widget(self.legend)
            # Set annotation inspector width, so that it does not auto-resize
            w, h = self.widget.window.get_size()
            self.inspector_pane.set_position(w - 160)
            self.widget.disconnect(self.expose_signal)
            return False
        self.expose_signal=self.widget.connect('expose-event', set_default_parameters)


    def get_save_arguments(self):
        # FIXME: add a dialog to ask for what elements to save
        arguments = [ ('annotation-type', at.id) for at in self.annotationtypes ]
        arguments.append( ('position', self.pixel2unit(self.adjustment.value) ) )
        arguments.append( ('zoom', self.fraction_adj.value) )
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
                b,e=self.bounds()
                self.maximum = e
            if self.maximum != oldmax:
                # Reset to display whole timeline
                (w, h)=self.layout.window.get_size()
                self.scale.set_value( (self.maximum - self.minimum) / float(w) )

            if self.list is None:
                # We display the whole package, so display also
                # empty annotation types
                self.annotationtypes = list(self.controller.package.annotationTypes)
            else:
                # We specified a list. Display only the annotation
                # types for annotations present in the set
                self.annotationtypes = list(sets.Set([ a.type for a in self.list ]))

        self.layout.foreach(self.layout.remove)
        self.layer_position.clear()
        self.update_layer_position()
        self.populate()
        self.draw_marks()
        self.draw_current_mark()
        self.legend.foreach(self.legend.remove)
        self.update_legend_widget(self.legend)
        self.legend.show_all()
        self.fraction_event(widget=None)
        #self.layout.show_all()
        return

    def set_autoscroll_mode(self, v):
        """Set the autoscroll value.
        """
        if v not in (0, 1, 2):
            return False
        # Update self.autoscroll_choice
        self.autoscroll_choice.set_active(v)
        return True

    def update_layer_position(self):
        """Update the layer_position attribute

        """
        s = config.data.preferences['timeline']['interline-height']
        h = self.button_height + s
        for at in self.annotationtypes:
            self.layer_position[at] = h
            h += self.button_height + s

    def refresh(self, *p):
        self.update_model(self.controller.package, partial_update=True)
        return True

    def selection_handle(self, widget, selection_data, info, time_stamp):
        p = str(self.selected_position)
        selection_data.set_text (p, len(p))
        return

    def selection_clear(self, widget, event):
        # Another application claimed the selection. Remove the marker.
        self.selected_position = 0
        self.remove_selection_marker()
        return True

    def set_selection(self, value):
        self.selected_position = long(value)
        return True

    def activate_selection(self):
        # Define which selections we can handle
        self.layout.selection_add_target("CLIPBOARD", "STRING", 1)
        self.layout.selection_add_target("CLIPBOARD", "COMPOUND_TEXT", 1)
        # Define the selection handler
        self.layout.connect("selection_get", self.selection_handle)
        # Claim selection ownership
        self.layout.selection_owner_set("CLIPBOARD")
        # Display a mark
        self.set_selection_marker(self.selected_position)
        return

    def set_annotation(self, a=None):
        self.statusbar.set_annotation(a)
        for v in self._slave_views:
            try:
                v.set_annotation(a)
            except AttributeError:
                pass

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
        pos = self.unit2pixel (annotation.fragment.begin)
        a = self.adjustment
        if pos < a.lower:
            pos = a.lower
        elif pos > a.upper:
            pos = a.upper
        if pos < a.value or pos > (a.value + a.page_size):
            a.set_value (pos)
        self.update_position (None)
        return True

    def center_on_position(self, position):
        """Scroll the view to center on the given position.
        """
        (w, h) = self.layout.window.get_size ()
        pos = self.unit2pixel (position) - w/2
        a = self.adjustment
        if pos < a.lower:
            pos = a.lower
        elif pos >= a.upper - a.page_size:
            pos = a.upper - a.page_size
        if a.value != pos:
            a.set_value (pos)
        return True

    def activate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None:
            if self.options['autoscroll'] == 2:
                self.scroll_to_annotation(annotation)
            if self.options['highlight']:
                self.activate_annotation (annotation)
            self.update_position (None)
        return True

    def desactivate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None:
            if self.options['highlight']:
                self.desactivate_annotation (annotation)
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
                ))

    def type_restricted_handler(self, context, parameters):
        at=context.globals['annotationtype']
        for w in self.legend.get_children():
            if isinstance(w, AnnotationTypeWidget):
                w.set_playing(w.annotationtype == at)
            elif isinstance(w, gtk.ToggleButton):
                w.set_active(w.annotationtype == at)
        return True

    def tag_update(self, context, parameters):
        tag=context.evaluateValue('tag')
        bs = [ b
               for b in self.layout.get_children()
               if hasattr (b, 'annotation') and tag in b.annotation.tags ]
        for b in bs:
            self.update_button(b)
        return True

    def unregister_callback (self, controller=None):
        for r in self.registered_rules:
            controller.event_handler.remove_rule(r, type_="internal")

    def set_widget_background_color(self, widget, color=None):
        if isinstance(widget, AnnotationWidget):
            widget.update_widget()
            return True
        if color is None:
            try:
                color=widget._default_color
            except AttributeError:
                return True
        for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            widget.modify_bg (style, color)
        return True

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
        return True

    def toggle_annotation (self, annotation):
        button = self.get_widget_for_annotation (annotation)
        if button:
            if button.active:
                self.desactivate_annotation (annotation, buttons=button)
            else:
                self.activate_annotation (annotation, buttons=button)

    def unit2pixel (self, v):
        return (long(v / self.scale.value)) or 1

    def pixel2unit (self, v):
        return v * self.scale.value

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
            'begin': helper.format_time(a.fragment.begin),
            'end': helper.format_time(a.fragment.end) }
        self.annotation_tips.set_tip(b, tip)
        self.layout.move(b, self.unit2pixel(a.fragment.begin), self.layer_position[a.type])
        return True

    def update_annotation (self, annotation=None, event=None):
        """Update an annotation's representation."""
        if self.list is None:
            l=self.controller.package.annotations
        else:
            l=self.list
        if event == 'AnnotationActivate' and annotation in l:
            self.activate_annotation(annotation)
            if self.options['autoscroll'] == 2:
                self.scroll_to_annotation(annotation)
            return True
        if event == 'AnnotationDeactivate' and annotation in l:
            self.desactivate_annotation(annotation)
            return True
        if event == 'AnnotationCreate' and annotation in l:
            if self.get_widget_for_annotation(annotation):
                # It was already created (for instance by the code
                # in update_legend_widget/create_annotation
                return True
            b=self.create_annotation_widget(annotation)
            if annotation == self.transmuted_annotation:
                # Get the focus
                b.grab_focus()
            self.layout.show_all()
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
        def split_annotation(menu, widget, ann, p):
            self.controller.split_annotation(ann, p)
            return True

        def center_and_zoom(menu, widget, ann):
            # Deactivate autoscroll...
            self.set_autoscroll_mode(0)

            # Set the zoom
            z=1.0 * ann.fragment.duration / (self.maximum - self.minimum)
            if z < 0.05:
                z=0.05
            self.fraction_adj.value=z

            # Center on annotation
            self.center_on_position(ann.fragment.begin)
            return True

        p=self.pixel2unit(widget.allocation.x + x)
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

    def dump_adjustment (self):
        a = self.adjustment
        print ("Lower: %.1f\tUpper: %.1f\tValue: %.1f\tPage size: %.1f"
               % (a.lower, a.upper, a.value, a.page_size))

    def align_annotations(self, source, dest, mode):
        new={
            'begin': source.fragment.begin,
            'end': source.fragment.end
            }
        if '-' in mode:
            (s, d) = mode.split('-')
            new[s]=getattr(dest.fragment, d)
        elif mode == 'align':
            for k in ('begin', 'end'):
                new[k]=getattr(dest.fragment, k)
        else:
            print "Unknown drag mode: %s" % mode

        if new['begin'] < new['end']:
            for k in ('begin', 'end'):
                setattr(source.fragment, k, new[k])
        self.controller.notify("AnnotationEditEnd", annotation=source)
        return True

    def annotation_fraction(self, widget):
        """Return the fraction of the cursor position relative to the annotation widget.

        @return: a fraction (float)
        """
        x, y = widget.get_pointer()
        w = widget.allocation.width
        f = 1.0 * x / w
        return f

    def drag_begin(self, widget, context):
        """Handle drag begin for annotations.
        """
        # Determine in which part of the annotation we clicked.
        widget._drag_fraction = self.annotation_fraction(widget)
        return False

    def create_relation(self, source, dest, rt):
        """Create the reation of type rt between source and dest.
        """
        # Get the id from the idgenerator
        p=self.controller.package
        id_=self.controller.package._idgenerator.get_id(Relation)
        relation=p.createRelation(ident=id_,
                                 members=(source, dest),
                                 type=rt)
        p.relations.append(relation)
        self.controller.notify("RelationCreate", relation=relation)
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        #print "drag_received event for %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
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
                sitem=gtk.MenuItem(self.controller.get_title(rt))
                sitem.connect('activate', create_relation, source, dest, rt)
                sm.append(sitem)
            if True:
                # Propose to create a new one
                sitem=gtk.MenuItem(_("Create a new relation-type."))
                sitem.connect('activate', create_relation_type_and_relation, source, dest)
                sm.append(sitem)
            item.set_submenu(sm)

            def align_annotations(item, s, d, m):
                self.align_annotations(s, d, m)
                return True

            for (title, mode) in (
                (_("Align both begin times"), 'begin-begin'),
                (_("Align both end times"), 'end-end'),
                (_("Align end time to selected begin time"), 'end-begin'),
                (_("Align begin time to selected end time"), 'begin-end'),
                (_("Align all times"), 'align'),
                ):
                item=gtk.ImageMenuItem(title)
                im=gtk.Image()
                im.set_from_file(config.data.advenefile( ( 'pixmaps', mode + '.png') ))
                item.set_image(im)
                item.connect('activate', align_annotations, source, dest, mode)
                menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        elif targetType == config.data.target_type['tag']:
            tags=selection.data.split(',')
            a=widget.annotation
            l=[t for t in tags if not t in a.tags ]
            a.tags = a.tags + l
            self.controller.notify('AnnotationEditEnd', annotation=a)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def type_drag_sent(self, widget, context, selection, targetType, eventTime):
        #print "drag_sent event from %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation-type']:
            selection.set(selection.target, 8, widget.annotationtype.uri)
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def move_or_copy_annotation(self, source, dest, position=None):
        """Display a popup menu to move or copy the source annotation to the dest annotation type.

        If position is given (in ms), then the choice will also be
        offered to move/copy the annotation and change its bounds.
        """
        def move_annotation(i, an, typ, position=None):
            if an.relations:
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

        # Popup a menu to propose the drop options
        menu=gtk.Menu()

        if source.type != dest:
            item=gtk.MenuItem(_("Duplicate annotation to type %s") % self.controller.get_title(dest))
            item.connect('activate', copy_annotation, source, dest)
            menu.append(item)

            item=gtk.MenuItem(_("Move annotation to type %s") % self.controller.get_title(dest))
            item.connect('activate', move_annotation, source, dest)
            menu.append(item)
            if source.relations:
                item.set_sensitive(False)

        if position is not None and abs(position-source.fragment.begin) > 1000:
            item=gtk.MenuItem(_("Duplicate annotation at %s") % helper.format_time(position))
            item.connect('activate', copy_annotation, source, dest, position)
            menu.append(item)

            item=gtk.MenuItem(_("Move annotation at %s") % helper.format_time(position))
            item.connect('activate', move_annotation, source, dest, position)
            menu.append(item)
            if source.relations:
                item.set_sensitive(False)
            
        # If there are compatible relation-types, propose to directly create a relation
        relationtypes=helper.matching_relationtypes(self.controller.package,
                                                    source.type,
                                                    dest)
        if relationtypes:
            if source.type != dest:
                item=gtk.MenuItem(_("Duplicate and create a relation"))
                # build a submenu
                sm=gtk.Menu()
                for rt in relationtypes:
                    sitem=gtk.MenuItem(self.controller.get_title(rt))
                    sitem.connect('activate', copy_annotation, source, dest, None, rt)
                    sm.append(sitem)
                menu.append(item)
                item.set_submenu(sm)

            if position is not None:
                item=gtk.MenuItem(_("Duplicate at %s and create a relation") % helper.format_time(position))
                # build a submenu
                sm=gtk.Menu()
                for rt in relationtypes:
                    sitem=gtk.MenuItem(self.controller.get_title(rt))
                    sitem.connect('activate', copy_annotation, source, dest, position, rt)
                    sm.append(sitem)
                menu.append(item)
                item.set_submenu(sm)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())
            
    def copy_annotation_type(self, source, dest):
        """Display a popup menu to copy the source annotation type to the dest annotation type.
        """
        def copy_annotations(i, at, typ, relationtype=None):
            for an in at.annotations:
                self.transmuted_annotation=self.controller.transmute_annotation(an,
                                                                                typ,
                                                                                delete=False)
            return self.transmuted_annotation

        def copy_annotations_filtered(i, at, typ, relationtype=None):
            s=dialog.entry_dialog(title=_("Annotation filter"),
                                  text=_("Enter the searched string"))
            if s:
                for an in at.annotations:
                    if s in an.content.data:
                        self.transmuted_annotation=self.controller.transmute_annotation(an,
                                                                                        typ,
                                                                                        delete=False)
            return self.transmuted_annotation

        # Popup a menu to propose the drop options
        menu=gtk.Menu()

        if source != dest:
            item=gtk.MenuItem(_("Copy all annotations to type %s") % self.controller.get_title(dest))
            item.connect('activate', copy_annotations, source, dest)
            menu.append(item)
            item=gtk.MenuItem(_("Copy all annotations matching a string to type %s") % self.controller.get_title(dest))
            item.connect('activate', copy_annotations_filtered, source, dest)
            menu.append(item)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())
            
    def annotation_type_drag_received_cb(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
            dest=widget.annotationtype
            self.move_or_copy_annotation(source, dest)
        elif targetType == config.data.target_type['annotation-type']:
            # Copy annotations
            source_uri=selection.data
            source=self.controller.package.annotationTypes.get(source_uri)
            dest=widget.annotationtype
            self.copy_annotation_type(source, dest)
        elif targetType == config.data.target_type['color']:
            # Got a color
            # The structure consists in 4 unsigned shorts: r, g, b, opacity
            (r, g, b, opacity)=struct.unpack('HHHH', selection.data)
            widget.annotationtype.setMetaData(config.data.namespace, 'color', u"string:#%04x%04x%04x" % (r, g, b))
            # FIXME: notify the change
            self.set_widget_background_color(widget)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def new_annotation_type_drag_received_cb(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)

            # Create a type
            dest=self.create_annotation_type()
            if dest is None:
                return True

            self.move_or_copy_annotation(source, dest)
            return True
        return False

    def legend_drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop from an annotation-type to the legend
        """
        if targetType == config.data.target_type['annotation-type']:
            source_uri=selection.data
            source=self.controller.package.annotationTypes.get(source_uri)
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

    def annotation_button_press_cb(self, widget, event, annotation):
        """Handle button presses on annotation widgets.
        """
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.annotation_cb(widget, annotation, event.x)
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.quick_edit(annotation, button=widget)
            return True
        elif event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS and event.state & gtk.gdk.CONTROL_MASK:
            # Control + click : set annotation begin/end time to current time
            f=self.annotation_fraction(widget)
            if f < .25:
                at='begin'
            elif f > .75:
                at='end'
            else:
                return False
            f=annotation.fragment
            setattr(f, at, long(self.controller.player.current_position_value))
            if f.begin > f.end:
                f.begin, f.end = f.end, f.begin
            self.controller.notify('AnnotationEditEnd', annotation=annotation)
            return True
        elif event.button == 1 and event.type == gtk.gdk.BUTTON_PRESS:
            if not self.options['goto-on-click']:
                return True
            # Goto annotation if not already playing it
            p=self.controller.player.current_position_value
            # We do not use 'p in annotation.fragment' since if we are
            # at the end of the annotation, we may want to go back to its beginning
            if p >= annotation.fragment.begin and p < annotation.fragment.end:
                return True

            c=self.controller
            pos = c.create_position (value=annotation.fragment.begin,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            self.controller.update_status (status="set", position=pos)
            if self.loop_toggle_button.get_active():
                self.controller.gui.loop_on_annotation_gui(annotation)
            return True
        return False

    def quick_edit(self, annotation, button=None, callback=None):
        """Quickly edit a textual annotation
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

        def key_handler(widget, event, ann, cb, controller, close_eb):
            if event.keyval == gtk.keysyms.Return:
                # Validate the entry
                rep=ann.type.getMetaData(config.data.namespace, "representation")
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
                        controller.log("Cannot update the annotation, its representation is too complex")
                        r=ann.content.data
                ann.content.data = r
                if cb:
                    cb(ann)
                controller.notify('AnnotationEditEnd', annotation=ann)
                close_eb(widget)
                return True
            elif event.keyval == gtk.keysyms.Escape:
                # Abort and close the entry
                close_eb(widget)
                return True
            return False
        e.connect("key_press_event", key_handler, annotation, callback, self.controller, close_editbox)
        def grab_focus(widget, event):
            widget.grab_focus()
            return False
        e.connect('enter_notify_event', grab_focus)

        e.show()

        # Put the entry on the layout
        al=button.get_allocation()
        button.parent.put(e, al.x, al.y)
        e.grab_focus()
        return

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
                position=annotation.fragment.end
            else:
                position=annotation.fragment.begin
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
        return True

    def create_annotation_widget(self, annotation):
        if not annotation.type in self.layer_position:
            # The annotation is not displayed
            return None

        b = AnnotationWidget(annotation=annotation, container=self)
        # Put at a default position.
        self.layout.put(b, 0, 0)
        b.show()
        self.update_button(b)

        b.connect("key_press_event", self.annotation_key_press_cb, annotation)
        b.connect("button_press_event", self.annotation_button_press_cb, annotation)
        b.connect("enter_notify_event", lambda b, e: b.grab_focus())

        def focus_out(widget, event):
            self.set_annotation(None)
            if self.options['display-relations']:
                self.relations_to_draw = []
                self.update_relation_lines()
            return False
        b.connect("focus-out-event", focus_out)

        def focus_in(button, event):
            self.set_annotation(button.annotation)
            if self.options['display-relations']:
                a=button.annotation
                for r in button.annotation.relations:
                    # FIXME: handle more-than-binary relations
                    if r.members[0] != a:
                        b=self.get_widget_for_annotation(r.members[0])
                        if b:
                            # b may be None, if the related annotation is not displayed
                            self.relations_to_draw.append( (b, button, r) )
                    elif r.members[1] != a:
                        b=self.get_widget_for_annotation(r.members[1])
                        if b:
                            self.relations_to_draw.append( (button, b, r) )
                self.update_relation_lines()

            if (self.options['autoscroll'] and
                self.controller.player.status != self.controller.player.PlayingStatus):
                # Check if the annotation is not already visible
                a = self.adjustment
                start=a.value
                finish=a.value + a.page_size
                begin = self.unit2pixel (annotation.fragment.begin)
                if begin >= start and begin <= finish:
                    return False
                end = self.unit2pixel (annotation.fragment.end)
                if end >= start and end <= finish:
                    return False
                if begin <= start and end >= finish:
                    # The annotation bounds are off-screen anyway. Do
                    # not move.
                    return False
                self.scroll_to_annotation(button.annotation)
            return False
        b.connect("focus-in-event", focus_in)

        # The button can generate drags
        b.connect("drag_begin", self.drag_begin)

        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['annotation']
                          + config.data.drag_type['uri-list']
                          + config.data.drag_type['text-plain']
                          + config.data.drag_type['TEXT']
                          + config.data.drag_type['STRING']
                          + config.data.drag_type['timestamp']
                          + config.data.drag_type['tag']
                          ,
                          gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY)
        # The button can receive drops (to create relations)
        b.connect("drag_data_received", self.drag_received)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation']
                        + config.data.drag_type['tag']
                        , gtk.gdk.ACTION_LINK)

        # Handle scroll actions
        def handle_scroll_event(button, event):
            if not (event.state & gtk.gdk.CONTROL_MASK):
                return False
            if event.direction == gtk.gdk.SCROLL_DOWN:
                incr=config.data.preferences['scroll-increment']
            #elif event.direction == gtk.gdk.SCROLL_UP:
            else:
                incr=-config.data.preferences['scroll-increment']

            fr=self.annotation_fraction(button)
            f=button.annotation.fragment
            if event.state & gtk.gdk.SHIFT_MASK:
                f.begin += incr
                f.end += incr
            elif fr < .5:
                f.begin += incr
            elif fr >= .5:
                f.end += incr

            self.controller.notify('AnnotationEditEnd', annotation=button.annotation)
            self.set_annotation(button.annotation)
            button.grab_focus()
            return True

        b.connect("scroll_event", handle_scroll_event)

        b.show_all()
        return b

    def populate (self):
        u2p = self.unit2pixel
        if self.list is None:
            l=self.controller.package.annotations
        else:
            l=self.list

        for annotation in l:
            self.create_annotation_widget(annotation)

        self.layout.set_size (u2p (self.maximum - self.minimum),
                              max(self.layer_position.values() or (0,))
                              + self.button_height + config.data.preferences['timeline']['interline-height'])

        #self.layout.show_all ()

    def remove_marks(self, widget=None, data=None):
        if hasattr(widget, 'mark'):
            self.layout.remove(widget)

    def draw_current_mark (self):
        u2p = self.unit2pixel
        a = gtk.VSeparator()
        a.set_size_request (2, max(self.layer_position.values() or (0,))
                            + self.button_height)
        self.current_marker = a
        a.mark = self.current_position
        a.pos = 5
        self.layout.put (a, u2p(a.mark), a.pos)
        a.show ()

    def update_current_mark (self, pos=None):
        a = self.current_marker
        u2p = self.unit2pixel
        if pos is None:
            pos = self.current_position
        else:
            self.current_position = pos
        a.mark = pos
        self.layout.move (a, u2p(pos), a.pos)

    def update_position (self, pos):
        if pos is None:
            pos = self.current_position
        if (self.options['autoscroll'] == 1
            and self.controller.player.status == self.controller.player.PlayingStatus):
            self.center_on_position(pos)
        self.update_current_mark (pos)
        return True

    def position_reset(self):
        # The position was reset. Deactive active annotations.
        self.deactivate_all()
        self.update_current_mark(self.minimum)
        return True

    def mark_press_cb(self, eventbox, event, t):
        # What is the current relative position of the
        # mark in the window ?
        a = self.adjustment
        (w, h) = self.layout.window.get_size ()
        rel = (self.unit2pixel(t) - a.value) / float(w)

        f=self.fraction_adj.value
        if event.button == 1:
            f=f/2.0
        elif event.button == 3:
            f=min(f*2.0, 1.0)
        else:
            return False
        if f > 1.0:
            f = 1.0
        self.fraction_adj.value=f

        # Center the view around the selected mark
        pos = self.unit2pixel (t) - ( w * rel )
        if pos < a.lower:
            pos = a.lower
        elif pos > a.upper - a.page_size:
            pos = a.upper - a.page_size
        a.set_value (pos)
        self.update_position (None)
        return True

    def draw_marks (self):
        """Draw marks for stream positioning"""
        u2p = self.unit2pixel
        # We want marks every 200 pixels
        step = self.pixel2unit (100)
        t = self.minimum
        while t <= self.maximum:
            x = u2p(t)

            i=gtk.Image()
            i.set_from_pixbuf(png_to_pixbuf (self.controller.package.imagecache.get(t, epsilon=1000), height=self.button_height))
            i.mark = t
            i.pos = 1
            i.show()
            self.layout.put(i, x, i.pos)

            a = gtk.Arrow (gtk.ARROW_DOWN, gtk.SHADOW_NONE)
            a.mark = t
            a.pos = 1
            a.show()
            self.layout.put (a, x, a.pos)

            l = gtk.Label (helper.format_time (t))
            l.mark = t
            l.pos = a.pos
            l.show()
            self.layout.put (l, x + 13, l.pos)
            t += step

    def bounds (self):
        """Bounds of the list.

        Return a tuple corresponding to the min and max values of the
        list, in list units.
        """
        minimum=sys.maxint
        maximum=0
        if self.list is None:
            l=self.controller.package.annotations
        else:
            l=self.list
        for a in l:
            if a.fragment.begin < minimum:
                minimum = a.fragment.begin
            if a.fragment.end > maximum:
                maximum = a.fragment.end
        return minimum, maximum

    def layout_key_press_cb (self, win, event):
        """Handles key presses in the timeline background
        """
        # Process player shortcuts
        if self.controller.gui and self.controller.gui.process_player_shortcuts(win, event):
            return True

        if event.keyval >= 49 and event.keyval <= 57:
            if self.statusbar.annotation is not None:
                pos=self.statusbar.annotation.fragment.begin
            else:
                pos=self.get_middle_position()
            self.fraction_adj.value=1.0/pow(2, event.keyval-49)
            self.set_middle_position(pos)
            return True
        elif event.keyval == gtk.keysyms.e:
            if self.statusbar.annotation is not None:
                self.controller.gui.edit_element(self.statusbar.annotation)
                return True
        elif event.keyval == gtk.keysyms.c:
            self.center_on_position(self.current_position)
            return True
        elif event.keyval == gtk.keysyms.p:
            # Play at the current position
            x, y = win.get_pointer()
            # Note: x is here relative to the visible portion of the window. Thus we must
            # add self.adjustment.value
            position=long(self.pixel2unit(self.adjustment.value + x))
            c=self.controller
            pos = c.create_position (value=position,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            return True
        elif event.keyval == gtk.keysyms.t:
            # Toggle tooltips display
            self.display_tooltips_toggle.set_active(not self.display_tooltips_toggle.get_active())
            return True
        return False

    def layout_drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop from an annotation to the layout.
        """
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
            # We received a drop. Determine the location.

            # Correct y value according to scrollbar position
            y += widget.parent.get_vscrollbar().get_adjustment().get_value()

            a=[ at 
                for (at, p) in self.layer_position.iteritems()
                if (y >= p and y <= p + self.button_height) ]
            if a:
                # Copy/Move to a[0]
                self.move_or_copy_annotation(source, a[0], position=self.pixel2unit(x))
            else:
                # Maybe we should propose to create a new annotation-type ?
                # Create a type
                dest=self.create_annotation_type()
                if dest is None:
                    return True
                self.move_or_copy_annotation(source, dest, position=self.pixel2unit(x))
            return True
        elif targetType == config.data.target_type['annotation-type']:
            source_uri=selection.data
            source=self.controller.package.annotationTypes.get(source_uri)
            # We received a drop. Determine the location.
            a=[ at 
                for (at, p) in self.layer_position.iteritems()
                if (y >= p and y <= p + self.button_height) ]
            if a:
                # Copy/Move to a[0]
                self.copy_annotation_type(source, a[0])
            else:
                # Maybe we should propose to create a new annotation-type ?
                # Create a type
                dest=self.create_annotation_type()
                if dest is None:
                    return True
                self.copy_annotation_type(source, dest)
            return True
        else:
            print "Unknown target type for drop: %d" % targetType
        return False

    def layout_button_press_cb(self, widget=None, event=None):
        """Handle mouse click in timeline window.
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
            x=long(self.adjustment.value + x)
            y=long(widget.get_parent().get_vadjustment().value + y)
            if y < self.button_height or event.type == gtk.gdk._2BUTTON_PRESS:
                c=self.controller
                pos = c.create_position (value=self.pixel2unit(x),
                                         key=c.player.MediaTime,
                                         origin=c.player.AbsolutePosition)
                c.update_status (status="set", position=pos)
                return True
        if event.button == 3:
            self.context_cb (timel=self, position=self.pixel2unit(event.x), height=event.y)
            return True
        return False

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
            id_=self.controller.package._idgenerator.get_id(Annotation)
            # Determine annotation type
            at=None
            h=long(height)
            for a, p in self.layer_position.iteritems():
                if h >= p and h < p + self.button_height:
                    at=a
                    break
            if at is None:
                at=self.controller.package.annotationTypes[0]

            duration=self.controller.cached_duration / 20
            # Make the end bound not override the screen
            d=long(self.pixel2unit(self.adjustment.value + self.layout.window.get_size()[0]) - position)
            if d > 0:
                duration=min(d, duration)
            else:
                # Should not happen
                print "Strange, click outside the timeline"

            el=self.controller.package.createAnnotation(
                ident=id_,
                type=at,
                author=config.data.userid,
                date=self.controller.get_timestamp(),
                fragment=MillisecondFragment(begin=long(position),
                                             duration=duration))
            self.controller.package.annotations.append(el)
            self.controller.notify('AnnotationCreate', annotation=el)
            return True

        def copy_value(win, position):
            timel.set_selection(position)
            timel.activate_selection()
            return True

        item = gtk.MenuItem(_("Position %s") % helper.format_time(position))
        menu.append(item)

        item = gtk.SeparatorMenuItem()
        menu.append(item)

        item = gtk.MenuItem(_("Go to..."))
        item.connect("activate", popup_goto, position)
        menu.append(item)

        item = gtk.MenuItem(_("Copy value into clipboard"))
        item.connect("activate", copy_value, position)
        menu.append(item)

        item = gtk.MenuItem(_("Create a new annotation"))
        item.connect('activate', create_annotation, position)
        menu.append(item)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def set_selection_marker (self, position):
        """Display the marker representing the position.
        """
        x=self.unit2pixel(position)
        if self.selection_marker is None:
            # Draw a marker
            a = gtk.VSeparator()
            a.set_size_request (2, max(self.layer_position.values() or (0,))
                                + self.button_height)
            self.selection_marker = a
            a.modify_bg(gtk.STATE_NORMAL, self.colors['active'])
        else:
            a = self.selection_marker
        a.mark = position
        a.pos = 5
        self.layout.put (a, x, a.pos)
        a.show ()
        return True

    def remove_selection_marker (self):
        try:
            self.layout.remove(self.selection_marker)
        except AttributeError:
            pass
        return True

    def update_layout (self):
        (w, h) = self.layout.get_size ()
        self.layout.set_size (self.unit2pixel(self.maximum - self.minimum), h)
        return True

    def update_adjustment (self):
        """Update the adjustment values depending on the current aspect ratio.
        """
        u2p = self.unit2pixel
        a = self.adjustment

        width = self.maximum - self.minimum

        #a.value=u2p(minimum)
        a.lower=float(u2p(self.minimum))
        a.upper=float(u2p(self.maximum))
        a.step_incr=float(u2p(width / 100))
        a.page_incr=float(u2p(width / 10))
        a.page_size=float(self.layout.get_size()[0])
        #print "Update: from %.2f to %.2f" % (a.lower, a.upper)
        a.changed ()

    def scale_event (self, widget=None, data=None):
        self.update_adjustment ()
        self.update_layout ()
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

        fraction=self.fraction_adj.value

        self.zoom_combobox.child.set_text('%d%%' % long(100 * fraction))
        v = (self.maximum - self.minimum) / float(w) * fraction
        # Is it worth redrawing the whole timeline ?
        if abs(v - self.scale.value) / float(self.scale.value) > 0.01:
            self.scale.set_value(v)
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
            mouse_position=self.pixel2unit(event.x)
        else:
            # Plain scroll: scroll the timeline
            a = self.adjustment
            incr = a.step_incr

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
            self.adjustment.value=self.unit2pixel(mouse_position) - x
        return True

    def move_widget (self, widget=None):
        """Update the annotation widget position.
        """
        if hasattr (widget, 'annotation'):
            widget.update_widget()
            self.layout.move (widget,
                              self.unit2pixel(widget.annotation.fragment.begin),
                              self.layer_position[widget.annotation.type])
        return True


    def redraw_event(self, widget=None, data=None):
        """Redraw the layout according to the new ratio value.
        """
        if self.old_scale_value != self.scale.value:
            self.old_scale_value = self.scale.value
            # Remove old marks
            self.layout.foreach(self.remove_marks)
            # Reposition all buttons
            self.layout.foreach(self.move_widget)
            # Redraw marks
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

        # Resize all buttons to fit the largest
        if width > 10:
            layout.foreach(resize, width)
        layout.get_parent().get_parent().set_position (width + 30)

    def restrict_playing(self, at, widget=None):
        """Restrict playing to the given annotation-type.
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
            self.controller.restrict_playing(at)
            p=self.controller.player
            if p.status == p.PauseStatus or p == p.PlayingStatus:
                if [ a for a in self.controller.active_annotations if a.type == at ]:
                    # We are in an annotation of the right type. Do
                    # not move the player, just play from here.
                    pass
                self.controller.update_status("resume")
            else:
                l=[ a.fragment.begin for a in at.annotations ]
                l.sort()
                self.controller.update_status("start", position=l[0])
        return True

    def update_legend_widget(self, layout):
        """Update the legend widget.

        Its content may have changed.
        """
        width=0
        height=0

        def restrict_playing(m, at, w):
            self.restrict_playing(at, w)
            return True

        def annotationtype_keypress_handler(widget, event, at):
            if widget.keypress(widget, event, at):
                return True
            elif event.keyval == gtk.keysyms.Return:
                def set_end_time(an):
                    an.fragment.end=self.controller.player.current_position_value
                    return True

                if (self.controller.player.status != self.controller.player.PlayingStatus
                    and self.controller.player.status != self.controller.player.PauseStatus):
                    return True
                # Create a new annotation
                id_=self.controller.package._idgenerator.get_id(Annotation)

                duration=3000
                el=self.controller.package.createAnnotation(
                    ident=id_,
                    type=widget.annotationtype,
                    author=config.data.userid,
                    date=self.controller.get_timestamp(),
                    fragment=MillisecondFragment(begin=long(self.controller.player.current_position_value),
                                                 duration=duration))
                self.controller.package.annotations.append(el)
                self.controller.notify('AnnotationCreate', annotation=el)
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
            self.tooltips.set_tip(b, _("From schema %s") % self.controller.get_title(t.schema))
            layout.put (b, 20, self.layer_position[t])
            b.update_widget()
            b.show_all()
            b.connect("key_press_event", annotationtype_keypress_handler, t)
            b.connect("button_press_event", annotationtype_buttonpress_handler, t)

            def focus_in(button, event):
                for w in layout.get_children():
                    if isinstance(w, AnnotationTypeWidget) and w.annotationtype.schema == button.annotationtype.schema:
                        w.set_highlight(True)
                return False

            def focus_out(button, event):
                for w in layout.get_children():
                    if isinstance(w, AnnotationTypeWidget) and w.highlight:
                        w.set_highlight(False)
                return False

            b.connect("focus-in-event", focus_in)
            b.connect("focus-out-event", focus_out)

            # The button can receive drops (to transmute annotations)
            b.connect("drag_data_received", self.annotation_type_drag_received_cb)
            b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                            gtk.DEST_DEFAULT_HIGHLIGHT |
                            gtk.DEST_DEFAULT_ALL,
                            config.data.drag_type['annotation'] +
                            config.data.drag_type['annotation-type'] +
                            config.data.drag_type['color'],
                            gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
            # The button can generate drags (to change annotation type order)
            b.connect("drag_data_get", self.type_drag_sent)
            b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['annotation-type'], gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_LINK)

            height=max (height, self.layer_position[t] + 3 * self.button_height)

            p=gtk.ToggleButton()
            p.annotationtype=t
            p.add(gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_SMALL_TOOLBAR))
            p.connect('clicked', restrict_playing, t, b)
            p.set_size_request(15, self.button_height)
            self.tooltips.set_tip(p, _("Restrict playing to this annotation-type"))
            layout.put (p, 0, self.layer_position[t])
            
        # Add the "New type" button at the end
        b=gtk.Button()
        l=gtk.Label()
        l.set_markup("<b><span style='normal'>%s</span></b>" % _("+"))
        l.modify_font(self.annotation_type_font)
        b.add(l)
        self.tooltips.set_tip(b, _("Create a new annotation type"))
        b.set_size_request(-1, self.button_height)
        layout.put (b, 0, height - 2 * self.button_height + config.data.preferences['timeline']['interline-height'])
        b.annotationtype=None
        b.show()

        b.connect("clicked", self.create_annotation_type)
        # The button can receive drops (to create type and transmute annotations)
        b.connect("drag_data_received", self.new_annotation_type_drag_received_cb)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation'],
                        gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE)

        layout.set_size (width + 20, height)
        self.resize_legend_widget(layout)
        return

    def get_full_widget(self):
        """Return the layout with its controllers.
        """
        vbox = gtk.VBox()
        vbox.connect ("key_press_event", self.layout_key_press_cb)

        hb=gtk.HBox()
        toolbar = self.get_toolbar()
        hb.add(toolbar)

        def loop_toggle_cb(b):
            if not b.get_active():
                print "Deactive"
                # If we deactivate the locked looping feature, then also
                # disable the player loop toggle.
                self.controller.gui.loop_toggle_button.set_active(False)
            return True

        self.loop_toggle_button=gtk.ToggleToolButton(stock_id=gtk.STOCK_REFRESH)
        self.loop_toggle_button.connect("toggled", loop_toggle_cb)
        self.controller.gui.tooltips.set_tip(self.loop_toggle_button, _("Automatically activate loop when clicking on an annotation"))
        toolbar.insert(self.loop_toggle_button, -1)

        def goto_toggle_cb(b):
            self.options['goto-on-click']=b.get_active()
            return True

        self.goto_on_click_toggle=gtk.ToggleToolButton(stock_id=gtk.STOCK_GO_FORWARD)
        self.goto_on_click_toggle.set_active(self.options['goto-on-click'])
        self.goto_on_click_toggle.connect('toggled', goto_toggle_cb)
        self.controller.gui.tooltips.set_tip(self.goto_on_click_toggle, _("Goto annotation when clicking"))
        toolbar.insert(self.goto_on_click_toggle, -1)

        ti=gtk.SeparatorToolItem()
        ti.set_expand(True)
        ti.set_property('draw', False)
        toolbar.insert(ti, -1)

        self.statusbar=QuickviewBar(self.controller)

        # The annotation view button should be placed in the toolbar,
        # but this prevents DND from working correctly.
        def drag_sent(widget, context, selection, targetType, eventTime, name):
            if targetType == config.data.target_type['adhoc-view']:
                selection.set(selection.target, 8,
                              cgi.urllib.urlencode( {
                            'name': name,
                            'master': self.controller.gui.get_adhoc_view_instance_id(self),
                            } ))
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
        self.controller.gui.tooltips.set_tip(b, _("Open an annotation display view"))
        b.connect("drag_data_get", drag_sent, 'annotationdisplay')
        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)
        hb.pack_start(b, expand=False)

        b=get_pixmap_button('montage.png', open_slave_montage)
        self.controller.gui.tooltips.set_tip(b, _("Open a slave montage view (coordinated zoom level)"))
        b.connect("drag_data_get", drag_sent, 'montage')
        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)
        hb.pack_start(b, expand=False)

        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(self.player_toolbar)

        vbox.pack_start(hb, expand=False)

        vbox.add (self.get_packed_widget())

        vbox.pack_start(self.statusbar, expand=False)

        return vbox

    def get_packed_widget (self):
        """Return the widget packed into a scrolledwindow."""
        self.inspector_pane=gtk.HPaned()

        vbox = gtk.VBox ()

        hpaned = gtk.HPaned ()

        self.legend = gtk.Layout ()
        # The layout can receive drops
        self.legend.connect("drag_data_received", self.legend_drag_received)
        self.legend.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation-type'], 
                                  gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK)

        sw1 = gtk.ScrolledWindow ()
        sw1.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
        sw1.set_placement(gtk.CORNER_TOP_RIGHT)
        sw1.add (self.legend)
        hpaned.add1 (sw1)

        sw = gtk.ScrolledWindow ()
        sw.set_policy (gtk.POLICY_ALWAYS, gtk.POLICY_AUTOMATIC)
        sw.set_hadjustment (self.adjustment)
        sw.set_vadjustment (sw1.get_vadjustment())
        sw.add (self.layout)
        hpaned.add2 (sw)

        (w, h) = self.legend.get_size ()
        hpaned.set_position (max(w, 100))
        vbox.add (hpaned)

        #hgrade = stripchart.HGradeZoom()
        #hgrade.adjustment = self.adjustment
        #hgrade.set_size_request(400, 30)
        #vbox.pack_start (hgrade.widget, expand=False)

        self.inspector_pane.pack1(vbox, resize=True, shrink=True)
        a=AnnotationDisplay(controller=self.controller)
        f=gtk.Frame(_("Inspector"))
        f.add(a.widget)
        self.inspector_pane.pack2(f, resize=False, shrink=True)
        self.controller.gui.register_view (a)        
        a.set_master_view(self)
        a.widget.show_all()

        return self.inspector_pane

    def get_toolbar(self):
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        # Annotation-type selection button
        def trash_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation-type']:
                source_uri=selection.data
                source=self.controller.package.annotationTypes.get(source_uri)
                if source in self.annotationtypes:
                    self.annotationtypes.remove(source)
                    self.update_model(partial_update=True)
            else:
                print "Unknown target type for drop: %d" % targetType
            return True

        b=gtk.ToolButton(stock_id=gtk.STOCK_SELECT_COLOR)
        b.set_tooltip(self.tooltips, _("Drag an annotation type here to remove it from display.\nClick to edit all displayed types"))
        b.connect("clicked", self.edit_annotation_types)
        b.connect("drag_data_received", trash_drag_received)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation-type'],
                        gtk.gdk.ACTION_MOVE)
        tb.insert(b, -1)

        # Relation display toggle
        def handle_toggle(b, option):
            self.options[option]=b.get_active()
            return True

        self.display_relations_toggle=gtk.ToggleToolButton(stock_id=gtk.STOCK_REDO)
        self.display_relations_toggle.set_tooltip(self.tooltips, _("Display relations"))
        self.display_relations_toggle.set_active(self.options['display-relations'])
        self.display_relations_toggle.connect('toggled', handle_toggle, 'display-relations')
        tb.insert(self.display_relations_toggle, -1)

        # Annotation tooltip display toggle
        def handle_tooltip_toggle(b):
            v=b.get_active()
            self.options['annotation-tooltip-activate']=v
            if v:
                self.annotation_tips.enable()
            else:
                self.annotation_tips.disable()
            return True

        try:
            sid=gtk.STOCK_INFO
        except:
            sid=gtk.STOCK_HELP
        self.display_tooltips_toggle=gtk.ToggleToolButton(stock_id=sid)
        self.display_tooltips_toggle.set_tooltip(self.tooltips, _("Display tooltips for annotations (shortcut: t)"))
        self.display_tooltips_toggle.connect('toggled', handle_tooltip_toggle)
        self.display_tooltips_toggle.set_active(self.options['annotation-tooltip-activate'])
        tb.insert(self.display_tooltips_toggle, -1)

        # Separator
        tb.insert(gtk.SeparatorToolItem(), -1)

        def zoom_entry(entry):
            f=entry.get_text()

            i=re.findall(r'\d+', f)
            if i:
                f=int(i[0])/100.0
            else:
                return True
            if self.statusbar.annotation is not None:
                pos=self.statusbar.annotation.fragment.begin
            else:
                pos=self.get_middle_position()
            self.fraction_adj.value=f
            self.set_middle_position(pos)
            return True

        def zoom_change(combo):
            v=combo.get_current_element()
            if isinstance(v, float):
                if self.statusbar.annotation is not None:
                    pos=self.statusbar.annotation.fragment.begin
                else:
                    pos=self.get_middle_position()
                self.fraction_adj.value=v
                self.set_middle_position(pos)
            return True

        def zoom(i, factor):
            if self.statusbar.annotation is not None:
                pos=self.statusbar.annotation.fragment.begin
            else:
                pos=self.get_middle_position()
            self.fraction_adj.set_value(self.fraction_adj.value * factor)
            self.set_middle_position(pos)
            return True

        i=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_OUT)
        i.connect('clicked', zoom, 1.3)
        tb.insert(i, -1)

        i=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_IN)
        i.connect('clicked', zoom, .7)
        tb.insert(i, -1)

        self.zoom_combobox=dialog.list_selector_widget(members=[
                ( f, "%d%%" % long(100*f) )
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
            (_("Preferences"), gtk.STOCK_PREFERENCES, self.edit_preferences),
            (_("Center on current player position."), gtk.STOCK_JUSTIFY_CENTER, center_on_current_position),
            ):
            b=gtk.ToolButton(stock_id=icon)
            b.set_tooltip(self.tooltips, tooltip)
            b.connect("clicked", callback)
            tb.insert(b, -1)

        tb.show_all()
        return tb

    def edit_annotation_types(self, *p):
        l=self.annotationtypes
        notselected = [ at
                        for at in self.controller.package.annotationTypes
                        if at not in l ]
        selected_store, it = dialog.generate_list_model(
            [ (at, self.controller.get_title(at)) for at in l ])
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
                    print "Strange..."
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
        b.connect("clicked", transfer, notselectedtree, selectedtree)
        notselectedtree.connect("row_activated", row_activated, notselectedtree, selectedtree)
        actions.add(b)

        b=gtk.Button(_('< All <'))
        b.connect("clicked", transferall, notselectedtree, selectedtree)
        actions.add(b)

        b=gtk.Button(_('> All >'))
        b.connect("clicked", transferall, selectedtree, notselectedtree)
        actions.add(b)

        b=gtk.Button('>>>')
        b.connect("clicked", transfer, selectedtree, notselectedtree)
        selectedtree.connect("row_activated", row_activated, selectedtree, notselectedtree)
        actions.add(b)

        hbox.add(actions)

        hbox.add(notselectedtree)

        hbox.show_all()

        # The widget is built. Put it in the dialog.
        d = gtk.Dialog(title=_("Displayed annotation types"),
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
                       buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

        d.vbox.add(hbox)

        d.connect("key_press_event", dialog.dialog_keypressed_cb)

        d.show()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == gtk.RESPONSE_OK:
            self.annotationtypes = [ at[1] for at in selected_store ]
            self.update_model(partial_update=True)
        d.destroy()

        return True

    def create_annotation_type(self, *p):
        if self.controller.gui:
            sc=self.controller.gui.ask_for_schema(text=_("Select the schema where you want to\ncreate the new annotation type."), create=True)
            if sc is None:
                return None
            cr=CreateElementPopup(type_=AnnotationType,
                                  parent=sc,
                                  controller=self.controller)
            at=cr.popup(modal=True)
        return at

    def edit_preferences(self, *p):
        cache=dict(self.options)

        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Preferences"))
        ew.add_checkbox(_("Relation type"), "display-relation-type", _("Display relation types"))
        ew.add_checkbox(_("Relation content"), "display-relation-content", _("Display relation content"))
        ew.add_checkbox(_("Highlight"), "highlight", _("Highlight active annotations"))

        ew.add_label(_("Annotation tooltips"))
        ew.add_checkbox(_("Display annotation tooltips"), 'annotation-tooltip-activate', _("Display tooltips when the mouse gets over an annotation."))
        ew.add_spin(_("Annotation tooltip delay"), "annotation-tooltip-delay", _("Delay before displaying the tooltip"), 10, 6000)

        res=ew.popup()
        if res:
            self.display_tooltips_toggle.set_active(cache['annotation-tooltip-activate'])
            self.annotation_tips.set_delay(cache['annotation-tooltip-delay'])
            self.options.update(cache)
        return True

    def get_middle_position(self):
        """Return the current middle position, in ms.
        """
        a=self.adjustment
        return self.pixel2unit( a.value + a.page_size / 2 )

    def set_middle_position(self, pos):
        """Set the current middle position, in ms.
        """
        self.center_on_position(pos)
