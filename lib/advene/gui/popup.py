"""Popup menu for Advene elements.

Generic popup menu used by the various Advene views.
"""

import pygtk
pygtk.require('2.0')
import gtk

from gettext import gettext as _

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View
from advene.model.query import Query
from advene.model.bundle import StandardXmlBundle

import advene.gui.util
import advene.util.vlclib
import advene.gui.edit.elements

class Menu:
    def __init__(self, element=None, controller=None):
        self.element=element
        self.controller=controller
        self.menu=self.make_base_menu(element)

    def popup(self):
        self.menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def get_title (self, element):
        """Return the element title."""
        c = element.viewableClass
        if hasattr (element, 'title') and element.title is not None:
            name=element.title
        elif hasattr (element, 'id') and element.id is not None:
            name=element.id
        else:
            name=str(element)
        return "%s %s" % (c, name)

    def goto_annotation (self, widget, ann):
        c=self.controller
        pos = c.create_position (value=ann.fragment.begin,
                                 key=c.player.MediaTime,
                                 origin=c.player.AbsolutePosition)
        c.update_status (status="set", position=pos)
        return True

    def activate_annotation (self, widget, ann):
        self.controller.notify("AnnotationActivate", annotation=ann)
        return True

    def desactivate_annotation (self, widget, ann):
        self.controller.notify("AnnotationDeactivate", annotation=ann)
        return True

    def activate_related (self, widget, ann):
        for r in ann.relations:
            for a in r.members:
                if a != ann:
                    self.activate_annotation(widget, a)
        return True

    def desactivate_related (self, widget, ann):
        for r in ann.relations:
            for a in r.members:
                if a != ann:
                    self.desactivate_annotation(widget, a)
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

    def edit_element (self, widget, el):
        try:
            pop = advene.gui.edit.elements.get_edit_popup (el, self.controller)
        except TypeError, e:
            print _("Error: unable to find an edit popup for %s:\n%s") % (el, unicode(e))
        else:
            pop.edit ()
        return True

    def browse_element (self, widget, el):
        browser = advene.gui.views.browser.Browser(el)
        browser.popup()
        return True

    def delete_element (self, widget, el):
        p=el.ownerPackage
        if isinstance(el, Annotation):
            p.annotations.remove(el)
            self.controller.notify('AnnotationDelete', annotation=el)
        elif isinstance(el, Relation):
            p.relations.remove(el)
            self.controller.notify('RelationDelete', relation=el)
        elif isinstance(el, AnnotationType):
            if len(el.annotations) > 0:
                dialog = gtk.MessageDialog(
                    None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                    _("Cannot delete the annotation type %s:\nthere are still annotations of this type.") % (el.title or el.id))
                dialog.run()
                dialog.destroy()
                return True
            p.annotationTypes.remove(el)
            self.controller.notify('AnnotationTypeDelete', annotationtype=el)
        elif isinstance(el, RelationType):
            if len(el.relations) > 0:
                dialog = gtk.MessageDialog(
                    None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                    _("Cannot delete the relation type %s:\nthere are still relations of this type.") % (el.title or el.id))
                dialog.run()
                dialog.destroy()
                return True
            p.relationTypes.remove(el)
            self.controller.notify('RelationTypeDelete', relationtype=el)
        elif isinstance(el, Schema):
            if len(el.annotationTypes) > 0 or len(el.relationTypes) > 0:
                dialog = gtk.MessageDialog(
                    None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
                    _("Cannot delete the schema %s:\nthere are still types in it.") % (el.title or el.id))
                dialog.run()
                dialog.destroy()
                return True
            p.schemas.remove(el)
            self.controller.notify('SchemaDelete', schema=el)
        elif isinstance(el, View):
            p.views.remove(el)
            self.controller.notify('ViewDelete', view=el)
        elif isinstance(el, Query):
            p.queries.remove(el)
            self.controller.notify('QueryDelete', query=el)
        return True

    def add_menuitem(self, menu=None, item=None, action=None, *param, **kw):
        if item is None or item == "":
            i = gtk.SeparatorMenuItem()
        else:
            i = gtk.MenuItem(item)
        if action is not None:
            i.connect("activate", action, *param, **kw)
        menu.append(i)

    def make_base_menu(self, element):
        """Build a base popup menu dedicated to the given element.

        @param element: the element
        @type element: an Advene element

        @return: the built menu
        @rtype: gtk.Menu
        """
        menu = gtk.Menu()

        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)

        add_item(self.get_title(element))
        add_item("")

        if isinstance(element, StandardXmlBundle):
            self.make_bundle_menu(element, menu)
            menu.show_all()
            return menu

        # Common to all other elements:
        add_item(_("Edit"), self.edit_element, element)
        add_item(_("Browse"), self.browse_element, element)

        # Common to deletable elements
        if type(element) in (Annotation, Relation, View, Query,
                             Schema, AnnotationType, RelationType):
            add_item(_("Delete"), self.delete_element, element)

        specific_builder={
            Annotation: self.make_annotation_menu,
            Relation: self.make_relation_menu,
            AnnotationType: self.make_annotationtype_menu,
            RelationType: self.make_relationtype_menu,
            Schema: self.make_schema_menu,
            View: self.make_view_menu,
            Package: self.make_package_menu,
            Query: self.make_query_menu,
            }

        try:
            b=specific_builder[type(element)]
            b(element, menu)
        except KeyError:
            print "No menu for %s" % str(type(element))
            pass

        menu.show_all()
        return menu

    def activate_submenu(self, element):
        """Build an "activate" submenu for the given annotation"""
        submenu=gtk.Menu()
        def add_item(*p, **kw):
            self.add_menuitem(submenu, *p, **kw)
            
        add_item(_("Activate"), self.activate_annotation, element)
        add_item(_("Desactivate"), self.desactivate_annotation, element)
        if element.relations:
            add_item(_("Activate related"), self.activate_related, element)
            add_item(_("Desactivate related"), self.desactivate_related, element)
        submenu.show_all()
        return submenu
    
    def make_annotation_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)

        add_item(_("Go to..."), self.goto_annotation, element)

        item = gtk.MenuItem(_("Highlight"))
        item.set_submenu(self.activate_submenu(element))
        menu.append(item)

        add_item("")

        item = gtk.MenuItem()
        i = gtk.Image()
        i.set_from_pixbuf(advene.gui.util.png_to_pixbuf (self.controller.imagecache[element.fragment.begin]))
        item.add (i)
        item.connect("activate", self.goto_annotation, element)
        menu.append(item)

        add_item(element.content.data)
        add_item(_("Begin: %s")
                 % advene.util.vlclib.format_time (element.fragment.begin))
        add_item(_("End: %s") % advene.util.vlclib.format_time (element.fragment.end))
        return

    def make_relation_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(element.content.data)
        add_item(_("Members:"))
        for a in element.members:
            add_item(self.get_title(a), self.goto_annotation, a)
        return

    def make_package_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(_("Create a new view..."), self.create_element, View, element)
        add_item(_("Create a new annotation..."), self.create_element, Annotation, element)
        #add_item(_("Create a new relation..."), self.create_element, Relation, element)
        add_item(_("Create a new schema..."), self.create_element, Schema, element)
        add_item(_("Create a new query..."), self.create_element, Query, element)
        return

    def make_schema_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(_("Create a new annotation type..."),
                 self.create_element, AnnotationType, element)
        add_item(_("Create a new relation type..."),
                 self.create_element, RelationType, element)
        return

    def make_annotationtype_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        add_item(_("Create a new annotation..."), self.create_element, Annotation, element)
        return

    def make_relationtype_menu(self, element, menu):
        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)
        #add_item(_("Create a new relation..."), self.create_element, Relation, element)
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
        if element.viewableType == 'query-list':
            add_item(_("Create a new query..."), self.create_element, Query, element.rootPackage)
        elif element.viewableType == 'view-list':
            add_item(_("Create a new view..."), self.create_element, View, element.rootPackage)
        elif element.viewableType == 'schema-list':
            add_item(_("Create a new schema..."), self.create_element, Schema, element.rootPackage)
        return

