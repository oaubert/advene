#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2012 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
"""PlayPause button.
"""

import gtk

import advene.core.config as config

class PlayPauseButton(gtk.ToolButton):
    def __init__(self, *p, **kw):
        super(PlayPauseButton, self).__init__(*p, **kw)
        self.active_id = gtk.STOCK_MEDIA_PLAY
        self.inactive_id = gtk.STOCK_MEDIA_PAUSE
        self.is_active = True

    def set_stock_ids(self, active_id, inactive_id):
        self.active_id = active_id
        self.inactive_id = inactive_id
        if self.is_active:
            self.set_stock_id(self.active_id)
        else:
            self.set_stock_id(self.inactive_id)

    def set_active(self, a):
        if a == self.is_active:
            return
        if a:
            self.set_stock_id(self.active_id)
            self.is_active = True
        else:
            self.set_stock_id(self.inactive_id)
            self.is_active = False
