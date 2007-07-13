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
"""Module displaying time bookmarks (for navigation history for instance)."""

# Advene part
import advene.core.config as config
import advene.util.helper as helper
from advene.gui.util import image_from_position, get_small_stock_button
from advene.gui.views import AdhocView

from gettext import gettext as _

import gtk

name="History view plugin"

def register(controller):
    controller.register_viewclass(HistoryNavigation)

class HistoryNavigation(AdhocView):
    view_name = _("Bookmarks")
    view_id = 'history'
    tooltip= _("Bookmark timecodes with their corresponding screenshots")
    def __init__(self, controller=None, parameters=None, 
                 history=None, vertical=True, ordered=False, closable=True):
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Save view"), self.save_view),
            (_("Clear"), self.clear),
            )
        self.options={
            'ordered': ordered,
            'snapshot_width': 100,
            'vertical': vertical,
            }
        self.controller=controller
        self.history=history
        if history is None:
            self.history=[]

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        self.history=[ long(v) for (n, v) in arg if n == 'timestamp' ]
            
        self.closable=closable
        self.mainbox=None
        self.scrollwindow=None
        self.widget=self.build_widget()
        self.refresh()

    def get_save_arguments(self):
        return self.options, [ ('timestamp', t) for t in self.history ]

    def close(self, *p):
        if self.closable:
            AdhocView.close(self)
            return True
        else:
            return False

    def register_callback (self, controller=None):
        self.changerule=controller.event_handler.internal_rule (event="MediaChange",
                                                                method=self.clear)
        return True

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.changerule, type_="internal")
        return True

    def activate(self, widget=None, timestamp=None):
        self.controller.update_status("set", timestamp, notify=False)
        return True

    def append(self, position):
        if position in self.history:
            return True
        self.history.append(position)
        if self.options['ordered']:
            self.history.sort()
            self.refresh()
        else:
            self.append_repr(position)
        return True

    def remove_widget(self, widget=None, container=None):
        container.remove(widget)
        return True

    def refresh(self, *p):
        self.mainbox.foreach(self.remove_widget, self.mainbox)
        for p in self.history:
            self.append_repr(p)
        self.mainbox.show_all()
        return True

    def clear(self, *p):
        del self.history[:]
        self.mainbox.foreach(self.remove_widget, self.mainbox)
        return True

    def append_repr(self, t):

        def drag_sent(widget, context, selection, targetType, eventTime):
            if targetType == config.data.target_type['timestamp']:
                selection.set(selection.target, 8, str(t))
                return True
            else:
                print "Unknown target type for drag: %d" % targetType
            return False

        vbox=gtk.VBox()
        i=image_from_position(self.controller,
                              t,
                              width=self.options['snapshot_width'])
        e=gtk.Button()
        #e.connect("button-release-event", self.activate, t)
        e.connect("clicked", self.activate, t)
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
            if self.options['vertical']:
                adj=self.scrollwindow.get_vadjustment()
            else:
                adj=self.scrollwindow.get_hadjustment()
            adj.set_value(adj.upper)
        self.mainbox.add(vbox)

    def build_widget(self):
        v=gtk.VBox()

        if self.options['vertical']:
            mainbox=gtk.VBox()
        else:
            mainbox=gtk.HBox()

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        sw.add_with_viewport(mainbox)
        self.scrollwindow=sw
        self.mainbox=mainbox

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                position=long(selection.data)
                self.append(position)
                return True
            else:
                print "Unknown target type for drop: %d" % targetType
            return False

        self.mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['timestamp'], gtk.gdk.ACTION_LINK)
        self.mainbox.connect("drag_data_received", mainbox_drag_received)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                position=long(selection.data)
                if position in self.history:
                    self.history.remove(position)
                self.refresh()
                return True
            else:
                print "Unknown target type for drop: %d" % targetType
            return False

        v.add(sw)

        hb=gtk.HBox()
        hb.set_homogeneous(False)

        b=get_small_stock_button(gtk.STOCK_DELETE)
                                                 
        self.controller.gui.tooltips.set_tip(b, _("Drop a position here to remove it from the list"))
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['timestamp'], gtk.gdk.ACTION_LINK)
        b.connect("drag_data_received", remove_drag_received)
        hb.pack_start(b, expand=False)

        def bookmark_current_time(b):
            p=self.controller.player
            if p.status in (p.PlayingStatus, p.PauseStatus):
                v=p.current_position_value
                # Make a snapshot
                self.controller.update_snapshot(v)
                self.append(v)
            return True

        b=gtk.Button()
        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'set-to-now.png') ))
        b.add(i)
        self.controller.gui.tooltips.set_tip(b, _("Insert a bookmark for the current video time"))
        b.connect('clicked', bookmark_current_time)
        hb.pack_start(b, expand=False)

        v.pack_start(hb, expand=False)

        return v
