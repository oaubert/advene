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

# FIXME: handle DND from navigation and/or timeline

class HistoryNavigation(AdhocView):
    def __init__(self, controller=None, history=None, vertical=True, ordered=False):
        self.view_name = _("Navigation history")
        self.view_id = 'historyview'
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Clear"), self.clear),
            )

        self.controller=controller
        self.history=history
        self.scrollwindow=None
        self.snapshot_width=100
        if history is None:
            self.history=[]
        self.vertical=vertical
        self.ordered=ordered
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
        if position in self.history:
            return True
        self.history.append(position)
        if self.ordered:
            self.history.sort()
            self.mainbox.foreach(self.remove_widget, self.mainbox)
            for p in self.history:
                self.append_repr(p)
        else:
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

        def drag_sent(widget, context, selection, targetType, eventTime):
            if targetType == config.data.target_type['timestamp']:
                selection.set(selection.target, 8, str(t))
            else:
                print "Unknown target type for drag: %d" % targetType
            return True

        vbox=gtk.VBox()
        i=advene.gui.util.image_from_position(self.controller,
                                              t,
                                              width=self.snapshot_width)
        e=gtk.EventBox()
        e.connect("button-release-event", self.activate, t)
        e.add(i)

        # The button can generate drags
        e.connect("drag_data_get", drag_sent)

        e.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['timestamp'],
                          gtk.gdk.ACTION_LINK)

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

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['timestamp']:
            position=long(selection.data)
            self.append(position)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def build_widget(self):
        v=gtk.VBox()

        if self.vertical:
            mainbox=gtk.VBox()
        else:
            mainbox=gtk.HBox()

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        sw.add_with_viewport(mainbox)
        self.scrollwindow=sw
        self.mainbox=mainbox

        self.mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['timestamp'], gtk.gdk.ACTION_LINK)
        self.mainbox.connect("drag_data_received", self.drag_received)

        v.add(sw)

        return v
