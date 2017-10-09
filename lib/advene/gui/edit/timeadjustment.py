
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
"""Widget used to adjust times in Advene.

It depends on a Controller instance to be able to interact with the video player.
"""
import logging
logger = logging.getLogger(__name__)

import advene.core.config as config

from gi.repository import Gdk
from gi.repository import Gtk
import advene.util.helper as helper
from advene.gui.widget import TimestampRepresentation
from advene.gui.util import encode_drop_parameters, decode_drop_parameters
from gettext import gettext as _

class TimeAdjustment:
    """TimeAdjustment widget.

    Note: time values are integers in milliseconds.
    """
    def __init__(self, value=0, controller=None, videosync=False, editable=True, compact=False, callback=None):
        self.value=value
        self.controller=controller
        self.sync_video=videosync
        # Small increment
        self.small_increment=config.data.preferences['scroll-increment']
        # Large increment
        self.large_increment=config.data.preferences['second-scroll-increment']
        self.image=None
        self.editable=editable
        self.compact=compact
        # Callback is a method which will be called *before* setting
        # the new value. If it returns False, then the new value will
        # not be used.
        self.callback=callback
        self.widget=self.make_widget()
        self.update_display()

    def make_widget(self):

        def refresh_snapshot(item):
            self.image.refresh_snapshot()
            return True

        def image_button_clicked(button):
            event=Gtk.get_current_event()
            if event.get_state().state & Gdk.ModifierType.CONTROL_MASK:
                self.use_current_position(button)
                return True
            else:
                self.play_from_here(button)
                return True

        def image_button_press(button, event):
            if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
                # Display the popup menu
                menu = Gtk.Menu()
                item = Gtk.MenuItem(_("Refresh snapshot"))
                item.connect('activate', refresh_snapshot)
                menu.append(item)
                menu.show_all()
                menu.popup_at_pointer(None)
                return True
            return False

        def make_button(incr_value, pixmap):
            """Helper function to build the buttons."""
            b=Gtk.Button()
            i=Gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            b.set_image(i)

            def increment_value_cb(widget, increment):
                self.set_value(self.value + increment)
                return True
            b.connect('clicked', increment_value_cb, incr_value)
            if incr_value < 0:
                tip=_("Decrement value by %.2f s") % (incr_value / 1000.0)
            else:
                tip=_("Increment value by %.2f s") % (incr_value / 1000.0)
            b.set_tooltip_text(tip)
            return b

        vbox=Gtk.VBox()

        hbox=Gtk.HBox()
        hbox.set_homogeneous(False)

        if self.editable:
            vb=Gtk.VBox()
            b=make_button(-self.large_increment, "2leftarrow.png")
            vb.pack_start(b, False, True, 0)
            b=make_button(-self.small_increment, "1leftarrow.png")
            vb.pack_start(b, False, True, 0)
            hbox.pack_start(vb, False, True, 0)

        if self.compact:
            width=50
        else:
            width=100
        self.image = TimestampRepresentation(self.value,
                                             None,
                                             self.controller,
                                             width,
                                             visible_label=False,
                                             callback=self.set_value)
        self.image.connect('button-press-event', image_button_press)
        self.image.connect('clicked', image_button_clicked)
        self.image.set_tooltip_text(_("Click to play\nControl+click to set to current time\nScroll to modify value (with control/shift)\nRight-click to invalidate screenshot"))
        hbox.pack_start(self.image, False, True, 0)

        if self.editable:
            vb=Gtk.VBox()
            b=make_button(self.large_increment, "2rightarrow.png")
            vb.pack_start(b, False, True, 0)
            b=make_button(self.small_increment, "1rightarrow.png")
            vb.pack_start(b, False, True, 0)
            hbox.pack_start(vb, False, True, 0)

        hb = Gtk.HBox()

        if self.editable:
            self.entry=Gtk.Entry()
            self.entry.set_tooltip_text(_("Enter a timecode.\nAn integer value will be considered as milliseconds.\nA float value (12.2) will be considered as seconds.\nHH:MM:SS.sss values are possible."))
            # Default width of the entry field
            self.entry.set_width_chars(len(helper.format_time(0.0)))
            self.entry.connect('activate', self.convert_entered_value)
            self.entry.connect('focus-out-event', self.convert_entered_value)
            self.entry.set_editable(self.editable)
            hb.pack_start(self.entry, False, True, 0)
        else:
            self.entry=None

        if self.editable:
            current_pos=Gtk.Button()
            i=Gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', 'set-to-now.png') ))
            current_pos.set_tooltip_text(_("Set to current player position"))
            current_pos.add(i)
            current_pos.connect('clicked', self.use_current_position)
            hb.pack_start(current_pos, False, True, 0)

        vbox.pack_start(hbox, False, True, 0)
        vbox.pack_start(hb, False, True, 0)
        hb.set_style(self.image.box.get_style())
        #self.entry.set_style(self.image.box.get_style())
        vbox.set_style(self.image.box.get_style())
        vbox.show_all()

        hb.set_no_show_all(True)
        hbox.set_no_show_all(True)
        self.image.label.hide()
        hb.show()

        def handle_scroll_event(button, event):
            if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
                i=config.data.preferences['scroll-increment']
            elif event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                i=config.data.preferences['second-scroll-increment']
            else:
                # 1 frame
                i = self.controller.frame2time(1)

            if event.direction == Gdk.ScrollDirection.DOWN or event.direction == Gdk.ScrollDirection.LEFT:
                incr=-i
            elif event.direction == Gdk.ScrollDirection.UP or event.direction == Gdk.ScrollDirection.RIGHT:
                incr=i

            if not self.set_value(self.value + incr):
                return True
            return True

        if self.editable:
            # The widget can receive drops from annotations
            vbox.connect('drag-data-received', self.drag_received)
            vbox.drag_dest_set(Gtk.DestDefaults.MOTION |
                               Gtk.DestDefaults.HIGHLIGHT |
                               Gtk.DestDefaults.ALL,
                               config.data.get_target_types('annotation', 'timestamp'),
                               Gdk.DragAction.LINK)

            vbox.connect('scroll-event', handle_scroll_event)

        vbox.show_all()
        return vbox

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source_uri=str(selection.get_data(), 'utf8').split('\n')[0]
            source=self.controller.package.annotations.get(source_uri)
            self.set_value(source.fragment.begin)
        elif targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.get_data().decode('utf-8'))
            v=int(float(data['timestamp']))
            self.set_value(v)
        else:
            logger.warn("Unknown target type for drop: %d" % targetType)
        return True

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        """Handle the drag-sent event.
        """
        if targetType == config.data.target_type['timestamp']:
            selection.set(selection.get_target(), 8, encode_drop_parameters(timestamp=self.value))
            return True
        elif targetType in ( config.data.target_type['text-plain'],
                             config.data.target_type['TEXT'],
                             config.data.target_type['STRING'] ):
            selection.set(selection.get_target(), 8, helper.format_time(self.value))
            return True
        return False

    def play_from_here(self, button):
        self.controller.update_status("seek", self.value)
        return True

    def use_current_position(self, button):
        self.set_value(self.controller.player.current_position_value)
        return True

    def update_snapshot(self, button):
        # FIXME: to implement
        logger.warn("Not implemented yet.")
        pass

    def convert_entered_value(self, *p):
        t=self.entry.get_text()
        v=helper.parse_time(t)
        if v is not None and v != self.value:
            if not self.set_value(v):
                return False
        return False

    def check_bound_value(self, value):
        if value < 0 or value is None:
            value = 0
        elif (self.controller.cached_duration > 0
              and value > self.controller.cached_duration):
            value = self.controller.cached_duration
        return value

    def update(self):
        self.update_display()

    def update_display(self):
        """Updates the value displayed in the entry according to the current value."""
        self.entry.set_text(helper.format_time(self.value))
        self.image.value=self.value

    def get_widget(self):
        return self.widget

    def get_value(self):
        return self.value

    def set_value(self, v):
        """Set the new value.

        The method does various consistency checks, and can leave the
        value unset if a callback is defined and returns False.
        """
        if self.value == v:
            return True
        v = self.check_bound_value(v)
        if self.callback and not self.callback(v):
            return False
        self.value=v
        self.update_display()
        if self.sync_video:
            self.controller.update_status("seek", self.value)
        return True
