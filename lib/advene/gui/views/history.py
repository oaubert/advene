"""Module displaying navigation history."""

# Advene part
import advene.core.config as config
import advene.util.vlclib as vlclib
import advene.gui.util

from gettext import gettext as _

import gtk

class HistoryNavigation:
    def __init__(self, controller=None, history=None):
        self.controller=controller
        self.history=history
        self.widget=self.build_widget()

    def activate(self, widget=None, data=None, timestamp=None):
        print "Activated %s" % timestamp
        return True

    def build_widget(self):
        hbox=gtk.HBox()
        for t in self.history:
            snap=self.controller.imagecache[t]
            
            vbox=gtk.VBox()
            # FIXME: make Images clickable to select time            
            i=gtk.Image()
            i.set_from_pixbuf(advene.gui.util.png_to_pixbuf(snap))
            # Does not work:
            e=gtk.EventBox()
            e.connect("button-release-event", self.activate, t)
            e.add(i)
            vbox.add(e)
            l = gtk.Label(advene.util.vlclib.format_time(t))
            vbox.add(l)

            hbox.add(vbox)
        hbox.show_all()
        return hbox

    def popup(self):
        w = gtk.Window (gtk.WINDOW_TOPLEVEL)
        w.set_title (_("Navigation history"))

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        w.add(sw)
        
        sw.add_with_viewport(self.widget)

        w.show_all()
        return True
