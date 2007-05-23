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

import advene.core.config as config

from advene.model.annotation import Annotation
from advene.gui.views import AdhocView

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.popup

import advene.util.helper as helper

import gtk

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
	self.close_on_package_load = False
        self.contextual_actions = (
            )
        self.controller=controller
        self.elements=elements
        self.options={}

        self.model=self.build_model()
	self.widget = self.build_widget()

    def build_model(self):
        """Build the ListStore containing the data.
        
        """
        l=gtk.ListStore(object, str, str, str, long, long, long, str, str)
        for a in self.elements:
            if isinstance(a, Annotation):
                l.append( (a, 
                           self.controller.get_title(a),
                           self.controller.get_title(a.type),
                           a.id,
                           a.fragment.begin,
                           a.fragment.end,
                           a.fragment.duration,
                           helper.format_time(a.fragment.begin),
                           helper.format_time(a.fragment.end),
                           ) )
        return l

    def build_widget(self):
        tree_view = gtk.TreeView(self.model)

        select = tree_view.get_selection()
        # Set SELECTION_SINGLE to be able to use get_selected()
        select.set_mode(gtk.SELECTION_SINGLE)

        tree_view.connect("button_press_event", self.tree_view_button_cb)
        tree_view.connect("row-activated", self.row_activated_cb)
	#tree_view.set_search_column(COLUMN_CONTENT)

        def search_content(model, column, key, iter):
            if key in model.get_value(iter, COLUMN_CONTENT):
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

        #tree_view.connect("drag_data_get", self.drag_data_get_cb)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	sw.add(tree_view)

	sw.treeview = tree_view

        return sw

    def drag_data_get_cb(self, treeview, context, selection, targetType, timestamp):
        model, iter = treeview.get_selection().get_selected()

        el = model.get_value(iter, COLUMN_ELEMENT)

        if targetType == config.data.target_type['annotation']:
            if not isinstance(el, Annotation):
                return False
            selection.set(selection.target, 8, el.uri)
            return True
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def get_selected_node (self, tree_view):
        """Return the currently selected node.

        None if no node is selected.
        """
        selection = tree_view.get_selection ()
        if not selection:
            return None
        store, it = selection.get_selected()
        node = None
        if it is not None:
            node = tree_view.get_model().get_value (it,
                                                    COLUMN_ELEMENT)
        return node

    def debug_cb (self, *p, **kw):
        print "Debug cb:\n"
        print "Parameters: %s" % str(p)
        print "KW: %s" % str(kw)

    def row_activated_cb(self, widget, path, view_column):
        """Edit the element on Return or double click
        """
        node = self.get_selected_node (widget)
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
            selection.set(selection.target, 8, widget.annotation.uri)
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        #print "drag_received event for %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            print "Creating new relation (%s, %s)" % (source_uri, widget.annotation.uri)
            source=self.controller.package.annotations.get(source_uri)
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
	self.close_on_package_load = False
        self.contextual_actions = (
            )
        self.controller=controller
        self.elements=elements
        self.options={}

        self.model=self.build_model()
	self.widget = self.build_widget()

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

    def build_widget(self):
        tree_view = gtk.TreeView(self.model)

        select = tree_view.get_selection()
        # Set SELECTION_SINGLE to be able to use get_selected()
        select.set_mode(gtk.SELECTION_SINGLE)

        tree_view.connect("button_press_event", self.tree_view_button_cb)
        tree_view.connect("row-activated", self.row_activated_cb)
	#tree_view.set_search_column(COLUMN_CONTENT)

        def search_content(model, column, key, iter):
            if key in model.get_value(iter, COLUMN_CONTENT):
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

    def get_selected_node (self, tree_view):
        """Return the currently selected node.

        None if no node is selected.
        """
        selection = tree_view.get_selection ()
        if not selection:
            return None
        store, it = selection.get_selected()
        node = None
        if it is not None:
            node = tree_view.get_model().get_value (it,
                                                    COLUMN_ELEMENT)
        return node

    def debug_cb (self, *p, **kw):
        print "Debug cb:\n"
        print "Parameters: %s" % str(p)
        print "KW: %s" % str(kw)

    def row_activated_cb(self, widget, path, view_column):
        """Edit the element on Return or double click
        """
        node = self.get_selected_node (widget)
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
