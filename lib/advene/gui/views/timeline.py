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
import sre
import cgi
import struct
import gtk
try:
    import cairo
except ImportError:
    pass
import pango
from gettext import gettext as _

# Advene part
import advene.core.config as config

from advene.model.schema import AnnotationType
from advene.model.annotation import Annotation, Relation
from advene.model.fragment import MillisecondFragment
from advene.gui.views import AdhocView
import advene.gui.edit.elements
from advene.gui.edit.create import CreateElementPopup

import advene.util.helper as helper
import advene.gui.util
try:
    from advene.gui.widget import AnnotationWidget, AnnotationTypeWidget
except:
    AnnotationWidget=None

import advene.gui.edit.elements

name="Timeline view plugin"

def register(controller):
    controller.register_viewclass(TimeLine)

parsed_representation = sre.compile(r'^here/content/parsed/([\w\d_\.]+)$')

class QuickviewBar(gtk.HBox):
    def __init__(self, controller=None):
        gtk.HBox.__init__(self)
        self.controller=controller
        self.begin=gtk.Label()
        self.end=gtk.Label()
        self.content=gtk.Label()

        self.annotation=None

        self.pack_start(self.begin, expand=False)
        self.pack_start(self.end, expand=False)
        self.add(self.content)

    def set_annotation(self, a=None):
        if a is None:
            b=""
            e=""
            c=""
        else:
            b=helper.format_time(a.fragment.begin)
            e=" - " + helper.format_time(a.fragment.end) + ": "
            c=self.controller.get_title(a)
            if len(c) > 40:
                c=c[:40]
        self.annotation=a
        self.begin.set_text(b)
        self.end.set_text(e)
        self.content.set_markup("<b>%s</b>" % c)

class TimeLine(AdhocView):
    """Representation of a set of annotations placed on a timeline.

    If l is None, then use controller.package.annotations (and handle
    updates accordingly).

    There are 2 adjustments used to adjust the display scale: 

       * self.ratio_adj stores how many units does a pixel
         represent. It is an absolute value (and generally integer:
         given that units are milliseconds, we should not need to
         display fractions of ms.

       * self.fraction_adj stores the fraction of the whole stream
         displayed in the window. It thus depends on both the
         self.ratio_adj and the widget size.

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

        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            (_("Save view"), self.save_view),
            )
        self.options = {
            'highlight': True,
            # Autoscroll: 0: None, 1: continuous, 2: discrete
            'autoscroll': 1,
            'display-relations': True,
            'display-relation-type': True,
            'display-relation-content': True,
            }
        self.controller=controller

        if parameters:
            opt, arg = self.load_parameters(parameters)
            self.options.update(opt)
            ats=[]
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
                    # Override a potentially existing value of l
                    l=c.evaluateValue(v)
            if ats:
                annotationtypes=ats

        self.list = elements
        self.annotationtypes = annotationtypes
        self.tooltips = gtk.Tooltips()

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

        self.colors = {
            'active': gtk.gdk.color_parse ('#fdfd4b'),
            'inactive': gtk.Button().get_style().bg[0],
            'background': gtk.gdk.color_parse('red'),
            'relations': gtk.gdk.color_parse('orange'),
            'white': gtk.gdk.color_parse('white'),
            }

        def handle_toggle(b, option):
            self.options[option]=b.get_active()
            return True

        def handle_autoscroll_combo(combo):
            self.options['autoscroll'] = combo.get_current_element()
            return True

        # Scroll the window to display the activated annotations
        self.autoscroll_choice = advene.gui.util.list_selector_widget(
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
        # ratio_adjustment.value = unit by pixel
        # Unit = ms
        self.ratio_adjustment = gtk.Adjustment (value=36000,
                                                lower=5,
                                                upper=36000,
                                                step_incr=5,
                                                page_incr=1000)
        self.ratio_adjustment.connect ("value-changed", self.ratio_event)
        self.ratio_adjustment.connect ("changed", self.ratio_event)

        # The same value in relative form
        self.fraction_adj = gtk.Adjustment (value=1.0,
                                            lower=0.01,
                                            upper=1.0,
                                            step_incr=.01,
                                            page_incr=.02)
        self.fraction_adj.connect ("value-changed", self.fraction_event)
        self.fraction_adj.connect ("changed", self.fraction_event)

        self.layout_size=(None, None)

        self.layout = gtk.Layout ()
	if config.data.os == 'win32':
		self.layout.add_events(gtk.gdk.BUTTON_PRESS_MASK)
	#to catch mouse clics on win32
        #self.layout.bin_window.get_colormap().alloc_color(self.colors['relations'])
        self.layout.connect('scroll_event', self.layout_scroll_cb)
        self.layout.connect('key_press_event', self.layout_key_press_cb)
        self.layout.connect('button_press_event', self.layout_button_press_cb)
        self.layout.connect('size_allocate', self.layout_resize_event)
        self.layout.connect('map', self.layout_resize_event)
        self.layout.connect('expose_event', self.draw_background)
        self.layout.connect_after('expose_event', self.draw_relation_lines)

        # The layout can receive drops (to resize annotations)
        self.layout.connect("drag_data_received", self.layout_drag_received)
        self.layout.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation-resize'], gtk.gdk.ACTION_LINK)

        self.old_ratio_value = self.ratio_adjustment.value

        # Lines to draw in order to indicate related annotations
        self.relations_to_draw = []

        # Current position in units
        self.current_position = minimum

        # Used for paste operations
        self.selected_position = 0
        self.selection_marker = None

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

    def get_save_arguments(self):
        # FIXME: add a dialog to ask for what elements to save
        arguments = [ ('annotation-type', at.id) for at in self.annotationtypes ]
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

    def draw_relation_lines_old(self, layout, event):
        if not self.relations_to_draw:
            return False
        drawable=layout.bin_window
        gc=drawable.new_gc(foreground=self.colors['relations'],
                           background=self.colors['relations'],
                           line_width=1,
                           cap_style=gtk.gdk.CAP_ROUND)
        c=layout.get_pango_context()
        c.set_font_description(self.annotation_font)
        l=pango.Layout(c)

        for b1, b2, r in self.relations_to_draw:
            r1 = b1.get_allocation()
            r2 = b2.get_allocation()
            x_start = r1.x + 3 * r1.width / 4
            y_start  = r1.y + r1.height / 4
            drawable.draw_line(gc, 
                               x_start, y_start,
                               r2.x + r2.width / 4, r2.y + 3 * r2.height / 4)
            # Display the starting mark
            drawable.draw_rectangle(gc,
                                    True,
                                    x_start - 2, y_start - 2,
                                    4, 4)
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
                l.set_text(t)
                # We draw the relation type on a white background by default,
                # but this should depend on the active gtk theme
                color=self.get_element_color(r) or self.colors['white']
                drawable.draw_layout(gc,
                                     (r1.x + r2.x ) / 2,
                                     (r1.y + r2.y ) / 2,
                                     l,
                                     background=color
                                     )
        return False

    def draw_relation_lines_cairo(self, layout, event):
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
                                  (y_start + y_end ) / 2 - ext[3] - 4,
                                  ext[2] + 2, 
                                  ext[3] + 2)
                context.fill()
                
                context.set_source_rgb(0, 0, 0)
                context.move_to((x_start + x_end ) / 2,
                                (y_start + y_end ) / 2)
                context.show_text(t)
            context.stroke()

        return False

    if AnnotationWidget is not None:
        draw_relation_lines=draw_relation_lines_cairo
    else:
        draw_relation_lines=draw_relation_lines_old

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
                self.ratio_adjustment.set_value(36000)
                self.update_layout()

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
        self.beginrule=controller.event_handler.internal_rule (event="AnnotationBegin",
                                                method=self.activate_annotation_handler)
        self.endrule=controller.event_handler.internal_rule (event="AnnotationEnd",
                                                method=self.desactivate_annotation_handler)
        self.tagrule=controller.event_handler.internal_rule (event="TagUpdate",
                                                             method=self.tag_update)

    def tag_update(self, context, parameters):
        tag=context.evaluateValue('tag')
        bs = [ b
               for b in self.layout.get_children()
               if hasattr (b, 'annotation') and tag in b.annotation.tags ]
        for b in bs:
            self.update_button(b)
        return True

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.beginrule, type_="internal")
        controller.event_handler.remove_rule(self.endrule, type_="internal")
        controller.event_handler.remove_rule(self.tagrule, type_="internal")

    def set_widget_background_color(self, widget, color=None):
        if isinstance(widget, AnnotationWidget):
            widget.update_widget()
            return True
        if color is None:
            try:
                color=widget._default_color
            except:
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
            b.set_color(color)
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
            b.set_color(None)
        return True

    def toggle_annotation (self, annotation):
        button = self.get_widget_for_annotation (annotation)
        if button:
            if button.active:
                self.desactivate_annotation (annotation, buttons=button)
            else:
                self.activate_annotation (annotation, buttons=button)

    def unit2pixel (self, v):
        return (long(v / self.ratio_adjustment.value)) or 1

    def pixel2unit (self, v):
        return v * self.ratio_adjustment.value

    def get_element_color(self, element):
        """Return the gtk color for the given element.
        Return None if no color is defined.
        """
        color=self.controller.get_element_color(element)
        return advene.gui.util.name2color(color)

    def update_button (self, b):
        """Update the representation for button b.
        """
        b.update_widget()
        a=b.annotation
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
            self.layout.show_all()
            return True

        b = self.get_widget_for_annotation (annotation)
        if event == 'AnnotationEditEnd':
            self.update_button (b)
        elif event == 'AnnotationDelete':
            b.destroy()
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
            pos = self.unit2pixel (ann.fragment.begin)
            self.adjustment.set_value(pos)
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

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        if widget.drag_sent(widget, context, selection, targetType, eventTime):
            return True
        if targetType == config.data.target_type['annotation-resize']:
            selection.set(selection.target, 8,
                          cgi.urllib.urlencode( {
                        'uri': widget.annotation.uri,
                        'fraction': widget._drag_fraction,
                        } ))
            return True
        else:
            print "Unknown target type for drag: %d" % targetType
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

            relationtypes=helper.matching_relationtypes(self.controller.package,
                                                        source,
                                                        dest)
            if relationtypes:
                item=gtk.MenuItem(_("Create a relation"))
                # build a submenu
                sm=gtk.Menu()
                for rt in relationtypes:
                    sitem=gtk.MenuItem(self.controller.get_title(rt))
                    sitem.connect('activate', create_relation, source, dest, rt)
                    sm.append(sitem)
                menu.append(item)
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

    def annotation_type_drag_received_cb(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
            dest=widget.annotationtype

            def move_annotation(*p):
                if source.relations:
                    advene.gui.util.message_dialog(_("Cannot delete the annotation : it has relations."),
                                                   icon=gtk.MESSAGE_WARNING)
                    return True

                self.controller.transmute_annotation(source,
                                                     dest,
                                                     delete=True)
                return True

            # Popup a menu to propose the drop options
            menu=gtk.Menu()
            for (title, action) in ( 
                (_("Copy annotation"), 
                 lambda i: self.controller.transmute_annotation(source,
                                                                dest,
                                                                delete=False)),
                (_("Move annotation"), move_annotation)
                 ):
                item=gtk.MenuItem(title)
                item.connect('activate', action)
                menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())

        elif targetType == config.data.target_type['annotation-type']:
            source_uri=selection.data
            source=self.controller.package.annotationTypes.get(source_uri)
            dest=widget.annotationtype
            if source in self.annotationtypes:
                self.annotationtypes.remove(source)

                j=self.annotationtypes.index(dest)
                l= self.annotationtypes[:j+1]
                l.append(source)
                l.extend(self.annotationtypes[j+1:])
                self.annotationtypes = l
                self.update_model(partial_update=True)
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

            # FIXME: Duplicated code from previous method. Should factorize.a
            def move_annotation(*p):
                if source.relations:
                    advene.gui.util.message_dialog(_("Cannot delete the annotation : it has relations."),
                                                   icon=gtk.MESSAGE_WARNING)
                    return True

                self.controller.transmute_annotation(source,
                                                     dest,
                                                     delete=True)
                return True

            # Popup a menu to propose the drop options
            menu=gtk.Menu()
            for (title, action) in ( 
                (_("Copy annotation"), 
                 lambda i: self.controller.transmute_annotation(source,
                                                                dest,
                                                                delete=False)),
                (_("Move annotation"), move_annotation)
                 ):
                item=gtk.MenuItem(title)
                item.connect('activate', action)
                menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def layout_drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop from an annotation to the layout.
        """
        if targetType == config.data.target_type['annotation-resize']:
            q=dict(cgi.parse_qsl(selection.data))
            source=self.controller.package.annotations.get(q['uri'])
            try:
                fr = float(q['fraction'])
            except:
                fr = 0.0
            pos=long(self.pixel2unit(self.adjustment.value + x))

            def move_or_resize(*p):
                #print "Resizing ", source.id, self.pixel2unit(x), fr
                # Note: x is here relative to the visible portion of the window. Thus we must
                # add self.adjustment.value
                f=source.fragment
                if fr < 0.25:
                    # Modify begin
                    f.begin=pos
                elif fr > 0.75:
                    # Modify end
                    f.end = pos
                else:
                    d=f.duration
                    # Move annotation
                    f.begin = long(pos - fr * d)
                    f.end = f.begin + d
                if f.begin > f.end:
                    f.begin, f.end = f.end, f.begin
                self.controller.notify('AnnotationEditEnd', annotation=source)
                return True
                
            if fr < 0.25:
                message=_("Set begin time to %s" % helper.format_time(pos))
            elif fr > 0.75:
                message=_("Set end time to %s" % helper.format_time(pos))
            else:
                message=_("Move annotation to %s" % helper.format_time(long(pos - fr * source.fragment.duration)))

            menu=gtk.Menu()
            item=gtk.MenuItem(message)
            item.connect('activate', move_or_resize)
            menu.append(item)
            item=gtk.MenuItem(_("Cancel"))
            menu.append(item)
            
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

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
        return False

    def quick_edit(self, annotation, button=None, callback=None):
        """Quickly edit a textual annotation
        """
        if button is None:
            button=self.get_widget_for_annotation(annotation)
        if button is None:
            return False
        e=gtk.Entry()
        # get_title will either return the content data, or the computed representation
        e.set_text(self.controller.get_title(annotation))
        e.set_activates_default(True)
        def key_handler(widget, event):
            if event.keyval == gtk.keysyms.Return:
                # Validate the entry
                repr=annotation.type.getMetaData(config.data.namespace, "representation")
                if repr is None or repr == '' or sre.match('^\s+', repr):
                    r=e.get_text()
                else:
                    m=parsed_representation.match(repr)
                    if m:
                        # We have a simple representation (here/content/parsed/name)
                        # so we can update the name field.
                        name=m.group(1)
                        reg = sre.compile('^' + name + '=(.+?)$', sre.MULTILINE)
                        if reg.match(annotation.content.data):
                            r = reg.sub(name + '=' + e.get_text().replace('\n', '\\n'), annotation.content.data)
                        else:
                            # The key is not present, add it
                            if annotation.content.data:
                                r = annotation.content.data + "\n%s=%s" % (name,
                                                                           e.get_text().replace('\n', '\\n'))
                            else:
                                r = "%s=%s" % (name,
                                               e.get_text().replace('\n', '\\n'))
                    else:
                        self.log("Cannot update the annotation, its representation is too complex")
                        r=annotation.content.data
                annotation.content.data = r
                if callback:
                    callback(annotation)
                self.controller.notify('AnnotationEditEnd', annotation=annotation)
                e.destroy()
                button.grab_focus()
                return True
            elif event.keyval == gtk.keysyms.Escape:
                # Abort and close the entry
                e.destroy()
                button.grab_focus()
                return True
            return False
        e.connect("key_press_event", key_handler)

        # Put the entry on the layout
        al=button.get_allocation()
        button.parent.put(e, al.x, al.y)
        e.show()
        e.grab_focus()

        return

    def annotation_key_press_cb(self, widget, event, annotation):
        """Handle key presses on annotation widgets.
        """
        if widget.keypress(widget, event, annotation):
            return True

        if event.keyval == gtk.keysyms.p:
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

    def rel_activate(self, button, event):
        self.statusbar.set_annotation(button.annotation)
        button.grab_focus()
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
        return True

    def rel_deactivate(self, button, event):
        self.statusbar.set_annotation(None)
        if self.options['display-relations']:
            self.relations_to_draw = []
            self.update_relation_lines()
        return True

    def deactivate_all(self):
        """Deactivate all annotations.
        """
        def desactivate(widget):
            try:
                if widget.active:
                    widget.active = False
                    widget.update_widget()
            except AttributeError:
                pass
            return True
        self.layout.foreach(desactivate)
        return True

    def create_annotation_widget(self, annotation):
        try:
            pos = self.layer_position[annotation.type]
        except KeyError:
            # The annotation is not displayed
            return None

        u2p = self.unit2pixel
        b = AnnotationWidget(annotation=annotation, container=self)
        b.active = False
        # Put at a default position.
        self.layout.put(b, 0, 0)
        b.show()
        self.update_button(b)

        b.connect("key_press_event", self.annotation_key_press_cb, annotation)
        b.connect("enter_notify_event", self.rel_activate)
        b.connect("leave_notify_event", self.rel_deactivate)

        def focus_in(b, event):
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
                self.scroll_to_annotation(b.annotation)
            return False

        b.connect("focus_in_event", focus_in)
        # The button can generate drags
        b.connect("drag_data_get", self.drag_sent)
        b.connect("drag_begin", self.drag_begin)

        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['annotation']
                          + config.data.drag_type['annotation-resize']
                          + config.data.drag_type['uri-list']
                          + config.data.drag_type['text-plain']
                          + config.data.drag_type['TEXT']
                          + config.data.drag_type['STRING']
                          + config.data.drag_type['timestamp']
                          + config.data.drag_type['tag']
                          ,
                          gtk.gdk.ACTION_LINK)
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
            # Update the tooltip
            self.statusbar.set_annotation(button.annotation)
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

        return True

    def draw_marks (self):
        """Draw marks for stream positioning"""
        u2p = self.unit2pixel
        # We want marks every 200 pixels
        step = self.pixel2unit (200)
        t = self.minimum
        while t <= self.maximum:
            a = gtk.Arrow (gtk.ARROW_DOWN, gtk.SHADOW_NONE)
            a.mark = t
            a.pos = 1
            a.show()
            self.layout.put (a, u2p(t), a.pos)
            l = gtk.Label (helper.format_time (t))
            l.mark = t
            l.pos = 10
            e=gtk.EventBox()
            e.connect("button_press_event", self.mark_press_cb, t)
            e.add(l)
            e.show_all()

            self.layout.put (e, u2p(t), l.pos)
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

        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                win.emit('destroy')
                return True
            else:
                return False
        if event.keyval >= 49 and event.keyval <= 57:
            pos=self.get_middle_position()
            self.fraction_adj.value=1.0/pow(2, event.keyval-49)
            self.set_middle_position(pos)
            return True
        elif event.keyval == gtk.keysyms.e:
            if self.statusbar.annotation is not None:
                self.controller.gui.edit_element(self.statusbar.annotation)
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
        return False

    def layout_button_press_cb(self, widget=None, event=None):
        """Handle right-mouse click in timeline window.
        """
        retval = False
        if event.button == 3:
            self.context_cb (timel=self, position=self.pixel2unit(event.x), height=event.y)
            retval = True
        return retval

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

    def ratio_event (self, widget=None, data=None):
        self.update_adjustment ()
        self.update_layout ()
        self.redraw_event ()
        return True

    def layout_resize_event(self, widget=None, *p):
        """Recompute elements when the layout size changes
        """
        parent = self.layout.window

        if not parent:
            return False
        (w, h) = parent.get_size ()
        if (w, h) != self.layout_size:
            # Widget size changed.
            self.fraction_event(None)
            self.layout_size = (w, h)
        return False

    def fraction_event (self, widget=None, *p):
        """Set the zoom factor to display the given fraction of the movie.

        fraction is > 0 and <= 1.
        """
        parent = self.layout.window
        if not parent:
            return True
        (w, h) = parent.get_size ()

        fraction=self.fraction_adj.value
        #print "fraction event", fraction
        self.zoom_combobox.child.set_text('%d%%' % long(100 * fraction))
        v = (self.maximum - self.minimum) / float(w) * fraction
        self.ratio_adjustment.set_value(v)
        return True

    def layout_scroll_cb(self, widget=None, event=None):
        """Handle mouse scrollwheel events.
        """
        if event.state & gtk.gdk.CONTROL_MASK:
            a = self.fraction_adj
            incr = a.step_increment
        else:
            a = self.adjustment
            incr = a.step_incr

        if event.direction == gtk.gdk.SCROLL_DOWN:
            val = a.value + incr
            if val > a.upper - a.page_size:
                val = a.upper - a.page_size
            if val != a.value:
                a.value = val
                a.changed()
                #a.value_changed ()
            return True
        elif event.direction == gtk.gdk.SCROLL_UP:
            val = a.value - incr
            if val < a.lower:
                val = a.lower
            if val != a.value:
                a.value = val
                a.changed()
                #a.value_changed ()
            return True

        return False

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
        if self.old_ratio_value != self.ratio_adjustment.value:
            self.ratio = self.ratio_adjustment.value
            self.old_ratio_value = self.ratio
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

    def update_legend_widget(self, layout):
        """Update the legend widget.

        Its content may have changed.
        """
        width=0
        height=0

        def set_end_time(an):
            an.fragment.end=self.controller.player.current_position_value 
            return True
    
        def keypress_handler(widget, event, at):
            if widget.keypress(widget, event, at):
                return True
            elif event.keyval == gtk.keysyms.Return:
                if (self.controller.player.status != self.controller.player.PlayingStatus
                    and self.controller.player.status != self.controller.player.PauseStatus):
                    return True
                # Create a new annotation
                id_=self.controller.package._idgenerator.get_id(Annotation)

                duration=0
                el=self.controller.package.createAnnotation(
                    ident=id_,
                    type=at,
                    author=config.data.userid,
                    date=self.controller.get_timestamp(),
                    fragment=MillisecondFragment(begin=long(self.controller.player.current_position_value),
                                                 duration=duration))
                self.controller.package.annotations.append(el)
                self.controller.notify('AnnotationCreate', annotation=el)
                b=self.create_annotation_widget(el)
                b.show()
                self.quick_edit(el, button=widget, callback=set_end_time)
            return False

        for t in self.annotationtypes:
            b=AnnotationTypeWidget(t, self)
            self.tooltips.set_tip(b, _("From schema %s") % self.controller.get_title(t.schema))
            layout.put (b, 0, self.layer_position[t])
            b.update_widget()
            b.show()
            b.connect("key_press_event", keypress_handler, t)
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
                              config.data.drag_type['annotation-type'], gtk.gdk.ACTION_MOVE)

            # Does not work for the first time, since the layout itself is not realized,
            # thus its children cannot know their allocation.
            width=max(width, b.width)
            height=max (height, self.layer_position[t] + 3 * self.button_height)

        def resize(b, w):
            b.width=w
            b.update_widget()
            return True

        # Resize all buttons to fit the largest
        if width > 20:
            layout.foreach(resize, width)

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
        
        layout.set_size (width, height)
        return

    def build_legend_widget (self):
        """Return a Layout containing the legend widget."""
        legend = gtk.Layout ()
        self.update_legend_widget(legend)
        return legend

    def get_full_widget(self):
        """Return the layout with its controllers.
        """
        vbox = gtk.VBox()
        vbox.connect ("key_press_event", self.layout_key_press_cb)

        hb=gtk.HBox()
        toolbar = self.get_toolbar()
        hb.add(toolbar)

        self.statusbar=QuickviewBar(self.controller)
        ti=gtk.ToolItem()
        ti.add(self.statusbar)
        toolbar.insert(ti, -1)

        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(self.player_toolbar)

        vbox.pack_start(hb, expand=False)

        vbox.add (self.get_packed_widget())

        # Make sure that the timeline display is in sync with the
        # fraction widget value
        self.fraction_event (vbox)

        return vbox

    def get_packed_widget (self):
        """Return the widget packed into a scrolledwindow."""
        vbox = gtk.VBox ()

        hpaned = gtk.HPaned ()

        self.legend = self.build_legend_widget ()

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

        return vbox

    def get_toolbar(self):
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

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

        def handle_toggle(b, option):
            self.options[option]=b.get_active()
            return True

        self.display_relations_toggle=gtk.ToggleToolButton(stock_id=gtk.STOCK_REDO)
        self.display_relations_toggle.set_tooltip(self.tooltips, _("Display relations"))
        self.display_relations_toggle.set_active(self.options['display-relations'])
        self.display_relations_toggle.connect('toggled', handle_toggle, 'display-relations')
        tb.insert(self.display_relations_toggle, -1)

        tb.insert(gtk.SeparatorToolItem(), -1)

        def zoom_entry(entry):
            f=entry.get_text()

            i=sre.findall(r'\d+', f)
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
        tb.insert(i, -1)
        
        i=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_IN)
        i.connect('clicked', zoom, .7)
        tb.insert(i, -1)

        self.zoom_combobox=advene.gui.util.list_selector_widget(members=[
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

        tb.insert(gtk.SeparatorToolItem(), -1)

        i=gtk.ToolItem()
        i.add(self.autoscroll_choice)
        tb.insert(i, -1)

        def center_on_current_position(*p):
            if (self.controller.player.status == self.controller.player.PlayingStatus
                or self.controller.player.status == self.controller.player.PauseStatus):
                self.center_on_position(self.current_position)
            return True

        b=gtk.ToolButton(stock_id=gtk.STOCK_JUSTIFY_CENTER)
        b.set_tooltip(self.tooltips, _("Center on current player position."))
        b.connect("clicked", center_on_current_position)
        tb.insert(b, -1)

        for text, tooltip, icon, callback in ( 
            (_("Preferences"), _("Preferences"), 
             gtk.STOCK_PREFERENCES, self.edit_preferences), ):
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
        selected_store, it = advene.gui.util.generate_list_model(
            [ (at, self.controller.get_title(at)) for at in l ])
        notselected_store, it = advene.gui.util.generate_list_model(
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

        d.connect("key_press_event", advene.gui.util.dialog_keypressed_cb)

        d.show()
        advene.gui.util.center_on_mouse(d)
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
        res=ew.popup()
        if res:
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
        a=self.adjustment
        a.value = max(0, self.unit2pixel(pos) - a.page_size / 2)

class OldAnnotationWidget(gtk.Button):
    """Old method to render annotation widgets (in order to be usable on
       fink with gtk == 2.6 and no cairo is available)
    """
    def __init__(self, annotation=None, container=None):
        gtk.Button.__init__(self)
        self.annotation=annotation
        # container is the Advene view instance that manages this instance
        self.container=container
        if container:
            self.controller=container.controller
        else:
            self.controller=None

        self.local_color=None
        self.label=gtk.Label()
        self.label.modify_font(self.container.annotation_font)

        self.add(self.label)
        w=self.container.unit2pixel(self.annotation.fragment.duration)
        self.set_size_request(w, self.container.button_height)

    def set_color(self, color=None):
        self.local_color=color
        self.update_widget()

    def update_widget(self):
        if not self.window:
            return False

        # First check width
        w=self.container.unit2pixel(self.annotation.fragment.duration)
        if w != self.window.get_size()[0]:
            self.set_size_request(w, self.container.button_height)

        if self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotation)
        if color:
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                self.modify_bg (style, color)

        # Draw the text
        title=self.controller.get_title(self.annotation)
        if self.annotation.relations:
            self.label.set_markup('<u>%s</u>' % title)
        else:
            self.label.set_text(title)
        return True

class OldAnnotationTypeWidget(gtk.Button):
    """Old method to render annotation type widgets (in order to be usable on
       fink with gtk == 2.6 and no cairo is available)
    """
    def __init__(self, annotationtype=None, container=None):
        gtk.Button.__init__(self)
        self.annotationtype=annotationtype
        # container is the Advene view instance that manages this instance
        self.container=container
        if container:
            self.controller=container.controller
        else:
            self.controller=None

        self.local_color=None
        self.label=gtk.Label()
        self.label.modify_font(self.container.annotation_type_font)
        self.add(self.label)
        self.set_size_request(-1, self.container.button_height)
        self.width=None

        self.connect("key_press_event", self.keypress, self.annotationtype)
        self.connect("button_press_event", self.buttonpress)
        self.connect("enter_notify_event", lambda b, e: b.grab_focus() and True)

    def keypress(self, widget, event, annotationtype):
        if event.keyval == gtk.keysyms.e:
            self.controller.gui.edit_element(annotationtype)
            return True
        return False

    def buttonpress(self, widget, event):
        """Display the popup menu when right-clicking on annotation type.
        """
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            menu=advene.gui.popup.Menu(widget.annotationtype,
                                       controller=self.controller)
            menu.popup()
            return True
        return False

    def set_color(self, color=None):
        self.local_color=color
        self.update_widget()

    def update_widget(self):
        if not self.window:
            return False

        if self.width is not None:
            self.set_size_request(self.width, -1)
        if self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotationtype)
        if color:
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                self.modify_bg (style, color)

        # Draw the text
        title=self.controller.get_title(self.annotationtype)
        self.label.set_text(title)
        return True

if AnnotationWidget is None:
    AnnotationWidget=OldAnnotationWidget
    AnnotationTypeWidget=OldAnnotationTypeWidget

