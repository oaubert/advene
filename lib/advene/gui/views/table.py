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
import logging
logger = logging.getLogger(__name__)

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
import csv

from gettext import gettext as _

import advene.core.config as config

from advene.model.annotation import Annotation
from advene.gui.views import AdhocView

import advene.gui.edit.elements
import advene.gui.popup

import advene.util.helper as helper
from advene.gui.util import dialog, png_to_pixbuf, contextual_drag_begin, contextual_drag_end

COLUMN_ELEMENT=0
COLUMN_CONTENT=1
COLUMN_TYPE=2
COLUMN_ID=3
COLUMN_BEGIN=4
COLUMN_END=5
COLUMN_DURATION=6
COLUMN_BEGIN_FORMATTED=7
COLUMN_END_FORMATTED=8
COLUMN_PIXBUF=9
COLUMN_COLOR=10
COLUMN_SOURCE_PACKAGE=11
COLUMN_CUSTOM_FIRST=12

name="Element tabular view plugin"

def register(controller):
    controller.register_viewclass(AnnotationTable)
    controller.register_viewclass(GenericTable)

class AnnotationTable(AdhocView):
    view_name = _("Annotation table view")
    view_id = 'table'
    tooltip=_("Display annotations in a table")

    def __init__(self, controller=None, parameters=None, custom_data=None, elements=None, source=None):
        """We can initialize the table using either a list of elements, or  a TALES source expression.

        If both are specified, the list of elements takes precedence.
        """
        super(AnnotationTable, self).__init__(controller=controller)
        self.registered_rules = []
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Export as CSV"), self.csv_export),
            )
        self.controller=controller

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        a=dict(arg)
        if source is None and 'source' in a:
            source=a['source']

        self.source = source
        if elements is None and source:
            elements = self.get_elements_from_source(source)

        self.elements = elements
        self.options={ 'confirm-time-update': True }

        self.mouseover_annotation = None
        self.last_edited_path = None

        self.model = self.build_model(elements, custom_data)
        self.widget = self.build_widget()

        self.registered_rules.append( controller.event_handler.internal_rule (event="SnapshotUpdate",
                                                                              method=self.update_snapshot)
                                      )
        def unregister(*p):
            for r in self.registered_rules:
                self.controller.event_handler.remove_rule(r, type_="internal")
        self.widget.connect('destroy', unregister)

    def get_save_arguments(self):
        if self.source is not None:
            arguments = [ ('source', self.source) ]
        else:
            arguments = []
        return self.options, arguments

    def update_annotation(self, annotation=None, event=None):
        if self.source:
            # Re-evaluate source parameter, in case the annotation was
            # created.
            elements = self.get_elements_from_source(self.source)
        else:
            elements = self.elements

        if elements is not None and (annotation in elements or event.endswith('Delete')):
            self.set_elements(elements)

    def update_snapshot(self, context, parameters):
        pos = int(context.globals['position'])
        media = context.globals['media']
        eps = self.controller.package.imagecache.precision
        for r in self.widget.treeview.get_model():
            if (r[COLUMN_ELEMENT].media == media
                and abs(r[COLUMN_BEGIN] - pos) <= eps):
                # Update pixbuf
                r[COLUMN_PIXBUF] = png_to_pixbuf(self.controller.package.imagecache[pos],
                                                 height=32)

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

    def build_model(self, elements, custom_data=None):
        """Build the ListStore containing the data.

        See set_element docstring for the custom_data method explanation.
        """
        if custom_data is not None:
            custom = custom_data
        else:
            def custom(a):
                return tuple()
        args = (object, str, str, str, int, int, str, str, str, GdkPixbuf.Pixbuf, str, str) + custom(None)
        l=Gtk.ListStore(*args)
        if not elements:
            return l
        for a in elements:
            if isinstance(a, Annotation):
                l.append( (a,
                           self.controller.get_title(a),
                           self.controller.get_title(a.type),
                           a.id,
                           a.fragment.begin,
                           a.fragment.end,
                           helper.format_time(a.fragment.duration),
                           helper.format_time(a.fragment.begin),
                           helper.format_time(a.fragment.end),
                           png_to_pixbuf(self.controller.get_snapshot(annotation=a),
                                         height=32),
                           self.controller.get_element_color(a),
                           a.ownerPackage.getTitle()
                           ) + custom(a),
                          )
        return l

    def set_elements(self, elements, custom_data=None):
        """Use a new set of elements.

        If custom_data is not None, then it is a function returning
        tuples, that can be used to defined additional model columns.

        When called with None as parameter, it must return a tuple
        with the additional column types. It will be appended at the
        end of the ListStore, in columns COLUMN_CUSTOM_FIRST,
        COLUMN_CUSTOM_FIRST+1, etc.

        When called with an annotation as parameter, it must return a
        tuple with the appropriate values for the annotation in the
        custom columns.
        """
        if elements is None:
            elements = []
        model=self.build_model(elements, custom_data)
        self.widget.treeview.set_model(model)
        self.model = model
        self.elements=elements
        if self.last_edited_path is not None:
            # We just edited an annotation. This update must come from
            # it, so let us try to set the cursor position at the next element.
            path = self.last_edited_path.next()
            try:
                self.model.get_iter(path)
            except (ValueError, TypeError):
                path = self.last_edited_path
            self.widget.treeview.set_cursor(path,
                                            self.columns['id'],
                                            True)
            self.last_edited_path = None

    def motion_notify_event_cb(self, tv, event):
        if not event.get_window() is tv.get_bin_window():
            return False
        if event.is_hint:
            pointer = event.get_window().get_pointer()
            x = pointer.x
            y = pointer.y
        else:
            x = int(event.x)
            y = int(event.y)
        t = tv.get_path_at_pos(x, y)
        if t is not None:
            path, col, cx, cy = t
            it = self.model.get_iter(path)
            ann = self.model.get_value(it,
                                       COLUMN_ELEMENT)
            if self.mouseover_annotation != ann:
                # Update
                if self.mouseover_annotation is not None:
                    self.controller.notify('BookmarkUnhighlight', timestamp=self.mouseover_annotation.fragment.begin, media=self.mouseover_annotation.media, immediate=True)
                self.controller.notify('BookmarkHighlight', timestamp=ann.fragment.begin, media=ann.media, immediate=True)
                self.mouseover_annotation = ann
        return False

    def leave_notify_event_cb(self, tv, event):
        if self.mouseover_annotation is not None:
            self.controller.notify('BookmarkUnhighlight', timestamp=self.mouseover_annotation.fragment.begin, media=self.mouseover_annotation.media, immediate=True)
            self.mouseover_annotation = None
        return False

    def build_widget(self):
        tree_view = Gtk.TreeView(self.model)

        select = tree_view.get_selection()
        select.set_mode(Gtk.SelectionMode.MULTIPLE)

        tree_view.connect('button-press-event', self.tree_view_button_cb)
        tree_view.connect('key-press-event', self.tree_view_key_cb)
        tree_view.connect('row-activated', self.row_activated_cb)
        tree_view.connect('motion-notify-event', self.motion_notify_event_cb)
        tree_view.connect('leave-notify-event', self.leave_notify_event_cb)
        # Deactivate starting search by simply typing. Users have to use the search shortcut (Control-F)
        tree_view.set_enable_search(False)

        def search_content(model, column, key, it):
            if key in model.get_value(it, COLUMN_CONTENT):
                return False
            return True

        tree_view.set_search_equal_func(search_content)

        columns={}

        columns['snapshot']=Gtk.TreeViewColumn(_("Snapshot"), Gtk.CellRendererPixbuf(), pixbuf=COLUMN_PIXBUF)
        columns['snapshot'].set_reorderable(True)
        tree_view.append_column(columns['snapshot'])

        def cell_edited(cell, path_string, text):
            it = self.model.get_iter_from_string(path_string)
            if not it:
                return
            a = self.model.get_value (it, COLUMN_ELEMENT)
            new_content = helper.title2content(text,
                                               a.content,
                                               a.type.getMetaData(config.data.namespace, "representation"))
            if new_content is None:
                self.log(_("Cannot update the annotation, its representation is too complex"))
            elif a.content.data != new_content:
                self.last_edited_path = Gtk.TreePath.new_from_string(path_string)
                self.controller.notify('EditSessionStart', element=a)
                a.content.data = new_content
                self.controller.notify('AnnotationEditEnd', annotation=a)
                self.controller.notify('EditSessionEnd', element=a)
            return True

        def validate_entry_on_focus_out(widget, event, cell, path):
            cell.emit("edited", path, widget.get_text())
            return True

        def entry_editing_started(cell, editable, path):
            if isinstance(editable, Gtk.Entry):
                completion = Gtk.EntryCompletion()
                it = self.model.get_iter_from_string(path)
                if not it:
                    return
                el = self.model.get_value(it, COLUMN_ELEMENT)
                # Build the completion list
                store = Gtk.ListStore(str)
                for c in self.controller.package._indexer.get_completions("", context=el):
                    store.append([ c ])
                completion.set_model(store)
                completion.set_text_column(0)
                editable.set_completion(completion)
                editable.connect('focus-out-event', validate_entry_on_focus_out, cell, path)

        for (name, label, col) in (
                ('content', _("Content"), COLUMN_CONTENT),
                ('type', _("Type"), COLUMN_TYPE),
                ('begin', _("Begin"), COLUMN_BEGIN_FORMATTED),
                ('end', _("End"), COLUMN_END_FORMATTED),
                ('duration', _("Duration"), COLUMN_DURATION),
                ('id', _("Id"), COLUMN_ID),
                ('package', _("Package"), COLUMN_SOURCE_PACKAGE)
        ):
            renderer = Gtk.CellRendererText()
            columns[name]=Gtk.TreeViewColumn(label, renderer, text=col)
            if name == 'content':
                renderer.connect('editing-started', entry_editing_started)
                renderer.connect('edited', cell_edited)
                renderer.props.editable = True

            columns[name].set_reorderable(True)
            columns[name].set_sort_column_id(col)
            tree_view.append_column(columns[name])

        # Column-specific settings
        columns['begin'].set_sort_column_id(COLUMN_BEGIN)
        columns['end'].set_sort_column_id(COLUMN_END)
        self.model.set_sort_column_id(COLUMN_BEGIN, Gtk.SortType.ASCENDING)
        columns['type'].add_attribute(columns['type'].get_cells()[0],
                                      'cell-background',
                                      COLUMN_COLOR)

        # Resizable columns: content, type
        for name in ('content', 'type', 'snapshot'):
            columns[name].set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            columns[name].set_resizable(True)
            columns[name].set_min_width(40)
        columns['content'].set_expand(True)
        columns['content'].set_max_width(800)

        # Allow user classes to tweak behaviour
        self.columns = columns

        # Drag and drop for annotations
        tree_view.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                                  config.data.get_target_types('annotation',
                                                               'text-plain',
                                                               'TEXT',
                                                               'STRING'),
                                  Gdk.DragAction.LINK | Gdk.DragAction.COPY | Gdk.DragAction.MOVE)

        def get_element():
            selection = tree_view.get_selection ()
            if not selection:
                return None
            store, paths=selection.get_selected_rows()
            l=[ store.get_value (store.get_iter(p), COLUMN_ELEMENT) for p in paths ]
            if not l:
                return None
            elif len(l) == 1:
                return l[0]
            else:
                return l
        tree_view.connect('drag-begin', contextual_drag_begin, get_element, self.controller)
        tree_view.connect('drag-end', contextual_drag_end)

        tree_view.connect('drag-data-get', self.drag_data_get_cb)

        # The widget can receive drops
        def drag_received_cb(widget, context, x, y, selection, targetType, time):
            """Handle the drop of an annotation type.
            """
            if Gtk.drag_get_source_widget(context).is_ancestor(self.widget):
                # Ignore drops from our own widget
                return False

            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.annotations.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                if sources:
                    self.set_elements(sources)
                return True
            elif targetType == config.data.target_type['annotation-type']:
                sources=[ self.controller.package.annotationTypes.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                if sources:
                    self.set_elements(sources[0].annotations)
                return True
            return False

        tree_view.connect('drag-data-received', drag_received_cb)
        tree_view.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('annotation', 'annotation-type'),
                        Gdk.DragAction.COPY | Gdk.DragAction.LINK | Gdk.DragAction.MOVE)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(tree_view)

        sw.treeview = tree_view

        return sw

    def drag_data_get_cb(self, treeview, context, selection, targetType, timestamp):
        model, paths = treeview.get_selection().get_selected_rows()

        els=[ model[p][COLUMN_ELEMENT] for p in paths ]

        if targetType == config.data.target_type['annotation']:
            selection.set(selection.get_target(), 8, "\n".join( e.uri.encode('utf8')
                                                          for e in els
                                                          if isinstance(e, Annotation) ))
            return True
        elif (targetType == config.data.target_type['text-plain']
              or targetType == config.data.target_type['TEXT']
              or targetType == config.data.target_type['STRING']):
            selection.set(selection.get_target(), 8, "\n".join(e.content.data.encode('utf8')
                                                          for e in els
                                                          if isinstance(e, Annotation) ))
        else:
            logger.warn("Unknown target type for drag: %d" % targetType)
        return True

    def get_selected_nodes(self, with_path=False):
        """Return the currently selected nodes.
        """
        selection = self.widget.treeview.get_selection()
        store, paths = selection.get_selected_rows()
        if with_path:
            return [ (store.get_value(store.get_iter(p), COLUMN_ELEMENT), p) for p in paths ]
        else:
            return [ store.get_value(store.get_iter(p), COLUMN_ELEMENT) for p in paths ]

    def get_selected_node(self, with_path=False):
        """Return the currently selected node.

        None if no node is selected or multiple nodes are selected.
        """
        nodes = self.get_selected_nodes(with_path)
        if len(nodes) != 1:
            return None
        else:
            return nodes[0]

    def debug_cb (self, *p, **kw):
        logger.debug("Parameters: %s\nkw: %s", str(p), str(kw))

    def csv_export(self, name=None):
        if name is None:
            name=dialog.get_filename(title=_("Export data to file..."),
                                              default_file="advene_data.csv",
                                              action=Gtk.FileChooserAction.SAVE,
                                              button=Gtk.STOCK_SAVE)
        if name is None:
            return True
        try:
            f=open(name, 'w', encoding='utf-8')
        except IOError as e:
            dialog.message_dialog(label=_("Error while exporting data to %(filename)s: %(error)s"
                                          % {
                        'filename': name,
                        'error': str(e),
                        }), icon=Gtk.MessageType.ERROR)
        w=csv.writer(f)
        tv=self.widget.treeview
        store, paths=tv.get_selection().get_selected_rows()
        source=[ store.get_iter(p) for p in paths ]
        if not source:
            source=tv.get_model()
        w.writerow( (_("id"), _("type"), _("begin"), _("end"), _("content")) )
        for r in source:
            w.writerow( (r[COLUMN_ID], str(r[COLUMN_TYPE]).encode('utf-8'), r[COLUMN_BEGIN], r[COLUMN_END], str(r[COLUMN_ELEMENT].content.data).encode('utf-8') ) )
        f.close()
        self.log(_("Data exported to %s") % name)

    def row_activated_cb(self, widget, path, view_column):
        """Edit the element on Return or double click
        """
        widget.set_cursor(path, self.columns['content'], True)
        return False

    def set_time(self, attr):
        """Sets the time of the current annotation to the current player time.
        """
        an, an_path = self.get_selected_node(with_path=True)
        if an is None:
            return
        current_time = self.controller.player.current_position_value
        confirm = True
        if self.options['confirm-time-update']:
            confirm = dialog.message_dialog(_("Set %(attr)s time to %(time)s") % {
                'attr': _(attr),
                'time': helper.format_time(current_time)
                }, icon=Gtk.MessageType.QUESTION)
        if confirm:
            self.last_edited_path = an_path
            self.controller.notify('EditSessionStart', element=an, immediate=True)
            setattr(an.fragment, attr, current_time)
            self.controller.notify("AnnotationEditEnd", annotation=an)
            self.controller.notify('EditSessionEnd', element=an)


    def tree_view_key_cb(self, widget=None, event=None):
        if event.keyval == Gdk.KEY_space:
            # Space: goto annotation
            ann = self.get_selected_node ()
            if ann is not None:
                self.controller.update_status (status="seek", position=ann.fragment.begin)
                self.controller.gui.set_current_annotation(ann)
                return True
        elif event.keyval == Gdk.KEY_Return and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Control-return: edit annotation
            ann = self.get_selected_node ()
            if ann is not None:
                self.controller.gui.edit_element(ann)
                return True
        elif event.keyval == Gdk.KEY_less and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Control-< : set begin time
            self.set_time('begin')
            return True
        elif event.keyval == Gdk.KEY_greater and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Control-> : set end time
            self.set_time('end')
            return True
        elif event.keyval in (Gdk.KEY_1,
                              Gdk.KEY_2,
                              Gdk.KEY_3,
                              Gdk.KEY_4,
                              Gdk.KEY_5,
                              Gdk.KEY_6,
                              Gdk.KEY_7,
                              Gdk.KEY_8,
                              Gdk.KEY_9):
            ann, path = self.get_selected_node(with_path=True)
            if  ann.type.getMetaData(config.data.namespace, "completions"):
                # Shortcut for 1 key edition
                index = event.keyval - 48 - 1
                ret = self.controller.quick_completion_fill_annotation(ann, index)
                if ret:
                    self.last_edited_path = path
                # Gtk.TreePath.new_from_string(path_string)
                return ret
            return False

        return False

    def tree_view_button_cb(self, widget=None, event=None):
        if not event.get_window() is widget.get_bin_window():
            return False

        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)

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
            elif button == 1 and col.get_title() == _("Snapshot"):
                # Click on snapshot -> play
                self.controller.update_status("set", node.fragment.begin)
                # Allow further processing
                retval = False
        return retval

class GenericTable(AdhocView):
    view_name = _("Generic table view")
    view_id = 'generictable'
    tooltip=_("Display Advene elements in a table.")

    def __init__(self, controller=None, parameters=None, elements=None, source=None):
        super(GenericTable, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = ()
        self.controller=controller
        self.elements=elements
        self.source = source
        self.options = { }

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        a=dict(arg)
        if source is None and 'source' in a:
            source=a['source']

        if elements is None and source:
            c=self.controller.build_context()
            try:
                elements = c.evaluateValue(source)
                self.source = source
            except Exception as e:
                self.log(_("Error in source evaluation %(source)s: %(error)s") % {
                    'source': self.source,
                    'error': str(e) })
                elements = []

        self.model=self.build_model(elements)
        self.widget = self.build_widget()

    def get_save_arguments(self):
        if self.source is not None:
            arguments = [ ('source', self.source) ]
        else:
            arguments = []
        return self.options, arguments

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

    def set_elements(self, elements):
        model=self.build_model(elements)
        self.widget.treeview.set_model(model)
        self.model = model
        self.elements=elements

    def build_model(self, elements):
        """Build the ListStore containing the data.

        Columns: element, content (title), type, id
        """
        l=Gtk.ListStore(object, str, str, str)
        if not elements:
            return l
        for e in elements:
            l.append( (e,
                       self.controller.get_title(e),
                       helper.get_type(e),
                       e.id) )
        return l

    def csv_export(self, name=None):
        if name is None:
            name=dialog.get_filename(title=_("Export data to file..."),
                                              default_file="advene_data.csv",
                                              action=Gtk.FileChooserAction.SAVE,
                                              button=Gtk.STOCK_SAVE)
        if name is None:
            return True
        try:
            f=open(name, 'w', encoding='utf-8')
        except IOError as e:
            dialog.message_dialog(label=_("Error while exporting data to %(filename)s: %(error)s"
                                          % {
                        'filename': name,
                        'error': str(e),
                        }),
                                  icon=Gtk.MessageType.ERROR)
        w=csv.writer(f)
        tv=self.widget.treeview
        store, paths=tv.get_selection().get_selected_rows()
        source=[ store.get_iter(p) for p in paths ]
        if not source:
            source=tv.get_model()
        w.writerow( (_("Element title"), _("Element type"), _("Element id")) )
        for r in source:
            w.writerow( (str(r[COLUMN_CONTENT]).encode('utf-8'), str(r[COLUMN_TYPE]).encode('utf-8'), r[COLUMN_ID]) )
        f.close()
        self.log(_("Data exported to %s") % name)

    def build_widget(self):
        tree_view = Gtk.TreeView(self.model)

        select = tree_view.get_selection()
        select.set_mode(Gtk.SelectionMode.MULTIPLE)

        tree_view.connect('button-press-event', self.tree_view_button_cb)
        tree_view.connect('row-activated', self.row_activated_cb)
        # Deactivate starting search by simply typing. Users have to use the search shortcut (Control-F)
        tree_view.set_enable_search(False)
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
            columns[name]=Gtk.TreeViewColumn(label, Gtk.CellRendererText(), text=col)
            columns[name].set_reorderable(True)
            columns[name].set_sort_column_id(col)
            tree_view.append_column(columns[name])

        self.model.set_sort_column_id(COLUMN_CONTENT, Gtk.SortType.ASCENDING)

        # Resizable columns: title, type
        for name in ('title', 'type'):
            columns[name].set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            columns[name].set_resizable(True)
            columns[name].set_min_width(40)
        columns['title'].set_expand(True)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(tree_view)

        sw.treeview = tree_view

        # The widget can receive drops
        def drag_received_cb(widget, context, x, y, selection, targetType, time):
            """Handle the drop of an annotation type.
            """
            if Gtk.drag_get_source_widget(context).is_ancestor(self.widget):
                # Ignore drops from our own widget
                return False

            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.annotations.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                if sources:
                    self.set_elements(sources)
                return True
            elif targetType == config.data.target_type['annotation-type']:
                sources=[ self.controller.package.annotationTypes.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                if sources:
                    self.set_elements(sources[0].annotations)
                return True
            return False

        tree_view.connect('drag-data-received', drag_received_cb)
        tree_view.drag_dest_set(Gtk.DestDefaults.MOTION |
                                Gtk.DestDefaults.HIGHLIGHT |
                                Gtk.DestDefaults.ALL,
                                config.data.get_target_types('annotation', 'annotation-type'),
                                Gdk.DragAction.COPY | Gdk.DragAction.LINK | Gdk.DragAction.MOVE)

        return sw

    def get_selected_nodes(self, with_path=False):
        """Return the currently selected nodes.
        """
        selection = self.widget.treeview.get_selection()
        store, paths = selection.get_selected_rows()
        if with_path:
            return [ (store.get_value(store.get_iter(p), COLUMN_ELEMENT), p) for p in paths ]
        else:
            return [ store.get_value(store.get_iter(p), COLUMN_ELEMENT) for p in paths ]

    def get_selected_node(self, with_path=False):
        """Return the currently selected node.

        None if no node is selected or multiple nodes are selected.
        """
        nodes = self.get_selected_nodes(with_path)
        if len(nodes) != 1:
            return None
        else:
            return nodes[0]

    def debug_cb (self, *p, **kw):
        logger.debug("Parameters: %s\nkw: %s", str(p), str(kw))

    def row_activated_cb(self, widget, path, view_column):
        """Edit the element on Return or double click
        """
        el = self.get_selected_node ()
        if el  is not None:
            self.controller.gui.edit_element(el)
            return True
        return False

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)

        if button == 3 or button == 2:
            if event.get_window() is widget.get_bin_window():
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
