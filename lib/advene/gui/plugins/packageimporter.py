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
"""GUI to import packages.

It focuses on importing whole sets of elements: either views,
resources, or whole annotations (with their types) without
overwriting/merging with existing elements.

A common usage scenario is to be able to compare annotations for the
same document but edited by 2 persons using the same schema, by
importing annotations from User2, suffixing his annotation types with
his name.
"""
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango

from advene.gui.util import dialog
from advene.gui.views import AdhocView
from advene.util.merger import Differ

name="Package importer view plugin"

def register(controller):
    controller.register_viewclass(PackageImporter)

class TreeViewImporter:
    COLUMN_ELEMENT=0
    COLUMN_APPLY=1
    COLUMN_ELEMENT_NAME=2

    def __init__(self, controller=None, sourcepackage=None, destpackage=None):
        self.controller = controller
        self.package = sourcepackage
        self.destpackage = destpackage
        self.store = self.build_liststore()
        self.widget = self.build_widget()

    def build_liststore(self):
        # Store reference to the element, string representation (title and id)
        # and boolean indicating wether it is imported or not
        store = Gtk.ListStore(
            GObject.TYPE_PYOBJECT,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_STRING,
            )

        for at in self.package.annotationTypes:
            store.append(row=[ at,
                               True,
                               "%s (%d)" % (self.controller.get_title(at),
                                            len(at.annotations))
            ])
        return store

    def toggle_selection(self):
        """Toggle all elements from the current selection.
        """
        def toggle_row(model, path, iter, data=None):
            model.set_value(iter, self.COLUMN_APPLY, not model.get_value(iter, self.COLUMN_APPLY))
        self.widget.get_selection().selected_foreach(toggle_row)
        return True

    def build_widget(self):
        treeview = Gtk.TreeView(model=self.store)
        treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        treeview.set_headers_clickable(True)
        treeview.set_enable_search(False)

        renderer = Gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        column = Gtk.TreeViewColumn(_('Import?'), renderer,
                                    active=self.COLUMN_APPLY)
        column.set_sort_column_id(self.COLUMN_APPLY)

        def toggled_cb(renderer, path, model, column):
            model[path][column] = not model[path][column]
            return True
        renderer.connect('toggled', toggled_cb, self.store, self.COLUMN_APPLY)

        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Element'), renderer,
                                    text=self.COLUMN_ELEMENT_NAME)
        column.set_resizable(True)
        column.set_max_width(300)
        column.set_sort_column_id(self.COLUMN_ELEMENT_NAME)
        treeview.append_column(column)

        return treeview

class PackageImporter(AdhocView):
    view_name = _("Package importer view")
    view_id = 'packageimporter'
    tooltip=_("Display package import interface")

    def __init__(self, controller=None, parameters=None, sourcepackage=None, destpackage=None):
        super().__init__(controller=controller)
        self.close_on_package_load = True
        self.contextual_actions = ()
        self.controller=controller
        opt, arg = self.load_parameters(parameters)

        self.sourcepackage=sourcepackage
        self.destpackage=destpackage
        self.widget=self.build_widget()

    def build_widget(self):
        self.mergerview = TreeViewImporter(controller=self.controller, sourcepackage=self.sourcepackage, destpackage=self.destpackage)

        vbox=Gtk.VBox()



        label = Gtk.Label(_("Import annotations from %(source)s into %(dest)s") % {'source': self.sourcepackage.uri,
                                                                                   'dest': self.destpackage.uri})
        label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        vbox.pack_start(label, False, False, 0)

        hbox = Gtk.HBox()
        self.suffix_entry = Gtk.Entry()
        self.suffix_entry.set_text("IMPORTED")
        hbox.pack_start(Gtk.Label(_("Suffix to append to created types")), False, False, 0)
        hbox.pack_start(self.suffix_entry, True, True, 0)
        vbox.pack_start(hbox, False, False, 0)

        scroll_win = Gtk.ScrolledWindow ()
        scroll_win.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.add(scroll_win)

        scroll_win.add(self.mergerview.widget)

        self.buttonbox = Gtk.HButtonBox()

        def validate(b):
            m = self.mergerview.store
            suffix = self.suffix_entry.get_text().strip()
            if not suffix:
                dialog.message_dialog(_("The suffix cannot be empty."), icon=Gtk.MessageType.ERROR)
                return True

            annotation_count = 0
            type_count = 0
            # Let's use differ methods to copy elements
            differ = Differ(source=self.sourcepackage, destination=self.destpackage, controller=self.controller)
            batch_id=object()
            for l in m:
                if l[self.mergerview.COLUMN_APPLY]:
                    source_at = l[self.mergerview.COLUMN_ELEMENT]
                    logger.debug("Copying %s (%d annotations)", source_at.title, len(source_at.annotations))
                    type_count += 1
                    dest_at = differ.copy_annotation_type(source_at, generate_id=True)
                    dest_at.title = "%s %s" % (dest_at.title, suffix)
                    self.controller.notify('AnnotationTypeCreate', annotationtype=dest_at, immediate=True, batch=batch_id)
                    for a in source_at.annotations:
                        annotation_count += 1
                        # Since we copied the annotation type before, copy_annotation should use the translated name
                        new_a = differ.copy_annotation(a, generate_id=True)
                        self.controller.notify('AnnotationCreate', annotation=new_a, immediate=True, batch=batch_id)
            logger.info(_("Copied %d annotations from %d types"), annotation_count, type_count)
            self.close()
            return True

        def select_all(b):
            model=self.mergerview.store
            for l in model:
                l[self.mergerview.COLUMN_APPLY] = True
            return True

        def unselect_all(b):
            model=self.mergerview.store
            for l in model:
                l[self.mergerview.COLUMN_APPLY] = False
            return True

        def toggle_selection(b):
            self.mergerview.toggle_selection()
            return True

        b = Gtk.Button(_("All"))
        b.connect('clicked', select_all)
        self.buttonbox.add (b)

        b = Gtk.Button(_('None'))
        b.connect('clicked', unselect_all)
        self.buttonbox.add (b)

        b = Gtk.Button(_('Selection'))
        b.connect('clicked', toggle_selection)
        self.buttonbox.add (b)

        b = Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', validate)
        self.buttonbox.add (b)

        b = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b.connect('clicked', lambda b: self.close())
        self.buttonbox.add (b)

        vbox.pack_start(self.buttonbox, False, True, 0)

        return vbox
