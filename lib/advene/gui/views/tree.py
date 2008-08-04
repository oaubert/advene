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

from gettext import gettext as _
import gtk
import cgi

import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.resources import Resources, ResourceData
from advene.model.query import Query
from advene.model.view import View
from advene.gui.views import AdhocView

import advene.gui.edit.elements
import advene.gui.popup

import advene.util.helper as helper

name="Tree view plugin"

def register(controller):
    controller.register_viewclass(TreeWidget)

class AdveneTreeModel(gtk.GenericTreeModel, gtk.TreeDragSource, gtk.TreeDragDest):
    COLUMN_TITLE=0
    COLUMN_ELEMENT=1
    COLUMN_COLOR=2

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
        #print "Removing element ", e.id

        if isinstance(e, View):
            # Remove the element from the list view and refresh list view
            parent=self.nodeParent(e)
            #parent=self.get_package().views
            path=self.on_get_path(parent)
            #print "before row changed"
            self.row_changed(path, self.get_iter(path))
            #print "after row changed"
            return

        parent=None
        for p in self.childrencache:
            if e in self.childrencache[p]:
                parent=p
                #print "Found parent ", str(parent)
                break
        if parent is None:
            # Could not find the element in the cache.
            # It was not yet displayed
            print "Parent not found"
        else:
            # We can determine its path. Get the index for the deleted
            # element from the childrencache.
            path=self.on_get_path(parent)
            if path is not None:
                #print "Parent path", path
                #print "cache", self.childrencache[parent]
                try:
                    idx=self.childrencache[parent].index(e)
                except ValueError:
                    # The children was not in the cache. Should not
                    # normally happen, but who knows...
                    idx=None
                if idx is not None:
                    path=path + (idx, )
                    # Now that we have the old path for the deleted
                    # element, we can notify the row_deleted signal.
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
        return 3

    def on_get_column_type(self, index):
        types=(str, object, str)
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
            try:
                node = children[idx]
            except IndexError:
                node=None
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
        if ((hasattr(node, 'isImported') and node.isImported())
            or (hasattr(node, 'schema') and node.schema.isImported())):
            title += " (*)"
        return title

    def on_get_value(self, node, column):
        def get_color(e):
            if (isinstance(e, Annotation) or isinstance(e, Relation)
                or isinstance(e, AnnotationType) or isinstance(e, RelationType)):
                return self.controller.get_element_color(e)
            else:
                return None
        if column == AdveneTreeModel.COLUMN_TITLE:
            return self.title(node)
        elif column == AdveneTreeModel.COLUMN_COLOR:
            return get_color(node)
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
        if not children:
            return None
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
        selection.set(selection.target, 8, node.uri.encode('utf8'))
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
        self.virtual['admin']=VirtualNode(_("Admin views"), package, viewableType='view-list')
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
            if node.id.startswith('_'):
                parent=self.virtual['admin']
            else:
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
        elif node in (self.virtual['static'], self.virtual['dynamic'], self.virtual['adhoc'], self.virtual['admin']):
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
            children=[ self.virtual['static'], self.virtual['dynamic'], self.virtual['adhoc'], self.virtual['admin'] ]
        elif node is None:
            children = [ self.get_package() ]
        else:
            children = None
            if node == self.virtual['admin']:
                children=sorted([ v
                                  for v in node.rootPackage.views
                                  if v.id.startswith('_') ],
                                key=lambda e: (e.title or e.id).lower())
            else:
                for t in ('static', 'dynamic', 'adhoc'):
                    if node == self.virtual[t]:
                        children=sorted([ v
                                          for v in node.rootPackage.views
                                          if not v.id.startswith('_')
                                          and helper.get_view_type(v) == t ],
                                        key=lambda e: (e.title or e.id).lower())
                        break
        return children

    def nodeHasChildren (self, node):
        children = self.nodeChildren(node)
        return (children is not None and children)

class TreeWidget(AdhocView):
    view_name = _("Tree view")
    view_id = 'tree'
    tooltip=("Hierarchical view of an Advene package")
    def __init__(self, controller=None, parameters=None, package=None, modelclass=DetailedTreeModel):
        super(TreeWidget, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            )
        self.controller=controller
        self.options={}

        if package is None:
            package=controller.package
        self.package = package
        self.modelclass=modelclass

        self.model = modelclass(controller=controller, package=package)

        self.widget = self.build_widget()

    def build_widget(self):
        tree_view = gtk.TreeView(self.model)

        select = tree_view.get_selection()
        select.set_mode(gtk.SELECTION_SINGLE)

        tree_view.connect('button-press-event', self.tree_view_button_cb)
        tree_view.connect('row-activated', self.row_activated_cb)
        tree_view.set_search_column(AdveneTreeModel.COLUMN_TITLE)

        #tree_view.connect('select-cursor-row', self.debug_cb)
        #select.connect('changed', self.debug_cb)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Package View"), cell,
                                    text=AdveneTreeModel.COLUMN_TITLE,
                                    cell_background=AdveneTreeModel.COLUMN_COLOR,
                                    )
        tree_view.append_column(column)

        # Drag and drop for annotations
        tree_view.drag_source_set(gtk.gdk.BUTTON1_MASK,
                                  config.data.drag_type['text-plain']
                                  + config.data.drag_type['uri-list']
                                  + config.data.drag_type['TEXT']
                                  + config.data.drag_type['STRING']
                                  + config.data.drag_type['annotation-type']
                                  + config.data.drag_type['adhoc-view']
                                  + config.data.drag_type['annotation']
                                  + config.data.drag_type['view']
                                  ,
                                  gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)

        tree_view.connect('drag-data-get', self.drag_data_get_cb)

        try:
            # set_enable_tree_lines is available in gtk >= 2.10
            tree_view.set_enable_tree_lines(True)
        except AttributeError:
            pass

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(tree_view)

        sw.treeview = tree_view

        return sw

    def drag_data_get_cb(self, treeview, context, selection, targetType, timestamp):
        treeselection = treeview.get_selection()
        model, it = treeselection.get_selected()

        typ=config.data.target_type
        el = model.get_value(it, AdveneTreeModel.COLUMN_ELEMENT)

        #print "Drag data get ", targetType, "".join([ n for n in config.data.target_type if config.data.target_type[n] == targetType ])

        if targetType == typ['annotation']:
            if not isinstance(el, Annotation):
                return False
            selection.set(selection.target, 8, el.uri.encode('utf8'))
            return True
        elif targetType == typ['annotation-type']:
            if not isinstance(el, AnnotationType):
                return False
            selection.set(selection.target, 8, el.uri.encode('utf8'))
            return True
        elif targetType == typ['adhoc-view']:
            if not isinstance(el, View):
                return False
            if helper.get_view_type(el) != 'adhoc':
                return False
            selection.set(selection.target, 8,
                          cgi.urllib.urlencode( {
                        'id': el.id,
                        } ).encode('utf8'))
            return True
        elif targetType == typ['view']:
            if not isinstance(el, View):
                return False
            selection.set(selection.target, 8,
                          cgi.urllib.urlencode( {
                        'id': el.id,
                        } ).encode('utf8'))
            return True
        elif targetType == typ['uri-list']:
            try:
                ctx=self.controller.build_context(here=el)
                uri=ctx.evaluateValue('here/absolute_url')
            except:
                uri="No URI for " + unicode(el)
            selection.set(selection.target, 8, uri.encode('utf8'))
        elif targetType in (typ['text-plain'], typ['STRING']):
            selection.set(selection.target, 8, self.controller.get_title(el).encode('utf8'))
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
            # If node is an adhoc-view, then open it.
            if isinstance(node, View) and helper.get_view_type(node) == 'adhoc':
                self.controller.gui.open_adhoc_view(node)
            else:
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
            selection.set(selection.target, 8, widget.annotation.uri.encode('utf8'))
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        #print "drag_received event for %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            source=self.controller.package.annotations.get(unicode(selection.data, 'utf8').split('\n')[0])
            dest=widget.annotation
            self.create_relation_popup(source, dest)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True
