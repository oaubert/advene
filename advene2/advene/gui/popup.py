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
"""Popup menu for Advene elements.

Generic popup menu used by the various Advene views.
"""

import gtk
import re
import os

from gettext import gettext as _

import advene.core.config as config

from advene.model.cam.package import Package
from advene.model.cam.annotation import Annotation
from advene.model.cam.relation import Relation
from advene.model.cam.tag import AnnotationType, RelationType
from advene.model.cam.resource import Resource
from advene.model.cam.view import View
from advene.model.cam.query import Query

from advene.rules.elements import RuleSet, Rule, Event, Condition, Action

from advene.gui.util import image_from_position, dialog
#from advene.gui.edit.create import CreateElementPopup
import advene.util.helper as helper

class Menu:
    def __init__(self, element=None, controller=None, readonly=False):
        self.element=element
        self.controller=controller
        self.readonly=readonly
        self.menu=self.make_base_menu(element)

    def popup(self):
        self.menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def get_title (self, element):
        """Return the element title."""
        t=self.controller.get_title(element)
        if len(t) > 80:
            t=t[:80]
        return t

    def goto_annotation (self, widget, ann):
        c=self.controller
        pos = c.create_position (value=ann.begin,
                                 key=c.player.MediaTime,
                                 origin=c.player.AbsolutePosition)
        c.update_status (status="set", position=pos)
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
        cr = CreateElementPopup(type_=elementtype,
                                parent=parent,
                                controller=self.controller,
                                mimetype=mimetype)
        cr.popup()
        return True

    def do_insert_resource_file(self, parent=None, filename=None, id_=None):
        # FIXME: to rewrite
        el=None
        ##if id_ is None:
        ##    # Generate the id_
        ##    basename = os.path.basename(filename)
        ##    id_=re.sub('[^a-zA-Z0-9_.]', '_', basename)
        ##size=os.stat(filename).st_size
        ##f=open(filename, 'rb')
        ##parent[id_]=f.read(size + 2)
        ##f.close()
        ##el=parent[id_]
        ##self.controller.notify('ResourceCreate',
        ##                       resource=el)
        return el

    def do_insert_resource_dir(self, parent=None, dirname=None, id_=None):
        # FIXME: to rewrite
        el=None
        ##if id_ is None:
        ##    # Generate the id_
        ##    basename = os.path.basename(dirname)
        ##    id_=re.sub('[^a-zA-Z0-9_.]', '_', basename)
        ##parent[id_] = parent.DIRECTORY_TYPE
        ##el=parent[id_]
        ##self.controller.notify('ResourceCreate',
        ##                       resource=el)
        ##for n in os.listdir(dirname):
        ##    filename = os.path.join(dirname, n)
        ##    if os.path.isdir(filename):
        ##        self.do_insert_resource_dir(parent=el, dirname=filename)
        ##    else:
        ##        self.do_insert_resource_file(parent=el, filename=filename)
        return el

    def insert_resource_data(self, widget, parent=None):
        # FIXME
        #filename=dialog.get_filename(title=_("Choose the file to insert"))
        #if filename is None:
        #    return True
        #basename = os.path.basename(filename)
        #id_=re.sub('[^a-zA-Z0-9_.]', '_', basename)
        #if id_ != basename:
        #    while True:
        #        id_ = dialog.entry_dialog(title=_("Select a valid identifier"),
        #                                           text=_("The filename %s contains invalid characters\nthat have been replaced.\nYou can modify this identifier if necessary:") % filename,
        #                                           default=id_)
        #        if id_ is None:
        #            # Edition cancelled
        #            return True
        #        elif re.match('^[a-zA-Z0-9_.]+$', id_):
        #            break
        #self.do_insert_resource_file(parent=parent, filename=filename, id_=id_)
        return True

    def insert_resource_directory(self, widget, parent=None):
        # FIXME
        #dirname=dialog.get_dirname(title=_("Choose the directory to insert"))
        #if dirname is None:
        #    return True
        #
        #self.do_insert_resource_dir(parent=parent, dirname=dirname)
        return True
        
    def edit_element (self, widget, el):
        self.controller.gui.edit_element(el)
        return True

    def display_transcription(self, widget, annotationtype):
        self.controller.gui.open_adhoc_view('transcription',
                                            source="here/annotationTypes/%s/annotations/sorted" % annotationtype.id)
        return True

    def offset_element (self, widget, el):
        offset=dialog.entry_dialog(title='Enter an offset',
                                   text=_("Give the offset to use\non specified element.\nIt is in ms and can be\neither positive or negative."),
                                   default="0")
        if offset is not None:
            offset=long(offset)
        else:
            return True

        if isinstance(el, Annotation):
            self.controller.notify('ElementEditBegin', element=el, immediate=True)
            el.begin += offset
            el.end += offset
            self.controller.notify('AnnotationEditEnd', annotation=el)
            self.controller.notify('ElementEditCancel', element=el)
        elif isinstance(el, AnnotationType) or isinstance(el, Package):
            batch_id=object()
            for a in el.annotations:
                self.controller.notify('ElementEditBegin', element=a, immediate=True)
                a.begin += offset
                a.end += offset
                self.controller.notify('AnnotationEditEnd', annotation=a, batch=batch_id)
                self.controller.notify('ElementEditCancel', element=a)
        #elif isinstance(el, Schema):
        #    batch_id=object()
        #    for at in el.annotationTypes:
        #        for a in at.annotations:
        #            self.controller.notify('ElementEditBegin', element=a, immediate=True)
        #            a.begin += offset
        #            a.end += offset
        #            self.controller.notify('AnnotationEditEnd', annotation=a, batch=batch_id)
        #            self.controller.notify('ElementEditCancel', element=a)
        return True

    def copy_id (self, widget, el):
        clip=gtk.clipboard_get()
        clip.set_text(el.id)
        return True

    def browse_element (self, widget, el):
        self.controller.gui.open_adhoc_view('browser', element=el)
        return True

    def query_element (self, widget, el):
        self.controller.gui.open_adhoc_view('interactivequery', here=el, source="here")
        return True

    def delete_element (self, widget, el):
        self.controller.delete_element(el)
        return True

    def delete_elements (self, widget, el, elements):
        batch_id=object()
        if isinstance(el, AnnotationType) or isinstance(el, RelationType):
            for e in elements:
                self.controller.delete_element(e, batch_id=batch_id)
        return True

    def pick_color(self, widget, element):
        self.controller.gui.update_color(element)
        return True

    def add_menuitem(self, menu=None, item=None, action=None, *param, **kw):
        if item is None or item == "":
            i = gtk.SeparatorMenuItem()
        else:
            i = gtk.MenuItem(item, use_underline=False)
        if action is not None:
            i.connect('activate', action, *param, **kw)
        menu.append(i)
        return i

    def make_base_menu(self, element):
        """Build a base popup menu dedicated to the given element.

        @param element: the element
        @type element: an Advene element

        @return: the built menu
        @rtype: gtk.Menu
        """
        menu = gtk.Menu()

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

        # FIXME
        #if hasattr(element, 'viewableType'):
        #    self.make_bundle_menu(element, menu)

        specific_builder={
            Annotation: self.make_annotation_menu,
            Relation: self.make_relation_menu,
            AnnotationType: self.make_annotationtype_menu,
            RelationType: self.make_relationtype_menu,
            #Schema: self.make_schema_menu,
            View: self.make_view_menu,
            Package: self.make_package_menu,
            Query: self.make_query_menu,
            #Resources: self.make_resources_menu,
            #ResourceData: self.make_resourcedata_menu,
            }

        for t, method in specific_builder.iteritems():
            if isinstance(element, t):
                method(element, menu)

        menu.show_all()
        return menu

    def renumber_annotations(self, m, at):
        """Renumber all annotations of a given type.
        """
        d = gtk.Dialog(title=_("Renumbering annotations of type %s") % self.controller.get_title(at),
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 ))
        l=gtk.Label(_("Renumber all annotations according to their order.\n\nThis will replace the first numeric value of the annotation content with the new annotation number. If no numeric value is found and the annotation is structured, it will insert the number. *If no numeric value is found and the annotation is of type text/plain, it will overwrite the annotation content.*\nThe offset parameter allows you to renumber from the annotation number offset."))
        l.set_line_wrap(True)
        l.show()
        d.vbox.add(l)

        hb=gtk.HBox()
        l=gtk.Label(_("Offset"))
        hb.pack_start(l, expand=False)
        s=gtk.SpinButton()
        s.set_range(1, len(at.annotations))
        s.set_value(1)
        s.set_increments(1, 5)
        hb.add(s)
        d.vbox.pack_start(hb, expand=False)

        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        d.show_all()
        dialog.center_on_mouse(d)

        res=d.run()
        ret=None
        if res == gtk.RESPONSE_OK:
            re_number=re.compile('(\d+)')
            re_struct=re.compile('^num=(\d+)$', re.MULTILINE)
            offset=s.get_value_as_int()-1
            l=at.annotations
            l.sort(key=lambda a: a.fragment.begin)
            batch_id=object()
            for i, a in enumerate(l[offset:]):
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
                if data is not None:
                    # FIXME: for this kind of batch operations, we
                    # should record the global changes.
                    self.controller.notify('ElementEditBegin', element=a, immediate=True)
                    a.content.data=data
                    self.controller.notify('AnnotationEditEnd', annotation=a, batch=batch_id)
                    self.controller.notify('ElementEditCancel', element=a)
        else:
            ret=None

        d.destroy()
        return True

    def common_submenu(self, element):
        """Build the common submenu for all elements.
        """
        submenu=gtk.Menu()
        def add_item(*p, **kw):
            self.add_menuitem(submenu, *p, **kw)

        # Common to all other elements:
        add_item(_("Edit"), self.edit_element, element)
        if config.data.preferences['expert-mode']:
            add_item(_("Browse"), self.browse_element, element)
        add_item(_("Query"), self.query_element, element)

        def open_in_browser(i, v):
            c=self.controller.build_context(here=element)
            url=c.evaluate('here/absolute_url')
            self.controller.open_url(url)
            return True
        add_item(_("Open in web browser"), open_in_browser, element)

        if not self.readonly:
            # Common to deletable elements
            if type(element) in (Annotation, Relation, View, Query,
                                 AnnotationType, RelationType): # ResourceData
                add_item(_("Delete"), self.delete_element, element)

            #if type(element) == Resources and type(element.parent) == Resources:
            #    # Add Delete item to Resources except for the root resources (with parent = package)
            #    add_item(_("Delete"), self.delete_element, element)

            ## Common to offsetable elements
            if (config.data.preferences['expert-mode']
                and type(element) in (Annotation, AnnotationType, Package)):
                add_item(_("Offset"), self.offset_element, element)

        submenu.show_all()
        return submenu


    def activate_submenu(self, element):
        """Build an "activate" submenu for the given annotation"""
        submenu=gtk.Menu()
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

        add_item(_("Go to..."), self.goto_annotation, element)
        add_item(_("Loop"), loop_on_annotation, element)
        add_item(_("Duplicate"), self.duplicate_annotation, element)
        item = gtk.MenuItem(_("Highlight"), use_underline=False)
        item.set_submenu(self.activate_submenu(element))
        menu.append(item)


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
                    item=gtk.MenuItem(self.get_title(i), use_underline=False)
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
            # FIXME
            #if el.incomingRelations:
            #    i=gtk.MenuItem(_("Incoming"))
            #    submenu.append(i)
            #    i=gtk.SeparatorMenuItem()
            #    submenu.append(i)
            #    for t, l in el.typedRelatedIn.iteritems():
            #        at=self.controller.package.get_element_by_id(t)
            #        m=gtk.MenuItem(self.controller.get_title(at), use_underline=False)
            #        amenu=gtk.Menu()
            #        m.set_submenu(amenu)
            #        amenu.connect('map', build_submenu, at, l)
            #        submenu.append(m)
            #if submenu.get_children():
            #    # There were incoming annotations. Use a separator
            #    i=gtk.SeparatorMenuItem()
            #    submenu.append(i)
            #if el.outgoingRelations:
            #    i=gtk.MenuItem(_("Outgoing"))
            #    submenu.append(i)
            #    i=gtk.SeparatorMenuItem()
            #    submenu.append(i)
            #    for t, l in el.typedRelatedOut.iteritems():
            #        at=self.controller.package.get_element_by_id(t)
            #        m=gtk.MenuItem(self.controller.get_title(at), use_underline=False)
            #        amenu=gtk.Menu()
            #        m.set_submenu(amenu)
            #        amenu.connect('map', build_submenu, at, l)
            #        submenu.append(m)
            #submenu.show_all()
            return False

        # FIXME
        #if element.relations:
        #    i=gtk.MenuItem(_("Related annotations"), use_underline=False)
        #    submenu=gtk.Menu()
        #    i.set_submenu(submenu)
        #    submenu.connect('map', build_related, element)
        #    menu.append(i)
        #
        #    if element.incomingRelations:
        #        i=gtk.MenuItem(_("Incoming relations"), use_underline=False)
        #        submenu=gtk.Menu()
        #        i.set_submenu(submenu)
        #        submenu.connect('map', build_submenu, element, element.incomingRelations)
        #        menu.append(i)
        #
        #    if element.outgoingRelations:
        #        i=gtk.MenuItem(_("Outgoing relations"), use_underline=False)
        #        submenu=gtk.Menu()
        #        i.set_submenu(submenu)
        #        submenu.connect('map', build_submenu, element, element.outgoingRelations)
        #        menu.append(i)

        add_item("")

        item = gtk.MenuItem()
        item.add(image_from_position(self.controller,
                                     position=element.begin,
                                     height=60))
        item.connect('activate', self.goto_annotation, element)
        menu.append(item)

        #add_item(element.content.data[:40])
        add_item(_('Begin: %s')
                 % helper.format_time (element.begin))
        add_item(_('End: %s') % helper.format_time (element.end))
        return

    def make_relation_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(element.content.data)
        add_item(_('Members:'))
        for a in element:
            item=gtk.MenuItem(self.get_title(a), use_underline=False)
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
        return

    def make_resourcedata_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
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
            dialog.message_dialog(_("A caption dynamic view for %s already seems to exist.") % self.controller.get_title(at))
            return True
        v=p.create_view(id=ident,
                        mimetype='application/x-advene-ruleset')
        v.title=_("Caption %s annotations") % self.controller.get_title(at)
        
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
        add_item(_('Create a static view'), lambda i: create_static(element))
        add_item(_('Generate a caption dynamic view'), lambda i: self.create_dynamic_view(element))
        add_item(_('Display as transcription'), lambda i: self.controller.gui.open_adhoc_view('transcription', source='here/annotationTypes/%s/annotations/sorted' % element.id))
        add_item(_('Display annotations in table'), lambda i: self.controller.gui.open_adhoc_view('table', elements=element.annotations))
        if self.readonly:
            return
        add_item(_('Select a color'), self.pick_color, element)
        add_item(_('Create a new annotation...'), self.create_element, Annotation, element)
        add_item(_('Delete all annotations...'), self.delete_elements, element, element.annotations)
        add_item(_('Renumber annotations'), self.renumber_annotations, element)

        add_item('')
        i=gtk.MenuItem(_('%d annotations(s)') % len(element.annotations))
        menu.append(i)
        i.set_sensitive(False)

        return

    def make_relationtype_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_('Select a color'), self.pick_color, element)
        add_item(_('Delete all relations...'), self.delete_elements, element, element.relations)
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
            except Exception, e:
                self.controller.log(_('Exception in query: %s') % unicode(e))
            return True

        m=gtk.MenuItem(_('Apply query on...'))
        menu.append(m)
        sm=gtk.Menu()
        m.set_submenu(sm)
        for (expr, label) in (
             ('package', _('the package')),
             ('package/annotations', _('all annotations of the package')),
             ('package/annotations/first', _('the first annotation of the package')),
            ):
            i=gtk.MenuItem(label)
            i.connect('activate', try_query, expr)
            sm.append(i)
        return

    def make_view_menu(self, element, menu):
        def wysiwyg_edit(i, e):
            c=self.controller.build_context(here=e)
            url=c.evaluate('here/view/_richedit/absolute_url')
            self.controller.open_url(url)
            return True

        def open_in_browser(i, v):
            c=self.controller.build_context()
            url=c.evaluate('here/view/%s/absolute_url' % v.id)
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
        if 'html' in element.content.mimetype and helper.get_id(element.rootPackage.views, '_richedit'):
            # The richedit view is available. Propose to use it.
            add_item(_('Edit in the WYSIWYG editor'), wysiwyg_edit, element)
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
