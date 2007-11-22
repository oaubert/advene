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

# Advene finder, a la MacOS X

# Advene part
from advene.gui.views.tree import DetailedTreeModel
from advene.gui.views import AdhocView
from advene.gui.views.annotationdisplay import AnnotationDisplay
from advene.model.schema import AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
import advene.gui.popup

from gettext import gettext as _

import gtk

name="Package finder view plugin"

def register(controller):
    controller.register_viewclass(Finder)

class FinderColumn:
    COLUMN_TITLE=0
    COLUMN_NODE=1
    COLUMN_COLOR=2
    def __init__(self, controller=None, node=None, callback=None, parent=None):
        self.controller=controller
        self.node=node
        self.callback=callback
        self.previous=parent
        self.next=None
        self.widget=self.build_widget()

    def get_name(self):
        if self.node is None:
            return "FIXME"
        return self.node[self.COLUMN_TITLE]
    name=property(fget=get_name, doc="Displayed name for the element")
            
    def get_widget(self):
        return self.widget

    def get_valid_members(self, el):
        """Return the list of valid members for the element.
        """
        def title(c):
            el=c[DetailedTreeModel.COLUMN_ELEMENT]
            if isinstance(el, AnnotationType):
                return "(%d) %s" % (len(el.annotations), c[DetailedTreeModel.COLUMN_TITLE])
            elif isinstance(el, RelationType):
                return "(%d) %s" % (len(el.relations), c[DetailedTreeModel.COLUMN_TITLE])
            else:
                return c[DetailedTreeModel.COLUMN_TITLE]
            
        return [ (title(c),
                  c, 
                  c[DetailedTreeModel.COLUMN_COLOR]) for c in self.node.iterchildren() ]

    def get_liststore(self):
        ls=gtk.ListStore(str, object, str)
        if self.node is None:
            return ls
        for row in self.get_valid_members(self.node):
            ls.append(row)
        return ls

    def update(self, node=None):
        self.node=node
        self.next=None
        self.liststore.clear()
        if self.node is None:
            return True
        self.label.set_label(self.name)
        for row in self.get_valid_members(node):
            self.liststore.append(row)
        # Destroy all following columns
        return True

    def on_column_activation(self, widget):
        # Delete all next columns
        cb=self.next
        while cb is not None:
            cb.widget.destroy()
            cb=cb.next
        self.next=None
        return True

    def on_button_press(self, widget, event):
        if not event.button in (1, 3):
            return False
        x = int(event.x)
        y = int(event.y)
        node=None
        if not event.window is widget.get_bin_window():
            return False
        model = widget.get_model()
        t = widget.get_path_at_pos(x, y)
        if t is None:
            return False
        path, col, cx, cy = t
        it = model.get_iter(path)
        node = model.get_value(it, DetailedTreeModel.COLUMN_ELEMENT)
        widget.get_selection().select_path (path)
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            # Double-click: edit the element
            self.controller.gui.edit_element(node[DetailedTreeModel.COLUMN_ELEMENT])
            return True
        elif event.button == 3:
            menu = advene.gui.popup.Menu(node[DetailedTreeModel.COLUMN_ELEMENT], controller=self.controller)
            menu.popup()
            return True
        return False

    def on_changed_selection(self, selection, model):
        att=None
        if selection is not None:
            store, it = selection.get_selected()
            if it is not None:
                att = model.get_value (it, self.COLUMN_NODE)
        if att and self.callback:
            self.callback(self, att)
            return True
        return False

    def build_widget(self):
        vbox=gtk.VBox()

        self.label=gtk.Button(self.name)
        self.label.connect("clicked", self.on_column_activation)
        vbox.pack_start(self.label, expand=False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add (sw)

        self.liststore = self.get_liststore()
        self.listview = gtk.TreeView(self.liststore)
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Attributes", renderer, 
                                    text=self.COLUMN_TITLE, 
                                    cell_background=self.COLUMN_COLOR)
        column.set_widget(gtk.Label())
        self.listview.append_column(column)

        selection = self.listview.get_selection()
        selection.unselect_all()
        selection.connect('changed', self.on_changed_selection, self.liststore)
        self.listview.connect("button-press-event", self.on_button_press)


        sw.add_with_viewport(self.listview)

        vbox.show_all()
        return vbox

class Finder(AdhocView):
    view_name = _("Package finder")
    view_id = 'finder'
    tooltip=_("Column-based package finder")
    def __init__(self, controller=None, parameters=None):
        super(Finder, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = []
        
        self.package=controller.package
        self.controller=controller

        self.model=DetailedTreeModel(controller=controller, package=self.package)
        # 640 / 4
        self.column_width=160
        self.rootcolumn=None
        self.widget=self.build_widget()

    def update_model(self, package=None):
        if package is None:
            package = self.controller.package

        # Reset to the rootcolumn
        cb=self.rootcolumn.next
        while cb is not None:
            cb.widget.destroy()
            cb=cb.next
        self.rootcolumn.next=None

        self.package = package
        self.model=DetailedTreeModel(controller=self.controller, package=package)

        # Update the rootcolumn element
        self.rootcolumn.update(self.model[0])
        return True

    def clicked_callback(self, columnbrowser, node):
        if columnbrowser is None:
            # We selected  the rootcolumn. Delete the next ones
            cb=self.rootcolumn.next
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next
            self.rootcolumn.next=None
        elif columnbrowser.next is None:
            if isinstance(node[DetailedTreeModel.COLUMN_ELEMENT], Annotation):
                col=AnnotationDisplay(controller=self.controller, annotation=node[DetailedTreeModel.COLUMN_ELEMENT])
                col.next=None
                def update(c, node):
                    c.set_annotation(node[DetailedTreeModel.COLUMN_ELEMENT])
                    return True
                col.update = update.__get__(col)
            else:
                # Create a new columnbrowser
                col=FinderColumn(controller=self.controller, 
                                 node=node, 
                                 callback=self.clicked_callback, 
                                 parent=columnbrowser)
            col.widget.set_property("width-request", self.column_width)
            self.hbox.pack_start(col.widget, expand=False)
            columnbrowser.next=col
        else:
            # Delete all next+1 columns (we reuse the next one)
            cb=columnbrowser.next.next
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next
            columnbrowser.next.update(node)

        # Scroll the columns
        adj=self.sw.get_hadjustment()
        adj.value = adj.upper - .1
        return True

    def scroll_event(self, widget=None, event=None):
        if event.state & gtk.gdk.CONTROL_MASK:
            a=widget.get_hadjustment()
            if event.direction == gtk.gdk.SCROLL_DOWN:
                val = a.value + a.step_increment
                if val > a.upper - a.page_size:
                    val = a.upper - a.page_size
                if val != a.value:
                    a.value = val
                    a.value_changed ()
                return True
            elif event.direction == gtk.gdk.SCROLL_UP:
                val = a.value - a.step_increment
                if val < a.lower:
                    val = a.lower
                if val != a.value:
                    a.value = val
                    a.value_changed ()
                return True
        return False

    def build_widget(self):
        vbox=gtk.VBox()

        self.sw=gtk.ScrolledWindow()
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.sw.connect('scroll_event', self.scroll_event)
        vbox.add(self.sw)

        self.hbox = gtk.HBox()

        self.rootcolumn=FinderColumn(controller=self.controller,
                                     node=self.model[0],
                                     callback=self.clicked_callback,
                                     parent=None)
        self.rootcolumn.widget.set_property("width-request", self.column_width)
        self.hbox.pack_start(self.rootcolumn.get_widget(), expand=False)

        self.sw.add_with_viewport(self.hbox)

        vbox.show_all()
        return vbox
