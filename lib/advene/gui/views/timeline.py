#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2016 Olivier Aubert <contact@olivieraubert.net>
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
import re
import operator
import urllib
import struct
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
import cairo
from gi.repository import Pango
from gettext import gettext as _
from threading import Lock

# Advene part
import advene.core.config as config

from advene.model.schema import AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.gui.views import AdhocView
import advene.gui.edit.elements
from advene.gui.util import png_to_pixbuf, enable_drag_source
from advene.gui.util import decode_drop_parameters

from advene.gui.views.annotationdisplay import AnnotationDisplay
import advene.util.helper as helper
from advene.gui.util import dialog, name2color, get_small_stock_button, get_pixmap_button, get_pixmap_toolbutton
from advene.gui.widget import AnnotationWidget, AnnotationTypeWidget, GenericColorButtonWidget

name="Timeline view plugin"

def register(controller):
    controller.register_viewclass(TimeLine)

class QuickviewBar(Gtk.HBox):
    def __init__(self, controller=None):
        GObject.GObject.__init__(self)
        self.controller=controller
        self.begin=Gtk.Label()
        self.end=Gtk.Label()
        self.content=Gtk.ProgressBar()
        self.content.set_ellipsize(Pango.EllipsizeMode.MIDDLE)

        self.annotation=None

        self.pack_start(self.content, True, True, 0)
        self.pack_start(self.begin, False, True, 0)
        self.pack_start(self.end, False, True, 0)

    def set_text(self, s, progress=0):
        self.begin.set_text("")
        self.end.set_text("")
        self.content.set_text(s)
        self.content.set_fraction(min(progress, 1.0))

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
        elif isinstance(a, AnnotationType):
            if len(a.annotations):
                b="   " + helper.format_time(min(a.fragment.begin for a in a.annotations))
                e=" - " + helper.format_time(max(a.fragment.end for a in a.annotations))
            else:
                b=""
                e=""
            c=self.controller.get_title(a)
            c += " (" + a.id + ")"
        else:
            b="   " + helper.format_time(a.fragment.begin)
            e=" - " + helper.format_time(a.fragment.end)
            c=self.controller.get_title(a)
            c += " (" + a.id + ")"
        self.annotation=a
        self.begin.set_text(b)
        self.end.set_text(e)
        self.content.set_text(c)
        self.content.set_fraction(0)

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
    tooltip = _("Display annotations on a timeline")

    def __init__ (self, elements=None,
                  minimum=0,
                  maximum=0,
                  controller=None,
                  annotationtypes=None,
                  parameters=None):
        super(TimeLine, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            (_("Save view"), self.save_view),
            (_("Save default options"), self.save_default_options),
            (_("Limit display to current area"), lambda i, b: self.limit_display()),
            (_("Display whole movie"), lambda i, b: self.unlimit_display()),
            )
        self.options = {
            'highlight': False,
            # Autoscroll: 0: None, 1: continuous, 2: discrete, 3: annotation
            'autoscroll': 2,
            'display-relations': True,
            'display-all-relations': False,
            'display-relation-type': True,
            'display-relation-content': True,
            }
        self.controller=controller

        self.update_lock = Lock()

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
            elif n == 'minimum':
                minimum=long(v)
            elif n == 'maximum':
                maximum=long(v)
        if ats:
            annotationtypes=ats

        self.list = elements
        self.annotationtypes = annotationtypes

        # package used when the update_model has been called from
        # __init__. This is used to avoid a double initialization.
        self.package_from_init = None

        self.current_marker = None
        self.current_marker_scale = None
        self.layout = Gtk.Layout ()

        self.minimum = minimum
        self.maximum = maximum
        if not self.maximum:
            self.update_min_max()

        if default_position is None:
            default_position=self.minimum

        self.colors = {
            'active': name2color('#fdfd4b'),
            'inactive': Gtk.Button().get_style_context().get_background_color(Gtk.StateFlags.NORMAL),
            'background': name2color('red'),
            'white': name2color('white'),
            }

        self.locked_inspector = False

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
        self.annotation_font = Pango.FontDescription("sans %d" % config.data.preferences['timeline']['font-size'])
        self.annotation_type_font = self.annotation_font.copy()
        self.annotation_type_font.set_style(Pango.Style.ITALIC)

        # Maybe we should ask pango the height of 'l' plus margins
        self.button_height = config.data.preferences['timeline']['button-height']

        # Shortcut
        u2p = self.unit2pixel

        # How many units does a pixel represent ?
        # self.scale.get_value = unit by pixel
        # Unit = ms
        self.scale = Gtk.Adjustment.new(value=((self.maximum - self.minimum) or 60 * 60 * 1000) / Gdk.get_default_root_window().get_width(),
                                        lower=5,
                                        upper=sys.maxint,
                                        step_increment=20,
                                        page_increment=100,
                                        page_size=20)
        self.scale.connect('value-changed', self.scale_event)
        #self.scale.connect('changed', self.scale_event)

        # The same value in relative form
        self.fraction_adj = Gtk.Adjustment.new(value=1.0,
                                               lower=0.01,
                                               upper=1.0,
                                               step_increment=.01,
                                               page_increment=.1,
                                               page_size=.1)
        self.fraction_adj.connect('value-changed', self.fraction_event)
        self.fraction_adj.connect('changed', self.fraction_event)

        # Coordinates of the selected region.
        self.layout_selection=[ [None, None], [None, None] ]

        # Session-set variable: if we get a horizontal scroll signal,
        # then we know that the device pointer for the session is able
        # to do both (vertical and horizontal), and we can act
        # accordingly.
        self.can_do_horizontal_scroll = False

        self.layout.add_events( Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK | Gdk.EventMask.BUTTON1_MOTION_MASK )
        self.scale_layout = Gtk.Layout()
        self.scale_layout.height=0
        self.scale_layout.step=0
        self.scale_layout.add_events( Gdk.EventMask.BUTTON_PRESS_MASK )

        # Memorize the current scale height, so that we can refresh it
        # when it is changed by a given amount (typically 10 or 16
        # pixels)
        self.current_scale_height=0
        # Global pane is the Paned holding the scale and the layout.
        self.global_pane=None

        self.legend = Gtk.Layout ()

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
        self.layout.connect('draw', self.draw_background)
        self.layout.connect_after('draw', self.draw_relation_lines)
        self.scale_layout.connect_after('draw', self.draw_bookmarks)

        # The layout can receive drops
        self.layout.connect('drag-data-received', self.layout_drag_received)
        self.layout.drag_dest_set(Gtk.DestDefaults.MOTION |
                                  Gtk.DestDefaults.HIGHLIGHT |
                                  Gtk.DestDefaults.ALL,
                                  config.data.get_target_types('annotation', 'annotation-type', 'timestamp'),
                                  Gdk.DragAction.COPY | Gdk.DragAction.LINK | Gdk.DragAction.MOVE | Gdk.DragAction.ASK )

        self.old_scale_value = self.scale.get_value()

        # Lines to draw in order to indicate related annotations
        self.relations_to_draw = []
        self.bookmarks_to_draw = []

        # Current position in units
        self.current_position = self.minimum

        # Holds the ref. to a newly created annotation, so that its
        # widget gets focus when it is created (cf  update_annotation)
        self.transmuted_annotation = None
        # Adjustment corresponding to the Virtual display
        # The page_size is the really displayed area
        self.adjustment = Gtk.Adjustment()

        # Dictionary holding the vertical position for each type
        self.layer_position = {}
        self.draw_current_mark()
        self.widget = self.get_full_widget()

        # Set default parameters (zoom) and refresh the legend widget
        # on the first expose signal
        def set_default_parameters(widget, event, zoom, pos, pane):
            self.update_adjustment ()
            self.adjustment.set_value(u2p(self.minimum, absolute=True))
            self.fraction_adj.set_value(zoom)
            if pos >= self.minimum and pos <= self.maximum:
                self.adjustment.set_value(u2p(pos, absolute=True))
            # Set annotation inspector width, so that it does not auto-resize
            if pane is None:
                pane = self.widget.get_window().get_width() - 160
            self.inspector_pane.set_position(pane)
            # Check if display is limited
            if self.minimum > 0 and self.maximum < self.controller.package.cached_duration:
                self.limit_navtools.show()
            self.widget.disconnect(self.expose_signal)
            self.update_model(from_init=True)
            return False
        # Convert values, that could be strings
        if default_position is not None:
            default_position=long(float(default_position))
        if pane_position is not None:
            pane_position=long(float(pane_position))

        self.expose_signal=self.widget.connect('draw', set_default_parameters,
                                               default_zoom, default_position, pane_position)

    def get_save_arguments(self):
        arguments = [ ('annotation-type', at.id) for at in self.annotationtypes ]
        arguments.append( ('minimum', self.minimum ) )
        arguments.append( ('maximum', self.maximum ) )
        arguments.append( ('position', self.pixel2unit(self.adjustment.get_value(), absolute=True) ) )
        arguments.append( ('zoom', self.fraction_adj.get_value()) )
        self.options['pane-position']=self.inspector_pane.get_position()
        return self.options, arguments

    def draw_background(self, layout, context):
        """Draw annotation type separating lines
        """
        width, height = layout.get_size()
        i=config.data.preferences['timeline']['interline-height']
        #drawable=layout.get_bin_window()
        #gc=drawable.new_gc(foreground=self.colors['background'], line_style=Gdk.LINE_ON_OFF_DASH)
        for p in sorted(self.layer_position.itervalues()):
            # Draw a different background
            context.move_to(0, p - i / 2) 
            context.line_to(width, p - i / 2)
        return False

    def update_relation_lines(self):
        self.layout.queue_draw()

    def draw_relation_lines(self, layout, context):
        if self.bookmarks_to_draw:
            self.draw_bookmarks(layout, context)
        if self.options['display-all-relations']:
            to_draw = [ (self.get_widget_for_annotation(r.members[0]),
                         self.get_widget_for_annotation(r.members[1]),
                         r)
                        for r in self.controller.package.relations ]
        else:
            to_draw = self.relations_to_draw
        if not to_draw:
            return False
        for b1, b2, r in to_draw:
            if b1 is None or b2 is None:
                continue
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

    def draw_bookmarks(self, layout, context):
        if not self.bookmarks_to_draw:
            return False
        a=self.adjustment
        begin=long(a.get_value())
        end=long(a.get_value() + a.get_page_size())

        w, h = layout.get_size()

        context.set_source_rgb(1.0, 0, 0)
        context.set_line_width(2)

        for t in self.bookmarks_to_draw:
            x=self.unit2pixel(t, absolute=True)
            # There is a clipping area applied to the context which
            # restricts drawing to the visible area. We have to use
            # coordinates relative to the visible area to draw the
            # marks
            if x < begin:
                # The bookmark is outside. Draw an arrow.
                context.move_to(16, 2)
                context.line_to(16, 16)
                context.line_to(2, 9)
                context.fill()
            elif x > end:
                # (x1, y2, x2, y2)
                clip_extents = context.clip_extents()
                width = clip_extents[2] - clip_extents[0]
                # The bookmark is outside. Draw an arrow.
                context.move_to(width - 16, 2)
                context.line_to(width - 16, 16)
                context.line_to(width - 2, 9)
                context.fill()
            else:
                context.move_to(x - begin, 0)
                context.line_to(x - begin, h)
                context.stroke()
        return False

    def dialog_too_many_annotations(self, n):
        d = Gtk.Dialog(title=_("%d annotations") % n,
                       parent=self.controller.gui.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( _("Display all types"), Gtk.ResponseType.YES,
                                 Gtk.STOCK_CLOSE, Gtk.ResponseType.CLOSE ) )
        l = Gtk.Label(_("There are %d annotations.\nThe current timeline may take a long time to display them, so only the first two annotation types are displayed. Use the annotation type selector (second button in the timeline) to select other annotations types to display, or click on the 'Display all types' button below.") % n)
        l.set_line_wrap(True)
        d.vbox.add(l)
        d.connect('key-press-event', dialog.dialog_keypressed_cb)

        d.show_all()
        d.resize(300, -1)
        dialog.center_on_mouse(d)
        def handle_response(d, res):
            d.destroy()
            if res == Gtk.ResponseType.YES:
                # Display all types
                self.annotationtypes = list(self.controller.package.annotationTypes)
                self.update_model(partial_update=True)
            return True
        d.connect('response', handle_response)
        return True

    def update_min_max(self):
        oldmax = self.maximum
        self.minimum=0
        self.maximum=0
        duration = self.controller.cached_duration
        if duration <= 0:
            duration = self.bounds()[1]
        if duration:
            self.maximum = long(duration)

        if not self.maximum:
            # self.maximum == 0, so try to compute it
            self.maximum = self.bounds()[1]

        # Ensure that self.maximum > self.minimum
        if self.maximum == self.minimum:
            self.maximum = self.minimum + 10000

        if self.minimum > self.maximum:
            self.minimum, self.maximum = self.maximum, self.minimum

        if self.maximum != oldmax and self.layout.get_window() is not None:
            # Reset to display whole timeline
            self.scale.set_value( (self.maximum - self.minimum) / float(self.layout.get_window().get_height()) )

    def update_model(self, package=None, partial_update=False, from_init=False):
        """Update the whole model.

        @param package: the package
        @type package: Package
        @param partial_update: it is only an update for the existing package, we do not need to rebuild everything
        @param partial_update: boolean
        """
        if not self.update_lock.acquire(False) or self.layout.get_window() is None:
            # An update is already ongoing or the layout is not realized yet
            return

        if package is None:
            package = self.controller.package

        if from_init:
            if len(self.layout.get_children()) < 3:
                self.package_from_init = package
            else:
                self.update_lock.release()
                return
        else:
            if package == self.package_from_init:
                # update_model is called on the same package as in the
                # __init__ method. This means that is is a result of
                # the PackageActivate, so do not update it twice. Just
                # reset package_from_init to enable future updates (in
                # case of mass-modification of the package: merging,
                # import...)
                self.package_from_init = None
                self.update_lock.release()
                return

        self.update_min_max()
        if partial_update:
            pos=self.get_middle_position()
        else:
            # It is not just an update, do a full redraw
            if self.annotationtypes is None and self.list is None:
                # We display the whole package, so display also
                # empty annotation types
                self.annotationtypes = list(self.controller.package.annotationTypes)
            elif self.list is not None:
                # We specified a list. Display only the annotation
                # types for annotations present in the set
                self.annotationtypes = list(set([ a.type for a in self.list ]))

        # Clear the layouts
        self.layout.foreach(self.layout.remove)
        self.scale_layout.foreach(self.scale_layout.remove)
        self.legend.foreach(self.legend.remove)

        self.layer_position.clear()
        self.update_layer_position()

        self.draw_marks()
        self.draw_current_mark()

        def finalize_callback():
            self.update_legend_widget(self.legend)
            self.legend.show_all()
            if self.layout.get_window() is not None:
                self.fraction_event(widget=None, forced_window_width=self.layout.get_window().get_width())
            self.update_lock.release()

        self.populate(finalize_callback)

        if partial_update:
            self.set_middle_position(pos)
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

    def set_annotation(self, a=None, force=False):
        if not force and self.locked_inspector:
            return
        self.quickview.set_annotation(a)
        for v in self._slave_views:
            m=getattr(v, 'set_annotation', None)
            if m:
                m(a)
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
        pos = helper.clamp(pos,
                           a.get_lower(),
                           a.get_upper() - a.get_page_size())
        if a.get_value() != pos:
            a.set_value(pos)
        return True

    def activate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None:
            if self.options['autoscroll'] == 3:
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

    def duration_update_handler(self, context, parameters):
        """Handle DurationUpdate event.

        There is a potential synchronization issue here: duration may
        be updated while an update_model is already occuring. In this
        case, the update_lock is held and the update_model call will
        not do anything. However, we also will miss the correct update
        of the timeline duration.

        We should check the update_lock and if it is held, delay the
        call to update_model intended to update the timeline duration.
        """
        if self.maximum != long(context.globals['duration']):
            # Need a refresh.  It can happen while an update_model is
            # already taking place. In this case, we have to wait
            # until the update_model is done before doing our own update.
            def duration_updated(d):
                if not self.update_lock.locked():
                    # There is a race possibility here. Let's assume
                    # that it will be rare enough...
                    self.refresh()
                    return False
                else:
                    print "duration_updated timeout"
                    # Try again at next timeout.
                    return True
            GObject.timeout_add(100, duration_updated, long(context.globals['duration']))
        return True

    def media_change_handler(self, context, parameters):
        # Note: this should trigger a DurationUpdate after a while anyway.
        # However, this will get the screenshots to update immediately
        self.update_scale_screenshots()
        return True

    def snapshot_update_handler(self, context, parameters):
        pos=long(context.globals['position'])
        epsilon=self.scale_layout.step / 2
        # Note: we check here w.timestamp, which is the timestamp of
        # the displayed snapshot, instead of w.mark (which is the
        # timestamp of the widget), so that the most precise snapshot
        # is kept.
        l=sorted( ( t
                    for t in ( (w, abs(w.mark - pos)) for w in self.scale_layout.get_children()
                               if isinstance(w, Gtk.Image) )
                    if t[1] <= epsilon and t[1] < abs(t[0].timestamp - pos) ),
                 key=operator.itemgetter(1))
        for t in l:
            w=t[0]
            # Iterate only on the first one (if any)
            png=self.controller.package.imagecache.get(pos)
            w.set_from_pixbuf(png_to_pixbuf (png, height=self.scale_layout.height))
            w.timestamp=png.timestamp
            break
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
                controller.event_handler.internal_rule (event="MediaChange",
                                                        method=self.media_change_handler),
                ))
        if 'async-snapshot' in self.controller.player.player_capabilities:
            self.registered_rules.append( controller.event_handler.internal_rule (event="SnapshotUpdate",
                                                                                  method=self.snapshot_update_handler))

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
            return (long( ( v - self.minimum) / self.scale.get_value() )) or 1
        else:
            return (long(v / self.scale.get_value())) or 1

    def pixel2unit (self, v, absolute=False):
        if absolute:
            return long((v * self.scale.get_value()) + self.minimum)
        else:
            return long(v * self.scale.get_value())

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
        self.layout.move(b, self.unit2pixel(a.fragment.begin, absolute=True), self.layer_position[a.type])
        return True

    def update_annotation (self, annotation=None, event=None):
        """Update an annotation's representation."""
        if self.list is None:
            l=self.controller.package.annotations
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
            z=1.0 * ann.fragment.duration / (self.maximum - self.minimum)
            if z < 0.05:
                z=0.05
            self.fraction_adj.set_value(z)

            # Center on annotation
            self.center_on_position(ann.fragment.begin)
            return True

        menu=advene.gui.popup.Menu(ann, controller=self.controller)
        v=self.controller.player.current_position_value
        if v > ann.fragment.begin and v < ann.fragment.end:
            menu.add_menuitem(menu.menu,
                              _("Split at current player position"),
                              split_annotation, widget, ann, v)

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
               % (a.get_lower(), a.get_upper(), a.get_value(), a.get_page_size()))

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
            self.controller.notify('EditSessionStart', element=source, immediate=True)
            for k in ('begin', 'end'):
                setattr(source.fragment, k, new[k])
            self.controller.notify("AnnotationEditEnd", annotation=source)
            self.controller.notify('EditSessionEnd', element=source)
        return True

    def annotation_fraction(self, widget):
        """Return the fraction of the cursor position relative to the annotation widget.

        @return: a fraction (float)
        """
        x, y = widget.get_pointer()
        w = widget.get_allocation().width
        f = 1.0 * x / w
        return f

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

    def create_annotation_type(self, *p):
        at=None
        if self.controller.gui:
            at=self.controller.gui.ask_for_annotation_type(text=_("Creation of a new annotation type"),
                                                           create=True,
                                                           force_create=True)
        return at

    def annotation_drag_begin(self, widget, context):
        """Handle drag begin for annotations.
        """
        # Determine in which part of the annotation we clicked.
        widget._drag_fraction = self.annotation_fraction(widget)
        return False

    def annotation_drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source=self.controller.package.annotations.get(unicode(selection.get_data(), 'utf8').split('\n')[0])
            dest=widget.annotation

            if source == dest:
                return True

            # Popup a menu to propose the drop options
            menu=Gtk.Menu()

            def create_relation(item, s, d, t):
                self.create_relation(s, d, t)
                return True

            def create_relation_type_and_relation(item, s, d):
                if self.controller.gui:
                    sc=self.controller.gui.ask_for_schema(text=_("Select the schema where you want to\ncreate the new relation type."), create=True)
                    if sc is None:
                        return None
                    cr=self.controller.gui.create_element_popup(type_=RelationType,
                                                                parent=sc,
                                                                controller=self.controller)
                    rt=cr.popup(modal=True)
                    self.create_relation(s, d, rt)
                return True

            relationtypes=helper.matching_relationtypes(self.controller.package,
                                                        source.type,
                                                        dest.type)
            item=Gtk.MenuItem(_("Create a relation"))
            menu.append(item)

            sm=Gtk.Menu()
            for rt in relationtypes:
                sitem=Gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                sitem.connect('activate', create_relation, source, dest, rt)
                sm.append(sitem)
            if True:
                # Propose to create a new one
                sitem=Gtk.MenuItem(_("Create a new relation-type."), use_underline=False)
                sitem.connect('activate', create_relation_type_and_relation, source, dest)
                sm.append(sitem)
            item.set_submenu(sm)

            # Propose to merge annotations of same type, or of
            # different types but with same fragments.
            # In both cases, we will merge the data.
            if source.type == dest.type or source.fragment == dest.fragment:
                ok=True
                if source.relations:
                    ok=False
                    #we should maybe accept it and delete relations.
                elif source.type == dest.type:
                    b=min(source.fragment.begin, dest.fragment.begin)
                    e=max(source.fragment.begin, dest.fragment.begin)
                    for a in source.type.annotations:
                        if a.fragment.begin > b and a.fragment.begin < e:
                            # There is at least one annotation between
                            # the merged annotations.
                            ok=False
                            break
                if ok:
                    def merge_annotations(widget, s, d):
                        self.controller.merge_annotations(s, d, extend_bounds=(s.type == d.type))
                        return True
                    item=Gtk.MenuItem(_("Merge with this annotation"))
                    item.connect('activate', merge_annotations, source, dest)
                    menu.append(item)

            def align_annotations(item, s, d, m):
                self.align_annotations(s, d, m)
                return True

            for (title, mode, condition) in (
                (_("Align both begin times"), 'begin-begin', dest.fragment.begin <= source.fragment.end),
                (_("Align both end times"), 'end-end', dest.fragment.end >= source.fragment.begin),
                (_("Align end time to selected begin time"), 'end-begin', dest.fragment.begin >= source.fragment.begin),
                (_("Align begin time to selected end time"), 'begin-end', dest.fragment.end <= source.fragment.end),
                (_("Align all times"), 'align', True),
                ):
                if not condition:
                    continue
                item=Gtk.ImageMenuItem(title)
                im=Gtk.Image()
                im.set_from_file(config.data.advenefile( ( 'pixmaps', mode + '.png') ))
                item.set_image(im)
                item.connect('activate', align_annotations, source, dest, mode)
                menu.append(item)
            menu.show_all()
            menu.popup_at_pointer(None)
        elif targetType == config.data.target_type['tag']:
            tags=unicode(selection.get_data(), 'utf8').split(',')
            a=widget.annotation
            l=[t for t in tags if not t in a.tags ]
            self.controller.notify('EditSessionStart', element=a, immediate=True)
            a.tags = a.tags + l
            self.controller.notify('AnnotationEditEnd', annotation=a)
            self.controller.notify('EditSessionEnd', element=a)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def move_or_copy_annotations(self, sources, dest, position=None, action=Gdk.DragAction.ASK):
        """Display a popup menu to move or copy the sources annotation to the dest annotation type.

        If position is given (in ms), then the choice will also be
        offered to move/copy the annotation and change its bounds.

        If action is specified, then the popup menu will be shortcircuited.
        """
        if not sources:
            return True
        source=sources[0]

        def move_annotation(i, an, typ, position=None):
            if an.relations and an.type != typ:
                dialog.message_dialog(_("Cannot delete the annotation : it has relations."),
                                      icon=Gtk.MessageType.WARNING)
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

        if action == Gdk.DragAction.COPY:
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
        elif action == Gdk.DragAction.MOVE:
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
        elif action == Gdk.DragAction.LINK:
            # Copy and create a relation. Ignore the selection (?)
            if len(relationtypes) == 1:
                copy_annotation(None, source, dest, relationtype=relationtypes[0])
            elif not relationtypes:
                # Create a new relationtype
                self.log("FIXME: no valid relation type is defined")
            else:
                # Multiple valid relationtypes.
                menu=Gtk.Menu()
                item=Gtk.MenuItem(_("Select the appropriate relation type"))
                menu.append(item)
                item.set_sensitive(False)
                for rt in relationtypes:
                    sitem=Gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                    sitem.connect('activate', copy_annotation, source, dest, None, rt)
                    menu.append(sitem)
                menu.show_all()
                menu.popup_at_pointer(None)
            return True

        # ACTION_ASK: Popup a menu to propose the drop options
        menu=Gtk.Menu()

        dest_title=self.controller.get_title(dest)

        if len(sources) > 1:
            if source.type == dest:
                return True
            item=Gtk.MenuItem(_("Duplicate selection to type %s") % dest_title, use_underline=False)
            item.connect('activate', copy_selection, sources, dest)
            menu.append(item)
            item=Gtk.MenuItem(_("Move selection to type %s") % dest_title, use_underline=False)
            item.connect('activate', copy_selection, sources, dest, True)
            menu.append(item)

            menu.show_all()
            menu.popup_at_pointer(None)
            return True

        if source.type != dest:
            item=Gtk.MenuItem(_("Duplicate annotation to type %s") % dest_title, use_underline=False)
            item.connect('activate', copy_annotation, source, dest)
            menu.append(item)

            item=Gtk.MenuItem(_("Move annotation to type %s") % dest_title, use_underline=False)
            item.connect('activate', move_annotation, source, dest)
            menu.append(item)
            if source.relations:
                item.set_sensitive(False)

        if position is not None and abs(position-source.fragment.begin) > 1000:
            item=Gtk.MenuItem(_("Duplicate to type %(type)s at %(position)s") % {
                    'type': dest_title,
                    'position': helper.format_time(position) }, use_underline=False)
            item.connect('activate', copy_annotation, source, dest, position)
            menu.append(item)

            item=Gtk.MenuItem(_("Move to type %(type)s at %(position)s") % {
                        'type': dest_title,
                        'position': helper.format_time(position) }, use_underline=False)
            item.connect('activate', move_annotation, source, dest, position)
            menu.append(item)
            if source.relations and source.type != dest:
                item.set_sensitive(False)

        if relationtypes:
            if source.type != dest:
                item=Gtk.MenuItem(_("Duplicate and create a relation"), use_underline=False)
                # build a submenu
                sm=Gtk.Menu()
                for rt in relationtypes:
                    sitem=Gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                    sitem.connect('activate', copy_annotation, source, dest, None, rt)
                    sm.append(sitem)
                menu.append(item)
                item.set_submenu(sm)

            if position is not None:
                item=Gtk.MenuItem(_("Duplicate at %s and create a relation") % helper.format_time(position), use_underline=False)
                # build a submenu
                sm=Gtk.Menu()
                for rt in relationtypes:
                    sitem=Gtk.MenuItem(self.controller.get_title(rt), use_underline=False)
                    sitem.connect('activate', copy_annotation, source, dest, position, rt)
                    sm.append(sitem)
                menu.append(item)
                item.set_submenu(sm)

        menu.show_all()
        menu.popup_at_pointer(None)

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

        def DTWalign_annotations(i, at, typ, mode, delete=True):
            sa = at.annotations
            sa.sort(key=lambda a: a.fragment.begin)
            da = typ.annotations
            da.sort(key=lambda a: a.fragment.begin)
            bestpath = []
            bestdist = []

            mindist = (abs(sa[0].fragment.begin - da[0].fragment.begin)
                       + abs(sa[0].fragment.end - da[0].fragment.end)
                       + abs((sa[0].fragment.end - sa[0].fragment.begin)
                             - (da[0].fragment.end - da[0].fragment.begin)))
            bestdist.append(mindist)
            bestpath.append([])
            bestpath[0].append(0)

            for j in range(1,len(sa)):
                bestpath.append([])
                bestpath[j].append(j)

                dist = (abs(sa[j].fragment.begin - da[0].fragment.begin)
                        + abs(sa[j].fragment.end - da[0].fragment.end)
                        + abs((sa[j].fragment.end - sa[j].fragment.begin)
                              - (da[0].fragment.end - da[0].fragment.begin)))
                if dist < mindist:
                    mindist = dist
                    bestpath[j] = [j]
                    bestdist.append(dist)
                else:
                    bestpath[j] = list(bestpath[j-1])
                    bestdist.append(bestdist[j-1] + dist)

            for i in range(1,len(da)):
                currentdist = 0
                prevsubdist = 0
                currentpath = []
                prevsubpath = []
                for j in range(0,len(sa)):
                    dist = (abs(sa[j].fragment.begin - da[i].fragment.begin)
                            + abs(sa[j].fragment.end - da[i].fragment.end)
                            + abs((sa[j].fragment.end - sa[j].fragment.begin)
                                  - (da[i].fragment.end - da[i].fragment.begin)))

                    if j == 0:
                        currentpath = list(bestpath[0])
                        currentdist = bestdist[0]

                        bestpath[0].append(0)
                        bestdist[0] = bestdist[0] + dist

                    else:
                        insdist = bestdist[j] + dist
                        deldist = bestdist[j-1] + dist
                        subdist = prevsubdist + dist*1.5

                        currentdist =  bestdist[j]
                        currentpath = list(bestpath[j])

                        if insdist < deldist :
                            if insdist < subdist:
                                bestpath[j].append(j)
                                bestdist[j] = insdist
                            else :
                                prevsubpath.append(j)
                                bestpath[j] = prevsubpath
                                bestdist[j] = subdist
                        elif subdist < deldist :
                            prevsubpath.append(j)
                            bestpath[j] = prevsubpath
                            bestdist[j] = subdist
                        else:
                           bestpath[j] = list(bestpath[j-1])
                           bestdist[j] = deldist

                    prevsubdist = currentdist
                    prevsubpath = list(currentpath)

            # Update annotation timestamp/contents
            batch_id=object()
            for (i,j) in enumerate(bestpath[len(sa)-1]):
                annotation=da[i]
                self.controller.notify('EditSessionStart', element=annotation, immediate=True)
                if mode == 'time':
                    annotation.fragment.begin = sa[j].fragment.begin
                    annotation.fragment.end = sa[j].fragment.end
                elif mode == 'content':
                    annotation.content.data = sa[j].content.data
                self.controller.notify('AnnotationEditEnd', annotation=annotation, batch=batch_id)
                self.controller.notify('EditSessionEnd', element=annotation)
            return True

        # Popup a menu to propose the drop options
        menu=Gtk.Menu()

        source_title=self.controller.get_title(source)
        dest_title=self.controller.get_title(dest)

        if source != dest:
            for (label, action) in (
                (_("Duplicate all annotations to type %s") % dest_title,
                 (copy_annotations, source, dest, False) ),
                (_("Move all annotations to type %s") % dest_title,
                 (copy_annotations, source, dest, True) ),
                (_("Duplicate all annotations matching a string to type %s") % dest_title,
                 (copy_annotations_filtered, source, dest, False) ),
                (_("Move all annotations matching a string to type %s") % dest_title,
                 (copy_annotations_filtered, source, dest, True) ),
                (_("Align all annotation time codes using %s as reference.") % source_title,
                 (DTWalign_annotations, source, dest, 'time', True) ),
                (_("Align all annotation contents using %s as reference") % source_title,
                 (DTWalign_annotations, source, dest, 'content', True) ),
                ):
                item=Gtk.MenuItem(label, use_underline=False)
                item.connect('activate', *action)
                menu.append(item)

        menu.show_all()
        menu.popup_at_pointer(None)

    def annotation_type_drag_received_cb(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.annotations.get(uri) for uri in unicode(selection.get_data(), 'utf8').split('\n') ]
            dest=widget.annotationtype
            self.move_or_copy_annotations(sources, dest)
        elif targetType == config.data.target_type['annotation-type']:
            # Copy annotations
            source=self.controller.package.annotationTypes.get(unicode(selection.get_data(), 'utf8'))
            dest=widget.annotationtype
            self.copy_annotation_type(source, dest)
        elif targetType == config.data.target_type['color']:
            # Got a color
            # The structure consists in 4 unsigned shorts: r, g, b, opacity
            (r, g, b, opacity)=struct.unpack('HHHH', selection.get_data())
            widget.annotationtype.setMetaData(config.data.namespace, 'color', u"string:#%04x%04x%04x" % (r, g, b))
            self.controller.notify('AnnotationTypeEditEnd', annotationtype=widget.annotationtype)
        elif targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.get_data())
            begin=long(data['timestamp'])
            content=data.get('comment', None)
            # Create an annotation with the timestamp as begin
            self.controller.create_annotation(begin, widget.annotationtype, content=content)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def new_annotation_type_drag_received_cb(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.annotations.get(uri) for uri in unicode(selection.get_data(), 'utf8').split('\n') ]
            # Create a type
            dest=self.create_annotation_type()
            if dest is None:
                return True

            self.move_or_copy_annotations(sources, dest)
            return True
        elif targetType == config.data.target_type['timestamp']:
            typ=self.create_annotation_type()
            if typ is not None:
                data=decode_drop_parameters(selection.get_data())
                begin=long(data['timestamp'])
                content=data.get('comment', None)
                # Create an annotation of type typ with the timestamp as begin
                self.controller.create_annotation(begin, typ, content=content)
        return False

    def legend_drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop from an annotation-type to the legend
        """
        if targetType == config.data.target_type['annotation-type']:
            source=self.controller.package.annotationTypes.get(unicode(selection.get_data(), 'utf8'))
            # We received a drop. Determine the location.
            s = config.data.preferences['timeline']['interline-height']

            # Correct y value according to scrollbar position
            y += widget.get_parent().get_vscrollbar().get_adjustment().get_value()

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
        if event.button == 1 and getattr(widget, '_single_click_guard', None):
            # Single click on an annotation -> lock inspector
            self.set_annotation(annotation, force=True)
            self.locked_inspector = True
            self.locked_icon.show()
            self.controller.gui.set_current_annotation(annotation)
            # Goto annotation
            c=self.controller
            pos = c.create_position (value=annotation.fragment.begin,
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
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            self.annotation_cb(widget, annotation, event.x)
            return True
        elif event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.controller.gui.edit_element(annotation)
            return True
        elif event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Control + click : set annotation begin/end time to current time
            f=self.annotation_fraction(widget)
            if f < .40:
                at='begin'
            elif f > .60:
                at='end'
            else:
                return False
            f=annotation.fragment
            self.controller.notify('EditSessionStart', element=annotation, immediate=True)
            setattr(f, at, long(self.controller.player.current_position_value))
            if f.begin > f.end:
                f.begin, f.end = f.end, f.begin
            self.controller.notify('AnnotationEditEnd', annotation=annotation)
            self.controller.notify('EditSessionEnd', element=annotation)
            return True
        elif (event.button == 1
              and event.type == Gdk.EventType.BUTTON_PRESS
              and event.get_state() & Gdk.ModifierType.SHIFT_MASK):
            # Shift-click: toggle annotation selection/activation
            if widget.active:
                self.desactivate_annotation (annotation, buttons=[ widget ])
            else:
                self.activate_annotation (annotation, buttons=[ widget ])
            return True
        elif event.button == 1 and event.type == Gdk.EventType.BUTTON_PRESS:
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

        e=Gtk.Entry()
        # get_title will either return the content data, or the computed representation
        e.set_text(self.controller.get_title(annotation))
        e.set_activates_default(True)

        completion = Gtk.EntryCompletion()
        # Build the completion list
        store = Gtk.ListStore(str)
        for c in self.controller.package._indexer.get_completions("", context=annotation):
            store.append([ c ])
        completion.set_model(store)
        completion.set_text_column(0)
        e.set_completion(completion)

        def key_handler(widget, event, ann, cb, controller, close_eb):
            if event.keyval == Gdk.KEY_Return:
                r = helper.title2content(widget.get_text(),
                                         ann.content.data,
                                         ann.type.getMetaData(config.data.namespace, "representation"))
                if r is None:
                    self.controller.log(_("Cannot update the annotation, its representation is too complex"))
                else:
                    if cb:
                        cb('validate', ann)
                    if r != ann.content.data:
                        self.controller.notify('EditSessionStart', element=ann, immediate=True)
                        ann.content.data = r
                        controller.notify('AnnotationEditEnd', annotation=ann)
                        self.controller.notify('EditSessionEnd', element=ann)
                close_eb(widget)
                return True
            elif event.keyval == Gdk.KEY_Escape:
                # Abort and close the entry
                if cb:
                    cb('cancel', ann)
                close_eb(widget)
                return True
            elif event.keyval == Gdk.KEY_Tab:
                # Validate the current annotation and go to the previous/next one
                r = helper.title2content(widget.get_text(),
                                         ann.content.data,
                                         ann.type.getMetaData(config.data.namespace, "representation"))
                if r is None:
                    self.controller.log("Cannot update the annotation, its representation is too complex")
                else:
                    if cb:
                        cb('validate', ann)
                    if r != ann.content.data:
                        self.controller.notify('EditSessionStart', element=ann, immediate=True)
                        ann.content.data = r
                        controller.notify('AnnotationEditEnd', annotation=ann)
                        self.controller.notify('EditSessionEnd', element=ann)
                # Navigate
                b=ann.fragment.begin
                if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                    # Previous.
                    l=[a
                       for a in ann.type.annotations
                       if a.fragment.end < b ]
                    # Sort in reverse order
                    l.sort(key=lambda a: a.fragment.begin, reverse=True)
                else:
                    l=[a
                       for a in ann.type.annotations
                       if a.fragment.begin > b ]
                    l.sort(key=lambda a: a.fragment.begin)
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
        if al.x == -1 and al.y == -1:
            # We have just create the annotation widget. Its child
            # properties wrt. layout are not yet updated. Simply
            # compute them again.
            button.get_parent().put(e, self.unit2pixel(annotation.fragment.begin, absolute=True), self.layer_position[annotation.type])
        else:
            button.get_parent().put(e, al.x, al.y)
        e.connect('size-allocate', grab_focus)
        # Keep the inspector window open on the annotation
        self.set_annotation(annotation)
        if move_cursor:
            d=Gdk.Display.get_default()
            x,y=button.get_window().get_deskrelative_origin()
            d.warp_pointer(d.get_default_screen(), x + 2, y + 2)
        return e

    def annotation_key_press_cb(self, widget, event, annotation):
        """Handle key presses on annotation widgets.
        """
        if widget.keypress(widget, event, annotation):
            return True

        if event.keyval == Gdk.KEY_Return and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Control-return: split at current player position
            self.controller.split_annotation(annotation, self.controller.player.current_position_value)
            return True
        elif event.keyval == Gdk.KEY_a:
            self.controller.gui.adjust_annotation_bound(annotation, 'begin')
        elif event.keyval == Gdk.KEY_A:
            self.controller.gui.adjust_annotation_bound(annotation, 'end')
        elif event.keyval == Gdk.KEY_p:
            # Play
            f=self.annotation_fraction(widget)
            x, y = widget.get_pointer()
            if (x < 0 or y < 0
                or x > widget.get_allocation().width
                or y > widget.get_allocation().height):
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
        elif event.keyval == Gdk.KEY_Return:
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
        if annotation.fragment.begin > self.maximum or annotation.fragment.end < self.minimum:
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
            if self.options['display-relations'] and not self.options['display-all-relations']:
                self.relations_to_draw = []
                self.update_relation_lines()
            return False
        b.connect('focus-out-event', focus_out)

        def focus_in(button, event):
            self.set_annotation(button.annotation)
            if self.options['display-relations'] and not self.options['display-all-relations']:
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
                start=a.get_value()
                finish=a.get_value() + a.get_page_size()
                begin = self.unit2pixel(annotation.fragment.begin, absolute=True)
                if begin >= start and begin <= finish:
                    return False
                end = self.unit2pixel(annotation.fragment.end, absolute=True)
                if end >= start and end <= finish:
                    return False
                if begin <= start and end >= finish:
                    # The annotation bounds are off-screen anyway. Do
                    # not move.
                    return False
                self.scroll_to_annotation(button.annotation)
            return False
        b.connect('focus-in-event', focus_in)

        b.connect('drag-begin', self.annotation_drag_begin)
        # The button can receive drops (to create relations)
        b.connect('drag-data-received', self.annotation_drag_received)
        b.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('annotation', 'tag'),
                        Gdk.DragAction.LINK | Gdk.DragAction.COPY | Gdk.DragAction.MOVE | Gdk.DragAction.ASK )

        def annotation_drag_motion(widget, drag_context, x, y, timestamp):
            actions=drag_context.get_actions()
            # Dragging an annotation. Set the default action to ASK.
            if (config.data.drag_type['annotation'][0][0] in drag_context.list_targets()
                and not actions in ( Gdk.DragAction.LINK, Gdk.DragAction.COPY, Gdk.DragAction.MOVE )):
                # No single action was selected. Force ASK
                Gdk.drag_status(drag_context, Gdk.DragAction.ASK, timestamp)
        b.connect('drag-motion', annotation_drag_motion)

        # Handle scroll actions
        def handle_scroll_event(button, event):
            if not (event.get_state() & Gdk.ModifierType.CONTROL_MASK):
                return False
            if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                i='second-scroll-increment'
            else:
                i='scroll-increment'

            if event.direction == Gdk.ScrollDirection.DOWN or event.direction == Gdk.ScrollDirection.RIGHT:
                incr=-config.data.preferences[i]
            elif event.direction == Gdk.ScrollDirection.UP or event.direction == Gdk.ScrollDirection.LEFT:
                incr=config.data.preferences[i]

            fr=self.annotation_fraction(button)
            f=button.annotation.fragment

            self.controller.notify('EditSessionStart', element=button.annotation, immediate=True)

            newpos = None
            if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                f.begin += incr
                f.end += incr
                newpos = f.begin
            elif fr < .5:
                f.begin += incr
                newpos = f.begin
            elif fr >= .5:
                f.end += incr
                newpos = f.end

            self.controller.player_delayed_scrub(newpos)

            self.controller.notify('AnnotationEditEnd', annotation=button.annotation)
            self.controller.notify('EditSessionEnd', element=button.annotation)

            self.set_annotation(button.annotation)
            button.grab_focus()
            return True

        b.connect('scroll-event', handle_scroll_event)

        b.show_all()
        return b

    def populate (self, callback=None):
        """Populate the annotations widget.

        Since we do it asynchronously in the idle loop, the callback
        can be used to execute actions at the end of the annotation
        widgets creation.
        """
        u2p = self.unit2pixel
        if self.list is None:
            l = self.controller.package.annotations
        else:
            l = self.list

        # Use a list so that the counter variable can be modified in
        # the closure.
        counter = [ 0 ]
        count = 10
        length = len(l)

        #print '----------------------------------------- populate', length
        #import traceback; traceback.print_stack()
        if l:
            old_position = self.inspector_pane.get_position()
            self.inspector_pane.set_position(2)
        def create_annotations(annotations, length):
            i = counter[0]
            if i < length:
                self.quickview.set_text(_("Displaying %(count)d / %(total)d annotations...") % {
                        'count': min(i + count, length),
                        'total': length },
                                        1.0 * (i+count) / length)
                for a in annotations[i:i+count]:
                    self.create_annotation_widget(a)
                counter[0] += count
                return True
            else:
                self.layout.thaw_child_notify()
                if hasattr(self, 'quickview'):
                    self.quickview.set_text(_("Displaying done."))
                    self.locked_inspector = False
                self.controller.gui.set_busy_cursor(False)
                if old_position:
                    self.inspector_pane.set_position(old_position)
                else:
                    # old_position was = 0, because its value was
                    # obtained before the widget was realized. There
                    # is a good chance that the value is now
                    # available.
                    if self.widget.get_window():
                        self.inspector_pane.set_position(max((0, self.widget.get_window().get_width() - 160)))
                if callback:
                    callback()
                return False
        if l:
            self.layout.freeze_child_notify()
            if hasattr(self, 'quickview'):
                self.quickview.set_text(_("Displaying %(count)d / %(total)d annotations...") % {
                        'count': count,
                        'total': length },
                                        1.0 * count / length)
                self.locked_inspector = True
            self.controller.gui.set_busy_cursor(True)
            GObject.idle_add(create_annotations, l, length)
        elif callback:
            callback()

        self.layout.set_size (u2p (self.maximum - self.minimum),
                              max(self.layer_position.values() or (0,))
                              + self.button_height + config.data.preferences['timeline']['interline-height'])

        self.scale_layout.set_size(u2p (self.maximum - self.minimum), 40)

    def draw_current_mark (self):
        u2p = self.unit2pixel

        red=Gdk.color_parse('red2')
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
        p = self.controller.player
        if (self.options['autoscroll'] == 1
            and (p.status == p.PlayingStatus or p.status == p.PauseStatus)):
            self.center_on_position(pos)
        elif (self.options['autoscroll'] == 2
            and (p.status == p.PlayingStatus or p.status == p.PauseStatus)):
            p=self.unit2pixel(pos, absolute=True)
            begin=self.adjustment.get_value()
            end=begin + self.adjustment.get_page_size()
            if p > end or p < begin:
                self.center_on_position(pos)
        self.update_current_mark (pos)
        return True

    def position_reset(self):
        # The position was reset. Deactive active annotations.
        self.deactivate_all()
        self.update_current_mark(self.minimum)
        return True

    def update_scale_height(self, *p):
        """Callback for notify::height of the scale widget.
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

        if abs(height - self.current_scale_height) > 10:
            # The position changed significantly. Update the display.
            self.current_scale_height=height
            self.scale_layout.set_size(self.unit2pixel(self.maximum, absolute=True), 25 + height)
            self.update_scale_screenshots()

    def update_scale_screenshots(self):
        """Redraw scale screenshots in case of zoom change or global pane position change.
        """
        def display_image(widget, event, h, step):
            """Lazy-loading of images
            """
            ic=self.controller.package.imagecache
            png=ic.get(widget.mark, epsilon=step/2)
            if (png == ic.not_yet_available_image
                and 'async-snapshot' in self.controller.player.player_capabilities):
                self.controller.update_snapshot(widget.mark)
            else:
                widget.timestamp=png.timestamp
            widget.set_from_pixbuf(png_to_pixbuf (png, height=max(20, h)))
            if widget.expose_signal is not None:
                widget.disconnect(widget.expose_signal)
                widget.expose_signal=None
            return False

        # Remove previous images
        def remove_image(w):
            if isinstance(w, Gtk.Image):
                self.scale_layout.remove(w)
                return True
        self.scale_layout.foreach(remove_image)

        height = self.current_scale_height
        if height >= 16:
            # Big enough. Let's display screenshots.

            # Evaluate screenshot width.
            width=int(height * 4.0 / 3) + 5
            step = self.pixel2unit(width)
            t = self.minimum

            self.scale_layout.height=height
            self.scale_layout.step=step

            u2p=self.unit2pixel
            while t <= self.maximum:
                # Draw screenshots
                i=Gtk.Image()
                i.mark = t
                i.expose_signal=i.connect('draw', display_image, height, step)
                i.pos = 20
                # Real timestamp of the snapshot. If < 0 (and a
                # large value, since it is after used to get best
                # approximation through abs(pos - i.timestamp)),
                # the snapshot is the uninitialized one.
                i.timestamp=-self.controller.cached_duration
                i.show()
                self.scale_layout.put(i, u2p(i.mark, absolute=True), i.pos)

                t += step

    def draw_marks (self):
        """Draw marks for stream positioning"""
        u2p = self.unit2pixel
        # We want marks every 110 pixels
        step = self.pixel2unit (110)
        t = self.minimum

        font = Pango.FontDescription("sans 10")

        while t <= self.maximum:
            x = u2p(t, absolute=True)

            # Draw label
            l = Gtk.Label(label='|' + helper.format_time (t))
            l.modify_font(font)
            l.mark = t
            l.pos = 1
            l.show()
            self.scale_layout.put (l, x, l.pos)
            t += step
        # Reset current_scale_height to force screenshots redraw
        self.current_scale_height=0
        self.update_scale_height()

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
            # 1-9 keys set the zoom factor
            pos=self.get_middle_position()
            self.fraction_adj.set_value(1.0/pow(2, event.keyval-49))
            self.set_middle_position(pos)
            return True
        elif event.keyval == Gdk.KEY_plus and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Zoom in
            a=self.fraction_adj
            pos=self.get_middle_position()
            a.set_value(min(a.get_value() + a.get_page_increment(), a.get_upper()))
            self.set_middle_position(pos)
        elif event.keyval == Gdk.KEY_plus and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Zoom out
            a=self.fraction_adj
            pos=self.get_middle_position()
            a.set_value(max(a.get_value() - a.get_page_increment(), a.get_lower()))
            self.set_middle_position(pos)
        elif event.keyval == Gdk.KEY_e:
            if isinstance(self.quickview.annotation, Annotation):
                self.controller.gui.edit_element(self.quickview.annotation)
                return True
        elif event.keyval == Gdk.KEY_c:
            self.center_on_position(self.current_position)
            return True
        elif event.keyval == Gdk.KEY_p:
            # Play at the current position
            x, y = win.get_pointer()
            # Note: x is here relative to the visible portion of the window. Thus we must
            # add self.adjustment.get_value
            position=self.pixel2unit(self.adjustment.get_value() + x, absolute=True)
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
        # We received a drop. Determine the location.

        # Correct y value according to scrollbar position
        y += widget.get_parent().get_vscrollbar().get_adjustment().get_value()
        drop_types=[ at
                     for (at, p) in self.layer_position.iteritems()
                     if (y >= p and y <= p + self.button_height + config.data.preferences['timeline']['interline-height']) ]

        if targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.annotations.get(uri) for uri in unicode(selection.get_data(), 'utf8').split('\n') ]
            if drop_types:
                # Copy/Move to a[0]
                if config.data.os == 'win32':
                    # Control/Shift mods for DND is broken on win32. Force ACTION_ASK.
                    ac=Gdk.DragAction.ASK
                else:
                    ac=context.get_actions()
                self.move_or_copy_annotations(sources, drop_types[0], position=self.pixel2unit(self.adjustment.get_value() + x, absolute=True), action=ac)
            else:
                # Maybe we should propose to create a new annotation-type ?
                # Create a type
                dest=self.create_annotation_type()
                if dest is None:
                    return True
                self.move_or_copy_annotations(sources, dest, position=self.pixel2unit(self.adjustment.get_value() + x, absolute=True), action=context.get_actions())
            return True
        elif targetType == config.data.target_type['annotation-type']:
            source=self.controller.package.annotationTypes.get(unicode(selection.get_data(), 'utf8'))
            if drop_types:
                # Copy/Move to drop_types[0]
                if source != drop_types[0]:
                    self.copy_annotation_type(source, drop_types[0])
                else:
                    # Create an annotation in the type.
                    self.controller.create_annotation(position=self.pixel2unit(self.adjustment.get_value() + x, absolute=True),
                                                      type=source,
                                                      duration=self.pixel2unit(Gtk.drag_get_source_widget(context).get_allocation().width),
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
            if drop_types:
                typ=drop_types[0]
            else:
                typ=self.create_annotation_type()
            if typ is not None:
                data=decode_drop_parameters(selection.get_data())
                begin=long(data['timestamp'])
                content=data.get('comment', None)
                # Create an annotation of type typ with the timestamp as begin
                self.controller.create_annotation(begin, typ, content=content)
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
        x=long(p.get_hadjustment().get_value() + x)
        y=long(p.get_vadjustment().get_value() + y)

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
        def set_end_time(action, an):
            if action == 'validate':
                v = self.controller.player.current_position_value
                if v == an.fragment.begin:
                    # Same value. May be that we were paused. Use a
                    # default value so that the annotation remains
                    # accessible.
                    v += 2000
                an.fragment.end = v
            elif action == 'cancel':
                # Delete the annotation
                self.controller.notify('EditSessionStart', element=an, immediate=True)
                self.controller.package.annotations.remove(an)
                self.controller.notify('AnnotationDelete', annotation=an)
            return True

        # Note: event.(x|y) may be relative to a child widget, so
        # we must determine the pointer position
        x, y = widget.get_pointer()
        # Convert x, y (relative to the layout allocation) into
        # values relative to the whole layout size
        p=widget.get_parent()
        x=long(p.get_hadjustment().get_value() + x)
        y=long(p.get_vadjustment().get_value() + y)

        if event.button == 3:
            self.context_cb (timel=self, position=self.pixel2unit(x, absolute=True), height=y)
            return True
        elif event.button == 1:
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
                # Control-click: create annotation + edit it
                ats=[ at
                      for (at, pos) in self.layer_position.iteritems()
                      if (y >= pos and y <= pos + self.button_height) ]
                if not ats:
                    at = None
                else:
                    at=ats[0]
                if at is not None:
                    # Create an annotation and edit it
                    el = self.controller.create_annotation(position=self.controller.player.current_position_value,
                                                           type=at)
                    if el is not None:
                        b=self.create_annotation_widget(el)
                        b.show()
                        self.quick_edit(el, button=b, callback=set_end_time)
                return True

            if event.type == Gdk.EventType._2BUTTON_PRESS:
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
        # Any click in the layout background unlocks the inspector
        self.locked_inspector = False
        self.locked_icon.hide()

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
            x=long(p.get_hadjustment().get_value() + x)
            y=long(p.get_vadjustment().get_value() + y)

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
                if not (event.get_state() & Gdk.ModifierType.CONTROL_MASK or event.get_state() & Gdk.ModifierType.SHIFT_MASK):
                    # Control or shift was not held: it is a new selection.
                    self.unselect_all()

                res=[]
                for widget in self.layout.get_children():
                    if not isinstance(widget, AnnotationWidget):
                        continue
                    #x=self.layout.child_get_property(widget, 'x')
                    #y=self.layout.child_get_property(widget, 'y')
                    # memory leak in container.child_get_property
                    w = widget.get_window()
                    x, y = w.get_position()
                    if ( x >= x1 and x + w.get_width() <= x2
                         and y >= y1 and y + w.get_height() <= y2):
                        self.activate_annotation(widget.annotation, buttons=[ widget ])
                        res.append(widget)

                if not res:
                    # No selected annotations. Propose to create a new one.
                    a=[ at
                        for (at, pos) in self.layer_position.iteritems()
                        if (y1 >= pos and y1 <= pos + self.button_height) ]
                    at = None
                    if a:
                        at = a[0]

                    def create(i):
                        self.controller.create_annotation(position=self.pixel2unit(x1, absolute=True),
                                                          type=at,
                                                          duration=self.pixel2unit(x2-x1))
                        return True
                    def zoom(i):
                        self.zoom_on_region(self.pixel2unit(x1, absolute=True),
                                            self.pixel2unit(x2, absolute=True))
                        return True
                    def restrict(i):
                        self.limit_display(self.pixel2unit(x1, absolute=True),
                                           self.pixel2unit(x2, absolute=True))
                        return True

                    menu=Gtk.Menu()
                    for (label, action) in (
                        (_("Create a new annotation"), create),
                        (_("Zoom on region"), zoom),
                        (_("Restrict display to region"), restrict),
                        ):
                        if at is None and action == create:
                            continue
                        i=Gtk.MenuItem(label)
                        i.connect('activate', action)
                        menu.append(i)
                    menu.show_all()
                    menu.popup_at_pointer(None)
                return True
        return False

    def draw_selection_rectangle(self, invert=False):
        drawable=self.layout.get_bin_window()
        ctx = drawable.cairo_create()
        ctx.set_line_width(1)
        ctx.set_dash([ 10 ])

        if self.layout_selection[1][0] is not None:
            # Invert the previous selection
            #col=pixmap.get_colormap().alloc_color(self.color)
            if invert:
                ctx.set_operator(cairo.OPERATOR_XOR)
            else:
                ctx.set_operator(cairo.OPERATOR_OVER)

            x1=min(self.layout_selection[0][0], self.layout_selection[1][0])
            x2=max(self.layout_selection[0][0], self.layout_selection[1][0])
            y1=min(self.layout_selection[0][1], self.layout_selection[1][1])
            y2=max(self.layout_selection[0][1], self.layout_selection[1][1])

            # Display the starting mark
            ctx.rectangle(x1, y1, x2-x1, y2-y1)
        ctx.stroke()
        return True

    # Draw rectangle during mouse movement
    def layout_motion_notify_cb(self, widget, event):
        if event.is_hint:
            pointer = event.get_window().get_pointer()
            x, y, state = pointer.x, pointer.y, pointer.mask
        else:
            x = event.x
            y = event.y
            state = event.get_state()

        if state & Gdk.ModifierType.BUTTON1_MASK:
            # Display current time
            self.set_annotation(self.pixel2unit(self.adjustment.get_value() + x, absolute=True))
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
        t=self.pixel2unit(self.adjustment.get_value() +  x, absolute=True)
        w=Gtk.drag_get_source_widget(drag_context)
        precision=max(20, self.pixel2unit(1, absolute=False))
        try:
            w._icon.set_cursor(t, precision)
        except AttributeError:
            pass
        actions=drag_context.get_actions()
        # Dragging an annotation. Set the default action to ASK.
        if (config.data.drag_type['annotation'][0][0] in drag_context.list_targets()
            and not actions in ( Gdk.DragAction.LINK, Gdk.DragAction.COPY, Gdk.DragAction.MOVE )):
            # No single action was selected. Force ASK
            Gdk.drag_status(drag_context, Gdk.DragAction.ASK, timestamp)
        return True

    def layout_drag_leave_cb(self, widget, drag_context, timestamp):
        w=Gtk.drag_get_source_widget(drag_context)
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
        menu = Gtk.Menu()

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
                at=self.controller.package.annotationTypes[0]
            self.controller.create_annotation(position, at)
            return True

        item = Gtk.MenuItem(_("Position %s") % helper.format_time(position))
        menu.append(item)

        item = Gtk.SeparatorMenuItem()
        menu.append(item)

        item = Gtk.MenuItem(_("Go to..."))
        item.connect('activate', popup_goto, position)
        menu.append(item)

        item = Gtk.MenuItem(_("New annotation at player time"))
        item.connect('activate', create_annotation, self.controller.player.current_position_value)
        menu.append(item)

        item = Gtk.MenuItem(_("New annotation at mouse position"))
        item.connect('activate', create_annotation, position)
        menu.append(item)

        item = Gtk.MenuItem(_("Selection"))
        if self.get_selected_annotation_widgets():
            item.set_submenu(self.selection_menu(popup=False))
        else:
            item.set_sensitive(False)
        menu.append(item)

        menu.show_all()
        menu.popup_at_pointer(None)
        return True

    def update_adjustment (self):
        """Update the adjustment values depending on the current aspect ratio.
        """
        u2p = self.unit2pixel
        a = self.adjustment

        width = self.maximum - self.minimum

        #a.set_value(u2p(minimum))
        a.set_lower(float(u2p(self.minimum, absolute=True)))
        a.set_upper(float(u2p(self.maximum, absolute=True)))
        a.set_step_increment(min(float(u2p(width / 100)), 10))
        a.set_page_increment(float(u2p(width / 10)))
        a.set_page_size(min(a.get_upper(), self.layout.get_allocation().width))
        #print "Update: from %.2f to %.2f" % (a.get_lower(), a.get_upper())
        a.changed ()

    def scale_event (self, widget=None, data=None):
        if not self.update_lock.acquire(False) or self.layout.get_window() is None:
            # An update is pending. Ignore the scale event.
            return True
        self.update_adjustment ()

        # Update the layout and scale_layout dimensions
        width = self.unit2pixel(self.maximum - self.minimum)
        self.layout.set_size (width, self.layout.get_size()[1])
        self.scale_layout.set_size (width, self.scale_layout.get_size()[1])

        # Update the scale legend
        if config.data.preferences['expert-mode']:
            dur=self.pixel2unit(110) / 1000.0
            self.scale_label.set_text('1mark=%dm%.02fs' % (int(dur / 60), dur % 60))

        self.redraw_event ()
        self.update_lock.release()
        return True

    def layout_resize_event(self, widget=None, event=None, *p):
        """Recompute fraction_adj value when the layout size changes
        """
        parent = self.layout.get_window()
        if not parent:
            return False
        if self.maximum != self.minimum:
            fraction=self.scale.get_value() * float(parent.get_width()) / (self.maximum - self.minimum)
            #print "Layout resize, reset fraction_adj to ", fraction, w
            self.fraction_adj.set_value(fraction)
            self.zoom_combobox.get_child().set_text('%d%%' % long(100 * fraction))
        return False

    def zoom_on_region(self, begin, end):
        # Deactivate autoscroll...
        self.set_autoscroll_mode(0)

        self.scale.set_value(1.3 * (end - begin) / self.layout.get_window().get_width())

        # Center on annotation
        self.center_on_position( (begin + end) / 2 )
        return True

    def limit_display(self, minimum=None, maximum=None):
        """Limit the timeline to the specified or currently displayed area.
        """
        if minimum is None:
            minimum=self.pixel2unit(self.adjustment.get_value(), absolute=True)
            maximum=self.pixel2unit(self.adjustment.get_value() + self.adjustment.get_page_size(), absolute=True)
        # Cannot do the assignment immediately, since unit2pixel uses self.minimum
        self.minimum = minimum
        self.maximum = maximum
        self.update_model(partial_update=True)
        self.fraction_adj.set_value(1.0)
        self.limit_navtools.show()
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
        self.fraction_adj.set_value(1.0)
        self.limit_navtools.hide()
        return True

    def fraction_event (self, widget=None, forced_window_width=0, *p):
        """Set the zoom factor to display the given fraction of the movie.

        fraction is > 0 and <= 1.
        """
        parent = self.layout.get_window()
        if not parent:
            return True
        w = parent.get_width()
        if forced_window_width != 0:
            w = forced_window_width

        if w < 10:
            return True

        if self.minimum == self.maximum:
            return True

        fraction = self.fraction_adj.get_value()

        v = (self.maximum - self.minimum) / float(w) * fraction
        # New width in pixel
        if v < 5 or (self.maximum - self.minimum) / v > 65535:
            self.log(_("Cannot zoom more"))
            return True

        # Is it worth redrawing the whole timeline ?
        if abs(v - self.scale.get_value()) / float(self.scale.get_value()) > 0.01:
            self.scale.set_value(v)
        self.zoom_combobox.get_child().set_text('%d%%' % long(100 * fraction))

        return True

    def layout_scroll_cb(self, widget=None, event=None):
        """Handle mouse scrollwheel events.
        """
        if event.direction == Gdk.ScrollDirection.RIGHT or event.direction == Gdk.ScrollDirection.LEFT:
            self.can_do_horizontal_scroll = True

        zoom=event.get_state() & Gdk.ModifierType.CONTROL_MASK
        if zoom:
            # Control+scroll: zoom in/out
            a = self.fraction_adj
            incr = a.get_page_increment()
            # Memorize mouse position (in units)
            # Get x, y (relative to the layout allocation)
            x,y=widget.get_pointer()
            mouse_position=self.pixel2unit(event.x, absolute=True)
        else:
            # Plain scroll: scroll the timeline
            if (self.can_do_horizontal_scroll
                and (event.direction == Gdk.ScrollDirection.UP
                     or event.direction == Gdk.ScrollDirection.DOWN)):
                # Vertical scroll with a device that knows how to do horizontal. Let's scroll vertically
                a = self.vadjustment
                incr = a.get_step_increment()
            else:
                a = self.adjustment
                incr = a.get_step_increment()

        if event.direction == Gdk.ScrollDirection.DOWN or event.direction == Gdk.ScrollDirection.RIGHT:
            a.set_value(helper.clamp(a.get_value() + incr,
                                     a.get_lower(),
                                     a.get_upper() - a.get_page_size()))
        elif event.direction == Gdk.ScrollDirection.UP or event.direction == Gdk.ScrollDirection.LEFT:
            a.set_value(helper.clamp(a.get_value() - incr,
                                     a.get_lower(),
                                     a.get_upper() - a.get_page_size()))

        # Try to preserve the mouse position when zooming
        if zoom:
            self.adjustment.set_value(self.unit2pixel(mouse_position, absolute=True) - x)
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
                                  self.unit2pixel(w.annotation.fragment.begin, absolute=True),
                                  self.layer_position[w.annotation.type])
            return True

        if self.old_scale_value != self.scale.get_value():
            self.old_scale_value = self.scale.get_value()
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
        width=120
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

        if layout.get_parent() is not None:
            p = layout.get_parent().get_parent()
            if p is not None:
                p.set_position (width + 60)

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
        height=0

        def navigate(b, event, direction, typ):
            p=self.controller.player.current_position_value
            if direction == 'next':
                l=[a
                   for a in typ.annotations
                   if a.fragment.begin > p ]
                l.sort(key=lambda a: a.fragment.begin)
            else:
                l=[a
                   for a in typ.annotations
                   if a.fragment.begin < p ]
                # Sort in reverse order
                l.sort(key=lambda a: a.fragment.begin, reverse=True)
            if l:
                a=l[0]
                self.controller.update_status("set", position=a.fragment.begin)
                self.set_annotation(a)
            return True

        def restrict_playing(m, at, w):
            self.restrict_playing(at, w)
            return True

        def annotationtype_keypress_handler(widget, event, at):
            if widget.keypress(widget, event, at):
                return True
            elif event.keyval == Gdk.KEY_a:
                # Adjust bounds
                self.controller.gui.adjust_annotationtype_bounds(at)
            elif event.keyval == Gdk.KEY_Return:
                def set_end_time(action, an):
                    if action == 'validate':
                        v = self.controller.player.current_position_value
                        if v == an.fragment.begin:
                            # Same value. May be that we were paused. Use a
                            # default value so that the annotation remains
                            # accessible.
                            v += 2000
                        an.fragment.end = v
                    elif action == 'cancel':
                        # Delete the annotation
                        self.controller.notify('EditSessionStart', element=an, immediate=True)
                        self.controller.package.annotations.remove(an)
                        self.controller.notify('AnnotationDelete', annotation=an)
                    return True

                if (self.controller.player.status != self.controller.player.PlayingStatus
                    and self.controller.player.status != self.controller.player.PauseStatus):
                    return True
                # Create a new annotation
                el=self.controller.create_annotation(position=long(self.controller.player.current_position_value),
                                                     type=widget.annotationtype)
                if el is not None:
                    b=self.create_annotation_widget(el)
                    b.show()
                    self.quick_edit(el, button=b, callback=set_end_time)
                return True
            elif event.keyval == Gdk.KEY_space:
                self.restrict_playing(at, widget)
                return True
            return False

        def annotationtype_buttonpress_handler(widget, event, t):
            """Display the popup menu when right-clicking on annotation type.
            """
            if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
                menu=advene.gui.popup.Menu(t, controller=self.controller)
                menu.popup()
                return True
            return False

        for t in self.annotationtypes:
            b=AnnotationTypeWidget(annotationtype=t, container=self)
            b.set_tooltip_text(_("From schema %s") % self.controller.get_title(t.schema))
            layout.put (b, 20, self.layer_position[t])
            b.update_widget()
            b.show_all()
            b.connect('key-press-event', annotationtype_keypress_handler, t)
            b.connect('button-press-event', annotationtype_buttonpress_handler, t)

            def focus_in(button, event):
                for w in layout.get_children():
                    if isinstance(w, AnnotationTypeWidget) and w.annotationtype.schema == button.annotationtype.schema:
                        w.set_highlight(True)
                self.set_annotation(button.annotationtype)

                a=self.legend.get_vadjustment()
                y=self.legend.child_get_property(button, 'y')
                if y < a.get_value():
                    pos=max(a.get_lower(), y)
                elif y > a.get_value() + a.get_page_size():
                    pos=min(a.get_upper() - a.get_page_size(), y)
                else:
                    pos=None
                if pos is not None:
                    a.set_value(pos)
                return False

            def focus_out(button, event):
                for w in layout.get_children():
                    if isinstance(w, AnnotationTypeWidget) and w.highlight:
                        w.set_highlight(False)
                return False

            b.connect('focus-in-event', focus_in)
            b.connect('focus-out-event', focus_out)

            # The button can receive drops (to transmute annotations)
            b.connect('drag-data-received', self.annotation_type_drag_received_cb)
            b.drag_dest_set(Gtk.DestDefaults.MOTION |
                            Gtk.DestDefaults.HIGHLIGHT |
                            Gtk.DestDefaults.ALL,
                            config.data.get_target_types('annotation',
                                                         'annotation-type',
                                                         'timestamp',
                                                         'color'),
                            Gdk.DragAction.COPY | Gdk.DragAction.LINK | Gdk.DragAction.MOVE)
            # The button can generate drags (to change annotation type order)
            enable_drag_source(b, t, self.controller)

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
            p.get_style_context().add_class('restrict_playing_button')
            p.set_playing = set_playing.__get__(p)
            p.annotationtype=t
            p.set_size_request(20, self.button_height)
            p.set_tooltip_text(_('Restrict playing to this annotation-type'))
            layout.put (p, 0, self.layer_position[t])

            # At the right of the annotation type : prev/next buttons
            nav=Gtk.Arrow(Gtk.ArrowType.LEFT, Gtk.ShadowType.IN)
            nav.set_size_request(16, self.button_height)
            nav.annotationtype=t
            nav.set_tooltip_text(_('Goto previous annotation'))
            eb=Gtk.EventBox()
            eb.connect('button-press-event', navigate, 'prev', t)
            eb.add(nav)
            eb.prev=True
            # Put it in an arbitrary location. It will be moved by resize_legend_widget
            layout.put (eb, 102, self.layer_position[t])

            nav=Gtk.Arrow(Gtk.ArrowType.RIGHT, Gtk.ShadowType.IN)
            nav.set_size_request(16, self.button_height)
            nav.annotationtype=t
            nav.set_tooltip_text(_('Goto next annotation'))
            eb=Gtk.EventBox()
            eb.connect('button-press-event', navigate, 'next', t)
            eb.add(nav)
            eb.next=True
            # Put it in an arbitrary location. It will be moved by resize_legend_widget
            layout.put (eb, 112, self.layer_position[t])

        # Add the 'New type' button at the end
        b=Gtk.Button()
        l=Gtk.Label()
        l.set_markup('<b><span style="normal">%s</span></b>' % _('+'))
        l.modify_font(self.annotation_type_font)
        b.add(l)
        b.set_tooltip_text(_('Create a new annotation type'))
        b.set_size_request(-1, self.button_height)
        layout.put (b, 0, height - 2 * self.button_height + config.data.preferences['timeline']['interline-height'])
        b.annotationtype=None
        b.show()

        b.connect('clicked', self.create_annotation_type)
        # The button can receive drops (to create type and transmute annotations)
        b.connect('drag-data-received', self.new_annotation_type_drag_received_cb)
        b.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('annotation', 'timestamp'),
                        Gdk.DragAction.LINK | Gdk.DragAction.MOVE)

        # Set a default size. We will resize it anyway.
        layout.set_size(200, height)
        layout.show()
        self.resize_legend_widget(layout)
        return

    def get_full_widget(self):
        """Return the layout with its controllers.
        """
        vbox = Gtk.VBox()
        vbox.connect('key-press-event', self.layout_key_press_cb)

        hb=Gtk.HBox()
        toolbar = self.get_toolbar()
        hb.add(toolbar)

        self.quickview=QuickviewBar(self.controller)

        # The annotation view button should be placed in the toolbar,
        # but this prevents DND from working correctly.
        def drag_sent(widget, context, selection, targetType, eventTime, name):
            if targetType == config.data.target_type['adhoc-view']:
                selection.set(selection.get_target(), 8,
                              urllib.urlencode( {
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

        b=get_small_stock_button(Gtk.STOCK_FIND, open_annotation_display)
        b.set_tooltip_text(_('Open an annotation display view'))
        b.connect('drag-data-get', drag_sent, 'annotationdisplay')
        b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                          config.data.get_target_types('adhoc-view'), Gdk.DragAction.COPY)
        hb.pack_start(b, False, True, 0)

        b=get_pixmap_button('montage.png', open_slave_montage)
        b.set_tooltip_text(_('Open a slave montage view (coordinated zoom level)'))
        b.connect('drag-data-get', drag_sent, 'montage')
        b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                          config.data.get_target_types('adhoc-view'), Gdk.DragAction.COPY)
        hb.pack_start(b, False, True, 0)

        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(self.player_toolbar)

        vbox.pack_start(hb, False, True, 0)

        vbox.add (self.get_packed_widget())

        vbox.pack_start(self.quickview, False, True, 0)

        return vbox

    def selection_menu(self, button=None, popup=True):
        """Display the menu for the selection.
        """
        def center_and_zoom(m, sel):
            begin=min( [ w.annotation.fragment.begin for w in sel ] )
            end=max( [ w.annotation.fragment.end for w in sel ] )
            self.zoom_on_region(begin, end)
            return True

        def create_static(m, sel):
            v=self.controller.create_static_view([ w.annotation for w in sel])
            if v is not None:
                self.controller.gui.edit_element(v)
            return True

        def display_stats(m, sel):
            self.controller.gui.display_statistics([ w.annotation for w in sel],
                                                   label=_("<b>Statistics about current selection</b>\n\n"))
            return True

        m=Gtk.Menu()
        l=self.get_selected_annotation_widgets()
        n=len(l)
        if n == 0:
            i=Gtk.MenuItem(_('No selected annotation'))
            m.append(i)
            i.set_sensitive(False)
        else:
            i=Gtk.MenuItem(_('%d selected annotation(s)') % n)
            m.append(i)
            i.set_sensitive(False)
            i=Gtk.SeparatorMenuItem()
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
                (_('Display statistics'), display_stats),
                ):
                i=Gtk.MenuItem(label)
                i.connect('activate', action, l)
                m.append(i)

        m.show_all()
        if popup:
            m.popup(None, None, None, 0, Gtk.get_current_event_time())
        return m

    def get_packed_widget (self):
        """Return the widget packed into a scrolledwindow."""
        vbox = Gtk.VBox ()

        content_pane = Gtk.Paned()
        content_pane.set_name('content_pane')

        # The layout can receive drops
        self.legend.connect('drag-data-received', self.legend_drag_received)
        self.legend.drag_dest_set(Gtk.DestDefaults.MOTION |
                                  Gtk.DestDefaults.HIGHLIGHT |
                                  Gtk.DestDefaults.ALL,
                                  config.data.get_target_types('annotation-type'),
                                  Gdk.DragAction.COPY | Gdk.DragAction.LINK)

        sw_legend = Gtk.ScrolledWindow ()
        sw_legend.set_name('sw_legend')
        sw_legend.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        sw_legend.set_placement(Gtk.CornerType.TOP_RIGHT)
        sw_legend.add (self.legend)
        content_pane.add1 (sw_legend)

        # Vertical auto-scroll when DNDing
        def scroll_on_drag(widget, drag_context, x, y, timestamp, vertical=True):
            adj=widget.get_adjustment()
            v=adj.get_value()
            if vertical:
                pointer=y
                ref=widget.get_allocation().height / 2
            else:
                pointer=x
                ref=widget.get_allocation().width / 2
            if pointer > ref:
                # Try to scroll down
                v += max(adj.get_step_increment(), adj.get_page_increment() / 3)
            else:
                v -= max(adj.get_step_increment(), adj.get_page_increment() / 3)
            adj.set_value(helper.clamp(v, 0, adj.get_upper() - adj.get_page_size()))
            return True
        sb=sw_legend.get_vscrollbar()
        sb.drag_dest_set(Gtk.DestDefaults.MOTION |
                         Gtk.DestDefaults.HIGHLIGHT |
                         Gtk.DestDefaults.ALL,
                         config.data.get_target_types('annotation', 'timestamp', 'annotation-type'),
                         Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        sb.connect('drag-motion', scroll_on_drag, True)

        sw_layout = Gtk.ScrolledWindow ()
        sw_layout.set_name('sw_layout')
        sw_layout.set_policy (Gtk.PolicyType.ALWAYS, Gtk.PolicyType.AUTOMATIC)
        sw_layout.set_hadjustment (self.adjustment)
        self.vadjustment = sw_legend.get_vadjustment()
        sw_layout.set_vadjustment (self.vadjustment)
        sw_layout.add (self.layout)
        content_pane.add2 (sw_layout)

        # Fix step_increment for vadjustment
        sw_layout.get_vadjustment().step_increment=10

        sb=sw_layout.get_hscrollbar()
        sb.drag_dest_set(Gtk.DestDefaults.MOTION |
                         Gtk.DestDefaults.HIGHLIGHT |
                         Gtk.DestDefaults.ALL,
                         config.data.get_target_types('annotation', 'timestamp', 'annotation-type'),
                         Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        sb.connect('drag-motion', scroll_on_drag, False)

        sb=sw_layout.get_vscrollbar()
        sb.drag_dest_set(Gtk.DestDefaults.MOTION |
                         Gtk.DestDefaults.HIGHLIGHT |
                         Gtk.DestDefaults.ALL,
                         config.data.get_target_types('annotation', 'timestamp', 'annotation-type'),
                         Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        sb.connect('drag-motion', scroll_on_drag)

        # Now build the scale_pane
        scale_pane = Gtk.Paned()
        scale_pane.set_name('scale_pane')

        vb=Gtk.VBox()
        self.scale_label = Gtk.Label(label='Scale')
        vb.pack_start(self.scale_label, False, True, 0)
        if not config.data.preferences['expert-mode']:
            self.scale_label.hide()
            self.scale_label.set_no_show_all(True)

        self.limit_navtools = Gtk.HBox()

        def navigate(button, event, direction):
            # Navigate to the previous/next page, when display is limited
            page_duration=self.pixel2unit(self.adjustment.get_page_size(), absolute=False)
            if direction == -1:
                # Previous page
                mi = max(self.minimum - page_duration, 0)
            elif direction == +1:
                # Next page
                mi = self.minimum + page_duration
                if mi > self.controller.cached_duration:
                    return True
            self.limit_display(mi, mi + page_duration)
            return True

        # At the right of the annotation type : prev/next buttons
        nav=Gtk.Arrow(Gtk.ArrowType.LEFT, Gtk.ShadowType.IN)
        nav.set_size_request(16, 16)
        nav.set_tooltip_text(_('Goto previous page'))
        eb=Gtk.EventBox()
        eb.connect('button-press-event', navigate, -1)
        eb.add(nav)
        self.limit_navtools.pack_start(eb, False, True, 0)

        b=get_small_stock_button(Gtk.STOCK_ZOOM_100, self.unlimit_display)
        b.set_tooltip_text(_("Display whole movie"))
        self.limit_navtools.pack_start(b, False, True, 0)

        nav=Gtk.Arrow(Gtk.ArrowType.RIGHT, Gtk.ShadowType.IN)
        nav.set_size_request(16, 16)
        nav.set_tooltip_text(_('Goto next page'))
        eb=Gtk.EventBox()
        eb.connect('button-press-event', navigate, +1)
        eb.add(nav)
        self.limit_navtools.pack_start(eb, False, True, 0)

        # Show contained widgets
        self.limit_navtools.show_all()
        # Do not honour future show_all calls, so that the navtools remain hidden
        self.limit_navtools.set_no_show_all(True)
        vb.add(self.limit_navtools)
        self.limit_navtools.hide()

        scale_pane.add1(vb)

        sw_scale=Gtk.ScrolledWindow()
        sw_scale.set_name('sw_scale')
        sw_scale.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        sw_scale.set_hadjustment (sw_layout.get_hadjustment())
        sw_scale.add(self.scale_layout)
        scale_pane.add2(sw_scale)

        def synchronize_position(w, param, other_pane):
            other_pane.set_position(w.props.position)
            return True
        content_pane.connect('notify::position', synchronize_position, scale_pane)
        def ignore(*p):
            return True
        scale_pane.connect('button-press-event', ignore)
        scale_pane.connect('button-release-event', ignore)

        self.global_pane=Gtk.Paned.new(Gtk.Orientation.VERTICAL)
        self.global_pane.set_name('global_pane')

        self.global_pane.add1(scale_pane)
        self.global_pane.add2(content_pane)

        self.global_pane.set_position(50)
        self.global_pane.connect('notify::position', self.update_scale_height)

        vbox.add (self.global_pane)

        content_pane.set_position (max(self.legend.get_size()[0], 100))

        self.inspector_pane=Gtk.Paned()
        self.inspector_pane.set_name('inspector_pane')
        self.inspector_pane.pack1(vbox, resize=True, shrink=True)
        a=AnnotationDisplay(controller=self.controller)
        self.inspector_frame=Gtk.Frame()
        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(_('Inspector')), False, False, 0)
        def unlock(b):
            b.hide()
            self.locked_inspector = False
            return True
        self.locked_icon = get_pixmap_button('small_locked.png', unlock)
        self.locked_icon.set_tooltip_text(_("Inspector locked. Click here or in the timeline background to unlock."))
        self.locked_icon.set_no_show_all(True)
        hbox.pack_start(self.locked_icon, False, True, 0)
        self.inspector_frame.set_label_widget(hbox)

        self.inspector_frame.add(a.widget)
        self.inspector_pane.pack2(self.inspector_frame, resize=False, shrink=True)
        self.controller.gui.register_view (a)
        a.set_master_view(self)
        a.widget.show_all()

        return self.inspector_pane

    def get_toolbar(self):
        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.annotations.get(uri) for uri in unicode(selection.get_data(), 'utf8').split('\n') ]
                if sources:
                    batch_id=object()
                    for a in sources:
                        self.controller.delete_element(a, batch=batch_id)
                return True
            return False

        b=Gtk.ToolButton(stock_id=Gtk.STOCK_DELETE)
        b.set_tooltip_text(_('Delete the selected annotations or drop an annotation here to delete it.'))
        b.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('annotation'),
                        Gdk.DragAction.MOVE )
        b.connect('drag-data-received', remove_drag_received)
        b.connect('clicked', self.selection_delete)
        tb.insert(b, -1)

        # Annotation-type selection button
        def annotationtype_selection_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation-type']:
                source=self.controller.package.annotationTypes.get(unicode(selection.get_data(), 'utf8'))
                if source in self.annotationtypes:
                    self.annotationtypes.remove(source)
                    self.update_model(partial_update=True)
            else:
                print 'Unknown target type for drop: %d' % targetType
            return True

        b=Gtk.ToolButton(stock_id=Gtk.STOCK_SELECT_COLOR)
        b.set_tooltip_text(_('Drag an annotation type here to remove it from display.\nClick to edit all displayed types'))
        b.connect('clicked', self.edit_annotation_types)
        b.connect('drag-data-received', annotationtype_selection_drag_received)
        b.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('annotation-type'),
                        Gdk.DragAction.MOVE | Gdk.DragAction.COPY)
        tb.insert(b, -1)

        # Selection menu
        b=get_pixmap_toolbutton('selection.png', self.selection_menu)
        b.set_tooltip_text(_('Selection actions'))
        tb.insert(b, -1)
        b.set_sensitive(False)
        self.selection_button=b

        # Relation display toggle
        def handle_toggle(b, option):
            self.options[option]=b.get_active()
            if option == 'display-all-relations':
                region = self.layout.get_window().get_clip_region()
                if region:
                    self.layout.get_window().invalidate_region(region, True)
            return True

        self.display_relations_toggle=Gtk.ToggleToolButton(stock_id=Gtk.STOCK_REDO)
        self.display_relations_toggle.set_tooltip_text(_('Display relations'))
        self.display_relations_toggle.set_active(self.options['display-relations'])
        self.display_relations_toggle.connect('toggled', handle_toggle, 'display-relations')
        tb.insert(self.display_relations_toggle, -1)

        self.display_all_relations_toggle=Gtk.ToggleToolButton(stock_id=Gtk.STOCK_INFO)
        self.display_all_relations_toggle.set_tooltip_text(_('Display all relations'))
        self.display_all_relations_toggle.set_active(self.options['display-all-relations'])
        self.display_all_relations_toggle.connect('toggled', handle_toggle, 'display-all-relations')
        tb.insert(self.display_all_relations_toggle, -1)

        # Separator
        tb.insert(Gtk.SeparatorToolItem(), -1)

        def zoom_entry(entry):
            f=unicode(entry.get_text())

            i=re.findall(r'\d+', f)
            if i:
                f=int(i[0])/100.0
            else:
                return True
            pos=self.get_middle_position()
            self.fraction_adj.set_value(f)
            self.set_middle_position(pos)
            return True

        def zoom_change(combo):
            v=combo.get_current_element()
            if isinstance(v, float):
                pos=self.get_middle_position()
                self.fraction_adj.set_value(v)
                self.set_middle_position(pos)
            return True

        def zoom(i, factor):
            pos=self.get_middle_position()
            self.fraction_adj.set_value(self.fraction_adj.get_value() * factor)
            self.set_middle_position(pos)
            return True

        i=Gtk.ToolButton(stock_id=Gtk.STOCK_ZOOM_OUT)
        i.connect('clicked', zoom, 1.3)
        i.set_tooltip_text(_('Zoom out'))
        tb.insert(i, -1)

        i=Gtk.ToolButton(stock_id=Gtk.STOCK_ZOOM_IN)
        i.connect('clicked', zoom, .7)
        i.set_tooltip_text(_('Zoom in'))
        tb.insert(i, -1)

        self.zoom_combobox=dialog.list_selector_widget(members=[
                ( f, '%d%%' % long(100*f) )
                for f in [
                    (1.0 / pow(1.5, n)) for n in range(0, 10)
                    ]
                ],
                                                       entry=True,
                                                       callback=zoom_change)
        self.zoom_combobox.get_child().connect('activate', zoom_entry)
        self.zoom_combobox.get_child().set_width_chars(4)
        i=Gtk.ToolItem()
        i.add(self.zoom_combobox)
        tb.insert(i, -1)

        i=Gtk.ToolButton(stock_id=Gtk.STOCK_ZOOM_100)
        i.connect('clicked', lambda i: self.fraction_adj.set_value(1.0))
        tb.insert(i, -1)

        tb.insert(Gtk.SeparatorToolItem(), -1)

        i=Gtk.ToolItem()
        i.add(self.autoscroll_choice)
        tb.insert(i, -1)

        def center_on_current_position(*p):
            if (self.controller.player.status == self.controller.player.PlayingStatus
                or self.controller.player.status == self.controller.player.PauseStatus):
                self.center_on_position(self.current_position)
            return True

        for tooltip, icon, callback in (
            (_('Preferences'), Gtk.STOCK_PREFERENCES, self.edit_preferences),
            (_('Center on current player position.'), Gtk.STOCK_JUSTIFY_CENTER, center_on_current_position),
            ):
            b=Gtk.ToolButton(stock_id=icon)
            b.set_tooltip_text(tooltip)
            b.connect('clicked', callback)
            tb.insert(b, -1)

        def loop_toggle_cb(b):
            if not b.get_active():
                # If we deactivate the locked looping feature, then also
                # disable the player loop toggle.
                self.controller.gui.player_toolbar.buttons['loop'].set_active(False)
            return True

        self.loop_toggle_button=Gtk.ToggleToolButton(stock_id=Gtk.STOCK_REFRESH)
        self.loop_toggle_button.connect('toggled', loop_toggle_cb)
        self.loop_toggle_button.set_tooltip_text(_('Automatically activate loop when clicking on an annotation'))
        tb.insert(self.loop_toggle_button, -1)

        ti=Gtk.SeparatorToolItem()
        ti.set_expand(True)
        ti.set_property('draw', False)
        tb.insert(ti, -1)

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

        hbox = Gtk.HBox()
        selectedtree = Gtk.TreeView(model=selected_store)
        cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Displayed'), cell, text=0)
        selectedtree.append_column(column)

        selectedtree.set_reorderable(True)
        selectedtree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        notselectedtree = Gtk.TreeView(model=notselected_store)
        cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Not displayed'), cell, text=0)
        notselectedtree.append_column(column)
        notselectedtree.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)

        actions = Gtk.VBox()

        def transfer(b, source, dest):
            selection = source.get_selection ()
            if not selection:
                return True
            store, paths = selection.get_selected_rows()

            # Keep a stable reference of the selected rows, since we
            # will remove them iteratively from the source model
            rows = [ Gtk.TreeRowReference(store, path) for path in paths ]

            m=dest.get_model()
            for r in rows:
                path=r.get_path()
                if path is None:
                    # Should not happen...
                    print 'Strange...'
                    continue
                it=store.get_iter(path)
                # Add el to dest
                m.append(list(store[path]))
                store.remove(it)
            return True

        def transferall(b, source, dest):
            s=source.get_model()
            d=dest.get_model()
            while True:
                it=s.get_iter_first()
                if it is None:
                    break
                d.append(list(s[it]))
                s.remove(it)
            return True

        def row_activated(treeview, path, view_column, source, dest):
            transfer(None, source, dest)
            return True

        b=Gtk.Button('<<<')
        b.connect('clicked', transfer, notselectedtree, selectedtree)
        notselectedtree.connect('row_activated', row_activated, notselectedtree, selectedtree)
        actions.add(b)

        b=Gtk.Button(_('< All <'))
        b.connect('clicked', transferall, notselectedtree, selectedtree)
        actions.add(b)

        b=Gtk.Button(_('> All >'))
        b.connect('clicked', transferall, selectedtree, notselectedtree)
        actions.add(b)

        b=Gtk.Button('>>>')
        b.connect('clicked', transfer, selectedtree, notselectedtree)
        selectedtree.connect('row-activated', row_activated, selectedtree, notselectedtree)
        actions.add(b)

        sw1 = Gtk.ScrolledWindow()
        sw1.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw1.add(selectedtree)
        hbox.add(sw1)

        hbox.pack_start(actions, False, False, 0)

        sw2 = Gtk.ScrolledWindow()
        sw2.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw2.add(notselectedtree)
        hbox.add(sw2)

        hbox.show_all()

        # The widget is built. Put it in the dialog.
        d = Gtk.Dialog(title=_('Displayed annotation types'),
                       parent=self.controller.gui.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT | Gtk.DialogFlags.MODAL,
                       buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ))

        d.vbox.pack_start(hbox, True, True, 0)
        hbox.set_size_request(600, 400)
        d.connect('key-press-event', dialog.dialog_keypressed_cb)

        d.show()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == Gtk.ResponseType.OK:
            self.annotationtypes = [ at[1] for at in selected_store ]
            self.package_from_init = None
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
        return self.pixel2unit( a.get_value() + a.get_page_size() / 2, absolute=True )

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
            self.controller.delete_element(w.annotation, batch=batch_id)
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
                l.sort(key=lambda a: a.fragment.begin)
                end=max( a.fragment.end for a in l )
                # Resize the first annotation
                self.controller.notify('EditSessionStart', element=l[0], immediate=True)
                l[0].fragment.end=end
                self.controller.notify('AnnotationEditEnd', annotation=l[0], batch=batch_id)
                self.controller.notify('EditSessionEnd', element=l[0])
                # Remove all others
                for a in l[1:]:
                    self.controller.delete_element(a, batch=batch_id)
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
                                  icon=Gtk.MessageType.ERROR)
            return True
        batch_id=object()
        for w in selection:
            self.controller.notify('EditSessionStart', element=w.annotation, immediate=True)
            w.annotation.addTag(tag)
            self.controller.notify('AnnotationEditEnd', annotation=w.annotation, batch=batch_id)
            self.controller.notify('EditSessionEnd', element=w.annotation)
        return True
