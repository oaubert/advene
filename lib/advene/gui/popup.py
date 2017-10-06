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
"""Popup menu for Advene elements.

Generic popup menu used by the various Advene views.
"""

from gi.repository import Gtk
import re
import os

from gettext import gettext as _

import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.view import View
from advene.model.query import Query

from advene.rules.elements import RuleSet, Rule, Event, Condition, Action

from advene.gui.util import image_from_position, dialog, get_clipboard
import advene.util.helper as helper
import advene.util.importer

class Menu:
    def __init__(self, element=None, controller=None, readonly=False):
        self.element=element
        self.controller=controller
        self.readonly=readonly
        self.menu=self.make_base_menu(element)

    def popup(self):
        self.menu.popup_at_pointer(None)
        return True

    def get_title (self, element):
        """Return the element title."""
        return self.controller.get_title(element, max_size=40)

    def goto_annotation (self, widget, ann):
        c = self.controller
        c.update_status(status="seek", position=ann.fragment.begin)
        c.gui.set_current_annotation(ann)
        return True

    def duplicate_annotation(self, widget, ann):
        self.controller.duplicate_annotation(ann)
        return True

    def activate_annotation (self, widget, ann):
        self.controller.notify("AnnotationActivate", annotation=ann)
        return True

    def desactivate_annotation (self, widget, ann):
        self.controller.notify("AnnotationDeactivate", annotation=ann)
        return True

    def activate_stbv (self, widget, view):
        self.controller.activate_stbv(view)
        return True

    def open_adhoc_view (self, widget, view):
        self.controller.gui.open_adhoc_view(view)
        return True

    def create_element(self, widget, elementtype=None, parent=None):
        if elementtype == 'staticview':
            elementtype=View
            mimetype='text/html'
        elif elementtype == 'dynamicview':
            elementtype=View
            mimetype='application/x-advene-ruleset'
        else:
            mimetype=None
        cr = self.controller.gui.create_element_popup(type_=elementtype,
                                                      parent=parent,
                                                      controller=self.controller,
                                                      mimetype=mimetype)
        cr.popup()
        return True

    def do_insert_resource_file(self, parent=None, filename=None, id_=None):
        if id_ is None:
            # Generate the id_
            basename = os.path.basename(filename)
            id_=re.sub('[^a-zA-Z0-9_.]', '_', basename)
        size=os.stat(filename).st_size
        f=open(filename, 'rb')
        parent[id_]=f.read(size + 2)
        f.close()
        el=parent[id_]
        self.controller.notify('ResourceCreate',
                               resource=el)
        return el

    def do_insert_resource_dir(self, parent=None, dirname=None, id_=None):
        if id_ is None:
            # Generate the id_
            basename = os.path.basename(dirname)
            id_=re.sub('[^a-zA-Z0-9_.]', '_', basename)
        parent[id_] = parent.DIRECTORY_TYPE
        el=parent[id_]
        self.controller.notify('ResourceCreate',
                               resource=el)
        for n in os.listdir(dirname):
            filename = os.path.join(dirname, n)
            if os.path.isdir(filename):
                self.do_insert_resource_dir(parent=el, dirname=filename)
            else:
                self.do_insert_resource_file(parent=el, filename=filename)
        return el

    def insert_resource_data(self, widget, parent=None, title=None, filter=None):
        if title is None:
            title = _("Choose the file to insert")
        filename=dialog.get_filename(title=title, filter=filter)
        if filename is None:
            return True
        basename = os.path.basename(filename)
        id_=re.sub('[^a-zA-Z0-9_.]', '_', basename)
        if id_ != basename:
            while True:
                id_ = dialog.entry_dialog(title=_("Select a valid identifier"),
                                                   text=_("The filename %s contains invalid characters\nthat have been replaced.\nYou can modify this identifier if necessary:") % filename,
                                                   default=id_)
                if id_ is None:
                    # Edition cancelled
                    return True
                elif re.match('^[a-zA-Z0-9_.]+$', id_):
                    break
        self.do_insert_resource_file(parent=parent, filename=filename, id_=id_)
        return True

    def insert_soundclip(self, widget, parent=None):
        self.insert_resource_data(widget, parent, title=_("Choose the soundclip to insert"), filter='audio')
        return True

    def insert_resource_directory(self, widget, parent=None):
        dirname=dialog.get_dirname(title=_("Choose the directory to insert"))
        if dirname is None:
            return True

        self.do_insert_resource_dir(parent=parent, dirname=dirname)
        return True

    def edit_element (self, widget, el):
        self.controller.gui.edit_element(el)
        return True

    def filter_service(self, widget, importer, annotationtype):
        self.controller.gui.open_adhoc_view('importerview', message=_("Apply %s") % importer.name, display_unlikely=False, importerclass=importer, source_type=annotationtype)

    def popup_get_offset(self):
        offset=dialog.entry_dialog(title='Enter an offset',
                                   text=_("Give the offset to use\non specified element.\nIt is in ms and can be\neither positive or negative."),
                                   default="0")
        if offset is not None:
            return int(offset)
        else:
            return offset

    def offset_element (self, widget, el):
        offset = self.popup_get_offset()
        if offset is None:
            return True
        if isinstance(el, Annotation):
            self.controller.notify('EditSessionStart', element=el, immediate=True)
            el.fragment.begin += offset
            el.fragment.end += offset
            self.controller.notify('AnnotationEditEnd', annotation=el)
            self.controller.notify('EditSessionEnd', element=el)
        elif isinstance(el, AnnotationType):
            batch_id=object()
            for a in el.annotations:
                self.controller.notify('EditSessionStart', element=a, immediate=True)
                a.fragment.begin += offset
                a.fragment.end += offset
                self.controller.notify('AnnotationEditEnd', annotation=a, batch=batch_id)
                self.controller.notify('EditSessionEnd', element=a)
        elif isinstance(el, Package):
            for a in el.annotations:
                a.fragment.begin += offset
                a.fragment.end += offset
            self.controller.notify('PackageActivate', package=el)
        elif isinstance(el, Schema):
            batch_id=object()
            for at in el.annotationTypes:
                for a in at.annotations:
                    self.controller.notify('EditSessionStart', element=a, immediate=True)
                    a.fragment.begin += offset
                    a.fragment.end += offset
                    self.controller.notify('AnnotationEditEnd', annotation=a, batch=batch_id)
                    self.controller.notify('EditSessionEnd', element=a)
        return True

    def search_replace_content(self, widget, el):
        if isinstance(el, (Annotation, View)):
            l = [ el ]
            title = _("Replace content in %s" % self.controller.get_title(el))
        elif isinstance(el, AnnotationType):
            l = el.annotations
            title = _("Replace content in annotations of type %s" % self.controller.get_title(el))
        elif isinstance(el, Package):
            l = el.annotations
            title = _("Replace content in all annotations")
        self.controller.gui.search_replace_dialog(l, title=title)
        return True

    def copy_id (self, widget, el):
        clip = get_clipboard()
        clip.set_text(el.id, -1)
        return True

    def browse_element (self, widget, el):
        self.controller.gui.open_adhoc_view('browser', element=el)
        return True

    def query_element (self, widget, el):
        self.controller.gui.open_adhoc_view('interactivequery', here=el, sources= [ "here" ])
        return True

    def delete_element (self, widget, el):
        self.controller.delete_element(el)
        return True

    def delete_elements (self, widget, el, elements):
        batch_id=object()
        if isinstance(el, AnnotationType) or isinstance(el, RelationType):
            for e in elements:
                self.controller.delete_element(e, batch=batch_id)
        return True

    def create_montage(self, widget, rt):
        """Create a montage from a relationtype.
        """
        l = list(set( r.members[0] for r in rt.relations ))
        res = []
        if l:
            l.sort(key=lambda a: a.fragment.begin)
            ann = l[0]
            while True:
                res.append(ann)
                try:
                    l.remove(ann)
                except ValueError:
                    pass
                r = ann.typedRelatedOut.get(rt.id, None)
                if not r:
                    ann = None
                else:
                    ann = r[0]
                if ann is None or ann in res:
                    # End of relations. Look for other roots.
                    if l:
                        ann = l[0]
                    else:
                        break
        self.controller.gui.open_adhoc_view('montage', elements=res)
        return True

    def pick_color(self, widget, element):
        self.controller.gui.update_color(element)
        return True

    def add_menuitem(self, menu=None, item=None, action=None, *param, **kw):
        if item is None or item == "":
            i = Gtk.SeparatorMenuItem()
        else:
            i = Gtk.MenuItem(item, use_underline=False)
        if action is not None:
            i.connect('activate', action, *param, **kw)
        menu.append(i)
        return i

    def make_base_menu(self, element):
        """Build a base popup menu dedicated to the given element.

        @param element: the element
        @type element: an Advene element

        @return: the built menu
        @rtype: Gtk.Menu
        """
        menu = Gtk.Menu()

        def add_item(*p, **kw):
            return self.add_menuitem(menu, *p, **kw)

        title=add_item(self.get_title(element))

        if hasattr(element, 'id') or isinstance(element, Package):
            title.set_submenu(self.common_submenu(element))

        add_item("")

        try:
            i=element.id
            add_item(_("Copy id %s") % i,
                     self.copy_id,
                     element)
        except AttributeError:
            pass

        if hasattr(element, 'viewableType'):
            self.make_bundle_menu(element, menu)

        specific_builder={
            Annotation: self.make_annotation_menu,
            Relation: self.make_relation_menu,
            AnnotationType: self.make_annotationtype_menu,
            RelationType: self.make_relationtype_menu,
            Schema: self.make_schema_menu,
            View: self.make_view_menu,
            Package: self.make_package_menu,
            Query: self.make_query_menu,
            Resources: self.make_resources_menu,
            ResourceData: self.make_resourcedata_menu,
            }

        for t, method in specific_builder.items():
            if isinstance(element, t):
                method(element, menu)

        menu.show_all()
        return menu

    def display_stats(self, m, el):
        """Display statistics about the element's annotations.

        element can be either the package, or an annotation type.
        """
        self.controller.gui.display_statistics(el.annotations, label=_("<b>Statistics about %s</b>\n\n") % self.controller.get_title(el))
        return True

    def renumber_annotations(self, m, at):
        """Renumber all annotations of a given type.
        """
        d = Gtk.Dialog(title=_("Renumbering annotations of type %s") % self.get_title(at),
                       parent=self.controller.gui.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                 Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 ))
        l=Gtk.Label()
        l.set_markup(_("<b>Renumber all annotations according to their order.</b>\n\n<i>Note that this action cannot be undone.</i>\nReplace the first numeric value of the annotation content with the new annotation number.\nIf no numeric value is found and the annotation is structured, it will insert the number.\nIf no numeric value is found and the annotation is of type text/plain, it will overwrite the annotation content.\nThe offset parameter allows you to renumber from a given annotation."))
        l.set_line_wrap(True)
        l.show()
        d.vbox.add(l)

        hb=Gtk.HBox()
        l=Gtk.Label(label=_("Offset"))
        hb.pack_start(l, False, True, 0)
        s=Gtk.SpinButton()
        s.set_range(-5, len(at.annotations))
        s.set_value(1)
        s.set_increments(1, 5)
        hb.add(s)
        d.vbox.pack_start(hb, False, True, 0)

        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        d.show_all()
        dialog.center_on_mouse(d)

        res=d.run()
        if res == Gtk.ResponseType.OK:
            re_number=re.compile('(\d+)')
            re_struct=re.compile('^num=(\d+)$', re.MULTILINE)
            offset=s.get_value_as_int() - 1
            l=at.annotations
            l.sort(key=lambda a: a.fragment.begin)
            l=l[offset:]
            size=float(len(l))
            dial=Gtk.Dialog(_("Renumbering %d annotations") % size,
                           self.controller.gui.gui.win,
                           Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                           (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
            prg=Gtk.ProgressBar()
            dial.vbox.pack_start(prg, False, True, 0)
            dial.show_all()

            for i, a in enumerate(l[offset:]):
                prg.set_text(_("Annotation #%d") % i)
                prg.set_fraction( i / size )
                while Gtk.events_pending():
                    Gtk.main_iteration()

                if a.type.mimetype == 'application/x-advene-structured':
                    if re_struct.search(a.content.data):
                        # A 'num' field is present. Update it.
                        data=re_struct.sub("num=%d" % (i+1), a.content.data)
                    else:
                        # Insert the num field
                        data=("num=%d\n" % (i+1)) + a.content.data
                elif re_number.search(a.content.data):
                    # There is a number. Simply substitute the new one.
                    data=re_number.sub(str(i+1), a.content.data)
                elif a.type.mimetype == 'text/plain':
                    # Overwrite the contents
                    data=str(i+1)
                else:
                    data=None
                if data is not None and a.content.data != data:
                    a.content.data=data
            self.controller.notify('PackageActivate', package=self.controller.package)
            dial.destroy()

        d.destroy()
        return True

    def split_package_by_type(self, element):
        title = self.controller.get_title(element)
        count = len(element.annotations)
        dial=Gtk.Dialog(_("Splitting package according to %s") % title,
                        self.controller.gui.gui.win,
                        Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT)
        label = Gtk.Label(_("For each of the %(count)d annotations in %(atype)s, create a package named after the source package and the annotation content, copying only annotations contained in the reference annotation.") % { 'count': count,
                                                                                                                                                                                                                                   'atype': title })
        label.set_max_width_chars(50)
        dial.vbox.pack_start(label, False, True, 0)
        progress_bar=Gtk.ProgressBar()
        progress_bar.set_text("")
        progress_bar.set_show_text(True)
        dial.vbox.pack_start(progress_bar, False, True, 0)

        should_continue = True
        def do_cancel(b):
            nonlocal should_continue
            should_continue = False
            return True
        cancel_button = dial.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
        cancel_button.connect("clicked", do_cancel)
        dial.show_all()

        def progress_callback(name, filename, n, index):
            nonlocal should_continue
            progress_bar.set_text(_("Created %(name)s - %(n) annotations") % locals())
            progress_bar.set_fraction( index / count )
            while Gtk.events_pending():
                Gtk.main_iteration()
            return should_continue

        self.controller.split_package_by_type(element, callback=progress_callback)
        dial.destroy()

    def extract_fragment(self, m, ann):
        """Extract the fragment corresponding to an annotation.
        """
        title = self.controller.get_title(ann)
        begin = helper.format_time(ann.fragment.begin)
        end = helper.format_time(ann.fragment.end)
        self.controller.gui.render_montage_dialog([ ann ],
                                                  basename = ann.id + "-" + helper.title2id(title) + ".ogv",
                                                  title = _("Extracting %s") % title,
                                                  label = _("Exporting annotation %(title)s\nfrom %(begin)s to %(end)s\nto %%(filename)s") % locals())
        return True

    def common_submenu(self, element):
        """Build the common submenu for all elements.
        """
        submenu=Gtk.Menu()
        def add_item(*p, **kw):
            self.add_menuitem(submenu, *p, **kw)

        # Common to all other elements:
        add_item(_("Edit"), self.edit_element, element)
        if config.data.preferences['expert-mode']:
            add_item(_("Browse"), self.browse_element, element)
            add_item(_("Query"), self.query_element, element)

        def open_in_browser(i, v):
            c=self.controller.build_context(here=element)
            url=c.evaluateValue('here/absolute_url')
            self.controller.open_url(url)
            return True
        add_item(_("Open in web browser"), open_in_browser, element)

        if not self.readonly:
            # Common to deletable elements
            if type(element) in (Annotation, Relation, View, Query,
                                 Schema, AnnotationType, RelationType, ResourceData):
                add_item(_("Delete"), self.delete_element, element)

            if type(element) == Resources and type(element.parent) == Resources:
                # Add Delete item to Resources except for the root resources (with parent = package)
                add_item(_("Delete"), self.delete_element, element)

            if isinstance(element, (Annotation, AnnotationType, Package)):
                add_item(_("Search/replace content"), self.search_replace_content, element)

            ## Common to offsetable elements
            if (config.data.preferences['expert-mode']
                and type(element) in (Annotation, Schema, AnnotationType, Package)):
                add_item(_("Offset"), self.offset_element, element)

        submenu.show_all()
        return submenu


    def activate_submenu(self, element):
        """Build an "activate" submenu for the given annotation"""
        submenu=Gtk.Menu()
        def add_item(*p, **kw):
            self.add_menuitem(submenu, *p, **kw)

        add_item(_("Activate"), self.activate_annotation, element)
        add_item(_("Desactivate"), self.desactivate_annotation, element)
        submenu.show_all()
        return submenu

    def make_annotation_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)

        def loop_on_annotation(menu, ann):
            self.controller.gui.loop_on_annotation_gui(ann, goto=True)
            return True

        def save_snapshot(menu, ann):
            self.controller.gui.save_snapshot_as(ann.fragment.begin)
            return True

        add_item(_("Go to..."), self.goto_annotation, element)
        add_item(_("Loop"), loop_on_annotation, element)
        add_item(_("Duplicate"), self.duplicate_annotation, element)
        item = Gtk.MenuItem(_("Highlight"), use_underline=False)
        item.set_submenu(self.activate_submenu(element))
        menu.append(item)
        add_item(_("Save snapshot..."), save_snapshot, element)
        if 'montagerenderer' in self.controller.generic_features:
            add_item(_("Extract video fragment"), self.extract_fragment, element)

        def build_submenu(submenu, el, items):
            """Build the submenu for the given element.
            """
            if submenu.get_children():
                # The submenu was already populated.
                return False
            if len(items) == 1:
                # Only 1 elements, do not use an intermediary menu
                m=Menu(element=items[0], controller=self.controller)
                for c in m.menu.get_children():
                    m.menu.remove(c)
                    submenu.append(c)
            else:
                for i in items:
                    item=Gtk.MenuItem(self.get_title(i), use_underline=False)
                    m=Menu(element=i, controller=self.controller)
                    item.set_submenu(m.menu)
                    submenu.append(item)
            submenu.show_all()
            return False

        def build_related(submenu, el):
            """Build the related annotations submenu for the given element.
            """
            if submenu.get_children():
                # The submenu was already populated.
                return False
            if el.incomingRelations:
                i=Gtk.MenuItem(_("Incoming"))
                submenu.append(i)
                i=Gtk.SeparatorMenuItem()
                submenu.append(i)
                for t, l in el.typedRelatedIn.items():
                    at=self.controller.package.get_element_by_id(t)
                    m=Gtk.MenuItem(self.get_title(at), use_underline=False)
                    amenu=Gtk.Menu()
                    m.set_submenu(amenu)
                    amenu.connect('map', build_submenu, at, l)
                    submenu.append(m)
            if submenu.get_children():
                # There were incoming annotations. Use a separator
                i=Gtk.SeparatorMenuItem()
                submenu.append(i)
            if el.outgoingRelations:
                i=Gtk.MenuItem(_("Outgoing"))
                submenu.append(i)
                i=Gtk.SeparatorMenuItem()
                submenu.append(i)
                for t, l in el.typedRelatedOut.items():
                    at=self.controller.package.get_element_by_id(t)
                    m=Gtk.MenuItem(self.get_title(at), use_underline=False)
                    amenu=Gtk.Menu()
                    m.set_submenu(amenu)
                    amenu.connect('map', build_submenu, at, l)
                    submenu.append(m)
            submenu.show_all()
            return False

        if element.relations:
            i=Gtk.MenuItem(_("Related annotations"), use_underline=False)
            submenu=Gtk.Menu()
            i.set_submenu(submenu)
            submenu.connect('map', build_related, element)
            menu.append(i)

            if element.incomingRelations:
                i=Gtk.MenuItem(_("Incoming relations"), use_underline=False)
                submenu=Gtk.Menu()
                i.set_submenu(submenu)
                submenu.connect('map', build_submenu, element, element.incomingRelations)
                menu.append(i)

            if element.outgoingRelations:
                i=Gtk.MenuItem(_("Outgoing relations"), use_underline=False)
                submenu=Gtk.Menu()
                i.set_submenu(submenu)
                submenu.connect('map', build_submenu, element, element.outgoingRelations)
                menu.append(i)

        add_item("")

        item = Gtk.MenuItem()
        item.add(image_from_position(self.controller,
                                     position=element.fragment.begin,
                                     media=element.media,
                                     height=60))
        item.connect('activate', self.goto_annotation, element)
        menu.append(item)

        #add_item(element.content.data[:40])
        add_item(_('Begin: %s')
                 % helper.format_time (element.fragment.begin), lambda i: self.controller.gui.adjust_annotation_bound(element, 'begin'))
        add_item(_('End: %s') % helper.format_time (element.fragment.end), lambda i: self.controller.gui.adjust_annotation_bound(element, 'end'))
        add_item(_('Duration: %s') % helper.format_time (element.fragment.duration))
        return

    def make_relation_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(element.content.data)
        add_item(_('Members:'))
        for a in element.members:
            item=Gtk.MenuItem(self.get_title(a), use_underline=False)
            m=Menu(element=a, controller=self.controller)
            item.set_submenu(m.menu)
            menu.append(item)
        return

    def make_package_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_('Edit package properties...'), self.controller.gui.on_package_properties1_activate)
        add_item(_('%d annotations(s) - statistics') % len(element.annotations), self.display_stats, element)
        add_item('')
        add_item(_('Create a new static view...'), self.create_element, 'staticview', element)
        add_item(_('Create a new dynamic view...'), self.create_element, 'dynamicview', element)
        add_item(_('Create a new annotation...'), self.create_element, Annotation, element)
        #add_item(_('Create a new relation...'), self.create_element, Relation, element)
        add_item(_('Create a new schema...'), self.create_element, Schema, element)
        add_item(_('Create a new query...'), self.create_element, Query, element)
        return

    def make_resources_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_('Create a new folder...'), self.create_element, Resources, element)
        add_item(_('Create a new resource file...'), self.create_element, ResourceData, element)
        add_item(_('Insert a new resource file...'), self.insert_resource_data, element)
        add_item(_('Insert a new resource directory...'), self.insert_resource_directory, element)
        #print "Menu for", id(element), id(self.controller.package.resources), element.id

        if element.resourcepath == '':
            # Resources root
            if 'soundclips' not in element:
                # Create the soundclips folder
                element['soundclips'] = element.DIRECTORY_TYPE
                self.controller.notify('ResourceCreate', resource=element['soundclips'])
            add_item(_('Insert a soundclip...'), self.insert_soundclip, element['soundclips'])
        elif element.resourcepath == 'soundclips':
            add_item(_('Insert a soundclip...'), self.insert_soundclip, element)
        return

    def make_resourcedata_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        def play_sound(w, filename):
            self.controller.soundplayer.play(filename)
            return True
        if element.id.split('.')[-1] in ('wav', 'ogg', 'mp3'):
            # Audio resource (presumably). Propose to play it.
            add_item(_('Play sound'), play_sound, element.file_)
        if self.readonly:
            return
        return

    def make_schema_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_('Create a new annotation type...'),
                 self.create_element, AnnotationType, element)
        add_item(_('Create a new relation type...'),
                 self.create_element, RelationType, element)
        add_item(_('Select a color'), self.pick_color, element)
        return

    def create_dynamic_view(self, at):
        """Create a caption dynamic view for the given annotation-type.
        """
        p=self.controller.package
        ident='v_caption_%s' % at.id
        if p.get_element_by_id(ident) is not None:
            dialog.message_dialog(_("A caption dynamic view for %s already seems to exist.") % self.get_title(at))
            return True
        v=p.createView(
            ident=ident,
            author=config.data.userid,
            date=self.controller.get_timestamp(),
            clazz='package',
            content_mimetype='application/x-advene-ruleset'
            )
        v.title=_("Caption %s annotations") % self.get_title(at)

        # Build the ruleset
        r=RuleSet()
        catalog=self.controller.event_handler.catalog

        ra=catalog.get_action("AnnotationCaption")
        action=Action(registeredaction=ra, catalog=catalog)
        action.add_parameter('message', 'annotation/content/data')

        rule=Rule(name=_("Caption the annotation"),
                  event=Event("AnnotationBegin"),
                  condition=Condition(lhs='annotation/type/id',
                                      operator='equals',
                                      rhs='string:%s' % at.id),
                  action=action)
        r.add_rule(rule)

        v.content.data=r.xml_repr()

        p.views.append(v)
        self.controller.notify('ViewCreate', view=v)
        self.controller.activate_stbv(v)
        return True

    def make_annotationtype_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        def create_static(at):
            v=self.controller.create_static_view([ at ])
            self.controller.gui.edit_element(v)
            return True
        add_item(_('Create a comment view'), lambda i: create_static(element))
        add_item(_('Generate a caption dynamic view...'), lambda i: self.create_dynamic_view(element))
        add_item(_('Display as transcription'), lambda i: self.controller.gui.open_adhoc_view('transcription', source='here/annotationTypes/%s/annotations/sorted' % element.id))
        add_item(_('Display annotations in table'), lambda i: self.controller.gui.open_adhoc_view('table', elements=element.annotations, source='here/annotationTypes/%s/annotations' % element.id))
        add_item(_('Export to another format...'), lambda i: self.controller.gui.export_element(element))
        add_item(_('Split according to annotations'), lambda i: self.split_package_by_type(element))
        for imp in ( i for i in advene.util.importer.IMPORTERS if i.annotation_filter ):
            add_item(_("Apply %s..." % imp.name), self.filter_service, imp, element)
        if self.readonly:
            return
        add_item(None)
        add_item(_('Select a color'), self.pick_color, element)
        add_item(_('Create a new annotation...'), self.create_element, Annotation, element)
        add_item(_('Delete all annotations'), self.delete_elements, element, element.annotations)
        add_item(_('Renumber annotations...'), self.renumber_annotations, element)
        add_item(_('Shot validation view...'), lambda m, at: self.controller.gui.adjust_annotationtype_bounds(at), element)
        add_item('')
        add_item(_('%d annotations(s) - statistics') % len(element.annotations), self.display_stats, element)

        return

    def create_follow_dynamic_view(self, rt):
        """Create a dynamic view for the given relation-type.
        """
        p = self.controller.package
        ident = 'v_follow_%s' % rt.id
        if p.get_element_by_id(ident) is not None:
            dialog.message_dialog(_("A follow dynamic view for %s already seems to exist.") % self.get_title(rt))
            return True
        v = p.createView(
            ident=ident,
            author=config.data.userid,
            date=self.controller.get_timestamp(),
            clazz='package',
            content_mimetype='application/x-advene-ruleset'
            )
        v.title = _("Follow %s relation-type") % self.get_title(rt)

        # Build the ruleset
        r = RuleSet()
        catalog = self.controller.event_handler.catalog

        ra = catalog.get_action("PlayerGoto")
        action = Action(registeredaction=ra, catalog=catalog)
        action.add_parameter('position', 'annotation/typedRelatedOut/%s/first/fragment/begin' % rt.id)
        rule=Rule(name=_("Follow the relation"),
                  event=Event("AnnotationEnd"),
                  condition=Condition(lhs='annotation/typedRelatedOut/%s' % rt.id,
                                      operator='value'),
                  action=action)
        r.add_rule(rule)

        v.content.data=r.xml_repr()

        p.views.append(v)
        self.controller.notify('ViewCreate', view=v)
        self.controller.activate_stbv(v)
        return True

    def make_relationtype_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_('Select a color'), self.pick_color, element)
        add_item(_('Delete all relations...'), self.delete_elements, element, element.relations)
        add_item(_('Create montage from related annotations'), self.create_montage, element)
        add_item(_('Create dynamic view following relations'), lambda i, e: self.create_follow_dynamic_view(e), element)
        return

    def make_query_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)

        def try_query(item, expr):
            try:
                res, q = self.controller.evaluate_query(element, expr=expr)
                self.controller.gui.open_adhoc_view('interactiveresult',
                                                    query=element,
                                                    result=res,
                                                    destination='east')
            except Exception as e:
                self.controller.log(_('Exception in query: %s') % str(e))
            return True

        m=Gtk.MenuItem(_('Apply query on...'))
        menu.append(m)
        sm=Gtk.Menu()
        m.set_submenu(sm)
        for (expr, label) in (
             ('package', _('the package')),
             ('package/annotations', _('all annotations of the package')),
             ('package/annotations/first', _('the first annotation of the package')),
            ):
            i=Gtk.MenuItem(label)
            i.connect('activate', try_query, expr)
            sm.append(i)
        return

    def make_view_menu(self, element, menu):
        def open_in_browser(i, v):
            c=self.controller.build_context()
            url=c.evaluateValue('here/view/%s/absolute_url' % v.id)
            self.controller.open_url(url)
            return True

        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        t=helper.get_view_type(element)
        if t == 'dynamic':
            add_item(_('Activate view'), self.activate_stbv, element)
        elif t == 'adhoc':
            add_item(_('Open adhoc view'), self.open_adhoc_view, element)
        elif t == 'static' and element.matchFilter['class'] in ('package', '*'):
            add_item(_('Open in web browser'), open_in_browser, element)
        return

    def make_bundle_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        if element.viewableType == 'query-list':
            add_item(_('Create a new query...'), self.create_element, Query, element.rootPackage)
        elif element.viewableType == 'view-list':
            add_item(_('Create a new static view...'), self.create_element, 'staticview', element.rootPackage)
            add_item(_('Create a new dynamic view...'), self.create_element, 'dynamicview', element.rootPackage)
        elif element.viewableType == 'schema-list':
            add_item(_('Create a new schema...'), self.create_element, Schema, element.rootPackage)
        return

