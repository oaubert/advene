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

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.resources import Resources, ResourceData
from advene.model.query import Query
from advene.model.view import View
from advene.gui.views import AdhocView

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.popup

import advene.util.helper as helper

import gtk
import gobject

class AdveneTreeModel(gtk.GenericTreeModel, gtk.TreeDragSource, gtk.TreeDragDest):
    COLUMN_TITLE=0
    COLUMN_ELEMENT=1

    def nodeParent (self, node):
        raise Exception("This has to be implemented in subclasses.")

    def nodeChildren (self, node):
        raise Exception("This has to be implemented in subclasses.")

    def nodeHasChildren (self, node):
        raise Exception("This has to be implemented in subclasses.")

    def __init__(self, controller=None, package=None):
        gtk.GenericTreeModel.__init__(self)
        self.clear_cache ()
        self.controller=controller
        if package is None and controller is not None:
            package=controller.package
        self.__package=package

    def get_package(self):
        return self.__package

    def clear_cache (self):
        self.childrencache = {}

    def remove_element (self, e):
        """Remove an element from the model.

        The problem is that we do not know its previous path.
        """
        # FIXME: there is still a bug with ImportBundles (that are
	# mutable and thus cannot be dict keys
	print "Removing element ", str(e)

	if isinstance(e, View):
	    # Remove the element from the list view and refresh list view
            parent=self.nodeParent(e)
	    #parent=self.get_package().views
	    path=self.on_get_path(parent)
            print "before row changed"
	    self.row_changed(path, self.get_iter(path))
            print "after row changed"
	    return

	parent=None
	for p in self.childrencache:
	    if e in self.childrencache[p]:
		parent=p
		print "Found parent ", str(parent)
		break
	if parent is None:
	    # Could not find the element in the cache.
	    # It was not yet displayed
	    print "Parent not found"
	else:
	    # We can determine its path
	    path=list(self.on_get_path(parent))
	    path.append(self.childrencache[parent].index(e))
	    path=tuple(path)

	    print "Path: ", str(path)
            self.row_deleted(path)
            del (self.childrencache[parent])
	return True

    def update_element(self, e, created=False):
        """Update an element.

        This is called when a element has been modified or created.
        """
        parent=self.nodeParent(e)
        try:
            del (self.childrencache[parent])
        except KeyError:
            pass
        path=self.on_get_path(e)
        if path is not None:
            if created:
                self.row_inserted(path, self.get_iter(path))
            else:
                self.row_changed(path, self.get_iter(path))
        return

    def on_get_flags(self):
        return 0

    def on_get_n_columns(self):
        return 2

    def on_get_column_type(self, index):
        types=(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        return types[index]

    # FIXME: maybe we could use TALES expressions as path
    def on_get_path(self, node): # FIXME
        # print "on_get_path()"
        # print "node: " + str(node)
        # node is either an Annotation or an AnnotationType
        parent = self.nodeParent (node)
        child = node
        idx = []
        while parent is not None:
            children = self.nodeChildren(parent)
            try:
                i = children.index (child)
            except ValueError:
                # The element is not in the list
                return None
            idx.append (i)
            child = parent
            parent = self.nodeParent(parent)
        idx.append(0)
        idx.reverse()
        return tuple(idx)

    def on_get_iter(self, path):
        """Return the node corresponding to the given path.
        """
        node = self.__package
        for i in xrange(1, len(path)):
            idx = path[i]
            children = self.nodeChildren(node)
            node = children[idx]
        return node

    def on_get_tree_path(self, node):
        return self.on_get_path(node)

    def title (self, node):
        title=None
        if self.controller:
            title=self.controller.get_title(node)
        if not title:
            title = "???"
            try:
                title=node.id
            except AttributeError:
                pass
        # FIXME: bad hardcoded value
        if len(title) > 50:
            title=title[:50]
        if isinstance(node, Annotation):
            title="%s (%s, %s)" % (title,
                                   helper.format_time(node.fragment.begin),
                                   helper.format_time(node.fragment.end))
        if isinstance (node, View):
            if node.content.mimetype == 'application/x-advene-ruleset':
                title += ' [STBV]'
            elif node.content.mimetype == 'application/x-advene-adhoc-view':
                title += ' [AdHoc]'
        if ((hasattr(node, 'isImported') and node.isImported())
            or (hasattr(node, 'schema') and node.schema.isImported())):
            title += " (*)"
        return title

    def on_get_value(self, node, column):
        if column == AdveneTreeModel.COLUMN_TITLE:
            return self.title(node)
        else:
            return node

    def on_iter_next(self, node):
        """Return the next node at this level of the tree"""
        parent = self.nodeParent(node)
        next = None
        if parent is not None:
            children = self.nodeChildren(parent)
            count = len(children)
            idx = None
            for i in xrange(len(children)):
                child = children[i]
                if child is node:
                    idx = i + 1
                    break
            if idx is not None and idx < count:
                next = children[idx]
        return next

    def on_iter_children(self, node):
        """Return the first child of this node"""
        children = self.nodeChildren(node)
        if children is None:
            return children
        else:
            assert len(children), _("No children in on_iter_children()!")
            return children[0]

    def on_iter_has_child(self, node):
        """returns true if this node has children"""
        return self.nodeHasChildren(node)

    def on_iter_n_children(self, node):
        '''returns the number of children of this node'''
        return len(self.nodeChildren(node))

    def on_iter_nth_child(self, node, n):
        """Returns the nth child of this node"""
        child = None
        children = self.nodeChildren(node)
        assert len(children), _("No children in on_iter_nth_child()")
        child = children[n]
        return child

    def on_iter_parent(self, node):
        """Returns the parent of this node"""
        return self.nodeParent(node)

    def row_draggable(self, path):
        print "row draggable %s" % str(path)
        return True
#         node = self.on_get_iter(path)
#         if isinstance(node, Annotation):
#             return True
#         else:
#             return False

    def drag_data_delete(self, path):
        print "drag delete %s" % str(path)
        return False

    def drag_data_received (self, *p, **kw):
        print "drag data received: %s %s" % (str(p), str(kw))
        return True

    def drag_data_get(self, path, selection):
        print "drag data get %s %s" % (str(path), str(selection))
        node = self.on_get_iter(path)
        print "Got selection:\ntype=%s\ntarget=%s" % (str(selection.type),
                                                      str(selection.target))
        selection.set(selection.target, 8, node.uri)
        return True

class VirtualNode:
    """Virtual node.
    """
    def __init__(self, name, package, viewableType=None):
        self.title=name
        self.rootPackage=package
        self.viewableType=viewableType

class DetailedTreeModel(AdveneTreeModel):
    """Detailed Tree Model.

    In this model,
       - Annotations and Relations depend on their types.
       - Types depend on their schema
       - Schemas depend on their package list of schemas
       - Views depend on their package list of views
       - Resources depend on the Resource node
    """
    def __init__(self, controller=None, package=None):
        AdveneTreeModel.__init__(self, controller=controller, package=package)
        self.virtual={}
        self.virtual['views']=VirtualNode(_("List of views"), package, viewableType='view-list')
        self.virtual['static']=VirtualNode(_("Static views"), package, viewableType='view-list')
        self.virtual['dynamic']=VirtualNode(_("Dynamic views"), package, viewableType='view-list')
        self.virtual['adhoc']=VirtualNode(_("Adhoc views"), package)

    def nodeParent (self, node):
        #print "nodeparent %s" % node
        if isinstance (node, Annotation):
            parent = node.type
        elif isinstance (node, Relation):
            parent = node.type
        elif isinstance (node, RelationType):
            parent = node.schema
        elif isinstance (node, AnnotationType):
            parent = node.schema
        elif isinstance (node, Schema):
            parent = node.rootPackage.schemas
        elif isinstance (node, View):
            t=helper.get_view_type(node)
            parent=self.virtual[t]
        elif isinstance (node, Query):
            parent = node.rootPackage.queries
        elif isinstance (node, Package):
            parent = None
        elif isinstance (node, AbstractBundle):
            parent = node.rootPackage
        elif isinstance (node, Resources):
            parent = node.parent
        elif isinstance (node, ResourceData):
            parent = node.parent
        elif node in (self.virtual['static'], self.virtual['dynamic'], self.virtual['adhoc']):
            parent = self.virtual['views']
        elif node == self.virtual['views']:
            parent=node.rootPackage
        else:
            parent = None
        return parent

    def nodeChildren (self, node):
        #print "nodechildren %s" % node
        if isinstance (node, Annotation):
            children = None
        elif isinstance (node, Relation):
            children = None
        elif isinstance (node, AnnotationType):
            if not node in self.childrencache:
                self.childrencache[node] = node.annotations
            children = self.childrencache[node]
        elif isinstance (node, RelationType):
            if not node in self.childrencache:
                self.childrencache[node] = node.relations
            children = self.childrencache[node]
        elif isinstance (node, Schema):
	    # Do not cache these elements
	    l=list(node.annotationTypes)
	    l.extend(node.relationTypes)
            children = l
        elif isinstance (node, View):
            children = None
        elif isinstance (node, Query):
            children = None
        elif isinstance (node, Package):
            if not node in self.childrencache:
                self.childrencache[node] = [node.schemas, self.virtual['views'], node.queries, node.resources ]
            children = self.childrencache[node]
        elif isinstance (node, AbstractBundle):
            children = node
        elif isinstance (node, Resources):
            if not node in self.childrencache:
                self.childrencache[node] = node.children()
            children = self.childrencache[node]
        elif isinstance (node, ResourceData):
            children = None
        elif node == self.virtual['views']:
            children=[ self.virtual['static'], self.virtual['dynamic'], self.virtual['adhoc'] ]
        elif node is None:
            children = [ self.get_package() ]
        else:
            children = None
            for t in ('static', 'dynamic', 'adhoc'):
                if node == self.virtual[t]:
                    children=sorted([ v 
                                      for v in node.rootPackage.views
                                      if helper.get_view_type(v) == t ],
                                    key=lambda e: (e.title or e.id).lower())
                    break
        return children

    def nodeHasChildren (self, node):
        children = self.nodeChildren(node)
        return (children is not None and children)

class TreeWidget(AdhocView):
    def __init__(self, package, modelclass=DetailedTreeModel, controller=None):
        self.view_name = _("Tree view")
	self.view_id = 'treeview'
	self.close_on_package_load = False
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            )
        self.controller=controller
        self.options={}

        self.package = package
        self.modelclass=modelclass

        self.model = modelclass(controller=controller, package=package)

	self.widget = self.build_widget()

    def build_widget(self):
        tree_view = gtk.TreeView(self.model)

        select = tree_view.get_selection()
        select.set_mode(gtk.SELECTION_SINGLE)

        tree_view.connect("button_press_event", self.tree_view_button_cb)
        tree_view.connect("row-activated", self.row_activated_cb)
	tree_view.set_search_column(AdveneTreeModel.COLUMN_TITLE)

        #tree_view.connect("select-cursor-row", self.debug_cb)
        #select.connect ("changed", self.debug_cb)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Package View"), cell, text=0)
        tree_view.append_column(column)

        # Drag and drop for annotations
        tree_view.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['adhoc-view']
                          + config.data.drag_type['annotation-type']
                          + config.data.drag_type['annotation']
                          + config.data.drag_type['text-plain']
                          + config.data.drag_type['TEXT']
                          + config.data.drag_type['STRING']
                          ,
                          gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)

        tree_view.connect("drag_data_get", self.drag_data_get_cb)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	sw.add(tree_view)

	sw.treeview = tree_view

        return sw

    def drag_data_get_cb(self, treeview, context, selection, targetType, timestamp):
        treeselection = treeview.get_selection()
        model, iter = treeselection.get_selected()

        el = model.get_value(iter, AdveneTreeModel.COLUMN_ELEMENT)

        if targetType == config.data.target_type['annotation']:
            if not isinstance(el, Annotation):
                return False
            selection.set(selection.target, 8, el.uri)
            return True
        elif targetType == config.data.target_type['annotation-type']:
            if not isinstance(el, AnnotationType):
                return False
            selection.set(selection.target, 8, el.uri)
            return True
        elif targetType == config.data.target_type['adhoc-view']:
            if not isinstance(el, View):
                return False
            if el.content.mimetype != 'application/x-advene-adhoc-view':
                return False
            selection.set(selection.target, 8, 'id:' + el.id)
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
                                                    AdveneTreeModel.COLUMN_ELEMENT)
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
                                           AdveneTreeModel.COLUMN_ELEMENT)
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

    def refresh(self, *p):
        self.update_model(self.package)
        return True

    def update_element(self, element=None, event=None):
	#print "Update element ", str(element), str(event)
        if event.endswith('Create'):
            self.model.update_element(element, created=True)
        elif event.endswith('EditEnd'):
            self.model.update_element(element, created=False)
        elif event.endswith('Delete'):
            # FIXME: remove_element is incorrect for the moment
            #        so do a global update
	    #print "Remove element"
            #self.model.remove_element (element)
            self.update_model(element.rootPackage)
        else:
            return "Unknown event %s" % event
        return

    def update_annotation(self, annotation=None, event=None):
        """Update the annotation.
        """
        self.update_element(annotation, event)
        return

    def update_relation(self, relation=None, event=None):
        """Update the relation.
        """
        self.update_element(relation, event)
        return

    def update_view(self, view=None, event=None):
        self.update_element(view, event)
        return

    def update_query(self, query=None, event=None):
        self.update_element(query, event)
        return

    def update_schema(self, schema=None, event=None):
        self.update_element(schema, event)
        return

    def update_annotationtype(self, annotationtype=None, event=None):
        self.update_element(annotationtype, event)
        return

    def update_relationtype(self, relationtype=None, event=None):
        """Update the relationtype
        """
        self.update_element(relationtype, event)
        return

    def update_resource(self, resource=None, event=None):
        self.update_element(resource, event)
        return

    def update_model(self, package):
        """Update the model with a new package."""
        #print "Treeview: update model %s" % str(package)
        # Get current path
        oldpath=self.widget.treeview.get_cursor()[0]
        self.model = self.modelclass(controller=self.controller,
                                     package=package)
        self.widget.treeview.set_model(self.model)
        # Return to old path if possible
        if oldpath is not None:
            self.widget.treeview.expand_to_path(oldpath)
            self.widget.treeview.set_cursor(oldpath)
        return

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
