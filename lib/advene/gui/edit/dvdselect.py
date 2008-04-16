#
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
"""Widget used to select the DVD chapter in Advene.
"""

import gtk
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
            self.titlewidget.set_value(long(title))
            self.chapterwidget.set_value(long(chapter))
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

    def preview(self, button=None):
        if not hasattr(self, 'oldplaylist'):
            self.oldplaylist=self.controller.player.playlist_get_list()
            self.controller.player.playlist_clear()
            mediafile=self.get_url()
            if isinstance(mediafile, unicode):
                mediafile=mediafile.encode('utf8')
            self.controller.player.playlist_add_item(mediafile)
            self.controller.player.update_status("start")
            button.set_label(_("Stop"))
        else:
            self.controller.player.update_status("stop")
            self.controller.player.playlist_clear()
            for i in self.oldplaylist:
                if isinstance(i, unicode):
                    i=i.encode('utf8')
                self.controller.player.playlist_add_item(i)
            del self.oldplaylist
            button.set_label(_("Preview"))
        return True

    def get_widget(self):
        return self.widget

    def make_widget(self):
        vbox=gtk.VBox()

        label=gtk.Label(_("Select the correct\ntitle and chapter\nof the DVD"))
        vbox.add(label)

        hbox=gtk.HBox()
        hbox.add(gtk.Label(_("Title")))
        sp=gtk.SpinButton()
        sp.set_range(1, 15)
        sp.set_increments(1, 1)
        hbox.pack_start(sp, expand=False)
        self.titlewidget=sp
        vbox.add(hbox)

        hbox=gtk.HBox()
        hbox.add(gtk.Label(_("Chapter")))
        sp=gtk.SpinButton()
        sp.set_range(1, 30)
        sp.set_increments(1, 1)
        hbox.pack_start(sp, expand=False)
        self.chapterwidget=sp
        vbox.add(hbox)

        b=gtk.Button(_("Preview"))
        b.connect('clicked', self.preview)
        vbox.add(b)

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
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True
        return False

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.connect('key-press-event', key_pressed_cb)
    window.connect('destroy', lambda e: gtk.main_quit())

    c = DummyController()
    sel=DVDSelect(controller=c)
    window.add(sel.get_widget())
    window.show_all()
    gtk.main()
