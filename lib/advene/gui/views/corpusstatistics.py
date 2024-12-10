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

# Corpus statistics
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import csv
import os

from gi.repository import GObject
from gi.repository import Gtk

from advene.gui.util import dialog
from advene.gui.views import AdhocView
from advene.gui.views.table import AnnotationTable
from advene.util.tools import open_in_filebrowser

name = "Corpus statistics"

def register(controller):
    controller.register_viewclass(CorpusStatistics)

class CorpusStatistics(AdhocView):
    view_name = _("Corpus statistics")
    view_id = 'corpusstatistics'
    tooltip = _("Global analyses of multiple packages")

    def __init__(self, controller=None, parameters=None):
        super().__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = []
        self.controller = controller
        self.widget = self.build_widget()
        self.populate()

    @property
    def packages(self):
        """Return the package dict minus the advene alias
        """
        return dict( (k, v)
                      for (k, v) in self.controller.packages.items()
                      if k != "advene" )

    def relationtypes_liststore(self):
        model = dict(element=GObject.TYPE_PYOBJECT,
                     package_alias=GObject.TYPE_STRING,
                     id=GObject.TYPE_STRING,
                     title=GObject.TYPE_STRING,
                     color=GObject.TYPE_STRING,
                     relation_count=GObject.TYPE_INT,
                     annotation_count=GObject.TYPE_INT)

        # Store reference to the element (at), source package alias, string representation (title)
        store = Gtk.ListStore(*model.values())
        store.column = dict((alias, index) for (index, alias) in enumerate(model.keys()))

        for alias, package in self.packages.items():
            for rt in package.relationTypes:
                store.append(row=[ rt,
                                   alias,
                                   rt.id,
                                   self.controller.get_title(rt),
                                   self.controller.get_element_color(rt),
                                   len(rt.relations),
                                   len(rt.annotations)
                                  ])
        return store

    def annotationtypes_liststore(self):
        model = dict(element=GObject.TYPE_PYOBJECT,
                     package_alias=GObject.TYPE_STRING,
                     id=GObject.TYPE_STRING,
                     title=GObject.TYPE_STRING,
                     annotation_count=GObject.TYPE_INT)

        # Store reference to the element (at), source package alias, string representation (title)
        store = Gtk.ListStore(*model.values())
        store.column = dict((alias, index) for (index, alias) in enumerate(model.keys()))

        for alias, package in self.packages.items():
            for annotationtype in package.annotationTypes:
                store.append(row=[ annotationtype,
                                   alias,
                                   annotationtype.id,
                                   self.controller.get_title(annotationtype),
                                   len(annotationtype.annotations)
                                  ])
        return store

    def populate(self):

        def package_info(alias):
            p = self.packages[alias]
            return f"{alias} - { p.title } - { len(p.annotationTypes) } types d'annotation - { len(p.annotations) } annotations"

        packages_info = "\n".join(package_info(alias) for alias in self.packages)
        self.set_summary(f"""<big><b>Corpus statistics</b></big>

        <b>{len(self.packages)} loaded packages</b>
{packages_info}
        """)

    def build_annotation_type_table(self):
        rows = self.controller.global_package.annotation_types_by_title_stats()

        def csv_export():
            filename = dialog.get_filename(title=_("Give the CSV output filename"),
                                           default_dir=self.controller.global_package.dir,
                                           action=Gtk.FileChooserAction.SAVE,
                                           button=Gtk.STOCK_SAVE)
            if filename:
                if os.path.exists(filename):
                    dialog.message_dialog(_(f"Output file {filename} already exists. Remove it before proceeding."))
                    return
                with open(filename, mode="w", encoding="utf-8") as file:
                   writer = csv.writer(file)
                   writer.writerows(rows)
                message = _("Data exported to\n%s\nDo you want to open it?") % filename
                icon =  Gtk.MessageType.QUESTION
                if dialog.message_dialog(message, icon=icon) and icon ==  Gtk.MessageType.QUESTION:
                    # Try to open the file
                    open_in_filebrowser(filename)

        vbox = Gtk.VBox()

        controls = Gtk.HBox()
        controls.set_hexpand(False)
        controls.set_halign(Gtk.Align.START)

        b = Gtk.ToolButton(_("Export"))
        b.set_tooltip_text(_("Export data as CSV"))
        b.connect('clicked', lambda b: csv_export())
        b.set_icon_name('document-send')
        controls.add(b)
        vbox.pack_start(controls, False, False, 0)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.add(scrolled_window)

        # Create a Gtk.Grid
        grid = Gtk.Grid()
        grid.set_row_spacing(5)
        grid.set_column_spacing(10)

        for row_index, row in enumerate(rows):
            for col_index, text in enumerate(row):
                label = Gtk.Label()
                label.set_selectable(True)  # Enable text selection
                label.set_hexpand(True)
                if row_index == 0:
                    # Header -> bold
                    label.set_markup(f"<b>{text}</b>")
                elif text is None:
                    label.set_markup("<i>N/A</i>")
                else:
                    label.set_text(str(text))
                label.set_hexpand(True)
                label.set_halign(Gtk.Align.FILL)
                grid.attach(label, col_index, row_index, 1, 1)

        # Add the grid to the scrolled window
        scrolled_window.add(grid)
        return vbox

    def build_relationtype_table(self, callback=None):
        store = self.relationtypes_liststore()
        tree_view = Gtk.TreeView(store)
        select = tree_view.get_selection()
        select.set_mode(Gtk.SelectionMode.MULTIPLE)
        tree_view.set_enable_search(False)

        columns = {}
        for (name, label, col) in (
                ('package', _("Package"), store.column['package_alias']),
                ('title', _("Relation"), store.column['title']),
                ('annotations', _("Annotations"), store.column['annotation_count']) ):
            columns[name] = Gtk.TreeViewColumn(label,
                Gtk.CellRendererText(),
                cell_background=store.column['color'],
                text=col)
            columns[name].set_reorderable(True)
            columns[name].set_sort_column_id(col)
            tree_view.append_column(columns[name])

        # Resizable columns: title, type
        for name in ('title', 'package'):
            columns[name].set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            columns[name].set_resizable(True)
            columns[name].set_min_width(40)
        columns['title'].set_expand(True)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(tree_view)

        sw.treeview = tree_view

        def row_activated_cb(widget, path, view_column):
            if callback:
                callback(store[path][store.column['element']])
            return True
        tree_view.connect('row-activated', row_activated_cb)

        return sw

    def build_relationtype_explorer(self):
        """2-paned relationtype/relation table explorer
        """
        explorer = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        explorer.set_name('relationtype_explorer')
        annotation_table = AnnotationTable(controller=self.controller, elements=[])
        def selected_type(rt):
            annotation_table.set_elements(rt.annotations)
            return True
        relationtype_table = self.build_relationtype_table(selected_type)
        explorer.add1(relationtype_table)
        explorer.add2(annotation_table.widget)
        explorer.set_position(400)
        return explorer

    def build_annotation_type_list(self):
        tree_view = Gtk.TreeView(self.annotationtypes_liststore())
        select = tree_view.get_selection()
        select.set_mode(Gtk.SelectionMode.MULTIPLE)
        tree_view.set_enable_search(False)

        columns = {}
        for (name, label, col) in (
                ('title', _("Title"), 3),
                ('package', _("Package"), 1),
                ('annotations', _("Annotations"), 4) ):
            columns[name] = Gtk.TreeViewColumn(label,
                Gtk.CellRendererText(),
                text=col)
            columns[name].set_reorderable(True)
            columns[name].set_sort_column_id(col)
            tree_view.append_column(columns[name])

        # Resizable columns: title, type
        for name in ('title', 'package'):
            columns[name].set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            columns[name].set_resizable(True)
            columns[name].set_min_width(40)
        columns['title'].set_expand(True)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(tree_view)

        sw.treeview = tree_view
        return sw

    def set_summary(self, text):
        buf = self.summary_textview.get_buffer()
        buf.insert_markup(buf.get_end_iter(), text, -1)

    def build_summary(self):
        vbox = Gtk.VBox()
        description = Gtk.Label.new(_("Corpus summary"))
        description.set_line_wrap(True)
        vbox.pack_start(description, False, False, 0)

        textview = Gtk.TextView()

        textview.set_editable(True)
        textview.set_wrap_mode (Gtk.WrapMode.WORD)
        self.summary_textview = textview
        vbox.pack_start(textview, True, True, 0)

        grid = Gtk.Grid()
        grid.set_column_homogeneous(True)
        return vbox

    def add_page(self, label, widget):
        self.notebook.append_page(widget, Gtk.Label(label=label))
        self.notebook.show_all()

    def build_widget(self):
        mainbox = Gtk.VBox()

        package_count = len(self.packages)
        mainbox.pack_start(Gtk.Label(_(f"Corpus analysis - {package_count} packages")), False, False, 0)

        self.notebook = Gtk.Notebook()
        self.notebook.set_tab_pos(Gtk.PositionType.TOP)

        mainbox.add(self.notebook)
        self.add_page(_("Summary"), self.build_summary())
        self.add_page(_("Annotations"), self.build_annotation_type_table())
        self.add_page(_("Relations"), self.build_relationtype_explorer())

        return mainbox
