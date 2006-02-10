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
"""Module displaying navigation history."""

# Advene part
import advene.core.config as config
import advene.util.vlclib as vlclib
import advene.gui.util

from gettext import gettext as _

import gtk

class HistoryNavigation:
    def __init__(self, controller=None, history=None, container=None, vertical=True):
        self.view_name = _("Navigation history")
        self.controller=controller
        self.history=history
        self.container=container
        self.scrollwindow=None
        if history is None:
            self.history=[]
        self.vertical=vertical
        self.widget=self.build_widget()
	self.fill_widget()

    def activate(self, widget=None, data=None, timestamp=None):
        self.controller.update_status("set", timestamp, notify=False)
        return True

    def append(self, position):
        self.history.append(position)
        self.append_repr(position)
        return True
        
    def remove_widget(self, widget=None, container=None):
        container.remove(widget)
        return True
    
    def clear(self, *p):
        del self.history[:]
        self.widget.foreach(self.remove_widget, self.widget)
        return True
        
    def append_repr(self, t):
        vbox=gtk.VBox()
        i=advene.gui.util.image_from_position(self.controller,
                                              t,
                                              width=100)
        e=gtk.EventBox()
        e.connect("button-release-event", self.activate, t)
        e.add(i)
        vbox.pack_start(e, expand=False)
        l = gtk.Label(advene.util.vlclib.format_time(t))
        vbox.pack_start(l, expand=False)
        
        vbox.show_all()
        if self.scrollwindow:
            if self.vertical:
                adj=self.scrollwindow.get_vadjustment()
            else:
                adj=self.scrollwindow.get_hadjustment()
            adj.set_value(adj.upper)
	self.widget.add(vbox)

    def fill_widget(self):
        self.widget.foreach(self.remove_widget, self.widget)
	for t in self.history:
            self.append_repr(t)
        self.widget.show_all()
	return True

    def build_widget(self):
        if self.vertical:
            mainbox=gtk.VBox()
        else:
            mainbox=gtk.HBox()

        return mainbox

    def popup(self):
        if self.container:
            w=gtk.Frame()
            w.set_label(_("Navigation history"))
            vb=gtk.VBox()
            vb.add(w)
            self.container.add(vb)
        else:
            w = gtk.Window (gtk.WINDOW_TOPLEVEL)
            w.set_title (_("Navigation history"))
            vb=gtk.VBox()
            vb.add(w)

	    vb=None

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        w.add(sw)
        
        sw.add_with_viewport(self.widget)
        self.scrollwindow=sw

	if vb:
	    b=gtk.Button(stock=gtk.STOCK_CLEAR)
	    b.connect("clicked", self.clear)
	    vb.pack_start(b, expand=False)

	w.show_all()
        return w
