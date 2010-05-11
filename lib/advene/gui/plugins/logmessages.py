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
"""Log messages display.
"""

import gtk

from gettext import gettext as _
from advene.gui.views import AdhocView

name="Log messages"

def register(controller):
    controller.register_viewclass(LogMessages)

class LogMessages(AdhocView):
    """Display the content of the log buffer.
    """
    view_name = _("Log Messages")
    view_id = 'logmessages'
    def __init__ (self, controller=None, parameters=None):
        super(LogMessages, self).__init__(controller=controller)
        self.controller=controller
        self.widget=self.build_widget()

    def autoscroll(self, *p):
        # Autoscroll
        self.textview.scroll_mark_onscreen(self.controller.gui.logbuffer.get_mark("insert"))
        return True

    def reparent_done(self):
        self.autoscroll()
        return True

    def build_widget(self):
        sw=gtk.ScrolledWindow()
        self.textview=gtk.TextView(self.controller.gui.logbuffer)
        self.textview.set_wrap_mode(gtk.WRAP_CHAR)
        self.textview.set_editable(False)
        sw.add(self.textview)

        self.safe_connect(self.controller.gui.logbuffer, "changed", self.autoscroll)

        # Scroll for initial display
        def initial_display(t):
            self.autoscroll()
            return False
        self.textview.connect('map', initial_display)

        return sw
