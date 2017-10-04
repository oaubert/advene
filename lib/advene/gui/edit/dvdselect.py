#
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
"""Widget used to select the DVD chapter in Advene.
"""

from gi.repository import Gdk
from gi.repository import Gtk
import re

from gettext import gettext as _

class DVDSelect:
    """DVDSelect class.

    FIXME: we could access the DVD and request its structure.

    FIXME: we should not base on URI but the package metadata should be more structured

    """
    def __init__(self, controller=None, current=None):
        self.controller=controller
        self.chapterwidget=None
        self.titlewidget=None
        self.widget=self.make_widget()
        if current is not None:
            self.init(current)

    def init(self, current):
        m = re.match("dvd\w*:.+@(\d+)[,:](\d+)", current)
        if m is not None:
            (title, chapter) = m.groups()
            self.titlewidget.set_value(int(title))
            self.chapterwidget.set_value(int(chapter))
        return True

    def get_chapter(self):
        return int(self.chapterwidget.get_value())

    def get_title(self):
        return int(self.titlewidget.get_value())

    def get_url(self):
        return self.controller.player.dvd_uri(self.get_title(),
                                              self.get_chapter())
        # FIXME: should ask the DVD module for the right MRL syntax
        #return "dvdsimple:///dev/dvd@%d:%d" % (self.get_title(),
        #                                       self.get_chapter())

    def get_widget(self):
        return self.widget

    def make_widget(self):
        vbox=Gtk.VBox()

        label=Gtk.Label(label=_("Select the correct\ntitle and chapter\nof the DVD"))
        vbox.add(label)

        hbox=Gtk.HBox()
        hbox.add(Gtk.Label(label=_("Title")))
        sp=Gtk.SpinButton()
        sp.set_range(1, 15)
        sp.set_increments(1, 1)
        hbox.pack_start(sp, False, True, 0)
        self.titlewidget=sp
        vbox.add(hbox)

        hbox=Gtk.HBox()
        hbox.add(Gtk.Label(label=_("Chapter")))
        sp=Gtk.SpinButton()
        sp.set_range(1, 30)
        sp.set_increments(1, 1)
        hbox.pack_start(sp, False, True, 0)
        self.chapterwidget=sp
        vbox.add(hbox)

        vbox.show_all()
        return vbox

if __name__ == "__main__":

    import advene.core.mediacontrol

    class DummyController:
        def __init__(self):
            f=advene.core.mediacontrol.PlayerFactory()
            self.player = f.get_player()
            self.player.check_player()

    def key_pressed_cb (win, event):
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == Gdk.KEY_q:
                Gtk.main_quit ()
                return True
        return False

    window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
    window.connect('key-press-event', key_pressed_cb)
    window.connect('destroy', lambda e: Gtk.main_quit())

    c = DummyController()
    sel=DVDSelect(controller=c)
    window.add(sel.get_widget())
    window.show_all()
    Gtk.main()
