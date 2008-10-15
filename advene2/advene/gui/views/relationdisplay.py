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
"""Module displaying the contents of a relation
"""

import gtk
import gobject
from gettext import gettext as _

import advene.core.config as config
from advene.gui.views import AdhocView
import advene.util.helper as helper
from advene.gui.util import png_to_pixbuf
from advene.gui.widget import AnnotationRepresentation

name="Relation display plugin"

def register(controller):
    controller.register_viewclass(RelationDisplay)

class RelationDisplay(AdhocView):
    view_name = _("RelationDisplay")
    view_id = 'relationdisplay'
    tooltip = _("Display the contents of a relation")

    def __init__(self, controller=None, parameters=None, relation=None):
        super(RelationDisplay, self).__init__(controller=controller)
        self.close_on_package_load = True
        self.contextual_actions = ()
        self.controller=controller
        self.relation=relation
        self.widget=self.build_widget()
        self.refresh()

    def set_relation(self, r=None):
        self.relation=r
        self.refresh()
        return True

    def set_master_view(self, v):
        v.register_slave_view(self)
        self.close_on_package_load = False

    def update_annotation(self, annotation=None, event=None):
        if event == 'AnnotationEditEnd' and annotation in self.relation:
            self.refresh()
        return True

    def update_relation(self, relation=None, event=None):
        if relation != self.relation:
            return True
        if event == 'RelationEditEnd':
            self.refresh()
        elif event == 'RelationDelete':
            if self.master_view is None:
                # Autonomous view. We should close it.
                self.close()
            else:
                # There is a master view, just empty the representation
                self.set_relation(None)
        return True

    def refresh(self, *p):
        self.members_widget.foreach(self.members_widget.remove)

        if self.relation is None:
            self.label['title'].set_text(_("No relation"))
            self.label['contents'].set_text('')
        else:
            col=self.controller.get_element_color(self.relation)
            if col:
                title='<span background="%s">Relation <b>%s</b></span>' % (col, self.relation.id)
            else:
                title='Relation <b>%s</b>' % self.relation.id
            self.label['title'].set_markup(title)
            self.label['contents'].set_text('')
            for a in self.relation:
                self.members_widget.pack_start(AnnotationRepresentation(a, self.controller), expand=False)
            self.widget.show_all()
        return False

    def build_widget(self):
        v=gtk.VBox()

        self.label={}

        self.label['title']=gtk.Label()
        v.pack_start(self.label['title'], expand=False)

        exp=gtk.Expander()
        exp.set_expanded(False)
        exp.set_label(_("Contents"))
        c=self.label['contents']=gtk.Label()
        c.set_line_wrap(True)
        c.set_selectable(True)
        c.set_single_line_mode(False)
        c.set_alignment(0.0, 0.0)
        exp.add(c)
        v.pack_start(exp, expand=False)

        f=gtk.Frame(_("Members"))
        #  Display members
        self.members_widget=gtk.VBox()
        f.add(self.members_widget)

        v.add(f)
        return v
