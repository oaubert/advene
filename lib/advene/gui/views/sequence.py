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
"""Sequence view/editor.

This interface is used to easily edit a list of annotations in the
form of a list, specifying timestamps and content.

The data is presented as follows :

|  Begin   |  End   | Data      | Type* |

"""

import sys

import gtk
import gobject

# Advene part
import advene.core.config as config

from advene.model.package import Package
from advene.gui.views import AdhocView

import advene.util.helper as helper

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.popup

class SequenceModel(gtk.GenericTreeModel):
    COLUMN_BEGIN=0
    COLUMN_END=1
    COLUMN_DATA=2
    COLUMN_TYPE=3
    COLUMN_ELEMENT=4
    COLUMN_EDITABLE=5

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
        return 6

    def on_get_column_type(self, index):
        # Data is stored as:
        # begin, end, content, type, annotation, element, editable
        types=(gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING,
               gobject.TYPE_STRING, gobject.TYPE_PYOBJECT, gobject.TYPE_BOOLEAN)
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
        if column == self.COLUMN_BEGIN:
            return unicode(helper.format_time(node.fragment.begin))
        elif column == self.COLUMN_END:
            return unicode(helper.format_time(node.fragment.end))
        elif column == self.COLUMN_DATA:
            return unicode(node.content.data)
        elif column == self.COLUMN_TYPE:
            return unicode(node.type.title or node.type.id)
        elif column == self.COLUMN_EDITABLE:
            return True
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

class SequenceEditor(AdhocView):
    def __init__ (self, controller=None):
        # FIXME: pass AnnotationType here, and (optionaly) an existing list of
        # annotations
        self.view_name = _("Sequence Editor")
        self.view_id = 'sequenceview'
        self.close_on_package_load = True

        self.controller=controller
        self.package=controller.package
        self.model = SequenceModel(self.package.annotations)

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
        column = gtk.TreeViewColumn(_("Begin"), cell,
                                    text=SequenceModel.COLUMN_BEGIN,
                                    editable=SequenceModel.COLUMN_EDITABLE)
        tree_view.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("End"), cell,
                                    text=SequenceModel.COLUMN_END,
                                    editable=SequenceModel.COLUMN_EDITABLE)

        tree_view.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Data"), cell,
                                    text=SequenceModel.COLUMN_DATA,
                                    editable=SequenceModel.COLUMN_EDITABLE)
        tree_view.append_column(column)

        cell = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_("Type"), cell,
                                    text=SequenceModel.COLUMN_TYPE)
        tree_view.append_column(column)

        tree_view.connect("button_press_event", self.tree_view_button_cb)
        tree_view.connect("button-press-event", self.tree_select_cb)

        return tree_view

    def get_selected_node (self):
        """Return the currently selected node.

        None if no node is selected.
        """
        tree_view = self.get_widget()
        selection = tree_view.get_selection ()
        if not selection:
            return None
        store, it = selection.get_selected()
        node = None
        if it is not None:
            node = tree_view.get_model().get_value (it,
                                                    SequenceModel.COLUMN_ELEMENT)
        return node

    def tree_select_cb(self, tree_view, event):
        # On double-click, edit element
        if event.type == gtk.gdk._2BUTTON_PRESS:
            node = self.get_selected_node ()
            if node is not None:
                try:
                    pop = advene.gui.edit.elements.get_edit_popup (node,
                                                                   controller=self.controller)
                except TypeError, e:
                    print _("Error: unable to find an edit popup for %(element)s:\n%(error)s") % { 
                        'element': node,
                        'error': str(e) }
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
                                       SequenceModel.COLUMN_ELEMENT)
                widget.get_selection().select_path (path)
                if button == 3:
                    menu=advene.gui.popup.Menu(node, controller=self.controller)
                    menu.popup()
                    retval = True
        return retval

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    import advene.core.imagecache

    class DummyController:
        def notify(self, *p, **kw):
            print "Notify %s %s" % (p, kw)

    controller=DummyController()

    controller.package = Package (uri=sys.argv[1])
    controller.imagecache = advene.core.imagecache.ImageCache()

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
        package.save (name=filename)
        print "Package saved as %s" % filename
        gtk.main_quit ()


    b = gtk.Button (stock=gtk.STOCK_SAVE)
    b.connect ("clicked", validate_cb, controller.package)
    hbox.add (b)

    b = gtk.Button (stock=gtk.STOCK_QUIT)
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
                # Ctrl-return to Open popup to edit current element
                node=seq.get_selected_node()
                pop = advene.gui.edit.elements.get_edit_popup (node,
                                                               controller=controller)
                if pop is not None:
                    pop.display ()
                else:
                    print _("Error: unable to find an edit popup for %s") % node
        return False

    window.connect ("key-press-event", key_pressed_cb)
    window.connect ("destroy", lambda e: gtk.main_quit())

    window.show_all()
    gtk.main ()

