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
"""EditionHistory view

This view displays a list of last n edited/created elements.
"""

from advene.gui.views import AdhocView

from gettext import gettext as _

import gtk

name="EditionHistory view plugin"

def register(controller):
    controller.register_viewclass(EditionHistory)

class EditionHistory(AdhocView):
    view_name = _("Edition History")
    view_id = 'editionhistory'
    tooltip = _("Access last edited/created elements")
    def __init__ (self, controller=None, **kw):
        super(EditionHistory, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = ( )

        self.options={}

        self.update_annotation=self.refresh
        self.update_relation=self.refresh
        self.update_view=self.refresh
        self.update_query=self.refresh
        self.update_annotationtype=self.refresh
        self.update_relationtype=self.refresh
        self.update_schema=self.refresh

        self.controller=controller
        self.widget=self.build_widget()
        self.refresh()

    def refresh(self, *p, **kw):
        g=self.controller.gui
        for (w, elements) in ( (self.created, g.last_created),
                               (self.edited, g.last_edited) ):
            w.foreach(w.remove)
            for e in reversed(elements):
                b=gtk.Button(self.controller.get_title(e), use_underline=False)
                b.connect('clicked', (lambda i, el: self.controller.gui.edit_element(el)),
                          e)
                w.pack_start(b, expand=False)
        self.widget.show_all()
        return True

    def build_widget(self):
        hb=gtk.HBox()

        v=gtk.VBox()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        v.add(sw)

        self.edited=gtk.VBox()
        sw.add_with_viewport(self.edited)
    
        hb.add(v)

        v=gtk.VBox()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        v.add(sw)

        self.created=gtk.VBox()
        sw.add_with_viewport(self.created)
    
        hb.add(v)

        v.show_all()
        return hb
