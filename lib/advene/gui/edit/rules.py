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
"""Display and edit a Rule."""

import logging
logger = logging.getLogger(__name__)

from gi.repository import Gdk
from gi.repository import Gtk

import re

import advene.rules.elements
from advene.rules.elements import Event, Condition, ConditionList, Action, ActionList, Rule, SubviewList
import advene.core.config as config
from advene.gui.util import dialog
import advene.util.helper as helper

from advene.gui.edit.tales import TALESEntry

from gettext import gettext as _

class EditGeneric:
    def get_widget(self):
        return self.widget

    def get_model(self):
        return self.model

    def update_value(self):
        """Updates the value of the represented element.

        After that, the element can be accessed through get_model().
        """
        return True

    def invalid_items(self):
        """Returns the names of invalid items.
        """
        return []

class EditRuleSet(EditGeneric):
    """Edit form for RuleSets"""
    def __init__(self, ruleset, catalog=None, editable=True, controller=None):
        self.model=ruleset
        # List of used EditRule instances
        self.editlist=[]
        self.catalog=catalog
        self.editable=editable
        self.controller=controller
        self.widget=self.build_widget()
        for rule in self.model:
            self.add_rule(rule, append=False)
        # Focus on the first rule
        self.widget.set_current_page(0)

    def get_packed_widget(self):
        """Return an enriched widget (with rules add and remove buttons)."""
        vbox=Gtk.VBox()
        vbox.set_homogeneous (False)

        def add_rule_cb(button=None):
            if not self.editable:
                return True
            # Create a new default Rule
            event=Event("AnnotationBegin")
            ra=self.catalog.get_action("Message")
            action=Action(registeredaction=ra, catalog=self.catalog)
            for p in ra.parameters:
                action.add_parameter(p, ra.defaults.get(p, ''))
            # Find the next rulename index
            l=[ int(i) for i in re.findall(_('Rule')+'\s*(\d+)', ''.join(r.name for r in self.model)) ]
            idx=max(l or [ 0 ] ) + 1
            rule=Rule(name=_("Rule") + str(idx),
                      event=event,
                      action=action)
            self.add_rule(rule)
            return True

        def add_subview_cb(button=None):
            if not self.editable:
                return True
            rule=SubviewList(name=_("Subviews"))
            self.add_rule(rule)
            return True

        def remove_rule_cb(button=None):
            """Remove the currently activated rule."""
            if not self.editable:
                return True
            current=self.widget.get_current_page()
            w=self.widget.get_nth_page(current)
            l=[edit
               for edit in self.editlist
               if edit.get_widget() == w ]
            if len(l) == 1:
                edit=l[0]
                self.editlist.remove(edit)
                self.model.remove(edit.model)
                self.widget.remove_page(current)
            elif len(l) > 1:
                logger.error("Error in remove_rule")
            return True

        hb=Gtk.HBox()

        b=Gtk.Button(stock=Gtk.STOCK_ADD)
        b.connect('clicked', add_rule_cb)
        b.set_sensitive(self.editable)
        b.set_tooltip_text(_("Add a new rule"))
        hb.pack_start(b, False, True, 0)

        b=Gtk.Button(stock=Gtk.STOCK_SELECT_COLOR)
        b.set_label(_("Subview"))
        b.connect('clicked', add_subview_cb)
        b.set_sensitive(self.editable)
        b.set_tooltip_text(_("Add a subview list"))
        hb.pack_start(b, False, True, 0)

        b=Gtk.Button(stock=Gtk.STOCK_REMOVE)
        b.connect('clicked', remove_rule_cb)
        b.set_sensitive(self.editable)
        b.set_tooltip_text(_("Remove the current rule"))
        hb.pack_start(b, False, True, 0)


        vbox.pack_start(hb, False, True, 0)

        vbox.add(self.get_widget())

        return vbox

    def add_rule(self, rule, append=True):
        # Insert the given rule
        if not self.editable:
            return True
        if isinstance(rule, Rule):
            edit=EditRule(rule, self.catalog, controller=self.controller)
        elif isinstance(rule, SubviewList):
            edit=EditSubviewList(rule, controller=self.controller)

        eb=Gtk.EventBox()
        l=Gtk.Label(label=rule.name)
        edit.set_update_label(l)
        eb.add(l)

        eb.connect('drag-data-get', self.drag_sent)
        eb.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                           config.data.get_target_types('rule'),
                           Gdk.DragAction.COPY )
        eb.show_all()

        self.editlist.append(edit)
        if append and not rule in self.model:
            self.model.add_rule(rule)
        self.widget.append_page(edit.get_widget(), eb)
        self.widget.set_current_page(-1)
        return True

    def invalid_items(self):
        i=[]
        for e in self.editlist:
            i.extend(e.invalid_items())
        return i

    def update_value(self):
        if not self.editable:
            return False
        iv=self.invalid_items()
        if iv:
            dialog.message_dialog(
                _("The following items seem to be\ninvalid TALES expressions:\n\n%s") %
                "\n".join(iv),
                icon=Gtk.MessageType.ERROR)
            return False
        for e in self.editlist:
            e.update_value()
        return True

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        if targetType == config.data.target_type['rule']:
            # Get the current rule's content

            current=self.widget.get_current_page()
            w=self.widget.get_nth_page(current)
            l=[edit
               for edit in self.editlist
               if edit.get_widget() == w ]
            if len(l) == 1:
                edit=l[0]
                # We have the model. Convert it to XML
                selection.set(selection.get_target(), 8, edit.model.xml_repr().encode('utf8'))
            elif len(l) > 1:
                logger.error("Error in drag")
            return True

        else:
            logger.warn("Unknown target type for drag: %d" % targetType)
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['rule']:
            xml=str(selection.get_data(), 'utf8')
            if 'subviewlist' in xml:
                rule=SubviewList()
            else:
                rule=Rule()
            rule.from_xml_string(xml, catalog=self.catalog)

            name=rule.name
            l = [ r for r in self.model if r.name == name ]
            while l:
                name = "%s1" % name
                l = [ r for r in self.model if r.name == name ]
            rule.name = name
            self.add_rule(rule)
        else:
            logger.warn("Unknown target type for drop: %d" % targetType)
        return True


    def build_widget(self):
        # Create a notebook:
        notebook=Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.LEFT)
        notebook.popup_enable()
        notebook.set_scrollable(True)

        notebook.connect('drag-data-received', self.drag_received)
        notebook.drag_dest_set(Gtk.DestDefaults.MOTION |
                               Gtk.DestDefaults.HIGHLIGHT |
                               Gtk.DestDefaults.ALL,
                               config.data.get_target_types('rule'),
                               Gdk.DragAction.COPY)
        #b=Gtk.Button(rule.name)
        #b.connect('clicked', popup_edit, rule, catalog)
        #b.show()
        #vbox.add(b)
        return notebook

class EditQuery(EditGeneric):
    """Edit form for Query"""
    def __init__(self, query, controller=None, editable=True):
        self.model=query
        self.sourceentry=None
        self.valueentry=None
        self.controller=controller
        self.editconditionlist=[]
        if query.condition is not None:
            self.composition=query.condition.composition
        else:
            self.composition='and'
        self.editable=editable
        self.widget=self.build_widget()

    def invalid_items(self):
        iv=[]
        if not self.sourceentry.is_valid():
            iv.append(_("Source expression"))
        if self.valueentry is not None and not self.valueentry.is_valid():
            iv.append(_("Return expression"))

        for ec in self.editconditionlist:
            iv.extend(ec.invalid_items())

        return iv

    def update_value(self):
        if not self.editable:
            return False
        self.model.sources=self.sourceentry.get_text().split(';')
        if self.valueentry is None:
            v='element'
        else:
            v=self.valueentry.get_text()
        if v == '' or v == 'element':
            self.model.rvalue=None
        else:
            self.model.rvalue=v

        for w in self.editconditionlist:
            w.update_value()

        if self.editconditionlist:
            self.model.condition=ConditionList([ e.model for e in self.editconditionlist ])
            self.model.condition.composition=self.composition
        else:
            self.model.condition=None
        return True

    def remove_condition(self, widget, conditionwidget, hbox):
        if self.editable:
            self.editconditionlist.remove(conditionwidget)
            hbox.destroy()
        return True

    def add_condition(self, widget, conditionsbox):
        cond=Condition(lhs="element/content/data",
                       operator="contains",
                       rhs="string:???")
        self.add_condition_widget(cond, conditionsbox)
        return True

    def add_condition_widget(self, cond, conditionsbox):
        hb=Gtk.HBox()
        conditionsbox.add(hb)

        w=EditCondition(cond, editable=self.editable,
                        controller=self.controller,
                        parent=self)

        self.editconditionlist.append(w)

        hb.add(w.get_widget())
        w.get_widget().show()

        b=Gtk.Button(stock=Gtk.STOCK_REMOVE)
        b.set_sensitive(self.editable)
        b.connect('clicked', self.remove_condition, w, hb)
        b.show()
        hb.pack_start(b, False, True, 0)

        hb.show()

        return True

    def build_widget(self):
        frame=Gtk.Frame()

        vbox=Gtk.VBox()
        frame.add(vbox)
        vbox.show()

        # Event
        ef=Gtk.Frame.new(_("For all elements in "))
        predef=[ ('package/annotations', _("All annotations of the package")),
                 ('package/views', _("All views of the package")),
                 ('here/annotations', _("The context annotations")),
                 ('here/type/annotations', _("The annotations of the context type"))]
        for at in self.controller.package.annotationTypes:
            predef.append( ('package/annotationTypes/%s/annotations' % at.id,
                            _("Annotations of type %s") % self.controller.get_title(at) ) )
        self.sourceentry=TALESEntry(context=self.model,
                                    controller=self.controller,
                                    predefined=predef)
        self.sourceentry.set_text(";".join(self.model.sources))
        self.sourceentry.set_editable(self.editable)
        ef.add(self.sourceentry.widget)
        ef.show_all()
        vbox.pack_start(ef, False, True, 0)

        if config.data.preferences['expert-mode']:
            # Return value
            vf=Gtk.Frame.new(_("Return "))
            self.valueentry=TALESEntry(context=self.model,
                                       predefined=[ ('element', _("The element")),
                                                    ('element/content/data', _("The element's content")) ],
                                       controller=self.controller)
            v=self.model.rvalue
            if v is None or v == '':
                v='element'
            self.valueentry.set_text(v)
            self.valueentry.set_editable(self.editable)
            vf.add(self.valueentry.widget)
            vf.show_all()
            vbox.pack_start(vf, False, True, 0)
        else:
            self.valueentry=None

        # Conditions
        if config.data.preferences['expert-mode']:
            cf=Gtk.Frame.new(_("If the element matches "))
        else:
            cf=Gtk.Frame.new(_("Return the element if it matches "))
        conditionsbox=Gtk.VBox()
        cf.add(conditionsbox)

        # "Add condition" button
        hb=Gtk.HBox()
        b=Gtk.Button(stock=Gtk.STOCK_ADD)
        b.connect('clicked', self.add_condition, conditionsbox)
        b.set_sensitive(self.editable)
        hb.pack_start(b, False, True, 0)
        hb.set_homogeneous(False)

        hb.add(Gtk.HBox())

        def change_composition(combo):
            self.composition=combo.get_current_element()
            return True

        c=dialog.list_selector_widget( [ ('and', _("All conditions must be met") ),
                                         ('or', _("Any condition can be met") ) ],
                                       preselect=self.composition,
                                       callback=change_composition)
        hb.pack_start(c, False, True, 0)

        conditionsbox.pack_start(hb, False, False, 0)

        cf.show_all()

        if isinstance(self.model.condition, advene.rules.elements.ConditionList):
            for c in self.model.condition:
                self.add_condition_widget(c, conditionsbox)

        vbox.pack_start(cf, False, True, 0)

        frame.show()

        return frame

class EditRule(EditGeneric):
    def __init__(self, rule, catalog=None, editable=True, controller=None):
        # Original rule
        self.model=rule

        self.catalog=catalog
        self.editable=editable

        self.controller=controller

        self.namelabel=None

        self.composition=self.model.condition.composition

        self.editactionlist=[]
        self.editconditionlist=[]
        self.widget=self.build_widget()

    def set_update_label(self, l):
        """Specify a label to be updated when the rule name changes"""
        self.namelabel=l

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        if targetType == config.data.target_type['rule']:
            selection.set(selection.get_target(), 8, self.model.xml_repr().encode('utf8'))
        else:
            logger.warn("Unknown target type for drag: %d" % targetType)
        return True

    def invalid_items(self):
        iv=[]
        for e in self.editactionlist:
            iv.extend(e.invalid_items())
        for e in self.editconditionlist:
            iv.extend(e.invalid_items())
        return iv

    def update_value(self):
        if not self.editable:
            return False

        self.editevent.update_value()
        for w in self.editactionlist:
            w.update_value()
        for w in self.editconditionlist:
            w.update_value()

        self.model.name=self.name_entry.get_text()

        self.model.event=Event(self.editevent.current_event)

        if self.editconditionlist:
            self.model.condition=ConditionList([ e.model for e in self.editconditionlist ])
        else:
            self.model.condition=self.model.default_condition
        self.model.condition.composition=self.composition

        # Rebuild actionlist from editactionlist
        self.model.action=ActionList([ e.model for e in self.editactionlist ])

        return True

    def update_name(self, entry):
        if self.namelabel:
            self.namelabel.set_label(entry.get_text())
        self.framelabel.set_markup(_("Rule <b>%s</b>") % entry.get_text().replace('<', '&lt;'))
        return True

    def remove_condition(self, widget, conditionwidget, hbox):
        self.editconditionlist.remove(conditionwidget)
        hbox.destroy()
        return True

    def remove_action(self, widget, actionwidget, hbox):
        self.editactionlist.remove(actionwidget)
        hbox.destroy()
        return True

    def add_condition(self, widget, conditionsbox):
        cond=Condition(lhs="annotation/type/id",
                       operator="equals",
                       rhs="string:???")
        self.add_condition_widget(cond, conditionsbox)
        return True

    def add_condition_widget(self, cond, conditionsbox):
        hb=Gtk.HBox()
        conditionsbox.add(hb)

        w=EditCondition(cond, editable=self.editable, controller=self.controller, parent=self)

        self.editconditionlist.append(w)

        hb.add(w.get_widget())
        w.get_widget().show()

        b=Gtk.Button(stock=Gtk.STOCK_REMOVE)
        b.set_sensitive(self.editable)
        b.connect('clicked', self.remove_condition, w, hb)
        b.show()
        hb.pack_start(b, False, True, 0)

        hb.show()

        return True

    def add_action(self, widget, actionsbox):
        """Callback for the Add action button."""
        ra=self.catalog.get_action("Message")
        action=Action(registeredaction=ra, catalog=self.catalog)
        self.add_action_widget(action, actionsbox)

    def add_action_widget(self, action, actionsbox):
        """Add an action widget to the given actionsbox."""

        hb=Gtk.HBox()
        actionsbox.add(hb)

        w=EditAction(action, self.catalog, editable=self.editable,
                     controller=self.controller)
        self.editactionlist.append(w)
        hb.add(w.get_widget())
        w.get_widget().show()
        b=Gtk.Button(stock=Gtk.STOCK_REMOVE)
        b.connect('clicked', self.remove_action, w, hb)
        b.set_sensitive(self.editable)
        b.show()
        hb.pack_start(b, False, True, 0)

        hb.show()
        return True

    def build_widget(self):
        frame=Gtk.Frame()
        self.framelabel=Gtk.Label()
        self.framelabel.set_markup(_("Rule <b>%s</b>") % self.model.name.replace('<', '&lt;'))
        self.framelabel.show()
        frame.set_label_widget(self.framelabel)

        vbox=Gtk.VBox()
        frame.add(vbox)
        vbox.show()

        # Rule name
        hbox=Gtk.HBox()

        hbox.pack_start(Gtk.Label(_("Rule name")), False, False, 0)
        self.name_entry=Gtk.Entry()
        self.name_entry.set_text(self.model.name)
        self.name_entry.set_editable(self.editable)
        self.name_entry.connect('changed', self.update_name)
        hbox.add(self.name_entry)

        b=Gtk.Button(stock=Gtk.STOCK_COPY)
        b.connect('drag-data-get', self.drag_sent)
        b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                          config.data.get_target_types('rule'), Gdk.DragAction.COPY)
        hbox.pack_start(b, False, True, 0)

        hbox.show_all()
        vbox.pack_start(hbox, False, True, 0)

        # Event
        ef=Gtk.Frame.new(_("Event"))
        self.editevent=EditEvent(self.model.event, catalog=self.catalog,
                                 editable=self.editable, controller=self.controller)
        ef.add(self.editevent.get_widget())
        ef.show_all()
        vbox.pack_start(ef, False, True, 0)

        # Conditions
        cf=Gtk.Frame.new(_("If"))
        conditionsbox=Gtk.VBox()
        cf.add(conditionsbox)

        # "Add condition" button
        hb=Gtk.HBox()
        b=Gtk.Button(stock=Gtk.STOCK_ADD)
        b.connect('clicked', self.add_condition, conditionsbox)
        b.set_sensitive(self.editable)
        hb.pack_start(b, False, True, 0)
        hb.set_homogeneous(False)

        hb.add(Gtk.HBox())

        def change_composition(combo):
            self.composition=combo.get_current_element()
            return True

        c=dialog.list_selector_widget( [ ('and', _("All conditions must be met") ),
                                         ('or', _("Any condition can be met") ) ],
                                       preselect=self.composition,
                                       callback=change_composition)
        hb.pack_start(c, False, True, 0)

        conditionsbox.pack_start(hb, False, False, 0)

        cf.show_all()

        if isinstance(self.model.condition, advene.rules.elements.ConditionList):
            for c in self.model.condition:
                self.add_condition_widget(c, conditionsbox)
        else:
            if self.model.condition != self.model.default_condition:
                # Should not happen
                raise Exception("condition should be a conditionlist")

        vbox.pack_start(cf, False, True, 0)

        # Actions
        af=Gtk.Frame.new(_("Then"))
        actionsbox=Gtk.VBox()
        af.add(actionsbox)
        hb=Gtk.HBox()
        # Add Action button
        b=Gtk.Button(stock=Gtk.STOCK_ADD)
        b.connect('clicked', self.add_action, actionsbox)
        b.set_sensitive(self.editable)
        hb.pack_start(b, False, True, 0)
        hb.set_homogeneous(False)
        actionsbox.pack_start(hb, False, False, 0)

        for a in self.model.action:
            self.add_action_widget(a, actionsbox)

        vbox.pack_start(af, False, True, 0)
        af.show_all()

        frame.show()

        return frame

class EditEvent(EditGeneric):
    def __init__(self, event, catalog=None, expert=False, editable=True, controller=None):
        self.model=event
        self.current_event=event
        self.catalog=catalog
        self.controller=controller
        self.expert=expert
        self.editable=editable
        self.widget=self.build_widget()

    def update_value(self):
        # Nothing to update. The parent has the responsibility to
        # fetch the current_event value.
        return True

    def on_change_event(self, event):
        if self.editable:
            self.current_event=event

    def build_widget(self):
        hbox=Gtk.HBox()
        hbox.set_homogeneous(False)

        label=Gtk.Label(label=_("When the "))
        hbox.pack_start(label, True, True, 0)

        eventlist=self.catalog.get_described_events(expert=self.expert)
        if self.current_event not in eventlist:
            # The event was not in the list. It must be because
            # it is an expert-mode event. Add it manually.
            eventlist[self.current_event]=self.catalog.describe_event(self.current_event)

        eventname=dialog.build_optionmenu(eventlist, self.current_event, self.on_change_event,
                                          editable=self.editable)
        hbox.add(eventname)

        label=Gtk.Label(_(" occurs,"))
        hbox.add(label)

        hbox.show_all()
        return hbox

class EditCondition(EditGeneric):
    def __init__(self, condition, editable=True, controller=None, parent=None):
        self.model=condition

        self.current_operator=self.model.operator
        self.editable=editable
        self.controller=controller
        # We check if parent is a EditRuleSet or a EditQuery so that
        # we can populate the TALES expressions with appropriate values.
        self.parent=parent

        # Widgets:
        self.lhs=None # Entry
        self.rhs=None # Entry
        self.operator=None # Selector

        self.widget=self.build_widget()

    def invalid_items(self):
        iv=[]
        if not self.lhs.is_valid():
            iv.append(_("Condition expression: %s") % self.lhs.get_text())
        if (self.current_operator in Condition.binary_operators
            and not self.rhs.is_valid()):
            iv.append(_("Condition expression: %s") % self.lhs.get_text())
        return iv

    def update_value(self):
        if not self.editable:
            return False
        c=self.model
        c.operator=self.current_operator
        c.lhs=self.lhs.get_text()
        if c.operator in Condition.binary_operators:
            c.rhs=self.rhs.get_text()
        return True

    def update_widget(self):
        """Update the widget.

        Invoked when the operator has changed.
        """
        operator=self.current_operator
        if operator in Condition.binary_operators:
            self.lhs.show()
            self.rhs.show()
        elif operator in Condition.unary_operators:
            self.lhs.show()
            self.rhs.hide()
        else:
            raise Exception("Undefined operator: %s" % operator)
        return True

    def on_change_operator(self, operator):
        self.current_operator=operator
        self.update_widget()
        return True

    def build_widget(self):
        hbox=Gtk.HBox()

        if self.parent is None or isinstance(self.parent, EditRule):
            predefined=[
                ('annotation/type/id', _('The annotation type') ),
                ('annotation/content/data', _('The annotation content') ),
                ] + [
                ('annotation/content/parsed/%s' % p, _("The value of the %s attribute") % p)
                for p in set(a for at in self.controller.package.annotationTypes for a in getattr(at, '_fieldnames', [])) ] + [
                ('annotation/fragment', _('The annotation fragment') ),
                ('annotation/fragment/begin', _('The annotation begin time') ),
                ('annotation/fragment/end', _('The annotation end time') ),
                ('annotation/fragment/duration', _('The annotation duration') ),
                ('annotation/content/mimetype', _('The annotation MIME-type') ),
                ('annotation/incomingRelations', _("The annotation's incoming relations") ),
                ('annotation/outgoingRelations', _("The annotation's outgoing relations") ),
                ] + [
                ('annotation/typedRelatedIn/%s' % rt.id,
                 _("The %s-related incoming annotations") % self.controller.get_title(rt) )
                for rt in self.controller.package.relationTypes
                ] + [
                ('annotation/typedRelatedOut/%s' % rt.id,
                 _("The %s-related outgoing annotations") % self.controller.get_title(rt) )
                for rt in self.controller.package.relationTypes  ]
        elif isinstance(self.parent, EditQuery):
            predefined=[
                ('element', _('The element')),
                ('element/content/data', _("The element's content") ),
                ('element/fragment', _('The element fragment') ),
                ('element/fragment/begin', _('The element begin time') ),
                ('element/fragment/end', _('The element end time') ),
                ('element/fragment/duration', _('The element duration') ),
                ('element/type/id', _('The element type') ),
                ('element/incomingRelations', _("The element's incoming relations") ),
                ('element/outgoingRelations', _("The element's outgoing relations") ),
                ('here', _('The context')),
                ('here/fragment', _('The context fragment') ),
                ('here/annotations', _('The context annotations') ),
                ('here/type/annotations', _('The annotations of the context type') ),
                ]
        self.lhs=TALESEntry(controller=self.controller, predefined=predefined)
        self.lhs.set_text(self.model.lhs or "")
        self.lhs.set_editable(self.editable)
        self.lhs.show()
        self.lhs.set_no_show_all(True)

        if self.parent is None or isinstance(self.parent, EditRule):
            predef=[ ('string:%s' % at.id,
                      _("annotation-type %s") % self.controller.get_title(at) )
                     for at in self.controller.package.annotationTypes
                     ] + [ ('string:%s' % at.id,
                            _("relation-type %s") % self.controller.get_title(at) )
                           for at in self.controller.package.relationTypes
                           ] + predefined
        elif isinstance(self.parent, EditQuery):
            predef=predefined
        self.rhs=TALESEntry(controller=self.controller,
                            predefined=predef)
        self.rhs.set_text(self.model.rhs or "")
        self.rhs.set_editable(self.editable)
        self.rhs.hide()
        self.rhs.set_no_show_all(True)

        operators={}
        operators.update(Condition.binary_operators)
        operators.update(Condition.unary_operators)

        def description_getter(element):
            if element in Condition.condition_categories:
                return Condition.condition_categories[element]
            else:
                return operators[element][0]

        self.selector=dialog.CategorizedSelector(title=_("Select a condition"),
                                                 elements=list(operators),
                                                 categories=list(Condition.condition_categories),
                                                 current=self.current_operator,
                                                 description_getter=description_getter,
                                                 category_getter=lambda e: operators[e][1],
                                                 callback=self.on_change_operator,
                                                 editable=self.editable)
        self.operator=self.selector.get_button()

        hbox.add(self.lhs.widget)
        hbox.add(self.operator)
        hbox.add(self.rhs.widget)
        hbox.show()

        self.update_widget()

        return hbox

class EditAction(EditGeneric):
    def __init__(self, action, catalog, editable=True, controller=None):
        self.model=action

        self.editable=editable
        self.current_name=action.name
        self.current_parameters=dict(action.parameters)
        # RegisteredAction matching the self.current_name
        self.registeredaction=catalog.get_action(self.current_name)

        self.controller=controller

        # Cache the parameters value. Indexed by action name.
        # Used when using the mousewheel on the action name list:
        # it should keep the parameters values
        self.cached_parameters={}

        # Dict of parameter widgets (modified when the action name changes)
        # indexed by parameter name.
        self.paramlist={}

        self.catalog=catalog
        self.widget=self.build_widget()

    def invalid_items(self):
        iv=[ _("Parameter %s") % n
             for n in self.paramlist
             if not self.paramlist[n].entry.is_valid() ]
        return iv

    def update_value(self):
        if not self.editable:
            return False
        ra=self.catalog.get_action(self.current_name)
        self.model = Action(registeredaction=ra, catalog=self.catalog)
        regexp=re.compile('^(\(.+\)|)$')
        for n, v in self.current_parameters.items():
            # We ignore parameters fields that are empty or that match '^\(.+\)$'
            if not regexp.match(v):
                self.model.add_parameter(n, v)
        return True

    def sorted(self, l):
        """Return a sorted version of the list."""
        if isinstance(l, dict):
            res=list(l)
        else:
            res=l[:]
        res.sort()
        return res

    def on_change_name(self, element):
        if element.name == self.current_name:
            return True
        # Cache the old parameters values
        self.cached_parameters[self.current_name]=self.current_parameters.copy()

        self.current_name=element.name
        for w in self.paramlist.values():
            w.destroy()
        self.paramlist={}

        ra=self.catalog.get_action(self.current_name)
        self.registeredaction=ra
        if self.current_name in self.cached_parameters:
            self.current_parameters=self.cached_parameters[self.current_name]
        else:
            self.current_parameters={}.fromkeys(ra.parameters, "")

        for name in self.sorted(self.current_parameters):
            v=ra.default_value(name)
            p=self.build_parameter_widget(name,
                                          v,
                                          ra.describe_parameter(name))
            self.current_parameters[name]=v
            self.paramlist[name]=p
            p.show()
            self.widget.add(p)

        return True

    def on_change_parameter(self, entry, talesentry, name):
        value=talesentry.get_text()
        self.current_parameters[name]=value
        return True

    def build_parameter_widget(self, name, value, description):
        hbox=Gtk.HBox()
        label=Gtk.Label(label=name)
        hbox.pack_start(label, False, True, 0)

        ra=self.registeredaction
        if ra:
            # Get predefined values
            if callable(ra.predefined):
                predefined=ra.predefined(self.controller)[name]
            elif ra.predefined is not None:
                predefined=ra.predefined[name]
            else:
                predefined=None

        entry=TALESEntry(controller=self.controller, predefined=predefined)
        entry.set_text(value)
        entry.set_editable(self.editable)
        entry.entry.connect('changed', self.on_change_parameter, entry, name)

        entry.entry.set_tooltip_text(description)

        hbox.entry=entry

        hbox.pack_start(entry.widget, True, True, 0)
        hbox.show_all()
        return hbox

    def build_widget(self):
        vbox=Gtk.VBox()

        vbox.add(Gtk.HSeparator())

        def description_getter(element):
            if hasattr(element, 'description'):
                return element.description
            else:
                # it is a category
                return self.catalog.action_categories[element]

        c=self.catalog
        def expert_filter(l, attr=None):
            if config.data.preferences['expert-mode']:
                return l
            else:
                expert_categories = ('expert', 'gui', 'state')
                if attr is None:
                    # No attribute, directly test value
                    return [ e for e in l if not e in expert_categories ]
                else:
                    return [ e for e in l if not getattr(e, attr) in expert_categories ]

        self.selector=dialog.CategorizedSelector(title=_("Select an action"),
                                                 elements=expert_filter(sorted(c.actions.values()), 'category'),
                                                 categories=expert_filter(list(c.action_categories)),
                                                 current=c.actions[self.current_name],
                                                 description_getter=description_getter,
                                                 category_getter=lambda e: e.category,
                                                 callback=self.on_change_name,
                                                 editable=self.editable)
        self.name=self.selector.get_button()
        vbox.add(self.name)

        if self.model.registeredaction:
            # Action is derived from a RegisteredAction
            # we have information about its parameters.
            ra=self.model.registeredaction
            for name in self.sorted(ra.parameters):
                try:
                    v=self.model.parameters[name]
                except KeyError:
                    v=ra.default_value(name)
                p=self.build_parameter_widget(name=name,
                                              value=v,
                                              description=ra.describe_parameter(name))
                self.current_parameters[name]=v
                self.paramlist[name]=p
                vbox.add(p)
        else:
            # We display existing parameters
            for name in self.sorted(self.model.parameters):
                p=self.build_parameter_widget(name, self.model.parameters[name], "")
                self.paramlist[name]=p
                vbox.add(p)

        vbox.add(Gtk.HSeparator())

        vbox.show_all()
        return vbox

class EditSubviewList(EditGeneric):
    """Edit a subview list.
    """
    COLUMN_ELEMENT=0
    COLUMN_LABEL=1
    COLUMN_ID=2
    COLUMN_STATUS=3
    def __init__(self, subviewlist, editable=True, controller=None):
        # Original rule
        # subviews is a list of view ids that are to be activated
        self.model=subviewlist
        self.editable=editable
        self.controller=controller
        self.editconditionlist=[]
        self.namelabel=None
        self.widget=self.build_widget()

    def set_update_label(self, l):
        """Specify a label to be updated when the rule name changes"""
        self.namelabel=l

    def update_name(self, entry):
        if self.namelabel:
            self.namelabel.set_label(entry.get_text())
        return True

    def refresh(self):
        self.store.clear()
        l=[ v
            for v in self.controller.package.views
            if helper.get_view_type(v) == 'dynamic' ]
        for v in l:

            self.store.append([ v,
                                self.controller.get_title(v),
                                v.id,
                                v.id in self.model ])

    def toggled_cb(self, renderer, path, model, column):
        model[path][column] = not model[path][column]
        return True

    def build_widget(self):
        vbox=Gtk.VBox()

        self.store=Gtk.ListStore( object, str, str, bool )
        self.refresh()

        self.treeview=Gtk.TreeView(model=self.store)

        renderer = Gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        renderer.connect('toggled', self.toggled_cb, self.store, self.COLUMN_STATUS)
        column = Gtk.TreeViewColumn(_('Activate?'), renderer, active=self.COLUMN_STATUS)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('View'), renderer, text=self.COLUMN_LABEL)
        column.set_resizable(True)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Id'), renderer, text=self.COLUMN_ID)
        column.set_resizable(True)
        self.treeview.append_column(column)

        sw=Gtk.ScrolledWindow()
        sw.add(self.treeview)
        vbox.pack_start(sw, True, True, 0)

        vbox.show_all()
        return vbox

    def update_value(self):
        """Updates the value of the represented element.

        After that, the element can be accessed through get_model().
        """
        self.model.clear()
        self.model.extend([ row[self.COLUMN_ID]
                            for row in self.store
                            if row[self.COLUMN_STATUS] ])
        return True
