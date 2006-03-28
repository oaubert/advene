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
    """Implementation of the generic parts of AdhocViews.

    For details about the API of adhoc views, see gui.views.viewplugin.
    """
    def __init__(self, controller=None):
	self.view_name = "Generic adhoc view"
	self.view_id = 'generic'
        # List of couples (label, action) that are use to
        # generate contextual actions
        self.contextual_actions = ()

	# If True, the view should be closed when loading a new package.
	# Else, it can respond to a package load and update
	# itself accordingly (through the update_model method).
	self.close_on_package_load = True

	self.controller = controller
	# If self.buttonbox exists, then the widget has already
	# defined its own buttonbox, and the generic popup method
	# can but the "Close" button in it:
	# self.buttonbox = gtk.HButtonBox()
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

	w=self.get_widget()

	def close_popup(*p):
	    window.destroy()
	    return True

	# Close the popup window when the widget is destroyed
	w.connect("destroy", close_popup)

	# If the widget defines a buttonbox, we can use it and do not
	# have to define a enclosing VBox (which also solves a problem
	# with the timeline view not being embedable inside a VBox()
	if hasattr(w, 'buttonbox') and w.buttonbox is not None:
	    window.add(w)
	    window.buttonbox = w.buttonbox
	else:
	    vbox = gtk.VBox()
	    window.add (vbox)
	    vbox.add (w)
	    window.buttonbox = gtk.HButtonBox()
	    vbox.pack_start(window.buttonbox, expand=False)

        if self.controller and self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb, window, self)
            self.controller.gui.init_window_size(window, self.view_id)

        # Insert contextual_actions in buttonbox
        try:
            for label, action in self.contextual_actions:
                b=gtk.Button(label)
                b.connect("clicked", action)
                window.buttonbox.add(b)
        except AttributeError:
            pass

        b = gtk.Button(stock=gtk.STOCK_CLOSE)

        if self.controller and self.controller.gui:
            b.connect ("clicked", self.controller.gui.close_view_cb, window, self)
        else:
            b.connect ("clicked", lambda w: window.destroy())
        window.buttonbox.add (b)
        
        window.show_all()
        
        return window
