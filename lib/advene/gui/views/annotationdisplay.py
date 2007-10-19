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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Module displaying the contents of an annotation.
"""

# Advene part
from advene.gui.views import AdhocView

from gettext import gettext as _
import advene.util.helper as helper

import gtk

name="Annotation display plugin"

def register(controller):
    controller.register_viewclass(AnnotationDisplay)

class AnnotationDisplay(AdhocView):
    view_name = _("AnnotationDisplay")
    view_id = 'annotationdisplay'
    tooltip = _("Display the contents of an annotation")

    def __init__(self, controller=None, parameters=None, annotation=None):
        super(AnnotationDisplay, self).__init__(controller=controller)
        self.close_on_package_load = True
        self.contextual_actions = ()
        self.controller=controller
        self.annotation=annotation
        self.widget=self.build_widget()

    def set_annotation(self, a=None):
        self.annotation=a
        self.refresh()
        return True

    def set_master_view(self, v):
        v.register_slave_view(self)

    def refresh(self, *p):
        if self.annotation is None:
            d={ 'id': _("N/C"), 
                'begin': '--:--:--:--', 
                'end': '--:--:--:--', 
                'contents': '' }
        else:
            d={ 'id': self.annotation.id,
                'begin': helper.format_time(self.annotation.fragment.begin),
                'end': helper.format_time(self.annotation.fragment.end),
                'contents': self.annotation.content.data }
        for k, v in d.iteritems():
            self.label[k].set_text(v)
        return False

    def build_widget(self):
        v=gtk.VBox()

        self.label={}

        for label, name in (
            (_("Annotation "), 'id'),
            (_("Begin"), 'begin'),
            (_("End"), 'end'),
            ):
            h=gtk.HBox()
            l=gtk.Label(label)
            h.pack_start(l, expand=False)
            s=gtk.HSeparator()
            h.pack_start(s, expand=True)
            self.label[name]=gtk.Label()
            h.pack_start(self.label[name], expand=False)
            v.pack_start(h, expand=False)

        f=gtk.Frame(label=_("Contents"))
        c=self.label['contents']=gtk.Label()
        c.set_line_wrap(True)
        c.set_single_line_mode(False)
        c.set_alignment(0.0, 0.0)
        f.add(self.label['contents'])
        v.add(f)

        self.refresh()
        v.show_all()

        return v
