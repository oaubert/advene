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
# Advene part
import advene.core.config as config

from gettext import gettext as _

import advene.gui.popup

import gtk

class RelationView:
    """Controller for the MVC representing a relation."""
    def popup(self, button):
        menu = advene.gui.popup.Menu(self, controller=self.controller)
        menu.popup()
        return True

    def __init__(self, relation=None, controller=None):
        self.relation=relation
        self.controller=controller
        self.widget=self.build_widget()
        self.widget.connect('clicked', self.activate)

    def activate(self, button):
        print "Relation %s activated" % self.relation.id
        if self.controller:
            self.controller.notify("RelationActivate", relation=self.relation)
        return True

    def build_widget(self):
        l=gtk.Label()
        l.set_markup("<b>%s</b> relation between\nann. <i>%s</i>\nand\nann. <i>%s</i>" %
                     (self.relation.type.title,
                      self.relation.members[0].id,
                      self.relation.members[1].id))
        b=gtk.Button()
        b.add(l)
        b.connect('clicked', self.popup)

        return b

    def get_widget(self):
        return self.widget

class RelationsBox:
    """
    Representation of a list of relations
    """
    def __init__ (self, package=None, controller=None):
        self.view_name = _("Relations view")
        self.view_id = 'relationview'
        self.close_on_package_load = True

        self.package=package
        self.controller=controller
        self.relationviews=[]
        self.active_color = gtk.gdk.color_parse ('red')
        self.inactive_color = gtk.Button().get_style().bg[0]
        self.widget = self.build_widget()

    def build_widget(self):
        vbox=gtk.VBox()
        for r in self.package.relations:
            v=RelationView(relation=r, controller=self.controller)
            self.relationviews.append(v)
            vbox.pack_start(v.get_widget(), expand=False)
        vbox.show_all()
        return vbox

    def debug_cb (self, widget, data=None):
        print "Debug event."
        if data is not None:
            print "Data: %s" % data
        return True

    def get_widget_for_relation (self, relation):
        bs = [ b
               for b in self.widget.get_children()
               if hasattr (b, 'relation') and b.relation == relation ]
        return bs

    def activate_relation_handler (self, context, parameters):
        relation=context.evaluateValue('relation')
        if relation is not None:
            self.activate_relation(relation)
        return True

    def desactivate_relation_handler (self, context, parameters):
        relation=context.evaluateValue('relation')
        if relation is not None:
            self.desactivate_relation(relation)
        return True

    def register_callback (self, controller=None):
        """Add the activate handler for annotations."""
        pass
        #self.beginrule=controller.event_handler.internal_rule (event="AnnotationBegin",
        #                                        method=self.activate_annotation_handler)
        #self.endrule=controller.event_handler.internal_rule (event="AnnotationEnd",
        #                                        method=self.desactivate_annotation_handler)

    def unregister_callback (self, controller=None):
        pass
        #controller.event_handler.remove_rule(self.beginrule)
        #controller.event_handler.remove_rule(self.endrule)

    def activate_relation (self, relation):
        """Activate the representation of the given relation."""
        bs = self.get_widget_for_relation (relation)
        for b in bs:
            b.active = True
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                b.modify_bg (style, self.active_color)
        return True

    def desactivate_relation (self, relation):
        """Desactivate the representation of the given relation."""
        bs = self.get_widget_for_relation (relation)
        for b in bs:
            b.active = True
            for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                b.modify_bg (style, self.inactive_color)
        return True

    def get_widget (self):
        """Return the display widget."""
        return self.widget

    def update_relation (self, element=None, event=None):
        """Update a relation's representation."""
        if event == 'RelationCreate':
            # If it does not exist yet, we should create it if it is now in self.list
            if element in self.list:
                v=RelationView(relation=element, controller=self.controller)
                self.relationviews.append(v)
                self.widget.pack_start(v.get_widget(), expand=False)
            return True

        bs = self.get_widget_for_relation (element)
        for b in bs:
            if event == 'RelationEditEnd':
                self.update_button (b)
            elif event == 'RelationDelete':
                b.destroy()
            else:
                print "Unknown event %s" % event
        return True

    def update_relation (self, element=None):
        """Update a relation's representation."""
        bs = self.get_widget_for_relation (element)
        for b in bs:
            self.update_button (b)

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        #print "drag_sent event from %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            selection.set(selection.target, 8, widget.annotation.uri.encode('utf8'))
        else:
            print "Unknown target type for drag: %d" % targetType
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        #print "drag_received event for %s" % widget.annotation.content.data
        if targetType == config.data.target_type['annotation']:
            source=self.package.annotations.get(unicode(selection.data, 'utf8'))
            dest=widget.annotation
            self.create_relation_popup(source, dest)
            # FIXME: TODO
            # Find matching relation (we need to know the package...)
            # source=self.package.annotations.get(source_id)
            # dest=self.package.annotations.get(widget.annotation.id)
            # relation_list=self.package.findMatchingRelation(source, dest)
            # if len(relation_list) == 0:
            #     raise Exception ('')
            # elif len(relation_list) == 1:
            #     # Only one relation matches: create it
            #     rel=self.package.createRelation(relation_list[0], members=(source, dest))
            #     # FIXME: append ?
            # else:
            #     # Many possible relations. Ask the user.
            #     # FIXME...
            #     rel=self.package.createRelation(chosen_relation, members=(source, dest))
        else:
            print "Unknown target type for drop: %d" % targetType
        return True
