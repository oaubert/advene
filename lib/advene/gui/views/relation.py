#! /usr/bin/env python

import sys

# Advene part
import advene.core.config
from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

from gettext import gettext as _

import advene.gui.popup

import pygtk
pygtk.require ('2.0')
import gtk
import gobject

class RelationView:
    """Controller for the MVC representing a relation."""
    def popup(self, button):
        menu = advene.gui.popup.Menu(self, controller=self.controller)
        menu.popup()
        return True

    def __init__(self, relation=None, controller=None):
        self.relation=relation
        self.controller=controller
        self.widget=self.build_widget()
        self.widget.connect("clicked", self.activate)        

    def activate(self, button):
        print "Relation %s activated" % self.relation.id
        if self.controller:
            self.controller.notify("RelationActivation", relation=self.relation)
        return True
    
    def build_widget(self):
        l=gtk.Label()
        l.set_markup("<b>%s</b> relation between\nann. <i>%s</i>\nand\nann. <i>%s</i>" %
                     (self.relation.type.title,
                      self.relation.members[0].id,
                      self.relation.members[1].id))
        b=gtk.Button()
        b.add(l)
        b.connect("clicked", self.popup)
        
        return b

    def get_widget(self):
        return self.widget
        
class RelationsBox:
    """
    Representation of a list of relations
    """
    def __init__ (self, package=None, controller=None):
        self.package=package
        self.controller=controller
        self.relationviews=[]
        self.active_color = gtk.gdk.color_parse ('red')
        self.inactive_color = gtk.Button().get_style().bg[0]
        self.widget = self.build_widget()

    def build_widget(self):
        vbox=gtk.VBox()
        for r in self.package.relations:
            v=RelationView(relation=r, controller=self.controller)
            self.relationviews.append(v)
            vbox.pack_start(v.get_widget(), expand=False)
        vbox.show_all()
        return vbox
    
    def debug_cb (self, widget, data=None):
        print "Debug event."
        if data is not None:
            print "Data: %s" % data
        return True
    
    def get_widget_for_relation (self, relation):
        bs = [ b
               for b in self.widget.get_children()
               if hasattr (b, 'relation') and b.relation == relation ]
        return bs

    def activate_relation_handler (self, context, parameters):
        relation=context.evaluateValue('relation')
        if relation is not None:
            self.activate_relation(relation)
        return True
            
    def desactivate_relation_handler (self, context, parameters):
        relation=context.evaluateValue('relation')
        if relation is not None:
            self.desactivate_relation(relation)
        return True
            
    def register_callback (self, controller=None):
        """Add the activate handler for annotations."""
        pass
        #self.beginrule=controller.event_handler.internal_rule (event="AnnotationBegin",
        #                                        method=self.activate_annotation_handler)
        #self.endrule=controller.event_handler.internal_rule (event="AnnotationEnd",
        #                                        method=self.desactivate_annotation_handler)
        
    def unregister_callback (self, controller=None):
        pass
        #controller.event_handler.remove_rule(self.beginrule)
        #controller.event_handler.remove_rule(self.endrule)
    
    def activate_relation (self, relation):
        """Activate the representation of the given relation."""
        bs = self.get_widget_for_relation (relation)
        for b in bs:
            b.active = True
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                b.modify_bg (style, self.active_color)
        return True

    def desactivate_relation (self, relation):
        """Desactivate the representation of the given relation."""
        bs = self.get_widget_for_relation (relation)
        for b in bs:
            b.active = True
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                b.modify_bg (style, self.inactive_color)
        return True
    
    def get_widget (self):
        """Return the display widget."""
        return self.widget

    def update_relation (self, element=None, event=None):
        """Update a relation's representation."""
        if event == 'RelationCreate':
            # If it does not exist yet, we should create it if it is now in self.list
            if element in self.list:
                v=RelationView(relation=element, controller=self.controller)
                self.relationviews.append(v)
                self.widget.pack_start(v.get_widget(), expand=False)
            return True

        bs = self.get_widget_for_relation (element)
        for b in bs:
            if event == 'RelationEditEnd':
                self.update_button (b)
            elif event == 'RelationDelete':
                b.destroy()
            else:
                print "Unknown event %s" % event
        return True

    def update_relation (self, element=None):
        """Update a relation's representation."""
        bs = self.get_widget_for_relation (element)
        for b in bs:
            self.update_button (b)
        
    def drag_sent(self, widget, context, selection, targetType, eventTime):
        #print "drag_sent event from %s" % widget.annotation.content.data
        if targetType == config.data.TARGET_TYPE_ANNOTATION:
            selection.set(selection.target, 8, widget.annotation.uri)
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        #print "drag_received event for %s" % widget.annotation.content.data
        if targetType == config.data.TARGET_TYPE_ANNOTATION:
            source_uri=selection.data
            print "Creating new relation (%s, %s)" % (source_uri, widget.annotation.uri)
            source=self.package.annotations.get(source_uri)
            dest=widget.annotation
            self.create_relation_popup(source, dest)
            # FIXME: TODO
            # Find matching relation (we need to know the package...)
            # source=self.package.annotations.get(source_id)
            # dest=self.package.annotations.get(widget.annotation.id)
            # relation_list=self.package.findMatchingRelation(source, dest)
            # if len(relation_list) == 0:
            #     raise Exception ('')
            # elif len(relation_list) == 1:
            #     # Only one relation matches: create it
            #     rel=self.package.createRelation(relation_list[0], members=(source, dest))
            #     # FIXME: append ?
            # else:
            #     # Many possible relations. Ask the user.
            #     # FIXME...
            #     rel=self.package.createRelation(chosen_relation, members=(source, dest))
        else:
            print "Unknown target type for drop: %d" % targetType
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    package = Package (uri=sys.argv[1])
    
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_size_request (320, 200)

    def key_pressed_cb (win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True
        return False
            

    def validate_cb (win, package):
        filename="/tmp/package.xml"
        package.save (as=filename)
        print "Package saved as %s" % filename
        gtk.main_quit ()
        
    window.connect ("key-press-event", key_pressed_cb)
    window.connect ("destroy", lambda e: gtk.main_quit())
    window.set_title (package.title or "None")
    vbox = gtk.VBox()
    
    window.add (vbox)

    relbox=RelationsBox(package=package, controller=None)
    vbox.add (relbox.get_widget())

    hbox = gtk.HButtonBox()
    vbox.pack_start (hbox, expand=False)

    b = gtk.Button (stock=gtk.STOCK_QUIT)
    b.connect ("clicked", lambda w: window.destroy ())
    hbox.add (b)

    vbox.set_homogeneous (False)

    window.show_all()
    gtk.main ()
