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

from gi.repository import GObject
from gi.repository import Gtk

from advene.gui.views import AdhocView

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

    def annotationtypes_liststore(self):
        model = dict(element=GObject.TYPE_PYOBJECT,
                     package_alias=GObject.TYPE_STRING,
                     id=GObject.TYPE_STRING,
                     title=GObject.TYPE_STRING,
                     annotation_count=GObject.TYPE_INT)

        # Store reference to the element (at), source package alias, string representation (title)
        store = Gtk.ListStore(*model.values())

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

        {len(self.packages)} loaded packages :
{packages_info}
        """)

    def build_annotation_type_table(self):
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
        return vbox

    def add_page(self, label, widget):
        self.notebook.append_page(widget, Gtk.Label(label=label))
        self.notebook.show_all()

    def build_widget(self):
        mainbox = Gtk.VBox()

        package_count = len(self.packages)
        mainbox.pack_start(Gtk.Label(_(f"Corpus analysis - {package_count} packages")), False, False, 0)

        self.notebook=Gtk.Notebook()
        self.notebook.set_tab_pos(Gtk.PositionType.TOP)

        mainbox.add(self.notebook)
        self.add_page(_("Summary"), self.build_summary())
        self.add_page(_("Table"), self.build_annotation_type_table())

        return mainbox
