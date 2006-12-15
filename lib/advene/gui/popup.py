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
"""Popup menu for Advene elements.

Generic popup menu used by the various Advene views.
"""

import gtk
import sre
import os

from gettext import gettext as _

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.view import View
from advene.model.query import Query
from advene.model.bundle import StandardXmlBundle

from advene.gui.views.interactivequery import InteractiveQuery
from advene.gui.views.transcription import TranscriptionView
import advene.gui.util
import advene.util.helper as helper
import advene.gui.edit.elements

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
        t=helper.get_title(self.controller, element)
        if len(t) > 80:
            t=t[:80]
        return t

    def goto_annotation (self, widget, ann):
        c=self.controller
        pos = c.create_position (value=ann.fragment.begin,
                                 key=c.player.MediaTime,
                                 origin=c.player.AbsolutePosition)
        c.update_status (status="set", position=pos)
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

    def activate_stbv (self, view):
        self.controller.activate_stbv(view)
        return True

    def create_element(self, widget, elementtype=None, parent=None):
        #print "Creating a %s in %s" % (elementtype, parent)
        cr = advene.gui.edit.create.CreateElementPopup(type_=elementtype,
                                                       parent=parent,
                                                       controller=self.controller)
        cr.popup()
        return True

    def do_insert_resource_file(self, parent=None, filename=None, id_=None):
        if id_ is None:
            # Generate the id_
            basename = os.path.basename(filename)
            id_=sre.sub('[^a-zA-Z0-9_.]', '_', basename)
        size=os.stat(filename).st_size
        f=open(filename, 'r')
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
            id_=sre.sub('[^a-zA-Z0-9_.]', '_', basename)
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

    def do_remove_resource_dir(self, r):
        for c in r.children():
            if isinstance(c, ResourceData):
                self.do_remove_resource_file(c)
            elif isinstance(c, Resources):
                self.do_remove_resource_dir(c)
            else:
                print "Strange bug in do_remove_resource_dir"
                return True
        p=r.parent
        del(p[r.id])
        self.controller.notify('ResourceDelete',
                               resource=r)
        return True

    def do_remove_resource_file(self, r):
        p=r.parent
        del(p[r.id])
        self.controller.notify('ResourceDelete',
                               resource=r)
        return True

    def insert_resource_data(self, widget, parent=None):
        filename=advene.gui.util.get_filename(title=_("Choose the file to insert"))
        if filename is None:
            return True
        basename = os.path.basename(filename)
        id_=sre.sub('[^a-zA-Z0-9_.]', '_', basename)
        if id_ != basename:
            while True:
                id_ = advene.gui.util.entry_dialog(title=_("Select a valid identifier"),
                                                   text=_("The filename %s contains invalid characters\nthat have been replaced.\nYou can modify this identifier if necessary:") % filename,
                                                   default=id_)
                if id_ is None:
                    # Edition cancelled
                    return True
                elif sre.match('^[a-zA-Z0-9_.]+$', id_):
                    break
        self.do_insert_resource_file(parent=parent, filename=filename, id_=id_)
        return True

    def insert_resource_directory(self, widget, parent=None):
        dirname=advene.gui.util.get_dirname(title=_("Choose the directory to insert"))
        if dirname is None:
            return True

        self.do_insert_resource_dir(parent=parent, dirname=dirname)
        return True

    def edit_element (self, widget, el):
        try:
            pop = advene.gui.edit.elements.get_edit_popup (el, self.controller, 
                                                           editable=not self.readonly)
        except TypeError, e:
            print _("Error: unable to find an edit popup for %(element)s:\n%(error)s") % {
                'element': el,
                'error': unicode(e)}
        else:
            pop.edit ()
        return True

    def display_transcription(self, widget, annotationtype):
        transcription = TranscriptionView(controller=self.controller,
                                          annotationtype=annotationtype)

        transcription.popup()
        return True

    def popup_get_offset(self):
        offset=advene.gui.util.entry_dialog(title='Enter an offset',
                                            text=_("Give the offset to use\non specified element.\nIt is in ms and can be\neither positive or negative."),
                                            default="0")
        if offset is not None:
            return long(offset)
        else:
            return offset

    def offset_element (self, widget, el):
        offset = self.popup_get_offset()
        if offset is None:
            return True
        if isinstance(el, Annotation):
            el.fragment.begin += offset
            el.fragment.end += offset
            self.controller.notify('AnnotationEditEnd', annotation=el)
        elif isinstance(el, AnnotationType) or isinstance(el, Package):
            for a in el.annotations:
                a.fragment.begin += offset
                a.fragment.end += offset
                self.controller.notify('AnnotationEditEnd', annotation=a)
        elif isinstance(el, Schema):
            for at in el.annotationTypes:
                for a in at.annotations:
                    a.fragment.begin += offset
                    a.fragment.end += offset
                    self.controller.notify('AnnotationEditEnd', annotation=a)
        return True

    def copy_id (self, widget, el):
        clip=gtk.clipboard_get()
        clip.set_text(el.id)
        return True

    def browse_element (self, widget, el):
        browser = advene.gui.views.browser.Browser(el, controller=self.controller)
        browser.popup()
        return True

    def query_element (self, widget, el):
        iq = InteractiveQuery(here=el, controller=self.controller, source="here")
        iq.popup()
        return True

    def delete_element (self, widget, el):
        p=el.ownerPackage
        if isinstance(el, Annotation):
            rels=[ helper.get_title(self.controller, r.id)
                   for r in el.rootPackage.relations
                   if el in r.members ]
            if rels:
                advene.gui.util.message_dialog(
                    _("Cannot delete the annotation %(annotation)s:\nThe following relation(s) use it:\n%(relations)s") % { 'annotation': helper.get_title(self.controller, el), 
                                                                                                                            'relations': ", ".join(rels)})
                return True
            p.annotations.remove(el)
            self.controller.notify('AnnotationDelete', annotation=el)
        elif isinstance(el, Relation):
            p.relations.remove(el)
            self.controller.notify('RelationDelete', relation=el)
        elif isinstance(el, AnnotationType):
            if len(el.annotations) > 0:
                advene.gui.util.message_dialog(
                    _("Cannot delete the annotation type %s:\nthere are still annotations of this type.") % (el.title or el.id))
                return True
            el.schema.annotationTypes.remove(el)
            self.controller.notify('AnnotationTypeDelete', annotationtype=el)
        elif isinstance(el, RelationType):
            if len(el.relations) > 0:
                advene.gui.util.message_dialog(
                    _("Cannot delete the relation type %s:\nthere are still relations of this type.") % (el.title or el.id))
                return True
            el.schema.relationTypes.remove(el)
            self.controller.notify('RelationTypeDelete', relationtype=el)
        elif isinstance(el, Schema):
            if len(el.annotationTypes) > 0 or len(el.relationTypes) > 0:
                advene.gui.util.message_dialog(
                    _("Cannot delete the schema %s:\nthere are still types in it.") % (el.title or el.id))
                return True
            p.remove(el)
            self.controller.notify('SchemaDelete', schema=el)
        elif isinstance(el, View):
            p.views.remove(el)
            self.controller.notify('ViewDelete', view=el)
        elif isinstance(el, Query):
            p.queries.remove(el)
            self.controller.notify('QueryDelete', query=el)
        elif isinstance(el, Resources):
            self.do_remove_resource_dir(el)
        elif isinstance(el, ResourceData):
            self.do_remove_resource_file(el)
        return True

    def delete_elements (self, widget, el, elements):
        p=el.ownerPackage
        if isinstance(el, AnnotationType) or isinstance(el, RelationType):
            for e in elements:
                self.delete_element(widget, e)
        return True

    def add_menuitem(self, menu=None, item=None, action=None, *param, **kw):
        if item is None or item == "":
            i = gtk.SeparatorMenuItem()
        else:
            i = gtk.MenuItem(item, use_underline=False)
        if action is not None:
            i.connect("activate", action, *param, **kw)
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
        title.set_submenu(self.common_submenu(element))

        add_item("")

        try:
            i=element.id
            add_item(_("Copy id %s") % i,
                     self.copy_id,
                     element)
        except AttributeError:
            pass

        if isinstance(element, StandardXmlBundle):
            self.make_bundle_menu(element, menu)
            menu.show_all()
            return menu

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

        for t, method in specific_builder.iteritems():
            if isinstance(element, t):
                method(element, menu)

        menu.show_all()
        return menu

    def common_submenu(self, element):
        """Build the common submenu for all elements.
        """
        submenu=gtk.Menu()
        def add_item(*p, **kw):
            self.add_menuitem(submenu, *p, **kw)

        # Common to all other elements:
        add_item(_("Edit"), self.edit_element, element)
        add_item(_("Browse"), self.browse_element, element)
        add_item(_("Query"), self.query_element, element)

        if not self.readonly:
            # Common to deletable elements
            if type(element) in (Annotation, Relation, View, Query,
                                 Schema, AnnotationType, RelationType):
                add_item(_("Delete"), self.delete_element, element)

            # Common to offsetable elements
            if type(element) in (Annotation, Schema, AnnotationType, Package):
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

        add_item(_("Go to..."), self.goto_annotation, element)
        add_item(_("Duplicate"), self.duplicate_annotation, element)

        def build_submenu(submenu, el, items):
            """Build the submenu for the given element.
            """
            if submenu.get_children():
                # The submenu was already populated.
                return False
            for i in items:
                item=gtk.MenuItem(self.get_title(i), use_underline=False)
                m=Menu(element=i, controller=self.controller)
                item.set_submenu(m.menu)
                submenu.append(item)
            submenu.show_all()
            return False

        if element.incomingRelations:
            i=gtk.MenuItem(_("Incoming relations"), use_underline=False)
            submenu=gtk.Menu()
            i.set_submenu(submenu)
            submenu.connect("map", build_submenu, element, element.incomingRelations)
            menu.append(i)

        if element.outgoingRelations:
            i=gtk.MenuItem(_("Outgoing relations"), use_underline=False)
            submenu=gtk.Menu()
            i.set_submenu(submenu)
            submenu.connect("map", build_submenu, element, element.outgoingRelations)
            menu.append(i)

        item = gtk.MenuItem(_("Highlight"), use_underline=False)
        item.set_submenu(self.activate_submenu(element))
        menu.append(item)

        add_item("")

        item = gtk.MenuItem()
        item.add(advene.gui.util.image_from_position(self.controller,
                                                     position=element.fragment.begin,
                                                     height=60))
        item.connect("activate", self.goto_annotation, element)
        menu.append(item)

        #add_item(element.content.data[:40])
        add_item(_("Begin: %s")
                 % helper.format_time (element.fragment.begin))
        add_item(_("End: %s") % helper.format_time (element.fragment.end))
        return

    def make_relation_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(element.content.data)
        add_item(_("Members:"))
        for a in element.members:
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
        add_item(_("Create a new view..."), self.create_element, View, element)
        add_item(_("Create a new annotation..."), self.create_element, Annotation, element)
        #add_item(_("Create a new relation..."), self.create_element, Relation, element)
        add_item(_("Create a new schema..."), self.create_element, Schema, element)
        add_item(_("Create a new query..."), self.create_element, Query, element)
        return

    def make_resources_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_("Create a new folder..."), self.create_element, Resources, element)
        add_item(_("Create a new resource file..."), self.create_element, ResourceData, element)
        add_item(_("Insert a new resource file..."), self.insert_resource_data, element)
        add_item(_("Insert a new resource directory..."), self.insert_resource_directory, element)
        if isinstance(element.parent, Resources):
            add_item(_("Delete the resource..."), self.delete_element, element)
        return

    def make_resourcedata_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_("Delete the resource..."), self.delete_element, element)
        return

    def make_schema_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_("Create a new annotation type..."),
                 self.create_element, AnnotationType, element)
        add_item(_("Create a new relation type..."),
                 self.create_element, RelationType, element)
        return

    def make_annotationtype_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(_("Display as transcription"), self.display_transcription, element)
        if self.readonly:
            return
        add_item(_("Create a new annotation..."), self.create_element, Annotation, element)
        add_item(_("Delete all annotations..."), self.delete_elements, element, element.annotations)
        return

    def make_relationtype_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        add_item(_("Delete all relations..."), self.delete_elements, element, element.relations)
        return

    def make_query_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        return

    def make_view_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if element.content.mimetype == 'application/x-advene-ruleset':
            add_item(_("Activate view"), self.activate_stbv, element)
        return

    def make_bundle_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        if self.readonly:
            return
        if element.viewableType == 'query-list':
            add_item(_("Create a new query..."), self.create_element, Query, element.rootPackage)
        elif element.viewableType == 'view-list':
            add_item(_("Create a new view..."), self.create_element, View, element.rootPackage)
        elif element.viewableType == 'schema-list':
            add_item(_("Create a new schema..."), self.create_element, Schema, element.rootPackage)
        return

