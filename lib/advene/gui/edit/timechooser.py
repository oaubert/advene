#! /usr/bin/env python

# Advene part
import advene.core.config as config
import advene.util.vlclib
import advene.gui.util

from gettext import gettext as _

import gtk

class TimeChooser:
    def __init__(self, snapshots=None):
        self.snapshots=list(snapshots)
        self.widget=self.build_widget()

    def activate(self, snapshot):
        print "Activated %s" % snapshot
        return True

    def build_widget(self):
        self.snapshots.sort(lambda a, b: cmp(a.date,b.date))
        hbox=gtk.HBox()
        for snap in self.snapshots:
            vbox=gtk.VBox()
            # FIXME: make Images clickable to select time            
            i=gtk.Image()
            i.set_from_pixbuf(advene.gui.util.png_to_pixbuf(advene.util.vlclib.snapshot2png(snap)))
            # Does not work:
            i.connect("button-release-event", self.activate, snap)
            vbox.add(i)
            l = gtk.Label(advene.util.vlclib.format_time(snap.date))
            vbox.add(l)

            hbox.add(vbox)
        hbox.show_all()
        return hbox

    def popup(self):
        w = gtk.Window (gtk.WINDOW_TOPLEVEL)
        w.set_title (_("Snapshots"))

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        w.add(sw)
        
        sw.add_with_viewport(self.widget)

        w.show_all()
        return gtk.TRUE
