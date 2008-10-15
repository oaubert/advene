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
"""Dialogs for the creation of new elements.
"""

import advene.core.config as config

from gettext import gettext as _

import sys
import re

import gtk

from advene.model.cam.package import Package
from advene.model.cam.annotation import Annotation
from advene.model.cam.tag import AnnotationType, RelationType
from advene.model.cam.list import Schema
from advene.model.cam.resource import Resource
from advene.model.cam.view import View
from advene.model.cam.query import Query
from advene.rules.elements import RuleSet, Rule, Event, Action, SubviewList

from advene.gui.util import dialog
import advene.util.helper as helper

element_label = helper.element_label

class ViewType:
    def __init__(self, id_, title):
        self.id = id_
        self.title = title

    def __str__(self):
        return self.title

class CreateElementPopup(object):
    """Popup for creating elements.

    If takes as parameter the element type, its parent and the
    application controller. When present, the optional mimetype
    parameter is used as default mimetype.
    """
    def __init__(self, type_=None, parent=None, controller=None, mimetype=None):
        self.type_=type_
        self.mimetype=mimetype
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

        d=dialog.title_id_dialog(title=_("%s creation")  % element_label[self.type_],
                                          text=_("To create a new element of type %s,\nyou must give the following information.") % element_label[self.type_],
                                          element_title=i,
                                          element_id=i,
                                          flags=flags)
        d.type_combo=None

        # Choose a type if possible
        if self.type_ in (Annotation, AnnotationType, RelationType,
                          View, Query, Resource):
            hbox = gtk.HBox()
            l = gtk.Label(_("Type"))
            hbox.pack_start(l)

            if self.type_ == Annotation:
                if isinstance(self.parent, AnnotationType):
                    type_list = [ self.parent ]
                else:
                    type_list = self.parent.annotation_types
            elif self.type_ in (AnnotationType, RelationType):
                type_list = [ ViewType('text/plain', _("Plain text content")),
                              ViewType('application/x-advene-structured', _("Simple-structured content")),
                              ViewType('application/x-advene-zone', _("Rectangular zone content")),
                              ViewType('image/svg+xml', _("SVG graphics content")),
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
            elif self.type_ == Resource:
                type_list = [ ViewType("file", _("Resource File")) ]
            else:
                print "Error in advene.gui.edit.create.build_widget: invalid type %s" % self.type_
                return None

            if not type_list:
                dialog.message_dialog(_("No available type."))
                return None

            # Check for self.mimetype
            if self.mimetype is None:
                preselect=type_list[0]
            else:
                l=[ e for e in type_list if e.id == self.mimetype ]
                if l:
                    preselect=l[0]
                else:
                    # Insert self.mimetype in the list
                    preselect=ViewType(self.mimetype, self.mimetype)
                    type_list.insert(0, preselect)
            d.type_combo = dialog.list_selector_widget(
                members=[ (t, self.controller.get_title(t)) for t in type_list  ],
                preselect=preselect)
            hbox.pack_start(d.type_combo)

            d.vbox.add(hbox)

        d.show_all()
        return d

    def is_valid_id(self, i):
        if self.type_ == Resource:
            # FIXME: to check
            # Allow filenameextensions for Resource (?)
            return re.match(r'^[a-zA-Z0-9_\.]+$', i)
        else:
            return re.match(r'^[a-zA-Z0-9_]+$', i)

    def do_create_element(self):
        """Create the element according to the widget data.

        @return: the created element, None if an error occurred
        """
        id_ = self.dialog.id_entry.get_text()
        title_ = self.dialog.title_entry.get_text()
        # Check validity of id.
        if not self.is_valid_id(id_):
            dialog.message_dialog(
                _("The identifier %s is not valid.\nIt must be composed of non-accentuated alphabetic characters\nUnderscore is allowed.") % id_)
            return None

        if self.controller.package._idgenerator.exists(id_):
            dialog.message_dialog(
                _("The identifier %s is already defined.") % id_)
            return None
        else:
            self.controller.package._idgenerator.add(id_)

        if self.dialog.type_combo:
            t = self.dialog.type_combo.get_current_element()

        if self.type_ == Annotation:
            if isinstance(self.parent, AnnotationType):
                parent=self.controller.package
            else:
                parent=self.parent
            el=parent.create_annotation(
                id=id_,
                type=t,
                media=self.controller.current_media,
                begin=0,
                end=self.controller.player.stream_duration)

            if el.type._fieldnames:
                el.content.data="\n".join( "%s=" % f for f in sorted(el.type._fieldnames) )
            self.controller.notify('AnnotationCreate', annotation=el)
        elif self.type_ == Query:
            el=self.parent.create_query(id=id_, mimetype=t.id)
            el.title=title_
            if t.id == 'application/x-advene-simplequery':
                # Create a basic query
                q=advene.rules.elements.SimpleQuery(source="here")
                el.content.data=q.xml_repr()
            self.controller.notify('QueryCreate', query=el)
        elif self.type_ == View:
            el=self.parent.create_view(id=id_, mimetype=t.id)
            el.title=title_
            if t.id == 'application/x-advene-ruleset':
                # Create an empty ruleset to begin with
                r=RuleSet()

                # Create a new default Rule
                rule=SubviewList(name=_("Subviews"),
                                 elements=[])
                r.add_rule(rule)

                event=Event("AnnotationBegin")
                catalog=self.controller.event_handler.catalog
                ra=catalog.get_action("Message")
                action=Action(registeredaction=ra, catalog=catalog)
                for p in ra.parameters:
                    action.add_parameter(p, ra.defaults.get(p, ''))
                rule=Rule(name=_("Rule") + '1',
                          event=event,
                          action=action)
                r.add_rule(rule)

                el.content.data=r.xml_repr()
            self.controller.notify('ViewCreate', view=el)
        elif self.type_ == Schema:
            el=self.parent.create_schema(id=id_)
            el.title=title_
            self.controller.notify('SchemaCreate', schema=el)
        elif self.type_ == AnnotationType:
            if not isinstance(self.parent, Schema):
                print "Error: bad invocation of CreateElementPopup"
                el=None
            else:
                el=self.controller.package.create_annotation_type(id=id_)
                el.title=title_
                el.mimetype=t.id
                el.color=self.controller.package._color_palette.next()
                el.element_color='here/tag_color'
            self.controller.notify('AnnotationTypeCreate', annotationtype=el)
        elif self.type_ == RelationType:
            if not isinstance(self.parent, Schema):
                print "Error: bad invocation of CreateElementPopup"
                el=None
            else:
                el=self.controller.package.create_relation_type(id=id_)
                el.title=title_
                el.mimetype=t.id
                el.color=self.controller.package._color_palette.next()
                el.element_color='here/tag_color'
            self.controller.notify('RelationTypeCreate', relationtype=el)
        elif self.type_ == Resource:
            # Create a new resource file
            # FIXME: to implement
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
        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        self.dialog=d
        while True:
            d.show()
            dialog.center_on_mouse(d)
            res=d.run()
            retval=None
            if res == gtk.RESPONSE_OK:
                retval=self.do_create_element()

                if retval is not None:
                    break
            else:
                break
        d.destroy()

        if retval is not None and not modal:
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
        b.connect('clicked', create_element_cb, t)
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
    b.connect('clicked', validate_cb, package)
    hbox.add (b)

    b = gtk.Button (stock=gtk.STOCK_QUIT)
    b.connect('clicked', lambda w: window.destroy ())
    hbox.add (b)

    vbox.set_homogeneous (False)

    window.connect('destroy', lambda e: gtk.main_quit())

    window.show_all()
    gtk.main ()

