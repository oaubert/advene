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

# Advene finder, a la MacOS X
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from gi.repository import GObject
import urllib.request, urllib.parse, urllib.error

import advene.core.config as config
from advene.gui.edit.properties import EditWidget
from advene.gui.views import AdhocView
from advene.gui.views.annotationdisplay import AnnotationDisplay
from advene.gui.views.relationdisplay import RelationDisplay

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.resources import Resources, ResourceData
from advene.model.query import Query
from advene.model.view import View

import advene.rules.elements
import advene.gui.popup
import advene.util.helper as helper
import advene.model.tal.context
from advene.gui.util import get_target_types, enable_drag_source, contextual_drag_begin, drag_data_get_cb

name="Package finder view plugin"

def register(controller):
    controller.register_viewclass(Finder)

# Matching between element classes and the FinderColumn class
CLASS2COLUMN={}

class Metadata(object):
    """Virtual object describing an element Metadata.
    """
    def __init__(self, element, package, viewableType=None):
        self.element = element
        self.rootPackage = package
        self.viewableType = viewableType

    def get_config(self, uri):
        (ns, k) = uri.split(':')
        return self.element.getMetaData(config.data.namespace_prefix[ns], k)

    def set_config(self, uri, value):
        (ns, k) = uri.split(':')
        self.element.setMetaData(config.data.namespace_prefix[ns], k, value)

    def list_keys(self):
        try:
            return [ "%s:%s" % (config.data.reverse_namespace_prefix[nsuri],
                                name)
                     for (nsuri, name, value) in self.element.listMetaData() ]
        except AttributeError:
            return []

class VirtualNode:
    """Virtual node.
    """
    def __init__(self, name, package, viewableType=None):
        self.title=name
        self.rootPackage=package
        self.viewableType=viewableType

class DetailedTreeModel(object):
    """Detailed Tree Model.

    In this model,
       - Annotations and Relations depend on their types.
       - Types depend on their schema
       - Schemas depend on their package list of schemas
       - Views depend on their package list of views
       - Resources depend on the Resource node
    """
    def __init__(self, controller=None, package=None):
        self.childrencache = {}
        self.virtual={}
        self.virtual['root']    = VirtualNode(_("Package"),       package)
        self.virtual['views']   = VirtualNode(_("List of views"), package, viewableType='view-list')
        self.virtual['static']  = VirtualNode(_("Static views"),  package, viewableType='view-list')
        self.virtual['dynamic'] = VirtualNode(_("Dynamic views"), package, viewableType='view-list')
        self.virtual['admin']   = VirtualNode(_("Admin views"),   package, viewableType='view-list')
        self.virtual['adhoc']   = VirtualNode(_("Adhoc views"),   package)

    def nodeParent (self, node):
        #logger.warn("nodeparent %s", node)
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
        #logger.warn("nodechildren %s %s", type(node), node)
        children = []
        if isinstance (node, Annotation):
            children = []
        elif isinstance (node, Relation):
            children = []
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
            children = []
        elif isinstance (node, Query):
            children = []
        elif isinstance (node, Package):
            if not node in self.childrencache:
                self.childrencache[node] = [node.schemas, self.virtual['views'], node.queries, node.resources or _("No resources") ]
            children = self.childrencache[node]
        elif isinstance (node, AbstractBundle):
            children = node
        elif isinstance (node, Resources):
            if not node in self.childrencache:
                self.childrencache[node] = node.children()
            children = self.childrencache[node]
        elif isinstance (node, ResourceData):
            children = []
        elif node == self.virtual['views']:
            children=[ self.virtual['static'], self.virtual['dynamic'], self.virtual['adhoc'], self.virtual['admin'] ]
        elif node is []:
            children = [ self.get_package() ]
        else:
            children = []
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

    def update_element(self, e, created=False):
        """Update an element.

        This is called when a element has been modified or created.
        """
        parent=self.nodeParent(e)
        try:
            del (self.childrencache[parent])
        except KeyError:
            pass

    def remove_element (self, e):
        """Remove an element from the model.

        Return its parent node, so that we can update representations.
        """
        parent=None
        for p in self.childrencache:
            if e in self.childrencache[p]:
                parent=p
                break
        if parent is None:
            # Could not find the element in the cache.
            # It was not yet displayed
            pass
        else:
            del self.childrencache[parent]
        return parent

class FinderColumn(object):
    """Abstract FinderColumn class.
    """
    def __init__(self, controller=None, model=None, node=None, callback=None, parent=None):
        self.controller=controller
        self.model=model
        self.node=node
        self.callback=callback
        self.previous=parent
        self.next_column=None
        self.widget=Gtk.Frame()
        self.in_update = False
        self.widget.add(self.build_widget())
        self.widget.connect('key-press-event', self.key_pressed_cb)

    def key_pressed_cb(self, col, event):
        if event.keyval == Gdk.KEY_Right:
            # Next column
            if self.next_column is not None:
                self.next_column.get_focus()
            return True
        elif event.keyval == Gdk.KEY_Left:
            # Previous column
            if self.previous is not None:
                self.previous.get_focus()
            return True
        return False

    def get_focus(self):
        """Get the focus on the column.

        As we use a Gtk.Button at the top of every specialized
        ViewColumn, we want to use the second button.
        """
        b=self.get_child_buttons(self.widget)
        if len(b) >= 1:
            b[0].grab_focus()
        return True

    def get_child_buttons(self, w):
        """Return the buttons contained in the widget.
        """
        if isinstance(w, Gtk.Frame):
            w=w.get_children()[0]
        b=[]
        try:
            b=[ c for c in w.get_children() if isinstance(c, Gtk.Button) ]
        except AttributeError:
            return []
        for c in w.get_children():
            b.extend(self.get_child_buttons(c))
        return b

    def get_selected_annotation_widgets(self):
        return []

    def close(self):
        """Close this column, and all following ones.
        """
        logger.debug("Findercolumn.close")
        if self.next_column is not None:
            self.next_column.close()
        self.widget.destroy()
        if self.previous is not None:
            self.previous.next_column=None

    def get_name(self):
        return self.controller.get_title(self.node)
    name=property(fget=get_name, doc="Displayed name for the element")

    def update(self, node=None):
        logger.debug("FinderColumn.update %s", node)
        self.node=node
        return True

    def on_column_activation(self, widget):
        # Delete all next columns
        cb=self.next_column
        if cb:
            cb.close()
        self.next_column=None
        return True

    def build_widget(self):
        return Gtk.Label(label="Generic column for %s" % self.name)

class ModelColumn(FinderColumn):
    COLUMN_TITLE=0
    COLUMN_ELEMENT=1
    COLUMN_COLOR=2

    def get_valid_members(self, node):
        """Return the list of valid members for the element.
        """
        def title(el):
            t = self.controller.get_title(el)
            if isinstance(el, AnnotationType):
                return "%s (%d)" % (t, len(el.annotations))
            elif isinstance(el, RelationType):
                return "%s (%d)" % (t, len(el.relations))
            else:
                return t

        return [ (title(c),
                  c,
                  self.controller.get_element_color(c)) for c in self.model.nodeChildren(node) ]

    def get_selected_annotation_widgets(self):
        return []

    def get_focus(self):
        self.listview.grab_focus()
        return True

    def get_liststore(self):
        ls=Gtk.ListStore(str, object, str)
        if self.node is None:
            return ls
        for row in self.get_valid_members(self.node):
            ls.append(row)
        return ls

    def update(self, node=None):
        logger.debug("ModelColumn.update %s", node)
        self.in_update = True
        self.node=node
        self.liststore.clear()
        if self.node is None:
            return True
        self.column.set_title(self.controller.get_title(node))
        for row in self.get_valid_members(node):
            self.liststore.append(row)
        self.in_update = False
        self.on_changed_selection(None, self.model)

        if self.next_column is not None:
            # There is a next column. Should we still display it ?
            if not [ r
                     for r in self.liststore
                     if r[self.COLUMN_ELEMENT] == self.next_column.node ]:
                # The next node is no more in the current elements.
                self.next_column.close()
                self.next_column=None
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
        node = model.get_value(it, self.COLUMN_ELEMENT)
        widget.get_selection().select_path (path)
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            # Double-click: edit the element
            self.controller.gui.edit_element(node)
            return True
        elif event.button == 3:
            menu = advene.gui.popup.Menu(node, controller=self.controller)
            menu.popup()
            return True
        return False

    def on_changed_selection(self, selection, model):
        att=None
        if selection is not None:
            store, it = selection.get_selected()
            if it is not None:
                att = model.get_value (it, self.COLUMN_ELEMENT)
        if not self.in_update and att is not None and self.callback:
            self.callback(self, att)
            return True
        return False

    def on_treeview_button_press_event(self, treeview, event):
        if event.button == 1:
            x, y = treeview.get_pointer()
            row = treeview.get_dest_row_at_pos(int(x), int(y))
            if row is None:
                element=None
            else:
                element = treeview.get_model()[row[0]][self.COLUMN_ELEMENT]
            self.drag_data=(int(x), int(y), event, element)

    def on_treeview_button_release_event(self, treeview, event):
        self.drag_data=None
        self.drag_context=None

    def on_treeview_motion_notify_event(self, treeview, event):
        if (event.get_state() == Gdk.ModifierType.BUTTON1_MASK
            and self.drag_context is None
            and self.drag_data is not None
            and self.drag_data[3] is not None):
            x, y = treeview.get_pointer()
            threshold = treeview.drag_check_threshold(
                    self.drag_data[0], self.drag_data[1],
                    int(x), int(y))
            if threshold:
                # A drag was started. Setup the appropriate target.
                element=self.drag_data[3]
                targets = Gtk.TargetList.new(get_target_types(element))
                actions = Gdk.DragAction.MOVE | Gdk.DragAction.LINK | Gdk.DragAction.COPY
                button = 1
                self.drag_context = treeview.drag_begin_with_coordinates(targets, actions, button, event, -1, -1)
                contextual_drag_begin(treeview, self.drag_context, element, self.controller)
                self.drag_context._element=element

    def on_title_clicked(self, column):
        # Display metadata
        if self.callback:
            self.callback(self, Metadata(self.node, self.node.rootPackage))
        return True

    def own_drag_data_get_cb(self, treeview, context, selection, targetType, timestamp):
        model, paths = treeview.get_selection().get_selected_rows()

        els=[ model[p][self.COLUMN_ELEMENT] for p in paths ]

        context._element = els[0]
        drag_data_get_cb(treeview, context, selection, targetType, timestamp, self.controller)
        return True

    def build_widget(self):
        vbox=Gtk.VBox()

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.add (sw)

        self.liststore = self.get_liststore()
        self.listview = Gtk.TreeView(self.liststore)
        self.listview.container = self
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Attributes", renderer,
                                    text=self.COLUMN_TITLE,
                                    cell_background=self.COLUMN_COLOR)
        self.column = column
        column.set_title(self.get_name())
        column.set_clickable(True)
        column.connect('clicked', self.on_title_clicked)
        self.listview.append_column(column)

        selection = self.listview.get_selection()
        selection.unselect_all()
        selection.connect('changed', self.on_changed_selection, self.liststore)
        self.listview.connect('button-press-event', self.on_button_press)
        self.listview.connect('key-press-event', self.key_pressed_cb)

        self.drag_data=None
        self.drag_context=None
        self.listview.connect('button-press-event', self.on_treeview_button_press_event)
        self.listview.connect('button-release-event', self.on_treeview_button_release_event)
        self.listview.connect('motion-notify-event', self.on_treeview_motion_notify_event)
        self.listview.connect('drag-data-get', self.own_drag_data_get_cb)

        sw.add(self.listview)

        vbox.show_all()

        return vbox

class AnnotationColumn(FinderColumn):
    def update(self, node=None):
        self.node=node
        self.view.set_annotation(node)
        return True

    def get_selected_annotation_widgets(self):
        return []

    def build_widget(self):
        vbox=Gtk.VBox()

        self.view=AnnotationDisplay(controller=self.controller, annotation=self.node)
        vbox.add(self.view.widget)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Annotation]=AnnotationColumn

class RelationColumn(FinderColumn):
    def update(self, node=None):
        self.node=node
        self.view.set_relation(node)
        return True

    def build_widget(self):
        vbox=Gtk.VBox()

        self.view=RelationDisplay(controller=self.controller, relation=self.node)
        vbox.add(self.view.widget)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Relation]=RelationColumn

class ViewColumn(FinderColumn):
    def __init__(self, controller=None, model=None, node=None, callback=None, parent=None):
        self.element=node
        FinderColumn.__init__(self, controller, model, node, callback, parent)
        self.update(node)

    def update(self, node=None):
        self.node=node
        self.element = self.node

        self.label['title'].set_markup(_("View <b>%(title)s</b>\nId: %(id)s") % {
                'title': self.controller.get_title(self.element).replace('<', '&lt;'),
                'id': self.element.id })

        t=helper.get_view_type(self.element)
        self.label['activate'].set_sensitive(True)
        if t == 'static':
            self.label['activate'].set_label(_("Open in webbrowser"))
            self.label['info'].set_markup(_("View applied to %s\n") % self.element.matchFilter['class'])
            if not self.element.matchFilter['class'] in ('package', '*'):
                self.label['activate'].set_sensitive(False)
        elif t == 'dynamic':
            self.label['info'].set_text('')
            self.label['activate'].set_label(_("Activate"))
        elif t == 'adhoc':
            self.label['info'].set_text('')
            self.label['activate'].set_label(_("Open in GUI"))
        else:
            self.label['activate'].set_label(_("Unknown type of view??"))
            self.label['activate'].set_sensitive(False)
        return True

    def activate(self, *p):
        """Action to be executed.
        """
        t=helper.get_view_type(self.element)
        if t == 'static':
            c=self.controller.build_context()
            try:
                url=c.evaluateValue('here/view/%s/absolute_url' % self.element.id)
                self.controller.open_url(url)
            except:
                logger.warn("Cannot open static view: error when trying to get its url", exc_info=True)
        elif t == 'dynamic':
            self.controller.activate_stbv(self.element)
        elif t == 'adhoc':
            self.controller.gui.open_adhoc_view(self.element, destination='east')
        return True

    def build_widget(self):
        vbox=Gtk.VBox()
        self.label={}
        self.label['title']=Gtk.Label()
        vbox.pack_start(self.label['title'], False, True, 0)
        self.label['info']=Gtk.Label()
        vbox.pack_start(self.label['info'], False, True, 0)
        b=self.label['edit']=Gtk.Button(_("Edit view"))
        b.connect('clicked', lambda w: self.controller.gui.edit_element(self.element))
        # Enable DND
        def get_element():
            return self.element
        enable_drag_source(b, get_element, self.controller)

        vbox.pack_start(b, False, True, 0)

        b=self.label['activate']=Gtk.Button(_("Open view"))
        b.connect('clicked', self.activate)
        # Drag and drop for adhoc views

        def drag_data_get_cb(button, context, selection, targetType, timestamp):
            if targetType == config.data.target_type['adhoc-view']:
                if not isinstance(self.element, View):
                    return False
                if helper.get_view_type(self.element) != 'adhoc':
                    return False
                selection.set(selection.get_target(), 8,
                              urllib.parse.urlencode( {
                            'id': self.element.id,
                            } ).encode('utf8'))
                return True
            else:
                logger.warn("Unknown target type for drag: %d" % targetType)
            return True

        b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                          config.data.get_target_types('adhoc-view'),
                          Gdk.DragAction.LINK | Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        b.connect('drag-data-get', drag_data_get_cb)

        vbox.pack_start(b, False, True, 0)

        vbox.show_all()
        return vbox
CLASS2COLUMN[View]=ViewColumn

class QueryColumn(FinderColumn):
    def __init__(self, controller=None, model=None, node=None, callback=None, parent=None):
        self.element=node
        FinderColumn.__init__(self, controller, model, node, callback, parent)
        self.update(node)

    def update(self, node=None):
        self.node=node
        self.element=self.node

        self.label['title'].set_markup(_("%(type)s <b>%(title)s</b>\nId: %(id)s") % {
                'type': helper.get_type(self.element),
                'title': self.controller.get_title(self.element).replace('<', '&lt;'),
                'id': self.element.id })
        # Reset the sensitive state on apply buttons
        for b in self.apply_buttons:
            b.set_sensitive(True)
        return True

    def build_widget(self):
        vbox=Gtk.VBox()
        self.label={}
        self.label['title']=Gtk.Label()
        vbox.pack_start(self.label['title'], False, True, 0)

        b=self.label['edit']=Gtk.Button(_("Edit query"))
        # Enable DND
        def get_element():
            return self.element
        enable_drag_source(b, get_element, self.controller)
        b.connect('clicked', lambda w: self.controller.gui.edit_element(self.element))
        vbox.pack_start(b, False, True, 0)

        f=Gtk.Frame.new(_("Try to apply the query on..."))
        v=Gtk.VBox()
        f.add(v)

        def try_query(b, expr):
            try:
                res, q = self.controller.evaluate_query(self.element, expr=expr)
                self.controller.gui.open_adhoc_view('interactiveresult',
                                                    query=self.element,
                                                    result=res,
                                                    destination='east')
            except Exception:
                logger.debug("Exception in query evaluation", exc_info=True)
                b.set_sensitive(False)
            return True

        self.apply_buttons=[]
        for (expr, label) in (
             ('package', _("the package")),
             ('package/annotations', _("all annotations of the package")),
             ('package/annotations/first', _("the first annotation of the package")),
            ):
            b=Gtk.Button(label, use_underline=False)
            b.connect('clicked', try_query, expr)
            v.pack_start(b, False, True, 0)
            self.apply_buttons.append(b)

        vbox.add(f)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Query]=QueryColumn

class ResourceColumn(FinderColumn):
    def __init__(self, controller=None, model=None, node=None, callback=None, parent=None):
        self.element=node
        FinderColumn.__init__(self, controller, model, node, callback, parent)
        self.update(node)

    def update(self, node=None):
        self.node=node
        self.element=self.node
        self.label['title'].set_markup(_("%(type)s <b>%(title)s</b>\nId: %(id)s") % {
                'type': helper.get_type(self.element),
                'title': self.controller.get_title(self.element).replace('<', '&lt;'),
                'id': self.element.id })
        self.update_preview()
        return True

    def update_preview(self):
        self.preview.foreach(self.preview.remove)
        if self.element.mimetype.startswith('image/'):
            i=Gtk.Image()
            pixbuf=GdkPixbuf.Pixbuf.new_from_file(self.element.file_)
            i.set_from_pixbuf(pixbuf)
            self.preview.add(i)
            i.show()
        # FIXME: if self.element.mimetype.startswith('audio/'):
        # Add play icon
        return True

    def build_widget(self):
        vbox=Gtk.VBox()
        self.label={}
        self.label['title']=Gtk.Label()
        vbox.pack_start(self.label['title'], False, True, 0)
        b=self.label['edit']=Gtk.Button(_("Edit resource"))
        # Enable DND
        def get_element():
            return self.element
        enable_drag_source(b, get_element, self.controller)
        b.connect('clicked', lambda w: self.controller.gui.edit_element(self.element))
        vbox.pack_start(b, False, True, 0)
        self.preview=Gtk.VBox()
        vbox.add(self.preview)
        vbox.show_all()
        return vbox
CLASS2COLUMN[ResourceData]=ResourceColumn

class MetadataColumn(FinderColumn):
    def update(self, node=None):
        self.node=node
        return True

    def build_widget(self):
        el = self.node.element
        vbox=Gtk.VBox()

        info = Gtk.TextView()
        info.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        def set_text(widget, t):
            b=widget.get_buffer()
            b.delete(*b.get_bounds())
            b.set_text(t)
            b.set_modified(False)
            return True
        info.set_text = set_text.__get__(info)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        if isinstance(el, Package):
            info.set_text(_("""Package %(title)s:
%(schema)s
%(annotation)s in %(annotation_type)s
%(relation)s in %(relation_type)s
%(query)s
%(view)s

Description:
%(description)s

Annotation statistics:
%(statistics)s
""") % {
        'title': el.title,
        'schema': helper.format_element_name('schema', len(el.schemas)),
        'annotation': helper.format_element_name('annotation', len(el.annotations)),
        'annotation_type': helper.format_element_name('annotation_type', len(el.annotationTypes)),
        'relation': helper.format_element_name('relation', len(el.relations)),
        'relation_type': helper.format_element_name('relation_type', len(el.relationTypes)),
        'query': helper.format_element_name('query', len(el.queries)),
        'view': helper.format_element_name('view', len(el.views)),
        'description': el.getMetaData(config.data.namespace_prefix['dc'], 'description'),
        'statistics': helper.get_annotations_statistics(el.annotations)
        })
        elif isinstance(el, AnnotationType):
            info.set_text(_("""%(type)s %(title)s\n%(statistics)s""") % ({
                "type": helper.get_type(el),
                "title": self.controller.get_title(el),
                "statistics": helper.get_annotations_statistics(el.annotations)
            }))
        else:
            info.set_text(_("""%(type)s %(title)s""") % ({"type": helper.get_type(el),
                                                          "title": self.controller.get_title(el)}))

        frame = Gtk.Expander.new(_("Metadata"))
        frame.set_expanded(False)
        self.view = EditWidget(self.node.set_config, self.node.get_config)
        for p in self.node.list_keys():
            self.view.add_entry(p, p, "")

        sw.add(info)
        vbox.add(sw)
        frame.add(self.view)
        vbox.pack_start(frame, False, False, 0)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Metadata] = MetadataColumn

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
        # 640 / 3
        self.column_width=210
        self.rootcolumn=None
        self.widget=self.build_widget()

    def refresh(self):
        c=self.rootcolumn
        c.update(c.node)
        while c.next_column is not None:
            c=c.next_column
            c.update(c.node)
        return True

    def update_element(self, element=None, event=None):
        logger.debug("update_element %s %s", event, element)
        if event.endswith('Create'):
            self.model.update_element(element, created=True)
            self.refresh()
        elif event.endswith('EditEnd'):
            self.model.update_element(element, created=False)
            self.refresh()
        elif event.endswith('Delete'):
            parent = self.model.remove_element(element)
            if parent is not None:
                cb=self.rootcolumn.next_column
                while cb is not None:
                    if cb.node == parent:
                        cb.update(node=cb.node)
                        if cb.next_column is not None and cb.next_column.node == element:
                            cb.next_column.close()
                    cb=cb.next_column
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

    def update_model(self, package=None):
        if package is None:
            package = self.controller.package

        # Reset to the rootcolumn
        cb=self.rootcolumn.next_column
        while cb is not None:
            cb.widget.destroy()
            cb=cb.next_column
        self.rootcolumn.next_column=None

        self.package = package
        self.model=DetailedTreeModel(controller=self.controller, package=package)

        # Update the rootcolumn element
        self.rootcolumn.update(package)
        return True

    def clicked_callback(self, columnbrowser, node):
        logger.debug("clicked_callback %s %s %s", columnbrowser, node, columnbrowser.next_column)
        if columnbrowser is None:
            # We selected  the rootcolumn. Delete the next ones
            cb=self.rootcolumn.next_column
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next_column
            self.rootcolumn.next_column=None
        elif columnbrowser.next_column is None:
            t=type(node)
            clazz=CLASS2COLUMN.get(t, ModelColumn)
            # Create a new columnbrowser
            col=clazz(controller=self.controller,
                      model=self.rootcolumn.model,
                      node=node,
                      callback=self.clicked_callback,
                      parent=columnbrowser)
            col.widget.set_property("width-request", self.column_width)
            self.hbox.pack_start(col.widget, False, True, 0)
            col.widget.show_all()
            columnbrowser.next_column=col
        else:
            # Delete all next+1 columns (we reuse the next one)
            cb=columnbrowser.next_column.next_column
            if cb is not None:
                cb.close()
            # Check if the column is still appropriate for the node
            clazz=CLASS2COLUMN.get(type(node), None)
            if clazz is None or not isinstance(columnbrowser.next_column, clazz):
                # The column is not appropriate for the new node.
                # Close it and reopen it.
                columnbrowser.next_column.close()
                self.clicked_callback(columnbrowser, node)
            else:
                columnbrowser.next_column.update(node)

        # Scroll the columns
        GObject.timeout_add(100, lambda: self.autoscroll_end() and False)
        return True

    def autoscroll_end(self):
        adj=self.sw.get_hadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return True

    def scroll_event(self, widget=None, event=None):
        a=widget.get_hadjustment()
        if ((event.direction == Gdk.ScrollDirection.DOWN and event.get_state() & Gdk.ModifierType.SHIFT_MASK)
            or event.direction == Gdk.ScrollDirection.RIGHT):
            val = a.get_value() + a.get_step_increment()
            if val > a.get_upper() - a.get_page_size():
                val = a.get_upper() - a.get_page_size()
            if val != a.get_value():
                a.set_value(val)
                a.value_changed ()
            return True
        elif ((event.direction == Gdk.ScrollDirection.UP and event.get_state() & Gdk.ModifierType.SHIFT_MASK)
              or event.direction == Gdk.ScrollDirection.LEFT):
            val = a.get_value() - a.get_step_increment()
            if val < a.get_lower():
                val = a.get_lower()
            if val != a.get_value():
                a.set_value(val)
                a.value_changed ()
            return True
        return False

    def build_widget(self):
        vbox=Gtk.VBox()

        self.sw=Gtk.ScrolledWindow()
        self.sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.sw.connect('scroll-event', self.scroll_event)
        vbox.add(self.sw)

        self.hbox = Gtk.HBox()

        self.rootcolumn=ModelColumn(controller=self.controller,
                                    model=self.model,
                                    node=self.package,
                                    callback=self.clicked_callback,
                                    parent=None)
        self.rootcolumn.widget.set_property("width-request", self.column_width)
        self.hbox.pack_start(self.rootcolumn.widget, False, True, 0)

        self.sw.add_with_viewport(self.hbox)

        vbox.show_all()
        return vbox
