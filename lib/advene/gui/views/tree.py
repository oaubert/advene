#! /usr/bin/python

import sys

# Advene part
import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.edit.create

import pygtk
pygtk.require ('2.0')
import gtk
import gobject

class AdveneTreeModel(gtk.GenericTreeModel):
    def nodeParent (self, node):
        raise Exception("This has to be implemented in subclasses.")

    def nodeChildren (self, node):
        raise Exception("This has to be implemented in subclasses.")

    def nodeHasChildren (self, node):
        raise Exception("This has to be implemented in subclasses.")
        
    def __init__(self, package):
        gtk.GenericTreeModel.__init__(self)

        self.clear_cache ()
        self.__package = package

    def get_package(self):
        return self.__package
                    
    def clear_cache (self):
        self.childrencache = {}

    def remove_element (self, e):
        """Remove an element from the cache.

        Currently implemented only for Annotations.
        """
        assert isinstance (e, Annotation)
        # FIXME: remove annotation from its parent list
        del (self.childrencache[self.nodeParent(e)])
        
    def on_get_flags(self):
        return 0
    
    def on_get_n_columns(self):
        return 2

    def on_get_column_type(self, index):
        types=(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        return types[index]

    def on_get_path(self, node): # FIXME
        # print "on_get_path()"
        # print "node: " + str(node)
        # node is either an Annotation or an AnnotationType
        parent = self.nodeParent (node)
        child = node
        idx = []
        while parent is not None:
            children = self.nodeChildren(parent)
            i = children.index (child)
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
        title = "???"
        if isinstance (node, Annotation):
            title = _("Annotation %s (%d, %d)") % (node.id,
                                                   node.fragment.begin,
                                                   node.fragment.end)
        elif isinstance (node, Relation):
            title = _("Relation %s") % (node.id)
        elif isinstance (node, AnnotationType):
            title = _("Annotation Type %s") % (node.title or node.id)
        elif isinstance (node, RelationType):
            title = _("Relation Type %s") % (node.title or node.id)
        elif isinstance (node, Schema):
            title = _("Schema %s") % (node.title or node.id)
        elif isinstance (node, View):
            title = _("View %s") % (node.title or node.id)
        elif isinstance (node, Package):
            title = _("Package %s") % (node.title or _("No Title"))
        else:
            title = str(node)
        return title
    
    def on_get_value(self, node, column):
        if column == 0:
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
        if node is not None:
            children = self.nodeChildren(node)
            assert len(children), _("No children in on_iter_nth_child()")
            child = children[n]
        return child

    def on_iter_parent(self, node):
        """Returns the parent of this node"""
        return self.nodeParent(node)

class DetailedTreeModel(AdveneTreeModel):
    """Detailed Tree Model.

    In this model,
       - Annotations and Relations depend on their types.
       - Types depend on their schema
       - Schemas depend on their package list of schemas
       - Views depend on their package list of views
    """
    def nodeParent (self, node):
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
            parent = node.rootPackage.views
        elif isinstance (node, Package):
            parent = None
        elif isinstance (node, AbstractBundle):
            parent = node.rootPackage
        else:
            parent = None
        return parent

    def nodeChildren (self, node):
        if isinstance (node, Annotation):
            children = None
        elif isinstance (node, Relation):
            children = None
        elif isinstance (node, AnnotationType):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = node.annotations
            children = self.childrencache[node]
        elif isinstance (node, RelationType):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = node.relations
            children = self.childrencache[node]
        elif isinstance (node, Schema):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = list(node.annotationTypes)
                self.childrencache[node].extend(node.relationTypes)
            children = self.childrencache[node]
        elif isinstance (node, View):
            children = None
        elif isinstance (node, Package):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = (node.schemas, node.views)
            children = self.childrencache[node]
        elif isinstance (node, AbstractBundle):
            children = node
        else:
            children = None
        return children

    def nodeHasChildren (self, node):
        if isinstance (node, Annotation):
            return False
        elif isinstance (node, Relation):
            return False
        elif isinstance (node, AnnotationType):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = node.annotations
            return len (self.childrencache[node])
        elif isinstance (node, RelationType):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = node.relations
            return len (self.childrencache[node])
        elif isinstance (node, Schema):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = list(node.annotationTypes)
                self.childrencache[node].extend(node.relationTypes)
            return len (self.childrencache[node])
        elif isinstance (node, Package):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = (node.schemas, node.views)
            return len(self.childrencache[node]) > 0
        elif isinstance (node, AbstractBundle):
            return len(node)
        else:
            return False
        return False
        
class FlatTreeModel(AdveneTreeModel):
    """Flat Tree Model.

    In this model, no element other than Package has children.
    We display the elements by type.
    """
    def nodeParent (self, node):
        if isinstance (node, Annotation):
            parent = node.rootPackage.annotations
        elif isinstance (node, Relation):
            parent = node.rootPackage.relations
        elif isinstance (node, AnnotationType):
            parent = node.rootPackage.annotationTypes
        elif isinstance (node, RelationType):
            parent = node.rootPackage.relationTypes
        elif isinstance (node, Schema):
            parent = node.rootPackage.schemas
        elif isinstance (node, View):
            parent = node.rootPackage.views
        elif isinstance (node, Package):
            parent = None
        elif isinstance (node, AbstractBundle):
            try:
                parent = node.rootPackage
            except AttributeError:
                # FIXME: Horrible hack to workaround the fact that
                # p.relationTypes and p.annotationTypes bundles
                # do not have a rootPackage attribute.
                parent = self.get_package()
        else:
            parent = None
        return parent

    def nodeChildren (self, node):
        if isinstance (node, Annotation):
            children = None
        elif isinstance (node, Relation):
            children = None
        elif isinstance (node, AnnotationType):
            children = None
        elif isinstance (node, RelationType):
            children = None
        elif isinstance (node, Schema):
            children = None
        elif isinstance (node, View):
            children = None
        elif isinstance (node, Package):
            if not self.childrencache.has_key (node):
                self.childrencache[node] = (node.schemas, node.views, node.annotations,
                                            node.relationTypes, node.annotationTypes)
            children = self.childrencache[node]
        elif isinstance (node, AbstractBundle):
            children = node
        else:
            children = None
        return children

    def nodeHasChildren (self, node):
        children = self.nodeChildren(node)
        return (children is not None and children)

class TreeWidget:
    def __init__(self, package, modelclass=DetailedTreeModel,
                 annotation_cb=None, controller=None):
        self.package = package
        self.controller=controller

        if annotation_cb is not None:
            self.annotation_cb = annotation_cb

        self.model = modelclass(package)

        tree_view = gtk.TreeView(self.model)
        self.tree_view = tree_view
        
        select = tree_view.get_selection()
        select.set_mode(gtk.SELECTION_SINGLE)
        
        tree_view.connect("button-press-event", self.tree_select_cb)
        #tree_view.connect("select-cursor-row", self.debug_cb)
        #select.connect ("changed", self.debug_cb)
        
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Package View"), cell, text=0)
        tree_view.append_column(column)

        tree_view.connect("button_press_event", self.tree_view_button_cb)

        
    def get_widget (self):
        """Return the TreeView widget."""
        return self.tree_view

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
                                                    advene.gui.edit.elements.EditAttributesForm.COLUMN_VALUE)
        return node
    
    def tree_select_cb(self, tree_view, event):
        # On double-click, edit element
        if event.type == gtk.gdk._2BUTTON_PRESS:
            node = self.get_selected_node (tree_view)
            if node is not None:
                try:
                    pop = advene.gui.edit.elements.get_edit_popup (node,
                                                                   controller=self.controller)
                except TypeError, e:
                    print _("Error: unable to find an edit popup for %s:\n%s") % (node, str(e))
                else:
                    pop.edit ()
                return True
        return False
        
    def debug_cb (self, *p, **kw):
        print "Debug cb:\n"
        print "Parameters: %s" % str(p)
        print "KW: %s" % str(kw)

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)
        if event.window is widget.get_bin_window():
            model = self.model
            t = widget.get_path_at_pos(x, y)
            if t is not None:
                path, col, cx, cy = t
                iter = model.get_iter(path)
                node = model.get_value(iter,
                                       advene.gui.edit.elements.EditAttributesForm.COLUMN_VALUE)
                widget.get_selection().select_path (path)
                if button == 3:
                    menu = self.make_popup_menu(node, path)
                    menu.popup(None, None, None, button, event.time)
                    retval = True
        return retval

    def popup_edit (self, button=None, node=None, path=None):
        try:
            pop = advene.gui.edit.elements.get_edit_popup (node,
                                                           controller=self.controller)
        except TypeError, e:
            print _("Error: unable to find an edit popup for %s:\n%s") % (node, str(e))
        else:
            pop.edit ()
        return True
    
    def popup_delete (self, button=None, node=None, path=None):
        print "Popup delete %s %s" % (node, path)
        assert isinstance (node, Annotation)
        # Remove the element from the data
        a = node.rootPackage.annotations
        i = a.index (node)
        del (a[i])
        # Invalidate the model cache
        self.model.remove_element (node)
        return True
    
    def popup_display (self, button=None, node=None, path=None):
        pop = advene.gui.edit.elements.get_edit_popup (node,
                                                       controller=self.controller)
        if pop is not None:
            pop.display ()
        else:
            print _("Error: unable to find an edit popup for %s") % node
        return True

    def annotation_cb (self, widget=None, node=None):
        return True

    def create_element_cb(self, widget, elementtype=None, parent=None):
        print "Creating a %s in %s" % (elementtype, parent)
        cr = advene.gui.edit.create.CreateElementPopup(type_=elementtype,
                                                       parent=parent)
        cr.popup()
        return True
    
    def make_popup_menu(self, node=None, path=None):
        menu = gtk.Menu()

        def add_menuitem(menu, item, action, *param):
            item = gtk.MenuItem(item)
            item.connect("activate", action, *param)
            menu.append(item)
            
        if isinstance (node, Package):
            title=node.title
        elif isinstance (node, AbstractBundle):
            title = node.viewableType
        else:
            try:
                title=node.id
            except:
                title="????"
        item = gtk.MenuItem("%s %s" % (node.viewableClass, title))
        menu.append(item)

        item = gtk.SeparatorMenuItem()
        menu.append(item)

        add_menuitem(menu, _("Edit"), self.popup_edit, node, path)

        if isinstance (node, Annotation):
            add_menuitem(menu, _("Picture..."), self.annotation_cb, node)

        if isinstance(node, Package):
            add_menuitem(menu, _("Create a new view..."), self.create_element_cb, View, node)
            add_menuitem(menu, _("Create a new annotation..."), self.create_element_cb, Annotation, node)
            add_menuitem(menu, _("Create a new relation..."), self.create_element_cb, Relation, node)
            add_menuitem(menu, _("Create a new schema..."), self.create_element_cb, Schema, node)

        add_menuitem(menu, _("Display"), self.popup_display, node, path)

        menu.show_all()
        return menu

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    package = Package (uri=sys.argv[1])
    
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_size_request (640, 480)

    window.set_border_width(10)
    window.set_title (package.title)
    vbox = gtk.VBox()
    
    window.add (vbox)
    
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    vbox.add (sw)
        
    #tree = TreeWidget(package, modelclass=FlatTreeModel)
    tree = TreeWidget(package, modelclass=DetailedTreeModel)
    
    sw.add (tree.get_widget())

    hbox = gtk.HButtonBox()
    vbox.pack_start (hbox, expand=False)

    def validate_cb (win, package):
        filename="/tmp/package.xml"
        package.save (as=filename)
        print "Package saved as %s" % filename
        gtk.main_quit ()
        

    b = gtk.Button (stock=gtk.STOCK_SAVE)
    b.connect ("clicked", validate_cb, package)
    hbox.add (b)

    b = gtk.Button (stock=gtk.STOCK_CANCEL)
    b.connect ("clicked", lambda w: window.destroy ())
    hbox.add (b)

    vbox.set_homogeneous (False)

    def key_pressed_cb (win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True
        elif event.keyval == gtk.keysyms.Return:
            # Open popup to edit current element
            node=tree.get_selected_node(tree.view())
            pop = advene.gui.edit.elements.get_edit_popup (node,
                                                           controller=self.controller)
            if pop is not None:
                pop.display ()
            else:
                print _("Error: unable to find an edit popup for %s") % node
        return False            

    window.connect ("key-press-event", key_pressed_cb)
    window.connect ("destroy", lambda e: gtk.main_quit())

    window.show_all()
    gtk.main ()

