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
"""Event framework for Advene.

The event framework makes it possible to bind actions to specific
events that match a condition."""

import re
import sets
import StringIO
import urllib

import xml.etree.ElementTree as ET

import advene.core.config as config
from advene.model.cam.annotation import Annotation

from gettext import gettext as _

OLD_NS_PREFIX='http://experience.univ-lyon1.fr/advene/ns/advenetool'

class Event(str):
    """The Event class represents the various defined events in Advene.
    """
# Warning: if we change the str representation, it messes the indexing
# in catalog.get_described_events for instance.
#    def __str__(self):
#        return "Event %s" % self[:]
    pass
    
def tag(name, old=False):
    if old:
        return name
    else:
        return str(ET.QName(config.data.namespace, name))

class EtreeMixin:
    """This class defines helper methods for conversion to/from ElementTree.
    
    The mixed-in class should implement to_etree() and from_etree(element, **kw) methods.

    Optional arguments to from_etree can be 'catalog' and 'origin'.
    """
    def to_xml(self, uri=None, stream=None):
        """Save the instance to the given URI or stream."""
        root=self.to_etree()
        etree=ET.ElementTree(root)
        if stream is None:
            etree.write(uri, encoding='utf-8')
        else:
            etree.write(stream, encoding='utf-8')

    def xml_repr(self):
        """Return the XML representation of the instance."""
        s=StringIO.StringIO()
        self.to_xml(stream=s)
        buf=s.getvalue()
        s.close()
        return buf

    def from_xml_string(self, xmlstring, catalog=None):
        """Read the rule from a XML string.
        """
        s=StringIO.StringIO(xmlstring)
        rulenode=ET.parse(s).getroot()
        self.from_etree(rulenode, catalog=catalog, origin='XML string')
        s.close()

    def from_xml(self, uri=None, catalog=None, origin=None):
        """Read the ruleset from a URI.

        @param uri: the source URI
        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        """
        rulesetnode=ET.parse(uri).getroot()
        if origin is None and isinstance(uri, basestring):
            origin=uri
        self.from_etree(rulesetnode, catalog=catalog, origin=origin)

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
            left=context.evaluate(self.lhs)
            right=context.evaluate(self.rhs)
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
            # Note: self.rhs is ignored, whatever its value is.
            left=context.evaluate(self.lhs)
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

    def from_etree(self, node, **kw):
        if node.tag != tag('condition') and node.tag != 'condition':
            raise Exception("Bad invocation of Condition.from_etree")
        self.operator=node.attrib.get('operator', 'value')
        if not 'lhs' in node.attrib:
            raise Exception("Invalid condition (no left value) in condition %s." % self.operator)
        self.lhs=node.attrib['lhs']
        self.rhs=node.attrib.get('rhs', None)
        return self

    def to_etree(self):
        """Create an ElementTree representation of the condition.

        @return: an ET.Element
        """
        condnode=ET.Element(tag('condition'), {
                'operator': self.operator,
                'lhs': self.lhs })
        if self.operator in self.binary_operators:
            condnode.attrib['rhs']=self.rhs
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

    def to_etree(self):
        """Create an ElementTree representation of the action.

        @return: an ElementTree.Element
        """
        node=ET.Element(tag('action'), { 'name': self.name })
        for pname, pvalue in self.parameters.iteritems():
            paramnode=ET.Element(tag('param'), {
                    'name': pname,
                    'value': pvalue })
            node.append(paramnode)
        return node

class Rule(EtreeMixin):
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
    default_condition.composition='and'

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

    def from_etree(self, rulenode, catalog=None, origin=None):
        """Read the rule from an ElementTree.Element.

        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        @param domelement: the DOM element
        @param origin: the source URI
        @type origin: URI
        """
        self.origin=origin
        if catalog is None:
            catalog=ECACatalog()
        assert rulenode.tag == tag('rule') or rulenode.tag == 'rule', "Invalid XML element %s parsed as rule" % rulenode.tag
        self.name=rulenode.attrib['name']
        # Old XML versions (no namespace)
        compatibility=(rulenode.tag == 'rule')
        # Event
        eventnodes=rulenode.findall(tag('event', old=compatibility))
        if len(eventnodes) == 1:
            name=eventnodes[0].attrib['name']
            if catalog.is_event(name):
                self.event=Event(name)
            else:
                raise Exception("Undefined Event name: %s" % name)
        elif len(eventnodes) == 0:
            raise Exception("No event associated to rule %s" % self.name)
        else:
            raise Exception("Multiple events are associated to rule %s" % self.name)

        # Conditions
        for condnode in rulenode.findall(tag('condition', old=compatibility)):
            self.add_condition(Condition().from_etree(condnode, catalog=catalog, origin=origin))

        # Set the composition mode for the condition
        for n in rulenode.findall(tag('composition', old=compatibility)):
            self.condition.composition=n.attrib['value']

        # Actions
        for actionnode in rulenode.findall(tag('action', old=compatibility)):
            name=actionnode.attrib['name']
            param={}
            for paramnode in actionnode.findall(tag('param', old=compatibility)):
                param[paramnode.attrib['name']]=paramnode.attrib['value']
        
            if not catalog.is_action(name):
                # Dynamically register a dummy action with the same
                # name and parameters, so that it can be edited and saved.
                def unknown_action(context, parameters):
                    a=catalog.get_action('Message')
                    a.method(None, { 'message': _("Unknown action %s") % name })
                    return True

                catalog.register_action(RegisteredAction(
                        name=name,
                        method=unknown_action,
                        description=_("Unknown action %s") % name,
                        parameters=dict( (name, _("Unknown parameter %s") % name)
                                         for (name, value) in param.iteritems() ),
                        defaults=dict(param),
                        category='unknown',
                        ))
                catalog.action_categories['unknown']=_("Unknown actions")

            action=Action(registeredaction=catalog.get_action(name), catalog=catalog)
            for name, value in param.iteritems():
                action.add_parameter(name, value)
            self.add_action(action)
        return self

    def to_etree(self):
        """Create a ElementTree representation of the rule.

        @return: an ElementTree.Element
        """
        rulenode=ET.Element(tag('rule'), { 'name': self.name })

        rulenode.append(ET.Element(tag('event'), 
                                   {'name': str(self.event) }))

        if self.condition != self.default_condition:

            if isinstance(self.condition, ConditionList):
                for cond in self.condition:
                    if cond == self.default_condition:
                        continue
                    rulenode.append(cond.to_etree())
                    rulenode.append(ET.Element(tag('composition'), 
                                               { 'value': self.condition.composition } ))
            else:
                rulenode.append(self.condition.to_etree())
                rulenode.append(ET.Element(tag('composition'), 
                                           { 'value': 'and' } ))

        if isinstance(self.action, ActionList):
            l=self.action
        else:
            l=[self.action]
        for action in l:
            rulenode.append(action.to_etree())
        return rulenode

class SubviewList(list, EtreeMixin):
    """List of subview.

    It contains a list of *view ids* that are considered as subviews for a
    ruleset: their rules will be considered as part of the view.

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

    def from_etree(self, element, catalog=None, origin=None):
        """Read the list from a DOM element.

        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        @param element: the ElementTree element
        @param origin: the source URI
        @type origin: URI
        """
        self.origin=origin

        # FIXME: check the the element tagname is 'subviewlist'
        assert element.tag == tag('subviewlist'), "Trying to parse %s as a subviewlist" % element.tag

        self.name=element.attrib['name']
        v=element.attrib['value']
        if v:
            self[:]=v.split(',')
        else:
            self[:]=[]
        # Event
        return self

    def to_etree(self):
        """Create an ElementTree representation of the subviewlist.

        @return: an ElementTree.Element
        """
        el=ET.Element("subviewlist", 
                      { 'name': self.name,
                        'value': ','.join( self ) } )
        return el

class RuleSet(list, EtreeMixin):
    """Set of Rules.

    It is a list of Rule and SubviewList instances. Usually, there is
    only a single SubviewList.
    """
    def __init__(self, uri=None, catalog=None, priority=0):
        self.priority=priority
        if uri is not None and catalog is not None:
            self.from_xml(uri=uri, catalog=catalog)

    def add_rule(self, rule):
        """Add a new rule."""
        self.append(rule)

    def from_etree(self, rulesetnode, catalog=None, origin=None):
        """Read the ruleset from a DOM element.

        @param catalog: the ECAEngine catalog
        @type catalog: ECACatalog
        @param rulesetnode: the ElementTree.Element
        @param origin: the source URI
        @type origin: URI
        """
        assert rulesetnode.tag == tag('ruleset') or rulesetnode.tag == 'ruleset', "Trying to parse %s as a RuleSet" % rulesetnode.tag
        compatibility=(rulesetnode.tag == 'ruleset')
        if catalog is None:
            catalog=ECACatalog()
        for rulenode in rulesetnode.findall(tag('rule', old=compatibility)):
            rule=Rule(origin=origin, priority=self.priority)
            rule.from_etree(rulenode, catalog=catalog, origin=origin)
            self.append(rule)
        for rulenode in rulesetnode.findall(tag('subviewlist', old=compatibility)):
            rule=SubviewList()
            rule.from_etree(rulenode, catalog=catalog, origin=origin)
            self.append(rule)
        return self

    def to_etree(self):
        """Create an ElementTree representation of the ruleset.

        @return: an ElemenTree.Element
        """
        rulesetnode=ET.Element(tag('ruleset'))
        for rule in self:
            rulesetnode.append(rule.to_etree())
        return rulesetnode

    def filter_subviews(self):
        """Remove subview instances from the RuleSet.

        @return: list of removed SubviewList instances.
        """
        subviews=[ r for r in self if isinstance(r, SubviewList) ]
        for s in subviews:
            self.remove(s)
        return subviews

class SimpleQuery(EtreeMixin):
    """SimpleQuery component.

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

    def from_etree(self, querynode, **kw):
        """Read the SimpleQuery from an ElementTree.Element.

        @param querynode: the ElementTree.Element
        """
        assert querynode.tag == tag('query') or querynode.tag == 'query', "Invalid tag %s for SimpleQuery" % querynode.tag

        compatibility=(querynode.tag == 'query')
        sourcenodes=querynode.findall(tag('source', old=compatibility))
        assert len(sourcenodes) != 0, "No source associated to query"
        assert len(sourcenodes) == 1, "Multiple sources are associated to query"
        self.source=sourcenodes[0].attrib['value']

        # Conditions
        for condnode in querynode.findall(tag('condition', old=compatibility)):
            self.add_condition(Condition().from_etree(condnode))

        # Set the composition mode for the condition
        for n in querynode.findall(tag('composition', old=compatibility)):
            self.condition.composition=n.attrib['value']

        rnodes=querynode.findall(tag('return', old=compatibility))
        if len(rnodes) == 1:
            self.rvalue=rnodes[0].attrib['value']
        elif len(rnodes) == 0:
            self.rvalue=None
        else:
            raise Exception("Multiple return values are associated to query")

        return self

    def to_etree(self):
        """Create an ElementTree representation of the query.

        @return: an ElementTree.Element
        """
        qnode=ET.Element(tag('query'))

        qnode.append(ET.Element(tag('source'), 
                                    { 'value': self.source }))

        if self.condition is not None:
            if isinstance(self.condition, Condition):
                l=[self.condition]
            else:
                l=self.condition
            for cond in l:
                if cond is None:
                    continue
                qnode.append(cond.to_etree())

            qnode.append(ET.Element(tag('composition'),
                                    { 'value': self.condition.composition }))

        if self.rvalue is not None:
            qnode.append(ET.Element(tag('return'),
                                    { 'value': self.rvalue }))

        return qnode

    def execute(self, context):
        """Execute the query.

        @return: the list of elements matching the query or a boolean
        """
        s=context.evaluate(self.source)

        if self.condition is None:
            if self.rvalue is None or self.rvalue == 'element':
                return s
            else:
                r=[]
                #context.addLocals( [ ('element', None) ] )
                context.pushLocals()
                for e in s:
                    context.setLocal('element', e)
                    r.append(context.evaluate(self.rvalue))
                context.popLocals()
                return r

        if hasattr(s, '__getitem__'):
            # FIXME: test could be different in the Advene2 model ?

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
                        r.append(context.evaluate(self.rvalue))
            context.popLocals()
            return r
        else:
            # Not a list. What do we do in this case ?
            return s

class Quicksearch(EtreeMixin):
    """Quicksearch component.

    This quicksearch component returns a set of data matching strings
    from a given source (the source is a TALES expression).

    @ivar source: the source of the data
    @type source: a TALES expression
    @ivar searched: the searched string
    @type searched: a string
    @ivar controller: the controller
    """
    def __init__(self, controller=None, source=None, searched=None, case_sensitive=False):
        if source is None:
            source='package/annotations'
        self.source=source
        self.searched=searched
        self.case_sensitive=case_sensitive
        self.controller=controller

    def from_etree(self, element, **kw):
        """Read the SimpleQuery from an ElementTree.Element

        @param element: the ElementTree.Element
        """
        assert element.tag == tag('quicksearch') or element.tag == 'quicksearch', "Invalid tag %s for Quicksearch" % element.tag
        compatibility=(element.tag == 'quicksearch')
        sourcenode=element.find(tag('source', old=compatibility))
        if sourcenode is not None:
            self.source=sourcenode.attrib['value']

        # Searched string
        s=element.find('searched')
        if s is not None:
            self.searched=urllib.unquote(unicode(s.attrib['value']).encode('utf-8'))

        # Case-sensitive
        s=element.find['case_sensitive']
        if s is not None:
            self.case_sensitive=(s.attrib['value'] == '1')
        return self

    def to_etree(self):
        """Create an ElementTree representation of the quicksearch.

        @return: an ElementTree.Element
        """
        qnode=ET.Element(tag('quicksearch'))

        qnode.append(ET.Element(tag('source'), { 'value': self.source } ))
        qnode.append(ET.Element(tag('searched'), 
                     { 'value': 
                       urllib.quote(unicode(self.searched).encode('utf-8'))} ))

        qnode.append(ET.Element('case_sensitive'),
                     { 'value': str(int(self.case_sensitive)) })

        return qnode

    def execute(self, context=None):
        """Execute the query.

        @return: the list of elements matching the query or a boolean
        """
        return self.controller.search_string(searched=self.searched,
                                             source=self.source,
                                             case_sensitive=self.case_sensitive)

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
        'ElementEditBegin':       _("Start of the editing of an element"),
        'ElementEditCancel':      _("Cancel of the editing of an element"),
        'ElementEditDestroy':     _("Destruction of the edit window of an element"),
        'ElementEditEnd':         _("Validation of the editing of an element"),
        'PackageEditEnd':         _("Ending editing of a package"),
        'AnnotationBegin':        _("Beginning of an annotation"),
        'AnnotationEnd':          _("End of an annotation"),
        'AnnotationCreate':       _("Creation of a new annotation"),
        'AnnotationEditEnd':      _("Ending editing of an annotation"),
        'AnnotationDelete':       _("Suppression of an annotation"),
        'AnnotationActivate':     _("Activation of an annotation"),
        'AnnotationDeactivate':   _("Deactivation of an annotation"),
        'AnnotationMerge':        _("Merging of two annotations"),
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
        'BookmarkHighlight':      _("Highlight a bookmark"),
        'BookmarkUnhighlight':    _("Unhighlight a bookmark"),
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
        'gui': _("GUI actions"),
        'popup': _("Popup actions"),
        'sound': _("Sound actions"),
        'state': _("State actions"),
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
    r.from_xml(uri=filename, catalog=catalog)
    print "Read %d rules." % len(r)
