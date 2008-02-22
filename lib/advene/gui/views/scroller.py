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
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Module displaying a text scroller below the video output."""

# Advene part
from advene.gui.views import AdhocView

from gettext import gettext as _

import gtk

class ScrollerView(AdhocView):
    view_name = _("Scroller")
    view_id = 'scroller'
    def __init__(self, controller=None):
        super(ScrollerView, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = ()

        self.controller=controller
        self.widget=self.build_widget()

    def close(self, *p):
        return False

    def display_text(self, text, where=None):
        l=self.present_label
        if where == 'past':
            l=self.past_label
        elif where == 'future':
            l=self.future_label
        l.set_text(text)
        return True

    def build_widget(self):
        v=gtk.HBox()

        style=v.get_style().copy()
        self.style = style

        black=gtk.gdk.color_parse('black')
        white=gtk.gdk.color_parse('white')

        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            style.bg[state]=black
            style.fg[state]=white
            style.text[state]=white
            #style.base[state]=white

        v.set_style(style)

        self.past_widget=gtk.VBox()
        self.past_widget.set_style(style)

        self.present_widget=gtk.VBox()
        self.present_widget.set_style(style)
        #self.present_alignment=gtk.Alignment(0.25, 0.25, 0, 0)
        #self.present_alignment.add(self.present_widget)
        self.present_widget.set_style(style)
        #self.present_alignment.set_style(style)

        self.future_widget=gtk.VBox()
        self.future_widget.set_style(style)

        v.add(self.past_widget)
        #v.add(self.present_alignment)
        v.add(self.present_widget)
        v.add(self.future_widget)

        def create_label(text, widget):
            eb=gtk.EventBox()
            l=gtk.Label(text)
            l.set_single_line_mode(False)
            eb.add(l)
            l.set_style(style)
            eb.set_style(style)
            widget.pack_start(eb)
            return l

        self.present_label = create_label('present',
                                          self.present_widget)
        self.present_label.set_alignment(0.5, 0)

        self.future_label = create_label('future',
                                         self.future_widget)
        self.future_label.set_alignment(1, 0)

        self.past_label = create_label('past',
                                       self.past_widget)
        self.past_label.set_alignment(0, 0)

        v.show_all()

        return v
