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
"""EditionHistory view

This view displays a list of last n edited/created elements.
"""

from gettext import gettext as _

from gi.repository import Gtk

from advene.model.annotation import Annotation, Relation

from advene.gui.views import AdhocView
import advene.gui.popup
import advene.util.helper as helper
from advene.gui.util import enable_drag_source
from advene.gui.widget import AnnotationRepresentation, RelationRepresentation

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
        self.contextual_actions = ()

        self.options={}

        self.update_annotation=self.refresh
        self.update_relation=self.refresh
        self.update_view=self.refresh
        self.update_query=self.refresh
        self.update_annotationtype=self.refresh
        self.update_relationtype=self.refresh
        self.update_schema=self.refresh
        self.update_model=self.refresh

        self.controller=controller
        self.widget=self.build_widget()
        self.refresh()

    def refresh(self, *p, **kw):
        def display_popup(widget, event, element):
            if event.button == 3:
                menu = advene.gui.popup.Menu(element, controller=self.controller)
                menu.popup()
                return True
            return False
        g=self.controller.gui
        for (w, elements) in ( (self.created, g.last_created),
                               (self.edited, g.last_edited) ):
            w.foreach(w.remove)
            for e in reversed(elements):
                if isinstance(e, Annotation):
                    b = AnnotationRepresentation(e, self.controller)
                elif isinstance(e, Relation):
                    b = RelationRepresentation(e, self.controller)
                else:
                    b = Gtk.Button("\n".join((helper.get_type(e), self.controller.get_title(e))), use_underline=False)
                b.connect('clicked', (lambda i, el: self.controller.gui.edit_element(el)),
                          e)
                content=getattr(e, 'content', None)
                if content:
                    b.set_tooltip_text(content.data)
                enable_drag_source(b, e, self.controller)
                b.connect('button-press-event', display_popup, e)
                w.pack_start(b, False, True, 0)
        self.widget.show_all()
        return True

    def build_widget(self):
        hb=Gtk.HBox()

        for (label, attname) in ( (_("Created"), 'created'),
                                  (_("Edited"), 'edited' ) ):
            c=Gtk.VBox()
            c.pack_start(Gtk.Label(label), False, False, 0)

            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            c.add(sw)

            v=Gtk.VBox()
            sw.add_with_viewport(v)
            setattr(self, attname, v)

            hb.add(c)

        v.show_all()
        return hb
