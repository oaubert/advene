"""Singleton popup.
"""

import sys
import time

import pygtk
pygtk.require ('2.0')
import gtk
import gobject
import pango

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.edit.create
import advene.gui.popup

class SingletonPopup:
    """View displaying a unique popup.
    """
    def __init__ (self, controller=None, autohide=False):
        self.controller=controller
        # Hide the popup if there is no widget
        self.autohide = autohide
        self.widget=None
        # When should the widget be destroyed ?
        self.hidetime=None
        self.window=self.build_widget()

    def display(self, widget=None, timeout=None):
        """Display the given widget.

        timeout is in ms.
        """
        # Another widget is displayed.
        # Destroy it before going on.
        if self.widget is not None:
            ah=self.autohide
            self.autohide=False
            self.undisplay()
            self.autohide=True
        self.widget=widget
        self.vbox.add(widget)
        if timeout is not None and timeout != 0:
            self.hidetime=time.time() + (long(timeout) / 1000.0)
        self.show()
        return True

    def undisplay(self):
        if self.widget is not None:
            self.widget.destroy()
            self.widget=None
        self.hidetime=None
        if self.autohide:
            self.window.hide()
        return True
    
    def hide(self, *p, **kw):
        self.undisplay()
        self.window.hide()
        return True

    def show(self, *p, **kw):
        self.window.show_all()
        return True

    def update_position(self, pos):
        # This method is regularly called. We use it as a side-effect.
        if self.hidetime is not None and time.time() >= self.hidetime:
            self.undisplay()
        return True
    
    def build_widget(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        #if self.controller.gui:
        #    self.controller.gui.init_window_size(window, 'singletonpopup')

        window.set_title (_("Navigation popup"))

        mainbox=gtk.VBox()
        window.add(mainbox)
        
        self.vbox = gtk.VBox()
        mainbox.add(self.vbox)

        self.widget=gtk.Label(_("Navigation popup"))
        self.vbox.add(self.widget)
        
        if self.controller.gui:
            self.controller.gui.register_view (self)
        window.connect ("destroy", lambda w: True)

        hb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect("clicked", self.hide)
        hb.add(b)
        
        mainbox.pack_start(hb, expand=False)
        
        return window

    def get_widget (self):
        """Return the TreeView widget."""
        return self.window

    def popup(self):
        window.show_all()
        return window
