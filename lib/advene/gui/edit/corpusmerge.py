#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2024 Olivier Aubert <contact@olivieraubert.net>
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
"""GUI to merge template package into corpus (multiple loaded packages).

It limits itself to merging structure/views

Template package: # schemas, # annotation types, # relation types, # views

Update table
Package | UpdateCheckbox | # An.types | # Updated AT | # R.T | # Upd. R.T | # Views | # Upd. Views |
"""
import logging
logger = logging.getLogger(__name__)

from gi.repository import Gtk
from gi.repository import GObject

from gettext import gettext as _

from advene.util.merger import Differ
from advene.gui.views import AdhocView
from advene.gui.util import dialog

class TreeViewMultiMerger:
    def __init__(self, controller=None, differs=None):
        self.fields = dict((
            ("Differ", GObject.TYPE_PYOBJECT),
            ("Package name", GObject.TYPE_STRING),
            ("Apply", GObject.TYPE_BOOLEAN),
            ("Updated annotation types", GObject.TYPE_STRING),
            ("Updated relation types", GObject.TYPE_STRING),
            ("Updated views", GObject.TYPE_STRING),
            ("Updated queries", GObject.TYPE_STRING),
            ("Updated resources", GObject.TYPE_STRING)
        ))
        self.field_column = dict((name, index) for (index, name) in enumerate(self.fields.keys()))
        self.controller = controller
        self.differs = differs
        self.store = self.build_liststore()
        self.widget = self.build_widget()

    def build_liststore(self):
        # Store reference to the element, string representation (title and id)
        # and boolean indicating wether it is imported or not
        model_types = list(self.fields.values())
        store = Gtk.ListStore(*model_types)

        for alias, differ in self.differs.items():
            stats = differ.diff_stats()
            store.append(row=[
                differ,
                alias,
                True,
                f"{stats['annotation_types_updated']}/{stats['annotation_types']}",
                f"{stats['relation_types_updated']}/{stats['relation_types']}",
                f"{stats['views_updated']}/{stats['views']}",
                f"{stats['queries_updated']}/{stats['queries']}",
                f"{stats['resources_updated']}/{stats['resources']}",
            ])
        return store

    def build_widget(self):
        treeview = Gtk.TreeView(model=self.store)
        treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        treeview.set_headers_clickable(True)
        treeview.set_enable_search(False)

        # Package name
        column = Gtk.TreeViewColumn(_('Package'), Gtk.CellRendererText(),
                                    text=self.field_column['Package name'])
        column.set_resizable(True)
        column.set_max_width(300)
        column.set_sort_column_id(self.field_column['Package name'])
        treeview.append_column(column)

        # Toggle
        renderer = Gtk.CellRendererToggle()
        renderer.set_property('activatable', True)

        column = Gtk.TreeViewColumn(_('Merge?'), renderer,
                                    active=self.field_column['Apply'])
        column.set_sort_column_id(self.field_column['Apply'])

        def toggled_cb(renderer, path, model, column):
            model[path][column] = not model[path][column]
            return True
        renderer.connect('toggled', toggled_cb, self.store, self.field_column['Apply'])

        treeview.append_column(column)

        for item in ("Updated annotation types",
                     "Updated relation types",
                     "Updated views",
                     "Updated queries",
                     "Updated resources"):
            column = Gtk.TreeViewColumn(item, Gtk.CellRendererText(),
                                        text=self.field_column[item])
            column.set_resizable(False)
            column.set_sort_column_id(self.field_column[item])
            treeview.append_column(column)

        return treeview

class MultiMergerView(AdhocView):
    view_name = _("MultiMerger")
    view_id = 'multimerger'

    def __init__(self, controller=None, parameters=None, sourcepackage=None, destpackages=None):
        super().__init__(controller=controller)
        self.controller = controller
        self.parameters = parameters
        opt, arg = self.load_parameters(parameters)
        self.close_on_package_load = False
        self.contextual_actions = ()
        self.options = {
            'display-result-dialog': False
            }
        if opt is not None:
            self.options.update(opt)

        self.sourcepackage =  sourcepackage
        self.destpackages = destpackages
        self.differs = dict( (alias, Differ(sourcepackage, p, self.controller))
                             for (alias, p) in destpackages.items()
                             if alias != 'advene' )
        self.widget = self.build_widget()

    def build_widget(self):
        vbox = Gtk.VBox()

        vbox.pack_start(Gtk.Label(_("Here are the elements that would get updated by the merging of %(source)s") % {'source': self.sourcepackage.uri }),
                        False, False, 0)

        def scrolled(widget):
            scroll_win = Gtk.ScrolledWindow ()
            scroll_win.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll_win.add(widget)
            return scroll_win

        self.mergerview = TreeViewMultiMerger(controller=self.controller, differs=self.differs)

        vbox.add(scrolled(self.mergerview.widget))

        self.buttonbox = Gtk.HButtonBox()

        updated = {}
        def validate(b):
            for row in self.mergerview.store:
                if row[self.mergerview.field_column['Apply']]:
                    differ = row[self.mergerview.field_column['Differ']]
                    for name, s, d, action, value in differ.diff_structure():
                        action(s, d)
                    differ.destination._modified = True
                    updated[differ.destination] = updated.get(differ.destination, 0) + 1
            if self.options.get('display-result-dialog'):
                # We will display output by alias
                output = "\n".join(f" - {alias}"
                                   for alias, p in self.destpackages.items()
                                   if alias != 'advene' and updated.get(p))
                message = f"""Elements have been updated. Do not forget to save the corpus.\nHere is a summary of the packages that have been updated.\n{output}"""
                dialog.message_dialog(message)
            # Update the Packages menu
            self.controller.gui.update_gui()
            self.close()
            return True

        b = Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', validate)
        self.buttonbox.add (b)

        b = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b.connect('clicked', lambda b: self.close())
        self.buttonbox.add (b)

        vbox.pack_start(self.buttonbox, False, True, 0)

        vbox.show_all()
        return vbox
