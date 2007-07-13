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
"""Widget used to adjust times in Advene.

It depends on a Controller instance to be able to interact with the video player.
"""

import advene.core.config as config

import re
import gtk
import advene.util.helper
from advene.gui.util import png_to_pixbuf

from gettext import gettext as _

class TimeAdjustment:
    """TimeAdjustment widget.

    Note: time values are integers in milliseconds.
    """
    def __init__(self, value=0, controller=None, videosync=False, editable=True, compact=False):
        self.value=value
        self.controller=controller
        self.sync_video=videosync
        # Small increment
        self.small_increment=config.data.preferences['scroll-increment']
        # Large increment
        self.large_increment=10 * config.data.preferences['scroll-increment']
        self.image=None
        self.editable=editable
        self.compact=compact
        self.widget=self.make_widget()
        self.update_display()

    def make_widget(self):

        def invalidate_snapshot(item, value):
            # Invalidate the image
            self.controller.package.imagecache.invalidate(value)
            self.update_display()
            return True

        def handle_image_click(button, event):
            if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
                # Display the popup menu
                menu = gtk.Menu()
                item = gtk.MenuItem(_("Invalidate snapshot"))
                item.connect('activate', invalidate_snapshot, self.value)
                menu.append(item)
                menu.show_all()
                menu.popup(None, None, None, 0, gtk.get_current_event_time())
                return True
            if event.button != 1:
                return False
            if event.state & gtk.gdk.CONTROL_MASK:
                self.use_current_position(button)
                return True
            else:
                self.play_from_here(button)
                return True
            return False

        def make_button(incr_value, pixmap):
            """Helper function to build the buttons."""
            b=gtk.Button()
            i=gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            # FIXME: to re-enable
            # The proper way is to do
            #b.set_image(i)
            # but it works only on linux, gtk 2.10
            # and is broken on windows and mac
            al=gtk.Alignment()
            al.set_padding(0, 0, 0, 0)
            al.add(i)
            b.add(al)

            b.connect("clicked", self.update_value_cb, incr_value)
            if incr_value < 0:
                tip=_("Decrement value by %.2f s") % (incr_value / 1000.0)
            else:
                tip=_("Increment value by %.2f s") % (incr_value / 1000.0)
            self.tooltips.set_tip(b, tip)
            return b

        self.tooltips = self.controller.gui.tooltips

        vbox=gtk.VBox()

        hbox=gtk.HBox()
        hbox.set_homogeneous(False)

        vb=gtk.VBox()
        if self.editable and not self.compact:
            b=make_button(-self.large_increment, "2leftarrow.png")
            vb.pack_start(b, expand=False)
            b=make_button(-self.small_increment, "1leftarrow.png")
            vb.pack_start(b, expand=False)
            

        hbox.pack_start(vb, expand=False)

        self.image = gtk.Image()
        self.image.set_from_pixbuf(png_to_pixbuf (self.controller.package.imagecache[self.value], width=100))

        b=gtk.Button()
        b.connect("button-press-event", handle_image_click)
        #b.set_image(self.image)
        al=gtk.Alignment()
        al.set_padding(0, 0, 0, 0)
        al.add(self.image)
        b.add(al)
        self.tooltips.set_tip(b, _("Click to play\ncontrol+click to set to current time\ncontrol+scroll to modify value\nright-click to invalidate screenshot"))
        hbox.pack_start(b, expand=False)

        vb=gtk.VBox()
        if self.editable and not self.compact:
            b=make_button(self.large_increment, "2rightarrow.png")
            vb.pack_start(b, expand=False)
            b=make_button(self.small_increment, "1rightarrow.png")
            vb.pack_start(b, expand=False)
        hbox.pack_start(vb, expand=False)

        hb = gtk.HBox()

        self.entry=gtk.Entry()
        # Default width of the entry field
        self.entry.set_width_chars(len(advene.util.helper.format_time(0.0)))
        self.entry.connect('activate', self.convert_entered_value)
        self.entry.connect('focus-out-event', self.convert_entered_value)
        self.entry.set_editable(self.editable)

        b=gtk.Button()
        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'set-to-now.png') ))
        self.tooltips.set_tip(b, _("Set to current player position"))
        b.add(i)
        b.connect("clicked", self.use_current_position)

        hb.pack_start(self.entry, expand=False)
        hb.pack_start(b, expand=False)

        vbox.pack_start(hb, expand=False)
        vbox.pack_start(hbox, expand=False)
        vbox.show_all()

        # The widget can receive drops from annotations
        vbox.connect("drag_data_received", self.drag_received)
        vbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation'], gtk.gdk.ACTION_LINK)

        # Handle scroll actions
        def handle_scroll_event(button, event):
            if not (event.state & gtk.gdk.CONTROL_MASK):
                return True
            if event.direction == gtk.gdk.SCROLL_DOWN:
                incr=config.data.preferences['scroll-increment']
            else:
                incr=-config.data.preferences['scroll-increment']

            v=self.value
            self.value += incr
            self.update_display()
            return True

        vbox.connect("scroll-event", handle_scroll_event)

        vbox.show_all()
        return vbox

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
            self.value = source.fragment.begin
            self.update_display()
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def play_from_here(self, button):
        if self.controller.player.status == self.controller.player.PauseStatus:
            self.controller.update_status("resume", self.value)
        elif self.controller.player.status != self.controller.player.PlayingStatus:
            self.controller.update_status("start", self.value)
        self.controller.update_status("set", self.value)
        return True

    def use_current_position(self, button):
        self.value=self.controller.player.current_position_value
        self.update_display()
        return True

    def update_snapshot(self, button):
        # FIXME: to implement
        print "Not implemented yet."
        pass

    # Static values used in numericTime
    _hour = r'(?P<hour>\d+)'
    _minute = r'(?P<minute>\d+)'
    _second = r'(?P<second>\d+(\.\d+))'
    _time = _hour + r':' + _minute + r'(:' + _second + r')?'
    _timeRE = re.compile(_time, re.I)

    def numericTime(self, s):
        """Converts a time string into a long value.

        This function is inspired from the numdate.py example script from the
        egenix mxDateTime package.

        If the input string s is a valid time expression of the
        form hh:mm:ss.sss or hh:mm:ss or hh:mm, return
        the corresponding value in milliseconds (float), else None
        """

        if s is None: return None
        dt = None
        match = TimeAdjustment._timeRE.search(s)
        if match is not None:
            hh = int(match.group('hour'))
            mm = int(match.group('minute'))
            second = match.group('second')
            if second:
                ss = float(second)
            else:
                ss = 0.0
            dt=int(1000 * (ss + (60 * mm) + (3600 * hh)))
        return dt

    def convert_entered_value(self, *p):
        t=self.entry.get_text()
        v=self.numericTime(t)
        if v is not None and v != self.value:
            self.value = self.check_bound_value(v)
            if self.sync_video:
                self.controller.move_position(self.value, relative=False)
            self.update_display()
        return False

    def check_bound_value(self, value):
        if value < 0:
            value = 0
        elif (self.controller.cached_duration > 0
              and value > self.controller.cached_duration):
            value = self.controller.cached_duration
        return value

    def update_display(self):
        """Updates the value displayed in the entry according to the current value."""
        self.entry.set_text(advene.util.helper.format_time(self.value))
        # Update the image
        self.image.set_from_pixbuf(png_to_pixbuf (self.controller.package.imagecache[self.value],
                                                                  width=100))

    def update_value_cb(self, widget, increment):
        if not self.editable:
            return True
        self.value=self.value + increment
        self.value=self.check_bound_value(self.value)
        if self.sync_video:
            self.controller.move_position(self.value, relative=False)
        self.update_display()
        return True

    def get_widget(self):
        return self.widget

    def get_value(self):
        return self.value

if __name__ == "__main__":
    # Unit test
    import os
    import advene.core.imagecache
    from advene.model.package import Package

    p=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
    config.data.fix_paths(p)

    #config.data.fix_paths()
    class DummyController:
        def __init__(self, package):
            self.package=package
            self.package.imagecache=advene.core.imagecache.ImageCache()
            self.cached_duration = 2 * 3600 * 1000

        def move_position (self, value, relative=True):
            print "Move position %d (relative: %s)" % (value, str(relative))

    def key_pressed_cb (win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True
        return False

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.connect ("key-press-event", key_pressed_cb)
    window.connect ("destroy", lambda e: gtk.main_quit())

    p=Package ('dummy', source=None)
    con=DummyController(p)
    ta=TimeAdjustment(value=6000, controller=con)
    window.add(ta.get_widget())
    window.show_all()
    gtk.main()
