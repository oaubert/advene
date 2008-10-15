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

# Advene finder, a la MacOS X

from gettext import gettext as _

import gtk
import cgi

import advene.core.config as config

from advene.gui.views import AdhocView
from advene.gui.views.annotationdisplay import AnnotationDisplay
from advene.gui.views.relationdisplay import RelationDisplay
from advene.model.cam.tag import AnnotationType, RelationType
from advene.model.cam.annotation import Annotation
from advene.model.cam.relation import Relation
from advene.model.cam.view import View
from advene.model.cam.resource import Resource
from advene.model.cam.query import Query
from advene.model.cam.media import Media
import advene.rules.elements
import advene.gui.popup
import advene.util.helper as helper

name="Package finder view plugin"

def register(controller):
    controller.register_viewclass(Finder)

# Matching between element classes and the FinderColumn class
CLASS2COLUMN={}

class Node(object):
    """A data node.
    """
    def __init__(self, element=None, title=""):
        self.element=element
        self.title=title

    def children(self):
        return []

class ListNode(Node):
    def children(self):
        # FIXME: Should return different nodes based on type(e)
        for e in self.element:
            if hasattr(e, '__iter__'):
                yield ListNode(e)
            else:
                yield Node(e)

class ViewsNode(Node):
    """Classifies views among static/dynamic/adhoc/administrative.
    """
    def children(self):
        yield ListNode( [ v for v in self.element if helper.get_view_type(v) == 'static' and not v.id.startswith('_')], _("Static views"))
        yield ListNode( [ v for v in self.element if helper.get_view_type(v) == 'dynamic' and not v.id.startswith('_') ], _("Dynamic views"))
        yield ListNode( [ v for v in self.element if helper.get_view_type(v) == 'adhoc' and not v.id.startswith('_') ], _("Adhoc views"))
        yield ListNode( [ v for v in self.element if v.id.startswith('_') ], _("Admin views"))

class GroupNode(Node):
    def children(self):
        l=dir(self.element)
        for (attname, label) in (
            ('annotations', _("Annotations")),
            ('relations', _("Relations")),
            ('schemas', _("Schemas")),
            ('annotation_types', _("Annotation types")),
            ('relation_types', _("Relation types")),
            ('medias', _("Medias")),
            ('queries', _("Queries")),
            ('views', _("Views")),
            ('user_tags', _("Tags")),
            ):
            if attname in l:
                if attname == 'views':
                    yield ViewsNode(self.element.views, label)
                else:
                    yield ListNode(getattr(self.element, attname), label)

class PackageNode(Node):
    def children(self):
        # FIXME: there should maybe be an option to select either
        # always all, or both.
        yield GroupNode(self.element.all, _("All elements"))
        yield GroupNode(self.element.own, _("Own elements"))

class FinderColumn(object):
    """Abstract FinderColumn class.
    """
    def __init__(self, controller=None, node=None, callback=None, parent=None):
        self.controller=controller
        self.node=node
        self.callback=callback
        self.previous=parent
        self.next=None
        self.widget=self.build_widget()
        self.widget.connect('key-press-event', self.key_pressed_cb)

    def key_pressed_cb(self, col, event):
        if event.keyval == gtk.keysyms.Right:
            # Next column
            if self.next is not None:
                self.next.get_focus()
            return True
        elif event.keyval == gtk.keysyms.Left:
            # Previous column
            if self.previous is not None:
                self.previous.get_focus()
            return True
        return False

    def get_focus(self):
        """Get the focus on the column.

        As we use a gtk.Button at the top of every specialized
        ViewColumn, we want to use the second button.
        """
        b=self.get_child_buttons(self.widget)
        if len(b) >= 2:
            b[1].grab_focus()
        return True

    def get_child_buttons(self, w):
        """Return the buttons contained in the widget.
        """
        b=[]
        try:
            b=[ c for c in w.get_children() if isinstance(c, gtk.Button) ]
        except AttributeError:
            return []
        for c in w.get_children():
            b.extend(self.get_child_buttons(c))
        return b

    def close(self):
        """Close this column, and all following ones.
        """
        if self.next is not None:
            self.next.close()
        self.widget.destroy()
        if self.previous is not None:
            self.previous.next=None

    def get_name(self):
        if self.node is None:
            return "FIXME"
        return self.node.title or self.controller.get_title(self.node.element)
    name=property(fget=get_name, doc="Displayed name for the element")

    def update(self, node=None):
        self.node=node
        return True

    def build_widget(self):
        return gtk.Label("Generic finder column")

class ModelColumn(FinderColumn):
    COLUMN_TITLE=0
    COLUMN_NODE=1
    COLUMN_COLOR=2

    def get_valid_members(self):
        """Return the list of valid members for the element.
        """
        def title(c):
            el=c.element
            if isinstance(el, AnnotationType):
                return "(%d) %s" % (len(el.annotations), c.title or self.controller.get_title(el))
            elif isinstance(el, RelationType):
                return "(%d) %s" % (len(el.relations), c.title or self.controller.get_title(el))
            else:
                return c.title or self.controller.get_title(c.element)

        return [ (title(n),
                  n,
                  self.controller.get_element_color(n.element)) for n in self.node.children() ]

    def get_focus(self):
        self.listview.grab_focus()
        return True

    def get_liststore(self):
        ls=gtk.ListStore(str, object, str)
        if self.node is None:
            return ls
        for row in self.get_valid_members():
            ls.append(row)
        return ls

    def update(self, node=None):
        self.node=node
        self.liststore.clear()
        if self.node is None:
            return True
        self.label.set_label(self.name or self.node.title)
        col=self.controller.get_element_color(self.node.element)
        if col:
            try:
                color=gtk.gdk.color_parse(col)
                style = self.label.modify_bg(gtk.STATE_NORMAL, color)
            except ValueError:
                pass

        for row in self.get_valid_members():
            self.liststore.append(row)

        if self.next is not None:
            # There is a next column. Should we still display it ?
            if not [ r
                     for r in self.liststore
                     if r[self.COLUMN_NODE].element == self.next.node.element ]:
                # The next node is no more in the current elements.
                self.next.close()
                self.next=None
        return True

    def on_column_activation(self, widget):
        # Delete all next columns
        cb=self.next
        if cb:
            cb.close()
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
        node = model.get_value(it, self.COLUMN_NODE)
        widget.get_selection().select_path (path)
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            # Double-click: edit the element
            self.controller.gui.edit_element(node.element)
            return True
        elif event.button == 3:
            menu = advene.gui.popup.Menu(node.element, controller=self.controller)
            menu.popup()
            return True
        return False

    def on_changed_selection(self, selection, model):
        att=None
        if selection is not None:
            store, it = selection.get_selected()
            if it is not None:
                att = model.get_value(it, self.COLUMN_NODE)
        if att and self.callback:
            self.callback(self, att)
            return True
        return False

    def build_widget(self):
        vbox=gtk.VBox()

        self.label=gtk.Button(self.name, use_underline=False)
        col=self.controller.get_element_color(self.node.element)
        if col:
            try:
                color=gtk.gdk.color_parse(col)
                style = self.label.modify_bg(gtk.STATE_NORMAL, color)
            except ValueError:
                pass
        self.label.connect('clicked', self.on_column_activation)
        vbox.pack_start(self.label, expand=False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_ALWAYS, gtk.POLICY_AUTOMATIC)
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
        self.listview.connect('button-press-event', self.on_button_press)
        self.listview.connect('key-press-event', self.key_pressed_cb)

        sw.add(self.listview)

        vbox.show_all()

        return vbox

class AnnotationColumn(FinderColumn):
    def update(self, node=None):
        self.node=node
        self.view.set_annotation(node.element)
        return True

    def build_widget(self):
        vbox=gtk.VBox()

        l=gtk.Button(_("Annotation"), use_underline=False)
        vbox.pack_start(l, expand=False)
        self.view=AnnotationDisplay(controller=self.controller, annotation=self.node.element)
        vbox.add(self.view.widget)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Annotation]=AnnotationColumn

class RelationColumn(FinderColumn):
    def update(self, node=None):
        self.node=node
        self.view.set_relation(node.element)
        return True

    def build_widget(self):
        vbox=gtk.VBox()

        l=gtk.Button(_("Relation"), use_underline=False)
        vbox.pack_start(l, expand=False)
        self.view=RelationDisplay(controller=self.controller, relation=self.node.element)
        vbox.add(self.view.widget)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Relation]=RelationColumn

class ViewColumn(FinderColumn):
    def __init__(self, controller=None, node=None, callback=None, parent=None):
        FinderColumn.__init__(self, controller, node, callback, parent)
        self.element=self.node.element
        self.update(node)

    def update(self, node=None):
        self.node=node
        self.element=self.node.element

        self.label['title'].set_markup(_("View <b>%(title)s</b>\nId: %(id)s") % {
                'title': self.controller.get_title(self.element),
                'id': self.element.id })

        t=helper.get_view_type(self.element)
        self.label['activate'].set_sensitive(True)
        if t == 'static':
            self.label['activate'].set_label(_("Open in webbrowser"))
            # FIXME: check toplevel metadata
            #if not self.element.matchFilter['class'] in ('package', '*'):
            #    self.label['activate'].set_sensitive(False)
        elif t == 'dynamic':
            self.label['activate'].set_label(_("Activate"))
        elif t == 'adhoc':
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
            url=c.evaluate('here/absolute_url') + '/view/' % self.element.id
            self.controller.open_url(url)
        elif t == 'dynamic':
            self.controller.activate_stbv(self.element)
        elif t == 'adhoc':
            self.controller.gui.open_adhoc_view(self.element, destination='east')
        return True

    def build_widget(self):
        vbox=gtk.VBox()
        vbox.pack_start(gtk.Button(_("View")), expand=False)
        self.label={}
        self.label['title']=gtk.Label()
        vbox.pack_start(self.label['title'], expand=False)
        b=self.label['edit']=gtk.Button(_("Edit view"))
        b.connect('clicked', lambda w: self.controller.gui.edit_element(self.element))
        vbox.pack_start(b, expand=False)

        b=self.label['activate']=gtk.Button(_("Open view"))
        b.connect('clicked', self.activate)
        # Drag and drop for adhoc views

        def drag_data_get_cb(button, context, selection, targetType, timestamp):
            if targetType == config.data.target_type['adhoc-view']:
                if not isinstance(self.element, View):
                    return False
                if helper.get_view_type(self.element) != 'adhoc':
                    return False
                selection.set(selection.target, 8,
                              cgi.urllib.urlencode( {
                            'id': self.element.id,
                            } ).encode('utf8'))
                return True
            else:
                print "Unknown target type for drag: %d" % targetType
            return True

        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['adhoc-view'],
                          gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        b.connect('drag-data-get', drag_data_get_cb)

        vbox.pack_start(b, expand=False)

        vbox.show_all()
        return vbox
CLASS2COLUMN[View]=ViewColumn

class QueryColumn(FinderColumn):
    def __init__(self, controller=None, node=None, callback=None, parent=None):
        FinderColumn.__init__(self, controller, node, callback, parent)
        self.element=self.node.element
        self.update(node)

    def update(self, node=None):
        self.node=node
        self.element=self.node.element

        self.label['title'].set_markup(_("%(type)s <b>%(title)s</b>\nId: %(id)s") % {
                'type': helper.get_type(self.element),
                'title': self.controller.get_title(self.element),
                'id': self.element.id })
        # Reset the sensitive state on apply buttons
        for b in self.apply_buttons:
            b.set_sensitive(True)
        return True

    def build_widget(self):
        vbox=gtk.VBox()
        vbox.pack_start(gtk.Button(_("Query")), expand=False)
        self.label={}
        self.label['title']=gtk.Label()
        vbox.pack_start(self.label['title'], expand=False)

        b=self.label['edit']=gtk.Button(_("Edit query"))
        b.connect('clicked', lambda w: self.controller.gui.edit_element(self.element))
        vbox.pack_start(b, expand=False)

        f=gtk.Frame(_("Try to apply the query on..."))
        v=gtk.VBox()
        f.add(v)

        def try_query(b, expr):
            try:
                res, q = self.controller.evaluate_query(self.element, expr=expr)
                self.controller.gui.open_adhoc_view('interactiveresult',
                                                    query=self.element,
                                                    result=res,
                                                    destination='east')
            except Exception, e:
                #print "********** Oops"
                #import traceback
                #traceback.print_exc()
                b.set_sensitive(False)
            return True

        self.apply_buttons=[]
        for (expr, label) in (
             ('package', _("the package")),
             ('package/all/annotations', _("all annotations of the package")),
             ('package/all/annotations/first', _("the first annotation of the package")),
            ):
            b=gtk.Button(label, use_underline=False)
            b.connect('clicked', try_query, expr)
            v.pack_start(b, expand=False)
            self.apply_buttons.append(b)

        vbox.add(f)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Query]=QueryColumn

class ResourceColumn(FinderColumn):
    def __init__(self, controller=None, node=None, callback=None, parent=None):
        FinderColumn.__init__(self, controller, node, callback, parent)
        self.element=self.node.element
        self.update(node)

    def update(self, node=None):
        self.node=node
        self.element=self.node.element
        self.label['title'].set_markup(_("%(type)s <b>%(title)s</b>\nId: %(id)s") % {
                'type': helper.get_type(self.element),
                'title': self.controller.get_title(self.element),
                'id': self.element.id })
        self.update_preview()
        return True

    def update_preview(self):
        self.preview.foreach(self.preview.remove)
        if self.element.mimetype.startswith('image/'):
            i=gtk.Image()
            pixbuf=gtk.gdk.pixbuf_new_from_file(self.element.file_)
            i.set_from_pixbuf(pixbuf)
            self.preview.add(i)
            i.show()
        return True

    def build_widget(self):
        vbox=gtk.VBox()
        self.label={}
        self.label['title']=gtk.Label()
        vbox.pack_start(self.label['title'], expand=False)
        b=self.label['edit']=gtk.Button(_("Edit resource"))
        b.connect('clicked', lambda w: self.controller.gui.edit_element(self.element))
        vbox.pack_start(b, expand=False)
        self.preview=gtk.VBox()
        vbox.add(self.preview)
        vbox.show_all()
        return vbox
CLASS2COLUMN[Resource]=ResourceColumn

class MediaColumn(FinderColumn):
    def update(self, node=None):
        self.node=node
        self.id_label.set_text(self.node.element.id)
        self.url_label.set_text(self.node.element.url)
        return True

    def build_widget(self):
        vbox=gtk.VBox()

        l=gtk.Button(_("Media"), use_underline=False)
        vbox.pack_start(l, expand=False)
        self.id_label=gtk.Label(self.node.element.id)
        self.url_label=gtk.Label(self.node.element.url)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_('Id')), expand=False)
        hb.pack_start(self.id_label)
        vbox.pack_start(hb, expand=False)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_('URL')), expand=False)
        hb.pack_start(self.url_label)
        vbox.pack_start(hb, expand=False)

        vbox.show_all()
        return vbox
CLASS2COLUMN[Media]=MediaColumn

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

        self.model=PackageNode(self.package)
        # 640 / 3
        self.column_width=210
        self.rootcolumn=None
        self.widget=self.build_widget()

    def refresh(self):
        c=self.rootcolumn
        c.update(c.node)
        while c.next is not None:
            c=c.next
            c.update(c.node)
        return True

    def update_element(self, element=None, event=None):
        if event.endswith('Create'):
            #self.model.update_element(element, created=True)
            self.refresh()
        elif event.endswith('EditEnd'):
            #self.model.update_element(element, created=False)
            self.refresh()
        elif event.endswith('Delete'):
            #self.model.remove_element(element)
            cb=self.rootcolumn.next
            while cb is not None:
                if [ r
                     for r in cb.liststore
                     if r[ModelColumn.COLUMN_NODE].element == element ]:
                    # The element is present in the list of
                    # children. Remove the next column if necessary
                    # and update the children list.
                    cb.update(node=cb.node)
                    if cb.next is not None and cb.next.node.element == element:
                        cb.next.close()

                cb=cb.next
            #self.update_model(element.rootPackage)
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
        cb=self.rootcolumn.next
        while cb is not None:
            cb.widget.destroy()
            cb=cb.next
        self.rootcolumn.next=None

        self.package=package
        self.model=PackageNode(self.package)

        # Update the rootcolumn element
        self.rootcolumn.update(self.model)
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
            t=type(node.element)
            clazz=CLASS2COLUMN.get(t, ModelColumn)
            # Create a new columnbrowser
            col=clazz(controller=self.controller,
                      node=node,
                      callback=self.clicked_callback,
                      parent=columnbrowser)
            col.widget.set_property("width-request", self.column_width)
            self.hbox.pack_start(col.widget, expand=False)
            columnbrowser.next=col
        else:
            # Delete all next+1 columns (we reuse the next one)
            cb=columnbrowser.next.next
            if cb is not None:
                cb.close()
            # Check if the column is still appropriate for the node
            clazz=CLASS2COLUMN.get(type(node.element), ModelColumn)
            if not isinstance(columnbrowser.next, clazz):
                # The column is not appropriate for the new node.
                # Close it and reopen it.
                columnbrowser.next.close()
                self.clicked_callback(columnbrowser, node)
            else:
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

        self.sw.connect('scroll-event', self.scroll_event)
        vbox.add(self.sw)

        self.hbox = gtk.HBox()

        self.rootcolumn=ModelColumn(controller=self.controller,
                                     node=self.model,
                                     callback=self.clicked_callback,
                                     parent=None)
        self.rootcolumn.widget.set_property("width-request", self.column_width)
        self.hbox.pack_start(self.rootcolumn.widget, expand=False)

        self.sw.add_with_viewport(self.hbox)

        vbox.show_all()
        return vbox
