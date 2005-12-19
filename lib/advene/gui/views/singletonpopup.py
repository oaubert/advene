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
"""Singleton popup.
"""

import sys
import time

#import pygtk
#pygtk.require ('2.0')
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
    def __init__ (self, controller=None, autohide=False, container=None):
        self.controller=controller
        # Hide the popup if there is no widget
        self.autohide = autohide
        self.widget=None
        self.container=container
        # When should the widget be destroyed ?
        self.hidetime=None
        self.window=self.build_widget()

    def display(self, widget=None, timeout=None, title=None):
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

    def undisplay(self, widget=None):
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
        # This method is regularly called. We use it as a side-effect to
        # remove the widget when the timeout expires.
        if self.hidetime is not None and time.time() >= self.hidetime:
            self.undisplay()
        return True
    
    def build_widget(self):
        if self.container:
            window=self.container
        else:
            window = gtk.Window(gtk.WINDOW_TOPLEVEL)
            window.set_title (_("Navigation popup"))

        mainbox=gtk.VBox()
        window.add(mainbox)
        
        self.vbox = gtk.VBox()
        mainbox.add(self.vbox)

        self.widget=gtk.Label(_("Navigation popup"))
        self.vbox.add(self.widget)

        if self.controller.gui:
            self.controller.gui.register_view (self)

        if self.container is None:
            window.connect ("destroy", lambda w: True)
            
            hb=gtk.HButtonBox()
            
            b=gtk.Button(stock=gtk.STOCK_CLOSE)
            b.connect("clicked", self.hide)
            hb.add(b)
            
            mainbox.pack_start(hb, expand=False)
        
        return window

    def reparent(self, container=None):
        """Set a new container for the singleton popup."""
        self.container=container
        self.widget.destroy()
        self.vbox.destroy()
        self.window.destroy()
        self.window=self.build_widget()
        return self.window
    
    def get_widget (self):
        """Return the TreeView widget."""
        return self.window

    def popup(self):
        window.show_all()
        return window
