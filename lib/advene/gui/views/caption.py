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
"""Module displaying a text caption below the video output."""

# Advene part
from advene.gui.views import AdhocView

from gettext import gettext as _

from gi.repository import Gtk

class CaptionView(AdhocView):
    view_name = _("Caption")
    view_id = 'caption'
    tooltip = _("Display a text caption below the video output")

    def __init__(self, controller=None, parameters=None):
        super(CaptionView, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = ()

        self.controller=controller
        self.widget=self.build_widget()

    def close(self, *p):
        return False

    def update_position (self, pos):
        if pos is None:
            pos = self.controller.player.current_position_value
        if ( (self.begin and pos < self.begin)
             or (self.end and pos > self.end) ):
            self.display_text('', 0)
            self.begin=None
        return True

    def display_text(self, text, duration=1000):
        text=text[:50]
        self.label.set_text(text)
        self.begin=self.controller.player.current_position_value
        self.end=self.begin + duration
        return True

    def build_widget(self):
        v=Gtk.HBox()

        v.get_style_context().add_class('advene_caption')

        def create_label(text, widget):
            eb=Gtk.EventBox()
            l=Gtk.Label(label=text)
            l.set_single_line_mode(True)
            eb.add(l)
            l.get_style_context().add_class('advene_caption')
            eb.get_style_context().add_class('advene_caption')
            widget.pack_start(eb, True, True, 0)
            return l

        self.label=create_label('', v)

        v.show_all()

        return v
