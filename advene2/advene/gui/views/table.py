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
import gtk
import csv

from gettext import gettext as _

import advene.core.config as config

from advene.model.cam.annotation import Annotation
from advene.gui.views import AdhocView

import advene.gui.edit.elements
import advene.gui.popup

import advene.util.helper as helper
from advene.gui.util import dialog

COLUMN_ELEMENT=0
COLUMN_CONTENT=1
COLUMN_TYPE=2
COLUMN_ID=3
COLUMN_BEGIN=4
COLUMN_END=5
COLUMN_DURATION=6
COLUMN_BEGIN_FORMATTED=7
COLUMN_END_FORMATTED=8

name="Element tabular view plugin"

def register(controller):
    controller.register_viewclass(AnnotationTable)
    controller.register_viewclass(GenericTable)

class AnnotationTable(AdhocView):
    view_name = _("Annotation table view")
    view_id = 'table'
    tooltip=_("Display annotations in a table")

    def __init__(self, controller=None, parameters=None, elements=None):
        super(AnnotationTable, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            )
        self.controller=controller
        self.elements=elements
        self.options={}

        self.model=self.build_model()
        self.widget = self.build_widget()

    def get_elements(self):
        """Return the list of elements in their displayed order.

        If a selection is active, return only selected elements.
        """
        selection = self.widget.treeview.get_selection ()
        r=selection.count_selected_rows()
        if r == 0 or r == 1:
            selection.select_all()
        store, paths=selection.get_selected_rows()
        return [ store.get_value (store.get_iter(p), COLUMN_ELEMENT) for p in paths ]

    def build_model(self):
        """Build the ListStore containing the data.

        """
        l=gtk.ListStore(object, str, str, str, long, long, long, str, str)
        if not self.elements:
            return l
        for a in self.elements:
            if isinstance(a, Annotation):
                l.append( (a,
                           self.controller.get_title(a),
                           self.controller.get_title(a.type),
                           a.id,
                           a.begin,
                           a.end,
                           a.duration,
                           helper.format_time(a.begin),
                           helper.format_time(a.end),
                           ) )
        return l

    def build_widget(self):
        tree_view = gtk.TreeView(self.model)

        select = tree_view.get_selection()
        select.set_mode(gtk.SELECTION_MULTIPLE)

        tree_view.connect('button-press-event', self.tree_view_button_cb)
        tree_view.connect('row-activated', self.row_activated_cb)
        #tree_view.set_search_column(COLUMN_CONTENT)

        def search_content(model, column, key, it):
            if key in model.get_value(it, COLUMN_CONTENT):
                return False
            return True

        tree_view.set_search_equal_func(search_content)

        columns={}
        for (name, label, col) in (
            ('content', _("Content"), COLUMN_CONTENT),
            ('type', _("Type"), COLUMN_TYPE),
            ('begin', _("Begin"), COLUMN_BEGIN_FORMATTED),
            ('end', _("End"), COLUMN_END_FORMATTED),
            ('duration', _("Duration"), COLUMN_DURATION),
            ('id', _("Id"), COLUMN_ID) ):
            columns[name]=gtk.TreeViewColumn(label, gtk.CellRendererText(), text=col)
            columns[name].set_reorderable(True)
            columns[name].set_sort_column_id(col)
            tree_view.append_column(columns[name])

        # Column-specific settings
        columns['begin'].set_sort_column_id(COLUMN_BEGIN)
        columns['end'].set_sort_column_id(COLUMN_END)
        self.model.set_sort_column_id(COLUMN_BEGIN, gtk.SORT_ASCENDING)

        # Resizable columns: content, type
        for name in ('content', 'type'):
            columns[name].set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            columns[name].set_resizable(True)
            columns[name].set_min_width(40)
        columns['content'].set_expand(True)

        # Drag and drop for annotations
        tree_view.drag_source_set(gtk.gdk.BUTTON1_MASK,
                                  config.data.drag_type['annotation']
                                  + config.data.drag_type['text-plain']
                                  + config.data.drag_type['TEXT']
                                  + config.data.drag_type['STRING']
                                  ,
                                  gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)

        #tree_view.connect('drag-data-get', self.drag_data_get_cb)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(tree_view)

        sw.treeview = tree_view

        return sw

    def drag_data_get_cb(self, treeview, context, selection, targetType, timestamp):
        model, it = treeview.get_selection().get_selected()

        el = model.get_value(it, COLUMN_ELEMENT)

        if targetType == config.data.target_type['annotation']:
            # FIXME: handle multiple selection
            if not isinstance(el, Annotation):
                return False
            selection.set(selection.target, 8, el.uriref.encode('utf8'))
            return True
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def get_selected_nodes (self):
        """Return the currently selected node.

        None if no node is selected or multiple nodes are selected.
        """
        selection = self.widget.treeview.get_selection ()
        store, paths=selection.get_selected_rows()
        return [ store.get_value (store.get_iter(p), COLUMN_ELEMENT) for p in paths ]

    def debug_cb (self, *p, **kw):
        print "Debug cb:\n"
        print "Parameters: %s" % str(p)
        print "KW: %s" % str(kw)

    def csv_export(self, name=None):
        if name is None:
            name=dialog.get_filename(title=_("Export data to file..."),
                                              default_file="advene_data.csv",
                                              action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                              button=gtk.STOCK_SAVE)
        if name is None:
            return True
        try:
            f=open(name, 'w')
        except IOError, e:
            dialog.message_dialog(label=_("Error while exporting data to %(filename)s: %(error)s"
                                          % {
                        'filename': name,
                        'error': unicode(e),
                        }), icon=gtk.MESSAGE_ERROR)
        w=csv.writer(f)
        tv=self.widget.treeview
        store, paths=tv.get_selection().get_selected_rows()
        source=[ store.get_iter(p) for p in paths ]
        if not source:
            source=tv.get_model()
        w.writerow( (_("id"), _("type"), _("begin"), _("end"), _("content")) )
        for r in source:
            w.writerow( (r[COLUMN_ID], unicode(r[COLUMN_TYPE]).encode('utf-8'), r[COLUMN_BEGIN], r[COLUMN_END], unicode(r[COLUMN_ELEMENT].content.data).encode('utf-8') ) )
        f.close()
        self.log(_("Data exported to %s") % name)

    def row_activated_cb(self, widget, path, view_column):
        """Edit the element on Return or double click
        """
        nodes = self.get_selected_nodes ()
        if len(nodes) != 1:
            return True
        node=nodes[0]
        if node is not None:
            self.controller.gui.edit_element(node)
            return True
        return False

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)

        if button == 3 or button == 2:
            if event.window is widget.get_bin_window():
                model = self.model
                t = widget.get_path_at_pos(x, y)
                if t is not None:
                    path, col, cx, cy = t
                    it = model.get_iter(path)
                    node = model.get_value(it,
                                           COLUMN_ELEMENT)
                    widget.get_selection().select_path (path)
                    if button == 3:
                        menu = advene.gui.popup.Menu(node, controller=self.controller)
                        menu.popup()
                        retval = True
                    elif button == 2:
                        # Expand all children
                        widget.expand_row(path, True)
                        retval=True
        return retval

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        #print "drag_sent event from %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            selection.set(selection.target, 8, widget.annotation.uriref.encode('utf8'))
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        #print "drag_received event for %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            source=self.controller.package.get(unicode(selection.data, 'utf8').split('\n')[0])
            dest=widget.annotation
            self.create_relation_popup(source, dest)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

class GenericTable(AdhocView):
    view_name = _("Generic table view")
    view_id = 'generictable'
    tooltip=_("Display Advene elements in a table.")

    def __init__(self, controller=None, parameters=None, elements=None):
        super(GenericTable, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            )
        self.controller=controller
        self.elements=elements
        self.options={}

        self.model=self.build_model()
        self.widget = self.build_widget()

    def get_elements(self):
        """Return the list of elements in their displayed order.

        If a selection is active, return only selected elements.
        """
        selection = self.widget.treeview.get_selection ()
        r=selection.count_selected_rows()
        if r == 0 or r == 1:
            selection.select_all()
        store, paths=selection.get_selected_rows()
        return [ store.get_value (store.get_iter(p), COLUMN_ELEMENT) for p in paths ]

    def build_model(self):
        """Build the ListStore containing the data.

        Columns: element, content (title), type, id
        """
        l=gtk.ListStore(object, str, str, str)
        for e in self.elements:
            l.append( (e,
                       self.controller.get_title(e),
                       helper.get_type(e),
                       e.id) )
        return l

    def csv_export(self, name=None):
        if name is None:
            name=dialog.get_filename(title=_("Export data to file..."),
                                              default_file="advene_data.csv",
                                              action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                              button=gtk.STOCK_SAVE)
        if name is None:
            return True
        try:
            f=open(name, 'w')
        except IOError, e:
            dialog.message_dialog(label=_("Error while exporting data to %(filename)s: %(error)s"
                                          % {
                        'filename': name,
                        'error': unicode(e),
                        }),
                                  icon=gtk.MESSAGE_ERROR)
        w=csv.writer(f)
        tv=self.widget.treeview
        store, paths=tv.get_selection().get_selected_rows()
        source=[ store.get_iter(p) for p in paths ]
        if not source:
            source=tv.get_model()
        w.writerow( (_("Element title"), _("Element type"), _("Element id")) )
        for r in source:
            w.writerow( (unicode(r[COLUMN_CONTENT]).encode('utf-8'), unicode(r[COLUMN_TYPE]).encode('utf-8'), r[COLUMN_ID]) )
        f.close()
        self.log(_("Data exported to %s") % name)

    def build_widget(self):
        tree_view = gtk.TreeView(self.model)

        select = tree_view.get_selection()
        select.set_mode(gtk.SELECTION_MULTIPLE)

        tree_view.connect('button-press-event', self.tree_view_button_cb)
        tree_view.connect('row-activated', self.row_activated_cb)
        #tree_view.set_search_column(COLUMN_CONTENT)

        def search_content(model, column, key, it):
            if key in model.get_value(it, COLUMN_CONTENT):
                return False
            return True

        tree_view.set_search_equal_func(search_content)

        columns={}
        for (name, label, col) in (
            ('title', _("Title"), COLUMN_CONTENT),
            ('type', _("Type"), COLUMN_TYPE),
            ('id', _("Id"), COLUMN_ID) ):
            columns[name]=gtk.TreeViewColumn(label, gtk.CellRendererText(), text=col)
            columns[name].set_reorderable(True)
            columns[name].set_sort_column_id(col)
            tree_view.append_column(columns[name])

        self.model.set_sort_column_id(COLUMN_CONTENT, gtk.SORT_ASCENDING)

        # Resizable columns: title, type
        for name in ('title', 'type'):
            columns[name].set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
            columns[name].set_resizable(True)
            columns[name].set_min_width(40)
        columns['title'].set_expand(True)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(tree_view)

        sw.treeview = tree_view

        return sw

    def get_selected_nodes (self):
        """Return the currently selected node.

        None if no node is selected or multiple nodes are selected.
        """
        selection = self.widget.treeview.get_selection ()
        store, paths=selection.get_selected_rows()
        return [ store.get_value (store.get_iter(p), COLUMN_ELEMENT) for p in paths ]

    def debug_cb (self, *p, **kw):
        print "Debug cb:\n"
        print "Parameters: %s" % str(p)
        print "KW: %s" % str(kw)

    def row_activated_cb(self, widget, path, view_column):
        """Edit the element on Return or double click
        """
        nodes = self.get_selected_nodes ()
        if len(nodes) != 1:
            return True
        if nodes[0] is not None:
            self.controller.gui.edit_element(nodes[0])
            return True
        return False

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)

        if button == 3 or button == 2:
            if event.window is widget.get_bin_window():
                model = self.model
                t = widget.get_path_at_pos(x, y)
                if t is not None:
                    path, col, cx, cy = t
                    it = model.get_iter(path)
                    node = model.get_value(it,
                                           COLUMN_ELEMENT)
                    widget.get_selection().select_path (path)
                    if button == 3:
                        menu = advene.gui.popup.Menu(node, controller=self.controller)
                        menu.popup()
                        retval = True
                    elif button == 2:
                        # Expand all children
                        widget.expand_row(path, True)
                        retval=True
        return retval
