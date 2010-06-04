
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Frame selector widget.

It depends on a Controller instance to be able to interact with the video player.
"""

import gtk
from advene.gui.widget import TimestampRepresentation
from advene.gui.util import dialog
from gettext import gettext as _

class FrameSelector(object):
    """Frame selector interface.
    
    Given a timestamp, it displays a series of snapshots around
    the timestamp and allows to select the most appropriate
    one.
    """
    def __init__(self, controller, timestamp=0, callback=None):
        self.controller = controller
        self.timestamp = timestamp
        self.selected_value = timestamp
        self.callback = callback
        # Number of displayed timestamps
        self.count = 8
        self.frame_length = 1000 / 25
        # Reference to the HBox holding TimestampRepresentation widgets.
        # It is initialized in build_widget()
        self.container = None
        self.widget = self.build_widget()
        
    def set_timestamp(self, timestamp):
        """Set the reference timestamp.

        It is the timestamp displayed in the label, and corresponds
        most of the time to the original timestamp (before adjustment).
        """
        self.timestamp = timestamp
        self.selected_value = timestamp
        self.update_timestamp(timestamp)
        
    def update_timestamp(self, timestamp, focus_index=None):
        """Set the center timestamp.
        
        If focus_index is not specified, the center timestamp will get
        the focus.

        @param timestamp: the center timestamp
        @type timestamp: long
        @param focus_index: the index of the child widget which should get the focus
        @type focus_index: int
        """
        t = timestamp - self.count / 2 * self.frame_length
        if t < 0:
            # Display from 0. But we have to take this into account
            # when handling focus_index
            index_offset = t / self.frame_length
            t = 0
        else:
            index_offset = 0
        
        for c in self.container.get_children():
            c.value = t
            if t < self.timestamp:
                c.bgcolor = '#666666'
            else:
                c.bgcolor = 'black'
            t += self.frame_length

        # Handle focus
        if focus_index is None:
            focus_index = self.count / 2

        self.container.get_children()[focus_index + index_offset].grab_focus()
        return True

    def update_offset(self, offset, focus_index=None):
        """Update the timestamps to go forward/backward.
        """
        if offset < 0:
            ref=self.container.get_children()[0]
            start = max(ref.value + offset * self.frame_length, 0)
        else:
            ref=self.container.get_children()[offset]
            start = ref.value
        self.update_timestamp(start + self.count / 2 * self.frame_length, focus_index)
        return True

    def refresh_snapshots(self):
        """Update non-initialized snapshots.
        """
        ic=self.controller.package.imagecache
        for c in self.container.get_children():
            if not ic.is_initialized(c.value):
                self.controller.update_snapshot(c.value)
        return True

    def handle_scroll_event(self, widget, event):
        if event.direction == gtk.gdk.SCROLL_UP or event.direction == gtk.gdk.SCROLL_LEFT:
            offset=-1
        elif event.direction == gtk.gdk.SCROLL_DOWN or event.direction == gtk.gdk.SCROLL_RIGHT:
            offset=+1
        self.update_offset(offset)
        return True

    def focus_index(self):
        """Return the index of the TimestampRepresentation which has the focus.
        """
        return self.container.get_children().index(self.container.get_focus_child())

    def handle_key_press(self, widget, event):
        if event.keyval == gtk.keysyms.Left:
            i = self.focus_index()
            if i == 0:
                self.update_offset(-1, focus_index = 0)
            else:
                self.container.get_children()[i - 1].grab_focus()
            return True
        elif event.keyval == gtk.keysyms.Right:
            i = self.focus_index()
            if i == len(self.container.get_children()) -1:
                self.update_offset(+1, focus_index = -1)
            else:
                self.container.get_children()[i + 1].grab_focus()
            return True
        return False

    def get_value(self, title=None):
        if title is None:
            title = _("Select the appropriate snapshot")
        d = gtk.Dialog(title=title,
                       parent=None,
                       flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 ))

        def callback(v):
            d.response(gtk.RESPONSE_OK)
            return True
        self.callback = callback

        d.vbox.add(self.widget)
        d.show_all()
        dialog.center_on_mouse(d)

        res = d.run()
        timestamp = self.timestamp
        if res == gtk.RESPONSE_OK:
            timestamp = self.selected_value
        d.destroy()
        return timestamp
    
    def select_time(self, button=None):
        """General callback.

        It updates self.selected_value then calls self.callback if defined.
        """
        if button is not None:
            self.selected_value = button.value
        if self.callback is not None:
            self.callback(self.selected_value)
        return True
        
    def build_widget(self):
        vb=gtk.VBox()

        buttons = gtk.HBox()

        b=gtk.Button(stock=gtk.STOCK_REFRESH)
        b.set_tooltip_text(_("Refresh missing snapshots"))
        b.connect("clicked", lambda b: self.refresh_snapshots())
        buttons.pack_start(b, expand=True)

        vb.pack_start(buttons, expand=False)

        hb=gtk.HBox()

        for i in xrange(-self.count / 2, self.count / 2):
            r=TimestampRepresentation(0, self.controller, width=100, visible_label=True, epsilon=30)
            r.connect("clicked", self.select_time)
            hb.pack_start(r, expand=False)

        hb.connect('scroll-event', self.handle_scroll_event)
        hb.connect('key-press-event', self.handle_key_press)
        vb.add(hb)

        self.container = hb
        self.update_timestamp(self.timestamp)
        return vb
