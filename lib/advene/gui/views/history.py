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
import advene.util.helper as helper
import advene.gui.util
from advene.gui.views import AdhocView

from gettext import gettext as _

import gtk

class HistoryNavigation(AdhocView):
    def __init__(self, controller=None, history=None, container=None, vertical=True):
        self.view_name = _("Navigation history")
	self.view_id = 'historyview'
	self.close_on_package_load = False
        self.contextual_actions = (
            (_("Clear"), self.clear),
            )

        self.controller=controller
        self.history=history
        self.container=container
        self.scrollwindow=None
        self.snapshot_width=100
        if history is None:
            self.history=[]
        self.vertical=vertical
        self.mainbox=None
        self.widget=self.build_widget()
	self.fill_widget()

    def close(self, *p):
	return False

    def register_callback (self, controller=None):
        self.changerule=controller.event_handler.internal_rule (event="MediaChange",
								method=self.clear)
	return True

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.changerule, type_="internal")
	return True

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
        self.mainbox.foreach(self.remove_widget, self.mainbox)
        return True
        
    def append_repr(self, t):
        vbox=gtk.VBox()
        i=advene.gui.util.image_from_position(self.controller,
                                              t,
                                              width=self.snapshot_width)
        e=gtk.EventBox()
        e.connect("button-release-event", self.activate, t)
        e.add(i)
        vbox.pack_start(e, expand=False)
        l = gtk.Label(helper.format_time(t))
        vbox.pack_start(l, expand=False)
        
        vbox.show_all()
        if self.scrollwindow:
            if self.vertical:
                adj=self.scrollwindow.get_vadjustment()
            else:
                adj=self.scrollwindow.get_hadjustment()
            adj.set_value(adj.upper)
	self.mainbox.add(vbox)

    def fill_widget(self):
        self.mainbox.foreach(self.remove_widget, self.mainbox)
	for t in self.history:
            self.append_repr(t)
        self.mainbox.show_all()
	return True

    def build_widget(self):
	v=gtk.VBox()

        if self.vertical:
            mainbox=gtk.VBox()
        else:
            mainbox=gtk.HBox()
            mainbox.set_size_request(self.snapshot_width, -1)

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        sw.add_with_viewport(mainbox)
        self.scrollwindow=sw
        self.mainbox=mainbox

	v.add(sw)

        return v
