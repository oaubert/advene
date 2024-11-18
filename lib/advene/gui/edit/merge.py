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
"""GUI to merge packages.
"""
import logging
logger = logging.getLogger(__name__)

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GObject
import difflib
from gi.repository import Pango

from gettext import gettext as _

import advene.core.config as config

import advene.gui.popup
from advene.gui.views import AdhocView

from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.view import View
from advene.model.query import Query
import advene.util.helper as helper
from advene.util.merger import Differ

labels = {
    'new': _("Create element"),
    'new_annotation': _("Create annotation (duplicate id)"),
    'new_relation': _("Create relation (duplicate id)"),
    'update_meta_color': _("Update the color"),
    'update_meta_representation': _("Update the representation"),
    'update_meta_description': _("Update the description"),
    'update_title': _("Update the title"),
    'update_mimetype': _("Update the mimetype"),
    'update_begin': _("Update the begin time"),
    'update_end': _("Update the end time"),
    'update_content': _("Update the content"),
    'update_matchfilter': _("Update the matchFilter"),
    'update_member_types': _("Update the member types"),
    'update_tags': _("Update tags"),
}

class TreeViewMerger:
    COLUMN_ELEMENT = 0
    COLUMN_ACTION = 1
    COLUMN_ELEMENT_NAME = 2
    COLUMN_APPLY = 3
    COLUMN_ELEMENT_TYPE = 4

    def __init__(self, controller=None, differ=None):
        self.controller = controller
        self.differ = differ
        self.diff_textview = None
        self.store = self.build_liststore()
        self.widget = self.build_widget()

    def set_diff_textview(self, tv):
        self.diff_textview = tv
        buf = tv.get_buffer()
        self.minustag = buf.create_tag("minus", background="lightsalmon")
        self.plustag = buf.create_tag("plus", background="palegreen1")

    def build_liststore(self):
        # Store reference to the element, string representation (title and id)
        # and boolean indicating wether it is imported or not
        store = Gtk.ListStore(
            GObject.TYPE_PYOBJECT,
            GObject.TYPE_STRING,
            GObject.TYPE_STRING,
            GObject.TYPE_BOOLEAN,
            GObject.TYPE_STRING,
            )

        for line in self.differ.diff():
            name, s, d, action, value = line
            # Note: s and d are normally Advene elements, except for
            # resources for which we have the path.
            store.append(row=[ line,
                               labels.setdefault(name, name),
                               "%s %s (%s)" % (helper.get_type(s),
                                               self.controller.get_title(s),
                                               getattr(s, 'id', str(s))),
                               True,
                               self.controller.get_title(s.type) if hasattr(s, 'type') else helper.get_type(s) ])
        return store

    def toggle_selection(self):
        """Toggle all elements from the current selection.
        """
        def toggle_row(model, path, it, data=None):
            model.set_value(it, self.COLUMN_APPLY, not model.get_value(it, self.COLUMN_APPLY))
        self.widget.get_selection().selected_foreach(toggle_row)
        return True

    def build_widget(self):
        def show_diff(item, difftuple):
            name, s, d, action, value = difftuple

            diff = difflib.Differ()
            b = self.diff_textview.get_buffer()
            b.delete(*b.get_bounds())

            for line in diff.compare((value(d) or "").splitlines(1),
                                  (value(s) or "").splitlines(1)):
                if line.startswith('-'):
                    b.insert_with_tags(b.get_iter_at_mark(b.get_insert()), line, self.minustag)
                elif line.startswith('+'):
                    b.insert_with_tags(b.get_iter_at_mark(b.get_insert()), line, self.plustag)
                else:
                    b.insert_at_cursor(line)
            return True

        def build_popup_menu(difftuple):
            menu = Gtk.Menu()

            name, s, d, action, value = difftuple

            if name != 'new':
                i = Gtk.MenuItem(_("Current element"))
                m = advene.gui.popup.Menu(d, controller=self.controller, readonly=False)
                i.set_submenu(m.menu)
                menu.append(i)

            i = Gtk.MenuItem(_("Updated element"))
            m = advene.gui.popup.Menu(s, controller=self.controller, readonly=True)
            i.set_submenu(m.menu)
            menu.append(i)

            i = Gtk.MenuItem(_("Show diff"))
            i.connect('activate', show_diff, difftuple)
            menu.append(i)

            if config.data.preferences['expert-mode']:
                i = Gtk.MenuItem(_("Show _Evaluator"))
                i.connect('activate', lambda e: self.controller.gui.popup_evaluator(localsdict={
                    'name': name,
                    's': s,
                    'd': d,
                    'action': action,
                    'value': value
                }))
                menu.append(i)

            menu.show_all()
            return menu

        def tree_view_button_cb(widget=None, event=None):
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
                        it = model.get_iter(path)
                        node = model.get_value(it, self.COLUMN_ELEMENT)
                        widget.get_selection().select_path (path)
                        menu = build_popup_menu(node)
                        menu.popup_at_pointer(None)
                        retval = True
            return retval

        def key_pressed(widget, event):
            if event.keyval == Gdk.KEY_space:
                self.toggle_selection()
                return True
            return False

        treeview = Gtk.TreeView(model=self.store)
        treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
        treeview.set_headers_clickable(True)
        treeview.set_enable_search(False)
        treeview.connect('button-press-event', tree_view_button_cb)
        def row_activated(treeview, path, column):
            model = treeview.get_model()
            element = model.get_value(model.get_iter(path), self.COLUMN_ELEMENT)
            show_diff(element, element)
            return True
        treeview.connect('row-activated', row_activated)
        treeview.connect('key-press-event', key_pressed)

        renderer = Gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        column = Gtk.TreeViewColumn(_('Merge?'), renderer,
                                    active=self.COLUMN_APPLY)
        column.set_sort_column_id(self.COLUMN_APPLY)

        def toggled_cb(renderer, path, model, column):
            model[path][column] = not model[path][column]
            return True
        renderer.connect('toggled', toggled_cb, self.store, self.COLUMN_APPLY)

        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Action'), renderer,
                                    text=self.COLUMN_ACTION)
        column.set_resizable(True)
        column.set_sort_column_id(self.COLUMN_ACTION)
        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Element'), renderer,
                                    text=self.COLUMN_ELEMENT_NAME)
        column.set_resizable(True)
        column.set_max_width(300)
        column.set_sort_column_id(self.COLUMN_ELEMENT_NAME)
        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Type'), renderer,
                                    text=self.COLUMN_ELEMENT_TYPE)
        column.set_resizable(True)
        column.set_sort_column_id(self.COLUMN_ELEMENT_TYPE)
        treeview.append_column(column)

        return treeview

class MergerView(AdhocView):
    view_name = _("Package merger")
    view_id = "package_merger"

    def __init__(self, controller=None, parameters=None, sourcepackage=None, destpackage=None):
        super().__init__(controller=controller)
        self.controller = controller
        self.parameters = parameters
        opt, arg = self.load_parameters(parameters)
        self.close_on_package_load = False
        self.contextual_actions = ()
        self.options = {
            }
        self.sourcepackage = sourcepackage
        self.destpackage = destpackage
        self.differ = Differ(sourcepackage, destpackage, self.controller)
        self.widget = self.build_widget()

    def build_widget(self):
        vbox = Gtk.VBox()

        vbox.pack_start(Gtk.Label(_("Merge elements from %(source)s into %(dest)s") % {'source': self.sourcepackage.uri,
                                                                                       'dest': self.destpackage.uri}),
                        False, False, 0)

        def scrolled(widget):
            scroll_win = Gtk.ScrolledWindow ()
            scroll_win.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll_win.add(widget)
            return scroll_win

        self.mergerview = TreeViewMerger(controller=self.controller, differ=self.differ)

        # Textview for displaying diff info
        tv = Gtk.TextView()
        self.mergerview.set_diff_textview(tv)
        tv.set_wrap_mode(Gtk.WrapMode.CHAR)
        f = Pango.FontDescription("courier 12")
        tv.modify_font(f)

        content_paned = Gtk.Paned()
        content_paned.add1(scrolled(self.mergerview.widget))
        content_paned.add2(scrolled(tv))
        vbox.add(content_paned)
        content_paned.set_position(600)

        self.buttonbox = Gtk.HButtonBox()

        def validate(b):
            m = self.mergerview.store
            for row in m:
                if row[self.mergerview.COLUMN_APPLY]:
                    name, s, d, action, value = row[self.mergerview.COLUMN_ELEMENT]
                    action(s, d)
            self.destpackage._modified = True
            self.controller.notify('PackageActivate', package=self.destpackage)
            self.close()
            return True

        def select_all(b):
            model = self.mergerview.store
            for row in model:
                row[self.mergerview.COLUMN_APPLY] = True
            return True

        def unselect_all(b=None):
            model = self.mergerview.store
            for row in model:
                row[self.mergerview.COLUMN_APPLY] = False
            return True

        def is_all_selected():
            # Every element is selected if there is not unselected element
            return not [ row
                         for row in self.mergerview.store
                         if row[self.mergerview.COLUMN_APPLY] is False ]

        def select_structure(b):
            """Select schemas and types
            """
            # If everything is selected, then first unselect all
            if is_all_selected():
                unselect_all()
            for row in self.mergerview.store:
                if isinstance(row[self.mergerview.COLUMN_ELEMENT][1],
                              (Schema, AnnotationType, RelationType)):
                    row[self.mergerview.COLUMN_APPLY] = True
            return True

        def select_views(b):
            """Select views and queries
            """
            # If everything is selected, then first unselect all
            if is_all_selected():
                unselect_all()
            for row in self.mergerview.store:
                if isinstance(row[self.mergerview.COLUMN_ELEMENT][1],
                              (View, Query)):
                    row[self.mergerview.COLUMN_APPLY] = True
            return True

        def toggle_selection(b):
            self.mergerview.toggle_selection()
            return True

        b = Gtk.Button(_("All"))
        b.set_tooltip_text(_("Select all elements"))
        b.connect('clicked', select_all)
        self.buttonbox.add (b)

        b = Gtk.Button(_('None'))
        b.set_tooltip_text(_("Unselect all elements"))
        b.connect('clicked', unselect_all)
        self.buttonbox.add (b)

        b = Gtk.Button(_('Selection'))
        b.set_tooltip_text(_("Toggle the state of selected elements - you can select a range by holding Ctrl or Shift"))
        b.connect('clicked', toggle_selection)
        self.buttonbox.add (b)

        b = Gtk.Button(_("Structure"))
        b.set_tooltip_text(_("Select structure elements (schemas, types)"))
        b.connect('clicked', select_structure)
        self.buttonbox.add(b)

        b = Gtk.Button(_("Views"))
        b.set_tooltip_text(_("Select views"))
        b.connect('clicked', select_views)
        self.buttonbox.add(b)

        b = Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', validate)
        self.buttonbox.add (b)

        b = Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b.connect('clicked', lambda b: self.close())
        self.buttonbox.add (b)

        vbox.pack_start(self.buttonbox, False, True, 0)

        vbox.show_all()

        return vbox
