#! /usr/bin/env python

"""Widget used to select the DVD chapter in Advene.
"""

import advene.core.config as config

import gtk

from gettext import gettext as _

class DVDSelect:
    """DVDSelect class.

    FIXME: we could access the DVD and request its structure.
    """
    def __init__(self, controller=None):
        self.controller=controller
        self.chapterwidget=None
        self.titlewidget=None
        self.widget=self.make_widget()

    def get_chapter(self):
        return self.chapterwidget.get_value()

    def get_title(self):
        return self.titlewidget.get_value()

    def get_url(self):
        return "dvdsimple:///dev/dvd@%d,%d" % (self.get_title(),
                                               self.get_chapter())

    def preview(self, button=None):
        if not hasattr(self, 'oldplaylist'):
            self.oldplaylist=self.controller.player.playlist_get_list()
            self.controller.player.playlist_clear()
            self.controller.player.playlist_add_item(self.get_url())
            self.controller.player.update_status("start")
            button.set_label(_("Stop"))
        else:
            self.controller.player.update_status("stop")
            self.controller.player.playlist_clear()
            for i in self.oldplaylist:
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
        sp.set_increments(1,1)
        hbox.pack_start(sp, expand=False)
        self.titlewidget=sp
        vbox.add(hbox)
        
        hbox=gtk.HBox()
        hbox.add(gtk.Label(_("Chapter")))
        sp=gtk.SpinButton()
        sp.set_range(1, 30)
        sp.set_increments(1,1)
        hbox.pack_start(sp, expand=False)
        self.chapterwidget=sp
        vbox.add(hbox)

        b=gtk.Button(_("Preview"))
        b.connect("clicked", self.preview)
        vbox.add(b)
                 
        vbox.show_all()
        return vbox

if __name__ == "__main__":

    import advene.core.mediacontrol
    
    class DummyController:
        def __init__(self):
            self.player = advene.core.mediacontrol.Player ()
            self.player.check_player()

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

    c = DummyController()
    sel=DVDSelect(controller=c)
    window.add(sel.get_widget())
    window.show_all()
    gtk.main()
