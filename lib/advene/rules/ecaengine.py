#! /usr/bin/env python

"""ECA Engine.
"""

import advene.core.config as config

import time
import sched
import threading
import copy

import sre

import advene.model.tal.context
import advene.rules.elements

import advene.rules.actions

class ECAEngine:
    def __init__ (self, controller):
        self.rulesets = {
            'default': advene.rules.elements.RuleSet(),
            'internal': advene.rules.elements.RuleSet(),
            'user': advene.rules.elements.RuleSet()
            }
        self.ruledict = {}
        self.controller=controller
        self.catalog=advene.rules.elements.ECACatalog()
        for a in advene.rules.actions.DefaultActionsRepository(controller=controller).get_default_actions():
            self.catalog.register_action(a)
        self.scheduler=sched.scheduler(time.time, time.sleep)
        self.schedulerthread=threading.Thread(target=self.scheduler.run)

    def clear_ruleset(self, type_='user'):
        self.rulesets[type_] = advene.rules.elements.RuleSet()
        self.update_rulesets()

    def extend_ruleset(self, rs, type_='user'):
        self.rulesets[type_].extend(rs)
        self.update_rulesets()

    def get_ruleset(self, type_='user'):
        return self.rulesets[type_]

    def set_ruleset(self, rs, type_='user'):
        self.rulesets[type_] = copy.copy(rs)
        self.update_rulesets()
        
    def read_ruleset_from_file(self, filename, type_='user'):
        """Read from a file."""
        self.rulesets[type_] = advene.rules.elements.RuleSet(uri=filename, catalog=self.catalog)
        self.update_rulesets()

    def update_rulesets(self):
        """Update the self.ruledict.

        self.ruledict is a dict with event names as keys, and list of rules as actions.
        """
        self.ruledict.clear()
        # FIXME: maybe we should have a priority here (internal, then default, then user) ?
        for type_ in self.rulesets.keys():
            for rule in self.rulesets[type_]:
                self.ruledict.setdefault(rule.event, []).append(rule)

    def schedule(self, action, context, delay=0):
        if isinstance(action, advene.rules.elements.ActionList):
            for a in action:
                self.schedule(a, context)
            return
        
        if action.immediate:
            action.execute(context)
        else:
            self.scheduler.enter(delay, 0, action.execute, (context,))
            if not self.schedulerthread.isAlive():
                self.schedulerthread.run()

    def reset_queue (self):
        for i in self.scheduler.queue:
            self.scheduler.cancel(i[0])

    def build_context(self, event, kw):
        controller=self.controller
        options = {
            'package_url': u"/packages/advene",
            'snapshot': controller.imagecache,
            'namespace_prefix': config.data.namespace_prefix
            }
        globals={
            'package': controller.package,
            'annotation': None,
            'relation': None,
            'activeAnnotations': controller.active_annotations,
            'player': controller.player,
            'context': None,
            'event': event
            }
        context = advene.model.tal.context.AdveneContext (here=None,
                                                          options=options)
        globals.update(kw)
        for k in globals:
            context.addGlobal(k, globals[k])
        return context

    def register_action(self, registered_action):
        """Register a RegisteredAction instance."""
        self.catalog.register_action(registered_action)

    def internal_rule(self, event=None, condition=None, method=None):
        """Internal rule used by the application.

        It should not be exposed to the user (maybe not even to the developer).
        """
        if method is None or event is None:
            return
        rule=advene.rules.elements.Rule(name="internal",
                         event=event,
                         condition=condition,
                         action=advene.rules.elements.Action(method=method))
        self.rulesets['internal'].append(rule)
        self.update_rulesets()

    def remove_rule(self, ruleid, type_='user'):
        """Remove a rule from the ruleset.

        Used by view plugins when unregistering.
        """
        try:
            self.rulesets[type_].remove(ruleid)
            self.update_rulesets()
        except ValueError:
            # Ignore the error if the rule was already removed.
            # but display a warning anyway (it should not happen)
            print "Trying to remove non-existant rule %s from %s ruleset" % (str(ruleid), type_)
            pass
        
    def notify (self, event_name, *param, **kw):
        """Invoked by the application on the occurence of an event.
        
        @param event_name: the event name
        @type event_name: string
        """
        print "notify %s for %s" % (event_name, str(kw))
        context=self.build_context(event_name, kw)
        try:
            a=self.ruledict[event_name]
        except KeyError:
            return

        actions=[ rule.action
                  for rule in a
                  if rule.condition.match(context) ]
        for action in actions:
            self.schedule(action, context)
