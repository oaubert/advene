#! /usr/bin/env python

"""Annotation editing widget.

This module defines a popup aimed at editing annotation (metadata and
contents).
"""

import sys
import time

import pygtk
pygtk.require ('2.0')
import gtk
import gobject

# Advene part
import advene.core.config as config

from advene.model.schema import Schema, AnnotationType
from advene.gui.edit.timeadjustment import TimeAdjustment

from gettext import gettext as _

import advene.gui.edit.elements

class AnnotationEdit:
    def __init__(self, annotation, controller):
        self.annotation=annotation
        self.controller=controller
        self.widget=self.make_widget(annotation)

    def get_widget(self):
        return self.widget

    def get_plugin_for_annotation(self, annotation):
        """Determines the best widget to use to edit the annotation content."""
        # FIXME: Implement this
#        plugins={'text/*': EditTextPlugin,
#                 'text/plain': EditTextPlugin,
#                 'text/string': EditStringPlugin }
        plugins={}
        
        if plugins.has_key(annotation.content.mimetype):
            return plugins[annotation.content.mimetype](annotation)
        else:
            raise "Plugin not available for content-type %s" % annotation.content.mimetype

    def make_widget(self, annotation):
        vbox=gtk.VBox()
        hbox=gtk.HBox()

        self.begin=TimeAdjustment(value=self.annotation.fragment.begin,
                                  controller=self.controller)
        f=gtk.Frame()
        f.set_label(_("Begin"))
        f.add(self.begin.get_widget())
        hbox.add(f)
        
        self.end=TimeAdjustment(value=self.annotation.fragment.end, controller=self.controller)
        f=gtk.Frame()
        f.set_label(_("End"))
        f.add(self.end.get_widget())
        hbox.add(f)

        vbox.pack_start (hbox, expand=gtk.FALSE)

        # Now we can show the annotation contents (i.e. invoke the plugin manager)
        #self.plugin=self.get_plugin_for_annotation(annotation)
        #vbox.pack_start (plugin.get_widget(), expand=gtk.FALSE)

        # FIXME: for the moment, fragment information is displayed in
        # 2 places (timeadjustments and EditAnnotationPopup. This is
        # source of a synchronisation problem        
        self.plugin=advene.gui.edit.elements.EditAnnotationPopup(annotation,
                                                                 controller=self.controller)
        vbox.pack_start(self.plugin.make_widget(editable=True), expand=gtk.FALSE)
        
        # Button bar
        hbox = gtk.HButtonBox()

        b = gtk.Button (stock=gtk.STOCK_OK)
        b.connect ("clicked", self.validate_cb)
        hbox.add (b)

        b = gtk.Button (stock=gtk.STOCK_CANCEL)
        b.connect ("clicked", lambda w: self.window.destroy ())
        hbox.add (b)

        vbox.pack_start (hbox, expand=gtk.FALSE)

        vbox.show_all()

        return vbox

    def popup (self):
        self.window = gtk.Window (gtk.WINDOW_TOPLEVEL)
        self.window.set_title (self.plugin.get_title())
        self.window.add(self.get_widget())
        self.window.show_all()
        return gtk.TRUE

    def validate_cb(self, widget):
        """Update the values of the annotation attributes.
        
        according to the form data (esp. times) """
        
        if self.begin.value >= self.end.value:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_WARNING, gtk.BUTTONS_CLOSE,
                _("Begin time is greater than end time"))
            dialog.connect("response", lambda w, e: dialog.destroy())
            dialog.show()
            return False

        val=self.plugin.validate_cb(widget)
        
        self.annotation.fragment.begin=self.begin.value
        self.annotation.fragment.end=self.end.value
        
        self.controller.notify("AnnotationEditEnd", annotation=self.annotation)
        
        self.window.destroy()
        return val
        
if __name__ == "__main__":
    import sys
    import advene.core.imagecache
    
    if len(sys.argv) < 2:
        print "No name provided."
        sys.exit(1)
    else:
        filename=sys.argv[1]

    class Controller:
        """Dummy controller."""
        def __init__(self):
            self.annotation=None
            self.package=None
            self.active_annotations=[]
            self.player=None
            self.imagecache=advene.core.imagecache.ImageCache()

    controller=Controller()
    
    p = advene.model.package.Package(uri=filename)

    # Last annotation
    a = p.annotations[-1]
    
    w=gtk.Window(gtk.WINDOW_TOPLEVEL)
    w.set_title("Annotation %s" % a.id)
    w.connect ("destroy", lambda e: gtk.main_quit())

    vbox=gtk.VBox()
    vbox.set_homogeneous (gtk.FALSE)    
    w.add(vbox)

    edit=AnnotationEdit(a, controller)
    edit.get_widget().show()
    vbox.add(edit.get_widget())

    hb=gtk.HButtonBox()
    
#    b=gtk.Button(stock=gtk.STOCK_ADD)
#    b.connect("clicked", edit.add_rule)
#    hb.pack_start(b, expand=gtk.FALSE)
#
#    b=gtk.Button(stock=gtk.STOCK_REMOVE)
#    b.connect("clicked", edit.remove_rule)
#    hb.pack_start(b, expand=gtk.FALSE)

    def save_package(button):
        edit.update_value()
        fname='test.xml'
        print "Saving package as %s" % fname
        p.save(as=fname)
        dialog = gtk.MessageDialog(
            None, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
            "The package has been saved into %s." % fname)
        dialog.run()
        dialog.destroy()
        return True
    
    b=gtk.Button(stock=gtk.STOCK_SAVE)
    b.connect("clicked", save_package)
    hb.pack_start(b, expand=gtk.FALSE)

    b=gtk.Button(stock=gtk.STOCK_QUIT)
    b.connect("clicked", lambda e: gtk.main_quit())
    hb.pack_end(b, expand=gtk.FALSE)

    hb.show_all()

    vbox.pack_start(hb, expand=gtk.FALSE)
    vbox.show()
    
    w.show()
    
    gtk.mainloop()
