#! /usr/bin/env python

"""Sequence view/editor.

This interface is used to easily edit a list of annotations in the
form of a list, specifying timestamps and content.

The data is presented as follows :

|  Begin   |  End   | Data      | Type* |
"""

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

class AdveneListModel(gtk.GenericTreeModel):
    def __init__(self, elements):
        gtk.GenericTreeModel.__init__(self)
        self.elements = elements

    def nodeParent (self, node):
        return None

    def nodeChildren (self, node):
        return None

    def nodeHasChildren (self, node):
        return False
        
    def on_get_flags(self):
        return 0
    
    def on_get_n_columns(self):
        return 5
    
    def on_get_column_type(self, index):
        # Data is stored as:
        # begin, end, content, type, annotation
        types=(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,
               gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
        return types[index]

    def on_get_path(self, node): # FIXME
        # print "on_get_path()"
        # print "node: " + str(node)
        # node is either an Annotation or an AnnotationType
        return (self.elements.index(node), )
            
    def on_get_iter(self, path):
        """Return the node corresponding to the given path.
        """
        return self.elements[path[0]]

    def on_get_tree_path(self, node):
        return self.on_get_path(node)

    def on_get_value(self, node, column):
        if column == 0:
            return unicode(node.fragment.begin)
        elif column == 1:
            return unicode(node.fragment.end)
        elif column == 2:
            return unicode(node.content.data)
        elif column == 3:
            return unicode(node.type.title or node.type.id)
        else:
            return node

    def on_iter_next(self, node):
        """Return the next node at this level of the tree"""
        idx = self.elements.index(node)
        next = None
        try:
            next = self.elements[idx+1]
        except IndexError:
            pass
        return next

    def on_iter_children(self, node):
        """Return the first child of this node"""
        children = self.nodeChildren(node)
        assert len(children), _("No children in on_iter_children()!")
        return children[0]
    
    def on_iter_has_child(self, node):
        """returns true if this node has children"""
        return False

    def on_iter_n_children(self, node):
        """returns the number of children of this node"""
        return 0

    def on_iter_nth_child(self, node, n):
        """Returns the nth child of this node"""
        return None

    def on_iter_parent(self, node):
        """Returns the parent of this node"""
        return None

class SequenceEditor:
    def __init__ (self, controller=None):
        # FIXME: pass AnnotationType here, and (optionaly) an existing list of
        # annotations
        self.controller=controller
        self.package=controller.package
        self.model = AdveneListModel(self.package.annotations)

        self.widget=self.build_widget()

        # Two solutions: either have a model directly interacting with
        # the package's data, *or* creating an intermediate model in
        # order to be able to cancel actions
        
    def set_type(self, type):
        self.annotationtype=type

    def build_widget(self):
        tree_view = gtk.TreeView(self.model)
        
        select = tree_view.get_selection()
        select.set_mode(gtk.SELECTION_SINGLE)
        
        # Define the 4 cell renderers
        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Begin"), cell, text=0)
        tree_view.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("End"), cell, text=1)
        tree_view.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Data"), cell, text=2)
        tree_view.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Type"), cell, text=3)
        tree_view.append_column(column)

        tree_view.connect("button_press_event", self.tree_view_button_cb)
        tree_view.connect("button-press-event", self.tree_select_cb)

        return tree_view
    
    def get_widget (self):
        """Return the TreeView widget."""
        return self.widget

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

    class DummyController:
        pass

    controller=DummyController()
    
    controller.package = Package (uri=sys.argv[1])
    
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_size_request (640, 480)

    window.set_border_width(10)
    window.set_title (controller.package.title)
    vbox = gtk.VBox()
    
    window.add (vbox)
    
    sw = gtk.ScrolledWindow()
    sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    vbox.add (sw)

    seq = SequenceEditor(controller=controller)
    
    sw.add (seq.get_widget())

    hbox = gtk.HButtonBox()
    vbox.pack_start (hbox, expand=False)

    def validate_cb (win, package):
        filename="/tmp/package.xml"
        package.save (as=filename)
        print "Package saved as %s" % filename
        gtk.main_quit ()
        

    b = gtk.Button (stock=gtk.STOCK_SAVE)
    b.connect ("clicked", validate_cb, controller.package)
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

