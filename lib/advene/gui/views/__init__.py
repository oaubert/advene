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
import gtk

class AdhocView:
    def __init__(self, controller=None):
	self.view_name = "Generic adhoc view"
	self.view_id = 'generic'
	self.controller = controller
	self.widget=self.build_widget()

    def close(self):
        if self.controller and self.controller.gui:
            self.controller.gui.unregister_view (self)
	self.widget.destroy()
	return True

    def get_widget (self):
        """Return the widget."""
        return self.widget

    def build_widget(self):
	return gtk.Label(self.view_name)

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title (self.view_name)

        vbox = gtk.VBox()
        window.add (vbox)


	vbox.add (self.get_widget())

        if self.controller and self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb, window, self)
            self.controller.gui.init_window_size(window, self.view_id)

        window.buttonbox = gtk.HButtonBox()

        b = gtk.Button(stock=gtk.STOCK_CLOSE)

        if self.controller and self.controller.gui:
            b.connect ("clicked", self.controller.gui.close_view_cb, window, self)
        else:
            b.connect ("clicked", lambda w: window.destroy())
        window.buttonbox.add (b)

        vbox.pack_start(window.buttonbox, expand=False)
        
        window.show_all()
        
        return window
