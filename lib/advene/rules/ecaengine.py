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
"""ECA Engine module

This module holds the ECAEngine class which is dedicated to handling
events and triggering actions.
"""
import logging
logger = logging.getLogger(__name__)

import time
import sched
import threading
import copy

import advene.rules.elements

class MyThread(threading.Thread):
    """Override the standard run() method.

    Its behaviour changed in 2.6, and removed the __target, _args and
    _kwargs variable. Since we keep reusing them, this broke our code.
    """
    def __init__(self, **kwargs):
        super(MyThread, self).__init__(**kwargs)
        self._target=kwargs.get('target', None)

    def run(self):
        if self._target:
            self._target()

class ECAEngine:
    """ECAEngine class.

    Event-Condition-Action engine. It features three ruleset classes:

      - internal: for internal rules never exposed to the user
      - default: for default rules loaded from a configuration file
      - user: for user rules, defined in packages

    Internally, it stores the data in the L{self.rulesets} dictionary,
    indexed by class name ('internal', 'default', 'user'). Upon every
    update, it rebuilds the L{self.ruledict} dictionary, which is
    indexed by EventName and keeps a list of all rules associated to
    this EventName.

    @ivar ruledict: the global rules dictionary, indexed by EventName
    @type ruledict: dict
    @ivar rulesets: dictionary holding the rules indexed by classname
    @type rulesets: dict
    @ivar controller: the Advene controller
    @type controller: advene.core.controller.Controller
    @ivar catalog: the catalog of available actions
    @type catalog: elements.ECACatalog
    @ivar scheduler: the engine's scheduler
    @type scheduler: sched.scheduler
    @ivar schedulerthread: the scheduler's execution thread
    @type schedulerthread: threading.Thread
    """
    def __init__ (self, controller):
        """Initialize the ECAEngine.

        @param controller: the Advene controller
        @type controller: advene.core.controller.Controller
        """
        self.clear_state()
        self.ruledict = {}
        # History of events
        self.event_history = []
        self.controller=controller
        self.catalog=advene.rules.elements.ECACatalog()
        self.scheduler=sched.scheduler(time.time, time.sleep)
        self.schedulerthread=MyThread(target=self.scheduler.run)
        self.views_to_notify=[]

    def get_state(self):
        """Return a state of the current rulesets.

        @return: a copy of the current rulesets
        @rtype: dict
        """
        return self.rulesets.copy()

    def set_state(self, state):
        """Sets the state of all rulesets.

        @param state: a previously saved state (cf L{get_state})
        @type state: dict
        """
        for k, v in state.items():
            self.set_ruleset(v, type_=k)

    def clear_state(self):
        """Clear the state of all rulesets.
        """
        # Note: to add an additional class, do not forget to update
        # the notify method
        self.rulesets = {
            'default': advene.rules.elements.RuleSet(),
            'internal': advene.rules.elements.RuleSet(),
            'user': advene.rules.elements.RuleSet()
            }

    def clear_ruleset(self, type_='user'):
        """Clear the specified ruleset.

        @param type_: the ruleset's class
        @type type_: string
        """
        self.rulesets[type_] = advene.rules.elements.RuleSet()
        self.update_rulesets()

    def extend_ruleset(self, rs, type_='user'):
        """Extend the specified ruleset.

        @param rs: the set of rules to append
        @type rs: RuleSet
        @param type_: the destination ruleset's class
        @type type_: string
        """
        self.rulesets[type_].extend(rs)
        self.update_rulesets()

    def get_ruleset(self, type_='user'):
        """Get the specified ruleset.

        Note: it is the RuleSet itself, not a copy.

        @param type_: the ruleset's class
        @type type_: string
        """
        return self.rulesets[type_]

    def set_ruleset(self, rs, type_='user'):
        """Set the specified ruleset.

        Note: a copy of the new set of rules is made.

        @param rs: the new set of rules
        @type rs: RuleSet
        @param type_: the destination ruleset's class
        @type type_: string
        """
        self.rulesets[type_] = copy.copy(rs)
        self.update_rulesets()

    def read_ruleset_from_file(self, filename, type_='user', priority=0):
        """Read a ruleset from a file.

        @param filename: the file from which the rules are read.
        @type filename: string
        @param type_: the ruleset's class
        @type type_: string
        @return: the new ruleset
        @rtype: RuleSet
        """
        self.rulesets[type_] = advene.rules.elements.RuleSet(uri=filename, catalog=self.catalog, priority=priority)
        self.update_rulesets()
        return self.rulesets[type_]

    def update_rulesets(self):
        """Update the self.ruledict.

        L{self.ruledict} is a dict with event names as keys, and list
        of rules as actions.

        This method is called by the other helper methods
        (L{set_ruleset}, L{clear_ruleset}, ...).
        """
        self.ruledict.clear()
        # We could use self.rulesets.keys() but we want to specify the
        # class order:
        for type_ in ('internal', 'default', 'user'):
            for rule in self.rulesets[type_]:
                self.ruledict.setdefault(rule.event, []).append(rule)

    def schedule(self, action, context, delay=0, immediate=False):
        """Schedule an action for execution.

        @param action: the action to be executed
        @type action: Action
        @param context: the context parameter for the action
        @type context: AdveneContext
        @param delay: a delay for execution (in s)
        @type delay: float
        """
        if isinstance(action, advene.rules.elements.ActionList):
            for a in action:
                self.schedule(a, context, delay)
            return

        if action.immediate or immediate:
            action.execute(context)
        else:
            if delay:
                self.scheduler.enterabs(time.time()+delay, 0, action.execute, (context,))
            else:
                self.scheduler.enter(delay, 0, action.execute, (context,))
            if not self.schedulerthread.is_alive():
                try:
                    self.schedulerthread.run()
                except Exception:
                    logger.error("Exception in scheduler", exc_info=True)

    def reset_queue (self):
        """Reset the scheduler's queue.
        """
        for i in self.scheduler.queue:
            self.scheduler.cancel(i[0])

    def build_context(self, event, **kw):
        """Build an AdveneContext.

        @param event: the event name
        @type event: string
        @param kw: additional parameters
        @type kw: dict
        @return: the built context
        @rtype: AdveneContext
        """
        controller=self.controller
        try:
            here=kw['here']
        except KeyError:
            here=None
        context=controller.build_context(here=here)

        # Rule-specific root elements
        globals_={
            'annotation': None,
            'relation': None,
            'context': None,
            'event': event
            }
        globals_.update(kw)
        for k, v in globals_.items():
            context.addGlobal(k, v)
        return context

    def register_action(self, registered_action):
        """Register a RegisteredAction instance.

        @param registered_action: the action to be registered
        @type registered_action: RegisteredAction
        """
        self.catalog.register_action(registered_action)

    def register_view(self, view):
        self.views_to_notify.append(view)

    def unregister_view(self, view):
        self.views_to_notify.remove(view)


    def internal_rule(self, event=None, condition=None, method=None):
        """Declare an internal rule used by the application.

        It should not be exposed to the user (maybe not even to the
        developer).

        @param event: event name
        @type event: string
        @param condition: a condition
        @type condition: elements.Condition
        @param method: the method to be executed
        @type method: function or method
        @return: the new rule
        @rtype: elements.Rule
        """
        if method is None or event is None:
            return
        rule=advene.rules.elements.Rule(name="internal",
                                        priority=200,
                                        event=event,
                                        condition=condition,
                                        action=advene.rules.elements.Action(method=method))
        self.add_rule(rule, 'internal')
        return rule

    def add_rule(self, rule, type_='user'):
        """Add a new rule in the ruleset.

        @param rule: the rule to add.
        @type rule: elements.Rule
        @param type_: the ruleset's class
        @type type_: string
        """
        self.rulesets[type_].append(rule)
        self.update_rulesets()

    def remove_rule(self, rule, type_='user'):
        """Remove a rule from the ruleset.

        Used by view plugins when unregistering, and also for internal
        rules.

        @param rule: the rule to be removed
        @type rule: elements.Rule
        @param type_: the ruleset's class
        @type type_: string
        """
        try:
            self.rulesets[type_].remove(rule)
            self.update_rulesets()
        except ValueError:
            # Ignore the error if the rule was already removed.
            # but display a warning anyway (it should not happen)
            try:
                logger.warning("Trying to remove non-existant rule %s from %s ruleset", str(rule), type_)
            except AttributeError:
                logger.error("********** ATTRIBUTE ERROR for rule %s **********", hex(id(rule)))
            pass

    def dump(self):
        res=[]
        for k in sorted(self.ruledict.keys()):
            res.append("%s: %s" % (k, len(self.ruledict[k])))
        return res

    def notify (self, event_name, *param, **kw):
        """Invoked by the application on the occurence of an event.

        The event-dependant parameters are passed as named
        parameters. For instance, annotation-related events get a
        annotation= parameter.  See the ECA model documentation for
        more details and the parameters corresponding to each event.

        @param event_name: the event name
        @type event_name: string
        @param param: additionnal anonymous parameters
        @type param: misc
        @param kw: additionnal named parameters
        @type kw: depending on the context

        A special named parameter is delay, which will be given in ms.
        It contains the delay to apply to the rule execution.
        """
        immediate=False
        if 'immediate' in kw:
            immediate=True
            del kw['immediate']

        delay=0
        if 'delay' in kw:
            delay=int(kw['delay']) / 1000.0
            del kw['delay']
            logger.debug("Delay specified: %f", delay)

        context=self.build_context(event_name, **kw)
        try:
            a=self.ruledict[event_name]
        except KeyError:
            return

        rules=sorted( (rule
                       for rule in a
                       if rule.condition.match(context) ),
                      key=lambda e: e.priority,
                      reverse=True)

        context.pushLocals()
        for rule in rules:
            context.setLocal('rule', rule.name)
            # The 'view' is used in context.traversePathPreHook
            # to determine the context of interpretation of symbols

            # This is a kind of a mess. We should clarify all that
            # (first, we should not have used the same name for different
            # things).

            # It could already be set  (for instance, ViewCreate view=...)
            try:
                v=context.locals['view']
            except KeyError:
                try:
                    v = context.globals['view']
                except KeyError:
                    v=None
            try:
                v=self.controller.package.views[rule.origin]
            except KeyError:
                # rule.origin is not a view from the package. It may be
                # default_rule.xml for instance
                pass
            context.setLocal('view', v)
            self.schedule(rule.action, context, delay=delay, immediate=immediate)
        context.popLocals()
