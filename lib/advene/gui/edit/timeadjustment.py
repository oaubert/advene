"""Widget used to adjust times in Advene.

It depends on a Controller instance to be able to interact with the video player.
"""

import advene.core.config as config

import re
import gtk
import advene.util.vlclib
import advene.gui.util

from gettext import gettext as _

class TimeAdjustment:
    """TimeAdjustment widget.

    Note: time values are integers in milliseconds.
    """    
    def __init__(self, value=0, controller=None, videosync=False, editable=True):
        self.value=value
        self.controller=controller
        self.sync_video=videosync
        # Small increment: 1/10 sec
        self.small_increment=100
        # Large increment: 1 sec
        self.large_increment=1000
        self.image=None
        self.editable=editable
        self.widget=self.make_widget()
        self.update_display()
        
    def make_widget(self):
        self.tooltips = gtk.Tooltips ()
        
        vbox=gtk.VBox()
        
        self.image = gtk.Image()
        self.image.set_from_pixbuf(advene.gui.util.png_to_pixbuf (self.controller.imagecache[self.value]))
        vbox.add(self.image)

        hbox=gtk.HBox()

        def make_button(incr_value, pixmap):
            """Helper function to build the buttons."""
            b=gtk.Button()
            i=gtk.Image()
            i.set_from_file(config.data.advenefile(pixmap))
            b.add(i)
            b.connect("clicked", self.update_value_cb, incr_value)
            if incr_value < 0:
                tip=_("Decrement value by %.2f s") % (incr_value / 1000.0)
            else:
                tip=_("Increment value by %.2f s") % (incr_value / 1000.0)
            self.tooltips.set_tip(b, tip)
            return b

        if self.editable:
            b=make_button(-self.large_increment, "pixmaps/2leftarrow.png")
            hbox.add(b)
            b=make_button(-self.small_increment, "pixmaps/1leftarrow.png")
            hbox.add(b)

        self.entry=gtk.Entry()
        # Default width of the entry field (+2 chars for security)
        self.entry.set_width_chars(len(advene.util.vlclib.format_time(0))+2)
        self.entry.connect("changed", self.convert_entered_value)
        self.entry.set_editable(self.editable)
        hbox.add(self.entry)

        if self.editable:
            b=make_button(self.small_increment, "pixmaps/1rightarrow.png")
            hbox.add(b)
            b=make_button(self.large_increment, "pixmaps/2rightarrow.png")
            hbox.add(b)

        hbox.show_all()
        
        vbox.pack_start(hbox, expand=False)

        hbox=gtk.HButtonBox()

        b=gtk.Button(_("Play"))
        self.tooltips.set_tip(b, _("Play from the indicated position"))
        b.connect("clicked", self.play_from_here)
        hbox.add(b)

        if self.editable:
            b=gtk.Button(_("Current"))
            self.tooltips.set_tip(b, _("Use the current position value"))
            b.connect("clicked", self.use_current_position)
            hbox.add(b)
        
        b=gtk.Button(_("Snap"))
        self.tooltips.set_tip(b, _("Update the associated snapshot"))
        b.connect("clicked", self.update_snapshot)
        hbox.add(b)

        vbox.pack_start(hbox, expand=False)
        
        vbox.show_all()
        return vbox

    def play_from_here(self, button):
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
    _hour = r'(?P<hour>[012]?\d)'
    _minute = r'(?P<minute>[0-6]\d)'
    _second = r'(?P<second>[0-6]\d(?:\.\d+)?)'
    _time = _hour + r':' + _minute + r'(?::' + _second + r')?'
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
            hour = match.group('hour')
            minute = match.group('minute')
            second = match.group('second')
            hh = int(hour); mm = int(minute)
            if second:
                ss = int(float(second)*1000)
            else:
                ss = 0
            dt=ss + (60 * 1000 * mm) + (3600 * 1000 * hh)
        return dt

    def convert_entered_value(self, dummy):
        t=self.entry.get_text()
        v=self.numericTime(t)
        if v is not None and v != self.value:
            self.value = self.check_bound_value(v)
            if self.sync_video:
                self.controller.move_position(self.value, relative=False)            
            self.update_display()
        return True

    def check_bound_value(self, value):
        if value < 0:
            value = 0
        elif (self.controller.cached_duration > 0
              and value > self.controller.cached_duration):
            value = self.controller.cached_duration
        return value

    def update_display(self):
        """Updates the value displayed in the entry according to the current value."""
        self.entry.set_text(advene.util.vlclib.format_time(self.value))
        # Update the image
        self.image.set_from_pixbuf(advene.gui.util.png_to_pixbuf (self.controller.imagecache[self.value]))
        
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
    import advene.core.imagecache
    
    class DummyController:
        def __init__(self):
            self.imagecache=advene.core.imagecache.ImageCache()

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
    
    con=DummyController()
    ta=TimeAdjustment(value=6000, controller=con)
    window.add(ta.get_widget())
    window.show_all()
    gtk.main()
