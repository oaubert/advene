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
"""GUI to import package elements.
"""
import logging
logger = logging.getLogger(__name__)

import sys

from gi.repository import Gtk
from gi.repository import GObject

from gettext import gettext as _

import advene.core.config as config

import advene.gui.popup
from advene.gui.util import dialog
import advene.util.helper as helper

class TreeViewImporter:
    COLUMN_ELEMENT=0
    COLUMN_LABEL=1
    COLUMN_ID=2
    COLUMN_IMPORTED=3
    COLUMN_URI=4

    types_mapping={
        'view': 'views',
        'schema': 'schemas',
        'annotation-type': 'annotationTypes',
        'relation-type': 'relationTypes',
        'annotation': 'annotations',
        'relation': 'relations',
        'query': 'queries',
        }

    def __init__(self, controller=None):
        self.controller=controller
        self.widget=self.build_widget()

    def get_selected_node (self, treeview):
        """Return the currently selected node.

        None if no node is selected.
        """
        selection = treeview.get_selection ()
        if not selection:
            return None
        store, it = selection.get_selected()
        node = None
        if it is not None:
            node = treeview.get_model().get_value (it,
                                                   TreeViewImporter.COLUMN_ELEMENT)
        return node

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)

        if button == 3:
            if event.get_window() is widget.get_bin_window():
                model = widget.get_model()
                t = widget.get_path_at_pos(x, y)
                if t is not None:
                    path, col, cx, cy = t
                    node=model[path][self.COLUMN_ELEMENT]
                    widget.get_selection().select_path (path)
                    menu = advene.gui.popup.Menu(node, controller=self.controller)
                    menu.popup()
                    retval = True
        return retval

    def row_activated_cb(self, widget, path, view_column):
        """Edit the element on Return or double click
        """
        node = self.get_selected_node (widget)
        if node is not None:
            try:
                pop = advene.gui.edit.elements.get_edit_popup (node,
                                                               controller=self.controller,
                                                               editable=False)
            except TypeError:
                pass
            else:
                pop.edit ()
            return True
        return False

    def is_imported(self, el):
        """Check wether the element is imported in the controller's package."""
        source=None
        try:
            at=self.types_mapping[el.viewableClass]
            source=getattr(self.controller.package, at)
        except AttributeError:
            logger.error("Exception on %s", el.id, exc_info=True)
            return False
        l=[ e.uri for e in source if e.isImported() ]
        return (el.uri in l)

    def add_package(self, store, package=None, alias=None):
        """Add a package to the liststore.
        """
        p=package
        packagerow=store.append(parent=None,
                                row=[p,
                                     p.title,
                                     alias,
                                     True,
                                     p.uri])
        viewsrow=store.append(parent=packagerow,
                              row=[p.views,
                                   _('Views'),
                                   _('Views'),
                                   False,
                                   'list'])
        for v in p.views:
            store.append(parent=viewsrow,
                         row=[v,
                              v.title or v.id,
                              v.id,
                              self.is_imported(v),
                              v.uri])

        schemasrow=store.append(parent=packagerow,
                                row=[p.schemas,
                                     _('Schemas'),
                                     _('Schemas'),
                                     False,
                                     'list'])
        for s in p.schemas:
            srow=store.append(parent=schemasrow,
                              row=[s,
                                   s.title or s.id,
                                   s.id,
                                   self.is_imported(s),
                                   s.uri])
            for at in s.annotationTypes:
                atrow=store.append(parent=srow,
                                   row=[at,
                                        at.title or at.id,
                                        at.id,
                                        self.is_imported(at),
                                        at.uri])
                # Does not work because the model does not
                # grasp at.annotations for an importer package.
                # for a in at.annotations:
                #     print a.id
                #     store.append(parent=atrow,
                #                    row=[a,
                #                         self.controller.get_title(a),
                #                         a.id,
                #                         self.is_imported(a),
                #                         a.uri])
            for rt in s.relationTypes:
                store.append(parent=srow,
                             row=[rt,
                                  rt.title or rt.id,
                                  rt.id,
                                  self.is_imported(rt),
                                  rt.uri])

        annotationsrow=store.append(parent=packagerow,
                                    row=[p.annotations,
                                         _('Annotations'),
                                   _('Annotations'),
                                   False,
                                   'list'])
        for a in p.annotations:
            store.append(parent=annotationsrow,
                         row=[a,
                              self.controller.get_title(a),
                              a.id,
                              self.is_imported(a),
                              a.uri])

        relationsrow=store.append(parent=packagerow,
                                  row=[p.relations,
                                     _('Relations'),
                                     _('Relations'),
                                   False,
                                   'list'])
        for r in p.relations:
            store.append(parent=relationsrow,
                         row=[r,
                              self.controller.get_title(r),
                              r.id,
                              self.is_imported(r),
                              r.uri])

        queriesrow=store.append(parent=packagerow,
                                row=[p.queries,
                                     _('Queries'),
                                     _('Queries'),
                                   False,
                                   'list'])
        for q in p.queries:
            store.append(parent=queriesrow,
                         row=[q,
                              self.controller.get_title(q),
                              q.id,
                              self.is_imported(q),
                              q.uri])

        return

    def build_liststore(self):
        # Store reference to the element, string representation (title and id)
        # and boolean indicating wether it is imported or not
        store=Gtk.TreeStore(
            GObject.TYPE_PYOBJECT,
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_STRING,
            )

        for i in self.controller.package.imports:
            self.add_package(store, package=i.package, alias=i.getAlias())
        return store

    def toggled_cb(self, renderer, path, model, column):
        # Update the display
        model[path][column] = not model[path][column]

        element=model[path][self.COLUMN_ELEMENT]
        if model[path][column]:
            # If True, it means that it was previously False and that
            # we want to import the element
            logger.info("Importing %s", model[path][self.COLUMN_LABEL])
            # Depends on the type
            if hasattr(element, 'viewableClass'):
                if element.viewableClass == 'list':
                    # The user selected a whole category.
                    for e in element:
                        if not self.is_imported(e):
                            helper.import_element(self.controller.package,
                                                  e,
                                                  self.controller)
                    for c in model[path].iterchildren():
                        c[self.COLUMN_IMPORTED] = True
                elif element.viewableClass == 'schema':
                    helper.import_element(self.controller.package,
                                          element,
                                          self.controller)
                    # The user selected a schema, it automatically
                    # imports its types
                    for c in model[path].iterchildren():
                        c[self.COLUMN_IMPORTED] = True
                elif element.viewableClass in ('annotation-type',
                                               'relation-type'):
                    # We should import the parent schema
                    logger.warn("Annotation types and relation types are not directly importable.\nImport their schema instead.")
                else:
                    helper.import_element(self.controller.package,
                                          element,
                                          self.controller)
            else:
                # Unimport the element
                # FIXME: does not seem to work yet
                if self.is_imported(element):
                    # It was previously imported. Unimport it
                    logger.warn("Removing %s", model[path][self.COLUMN_LABEL])
                    helper.unimport_element(self.controller.package,
                                            element,
                                            self.controller)
                    if element.viewableClass == 'schema':
                        # The user selected a schema,
                        # show the types as non-imported
                        for c in model[path].iterchildren():
                            c[self.COLUMN_IMPORTED] = False
                elif element.viewableClass == 'list':
                    # The user selected a whole category.
                    for e in element:
                        if self.is_imported(e):
                            helper.unimport_element(self.controller.package,
                                                    e,
                                                    self.controller)
                    for c in model[path].iterchildren():
                        c[self.COLUMN_IMPORTED] = False
                elif element.viewableClass in ('annotation-type',
                                               'relation-type'):
                    # We should import the parent schema
                    logger.warn("Annotation types and relation types are not directly importable.\nImport their schema instead.")
                else:
                    # Package
                    logger.warn("Whole package import not implement yet - FIXME")
        return False

    def build_widget(self):
        vbox=Gtk.VBox()

        # FIXME: implement package removal from the list
        self.store=self.build_liststore()

        treeview=Gtk.TreeView(model=self.store)
        treeview.connect('button-press-event', self.tree_view_button_cb)
        treeview.connect('row-activated', self.row_activated_cb)

        renderer = Gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        renderer.connect('toggled', self.toggled_cb, self.store, self.COLUMN_IMPORTED)

        column = Gtk.TreeViewColumn(_('Imported?'), renderer,
                                    active=self.COLUMN_IMPORTED)
        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Id'), renderer,
                                    text=self.COLUMN_ID)
        column.set_resizable(True)
        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Title'), renderer,
                                    text=self.COLUMN_LABEL)
        column.set_resizable(True)
        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('URI'), renderer,
                                    text=self.COLUMN_URI)
        column.set_resizable(True)
        treeview.append_column(column)


        vbox.add(treeview)
        vbox.show_all()

        return vbox

class Importer:
    def __init__(self, controller=None, sourcepackage=None):
        self.controller=controller
        self.sourcepackage=sourcepackage
        self.widget=self.build_widget()

    def add_package(self, button=None):
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None
        filename, alias=dialog.get_filename(title=_("Choose the package to import, and its alias"),
                                                     action=Gtk.FileChooserAction.OPEN,
                                                     button=Gtk.STOCK_OPEN,
                                                     default_dir=d,
                                                     alias=True,
                                                     filter='advene')
        if not filename:
            return True

        # p = advene.model.package.Package(uri=file_, importer=self.controller.package)
        i = advene.model.package.Import(parent=self.controller.package,
                                        uri=filename)
        i.setAlias(alias)
        self.controller.package.imports.append(i)

        # Update the ListStore
        self.ti.add_package(self.ti.store, package=i.package, alias=alias)

        return True

    def build_widget(self):
        vbox=Gtk.VBox()

        vbox.pack_start(Gtk.Label("Elements imported into %s" % self.controller.package.title), False, False, 0)

        scroll_win = Gtk.ScrolledWindow ()
        scroll_win.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.add(scroll_win)

        self.ti=TreeViewImporter(controller=self.controller)
        scroll_win.add_with_viewport(self.ti.widget)

        hb=Gtk.HButtonBox()

        b=Gtk.Button(stock=Gtk.STOCK_ADD)
        b.connect('clicked', self.add_package)
        hb.pack_start(b, False, True, 0)

        vbox.pack_start(hb, False, True, 0)

        hb.show_all()

        return vbox

    def popup(self):
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        window.set_title (_("Package %s") % (self.controller.package.title or _("No title")))
        vbox = Gtk.VBox()
        window.add (vbox)

        vbox.add (self.widget)
        if self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect('destroy', self.controller.gui.close_view_cb, window, self)

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'importeditor')
            window.set_icon_list(self.controller.gui.get_icon_list())

        self.buttonbox = Gtk.HButtonBox()

        b = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        b.connect('clicked', lambda w: window.destroy ())
        self.buttonbox.add (b)

        vbox.pack_start(self.buttonbox, False, True, 0)

        window.show_all()

        return window


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) < 2:
        logger.error("Should provide a package name")
        sys.exit(1)

    class DummyController:
        pass

    from advene.model.package import Package

    controller=DummyController()

    controller.package = Package (uri=sys.argv[1])
    controller.gui=None

    i=Importer(controller=controller)
    window=i.popup()

    window.connect('destroy', lambda e: Gtk.main_quit())

    Gtk.main ()

