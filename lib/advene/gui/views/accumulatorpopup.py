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
"""Accumulator popup.
"""

import time
import operator

import gtk

from gettext import gettext as _

from advene.gui.views import AdhocView
from advene.gui.util import get_pixmap_button, name2color

class DummyLock:
    def __init__(self):
        self.count=0

    def acquire(self):
        #print "acquire %d" % self.count
        self.count += 1
        return True

    def release(self):
        #print "release %d" % self.count
        self.count -= 1
        return True

class AccumulatorPopup(AdhocView):
    """View displaying a limited number of popups.
    """
    view_name = _("PopupAccumulator")
    view_id = 'popupaccumulator'
    tooltip = ("Stack a limited number of popup widgets")

    def __init__ (self, controller=None, autohide=False, size=3,
                  vertical=False, scrollable=False):
        super(AccumulatorPopup, self).__init__(controller=controller)

        self.close_on_package_load = False

        self.size=size
        self.controller=controller
        # Hide the window if there is no widget
        self.autohide = autohide
        self.vertical=vertical
        self.scrollable=scrollable

        self.new_color = name2color('tomato')
        self.old_color = gtk.Button().get_style().bg[0]

        # List of tuples (widget, hidetime, frame)
        self.widgets=[]
        # Lock on self.widgets
        self.lock=DummyLock()

        # FIXME: find a way to make AdhocView.close() convert to hide()
        self.widget=self.build_widget()

    def undisplay_cb(self, button=None, widget=None):
        self.undisplay(widget)
        return True

    def display_message(self, message='', timeout=None, title=None):
        """Convenience method.
        """
        t=gtk.TextView()
        t.set_editable(False)
        t.set_cursor_visible(False)
        t.set_wrap_mode(gtk.WRAP_WORD)
        t.set_justification(gtk.JUSTIFY_LEFT)
        t.get_buffer().set_text(message)
        self.display(t, timeout, title)

    def display(self, widget=None, timeout=None, title=None):
        """Display the given widget.

        timeout is in ms.
        title is either a string (that will be converted to a label), or a gtk widget.
        """
        if title is None:
            title="X"
        if self.size and len(self.widgets) >= self.size:
            # Remove the last one
            self.undisplay(self.widgets[0][0])
        if timeout is not None and timeout != 0:
            hidetime=time.time() * 1000 + long(timeout)
        else:
            hidetime=None

        # Build a titled frame around the widget
        f=gtk.Frame()
        if isinstance(title, basestring):
            hb=gtk.HBox()

            l=gtk.Label(title)
            hb.pack_start(l, expand=False)

            b=get_pixmap_button('small_close.png')
            b.set_relief(gtk.RELIEF_NONE)
            b.connect('clicked', self.undisplay_cb, widget)
            hb.pack_start(b, expand=False, fill=False)

            f.set_label_widget(hb)
        else:
            # Hopefully it is a gtk widget
            f.set_label_widget(title)
        f.set_label_align(0.1, 0.5)
        f.set_shadow_type(gtk.SHADOW_ETCHED_OUT)
        f.add(widget)

        self.lock.acquire()
        for t in self.widgets:
            self.set_color(t[2].get_label_widget(), self.old_color)
        self.widgets.append( (widget, hidetime, f) )
        if hidetime:
            self.controller.register_usertime_action( hidetime,
                                                      lambda c, time: self.undisplay(widget))
        self.widgets.sort(key=operator.itemgetter(1))
        self.lock.release()
        self.contentbox.pack_start(f, expand=False, padding=2)

        f.show_all()
        self.show()
        nb=self.widget.get_parent()
        if isinstance(nb, gtk.Notebook):
            # Ensure that the view is visible
            nb.set_current_page(nb.page_num(self.widget))

        self.controller.notify('PopupDisplay', view=self)
        return True

    def set_color(self, button, color):
        for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            button.modify_bg (style, color)

    def get_popup_width(self):
        """Return the requested popup width

        According to the hbox size and the max number of popups.
        """
        if self.size:
            return self.contentbox.get_allocation().width / self.size
        else:
            return 120

    def undisplay(self, widget=None):
        # Find the associated frame
        self.lock.acquire()

        frames=[ t for t in self.widgets if t[0] == widget ]
        if not frames:
            return True
        if len(frames) > 1:
            print "Inconsistency in accumulatorpopup"
        t=frames[0]
        self.widgets.remove(t)
        self.lock.release()

        # We found at least one (and hopefully only one) matching record
        t[2].destroy()
        if not self.widgets and self.autohide:
            self.widget.hide()
        return True

    def hide(self, *p, **kw):
        self.widget.hide()
        return True

    def show(self, *p, **kw):
        self.widget.show_all()
        return True

    def update_position(self, pos):
        # This method is regularly called. We use it as a side-effect to
        # remove the widgets when the timeout expires.
        if self.widgets:
            self.lock.acquire()
            for w in self.widgets[:]:
                t=w[1]
                if t is not None and time.time() >= t:
                    self.undisplay(w[0])
            self.lock.release()
        return True

    def build_widget(self):
        mainbox=gtk.VBox()

        if self.vertical:
            self.contentbox = gtk.VBox()
            mainbox.add(self.contentbox)
        else:
            self.contentbox = gtk.HBox()
            mainbox.add(self.contentbox)

        if self.controller.gui:
            self.controller.gui.register_view (self)

        if self.scrollable:
            sw=gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            sw.add_with_viewport(mainbox)
            return sw
        else:
            return mainbox
