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
"""Transcription view.
"""

import itertools
from gi.repository import Gtk

from gettext import gettext as _

from advene.gui.views import AdhocView
from advene.gui.views.table import AnnotationTable
import advene.gui.views.table

name="Checker view plugin"

def register(controller):
    controller.register_viewclass(CheckerView)

class CheckerView(AdhocView):
    view_name = _("Checker")
    view_id = 'checker'
    tooltip = _("Check various package properties")

    def __init__ (self, controller=None, parameters=None):
        super(CheckerView, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = ()
        self.controller=controller
        self.options = {
            }

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        self.widget=self.build_widget()
        self.update_model()

    def overlapping_annotations(self):
        """Return a list of overlapping annotations for each annotation type.

        It returns 2 sets of elements: the ones which have a potentialy
        bogus begin time, and the ones with a potentialy bogus end
        time.
        """
        begins = set()
        ends = set()
        for at in self.controller.package.annotationTypes:
            for a, b in zip(at.annotations, at.annotations[1:]):
                if a.fragment.end > b.fragment.begin:
                    ends.add(a)
                    begins.add(b)
        return begins, ends

    def update_model(self):
        begins, ends = self.overlapping_annotations()
        overlap = list(begins.union(ends))

        def custom_data(b):
            if b is None:
                return (str, str)
            begin, end = None, None
            if b in begins:
                begin = "#ff6666"
            if b in ends:
                end = "#ff6666"
            return (begin, end)
        self.overlap_table.set_elements(overlap, custom_data)
        self.overlap_table.model.set_sort_column_id(advene.gui.views.table.COLUMN_TYPE, Gtk.SortType.ASCENDING)

    def build_widget(self):
        mainbox = Gtk.VBox()

        mainbox.pack_start(Gtk.Label(_("List of possible issues in the current package")), False, False, 0)

        notebook=Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.TOP)
        notebook.popup_disable()
        mainbox.add(notebook)

        table=AnnotationTable(controller=self.controller)
        self.overlap_table = table

        # Set colors
        table.columns['begin'].add_attribute(table.columns['begin'].get_cells()[0],
                                             'cell-background',
                                             advene.gui.views.table.COLUMN_CUSTOM_FIRST)
        table.columns['end'].add_attribute(table.columns['end'].get_cells()[0],
                                           'cell-background',
                                           advene.gui.views.table.COLUMN_CUSTOM_FIRST + 1)

        notebook.append_page(table.widget, Gtk.Label(label=_("Overlapping")))

        return mainbox

    def update_annotation (self, annotation=None, event=None):
        self.update_model()
        return True
