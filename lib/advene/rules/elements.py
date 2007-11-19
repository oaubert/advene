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
"""Event framework for Advene.

The event framework makes it possible to bind actions to specific
events that match a condition."""

import re
import sets
import StringIO

import xml.dom.ext.reader.PyExpat

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
        'equals': (_("is equal to"), 'basic'),
        'different': (_("is different from"), 'basic' ),
        'contains': (_("contains"), 'basic' ),
        'greater': (_("is greater than"), 'basic' ),
        'lower': (_("is lower than"), 'basic' ),
        'matches': (_("matches the regexp"), 'basic' ),
        'before': (_("is before"), 'allen' ),
        'meets': (_("meets"), 'allen' ),
        'overlaps': (_("overlaps"), 'allen' ),
        'during': (_("during"), 'allen' ),
        'starts': (_("starts"), 'allen' ),
        'finishes': (_("finishes"), 'allen' ),
        # 'equals': "equals (Allen)" missing (cf before)
        }
    # Unary operators apply on the LHS
    unary_operators={
        'not': (_('is not true'), 'basic' ),
        'value': (_('is true'), 'basic' ),
        }

    condition_categories={
        'basic': _("Basic conditions"),
        'allen': _("Allen relations"),
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
                return left != right
            elif self.operator == 'contains':
                return right in left
            elif self.operator == 'greater':
                # If it is possible to convert the values to
                # floats, then do it. Else, compare string values
                lv=self.convert_value(left, 'end')
                rv=self.convert_value(right, 'begin')
                return lv >= rv
            elif self.operator == 'lower' or self.operator == 'before':
                # If it is possible to convert the values to
                # floats, then do it. Else, compare string values
                lv=self.convert_value(left, 'end')
                rv=self.convert_value(right, 'begin')
                return lv <= rv
            elif self.operator == 'matches':
                return re.search(rv, lv)
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
            raise Exception("Invalid condition (no left value) in rule.")
        self.lhs=node.getAttribute('lhs')
        if node.hasAttribute('rhs'):
            self.rhs=node.getAttribute('rhs')
        else:
            self.rhs=None
        return self

    def to_dom(self, dom):
        """Create a DOM representation of the condition.

        @return: a DOMElement
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

    ``def method (context, parameters)``

    where:
      - context is a advene.tal.AdveneContext holding various information
      - parameters is a dictionary with named parameters, whose values are
        coded in TALES syntax (and should be evaluated through context).

    @ivar name: the action name
    @ivar parameters: the action's parameters
    @type parameters: dict
    @ivar catalog: the associated catalog
    @ivar category: the category that this action belongs to
    @type category: string
    @type catalog: ECACatalog
    @ivar doc: the action documentation
    @ivar registeredaction: the corresponding registeredaction
    @ivar immediate: indicates that the action should be executed at once and not scheduled
    @type immediate: boolean
    """
    def __init__ (self, registeredaction=None, method=None,
                  catalog=None, doc="", category="generic"):
        self.parameters={}
        if registeredaction is not None:
            self.name=registeredaction.name
            self.catalog=catalog
            if self.catalog is None:
                raise Exception("A RegisteredAction should always be initialized with a catalog.")
            self.doc=registeredaction.description
            self.registeredaction=registeredaction
            self.immediate=registeredaction.immediate
            self.category=registeredaction.category
        elif method is not None:
            self.bind(method)
            self.name="internal"
            self.doc=doc
            self.registeredaction=None
            self.catalog=catalog
            self.category=category
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

    def to_dom(self, dom):
        """Create a DOM representation of the action.

        @return: a DOMElement
        """
        node=dom.createElement('action')
        node.setAttribute('name', self.name)
        for pname, pvalue in self.parameters.iteritems():
            paramnode=dom.createElement('param')
            node.appendChild(paramnode)
            paramnode.setAttribute('name', pname)
            paramnode.setAttribute('value', pvalue)
        return node

class Rule:
    """Advene Rule, consisting in an Event, a Condition and an Action.

    The priority parameter is used to determine the order of execution
    of rules. The convention is::

      0 - 100   : user rules
      100 - 200 : default rules
      200+      : internal rules

    This will ensure that internal rules are always executed first.

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
    @ivar priority: the rule priority
    @type priority: int
    """

    default_condition=Condition()
    default_condition.match=default_condition.truematch

    def __init__ (self, name="N/C", event=None,
                  condition=None, action=None, origin=None, priority=0):
        self.name=name
        self.event=event
        self.priority=priority
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

    def from_xml_string(self, xmlstring, catalog=None):
        """Read the rule from a XML string
        """
        reader=xml.dom.ext.reader.PyExpat.Reader()
        s=StringIO.StringIO(xmlstring)
        di=reader.fromStream(s)
        rulenode=di._get_documentElement()
        self.from_dom(domelement=rulenode, catalog=catalog)
        s.close()

    def from_dom(self, domelement=None, catalog=None, origin=None):
        """Read the rule from a DOM element.

        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        @param domelement: the DOM element
        @param origin: the source URI
        @type origin: URI
        """
        self.origin=origin
        if catalog is None:
            catalog=ECACatalog()
        rulenode=domelement
        # FIXME: check the the rulenode tagname is 'rule'
        self.name=rulenode.getAttribute('name')
        # Event
        eventnodes=rulenode.getElementsByTagName('event')
        if len(eventnodes) == 1:
            name=eventnodes[0].getAttribute('name')
            if catalog.is_event(name):
                self.event=Event(name)
            else:
                raise Exception("Undefined Event name: %s" % name)
        elif len(eventnodes) == 0:
            raise Exception("No event associated to rule %s" % self.name)
        else:
            raise Exception("Multiple events are associated to rule %s" % self.name)

        # Conditions
        for condnode in rulenode.getElementsByTagName('condition'):
            self.add_condition(Condition().from_dom(condnode))

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
            self.add_action(action)
        return self

    def to_xml(self, uri=None, stream=None):
        """Save the ruleset to the given URI or stream."""
        dom=xml.dom.Document.Document(None)
        dom.appendChild(self.to_dom(dom))
        if stream is None:
            stream=open(uri, 'w')
            xml.dom.ext.PrettyPrint(dom, stream)
            stream.close()
        else:
            xml.dom.ext.PrettyPrint(dom, stream)

    def xml_repr(self):
        """Return the XML representation of the rule."""
        s=StringIO.StringIO()
        self.to_xml(stream=s)
        buf=s.getvalue()
        s.close()
        return buf

    def to_dom(self, dom):
        """Create a DOM representation of the rule.

        @return: a DOMElement
        """
        rulenode=dom.createElement('rule')
        rulenode.setAttribute('name', self.name)

        eventnode=dom.createElement('event')
        rulenode.appendChild(eventnode)
        eventnode.setAttribute('name', self.event[:])

        if self.condition != self.default_condition:
            for cond in self.condition:
                if cond == self.default_condition:
                    continue
                rulenode.appendChild(cond.to_dom(dom))

        if isinstance(self.action, ActionList):
            l=self.action
        else:
            l=[self.action]
        for action in l:
            rulenode.appendChild(action.to_dom(dom))
        return rulenode

class SubviewList(list):
    """List of subview.

    It contains a list of *view ids* that are considered as subviews for a
    ruleset: their rule will be considered as part of the view.
    
    We could store views themselves, but then we would depend on a
    controller when loading the XML representation.
    """
    def __init__ (self, name="N/C", elements=None, origin=None):
        self.name=name
        self.origin=origin
        if elements is None:
            elements=[]
        self[:]=elements[:]

    def clear(self):
        self[:]=[]

    def as_views(self, package):
        """Return the Subview list as a list of views, interpreted in the context of package
        """
        return [ package.get_element_by_id(i) for i in self ]

    def from_xml_string(self, xmlstring, catalog=None):
        """Read the list from a XML string
        """
        reader=xml.dom.ext.reader.PyExpat.Reader()
        s=StringIO.StringIO(xmlstring)
        di=reader.fromStream(s)
        rulenode=di._get_documentElement()
        self.from_dom(domelement=rulenode, catalog=catalog)
        s.close()

    def from_dom(self, domelement=None, origin=None, catalog=None):
        """Read the list from a DOM element.

        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        @param domelement: the DOM element
        @param origin: the source URI
        @type origin: URI
        """
        self.origin=origin
        rulenode=domelement
        
        # FIXME: check the the rulenode tagname is 'subviewlist'
        self.name=rulenode.getAttribute('name')
        v=rulenode.getAttribute('value')
        if v:
            self[:]=v.split(',')
        else:
            self[:]=[]
        # Event
        return self

    def to_xml(self, uri=None, stream=None):
        """Save the ruleset to the given URI or stream."""
        dom=xml.dom.Document.Document(None)
        dom.appendChild(self.to_dom(dom))
        if stream is None:
            stream=open(uri, 'w')
            xml.dom.ext.PrettyPrint(dom, stream)
            stream.close()
        else:
            xml.dom.ext.PrettyPrint(dom, stream)

    def xml_repr(self):
        """Return the XML representation of the rule."""
        s=StringIO.StringIO()
        self.to_xml(stream=s)
        buf=s.getvalue()
        s.close()
        return buf

    def to_dom(self, dom):
        """Create a DOM representation of the subviewlist.

        @return: a DOMElement
        """
        rulenode=dom.createElement("subviewlist")
        rulenode.setAttribute('name', self.name)
        rulenode.setAttribute('value', ','.join( self ) )
        return rulenode

class RuleSet(list):
    """Set of Rules.

    It is a list of Rule and SubviewList instances. Usually, there is
    only a single SubviewList.
    """
    def __init__(self, uri=None, catalog=None, priority=0):
        self.priority=priority
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
        self.from_dom(domelement=rulesetnode, catalog=catalog, origin=uri)

    def from_dom(self, domelement=None, catalog=None, origin=None):
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
            rule=Rule(origin=origin, priority=self.priority)
            rule.from_dom(rulenode, catalog, origin=origin)
            self.append(rule)
        for rulenode in ruleset.getElementsByTagName('subviewlist'):
            rule=SubviewList()
            rule.from_dom(rulenode, origin=origin)
            self.append(rule)
        return self

    def to_xml(self, uri=None, stream=None):
        """Save the ruleset to the given URI or stream."""
        dom=xml.dom.Document.Document(None)
        dom.appendChild(self.to_dom(dom))
        if stream is None:
            stream=open(uri, 'w')
            xml.dom.ext.PrettyPrint(dom, stream)
            stream.close()
        else:
            xml.dom.ext.PrettyPrint(dom, stream)

    def xml_repr(self):
        """Return the XML representation of the ruleset."""
        s=StringIO.StringIO()
        self.to_xml(stream=s)
        buf=s.getvalue()
        s.close()
        return buf

    def to_dom(self, dom):
        """Create a DOM representation of the ruleset.

        @return: a DOMElement
        """
        rulesetnode=dom.createElement('ruleset')
        for rule in self:
            rulesetnode.appendChild(rule.to_dom(dom))
        return rulesetnode

    def filter_subviews(self):
        """Remove subview instances from the RuleSet.
        
        @return: list of removed SubviewList instances.
        """
        subviews=[ r for r in self if isinstance(r, SubviewList) ]
        for s in subviews:
            self.remove(s)
        return subviews

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
        dom=xml.dom.Document.Document(None)
        dom.appendChild(self.to_dom(dom))
        if stream is None:
            stream=open(uri, 'w')
            xml.dom.ext.PrettyPrint(dom, stream)
            stream.close()
        else:
            xml.dom.ext.PrettyPrint(dom, stream)

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
        """Create a DOM representation of the query.

        @return: a DOMElement
        """
        qnode=dom.createElement('query')

        sourcenode=dom.createElement('source')
        sourcenode.setAttribute('value', self.source)
        qnode.appendChild(sourcenode)

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
            rnode.setAttribute('value', self.rvalue)
            qnode.appendChild(rnode)

        return qnode

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
                #context.addLocals( [ ('element', None) ] )
                context.pushLocals()
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
            #context.addLocals( [ ('element', None) ] )
            context.pushLocals()
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

    Some predefined values must be generated on-the-fly, depending on
    the package's elements. If predefined is a method, it must be
    called with (controller) as parameters, and will return the dict with values == list
    of couples (expression, description).

    @ivar name: the action name
    @type name: string
    @ivar category: the category this action belongs to
    @type category: string
    @ivar method: the action method (ignored)
    @ivar description: the action description
    @ivar parameters: the action parameters
    @type parameters: dict
    @ivar predefined: predefined parameter values
    @type: a dict whith list of couples as values or a method m(controller, item)
    @ivar immediate: if True, the action is immediately executed, else scheduled
    @type immediate: boolean
    """
    def __init__(self,
                 name=None,
                 method=None,
                 description="No available description",
                 parameters=None,
                 category="generic",
                 immediate=False,
                 predefined=None,
                 defaults=None):
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
        if defaults is None:
            defaults={}
        # Set default values for non-specified default
        for k, v in parameters.iteritems():
            defaults.setdefault(k, "string:%s" % v)
        self.defaults=defaults
        # If immediate, the action will be run in the main thread, and not
        # in the scheduler thread.
        self.immediate=immediate
        # The available categories are described in Catalog
        self.category=category
        self.predefined=predefined

    def add_parameter(self, name, description):
        """Add a new parameter to the action."""
        self.parameters[name]=description

    def describe_parameter(self, name):
        """Describe the parameter."""
        return self.parameters[name]

    def default_value(self, name):
        """Get the parameter default value."""
        return self.defaults[name]

    def as_html(self, action_url):
        r="""<form method="GET" action="%s">""" % action_url
        l=self.parameters.keys()
        l.sort()
        for k in l:
            r += """%s: <input name="%s" title="%s" value="%s"/>""" % (k,
                                                                       k,
                                                                       self.parameters[k],
                                                                       self.defaults[k])
        r += """<input type="submit" name="Execute" /></form>"""
        return r

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
        'QueryCreate':            _("Creation of a new query"),
        'QueryEditEnd':           _("Ending editing of a query"),
        'QueryDelete':            _("Suppression of a query"),
        'SchemaCreate':           _("Creation of a new schema"),
        'SchemaEditEnd':          _("Ending editing of a schema"),
        'SchemaDelete':           _("Suppression of a schema"),
        'AnnotationTypeCreate':   _("Creation of a new annotation type"),
        'AnnotationTypeEditEnd':  _("Ending editing an annotation type"),
        'AnnotationTypeDelete':   _("Suppression of an annotation type"),
        'RelationTypeCreate':     _("Creation of a new relation type"),
        'RelationTypeEditEnd':    _("Ending editing a relation type"),
        'RelationTypeDelete':     _("Suppression of a relation type"),
        'ResourceCreate':         _("Creation of a new resource"),
        'ResourceEditEnd':        _("Ending editing of a resource"),
        'ResourceDelete':         _("Suppression of a resource"),
        'TagUpdate':              _("Modification of the tag"),
        'LinkActivation':         _("Activating a link"),
        'PlayerStart':            _("Player start"),
        'PlayerStop':             _("Player stop"),
        'PlayerPause':            _("Player pause"),
        'PlayerResume':           _("Player resume"),
        'PlayerSet':              _("Going to a given position"),
        'PackageLoad':            _("Loading a new package"),
        'PackageActivate':        _("Activating a package"),
        'PackageSave':            _("Saving the package"),
        'ViewActivation':         _("Start of the dynamic view"),
        'ViewDeactivation':       _("End of the dynamic view"),
        'ApplicationStart':       _("Start of the application"),
        'ApplicationEnd':         _("End of the application"),
        'UserEvent':              _("User-defined event"),
        'MediaChange':            _("Modification of the associated media"),
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
        'ResourceCreate',
        'ResourceEditEnd',
        'ResourceDelete',
        ))

    # Basic events are exposed to the user when defining new STBV
    basic_events=('AnnotationBegin', 'AnnotationEnd', 'PlayerStart', 'PlayerPause',
                  'PlayerResume', 'PlayerStop', 'ApplicationStart', 'ViewActivation',
                  'UserEvent')

    action_categories={
        'generic': _("Generic actions"),
        'player': _("Basic player control"),
        'advanced': _("Advanced player control"),
        'gui': _("GUI actions")
        }

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
            return dict([ (k, self.describe_event(k)) for k in self.basic_events ])

    def get_described_actions(self, expert=False):
        """Return a dict holding all the actions with their description.

        @param expert: expert mode
        @type expert: boolean
        @return: a dictionary of descriptions indexed by name.
        @rtype: dict
        """
        d=dict( [ (a, self.describe_action(a)) for a in self.actions ] )
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

    controller=None
    catalog=ECACatalog()
    r=RuleSet()
    r.from_xml(catalog=catalog, uri=filename)
    print "Read %d rules." % len(r)
