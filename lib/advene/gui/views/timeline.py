import sys
import time

# Advene part
import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation
from advene.model.schema import Schema, AnnotationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

import advene.util.vlclib as vlclib

from gettext import gettext as _

import advene.gui.edit.elements

import pygtk
#pygtk.require ('2.0')
import gtk
import gobject

class TimeLine:
    """
    Representation of a list of annotations placed on a timeline.    
    """
    def __init__ (self, l,
                  minimum=None,
                  maximum=None,
                  adjustment=None,
                  controller=None):
        
        self.list = l
        self.controller=controller
        
        if minimum is None or maximum is None:
            b, e = self.bounds ()
            if minimum is None:
                minimum = b
            if maximum is None:
                maximum = e
        self.minimum = minimum
        self.maximum = maximum

        # Highlight activated annotations 
        self.highlight_activated_toggle=gtk.CheckButton(_("Highlight active annotations"))
        self.highlight_activated_toggle.set_active (True)
        
        # Scroll the window to display the activated annotations 
        self.scroll_to_activated_toggle=gtk.CheckButton(_("Scroll to active annotation"))
        self.scroll_to_activated_toggle.set_active (True)
                    
        # FIXME: Hardcoded values are bad...
        # Maybe we should ask pango the height of 'l' plus margins
        self.button_height = 30
        
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
        
        self.widget = gtk.Layout ()

        self.widget.connect('scroll_event', self.scroll_event)
        self.widget.connect("key_press_event", self.key_pressed_cb)
        self.widget.connect('button_press_event', self.mouse_pressed_cb)
        
        self.tooltips = gtk.Tooltips ()
        self.rapport = 1
        self.old_ratio_value = self.ratio_adjustment.value

        self.active_color = gtk.gdk.color_parse ('red')
        self.inactive_color = gtk.Button().get_style().bg[0]
        
        # Current position in units
        self.current_position = minimum

        # Used for paste operations
        self.selected_position = 0
        self.selection_marker = None

        # Dictionary holding the vertical position for each type
        self.layer_position = {}
        
        # Adjustment corresponding to the Virtual display
        # The page_size is the really displayed area
        if adjustment is None:
            self.adjustment = gtk.Adjustment ()
        else:
            self.adjustment = adjustment
        self.update_adjustment ()
        self.adjustment.set_value (u2p(minimum))

        self.populate ()
        self.draw_marks ()

        self.draw_current_mark()

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
        self.widget.selection_add_target("CLIPBOARD", "STRING", 1)
        self.widget.selection_add_target("CLIPBOARD", "COMPOUND_TEXT", 1)
        # Define the selection handler
        self.widget.connect("selection_get", self.selection_handle)
        # Claim selection ownership
        self.widget.selection_owner_set("CLIPBOARD")
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
               for b in self.widget.get_children()
               if hasattr (b, 'annotation') and b.annotation == annotation ]
        return bs

    def scroll_to_annotation(self, annotation):
        pos = self.unit2pixel (annotation.fragment.begin)
        a = self.adjustment
        if pos < a.value or pos > (a.value + a.page_size):
            a.set_value (pos)
        self.update_position (None)
        return True
    
    def activate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None:
            if self.scroll_to_activated_toggle.get_active():
                self.scroll_to_annotation(annotation)
            if self.highlight_activated_toggle.get_active():
                self.activate_annotation (annotation)
            self.update_position (None)                
        return True
            
    def desactivate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None:
            if self.highlight_activated_toggle.get_active():
                self.desactivate_annotation (annotation)
        return True
            
    def register_callback (self, controller=None):
        """Add the activate handler for annotations."""
        self.beginrule=controller.event_handler.internal_rule (event="AnnotationBegin",
                                                method=self.activate_annotation_handler)
        self.endrule=controller.event_handler.internal_rule (event="AnnotationEnd",
                                                method=self.desactivate_annotation_handler)
        
    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.beginrule, type_="internal")
        controller.event_handler.remove_rule(self.endrule, type_="internal")
    
    def activate_annotation (self, annotation, buttons=None):
        """Activate the representation of the given annotation."""
        if buttons is None:
            buttons = self.get_widget_for_annotation (annotation)
        for b in buttons:
            b.active = True
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                b.modify_bg (style, self.active_color)
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
                b.modify_bg (style, self.inactive_color)
        return True
    
    def toggle_annotation (self, annotation):
        buttons = self.get_widget_for_annotation (annotation)
        if buttons:
            if buttons[0].active:
                self.desactivate_annotation (annotation, buttons=buttons)
            else:
                self.activate_annotation (annotation, buttons=buttons)
        
    def update (self, widget=None, data=None):
        print "Update"
        
    def unit2pixel (self, v):
        return (long(v / self.ratio_adjustment.value)) or 1

    def pixel2unit (self, v):
        return v * self.ratio_adjustment.value
    
    def get_widget (self):
        """Return the display widget."""
        return self.widget

    def update_button (self, b):
        a = b.annotation
        l = b.label
        u2p = self.unit2pixel
        title=vlclib.get_title(self.controller, a)
        if a.relations:
            l.set_markup('<b>%s</b>' % title)
        else:
            l.set_text(title)
        b.set_size_request(u2p(a.fragment.duration),
                           self.button_height)
        
        self.widget.move(b, u2p(a.fragment.begin), self.layer_position[a.type])
        tip = _("%s\nBegin: %s\tEnd: %s") % (title,
                                            vlclib.format_time(a.fragment.begin),
                                            vlclib.format_time(a.fragment.end))
        self.tooltips.set_tip(b, tip)
        return True

    def update_model(self, package):
        self.list=package.annotations
        self.layer_position.clear()
        self.minimum = 0
        duration = package.getMetaData (config.data.namespace, "duration")
        if duration is not None:
            self.maximum = long(duration)
        else:
            b,e=self.bounds()
            self.maximum = e
        self.widget.foreach(self.remove_widget, self.widget)
        self.populate()
        self.ratio_event()
        self.legend.foreach(self.remove_widget, self.legend)
        self.update_legend_widget(self.legend)
        self.legend.show_all()
        return
    
    def update_annotation (self, annotation=None, event=None):
        """Update an annotation's representation."""
        if event == 'AnnotationActivate':
            self.activate_annotation(annotation)
            if self.scroll_to_activated_toggle.get_active():
                self.scroll_to_annotation(annotation)
            return True
        if event == 'AnnotationDeactivate':
            self.desactivate_annotation(annotation)
            return True
        if event == 'AnnotationCreate':
            # If it does not exist yet, we should create it if it is now in self.list
            if annotation in self.list:
                self.create_annotation_widget(annotation)
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
        
    def annotation_cb (self, widget, ann):
        menu=advene.gui.popup.Menu(ann, controller=self.controller)
        menu.popup()
        return True

    def dump_adjustment (self):
        a = self.adjustment
        print ("Lower: %.1f\tUpper: %.1f\tValue: %.1f\tPage size: %.1f"
               % (a.lower, a.upper, a.value, a.page_size))
        print "Ratio: %.3f" % self.rapport

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
            print "Creating new relation (%s, %s)" % (source_uri, widget.annotation.uri)
            source=self.controller.package.annotations.get(source_uri)
            dest=widget.annotation
            self.create_relation_popup(source, dest)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def create_relation_popup(self, source, dest):
        """Display a popup to create a binary relation between source and dest.
        """
        relationtypes=vlclib.matching_relationtypes(self.controller.package,
                                                    source,
                                                    dest)
        if not relationtypes:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
                _("No compatible relation types are defined."))
            dialog.set_position(gtk.WIN_POS_MOUSE)
            dialog.run()
            dialog.destroy()
            return True
        
        w=gtk.Window(gtk.WINDOW_POPUP)
        w.set_title(_("Create a relation"))
        w.set_position(gtk.WIN_POS_MOUSE)

        f=gtk.Frame(_("Create a relation"))
        w.add(f)
        
        vbox=gtk.VBox()
        f.add(vbox)

        l=gtk.Label()
        l.set_markup(_("Choose the type of relation\n you want to set between\n%s\nand\n%s")
                     % (source.id, dest.id))
        vbox.add(l)

        optionmenu = gtk.OptionMenu()

        menu=gtk.Menu()
        for r in relationtypes:
            item = gtk.MenuItem(r.title)
            item.show()
            menu.append(item)
        optionmenu.set_menu(menu)

        optionmenu.show()
        vbox.add(optionmenu)
        
        hbox=gtk.HButtonBox()
        vbox.add(hbox)
        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect("clicked", lambda e: w.destroy())
        hbox.pack_start(b, expand=False)

        def on_create_relation(widget, window):
            self.create_relation_option(source, dest, optionmenu, relationtypes)
            window.destroy()
            return True
        
        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect("clicked", on_create_relation, w) 
        hbox.pack_start(b, expand=False)

        w.show_all()
        return True

    def create_relation_option(self, source, dest, optionmenu, relationtypes):
        """Create a relation between source and dest whose type is in optionmenu."""
        rtype=relationtypes[optionmenu.get_history()]
        relation=self.controller.package.createRelation(members=(source, dest), type=rtype)
        self.controller.package.relations.append(relation)
        print "Relation %s created." % relation

    def button_press_handler(self, widget, event, annotation):
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            self.annotation_cb(widget, annotation)
            return True
        return False
    
    def create_annotation_widget(self, annotation):
        u2p = self.unit2pixel
        title=vlclib.get_title(self.controller, annotation)
        b = gtk.Button()
        l = gtk.Label()
        if annotation.relations:
            l.set_markup('<b>%s</b>' % title)
        else:
            l.set_text(title)
        b.label=l
        b.add(l)
        b.annotation = annotation
        b.active = False
        b.connect("clicked", self.annotation_cb, annotation)
        b.connect("button-press-event", self.button_press_handler, annotation)
        b.set_size_request(u2p(annotation.fragment.duration),
                           self.button_height)
        # Get the default height for the annotation type. If not defined,
        # set it to the following value.
        pos = self.layer_position.setdefault (annotation.type,
                                              max(self.layer_position.values() or (1,)) + self.button_height + 10)

        self.widget.put(b, u2p(annotation.fragment.begin), pos)
        tip = _("%s\nBegin: %s\tEnd: %s") % (title,
                                             vlclib.format_time(annotation.fragment.begin),
                                             vlclib.format_time(annotation.fragment.end))
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
        for annotation in self.list:
            self.create_annotation_widget(annotation)

        self.widget.set_size (u2p (self.maximum - self.minimum),
                              max(self.layer_position.values() or (0,))
                              + self.button_height + 10)
        self.widget.show_all ()

    def remove_marks(self, widget=None, data=None):
        if hasattr(widget, 'mark'):
            self.widget.remove(widget)

    def draw_current_mark (self):
        u2p = self.unit2pixel
        a = gtk.VSeparator()
        a.set_size_request (2, max(self.layer_position.values() or (0,))
                            + self.button_height)
        self.current_marker = a
        a.mark = self.current_position
        a.pos = 5        
        self.widget.put (a, u2p(a.mark), a.pos)
        a.show ()

    def update_current_mark (self, pos=None):
        u2p = self.unit2pixel
        if pos is None:
            pos = self.current_position
        else:
            self.current_position = pos
        a = self.current_marker
        a.mark = pos
        self.widget.move (a, u2p(pos), a.pos)

    def update_position (self, pos):
        self.update_current_mark (pos)
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
            self.widget.put (a, u2p(t), a.pos)
            l = gtk.Label (vlclib.format_time (t))
            l.mark = t
            l.pos = 10
            self.widget.put (l, u2p(t), l.pos)
            t += step
        self.widget.show_all ()
        
    def bounds (self):
        """Bounds of the list.
        
        Return a tuple corresponding to the min and max values of the
        list, in list units.        
        """
        minimum=sys.maxint
        maximum=0
        for a in self.list:
            if a.fragment.begin < minimum:
                minimum = a.fragment.begin
            if a.fragment.end > maximum:
                maximum = a.fragment.end
        return minimum, maximum

    def key_pressed_cb (self, win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                win.emit('destroy')
            return True
        if event.keyval == gtk.keysyms.Escape:
            win.emit('destroy')
            return True        
        if event.keyval >= 49 and event.keyval <= 57:
            self.display_fraction_event (widget=win, fraction=1.0/pow(2, event.keyval-49))
            return True
        if event.keyval == gtk.keysyms.Return:
            self.display_fraction_event (widget=win, fraction=1.0)
            return True
        return False

    def context_cb (self, timel=None, position=None):
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

        item = gtk.MenuItem(_("Position %s") % vlclib.format_time(position))
        menu.append(item)

        item = gtk.SeparatorMenuItem()
        menu.append(item)

        item = gtk.MenuItem(_("Go to..."))
        item.connect("activate", popup_goto, position)
        menu.append(item)

        item = gtk.MenuItem(_("Copy value into clipboard"))
        item.connect("activate", copy_value, position)
        menu.append(item)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True
            
    def set_selection_marker (self, position):
        x=self.unit2pixel(position)
        if self.selection_marker is None:
            # Draw a marker
            a = gtk.VSeparator()
            a.set_size_request (2, max(self.layer_position.values() or (0,))
                                + self.button_height)
            self.selection_marker = a
            a.modify_bg(gtk.STATE_NORMAL, self.active_color)
        else:
            a = self.selection_marker
        a.mark = position
        a.pos = 5
        self.widget.put (a, x, a.pos)
        a.show ()
        return True

    def remove_selection_marker (self):
        try:
            self.widget.remove(self.selection_marker)
        except AttributeError:
            pass
        return True
    
    def mouse_pressed_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = event.x
        y = event.y
        if button == 3:
            self.context_cb (timel=self, position=self.pixel2unit(x))
            retval = True
        return retval

    def remove_widget(self, widget=None, layout=None):
        layout.remove(widget)
        return True

    def update_layout (self):
        (w, h) = self.widget.get_size ()
        self.widget.set_size (self.unit2pixel(self.maximum - self.minimum), h)
        
    def update_adjustment (self):
        """Update the adjustment values depending on the current aspect ratio."""
        u2p = self.unit2pixel
        a = self.adjustment
        width = self.maximum - self.minimum
        
        #a.value=u2p(minimum)
        a.lower=float(u2p(self.minimum))
        a.upper=float(u2p(self.maximum))
        a.step_incr=float(u2p(width / 100))
        a.page_incr=float(u2p(width / 10))
        a.page_size=float(self.widget.get_size()[0])
        #print "Update: from %.2f to %.2f" % (a.lower, a.upper)
        a.changed ()

    def display_fraction_event (self, widget=None, fraction=1.0):
        """Set the zoom factor to display the given fraction of the movie.

        fraction is > 0 and <= 1.
        """
        parent = self.widget.window
        (w, h) = parent.get_size ()
        v = (self.maximum - self.minimum) / float(w) * fraction
        self.ratio_adjustment.set_value(v)
        self.ratio_adjustment.changed ()
        self.ratio_event (widget)
        return True

    def scroll_event(self, widget=None, event=None):
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
                a.value_changed ()
            return True
        elif event.direction == gtk.gdk.SCROLL_UP:
            val = a.value - incr
            if val < a.lower:
                val = a.lower
            if val != a.value:
                a.value = val
                a.value_changed ()
            return True
        
        return False

    def ratio_event (self, widget=None, data=None):
        self.update_adjustment ()
        self.update_layout ()
        self.redraw_event ()
        return True

    def move_widget (self, widget=None):
        """Update the annotation widget position"""
        if hasattr (widget, 'annotation'):
            u2p = self.unit2pixel
            widget.set_size_request(u2p(widget.annotation.fragment.duration),
                                    self.button_height)
            self.widget.move (widget,
                              u2p(widget.annotation.fragment.begin),
                              self.layer_position[widget.annotation.type])
        return True

    
    def redraw_event(self, widget=None, data=None):
        if self.old_ratio_value != self.ratio_adjustment.value:
            self.ratio = self.ratio_adjustment.value
            self.old_ratio_value = self.ratio
            # Remove old marks
            self.widget.foreach(self.remove_marks)
            # Reposition all buttons
            self.widget.foreach(self.move_widget)
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
        for t in self.layer_position.keys():
            l = gtk.Label (t.title)
            (w, h) = l.get_layout().get_pixel_size()
            width = max (width, w)
            height = max (height, self.layer_position[t] + h)
            layout.put (l, 0, self.layer_position[t])
        layout.set_size (width, height)
        return
    
    def build_legend_widget (self):
        """Return a Layout containing the legend widget."""
        legend = gtk.Layout ()
        self.update_legend_widget(legend)
        return legend
        
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
        sw.add (self.get_widget())
        hpaned.add2 (sw)

        (w, h) = self.legend.get_size ()
        hpaned.set_position (w)
        vbox.add (hpaned)
        
        #hgrade = stripchart.HGradeZoom()
        #hgrade.adjustment = self.adjustment
        #hgrade.set_size_request(400, 30)
        #vbox.pack_start (hgrade.widget, expand=False)

        return vbox

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        window.connect ("key-press-event", self.key_pressed_cb)

        window.set_title (self.controller.package.title or "???")

        vbox = gtk.VBox()

        window.add (vbox)

        vbox.add (self.get_packed_widget())

        hbox = gtk.HButtonBox()
        vbox.pack_start (hbox, expand=False)

        fraction_adj = gtk.Adjustment (value=0.1,
                                       lower=0.01,
                                       upper=1.0,
                                       step_incr=.01,
                                       page_incr=.02)

        def zoom_event (win=None, timel=None, adj=None):
            timel.display_fraction_event (widget=win, fraction=adj.value)
            return True

        s = gtk.HScale (fraction_adj)
        s.set_digits(2)
        s.connect ("value-changed", zoom_event, self, fraction_adj)
        hbox.add (s)

        hbox.add (self.highlight_activated_toggle)
        hbox.add (self.scroll_to_activated_toggle)

        b = gtk.Button (stock=gtk.STOCK_OK)
        if self.controller.gui:
            b.connect ("clicked", self.controller.gui.close_view_cb, window, self)
        else:
            b.connect ("clicked", lambda w: window.destroy())
        hbox.add (b)

        vbox.set_homogeneous (False)

        if self.controller.gui:
            window.connect ("destroy", self.controller.gui.close_view_cb, window, self)

        self.controller.gui.register_view (self)

        height=max(self.layer_position.values() or (1,)) + 3 * self.button_height

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'timelineview')
        window.show_all()

        # Make sure that the timeline display is in sync with the
        # fraction widget value
        self.display_fraction_event (window,
                                  fraction=fraction_adj.value)

        return window
    
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
