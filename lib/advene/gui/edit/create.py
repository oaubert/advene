#! /usr/bin/env python

"""Dialogs for the creation of new elements."""

import advene.core.config as config

from gettext import gettext as _

import sys
import time

import pygtk
pygtk.require('2.0')
import gtk
import gobject
import pango

from advene.model.package import Package
from advene.model.fragment import MillisecondFragment
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

import advene.gui.edit.rules
import advene.gui.edit.elements
import advene.rules.actions

element_label = {
    Package: _("Package"),
    Annotation: _("Annotation"),
    Relation: _("Relation"),
    Schema: _("Schema"),
    AnnotationType: _("Annotation Type"),
    RelationType: _("Relation Type"),
    View: _("View"),
    }

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
        # FIXME: This would be better in a central place
        self.prefix = {
            Package: "p",
            Annotation: "a",
            Relation: "r",
            Schema: "schema-",
            AnnotationType: "at-",
            RelationType: "rt-",
            View: "view-",
            }
        self.chosen_type = None
        self.widget=self.build_widget()
        
    def get_widget(self):
        return self.widget
    
    def display(self):
        pass

    def generate_id(self):
        return self.prefix[self.type_] + str(id(self)) + str(time.clock())

    def update_type(self, widget, t):
        self.chosen_type = t
        return True
    
    def build_widget(self):
        vbox = gtk.VBox()

        l = gtk.Label(_("To create a new element of type %s,\nyou must give the following information.") % element_label[self.type_])
        vbox.add(l)

        # Identifier
        hbox = gtk.HBox()
        l = gtk.Label(_("Identifier"))
        hbox.pack_start(l)

        self.id_entry = gtk.Entry()
        self.id_entry.set_text(self.generate_id())
        hbox.pack_start(self.id_entry)

        vbox.add(hbox)

        # Choose a type
        if self.type_ in (Annotation, Relation, View):
            hbox = gtk.HBox()
            l = gtk.Label(_("Type"))
            hbox.pack_start(l)

            if self.type_ == Annotation:
                type_list = self.parent.annotationTypes
            elif self.type_ == Relation:
                type_list = self.parent.relationTypes
            elif self.type_ == View:
                type_list = [ ViewType('text/html', _("HTML template")),
                              ViewType('application/x-advene-ruleset', _("Ruleset")) ]
            else:
                print _("Error in advene.gui.edit.create.build_widget: invalid type %s") % self.type_
                return None

            if not type_list:
                dialog = gtk.MessageDialog(
                    None, gtk.DIALOG_DESTROY_WITH_PARENT,
                    gtk.MESSAGE_WARNING, gtk.BUTTONS_OK,
                    _("No available type."))
                dialog.set_position(gtk.WIN_POS_MOUSE)
                dialog.run()
                dialog.destroy()
                return None
            
            self.chosen_type = type_list[0]
            
            menu = gtk.Menu()
            
            for t in type_list:
                i = gtk.MenuItem(t.title or t.id)
                i.connect("activate", self.update_type, t)
                i.show()
                menu.append(i)

            type_menu = gtk.OptionMenu()            
            type_menu.set_menu(menu)
            hbox.pack_start(type_menu)
            
            vbox.add(hbox)

        return vbox

    def get_date(self):
        return time.strftime("%F")
    
    def validate_cb(self, button, window):
        id_ = self.id_entry.get_text()
        t = self.chosen_type

        if self.type_ == Annotation:
            el=self.parent.createAnnotation(
                ident=id_,
                type=t,
                author=config.data.userid,
                date=self.get_date(),
                fragment=MillisecondFragment(begin=0,
                                             duration=self.controller.player.stream_duration))
            el.title=id_
            self.parent.annotations.append(el)
            self.controller.notify('AnnotationEditEnd', annotation=el)
        elif self.type_ == Relation:
            el=self.parent.createRelation(
                ident=id_,
                type=t,
                author=config.data.userid,
                date=self.get_date(),
                members=())
            el.title=id_
            self.parent.relations.append(el)
            self.controller.notify('RelationEditEnd', relation=el)
        elif self.type_ == View:
            el=self.parent.createView(
                ident=id_,
                author=config.data.userid,
                date=self.get_date(),
                clazz=self.parent.viewableClass,
                content_mimetype=t.id,
                )
            el.title=id_
            if t.id == 'application/x-advene-ruleset':
                # Create an empty ruleset to begin with
                el.content.data="<ruleset xmlns='http://liris.cnrs.fr/advene/ruleset'></ruleset>"
            self.parent.views.append(el)
            self.controller.notify('ViewEditEnd', view=el)
        elif self.type == Schema:
            el=self.parent.createSchema(
                ident=id_,
                author=config.data.userid,
                date=self.get_date())
            el.title=id_
            self.parent.schemas.append(el)
            self.controller.notify('SchemaEditEnd', schema=el)
        elif self.type == AnnotationType:
            if not isinstance(self.parent, Schema):
                print _("Error: bad invocation of CreateElementPopup")
                el=None
            else:
                el=self.parent.createAnnotationType(
                    ident=id_,
                    author=config.data.userid,
                    date=self.get_date())
                el.title=id_
            self.controller.notify('AnnotationTypeEditEnd', annotationtype=el)
            #FIXME: complete
        else:
            el=None
            print "Not implemented yet."
            
        window.destroy()
        
        if el is not None:
            try:
                pop = advene.gui.edit.elements.get_edit_popup (el, controller=self.controller)
            except TypeError, e:
                print _("Error: unable to find an edit popup for %s:\n%s") % (el, str(e))
            else:
                pop.edit ()
        return True
    
    def popup(self):
        window = gtk.Window (gtk.WINDOW_TOPLEVEL)
        window.set_title(_("Creation: %s") % element_label[self.type_])
        
        vbox = gtk.VBox()
        window.add(vbox)
        
        vbox.add (self.widget)

        # Button bar
        hbox = gtk.HButtonBox()

        b = gtk.Button (stock=gtk.STOCK_OK)
        b.connect ("clicked", self.validate_cb, window)
        hbox.add (b)

        b = gtk.Button (stock=gtk.STOCK_CANCEL)
        b.connect ("clicked", lambda w: window.destroy ())
        hbox.add (b)

        vbox.pack_start (hbox, expand=False)
        window.show_all ()
        return True
    
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
        # FIXME: parent can be different from package (for AnnotationType and RelationType)
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
        package.save (as=filename)
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

