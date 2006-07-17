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

# Advene part
import advene.core.config as config

from advene.model.package import Package
from advene.gui.views import AdhocView
import advene.gui.edit.elements

import advene.util.helper as helper
import advene.gui.util

from gettext import gettext as _

import advene.gui.edit.elements

import gtk
import pango

class TimeLine(AdhocView):
    """
    Representation of a list of annotations placed on a timeline.

    If l is None, then use controller.package.annotations (and handle
    updates accordingly).
    """
    def __init__ (self, l=None,
                  minimum=None,
                  maximum=None,
                  adjustment=None,
                  controller=None,
                  annotationtypes=None):

        self.view_name = _("Timeline")
        self.view_id = 'timeline'
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            )
        self.options = {
            'highlight': True,
	    # Autoscroll: 0: None, 1: continuous, 2: discrete
            'autoscroll': 1,
            'delete_transmuted': False,
            }

        self.list = l
        self.controller=controller
        self.annotationtypes = annotationtypes
        self.tooltips = gtk.Tooltips ()

        # Now that self.list is initialized, we reuse the l variable
        # for various checks.
        if l is None:
            l = controller.package.annotations
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
                    duration = max([a.fragment.end for a in l])
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

        def handle_toggle(b, option):
            self.options[option]=b.get_active()
            return True

        # Highlight activated annotations
        self.highlight_activated_toggle=gtk.CheckButton(_("Active"))
        self.tooltips.set_tip(self.highlight_activated_toggle,
                              _("Highlight active annotations"))
        self.highlight_activated_toggle.set_active (self.options['highlight'])
        self.highlight_activated_toggle.connect('toggled', handle_toggle, 'highlight')

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

        # Maybe we should ask pango the height of 'l' plus margins
        self.button_height = config.data.preferences['timeline']['button-height']

        # Shortcut
        u2p = self.unit2pixel

        # How many units does a pixel represent ?
        # ratio_adjustment.value = unit by pixel
        # Unit = ms
        self.ratio_adjustment = gtk.Adjustment (value=3600,
                                                lower=1,
                                                upper=3600,
                                                step_incr=5,
                                                page_incr=1000)
        self.ratio_adjustment.connect ("changed", self.ratio_event)

        # The same value in relative form
        self.fraction_adj = gtk.Adjustment (value=1.0,
                                            lower=0.01,
                                            upper=1.0,
                                            step_incr=.01,
                                            page_incr=.02)
        self.ratio_adjustment.connect ("changed", self.ratio_event)


        self.layout_size=(None, None)

        self.layout = gtk.Layout ()
        self.layout.connect('scroll_event', self.scroll_event)
        self.layout.connect("key_press_event", self.key_pressed_cb)
        self.layout.connect('button_press_event', self.mouse_pressed_cb)
        self.layout.connect ("size-allocate", self.resize_event)

        self.old_ratio_value = self.ratio_adjustment.value

        self.colors = {
            'active': gtk.gdk.color_parse ('red'),
            'inactive': gtk.Button().get_style().bg[0],
            'incoming': gtk.gdk.color_parse ('green'),
            'outgoing': gtk.gdk.color_parse ('yellow'),
            }
        # Current position in units
        self.current_position = minimum

        # Used for paste operations
        self.selected_position = 0
        self.selection_marker = None

        # Annotation subject to resizing methods
        self.resized_annotation = None

        # Default drag mode : create a relation
        self.drag_mode = "relation"
        # Default mode for over-buttons events (boolean)
        self.over_mode = True

        # Adjustment corresponding to the Virtual display
        # The page_size is the really displayed area
        if adjustment is None:
            adjustment = gtk.Adjustment ()
        self.adjustment = adjustment
        self.update_adjustment ()
        self.adjustment.set_value (u2p(minimum))

        # Dictionary holding the vertical position for each type
        self.layer_position = {}

        self.update_layer_position()

        self.populate ()

        self.draw_marks ()

        self.draw_current_mark()
        self.widget = self.get_full_widget()

    def update_model(self, package=None, partial_update=False):
        """Update the whole model.
	
	@param package: the package
	@type package: Package
	@param update: it is only an update for the existing package, we do not need to rebuild everything
	@param update: boolean
        """
        if package is None:
            package = self.controller.package

	if not partial_update:
	    # It is not just an update, do a full redraw
	    self.minimum = 0
	    oldmax=self.maximum
	    duration = package.getMetaData (config.data.namespace, "duration")
	    if duration is not None:
		self.maximum = long(duration)
	    else:
		b,e=self.bounds()
		self.maximum = e
	    if self.maximum != oldmax:
		self.update_layout()

	    if self.list is None:
		# We display the whole package, so display also
		# empty annotation types
		self.annotationtypes = list(self.controller.package.annotationTypes)
	    else:
		# We specified a list. Display only the annotation
		# types for annotations present in the set
		self.annotationtypes = list(sets.Set([ a.type for a in self.list ]))

	def remove_widget(widget=None, layout=None):
	    layout.remove(widget)
	    return True

	self.layout.foreach(remove_widget, self.layout)
	self.layer_position.clear()
	self.update_layer_position()
	self.populate()
	self.draw_marks()
	self.ratio_event()
	self.legend.foreach(remove_widget, self.legend)
	self.update_legend_widget(self.legend)
	self.legend.show_all()
	return

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
        return True

    def get_widget_for_annotation (self, annotation):
        bs = [ b
               for b in self.layout.get_children()
               if hasattr (b, 'annotation') and b.annotation == annotation ]
        return bs

    def scroll_to_annotation(self, annotation):
        """Scroll the view to put the annotation in the middle.
        """
        (w, h) = self.layout.window.get_size ()
        pos = self.unit2pixel (annotation.fragment.begin) - w/2
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
        elif pos > a.upper:
            pos = a.upper
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

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.beginrule, type_="internal")
        controller.event_handler.remove_rule(self.endrule, type_="internal")

    def activate_annotation (self, annotation, buttons=None, color=None):
        """Activate the representation of the given annotation."""
        if buttons is None:
            buttons = self.get_widget_for_annotation (annotation)
        if color is None:
            color=self.colors['active']
        for b in buttons:
            b.active = True
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                b.modify_bg (style, color)
        return True

    def desactivate_annotation (self, annotation, buttons=None):
        """Desactivate the representation of the given annotation."""
        if buttons is None:
            buttons = self.get_widget_for_annotation (annotation)
        for b in buttons:
            b.active = False
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                b.modify_bg (style, self.colors['inactive'])
        return True

    def toggle_annotation (self, annotation):
        buttons = self.get_widget_for_annotation (annotation)
        if buttons:
            if buttons[0].active:
                self.desactivate_annotation (annotation, buttons=buttons)
            else:
                self.activate_annotation (annotation, buttons=buttons)

    def unit2pixel (self, v):
        return (long(v / self.ratio_adjustment.value)) or 1

    def pixel2unit (self, v):
        return v * self.ratio_adjustment.value

    def update_button (self, b):
        """Update the representation for button b.
        """
        a = b.annotation
        l = b.label
        u2p = self.unit2pixel
        title=helper.get_title(self.controller, a)
        if a.relations:
            l.set_markup('<b>%s</b>' % title)
        else:
            l.set_text(title)
        b.set_size_request(u2p(a.fragment.duration),
                           self.button_height)

        self.layout.move(b, u2p(a.fragment.begin), self.layer_position[a.type])
        tip = _("%s\nBegin: %s\tEnd: %s") % (title,
                                            helper.format_time(a.fragment.begin),
                                            helper.format_time(a.fragment.end))
        self.tooltips.set_tip(b, tip)
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
            b=self.create_annotation_widget(annotation)
            self.layout.show_all()
            return True

        bs = self.get_widget_for_annotation (annotation)
        for b in bs:
            if event == 'AnnotationEditEnd':
                self.update_button (b)
            elif event == 'AnnotationDelete':
                b.destroy()
            else:
                print "Unknown event %s" % event
        return True

    def select_for_resize(self, widget, ann):
        self.resized_annotation=ann
        return True

    def annotation_cb (self, widget, ann):
        """Display the popup menu when clicking on annotation.
        """
        menu=advene.gui.popup.Menu(ann, controller=self.controller)
        menu.add_menuitem(menu.menu, _("Select for resize"), self.select_for_resize, ann)
        menu.menu.show_all()
        menu.popup()
        return True

    def annotation_type_cb (self, widget):
        """Display the popup menu when clicking on annotation type.
        """
        menu=advene.gui.popup.Menu(widget.annotationtype,
                                   controller=self.controller)
        menu.popup()
        return True

    def annotation_type_pressed_cb(self, widget, event):
        """Display the popup menu when right-clicking on annotation type.
        """
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.annotation_type_cb(widget)
            return True
        return False

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

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        #print "drag_sent event from %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            selection.set(selection.target, 8, widget.annotation.uri)
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        #print "drag_received event for %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
            dest=widget.annotation

            if self.drag_mode == 'relation':
                self.create_relation_popup(source, dest)
            elif self.drag_mode in ( 'begin-begin', 'begin-end',
                                     'end-begin', 'end-end', 'align' ):
                self.align_annotations(source, dest, self.drag_mode)
            else:
                print "Unknown drag mode: %s" % self.drag_mode
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

    def type_drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
            dest=widget.annotationtype

            if self.options['delete_transmuted'] and source.relations:
                advene.gui.util.message_dialog(_("Cannot delete the annotation : it has relations."),
                                               icon=gtk.MESSAGE_WARNING)
                return True

            self.controller.transmute_annotation(source,
                                                 dest,
                                                 delete=self.options['delete_transmuted'])
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
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def create_relation_popup(self, source, dest):
        """Display a popup to create a binary relation between source and dest.
        """
        relationtypes=helper.matching_relationtypes(self.controller.package,
                                                    source,
                                                    dest)
        if not relationtypes:
            advene.gui.util.message_dialog(_("No compatible relation types are defined."),
                                           icon=gtk.MESSAGE_WARNING)
            return True

        rt=advene.gui.util.list_selector(title=_("Create a relation"),
                                         text=_("Choose the type of relation\n you want to set between\n%s\nand\n%s") % (
            self.controller.get_title(source),
            self.controller.get_title(dest)),
                                         members=[ (r, self.controller.get_title(r)) for r in relationtypes],
                                         controller=self.controller)
        if rt is not None:
            relation=self.controller.package.createRelation(members=(source, dest),
                                                            type=rt)
            self.controller.package.relations.append(relation)
            self.controller.notify("RelationCreate", relation=relation)
        return True

    def button_press_handler(self, widget, event, annotation):
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.annotation_cb(widget, annotation)
            return True
        return False

    def button_key_handler(self, widget, event, annotation):
        if event.keyval == gtk.keysyms.e:
            try:
                pop = advene.gui.edit.elements.get_edit_popup (annotation, self.controller)
            except TypeError, e:
                self.controller.log(_("Error: unable to find an edit popup for %s:\n%s") % (annotation, unicode(e)))
            else:
                pop.edit ()
            return True
            pass
        return False

    def rel_activate(self, button):
        if self.over_mode:
            a=button.annotation
            for r in button.annotation.relations:
                if r.members[0] != a:
                    self.activate_annotation(r.members[0],
                                             color=self.colors['outgoing'])
                if r.members[1] != a:
                    self.activate_annotation(r.members[1],
                                             color=self.colors['incoming'])
        return True

    def rel_deactivate(self, button):
        if self.over_mode:
            a=button.annotation
            for r in button.annotation.relations:
                if r.members[0] != a:
                    self.desactivate_annotation(r.members[0])
                if r.members[1] != a:
                    self.desactivate_annotation(r.members[1])
        return True

    def deactivate_all(self):
        """Deactivate all annotations.
        """
        def desactivate(widget):
            try:
                if widget.active:
                    widget.active = False
                    for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                                  gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                                  gtk.STATE_PRELIGHT):
                        widget.modify_bg (style, self.colors['inactive'])
            except AttributeError:
                pass
            return True
        self.layout.foreach(desactivate)
        return True

    def create_annotation_widget(self, annotation):
        try:
            pos = self.layer_position[annotation.type]
        except KeyError:
            return None

        u2p = self.unit2pixel
        title=helper.get_title(self.controller, annotation)
        b = gtk.Button()
        l = gtk.Label()
        if annotation.relations:
            l.set_markup('<b>%s</b>' % title)
        else:
            l.set_text(title)
        l.modify_font(self.annotation_font)
        b.label=l
        b.add(l)
        b.annotation = annotation
        b.active = False
        #b.connect("clicked", self.annotation_cb, annotation)
        b.connect("button-press-event", self.button_press_handler, annotation)
        b.connect("key-press-event", self.button_key_handler, annotation)

        b.connect("enter", self.rel_activate)
        b.connect("leave", self.rel_deactivate)

        b.set_size_request(u2p(annotation.fragment.duration),
                           self.button_height)

        self.layout.put(b, u2p(annotation.fragment.begin), pos)
        tip = _("%s\nBegin: %s\tEnd: %s") % (title,
                                             helper.format_time(annotation.fragment.begin),
                                             helper.format_time(annotation.fragment.end))
        self.tooltips.set_tip(b, tip)
        # The button can generate drags
        b.connect("drag_data_get", self.drag_sent)
        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['annotation'], gtk.gdk.ACTION_LINK)
        # The button can receive drops (to create relations)
        b.connect("drag_data_received", self.drag_received)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation'], gtk.gdk.ACTION_LINK)
        b.show()
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
        self.layout.show_all ()

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
        u2p = self.unit2pixel
        if pos is None:
            pos = self.current_position
        else:
            self.current_position = pos
        a = self.current_marker
        a.mark = pos
        self.layout.move (a, u2p(pos), a.pos)

    def update_position (self, pos):
        if pos is None:
            pos = self.current_position
        if self.options['autoscroll'] == 1:
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
        self.fraction_event(widget=None)

        # Center the view around the selected mark
        pos = self.unit2pixel (t) - ( w * rel )
        if pos < a.lower:
            pos = a.lower
        elif pos > a.upper:
            pos = a.upper
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
            self.layout.put (a, u2p(t), a.pos)
            l = gtk.Label (helper.format_time (t))
            l.mark = t
            l.pos = 10
            e=gtk.EventBox()
            e.connect("button-press-event", self.mark_press_cb, t)
            e.add(l)

            self.layout.put (e, u2p(t), l.pos)
            t += step
        self.layout.show_all ()

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

    def key_pressed_cb (self, win, event):
        # Process player shortcuts
        if self.controller.gui and self.controller.gui.process_player_shortcuts(win, event):
            return True

        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                win.emit('destroy')
            return True
        if event.keyval == gtk.keysyms.Escape:
            win.emit('destroy')
            return True
        if event.keyval >= 49 and event.keyval <= 57:
            self.fraction_adj.value=1.0/pow(2, event.keyval-49)
            self.fraction_event (widget=win)
            return True
        if event.keyval == gtk.keysyms.Return:
            self.fraction_adj.value=1.0
            self.fraction_event (widget=win)
            return True
        return False

    def mouse_pressed_cb(self, widget=None, event=None):
        """Handle right-mouse click in timeline window.
        """
        retval = False
        if event.button == 3 or event.button == 1:
            self.context_cb (timel=self, position=self.pixel2unit(event.x))
            retval = True
        return retval

    def context_cb (self, timel=None, position=None):
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

        def copy_value(win, position):
            timel.set_selection(position)
            timel.activate_selection()
            return True

        def set_value(win, position, attr):
            if self.resized_annotation is not None:
                setattr(self.resized_annotation.fragment, attr, long(position))
                self.controller.notify("AnnotationEditEnd", annotation=self.resized_annotation)
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

        if self.resized_annotation is not None:
            item = gtk.MenuItem(_("Set %s.begin") % self.resized_annotation.id)
            item.connect("activate", set_value, position, 'begin')
            menu.append(item)
            item = gtk.MenuItem(_("Set %s.end") % self.resized_annotation.id)
            item.connect("activate", set_value, position, 'end')
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

    def resize_event(self, widget=None, *p):
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
        v = (self.maximum - self.minimum) / float(w) * fraction
        self.ratio_adjustment.set_value(v)
        self.ratio_adjustment.changed ()
        #self.ratio_event (widget)
        return True

    def scroll_event(self, widget=None, event=None):
        """Handle mouse scrollwheel events.
        """
        if event.state & gtk.gdk.CONTROL_MASK:
            a = self.ratio_adjustment
            incr = a.page_size / 2
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
            u2p = self.unit2pixel
            widget.set_size_request(u2p(widget.annotation.fragment.duration),
                                    self.button_height)
            self.layout.move (widget,
                              u2p(widget.annotation.fragment.begin),
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
        for t in self.annotationtypes:
            b=gtk.Button()
            l=gtk.Label(self.controller.get_title(t))
            l.modify_font(self.annotation_font)
            b.add(l)
            b.set_size_request(-1, self.button_height)
            layout.put (b, 0, self.layer_position[t])
            b.annotationtype=t
            b.show()
            b.connect("clicked", self.annotation_type_cb)
            b.connect("button-press-event", self.annotation_type_pressed_cb)
            # The button can receive drops (to transmute annotations)
            b.connect("drag_data_received", self.type_drag_received)
            b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                            gtk.DEST_DEFAULT_HIGHLIGHT |
                            gtk.DEST_DEFAULT_ALL,
                            [ config.data.drag_type['annotation'][0],
                              config.data.drag_type['annotation-type'][0] ],
                            gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE)
            # The button can generate drags (to change annotation type order)
            b.connect("drag_data_get", self.type_drag_sent)
            b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['annotation-type'], gtk.gdk.ACTION_MOVE)

            a=b.get_allocation()
            width=max(width, a.width)
            height=max (height, self.layer_position[t] + 3 * self.button_height)

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
        vbox.connect ("key-press-event", self.key_pressed_cb)

        hb=gtk.HBox()
        toolbar = self.get_toolbar()
        hb.add(toolbar)
        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(self.player_toolbar)

        vbox.pack_start(hb, expand=False)

        vbox.add (self.get_packed_widget())

        hbox = gtk.HButtonBox()
        hbox.set_homogeneous (False)
        vbox.pack_start (hbox, expand=False)


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

        b=gtk.Button(_("Displayed types"))
        self.tooltips.set_tip(b, _("Drag an annotation type here to remove it from display.\nClick to edit all displayed types"))
        b.connect("clicked", self.edit_annotation_types)
        b.connect("drag_data_received", trash_drag_received)
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation-type'],
                        gtk.gdk.ACTION_MOVE)
        hbox.add(b)

        s = gtk.HScale (self.fraction_adj)
        s.set_digits(2)
        s.connect ("value-changed", self.fraction_event)
        hbox.add (s)

        hbox.pack_start (self.highlight_activated_toggle, expand=False)
	hbox.pack_start (self.autoscroll_choice, expand=False)

        vbox.set_homogeneous (False)

        height=max(self.layer_position.values() or (1,)) + 3 * self.button_height

        # Make sure that the timeline display is in sync with the
        # fraction widget value
        self.fraction_event (vbox)

        setattr(vbox, 'buttonbox', hbox)

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

    def set_drag_mode(self, button, mode):
        self.drag_mode = mode
        return True

    def get_toolbar(self):
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)
        radiogroup_ref=None

        tb_list = (
            (_("Relations"), _("Create relations"),
             gtk.STOCK_CONVERT, self.set_drag_mode, "relation"),

            (_("BeginBegin"), _("Set the same begin time as the selected annotation"),
             gtk.STOCK_JUSTIFY_LEFT, self.set_drag_mode, "begin-begin"),

            (_("BeginEnd"), _("Align the begin time to the selected end time"),
             gtk.STOCK_JUSTIFY_CENTER, self.set_drag_mode, "begin-end"),


            (_("EndEnd"), _("Align the end time to the selected end time"),
             gtk.STOCK_JUSTIFY_RIGHT, self.set_drag_mode, "end-end"),

            (_("EndBegin"), _("Align the end time to the selected begin time"),
             gtk.STOCK_JUSTIFY_CENTER, self.set_drag_mode, "end-begin"),

            (_("Align"), _("Align the boundaries"),
             gtk.STOCK_JUSTIFY_FILL, self.set_drag_mode, "align"),

            )

        for text, tooltip, icon, callback, arg in tb_list:
            b=gtk.RadioToolButton(group=radiogroup_ref,
                                  stock_id=icon)
            b.set_tooltip(self.tooltips, tooltip)
            b.connect("clicked", callback, arg)
            tb.insert(b, -1)

            if radiogroup_ref is None:
                radiogroup_ref=b

        def set_over_mode(button, value):
            self.over_mode=value
            return True

        radiogroup_ref=None
        tb_list = (
            (_("Relations"), _("Display relations"),
             gtk.STOCK_REDO, set_over_mode, True),
            (_("No Display"), _("Do not display relations"),
             gtk.STOCK_REMOVE, set_over_mode, False),
            )

        for text, tooltip, icon, callback, arg in tb_list:
            b=gtk.RadioToolButton(group=radiogroup_ref,
                                  stock_id=icon)
            b.set_tooltip(self.tooltips, tooltip)
            b.connect("clicked", callback, arg)
            tb.insert(b, -1)

            if radiogroup_ref is None:
                radiogroup_ref=b

        def handle_toggle(b, option):
            self.options[option]=b.get_active()
            return True

        self.delete_transmuted_toggle=gtk.ToggleToolButton(stock_id=gtk.STOCK_DELETE)
        self.delete_transmuted_toggle.set_tooltip(self.tooltips, _("Delete the original transmuted annotation"))
        self.delete_transmuted_toggle.set_active(self.options['delete_transmuted'])
        self.delete_transmuted_toggle.connect('toggled', handle_toggle, 'delete_transmuted')
        tb.insert(self.delete_transmuted_toggle, -1)
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

        notselectedtree = gtk.TreeView(model=notselected_store)
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Not displayed'), cell, text=0)
        notselectedtree.append_column(column)

        hbox.add(selectedtree)
        actions = gtk.VBox()

        def transfer(b, source, dest):
            path, column = source.get_cursor()
            if path is None:
                return True
            m=source.get_model()
            it=m.get_iter(path)
            # Add el to dest
            dest.get_model().append(m[path])
            m.remove(it)
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
        notselectedtree.connect("row-activated", row_activated, notselectedtree, selectedtree)
        actions.add(b)

        b=gtk.Button(_('< All <'))
        b.connect("clicked", transferall, notselectedtree, selectedtree)
        actions.add(b)

        b=gtk.Button(_('> All >'))
        b.connect("clicked", transferall, selectedtree, notselectedtree)
        actions.add(b)

        b=gtk.Button('>>>')
        b.connect("clicked", transfer, selectedtree, notselectedtree)
        selectedtree.connect("row-activated", row_activated, selectedtree, notselectedtree)
        actions.add(b)

        # FIXME: allow multiple selection?
        hbox.add(actions)

        hbox.add(notselectedtree)

        hbox.show_all()

        # The widget is built. Put it in the dialog.
        d = gtk.Dialog(title=_("Displayed annotation types"),
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
                       buttons=( gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                                 gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

        d.vbox.add(hbox)

        d.connect("key_press_event", advene.gui.util.dialog_keypressed_cb)

        res=d.run()
        if res == gtk.RESPONSE_ACCEPT:
            self.annotationtypes = [ at[1] for at in selected_store ]
            self.update_model(partial_update=True)
        d.destroy()

        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    class DummyController:
        pass

    controller=DummyController()

    controller.package = Package (uri=sys.argv[1])
    controller.gui = None

    timeline = TimeLine (controller.package.annotations,
                         controller=controller)
    timeline.popup()

    gtk.main ()
