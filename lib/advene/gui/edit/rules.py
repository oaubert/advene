#! /usr/bin/env python

"""Display and edit a Rule."""

import gtk

import sre
import copy

import advene.rules.elements
from advene.rules.elements import Event, Condition, ConditionList, Action, ActionList
from advene.rules.elements import Rule, RuleSet

from gettext import gettext as _

class EditGeneric:
    def get_widget(self):
        return self.widget

    def get_model(self):
        return self.model
    
    def update_value(self):
        """Updates the value of the represented element.

        After that, the element can be access throught get_model().
        """
        pass
    
    def build_option(self, elements, current, on_change_element, editable=True):
        """Build an OptionMenu.

        elements is a dict holding (key, values) where the values will be used as labels
        current is the current activated element (i.e. one of the keys)
        on_change_element is the method which will be called upon option modification.
        
        Its signature is:
            def on_change_element([self,] optionmenu, elements):
                
        elements will be a list of keys with the same index as the optionmenu, i.e. :
            chosen_key=elements[optionmenu.get_history()]
        """
        # List of elements, with the same index as the menus
        optionmenu = gtk.OptionMenu()

        items=[]
        cnt=0
        index=0
        menu=gtk.Menu()
        for k, v in elements.iteritems():
            item = gtk.MenuItem(v)
            item.show()
            menu.append(item)
            items.append(k)
            if (k == current): index = cnt
            cnt += 1
            
        optionmenu.set_menu(menu)
        optionmenu.set_history(index)
        optionmenu.connect("changed", on_change_element, items)
        optionmenu.set_sensitive(editable)
        optionmenu.show()
        return optionmenu

class EditRuleSet(EditGeneric):
    """Edit form for RuleSets"""
    def __init__(self, ruleset, catalog=None, editable=True):
        self.model=ruleset
        # List of used EditRule instances
        self.editlist=[]
        self.catalog=catalog
        self.editable=editable
        self.widget=self.build_widget()

    def remove_rule(self, button):
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
            print "Error in remove_rule"
        return True

    def get_packed_widget(self):
        """Return an enriched widget (with rules add and remove buttons)."""
        vbox=gtk.VBox()
        vbox.set_homogeneous (False)

        vbox.add(self.get_widget())

        hb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", self.add_rule)
        b.set_sensitive(self.editable)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.connect("clicked", self.remove_rule)
        b.set_sensitive(self.editable)
        hb.pack_start(b, expand=False)
        vbox.add(hb)
        
        return vbox

    def add_rule(self, button):
        if not self.editable:
            return True
        event=Event("AnnotationBegin")
        ra=self.catalog.get_action("Message")
        action=Action(registeredaction=ra, catalog=self.catalog)
        for p in ra.parameters:
            action.add_parameter(p, "(%s)" % ra.parameters[p])
        rule=Rule(name=_("New rule"),
                  event=event,
                  action=action)
        edit=EditRule(rule, self.catalog)
        l=gtk.Label(rule.name)
        edit.set_update_label(l)
        self.editlist.append(edit)
        #print "Model: %d rules" % len(self.model)
        self.model.add_rule(rule)
        #print "-> Model: %d rules" % len(self.model)
        self.widget.append_page(edit.get_widget(), l)
        self.widget.set_current_page(-1)
        return True

    def update_value(self):
        if self.editable:
            for e in self.editlist:
                e.update_value()
        #print "update_value for %d rules" % len(self.model)
        
        # Clear the list (we need to keep the same reference as before)
        # del self.model[:]        
        
    def build_widget(self):
        # Create a notebook:
        notebook=gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_LEFT)
        notebook.popup_enable()
        notebook.set_scrollable(True)
        
        for rule in self.model:
            edit=EditRule(rule, self.catalog, editable=self.editable)
            l=gtk.Label(rule.name)
            edit.set_update_label(l)
            self.editlist.append(edit)
            notebook.append_page(edit.get_widget(), l)
            
        #b=gtk.Button(rule.name)
        #b.connect("clicked", popup_edit, rule, catalog)
        #b.show()
        #vbox.add(b)
        return notebook
    
class EditQuery(EditGeneric):
    """Edit form for Query"""
    def __init__(self, query, editable=True):
        self.model=query
        self.sourceentry=None
        self.valueentry=None
        self.editconditionlist=[]
        self.editable=editable
        self.widget=self.build_widget()
        
    def update_value(self):
        if not self.editable:
            return True
        self.model.source=self.sourceentry.get_text()
        v=self.valueentry.get_text()
        if v == '' or v == 'element':
            self.model.rvalue=None
        else:
            self.model.rvalue=v
        
        for w in self.editconditionlist:
            w.update_value()

        if self.editconditionlist:
            self.model.condition=ConditionList([ e.model for e in self.editconditionlist ])
        else:
            self.model.condition=None
        return

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
        hb=gtk.HBox()
        conditionsbox.add(hb)

        try:
            w=EditCondition(cond, editable=self.editable)
        except Exception, e:
            print str(e)
            print "for a query"
            w = gtk.Label("Error in query")
            
        self.editconditionlist.append(w)
        
        hb.add(w.get_widget())
        w.get_widget().show()

        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.set_sensitive(self.editable)
        b.connect("clicked", self.remove_condition, w, hb)
        b.show()
        hb.pack_start(b, expand=False)

        hb.show()
        
        return True

    def build_widget(self):
        frame=gtk.Frame()
        
        vbox=gtk.VBox()
        frame.add(vbox)
        vbox.show()
        
        # Event
        ef=gtk.Frame(_("For all elements in "))
        self.sourceentry=gtk.Entry()
        self.sourceentry.set_text(self.model.source)
        self.sourceentry.set_editable(self.editable)
        ef.add(self.sourceentry)
        ef.show_all()
        vbox.pack_start(ef, expand=gtk.FALSE)

        # Return value
        vf=gtk.Frame(_("Return "))
        # FIXME: Add tooltip to indicate the 'element' root
        self.valueentry=gtk.Entry()
        v=self.model.rvalue
        if v is None:
            v='element'
        self.valueentry.set_text(v)
        self.valueentry.set_editable(self.editable)
        vf.add(self.valueentry)
        vf.show_all()
        vbox.pack_start(vf, expand=gtk.FALSE)
        
        # Conditions
        cf=gtk.Frame(_("If the element matches "))
        conditionsbox=gtk.VBox()
        cf.add(conditionsbox)

        # "Add condition" button
        hb=gtk.HBox()
        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", self.add_condition, conditionsbox)
        b.set_sensitive(self.editable)
        hb.pack_start(b, expand=gtk.FALSE)
        hb.set_homogeneous(gtk.FALSE)
        conditionsbox.pack_start(hb, expand=gtk.FALSE, fill=gtk.FALSE)
        
        cf.show_all()
        
        if isinstance(self.model.condition, advene.rules.elements.ConditionList):
            for c in self.model.condition:
                self.add_condition_widget(c, conditionsbox)
                
        vbox.pack_start(cf, expand=gtk.FALSE)

        frame.show()

        return frame

    
class EditRule(EditGeneric):
    def __init__(self, rule, catalog=None, editable=True):
        # Original rule
        self.model=rule
        
        self.catalog=catalog
        self.editable=editable
        
        self.namelabel=None
        
        self.editactionlist=[]
        self.editconditionlist=[]
        self.widget=self.build_widget()

    def set_update_label(self, l):
        """Specify a label to be updated when the rule name changes"""
        self.namelabel=l
        
    def update_value(self):
        if not self.editable:
            return True
        
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

        # Rebuild actionlist from editactionlist
        self.model.action=ActionList([ e.model for e in self.editactionlist ])

        return

    def update_name(self, entry):
        if self.namelabel:
            self.namelabel.set_label(entry.get_text())
        self.framelabel.set_markup("Rule <b>%s</b>" % entry.get_text())
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
        hb=gtk.HBox()
        conditionsbox.add(hb)

        try:
            w=EditCondition(cond, editable=self.editable)
        except Exception, e:
            print str(e)
            print "for rule %s" % self.model.name
            w = gtk.Label("Error in rule %s" % self.model.name)
            
        self.editconditionlist.append(w)
        
        hb.add(w.get_widget())
        w.get_widget().show()
        
        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.set_sensitive(self.editable)
        b.connect("clicked", self.remove_condition, w, hb)
        b.show()
        hb.pack_start(b, expand=False)

        hb.show()
        
        return True

    def add_action(self, widget, actionsbox):
        """Callback for the Add action button."""
        ra=self.catalog.get_action("Message")
        action=Action(registeredaction=ra, catalog=self.catalog)
        self.add_action_widget(action, actionsbox)

    def add_action_widget(self, action, actionsbox):
        """Add an action widget to the given actionsbox."""
        
        hb=gtk.HBox()
        actionsbox.add(hb)

        w=EditAction(action, self.catalog, editable=self.editable)
        self.editactionlist.append(w)
        hb.add(w.get_widget())
        w.get_widget().show()
        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.connect("clicked", self.remove_action, w, hb)
        b.set_sensitive(self.editable)
        b.show()
        hb.pack_start(b, expand=False)

        hb.show()
        return True

    def build_widget(self):
        frame=gtk.Frame()
        self.framelabel=gtk.Label()
        self.framelabel.set_markup("Rule <b>%s</b>" % self.model.name)
        self.framelabel.show()
        frame.set_label_widget(self.framelabel)
        
        vbox=gtk.VBox()
        frame.add(vbox)
        vbox.show()
        
        # Rule name
        hbox=gtk.HBox()
        hbox.add(gtk.Label(_("Rule name")))
        self.name_entry=gtk.Entry()
        self.name_entry.set_text(self.model.name)
        self.name_entry.set_editable(self.editable)
        self.name_entry.connect("changed", self.update_name)
        hbox.add(self.name_entry)
        hbox.show_all()
        vbox.pack_start(hbox, expand=gtk.FALSE)

        # Event
        ef=gtk.Frame(_("Event"))
        self.editevent=EditEvent(self.model.event, self.catalog,
                                 editable=self.editable)
        ef.add(self.editevent.get_widget())
        ef.show_all()
        vbox.pack_start(ef, expand=gtk.FALSE)

        # Conditions
        cf=gtk.Frame(_("If"))
        conditionsbox=gtk.VBox()
        cf.add(conditionsbox)

        # "Add condition" button
        hb=gtk.HBox()
        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", self.add_condition, conditionsbox)
        b.set_sensitive(self.editable)
        hb.pack_start(b, expand=gtk.FALSE)
        hb.set_homogeneous(gtk.FALSE)
        conditionsbox.pack_start(hb, expand=gtk.FALSE, fill=gtk.FALSE)

        cf.show_all()
        
        if isinstance(self.model.condition, advene.rules.elements.ConditionList):
            for c in self.model.condition:
                self.add_condition_widget(c, conditionsbox)
        #FIXME: else?
        
        vbox.pack_start(cf, expand=False)

        # Actions
        af=gtk.Frame(_("Then"))
        actionsbox=gtk.VBox()
        af.add(actionsbox)
        hb=gtk.HBox()
        # Add Action button
        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", self.add_action, actionsbox)
        b.set_sensitive(self.editable)
        hb.pack_start(b, expand=gtk.FALSE)
        hb.set_homogeneous(gtk.FALSE)
        actionsbox.pack_start(hb, expand=gtk.FALSE, fill=gtk.FALSE)

        for a in self.model.action:
            self.add_action_widget(a, actionsbox)
            
        vbox.pack_start(af, expand=gtk.FALSE)
        af.show_all()
        
        frame.show()

        return frame

class EditEvent(EditGeneric):
    def __init__(self, event, catalog, expert=False, editable=True):
        self.model=event
        self.current_event=event
        self.catalog=catalog
        self.expert=expert
        self.editable=editable
        self.widget=self.build_widget()
        
    def update_value(self):
        # Nothing to update. The parent has the responsibility to
        # fetch the current_event value.
        pass

    def on_change_event(self, widget, eventlist):
        if self.editable:
            self.current_event=eventlist[widget.get_history()]
        return True

    def build_widget(self):
        hbox=gtk.HBox()
        hbox.set_homogeneous(gtk.FALSE)

        label=gtk.Label(_("When the "))
        hbox.pack_start(label)

        eventlist=self.catalog.get_described_events(expert=self.expert)
        if self.current_event not in eventlist:
            # The event was not in the list. It must be because
            # it is an expert-mode event. Add it manually.
            eventlist[self.current_event]=self.catalog.describe_event(self.current_event)

        eventname=self.build_option(eventlist, self.current_event, self.on_change_event,
                                    editable=self.editable)
        hbox.add(eventname)

        label=gtk.Label(_(" occurs,"))
        hbox.add(label)

        hbox.show_all()
        return hbox

class EditCondition(EditGeneric):
    def __init__(self, condition, editable=True):
        self.model=condition

        self.current_operator=self.model.operator
        self.editable=editable
        
        # Widgets:
        self.lhs=None # Entry
        self.rhs=None # Entry
        self.operator=None # Combo list

        self.widget=self.build_widget()

    def update_value(self):
        if self.editable:
            c=self.model
            c.operator=self.current_operator
            c.lhs=self.lhs.entry.get_text()
            if c.operator in Condition.binary_operators:
                c.rhs=self.rhs.entry.get_text()
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

    def on_change_operator(self, widget, operators):
        self.current_operator=operators[widget.get_history()]
        self.update_widget()
        return True

    def build_widget(self):
        hbox=gtk.HBox()

        self.lhs=gtk.Combo()
        self.lhs.entry.set_text(self.model.lhs or "")
        self.lhs.set_sensitive(self.editable)
        self.lhs.show()

        self.rhs=gtk.Combo()
        self.rhs.entry.set_text(self.model.rhs or "")
        self.rhs.set_sensitive(self.editable)
        self.rhs.hide()

        self.operator = gtk.OptionMenu()
        self.operator.set_sensitive(self.editable)
        self.operator.show()

        operators={}
        operators.update(Condition.binary_operators)
        operators.update(Condition.unary_operators)
        
        self.operator=self.build_option(operators,
                                        self.current_operator,
                                        self.on_change_operator,
                                        editable=self.editable)

        hbox.add(self.lhs)
        hbox.add(self.operator)
        hbox.add(self.rhs)
        hbox.show()
        
        self.update_widget()
        
        return hbox

class EditAction(EditGeneric):
    def __init__(self, action, catalog, editable=True):
        self.model=action

        self.editable=editable
        self.current_name=action.name
        self.current_parameters=dict(action.parameters)
        
        # Dict of parameter widgets (modified when the action name changes)
        # indexed by parameter name
        self.paramlist={}
        
        self.catalog=catalog
        self.tooltips=gtk.Tooltips()
        self.widget=self.build_widget()

    def update_value(self):
        if not self.editable:
            return
        ra=self.catalog.get_action(self.current_name)
        self.model = Action(registeredaction=ra, catalog=self.catalog)
        regexp=sre.compile('^(\(.+\)|)$')
        for n, v in self.current_parameters.iteritems():
            # We ignore parameters fields that are empty or that match '^\(.+\)$'
            if not regexp.match(v):
                #print "Updating %s = %s" % (n, v)
                self.model.add_parameter(n, v)
        return

    def sorted(self, l):
        """Return a sorted version of the list."""
        if isinstance(l, dict):
            res=l.keys()
        else:
            res=l[:]
        res.sort()
        return res
        
    def on_change_name(self, widget, names):
        if names[widget.get_history()] == self.current_name:
            return True
        self.current_name=names[widget.get_history()]
        for w in self.paramlist.values():
            w.destroy()
        self.paramlist={}
        
        ra=self.catalog.get_action(self.current_name)
        self.current_parameters=dict(ra.parameters)
        for name in self.sorted(ra.parameters):
            p=self.build_parameter_widget(name,
                                          "",
                                          ra.describe_parameter(name))
            self.paramlist[name]=p
            p.show_all()
            self.widget.add(p)
            
        return True
        
    def on_change_parameter(self, entry, name):
        value=entry.get_text()
        self.current_parameters[name]=value
        return True

    def build_parameter_widget(self, name, value, description):
        hbox=gtk.HBox()
        label=gtk.Label(name)
        hbox.pack_start(label, expand=False)
        
        entry=gtk.Entry()
        entry.set_text(value)
        entry.set_editable(self.editable)
        entry.connect("changed", self.on_change_parameter, name)

        self.tooltips.set_tip(entry, description)        
        hbox.pack_start(entry)
        return hbox
        
    def build_widget(self):
        vbox=gtk.VBox()

        vbox.add(gtk.HSeparator())
        actions=self.catalog.get_described_actions()
        self.name=self.build_option(actions, self.current_name, self.on_change_name,
                                    editable=self.editable)
        vbox.add(self.name)

        if self.model.registeredaction:
            # Action is derived from a RegisteredAction
            # we have information about its parameters
            ra=self.model.registeredaction
            for name in self.sorted(ra.parameters):
                p=self.build_parameter_widget(name,
                                              self.model.parameters.setdefault(name,""),
                                              ra.describe_parameter(name))
                self.paramlist[name]=p
                vbox.add(p)
        else:
            # We display existing parameters
            for name in self.sorted(self.model.parameters):
                p=self.build_parameter_widget(name, self.model.parameters[name], "")
                self.paramlist[name]=p
                vbox.add(p)

        vbox.add(gtk.HSeparator())
                
        vbox.show_all()
        return vbox

if __name__ == "__main__":
    default='default_rules.xml'
    
    import sys
    
    if len(sys.argv) < 2:
        print "No name provided. Using %s." % default
        filename=default
    else:
        filename=sys.argv[1]

    class Controller:
        """Dummy controller."""
        def __init__(self):
            self.annotation=None
            self.package=None
            self.active_annotations=[]
            self.player=None
            self.imagecache={}

    controller=Controller()
    
    import advene.rules.actions
    catalog=advene.rules.elements.ECACatalog()
    
    for a in advene.rules.actions.DefaultActionsRepository(controller=controller).get_default_actions():
            catalog.register_action(a)
            
    ruleset=RuleSet()
    if filename.endswith('.xml'):
        ruleset.from_xml(catalog=catalog, uri=filename)
    else:
        ruleset.from_file(catalog=catalog, filename=filename)

    w=gtk.Window(gtk.WINDOW_TOPLEVEL)
    w.set_title("RuleSet %s" % filename)
    w.connect ("destroy", lambda e: gtk.main_quit())

    vbox=gtk.VBox()
    vbox.set_homogeneous (gtk.FALSE)    
    w.add(vbox)

    edit=EditRuleSet(ruleset, catalog)
    edit.get_widget().show()
    vbox.add(edit.get_widget())

    hb=gtk.HButtonBox()
    
    b=gtk.Button(stock=gtk.STOCK_ADD)
    b.connect("clicked", edit.add_rule)
    hb.pack_start(b, expand=False)

    b=gtk.Button(stock=gtk.STOCK_REMOVE)
    b.connect("clicked", edit.remove_rule)
    hb.pack_start(b, expand=False)

    def save_ruleset(button):
        f='test.xml'
        edit.update_value()
        print "Saving model with %d rules" % len(edit.model)
        edit.model.to_xml(f)
        dialog = gtk.MessageDialog(
            None, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_INFO, gtk.BUTTONS_OK,
            "The ruleset has been saved into %s." % f)
        dialog.run()
        dialog.destroy()
        return True
    
    b=gtk.Button(stock=gtk.STOCK_SAVE)
    b.connect("clicked", save_ruleset)
    hb.pack_start(b, expand=False)

    b=gtk.Button(stock=gtk.STOCK_QUIT)
    b.connect("clicked", lambda e: gtk.main_quit())
    hb.pack_end(b, expand=False)

    hb.show_all()

    vbox.pack_start(hb, expand=gtk.FALSE)
    vbox.show()
    
    w.show()
    
    gtk.mainloop()
