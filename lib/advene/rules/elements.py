#! /usr/bin/env python

"""Event framework for Advene.

The event framework makes it possible to bind actions to specific
events that match a condition."""

import sre
import sys
import sets
import StringIO

import urllib

import xml.dom.ext.reader.PyExpat

import advene.core.config

from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment

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
    """A list of conditions.

    It inherits from list, and adds a L{match} method.

    @ivar composition: the composition mode (and/or)
    @type composition: string
    """
    def __init__(self, val=None):
        self.composition="and"
        if val is not None:
            list.__init__(self, val)
        else:
            list.__init__(self)

    def is_true(self):
        """The ConditionList is never True by default."""
        return False

    def match(self, context):
        """Test is the context matches the ConditionList.
        """
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

    @ivar lhs: Left-Hand side expression
    @type lhs: TALES expression
    @ivar rhs: Right-Hand side expression
    @type rhs: TALES expression
    @ivar operator: condition operator
    @type operator: string
    """

    binary_operators={
        'equals': _("is equal to"),
        'different': _("is different from"),
        'contains': _("contains"),
        'greater': _("is greater than"),
        'lower': _("is lower than"),
        'matches': _("matches the regexp"),
        'before': _("is before (Allen)"),
        'meets': _("meets (Allen)"),
        'overlaps': _("overlaps (Allen)"),
        'during': _("during (Allen)"),
        'starts': _("starts (Allen)"),
        'finishes': _("finishes (Allen)")
        # 'equals': missing (cf before)
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
        """Test if the Condition is true by default.
        """
        return self.match == self.truematch

    def convert_value(self, element, mode='begin'):
        """Converts a value (Annotation, Fragment or number) into a number.
        Mode is used for Annotation and Fragment and tells wether to consider
        begin or end."""
        if isinstance(element, Annotation):
            rv=getattr(element.fragment, mode)
        elif isinstance(element, MillisecondFragment):
            rv=getattr(element, mode)
        else:
            try:
                rv=float(element)
            except ValueError:
                rv=element
        return rv
        
    def match(self, context):
        """Test if the condition matches the context."""
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
                # If it is possible to convert the values to
                # floats, then do it. Else, compare string values
                lv=self.convert_value(left, 'end')
                rv=self.convert_value(right, 'begin')
                return lv > rv
            elif self.operator == 'lower' or self.operator == 'before':
                # If it is possible to convert the values to
                # floats, then do it. Else, compare string values
                lv=self.convert_value(left, 'end')
                rv=self.convert_value(right, 'begin')
                return lv < rv
            elif self.operator == 'matches':
                return sre.search(rv, lv)
            elif self.operator == 'meets':
                lv=self.convert_value(left, 'end')
                rv=self.convert_value(right, 'begin')
                return lv == rv
            elif self.operator == 'overlaps':
                if isinstance(left, Annotation):
                    lv=left.fragment
                elif isinstance(left, MillisecondFragment):
                    lv=left
                else:
                    raise Exception(_("Unknown type for overlaps comparison"))
                if isinstance(right, Annotation):
                    rv=right.fragment
                elif isinstance(right, MillisecondFragment):
                    rv=right
                else:
                    raise Exception(_("Unknown type for overlaps comparison"))
                return (lv.begin in rv or rv.begin in lv)
            elif self.operator == 'during':
                if isinstance(left, Annotation):
                    lv=left.fragment
                elif isinstance(left, MillisecondFragment):
                    lv=left
                else:
                    raise Exception(_("Unknown type for during comparison"))
                if isinstance(right, Annotation):
                    rv=right.fragment
                elif isinstance(right, MillisecondFragment):
                    rv=right
                else:
                    raise Exception(_("Unknown type for during comparison"))
                return lv in rv
            elif self.operator == 'starts':
                lv=self.convert_value(left, 'begin')
                rv=self.convert_value(right, 'begin')
                return lv == rv
            elif self.operator == 'finishes':
                lv=self.convert_value(left, 'end')
                rv=self.convert_value(right, 'end')
                return lv == rv
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

    def from_dom(self, node):
        if node._get_nodeName() != 'condition':
            raise Exception("Bad invocation of Condition.from_dom")
        if node.hasAttribute('operator'):
            self.operator=node.getAttribute('operator')
        else:
            self.operator='value'
        if not node.hasAttribute('lhs'):
            raise Exception("Invalid condition (no value) in rule %s." % rule)
        self.lhs=node.getAttribute('lhs')
        if node.hasAttribute('rhs'):
            self.rhs=node.getAttribute('rhs')
        else:
            self.rhs=None
        return self

    def to_dom(self, dom):
        """Creates a DOM representation of the condition.
        """
        condnode=dom.createElement('condition')
        condnode.setAttribute('operator', self.operator)
        condnode.setAttribute('lhs', self.lhs)
        if self.operator in self.binary_operators:
            condnode.setAttribute('rhs', self.rhs)
        return condnode

class ActionList(list):
    """List of actions.

    It just forwards the L{execute} call to all its elements.
    """

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

    @ivar name: the action name
    @ivar parameters: the action's parameters
    @type parameters: dict
    @ivar catalog: the associated catalog
    @type catalog: ECACatalog
    @ivar doc: the action documentation
    @ivar registeredaction: the corresponding registeredaction
    @ivar immediate: indicates that the action should be executed at once and not scheduled
    @type immediate: boolean
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
        """Bind a given method to the action.

        @param method: the method
        """
        self.method=method

    def add_parameter(self, name, value):
        """Declare a new parameter for the action.

        @param name: the parameter name
        @type name: string
        @param value: the parameter value
        @type value: a TALES expression
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
    """Advene Rule, consisting in an Event, a Condition and an Action.

    @ivar name: the rulename
    @type name: string
    @ivar event: the event name
    @type event: string
    @ivar condition: the condition
    @type condition: Condition or ConditionList
    @ivar action: the action
    @type action: ActionList
    @ivar origin: the rule origin
    @type origin: URL
    """

    default_condition=Condition()
    default_condition.match=default_condition.truematch

    def __init__ (self, name="N/C", event=None, condition=None, action=None, origin=None):
        self.name=name
        self.event=event
        self.condition=condition
        if self.condition is None:
            self.condition=self.default_condition
        if isinstance(action, ActionList):
            self.action=action
        else:
            self.action=ActionList()
            if action is not None:
                self.add_action(action)
        self.origin=origin

    def __str__(self):
        return "Rule '%s'" % self.name

    def add_action(self, action):
        """Add a new action to the rule.
        """
        self.action.append(action)

    def add_condition(self, condition):
        """Add a new condition

        @param condition: the new condition
        @type condition: Condition
        """
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
        """Add a new rule."""
        self.append(rule)

    def from_xml(self, catalog=None, uri=None):
        """Read the ruleset from a URI.

        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        @param uri: the source URI
        """
        reader=xml.dom.ext.reader.PyExpat.Reader()
        di=reader.fromStream(open(uri, 'r'))
        rulesetnode=di._get_documentElement()
        self.from_dom(catalog=catalog, domelement=rulesetnode, origin=uri)

    def from_dom(self, catalog=None, domelement=None, origin=None):
        """Read the ruleset from a DOM element.

        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        @param domelement: the DOM element
        @param origin: the source URI
        @type origin: URI
        """
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
                rule.add_condition(Condition().from_dom(condnode))

            # Actions
            for actionnode in rulenode.getElementsByTagName('action'):
                name=actionnode.getAttribute('name')
                if catalog.is_action(name):
                    action=Action(registeredaction=catalog.get_action(name), catalog=catalog)
                else:
                    # FIXME: we should just display warnings if the action
                    # is not defined ? Or maybe accept it in the case it is defined
                    # in a module loaded later at runtime
                    raise Exception("Undefined action in %s: %s" % (origin, name))
                for paramnode in actionnode.getElementsByTagName('param'):
                    p_name=paramnode.getAttribute('name')
                    p_value=paramnode.getAttribute('value')
                    action.add_parameter(p_name, p_value)
                rule.add_action(action)
            self.append(rule)
        return self

    def to_xml(self, uri=None, stream=None):
        """Save the ruleset to the given URI or stream."""
        di = xml.dom.DOMImplementation.DOMImplementation()
        rulesetdom = di.createDocument(advene.core.config.data.namespace, "ruleset", None)
        self.to_dom(rulesetdom)
        if stream is None:
            stream=open(uri, 'w')
            xml.dom.ext.PrettyPrint(rulesetdom, stream)
            stream.close()
        else:
            xml.dom.ext.PrettyPrint(rulesetdom, stream)

    def xml_repr(self):
        """Return the XML representation of the ruleset."""
        s=StringIO.StringIO()
        self.to_xml(stream=s)
        buf=s.getvalue()
        s.close()
        return buf

    def to_dom(self, dom):
        """Save the ruleset in the given DOM element."""
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
                    rulenode.appendChild(cond.to_dom(dom))
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
        """Deprecated.

        Save the ruleset to a simple text file.
        """
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
        """Deprecated. Read from a flat text file.

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

class Query:
    """Simple Query component.

    This query component returns a set of data matching a condition
    from a given source. If the source is not a list, it will return a
    boolean.

    The 'condition' and 'return value' TALES expression will be
    evaluated in a context where the loop value is stored in the
    'element' global. In other words, use 'element' as the root of
    condition and return value expressions.

    @ivar source: the source of the data
    @type source: a TALES expression
    @ivar condition: the matching condition
    @type condition: a Condition
    @ivar rvalue: the return value (specified as a TALES expression)
    @type rvalue: a TALES expression
    @ivar controller: the controller
    """
    def __init__(self, source=None, condition=None, controller=None, rvalue=None):
        self.source=source
        self.condition=condition
        self.controller=controller
        self.rvalue=rvalue

    def add_condition(self, condition):
        """Add a new condition

        @param condition: the new condition
        @type condition: Condition
        """
        if self.condition is None:
            self.condition=ConditionList()
        self.condition.append(condition)

    def from_xml(self, uri=None):
        """Read the query from a URI.

        @param uri: the source URI
        """
        reader=xml.dom.ext.reader.PyExpat.Reader()
        di=reader.fromStream(open(uri, 'r'))
        querynode=di._get_documentElement()
        self.from_dom(domelement=querynode)

    def to_xml(self, uri=None, stream=None):
        """Save the query to the given URI or stream."""
        di = xml.dom.DOMImplementation.DOMImplementation()
        # FIXME: hardcoded NS URI
        querydom = di.createDocument("http://liris.cnrs.fr/advene/ruleset", "query", None)
        self.to_dom(querydom)
        if stream is None:
            stream=open(uri, 'w')
            xml.dom.ext.PrettyPrint(querydom, stream)
            stream.close()
        else:
            xml.dom.ext.PrettyPrint(querydom, stream)

    def xml_repr(self):
        """Return the XML representation of the ruleset."""
        s=StringIO.StringIO()
        self.to_xml(stream=s)
        buf=s.getvalue()
        s.close()
        return buf

    def from_dom(self, domelement=None):
        """Read the Query from a DOM element.

        @param domelement: the DOM element
        """
        if domelement._get_nodeName() != 'query':
            raise Exception("Invalid DOM element for Query")

        sourcenodes=domelement.getElementsByTagName('source')
        if len(sourcenodes) == 1:
            self.source=sourcenodes[0].getAttribute('value')
        elif len(sourcenodes) == 0:
            raise Exception("No source associated to query")
        else:
            raise Exception("Multiple sources are associated to query")

        # Conditions
        for condnode in domelement.getElementsByTagName('condition'):
            self.add_condition(Condition().from_dom(condnode))

        rnodes=domelement.getElementsByTagName('return')
        if len(rnodes) == 1:
            self.rvalue=rnodes[0].getAttribute('value')
        elif len(rnodes) == 0:
            self.rvalue=None
        else:
            raise Exception("Multiple return values are associated to query")

        return self

    def to_dom(self, dom):
        """Save the query in the given DOM element."""
        qnode=dom._get_documentElement()
        sourcenode=dom.createElement('source')
        qnode.appendChild(sourcenode)
        sourcenode.setAttribute('value', self.source)

        if self.condition is not None:
            if isinstance(self.condition, Condition):
                l=[self.condition]
            else:
                l=self.condition
            for cond in l:
                if cond is None:
                    continue
                qnode.appendChild(cond.to_dom(dom))

        if self.rvalue is not None:
            rnode=dom.createElement('return')
            qnode.appendChild(rnode)
            rnode.setAttribute('value', self.rvalue)

    def execute(self, context):
        """Execute the query.

        @return: the list of elements matching the query or a boolean
        """
        s=context.evaluateValue(self.source)

        if self.condition is None:
            if self.rvalue is None or self.rvalue == 'element':
                return s
            else:
                r=[]
                context.addLocals( [ ('element', None) ] )
                for e in s:
                    context.setLocal('element', e)
                    r.append(context.evaluateValue(self.rvalue))
                context.popLocals()
                return r

        if hasattr(s, '__getitem__'):
            # It is either a real list or a Bundle
            # (for isinstance(someBundle, list) == False !
            # FIXME: should we use a Bundle ?
            r=[]
            context.addLocals( [ ('element', None) ] )
            for e in s:
                context.setLocal('element', e)
                if self.condition.match(context):
                    if self.rvalue is None or self.rvalue == 'element':
                        r.append(e)
                    else:
                        r.append(context.evaluateValue(self.rvalue))
            context.popLocals()
            return r
        else:
            # Not a list. What do we do in this case ?
            return s

class RegisteredAction:
    """Registered action.

    @ivar name: the action name
    @type name: string
    @ivar method: the action method (ignored)
    @ivar description: the action description
    @ivar parameters: the action parameters
    @type parameters: dict
    @param immediate: if True, the action is immediately executed, else scheduled
    @type immediate: boolean
    """
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
        """Add a new parameter to the action."""
        self.parameters[name]=description

    def describe_parameter(self, name):
        """Describe the parameter."""
        return self.parameters[name]

class ECACatalog:
    """Class holding information about available elements (events, conditions, actions).

    @ivar actions: the list of registered actions indexed by name
    @type actions: dict
    """

    # FIXME: Maybe this should be put in an external resource file
    event_names={
        'PackageEditEnd':         _("Ending editing of a package"),
        'AnnotationBegin':        _("Beginning of an annotation"),
        'AnnotationEnd':          _("End of an annotation"),
        'AnnotationCreate':       _("Creation of a new annotation"),
        'AnnotationEditEnd':      _("Ending editing of an annotation"),
        'AnnotationDelete':       _("Suppression of an annotation"),
        'AnnotationActivate':     _("Activation of an annotation"),
        'AnnotationDeactivate':   _("Deactivation of an annotation"),
        'RelationActivate':       _("Activation of a relation"),
        'RelationDeactivate':     _("Deactivation of a relation"),
        'RelationCreate':         _("Creation of a new relation"),
        'RelationEditEnd':        _("Ending editing of a relation"),
        'RelationDelete':         _("Suppression of a relation"),
        'ViewCreate':             _("Creation of a new view"),
        'ViewEditEnd':            _("Ending editing of a view"),
        'ViewDelete':             _("Suppression of a view"),
        'QueryCreate':             _("Creation of a new query"),
        'QueryEditEnd':            _("Ending editing of a query"),
        'QueryDelete':             _("Suppression of a query"),
        'SchemaCreate':           _("Creation of a new schema"),
        'SchemaEditEnd':          _("Ending editing of a schema"),
        'SchemaDelete':           _("Suppression of a schema"),
        'AnnotationTypeCreate':   _("Creation of a new annotation type"),
        'AnnotationTypeEditEnd':  _("Ending editing an annotation type"),
        'AnnotationTypeDelete':   _("Suppression of an annotation type"),
        'RelationTypeCreate':     _("Creation of a new relation type"),
        'RelationTypeEditEnd':    _("Ending editing a relation type"),
        'RelationTypeDelete':     _("Suppression of a relation type"),
        'LinkActivation':         _("Activating a link"),
        'PlayerStart':            _("Player start"),
        'PlayerStop':             _("Player stop"),
        'PlayerPause':            _("Player pause"),
        'PlayerResume':           _("Player resume"),
        'PlayerSet':              _("Going to a given position"),
        'PackageLoad':            _("Loading a new package"),
        'PackageSave':            _("Saving the package"),
        'ViewActivation':         _("Start of the dynamic view"),
        'ApplicationStart':       _("Start of the application"),
        'ApplicationEnd':         _("End of the application"),
        'UserEvent':              _("User-defined event"),
        }

    # Events that set the controller.modified state
    modifying_events=sets.Set((
        'PackageEditEnd',
        'AnnotationCreate',
        'AnnotationEditEnd',
        'AnnotationDelete',
        'RelationCreate',
        'RelationEditEnd',
        'RelationDelete',
        'ViewCreate',
        'ViewEditEnd',
        'ViewDelete',
        'SchemaCreate',
        'SchemaEditEnd',
        'SchemaDelete',
        'AnnotationTypeCreate',
        'AnnotationTypeEditEnd',
        'AnnotationTypeDelete',
        'RelationTypeCreate',
        'RelationTypeEditEnd',
        'RelationTypeDelete',
        'QueryCreate',
        'QueryEditEnd',
        'QueryDelete',
        ))

    # Basic events are exposed to the user when defining new STBV
    basic_events=('AnnotationBegin', 'AnnotationEnd', 'PlayerStart', 'PlayerPause',
                  'PlayerResume', 'PlayerStop', 'ApplicationStart', 'ViewActivation',
                  'UserEvent')

    def __init__(self):
        # Dict of registered actions, indexed by name
        self.actions={}

    def is_event(self, name):
        """Check if name is a valid event name.

        @param name: the checked name
        @type name: string
        @return: True if name is a valid event name
        @rtype: boolean
        """
        return name in ECACatalog.event_names

    def is_action(self, name):
        """Check if name is a valid registered action name.

        @param name: the checked name
        @type name: string
        @return: True if name is a valid action name
        @rtype: boolean
        """
        return self.actions.has_key(name)

    def get_action(self, name):
        """Return the action matching name.

        @param name: the checked name
        @type name: string
        @return: the matching registered action
        @rtype: RegisteredAction
        """
        return self.actions[name]

    def register_action(self, registered_action):
        """Register a RegisteredAction instance.
        """
        self.actions[registered_action.name]=registered_action

    def describe_action(self, name):
        """Return the description of the action.
        """
        return self.actions[name].description

    def describe_event(self, name):
        """Return the description of the event.
        """
        return self.event_names[name]

    def get_events(self, expert=False):
        """Return the list of defined event names.

        @param expert: expert mode
        @type expert: boolean
        @return: the list of defined event names
        @rtype: list
        """
        if expert:
            return self.event_names.keys()
        else:
            return self.basic_events

    def get_described_events(self, expert=False):
        """Return a dict holding all the events with their description.

        @param expert: expert mode
        @type expert: boolean
        @return: a dictionary of descriptions indexed by name.
        @rtype: dict
        """
        if expert:
            return dict(self.event_names)
        else:
            d={}
            for k in self.basic_events:
                d[k]=self.describe_event(k)
            return d

    def get_described_actions(self, expert=False):
        """Return a dict holding all the actions with their description.

        @param expert: expert mode
        @type expert: boolean
        @return: a dictionary of descriptions indexed by name.
        @rtype: dict
        """
        d={}
        for a in self.actions:
            d[a]=self.describe_action(a)
        return d

    def get_actions(self, expert=False):
        """Return the list of defined actions.
        """
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
