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
"""Dialogs for the creation of new elements."""

import advene.core.config as config

from gettext import gettext as _

import sys
import time
import sre

import gtk

from advene.model.package import Package
from advene.model.fragment import MillisecondFragment
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.view import View
from advene.model.query import Query
from advene.rules.elements import RuleSet, Rule, Event, Action

import advene.gui.util
import advene.gui.edit.elements
import advene.util.helper as helper

element_label = helper.element_label

class ViewType:
    def __init__(self, id_, title):
        self.id = id_
        self.title = title

    def __str__(self):
        return self.title

class CreateElementPopup(object):
    def __init__(self, type_=None, parent=None, controller=None):
        self.type_=type_
        self.parent=parent
        self.controller=controller
        self.dialog=None

    def display(self):
        pass

    def generate_id(self):
        return self.controller.package._idgenerator.get_id(self.type_)

    def build_widget(self, modal=False):
        i=self.generate_id()
        if modal:
            flags=gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL
        else:
            flags=gtk.DIALOG_DESTROY_WITH_PARENT

        d=advene.gui.util.title_id_dialog(title=_("%s creation")  % element_label[self.type_],
                                          text=_("To create a new element of type %s,\nyou must give the following information.") % element_label[self.type_],
                                          element_title=i,
                                          element_id=i,
                                          flags=flags)
        d.type_combo=None

        # Choose a type if possible
        if self.type_ in (Annotation, Relation, AnnotationType, RelationType,
                          View, Query, Resources, ResourceData):
            hbox = gtk.HBox()
            l = gtk.Label(_("Type"))
            hbox.pack_start(l)

            if self.type_ == Annotation:
                if isinstance(self.parent, AnnotationType):
                    type_list = [ self.parent ]
                else:
                    type_list = self.parent.annotationTypes
            elif self.type_ == Relation:
                if isinstance(self.parent, RelationType):
                    type_list = [ self.parent ]
                else:
                    type_list = self.parent.relationTypes
            elif self.type_ in (AnnotationType, RelationType):
                type_list = [ ViewType('text/plain', _("Plain text content")),
                              ViewType('application/x-advene-structured', _("Simple-structured content")),
                              ViewType('application/x-advene-zone', _("Rectangular zone content")),
                              ]
            elif self.type_ == View:
                type_list = [ ViewType('application/x-advene-ruleset', _("Dynamic view")),
                              ViewType('text/html', _("HTML template")),
                              ViewType('application/xml', _("Plain XML")),
                              ViewType('image/svg+xml', _("SVG template")),
                              ViewType('text/plain', _("Plain text template")),
                              ]
            elif self.type_ == Query:
                type_list = [ ViewType('application/x-advene-simplequery', _("Simple query")),
                              ViewType('application/x-advene-sparql-query', _("SPARQL query")) ]
            elif self.type_ == Resources:
                type_list = [ ViewType(Resources.DIRECTORY_TYPE, _("Directory")) ]
            elif self.type_ == ResourceData:
                type_list = [ ViewType("file", _("Resource File")) ]
            else:
                print _("Error in advene.gui.edit.create.build_widget: invalid type %s") % self.type_
                return None

            if not type_list:
                advene.gui.util.message_dialog(_("No available type."))
                return None

            d.type_combo = advene.gui.util.list_selector_widget(
                members=[ (t, self.controller.get_title(t)) for t in type_list  ],
                preselect=type_list[0])
            hbox.pack_start(d.type_combo)
            
            d.vbox.add(hbox)

        d.show_all()
        return d

    def get_date(self):
        return time.strftime("%Y-%m-%d")

    def is_valid_id(self, i):
        if self.type_ == ResourceData:
            # Allow filename extensions for ResourceData
            return sre.match(r'^[a-zA-Z0-9_\.]+$', i)
        else:
            return sre.match(r'^[a-zA-Z0-9_]+$', i)

    def do_create_element(self):
        """Create the element according to the widget data.

        @return: the created element, None if an error occurred
        """
        id_ = self.dialog.id_entry.get_text()
        title_ = self.dialog.title_entry.get_text()
        # Check validity of id.
        if not self.is_valid_id(id_):
            advene.gui.util.message_dialog(
                _("The identifier %s is not valid.\nIt must be composed of non-accentuated alphabetic characters\nUnderscore is allowed.") % id_)
            return None

        if self.controller.package._idgenerator.exists(id_):
            advene.gui.util.message_dialog(
                _("The identifier %s is already defined.") % id_)
            return None
        else:
            self.controller.package._idgenerator.add(id_)

        if self.dialog.type_combo:
            t = self.dialog.type_combo.get_current_element()

        if self.type_ == Annotation:
            if isinstance(self.parent, AnnotationType):
                parent=self.parent.rootPackage
            else:
                parent=self.parent
            el=parent.createAnnotation(
                ident=id_,
                type=t,
                author=config.data.userid,
                date=self.get_date(),
                fragment=MillisecondFragment(begin=0,
                                             duration=self.controller.player.stream_duration))
            parent.annotations.append(el)
            self.controller.notify('AnnotationCreate', annotation=el)
        elif self.type_ == Relation:
            # Unused code: relations can not be created without annotations
            if isinstance(self.parent, RelationType):
                parent=self.parent.rootPackage
            else:
                parent=self.parent
            el=parent.createRelation(
                ident=id_,
                type=t,
                author=config.data.userid,
                date=self.get_date(),
                members=())
            parent.relations.append(el)
            self.controller.notify('RelationCreate', relation=el)
        elif self.type_ == Query:
            el=self.parent.createQuery(ident=id_)
            el.author=config.data.userid
            el.date=self.get_date()
            el.title=title_
            el.content.mimetype=t.id
            if t.id == 'application/x-advene-simplequery':
                # Create a basic query
                q=advene.rules.elements.Query(source="here")
                el.content.data=q.xml_repr()
                el.content.mimetype=t.id
            self.parent.queries.append(el)
            self.controller.notify('QueryCreate', query=el)
        elif self.type_ == View:
            el=self.parent.createView(
                ident=id_,
                author=config.data.userid,
                date=self.get_date(),
                clazz=self.parent.viewableClass,
                content_mimetype=t.id,
                )
            el.title=title_
            if t.id == 'application/x-advene-ruleset':
                # Create an empty ruleset to begin with
                r=RuleSet()

                # Create a new default Rule
                event=Event("AnnotationBegin")
                catalog=self.controller.event_handler.catalog
                ra=catalog.get_action("Message")
                action=Action(registeredaction=ra, catalog=catalog)
                for p in ra.parameters:
                    action.add_parameter(p, "(%s)" % ra.parameters[p])
                rule=Rule(name=_("New rule"),
                          event=event,
                          action=action)
                r.add_rule(rule)

                el.content.data=r.xml_repr()

            self.parent.views.append(el)
            self.controller.notify('ViewCreate', view=el)
        elif self.type_ == Schema:
            el=self.parent.createSchema(
                ident=id_)
            el.author=config.data.userid
            el.date=self.get_date()
            el.title=title_
            self.parent.schemas.append(el)
            self.controller.notify('SchemaCreate', schema=el)
        elif self.type_ == AnnotationType:
            if not isinstance(self.parent, Schema):
                print _("Error: bad invocation of CreateElementPopup")
                el=None
            else:
                el=self.parent.createAnnotationType(
                    ident=id_)
                el.author=config.data.userid
                el.date=self.get_date()
                el.title=title_
                el.mimetype=t.id
                el.setMetaData(config.data.namespace, 'color', 'here/tag_color')
            self.parent.annotationTypes.append(el)
            self.controller.notify('AnnotationTypeCreate', annotationtype=el)
        elif self.type_ == RelationType:
            if not isinstance(self.parent, Schema):
                print _("Error: bad invocation of CreateElementPopup")
                el=None
            else:
                el=self.parent.createRelationType(
                    ident=id_)
                el.author=config.data.userid
                el.date=self.get_date()
                el.title=title_
                el.mimetype=t.id
            self.parent.relationTypes.append(el)
            self.controller.notify('RelationTypeCreate', relationtype=el)
        elif self.type_ == Resources:
            # Create a new dir.
            # Parent should be a Resources
            self.parent[id_]=Resources.DIRECTORY_TYPE
            el=self.parent[id_]
            self.controller.notify('ResourceCreate',
                                   resource=el)
        elif self.type_ == ResourceData:
            # Create a new resource file
            self.parent[id_]=_("New resource data")
            el=self.parent[id_]
            self.controller.notify('ResourceCreate',
                                   resource=el)

        else:
            el=None
            print "Not implemented yet."
        return el

    def popup(self, modal=False):
        d=self.build_widget(modal)
        d.connect("key_press_event", advene.gui.util.dialog_keypressed_cb)
        self.dialog=d
        while True:
            d.show()
            advene.gui.util.center_on_mouse(d)
            res=d.run()
            retval=None
            if res == gtk.RESPONSE_OK:
                retval=self.do_create_element()

                if retval is not None:
                    break
            else:
                break
        d.destroy()

        if retval is not None and not modal and not isinstance(retval, Resources):
            if self.controller.gui:
                self.controller.gui.edit_element(retval)
        return retval

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    package = Package (uri=sys.argv[1])

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)

    window.set_border_width(10)
    window.set_title (package.title)
    vbox = gtk.VBox()
    window.add (vbox)

    def create_element_cb(button, t):
        cr = CreateElementPopup(type_=t, parent=package)
        cr.popup()
        return True

    for (t, l) in element_label.iteritems():
        b = gtk.Button(l)
        b.connect("clicked", create_element_cb, t)
        b.show()
        vbox.pack_start(b)

    hbox = gtk.HButtonBox()
    vbox.pack_start (hbox, expand=False)

    def validate_cb (win, package):
        filename="/tmp/package.xml"
        package.save (name=filename)
        print "Package saved as %s" % filename
        gtk.main_quit ()

    b = gtk.Button (stock=gtk.STOCK_SAVE)
    b.connect ("clicked", validate_cb, package)
    hbox.add (b)

    b = gtk.Button (stock=gtk.STOCK_QUIT)
    b.connect ("clicked", lambda w: window.destroy ())
    hbox.add (b)

    vbox.set_homogeneous (False)

    window.connect ("destroy", lambda e: gtk.main_quit())

    window.show_all()
    gtk.main ()

