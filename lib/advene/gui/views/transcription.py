#! /usr/bin/env python

"""Transcription view.
"""

import sys

import pygtk
pygtk.require ('2.0')
import gtk
import gobject
import pango

# Advene part
import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

import advene.util.vlclib as vlclib

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.edit.create
import advene.gui.popup

class TranscriptionView:
    def __init__ (self, controller=None, annotationtype=None, separator=" "):
        self.controller=controller
        self.package=controller.package
        self.model = annotationtype
        self.separator = separator
        self.widget=self.build_widget()

    def build_widget(self):
        vbox = gtk.VBox()
        self.textview = gtk.TextView()
        # We could make it editable and modify the annotation 
        self.textview.set_editable(False)
        self.textview.set_wrap_mode (gtk.WRAP_CHAR)

        b=self.textview.get_buffer()
        for a in self.model.annotations:
            mark = b.create_mark("b_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            b.insert_at_cursor(a.content.data)
            mark = b.create_mark("e_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            #print "inserted from %d to %d" % (b_a, e_a)
            b.insert_at_cursor(self.separator)

        activated_tag = b.create_tag("activated")
        activated_tag.set_property("background", "red")
        activated_tag.set_property("weight", pango.WEIGHT_BOLD)
        
        vbox.add(self.textview)
        vbox.show_all()
        return vbox

    def update_annotation (self, annotation=None, event=None):
        """Update an annotation's representation."""
        if event == 'AnnotationActivate':
            self.activate_annotation(annotation)
            return True
        if event == 'AnnotationDeactivate':
            self.desactivate_annotation(annotation)
            return True
        if event == 'AnnotationCreate':
            # If it does not exist yet, we should create it if it is now in self.list
            if annotation in self.model.annotationTypes:
                # FIXME
                print "Not implemented yet."
                pass
            return True

        if event == 'AnnotationEditEnd':
            # FIXME
            print "Update representation"
        elif event == 'AnnotationDelete':
            # FIXME
            print "Remove representation"
        else:
            print "Unknown event %s" % event
        return True

    def activate_annotation(self, a):
        b=self.textview.get_buffer()
        beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % a.id))
        enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % a.id))
        b.apply_tag_by_name("activated", beginiter, enditer)
        return True
    
    def desactivate_annotation(self, a):
        b=self.textview.get_buffer()
        beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % a.id))
        enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % a.id))
        b.remove_tag_by_name("activated", beginiter, enditer)
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

    def activate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None and annotation.type == self.model:
            self.activate_annotation (annotation)
        return True
            
    def desactivate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None and annotation.type == self.model:
            self.desactivate_annotation (annotation)
        return True
    
    def get_widget (self):
        """Return the TreeView widget."""
        return self.widget


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)
    
    class DummyController:
        def notify(self, *p, **kw):
            print "Notify %s %s" % (p, kw)

    controller=DummyController()
    
    controller.package = Package (uri=sys.argv[1])

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_size_request (640, 480)

    window.set_border_width(10)
    window.set_title (controller.package.title)
    vbox = gtk.VBox()
    
    window.add (vbox)
    
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    vbox.add (sw)

    transcription = TranscriptionView(controller=controller,
                                      annotationtype=controller.package.annotationTypes[0])
    
    sw.add_with_viewport (transcription.get_widget())

    hbox = gtk.HButtonBox()
    vbox.pack_start (hbox, expand=False)

    def validate_cb (win, package):
        filename="/tmp/package.xml"
        package.save (as=filename)
        print "Package saved as %s" % filename
        gtk.main_quit ()
        

    b = gtk.Button (stock=gtk.STOCK_SAVE)
    b.connect ("clicked", validate_cb, controller.package)
    hbox.add (b)

    b = gtk.Button (stock=gtk.STOCK_QUIT)
    b.connect ("clicked", lambda w: window.destroy ())
    hbox.add (b)

    vbox.set_homogeneous (False)

    i = 0
    def key_pressed_cb (win, event):
        global i
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True
            elif event.keyval == gtk.keysyms.space:
                if i > 0:
                    b = controller.package.annotationTypes[0].annotations[i-1]
                    transcription.desactivate_annotation(b)
                a = controller.package.annotationTypes[0].annotations[i]
                print "Activating %s" % a.content.data
                transcription.activate_annotation(a)
                i += 1
        return False            

    window.connect ("key-press-event", key_pressed_cb)
    window.connect ("destroy", lambda e: gtk.main_quit())

    window.show_all()
    gtk.main ()

