#! /usr/bin/env python

"""Event framework for Advene.

The event framework makes it possible to bind actions to specific
events that match a condition."""

import sre
import sys

import urllib

import xml.dom.ext.reader.PyExpat

from gettext import gettext as _

class Event(str):
    """The Event class represents the various defined events in Advene.
    """
    pass
# Warning: if we change the str representation, it messes the indexing
# in catalog.get_described_events for instance.
#    def __str__(self):
#        return "Event %s" % self[:]

class ConditionList(list):
    """A list of conditions"""
    def __init__(self, val=None):
        self.composition="and"
        if val is not None:
            list.__init__(self, val)
        else:
            list.__init__(self)

    def is_true(self):
        return False
    
    def match(self, context):
        if self.composition == "and":
            for condition in self:
                if not condition.match(context):
                    return False
            return True
        else:
            for condition in self:
                if condition.match(context):
                    return True
            return False
    
class Condition:
    """The Condition class.
    """
    binary_operators={
        'equals': _("is equal to"),
        'different': _("is different from"),
        'contains': _("contains"),
        'greater': _("is greater than"),
        'lower': _("is lower than")
        }
    # Unary operators apply on the LHS
    unary_operators={
        'not': _('is not true'),
        'value': _('is true')
        }
    
    def __init__(self, lhs=None, rhs=None, operator=None):
        self.lhs=lhs
        self.rhs=rhs
        self.operator=operator

    def is_true(self):
        return self.match == self.truematch
    
    def match(self, context):
        """Return True if the condition matches the context."""
        if self.operator in self.binary_operators:
            # Binary operator
            left=context.evaluateValue(self.lhs)
            right=context.evaluateValue(self.rhs)
            if self.operator == 'equals':
                return left == right
            if self.operator == 'different':
                return left == right
            elif self.operator == 'contains':
                return right in left
            elif self.operator == 'greater':
                return right >= left
            elif self.operator == 'lower':
                return right <= left
            else:
                raise Exception("Unknown operator: %s" % self.operator)
        elif self.operator in self.unary_operators:
            # Unary operator
            # Note: self.lhs should be None
            left=context.evaluateValue(self.lhs)
            if self.operator == 'not':
                return not left
            elif self.operator == 'value':
                return left
            else:
                raise Exception("Unknown operator: %s" % self.operator)
        else:
            raise Exception("Unknown operator: %s" % self.operator)

    def truematch(self, context):
        """Condition which always return True.

        It can be used to replace the match method.
        """
        return True

class ActionList(list):
    def execute(self, context):
        for action in self:
            action.execute(context)        
            
class Action:
    """The Action class.

    The associated method should have the following signature:
    def method (context, parameters)
    where:
        context is a advene.tal.AdveneContext holding various information
        parameters is a dictionary with named parameters, whose values are
                   coded in TALES syntax (and should be evaluated through context).
    """
    def __init__ (self, registeredaction=None, method=None, catalog=None, doc=""):
        self.parameters={}
        if registeredaction is not None:
            self.name=registeredaction.name
            self.catalog=catalog
            if self.catalog is None:
                raise Exception("A RegisteredAction should always be initialized with a catalog.")
            self.doc=registeredaction.description
            self.registeredaction=registeredaction
            self.immediate=registeredaction.immediate
        elif method is not None:
            self.bind(method)
            self.name="internal"
            self.doc=doc
            self.registeredaction=None
            self.catalog=None
            self.immediate=False
        else:
            raise Exception("Error in Action constructor.")
        
    def __str__(self):
        return "Action %s" % self.name
    
    def bind(self, method):
        self.method=method

    def add_parameter(self, name, value):
        """Declare a new parameter for the action.

        Value is a TALES expression.
        """
        self.parameters[name]=value
        
    def execute(self, context):
        """Execute the action in the given TALES context.

        Parameters are in TALES syntax, and the method should evaluate
        them as needed.
        """
        if self.registeredaction:
            return self.catalog.get_action(self.name).method(context, self.parameters)
        else:
            return self.method(context, self.parameters)

class Rule:
    """Advene Rule, consisting in an Event, a Condition and an Action"""
    
    default_condition=Condition()
    default_condition.match=default_condition.truematch
    
    def __init__ (self, name="N/C", event=None, condition=None, action=None, origin=None):
        self.name=name
        self.event=event
        self.condition=condition
        if self.condition is None:
            self.condition=self.default_condition
        self.action=ActionList()
        if action is not None:
            self.add_action(action)
            
    def __str__(self):
        return "Rule '%s'" % self.name

    def add_action(self, action):
        self.action.append(action)

    def add_condition(self, condition):
        if self.condition == self.default_condition:
            self.condition=ConditionList()
        self.condition.append(condition)
        
class RuleSet(list):
    """Set of Rules.

    """
    def __init__(self, uri=None, catalog=None):
        if uri is not None and catalog is not None:
            self.from_xml(catalog=catalog, uri=uri)

    def add_rule(self, rule):
        self.append(rule)
        
    def from_xml(self, catalog=None, uri=None):
        reader=xml.dom.ext.reader.PyExpat.Reader()
        di=reader.fromStream(open(uri, 'r'))
        rulesetnode=di._get_documentElement()
        self.from_dom(catalog=catalog, domelement=rulesetnode, origin=uri)
        
    def from_dom(self, catalog=None, domelement=None, origin=None):
        if catalog is None:
            catalog=ECACatalog()
        ruleset=domelement
        for rulenode in ruleset.getElementsByTagName('rule'):
            rulename=rulenode.getAttribute('name')
            rule=Rule(name=rulename, origin=origin)

            # Event
            eventnodes=rulenode.getElementsByTagName('event')
            if len(eventnodes) == 1:
                name=eventnodes[0].getAttribute('name')
                if catalog.is_event(name):
                    rule.event=Event(name)
                else:
                    raise Exception("Undefined Event name: %s" % name)
            elif len(eventnodes) == 0:
                raise Exception("No event associated to rule %s" % rulename)
            else:
                raise Exception("Multiple events are associated to rule %s" % rulename)
            
            # Conditions
            for condnode in rulenode.getElementsByTagName('condition'):
                if condnode.hasAttribute('operator'):
                    operator=condnode.getAttribute('operator')
                else:
                    operator='value'
                if not condnode.hasAttribute('lhs'):
                    raise Exception("Invalid condition (no value) in rule %s." % rule)
                lhs=condnode.getAttribute('lhs')
                if condnode.hasAttribute('rhs'):
                    rhs=condnode.getAttribute('rhs')
                else:
                    rhs=None
                rule.add_condition(Condition(lhs=lhs,
                                             rhs=rhs,
                                             operator=operator))

            # Actions
            for actionnode in rulenode.getElementsByTagName('action'):
                name=actionnode.getAttribute('name')
                if catalog.is_action(name):
                    action=Action(registeredaction=catalog.get_action(name), catalog=catalog)
                else:
                    # FIXME: we should just display warnings if the action
                    # is not defined ?
                    raise Exception("Undefined action in %s: %s" % (origin, name))
                for paramnode in actionnode.getElementsByTagName('param'):
                    p_name=paramnode.getAttribute('name')
                    p_value=paramnode.getAttribute('value')
                    action.add_parameter(p_name, p_value)
                rule.add_action(action)
            self.append(rule)

    def to_xml(self, uri=None):
        di = xml.dom.DOMImplementation.DOMImplementation()
        # FIXME: hardcoded NS URI
        rulesetdom = di.createDocument("http://liris.cnrs.fr/advene/ruleset", "ruleset", None)
        self.to_dom(rulesetdom)
        stream=open(uri, 'w')
        xml.dom.ext.PrettyPrint(rulesetdom, stream)
        stream.close()
        
    def to_dom(self, dom):
        #rulesetnode=domtree.createElement('ruleset')
        rulesetnode=dom._get_documentElement()
        for rule in self:
            rulenode=dom.createElement('rule')
            rulesetnode.appendChild(rulenode)
            rulenode.setAttribute('name', rule.name)
            eventnode=dom.createElement('event')
            rulenode.appendChild(eventnode)
            eventnode.setAttribute('name', rule.event[:])
            if rule.condition != rule.default_condition:
                for cond in rule.condition:
                    if cond == rule.default_condition:
                        continue
                    condnode=dom.createElement('condition')
                    rulenode.appendChild(condnode)
                    condnode.setAttribute('operator', cond.operator)
                    condnode.setAttribute('lhs', cond.lhs)
                    if cond.operator in cond.binary_operators:
                        condnode.setAttribute('rhs', cond.rhs)
            if isinstance(rule.action, ActionList):
                l=rule.action
            else:
                l=[rule.action]
            for action in l:
                actionnode=dom.createElement('action')
                rulenode.appendChild(actionnode)
                actionnode.setAttribute('name', action.name)
                for pname, pvalue in action.parameters.iteritems():
                    paramnode=dom.createElement('param')
                    actionnode.appendChild(paramnode)
                    paramnode.setAttribute('name', pname)
                    paramnode.setAttribute('value', pvalue)

    def to_file(self, catalog=None, filename=None):
        if catalog is None:
            catalog=event.ECACatalog()
        if filename == '-':
            fd=sys.stderr
        else:
            fd=open(filename, 'w')
        for rule in self:
            fd.write("Rule %s:\n" % rule.name)
            fd.write("\tEvent %s\n" % rule.event[:])
            if rule.condition != rule.default_condition:
                for cond in rule.condition:
                    if cond == rule.default_condition:
                        continue
                    if cond.operator in cond.binary_operators:
                        fd.write("\tIf %s %s %s\n" % (cond.lhs, cond.operator, cond.rhs))
                    else:
                        fd.write("\tIf %s %s\n" % (cond.lhs, cond.operator))
            fd.write("\tThen\n")
            if isinstance(rule.action, ActionList):
                l=rule.action
            else:
                l=[rule.action]
            for action in l:
                fd.write("\t%s (%s)\n" % (action.name, str(action.parameters)))
        if filename != '-':
            fd.close()
        return
        
    def from_file(self, catalog=None, filename=None):
        """Read from a flat text file.

        Proof of concept. We should move to an XML structured file.
        
        Syntax of the file:
        
        Rule rulename
          event: AnnotationBegin
          condition: annotation/type equals package/annotationTypes/teacher:narrative
          action: DisplayMessage message=string: Narrator: ${annotation/content/data}
        EndRule

        The available operators are Condition.binary_operators and Condition.unary_operators
        If the action has several parameters, they should be separated by ;
        
        """
        if catalog is None:
            catalog=event.ECACatalog()
        f = open(filename, 'r')
        rule_regexp=sre.compile('^rule\s+(.+)$', sre.I)
        endrule_regexp=sre.compile('^endrule', sre.I)
        content_regexp=sre.compile('\s*(event|condition|action):\s+(.+)', sre.I)
        comment_regexp=sre.compile('^\s*(#.+)?$')
        rule=None
        conditionlist=None
        for l in f:
            if comment_regexp.match(l):
                continue
            if endrule_regexp.match(l):
                if rule is None:
                    raise Exception(_("Malformed ruleset file: end without a start."))
                if conditionlist:
                    rule.condition=conditionlist
                self.append(rule)
                rule=None
                continue
            match=rule_regexp.match(l)
            if match is not None:
                name=match.group(1)
                rule=Rule(name=name)
                conditionlist=ConditionList()
                continue
            match=content_regexp.match(l)
            if match is not None:
                attr, value=match.group(1, 2)
                attr=attr.lower()
                if rule is None:
                    raise Exception(_("Syntax error in file %s:\n%s") % (filename, l))
                if attr == 'event':
                    if catalog.is_event(value):
                        rule.event=Event(value)
                    else:
                        raise Exception(_("Undefined Event name: %s") % value)
                    continue
                elif attr == 'condition':
                    cond=sre.split("\s+", value)
                    if len(cond) == 3:
                        lhs=urllib.unquote(cond[0])
                        operator=urllib.unquote(cond[1])
                        rhs=urllib.unquote(cond[2])
                        conditionlist.append(Condition(lhs=lhs,
                                                       rhs=rhs,
                                                       operator=operator))
                    elif len(cond) == 2:
                        operator=cond[0]
                        lhs=urllib.unquote(cond[1])
                        conditionlist.append(Condition(lhs=lhs,
                                                       rhs=None,
                                                       operator=operator))
                    elif len(cond) == 1:
                        lhs=urllib.unquote(cond[0])
                        conditionlist.append(Condition(lhs=lhs,
                                                       rhs=None,
                                                       operator='value'))
                    else:
                        raise Exception("Syntax error in file %s:\n%s" % (filename, l))
                    continue
                elif attr == 'action':
                    if sre.match('^(\w+)$', value):
                        # Parameterless action
                        if catalog.is_action(value):
                            action=Action(registeredaction=catalog.get_action(value),
                                          catalog=catalog)
                        else:
                            raise Exception("Undefined action in %s: %s" % (filename, value))
                    else:
                        match=sre.match('^(\w+)\s+(.+)', value)
                        name=match.group(1)
                        if catalog.is_action(name):
                            action=Action(registeredaction=catalog.get_action(name),
                                          catalog=catalog)
                        else:
                            raise Exception("Undefined action in %s: %s" % (filename, name))
                        parameters=match.group(2)
                        for pair in sre.split('\s*&\s*', parameters):
                            (p_name, p_value)=pair.split('=')
                            action.add_parameter(urllib.unquote(p_name),
                                                 urllib.unquote(p_value))
                    rule.add_action(action)
                    continue
                else:
                    raise Exception("Syntax error in file %s:\n%s" % (filename, l))
            raise Exception("Syntax error in file %s:\n%s" % (filename, l))
        f.close()

class RegisteredAction:
    def __init__(self,
                 name=None,
                 method=None,
                 description="No available description",
                 parameters=None,
                 immediate=False):
        self.name=name
        # The method attribute is in fact ignored, since we always lookup in the
        # ECACatalog for each invocation
        self.method=method
        self.description=description
        # Dict indexed by parameter name.
        # The value holds a description of the parameter.
        if parameters is None:
            parameters={}
        self.parameters=parameters
        # If immediate, the action will be run in the main thread, and not
        # in the scheduler thread.
        self.immediate=immediate

    def add_parameter(self, name, description):
        self.parameters[name]=description

    def describe_parameter(self, name):
        return self.parameters[name]
    
class ECACatalog:
    """Class holding information about available elements (events, conditions, actions).
    """
    # FIXME: Maybe this should be put in an external resource file
    event_names={
        'AnnotationBegin': _("Beginning of an annotation"),
        'AnnotationEnd': _("End of an annotation"),
        'AnnotationEditBegin': _("Starting editing of an annotation"),
        'AnnotationEditEnd': _("Ending editing of an annotation"),
        'AnnotationActivation': _("Activation of an annotation"),
        'AnnotationDeactivation': _("Deactivation of an annotation"),
        'RelationActivation': _("Activation of a relation"),
        'RelationDeactivation': _("Deactivation of a relation"),
        'RelationEditBegin': _("Starting editing of a relation"),
        'RelationEditEnd': _("Ending editing of a relation"),
        'LinkActivation': _("Activating a link"),
        'PlayerStart': _("Player start"),
        'PlayerStop': _("Player stop"),
        'PlayerPause': _("Player pause"),
        'PlayerResume': _("Player resume"),
        'PlayerSet': _("Going to a given position"),
        'PackageLoad': _("Loading a new package"),
        'PackageSave': _("Saving the package"),
        'ViewActivation': _("Start of a dynamic view"),
        'ApplicationStart': _("Start of the application"),
        'ApplicationEnd': _("End of the application")
        }

    basic_events=('AnnotationBegin', 'AnnotationEnd', 'PlayerStart', 'PlayerPause',
                  'PlayerResume', 'PlayerStop', 'ApplicationStart', 'ViewActivation')
    
    def __init__(self):
        # Dict of registered actions, indexed by name
        self.actions={}

    def is_event(self, name):
        return name in ECACatalog.event_names

    def is_action(self, name):
        return self.actions.has_key(name)
    
    def get_action(self, name):
        return self.actions[name]
    
    def register_action(self, registered_action):
        """Register a RegisteredAction instance."""
        self.actions[registered_action.name]=registered_action

    def describe_action(self, name):
        return self.actions[name].description

    def describe_event(self, name):
        return self.event_names[name]

    def get_events(self, expert=False):
        if expert:
            return self.event_names.keys()
        else:
            return self.basic_events

    def get_described_events(self, expert=False):
        """Return a dict holding all the events with their description."""
        if expert:
            return dict(self.event_names)
        else:
            d={}
            for k in self.basic_events:
                d[k]=self.describe_event(k)
            return d

    def get_described_actions(self, expert=False):
        """Return a dict holding all the actions with their description."""
        d={}
        for a in self.actions:
            d[a]=self.describe_action(a)
        return d
    
    def get_actions(self, expert=False):
        if expert:
            return self.actions.keys()
        else:
            return self.actions.keys()

if __name__ == "__main__":
    default='default_rules.txt'
    import sys
    if len(sys.argv) < 2:
        print "No name provided. Using %s." % default
        filename=default
    else:
        filename=sys.argv[1]

    import actions
    controller=None
    catalog=ECACatalog()
    for a in actions.DefaultActionsRepository(controller=controller).get_default_actions():
            catalog.register_action(a)
    r=RuleSet()
    if filename.endswith('.xml'):
        r.from_xml(catalog=catalog, uri=filename)
    else:
        r.from_file(catalog=catalog, filename=filename)
    print "Read %d rules." % len(r)
