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
"""
Advene controller
=================

This is the core of the Advene framework. It holds the various
components together (data model, webserver, GUI, event handler...),
and can be seen as a Facade design pattern for these components.

The X{AdveneEventHandler} is used by the application to handle events
notifications and actions triggering.
"""

import logging
logger = logging.getLogger(__name__)

import datetime
import sys
import time
import os
import cgi
import socket
import re
import webbrowser
import urllib.request, urllib.parse, urllib.error
from urllib.parse import urljoin
import io
from gi.repository import GObject
import shlex
import itertools
import operator

import advene.core.config as config

if config.data.debug:
    from advene.util.debug import debug_log

from gettext import gettext as _

import advene.core.plugin
from advene.core.mediacontrol import PlayerFactory
from advene.core.imagecache import ImageCache
import advene.core.idgenerator

from advene.rules.elements import RuleSet, RegisteredAction, SimpleQuery, Quicksearch
import advene.rules.ecaengine
import advene.rules.actions

from advene.model.package import Package
from advene.model.zippackage import ZipPackage
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.annotation import Annotation, Relation
from advene.model.fragment import MillisecondFragment
from advene.model.view import View
from advene.model.query import Query
from advene.model.util.defaultdict import DefaultDict
from advene.model.tal.context import AdveneTalesException
from advene.util.merger import Differ
from advene.util.website_export import WebsiteExporter

import advene.model.tal.context

import advene.util.helper as helper
import advene.util.importer
import xml.etree.ElementTree as ET
from advene.util.audio import SoundPlayer

from simpletal import simpleTAL, simpleTALES

if config.data.webserver['mode']:
    from advene.core.webcherry import AdveneWebServer

import threading
GObject.threads_init()

old_excepthook = sys.excepthook
def _advene_excepthook(type, value, tracebk, thread=None):
    """This function will replace sys.excepthook.
    """
    sys.last_type, sys.last_value, sys.last_traceback = type, value, tracebk
    logger.error("General exception %s %s %s", type, value, tracebk, exc_info=True)
    if config.data.livedebug:
        import pdb
        pdb.post_mortem(tracebk.tb_next or tracebk)
    # Use standard method also
    old_excepthook(type, value, tracebk)
sys.excepthook = _advene_excepthook

class MessageHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET, controller=None):
        super(MessageHandler, self).__init__(level)
        self.controller = controller
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        self.setFormatter(formatter)

    def emit(self, record):
        if self.controller.gui:
            self.controller.gui.log_message(self.format(record))

class GlobalPackage(object):
    """Wrapper to access all packages loaded data.
    """
    def __init__(self, controller):
        self.controller = controller

    @property
    def annotations(self):
        for p in self.controller.packages.values():
            for a in p.annotations:
                yield a

    @property
    def relations(self):
        for p in self.controller.packages.values():
            for r in p.relations:
                yield r

    @property
    def annotationTypes(self):
        for p in self.controller.packages.values():
            for at in p.annotationTypes:
                yield at

    @property
    def relationTypes(self):
        for p in self.controller.packages.values():
            for rt in p.relationTypes:
                yield rt

    @property
    def schemas(self):
        for p in self.controller.packages.values():
            for s in p.schemas:
                yield s

class AdveneController(object):
    """AdveneController class.

    The main attributes for this class are:
      - L{package} : the currently active package
      - L{packages} : a dict of loaded packages, indexed by their alias

      - L{active_annotations} : the currently active annotations
      - L{player} : the player (X{advene.core.mediacontrol.Player} instance)
      - L{event_handler} : the event handler
      - L{server} : the embedded web server

    Some entry points in the methods:
      - L{__init__} : controller initialization
      - L{update} : regularly called method used to update information about the current stream
      - L{update_status} : use this method to interact with the player

    On loading, we append the following attributes to package:
      - L{imagecache} : the associated imagecache
      - L{_idgenerator} : the associated idgenerator
      - L{_modified} : boolean

    @ivar active_annotations: the currently active annotations.
    @type active_annotations: list
    @ivar future_begins: the annotations that should be activated next (sorted)
    @type future_begins: list
    @ivar future_ends: the annotations that should be desactivated next (sorted)
    @type future_ends: list

    @ivar last_position: a cache to check whether an update is necessary
    @type last_position: int

    @ivar package: the package currently loaded and active
    @type package: advene.model.Package

    @ivar preferences: the current preferences
    @type preferences: dict

    @ivar player: a reference to the player
    @type player: advene.core.mediacontrol.Player

    @ivar event_handler: the event handler instance
    @type event_handler: AdveneEventHandler

    @ivar server: the embedded web server
    @type server: webserver.AdveneWebServer

    @ivar gui: the embedding GUI (may be None)
    @type gui: AdveneGUI
    """

    def __init__ (self, args=None):
        """Initializes player and other attributes.
        """
        # GUI (optional)
        self.gui=None
        # Webserver (optional)
        self.server=None

        # Dictionaries indexed by alias
        self.packages = {}
        self.global_package = GlobalPackage(self)

        # Reverse mapping indexed by package
        self.aliases = {}
        self.current_alias = None

        # Imagecache indexed by media
        self.imagecache = {}

        # Unknown arguments (neither a package nor a video file)
        self.unknown_args = []

        self.cleanup_done=False
        if args is None:
            args = []

        # Regexp to recognize DVD URIs
        self.dvd_regexp = re.compile("^dvd.*@(\d+):(\d+)")

        # List of active annotations
        self.active_annotations = []
        self.future_begins = None
        self.future_ends = None
        self.last_position = -1

        # List of (time, action) tuples, sorted along time
        # When the player or usertime reaches 'time', execute the action.
        self.videotime_bookmarks = []
        self.usertime_bookmarks = []

        self.pending_duration_update = False

        self.restricted_annotation_type=None
        self.restricted_annotations=None
        self.restricted_rule=None

        # Useful for debug in the evaluator window
        self.config=config.data

        # STBV
        self.current_stbv = None

        self.package = None

        self._soundplayer=None

        self.playerfactory=PlayerFactory()
        self.player = self.playerfactory.get_player()
        self.player.get_default_media = self.get_default_media
        self.player_restarted = 0
        self.slave_players = set()
        # source-id (returned by GObject.timeout_add)
        self.slave_player_timeout = None

        # Some player can define a cleanup() method
        try:
            self.player.cleanup()
        except AttributeError:
            pass

        # Scrubbing timeout guard
        self.scrub_lastvalue = None

        # Misc. modules: some features are implemented as plugins but
        # do not fit in the available categories (content-handler,
        # view, tracer...). Here is a placeholder for keeping their
        # reference, indexed by view name. The value is a class.
        self.generic_features = {}

        # Event handler initialization
        self.event_handler = advene.rules.ecaengine.ECAEngine (controller=self)
        self.modifying_events = self.event_handler.catalog.modifying_events
        self.event_queue = []
        self.tracers=[]

        # Load default actions
        advene.rules.actions.register(self)

        # Used in update_status to emit appropriate notifications
        self.status2eventname = {
            'pause':  'PlayerPause',
            'resume': 'PlayerResume',
            'start':  'PlayerStart',
            'stop':   'PlayerStop',
            'seek':    'PlayerSeek',
            'seek_relative':    'PlayerSeek',
            }
        self.event_handler.register_action(RegisteredAction(
                name="Message",
                method=self.message_log,
                description=_("Display a message"),
                parameters={'message': _("String to display.")},
                defaults={'message': 'annotation/content/data'},
                category='gui',
                ))

    def get_cached_duration(self):
        try:
            return self.package.cached_duration
        except AttributeError:
            return 0

    def set_cached_duration(self, value):
        if self.package is not None:
            self.package.cached_duration = int(value)

    cached_duration = property(get_cached_duration,
                               set_cached_duration,
                               doc="Cached duration for the current package")

    def self_loop(self):
        """Autonomous gobject loop for GUI-less controller.
        """
        self.mainloop = GObject.MainLoop()

        def update_wrapper():
            """Wrapper for the application update.

            This is necessary, since update() returns a position, that
            may be 0, thus interpreted as False by the loop handler if
            we directly invoke it.
            """
            self.update()
            return True

        GObject.timeout_add (100, update_wrapper)
        self.notify ("ApplicationStart")
        self.mainloop.run ()
        self.notify ("ApplicationEnd")

    def load_plugins(self, directory, prefix="advene_plugins"):
        """Load the plugins from the given directory.
        """
        logger.debug("Loading plugins from %s", directory)
        l=advene.core.plugin.PluginCollection(directory, prefix)
        for p in l:
            try:
                # Do not log plugin info if it could not be
                # initialized (return False).  For compatibility with
                # previous plugin API, the test must be explicitly
                # done as "is False", since old versions of
                # register did not have a return clause (and thus
                # return None)
                if p.register(controller=self) is False:
                    logger.error("Could not register " + p.name)
                else:
                    logger.info("Registering " + p.name)
            except AttributeError:
                logger.error("AttributeError in %s/%s", directory, p.name, exc_info=True)
                pass
        return l

    def queue_action(self, method, *args, **kw):
        """Queue an action.

        The method will be called in the application mainloop, i.e. in
        the main application thread. This can prevent problems when
        running in a GUI environment.
        """
        self.event_queue.append( (method, args, kw) )
        return True

    def queue_registered_action(self, ra, parameters):
        """Queue a registered action for execution.
        """
        c=self.build_context(here=self.package)
        self.queue_action(ra.method, c, parameters)
        return True

    def process_queue(self):
        """Batch process pending events.

        We process all the pending events since the last notification.
        Cannot use a while loop on event_queue, since triggered
        events can generate new notification.
        """
        # Dump the pending events into a local queue
        ev=self.event_queue[:]
        self.event_queue=[]

        # Now we can process the events
        for (method, args, kw) in ev:
            try:
                method(*args, **kw)
            except Exception:
                logger.error("Exception in process_queue", exc_info=True)

        return True

    def register_gui(self, gui):
        """Register the GUI for the controller.
        """
        self.gui=gui
        # Log messages to GUI
        logging.getLogger().addHandler(MessageHandler(controller=self))

    def register_tracer(self, tracer):
        """Register a trace builder
        """
        self.tracers.append(tracer)

    def register_event(self, name, description, modifying=False):
        """Register a new event.
        """
        catalog=self.event_handler.catalog
        catalog.basic_events.append(name)
        catalog.event_names[name]=description
        if modifying:
            catalog.modifying_events.add(name)

    def register_view(self, view):
        """Register a view.
        """
        if self.gui:
            self.gui.register_view(view)
        else:
            logger.error(_("No available GUI"))

    # Register methods for user-defined plugins
    def register_content_handler(self, handler):
        """Register a content-handler.
        """
        config.data.register_content_handler(handler)

    def register_global_method(self, method, name=None):
        """Register a global method.
        """
        config.data.register_global_method(method, name)

    def register_action(self, action):
        """Register an action.
        """
        if self.event_handler:
            self.event_handler.register_action(action)
        else:
            logger.error(_("No available event handler"))

    def register_viewclass(self, viewclass, name=None):
        """Register an adhoc view.
        """
        if self.gui:
            self.gui.register_viewclass(viewclass, name)
        else:
            logger.error(_("No available gui"))

    def register_importer(self, imp):
        """Register an importer.
        """
        advene.util.importer.register(imp)

    def register_player(self, imp):
        """Register a video player plugin.
        """
        config.data.register_player(imp)

    def register_generic_feature(self, name, feature_class):
        """Register a generic feature.
        """
        if name in self.generic_features:
            logger.warn(_("Warning: redefining an existing feature %s") % name)
        self.generic_features[name] = feature_class

    def register_slave_player(self, p):
        """Register a slave video player.
        """
        self.slave_players.add(p)

        def synchronize_players():
            for p in self.slave_players:
                p.synchronize()
            if not self.slave_players or config.data.preferences['slave-player-sync-delay'] == 0:
                # Abort the timeout
                self.slave_player_timeout = None
                return False
            else:
                return True

        if self.slave_player_timeout is None and config.data.preferences['slave-player-sync-delay'] != 0:
            self.slave_player_timeout = GObject.timeout_add(config.data.preferences['slave-player-sync-delay'], synchronize_players)

    def unregister_slave_player(self, p):
        """Unregister a slave video player.
        """
        try:
            self.slave_players.remove(p)
        except KeyError:
            pass

    def register_videotime_action(self, t, action):
        """Register an action to be executed when reaching the given movie time.

        action will be given the controller and current position as parameters.
        """
        self.videotime_bookmarks.append( (t, action) )
        return True

    def register_usertime_action(self, t, action):
        """Register an action to be executed when reaching the given user time (in ms)

        action will be given the controller and current position as parameters.
        """
        self.usertime_bookmarks.append( (t / 1000.0, action) )
        return True

    def register_usertime_delayed_action(self, delay, action):
        """Register an action to be executed after a given delay (in ms).

        action will be given the controller and current position as parameters.
        """
        self.usertime_bookmarks.append( (time.time() + delay / 1000.0, action) )
        return True

    def restrict_playing(self, at=None, annotations=None):
        """Restrict playing to the given annotation-type.

        If no annotation-type is given, restore unrestricted playing.
        """
        if at == self.restricted_annotation_type:
            return True

        # First remove the previous rule
        if self.restricted_rule is not None:
            self.event_handler.remove_rule(self.restricted_rule, type_='internal')
            self.restricted_rule=None

        self.restricted_annotation_type=at
        if annotations is None or at is None:
            self.restricted_annotations=None
        else:
            self.restricted_annotations=sorted(annotations, key=lambda a: a.fragment.begin)

        def restricted_play(context, parameters):
            a=context.globals['annotation']
            t=a.type
            if a.type == self.restricted_annotation_type:
                # Find the next relevant position.
                # First check the current annotations
                if self.restricted_annotations:
                    l=[an for an in self.active_annotations if an in self.restricted_annotations and an != a ]
                else:
                    l=[an for an in self.active_annotations if an.type == a.type and an != a ]
                if l:
                    # There is a least one other annotation of the
                    # same type which is also active. We can just wait for its end.
                    return True
                # future_begins holds a sorted list of (annotation, begin, end)
                if self.restricted_annotations:
                    l=[(an, an.fragment.begin, an.fragment.end)
                       for an in self.restricted_annotations
                       if an.fragment.begin > a.fragment.end ]
                else:
                    l=[an
                       for an in self.future_begins
                       if an[0].type == t ]
                if l and l[0][1] > a.fragment.end:
                    self.queue_action(self.update_status, 'seek', l[0][1])
                else:
                    # No next annotation. Return to the start
                    if self.restricted_annotations:
                        l=self.restricted_annotations
                    else:
                        l=[ an.fragment.begin for an in at.annotations ]
                        l.sort()
                    self.queue_action(self.update_status, "set", position=l[0])
            return True

        if at is not None:
            # New annotation-type restriction
            self.restricted_rule=self.event_handler.internal_rule(event="AnnotationEnd",
                                                                  method=restricted_play)
            p=self.player
            if p.is_playing():
                if [ a for a in self.active_annotations if a.type == at ]:
                    # We are in an annotation of the right type. Do
                    # not move the player, just play from here.
                    pass
                self.update_status("resume")
            else:
                l=[ a.fragment.begin for a in at.annotations ]
                if l:
                    l.sort()
                    self.update_status("start", position=l[0])

        self.notify('RestrictType', annotationtype=at)
        return True

    @property
    def defined_quicksearch_sources(self):
        """Return a list of TitledElements
        """
        return [ helper.TitledElement(expression, label)
                 for (label, expression) in [ (_("Annotations in current package"), "all_annotations"),
                                              (_("Annotations in all packages"), "global_annotations") ] + [
                (_("Annotations of type %s") % self.get_title(at),
                 'here/annotationTypes/%s/annotations' % at.id) for at in self.package.annotationTypes ] + [ (_("Views"), 'here/views'), (_("Tags"), 'tags'), (_("Ids"), 'ids') ]
                 ]

    def search_string(self, searched=None, sources=None, case_sensitive=False):
        """Search a string in the given sources (TALES expressions).

        A special source value 'tags' will return the elements that
        are tagged with the searched string.

        A special source value 'ids' will return the element with the
        given id.

        The search string obeys the classical syntax:
        w1 w2 -> search objects containing w1 or w2
        +w1 +w2 -> search objects containing w1 and w2
        w1 -w2 -> search objects containing w1 and not w2
        "foo bar" -> search objects containing the string "foo bar"
        """
        p=self.package

        def normalize_case(s):
            if case_sensitive:
                return s
            else:
                return s.lower()

        if case_sensitive:
            data_func=lambda e: e.content.data
        else:
            data_func=lambda e: normalize_case(e.content.data)

        if sources is None:
            sources=[ "all_annotations" ]

        # Replace standard \n/\t escape, because \ are parsed by shlex
        searched=searched.replace('\\n', '%n').replace('\\t', '%t')
        try:
            words=[ w.replace('%n', "\n").replace('%t', "\t") for w in shlex.split(searched) ]
        except ValueError:
            # Unbalanced quote. Just do a split along whitespace, the
            # user may be looking for a string with a quote and not
            # know it should be escaped.
            words=[ w.replace('%n', "\n").replace('%t', "\t") for w in searched.split() ]

        mandatory=[ w[1:] for w in words if w.startswith('+') ]
        exceptions=[ w[1:] for w in words if w.startswith('-') ]
        normal=[ w for w in words if not w.startswith('+') and not w.startswith('-') ]

        result=[]

        for source in sources:
            if source == 'tags':
                sourcedata=itertools.chain( p.annotations, p.relations )
                if case_sensitive:
                    data_func=lambda e: e.tags
                else:
                    data_func=lambda e: [ normalize_case(t) for t in e.tags ]
            elif source == 'ids':
                # Special search.
                for i in searched.split():
                    e=p.get_element_by_id(i)
                    if e is not None:
                        result.append(e)
                continue
            else:
                if source == 'all_annotations':
                    source = 'here/annotations'
                    sourcedata = p.annotations
                elif source == 'global_annotations':
                    sourcedata = self.global_package.annotations
                else:
                    c=self.build_context()
                    sourcedata=c.evaluateValue(source)

            for w in mandatory:
                w=normalize_case(w)
                sourcedata=[ el for el in sourcedata if w in data_func(el) ]
            for w in exceptions:
                w=normalize_case(w)
                sourcedata=[ el for el in sourcedata if w not in data_func(el) ]
            if not normal:
                # No "normal" search terms. Return the result.
                result.extend(sourcedata)
            else:
                normal=[ normalize_case(el) for el in normal ]
                for e in sourcedata:
                    data=data_func(e)
                    for w in normal:
                        if w in data:
                            result.append(e)
                            break
        return result

    def evaluate_query(self, query=None, context=None, expr=None):
        """Evaluate a Query in a given context.

        If context is None and expr is not None, then expr will be
        evaluated as a TALES expression and the result will be used to
        build a new context. This way, passing
        context=None, expr='package/annotations'
        will evaluate the query on all package's annotations.

        @param query: the query
        @type query: advene.model.queries.Query (hence with a content)
        @param context: the query context
        @type context: advene.model.tal.context.AdveneContext
        @param expr: an expression used to build the context
        @type expr: a TALES expression (string)
        @return: a tuple (result, query_object)
        @type: result may be None, query_object is a SimpleQuery or a Quicksearch or None
        """
        if context is None:
            if expr is None:
                context=self.build_context()
            else:
                context=self.build_context()
                source=context.evaluateValue(expr)
                context=self.build_context(here=source)

        result=None
        if query.content.mimetype == 'application/x-advene-simplequery':
            qexpr=SimpleQuery()
            qexpr.from_xml(query.content.stream)
            result=qexpr.execute(context=context)
        elif query.content.mimetype == 'application/x-advene-quicksearch':
            # Parse quicksearch query
            qexpr=Quicksearch(controller=self)
            qexpr.from_xml(query.content.stream)
            if expr is not None:
                # Override the sources... Is it a good idea ?
                qexpr.sources=[ expr ]
            result=qexpr.execute(context=context)
        else:
            raise Exception("Unsupported query type for %s" % query.id)
        return result, qexpr

    @property
    def typed_active(self):
        """Return a DefaultDict of active annotations grouped by type id.
        """
        d=DefaultDict(default=False)
        for a in self.active_annotations:
            d.setdefault(a.type.id, []).append(a)
        return d

    def build_context(self, here=None, alias=None, baseurl=None):
        """Build a context object with additional information.

        The information is cached if no additional parameter (alias,
        baseurl) is specified.
        """
        if here is None:
            here=self.package
        if alias is None and baseurl is None:
            try:
                c = here._cached_context
                c.restore()
                return c
            except AttributeError:
                pass
        if baseurl is None:
            baseurl=self.get_default_url(root=True, alias=alias)
        c=advene.model.tal.context.AdveneContext(here,
                                                 options={
                'package_url': baseurl,
                'snapshot': self.package.imagecache,
                'namespace_prefix': config.data.namespace_prefix,
                'config': config.data.web,
                'aliases': self.aliases,
                'controller': self,
                })
        c.addGlobal('package', self.package)
        c.addGlobal('packages', self.packages)
        c.addGlobal('player', self.player)
        for name, method in config.data.global_methods.items():
            c.addMethod(name, method)
        # Preserve a copy of globals/locals for later restoring
        c.checkpoint()
        return c

    def busy_port_info(self):
        """Display the processes using the webserver port.
        """
        processes=[]
        pat=':%d' % config.data.webserver['port']
        f=os.popen('netstat -atlnp 2> /dev/null', 'r')
        for l in f.readlines():
            if pat not in l:
                continue
            pid=l.rstrip().split()[-1]
            processes.append(pid)
        f.close()
        logger.warn(_("Cannot start the webserver\nThe following processes seem to use the %(port)s port: %(processes)s") % { 'port': pat,
                                                                                                                           'processes':  processes})

    @property
    def soundplayer(self):
        if self._soundplayer is None:
            self._soundplayer=SoundPlayer()
        return self._soundplayer

    def init(self, args=None):
        """Initialize the controller.
        """
        if args is None:
            args=[]

        try:
            self.player_plugins=self.load_plugins(os.path.join(os.path.dirname(advene.__file__), 'player'),
                                                  prefix="advene_player_plugins")
        except OSError:
            logger.error("Error while loading player plugins", exc_info=True)

        try:
            self.app_plugins=self.load_plugins(os.path.join(os.path.dirname(advene.__file__), 'plugins'),
                                               prefix="advene_app_plugins")
        except OSError:
            logger.error("Error while loading app plugins", exc_info=True)

        try:
            self.user_plugins=self.load_plugins(config.data.advenefile('plugins', 'settings'),
                                                prefix="advene_user_plugins")
        except OSError:
            logger.error("Error while loading user plugins", exc_info=True)

        # Read the default rules
        self.event_handler.read_ruleset_from_file(config.data.advenefile('default_rules.xml'),
                                                  type_='default', priority=100)

        self.event_handler.internal_rule (event="PackageLoad",
                                          method=self.manage_package_load)

        media=None
        # Arguments handling
        for uri in args:
            if '=' in uri:
                # alias=uri syntax
                alias, uri = uri.split('=', 2)
                alias = re.sub('[^a-zA-Z0-9_]', '_', alias)
                try:
                    self.load_package (uri=uri, alias=alias)
                    logger.info(_("Loaded %(uri)s as %(alias)s") % {'uri': uri, 'alias': alias})
                except Exception as e:
                    logger.error(_("Cannot load package from file %(uri)s: %(error)s") % {
                            'uri': uri,
                            'error': str(e)}, exc_info=True)
            else:
                name, ext = os.path.splitext(uri)
                if ext.lower() in ('.xml', '.azp', '.apl'):
                    alias = re.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))
                    try:
                        self.load_package (uri=uri, alias=alias)
                        logger.info(_("Loaded %(uri)s as %(alias)s") % {
                                'uri': uri, 'alias':  alias})
                    except Exception as e:
                        logger.error(_("Cannot load package from file %(uri)s: %(error)s") % {
                                'uri': uri,
                                'error': str(e)}, exc_info=True)
                elif ('dvd' in name
                      or ext.lower() in config.data.video_extensions):
                    # Try to load the file as a video file
                    media = uri
                else:
                    self.unknown_args.append(uri)

        # If no package is defined yet, load the template
        if self.package is None:
            # Do not activate, in order to prevent the triggering of a
            # MediaChange event. If the user only provided a movie
            # file on the command line, the appropriate MediaChange
            # will be notified through set_default_media
            self.load_package (activate=False)
            if media is not None:
                self.set_default_media(media, self.package)
            self.activate_package(self.aliases[self.package])
        else:
            if media is not None:
                self.set_default_media(media)

        # Register private mime.types if necessary
        if config.data.os != 'linux':
            config.data.register_mimetype_file(config.data.advenefile('mime.types'))

        self.player.check_player()

        if config.data.webserver['mode']:
            try:
                self.server = AdveneWebServer(controller=self, port=config.data.webserver['port'])
                serverthread = threading.Thread (target=self.server.start)
                serverthread.setName("Advene webserver")
                serverthread.start ()
            except socket.error:
                if config.data.os != 'win32':
                    self.busy_port_info()
                logger.info(_("Deactivating web server"))
                self.server = None
        return True

    def create_annotation(self, position, type, duration=None, content=None):
        position=int(position)
        if position > self.cached_duration:
            return None
        id_=self.package._idgenerator.get_id(Annotation)

        if duration is None:
            duration = int(self.cached_duration / 20)
        if position + duration > self.cached_duration:
            duration = self.cached_duration - position

        el=self.package.createAnnotation(
            ident=id_,
            type=type,
            author=config.data.userid,
            date=self.get_timestamp(),
            fragment=MillisecondFragment(begin=position,
                                         duration=duration))
        if content is not None:
            if getattr(el.type, '_fieldnames', None):
                # Structured data
                if "=" in content:
                    # Let's assume that content is simple-structured data.
                    try:
                        data = dict( (k, v) for l in content.splitlines() for (k, v) in l.split('=') )
                        # Add other keys
                        data.update(dict( (f, "") for f in sorted(el.type._fieldnames) ))
                        # Serialize
                        content = "\n".join( "%s=%s" % (k, v) for (k, v) in data.items() )
                    except ValueError:
                        # Badly formatted data
                        content = "\n".join( "%s=" % f for f in sorted(el.type._fieldnames) ) + "\ncontent=%s" % content.replace("\n", " ")
                else:
                    content = "\n".join( "%s=" % f for f in sorted(el.type._fieldnames) ) + "\ncontent=%s" % content.replace("\n", " ")
            elif 'svg' in el.type.mimetype:
                if not '<svg' in content:
                    # It must be simple text. Generate appropriate SVG.
                    content = """<svg:svg width="640pt" height="480pt" preserveAspectRatio="xMinYMin meet" version="1" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="http://www.w3.org/2000/svg">
  <text fill="green" name="Content" stroke="green" style="stroke-width:1; font-family: sans-serif; font-size: 22" x="8" y="390">%s</text>
</svg:svg>""" % content

            el.content.data=content
        elif getattr(el.type, '_fieldnames', None):
            el.content.data="\n".join( "%s=" % f for f in sorted(el.type._fieldnames) )
        elif 'svg' in el.type.mimetype:
            el.content.data = """<svg:svg width="640pt" height="480pt" preserveAspectRatio="xMinYMin meet" version="1" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="http://www.w3.org/2000/svg">
  <rect fill="none" name="Rect" stroke="green" style="stroke-width:2;" x="100" y="100" width="100" height="100" />
</svg:svg>"""

        self.package.annotations.append(el)
        el.complete=False
        self.notify('AnnotationCreate', annotation=el)
        return el

    def notify (self, event_name, *param, **kw):
        """Notify the occurence of an event.

        This method will trigger the corresponding actions. If the
        named parameter immediate=True is present, then execute the
        actions in the same thread of execution. Else, the actions
        will be triggered through queue_action in the application
        mainloop (main thread).
        """
        if config.data.debug:
            debug_log("Notify %s (%s): %s" % (
                event_name,
                helper.format_time_reference(self.player.current_position_value),
                str(kw)))

        # Set the package._modified state
        # This does not really belong here, but it is the more convenient and
        # maybe more effective way to implement it
        if event_name in self.modifying_events:
            # Find the element's package
            # Kind of hackish... This information should be clearly available somewhere
            el_name=event_name.lower().replace('create','').replace('editend','').replace('delete', '')
            el=kw[el_name]
            p=el.ownerPackage
            p._modified = True
            if event_name.endswith('Delete'):
                # We removed an element, so remove its id from the _idgenerator set
                p._idgenerator.remove(el.id)
            elif event_name.endswith('Create'):
                # We created an element. Make sure its id is registered in the _idgenerator
                p._idgenerator.add(el.id)

        if 'immediate' in kw:
            self.event_handler.notify(event_name, *param, **kw)
        else:
            self.queue_action(self.event_handler.notify, event_name, *param, **kw)
        return

    def set_volume(self, v):
        """Set the audio volume.
        """
        self.queue_action(self.player.sound_set_volume, v)
        return

    def get_volume(self):
        """Get the current audio volume.
        """
        try:
            v=self.player.sound_get_volume()
        except Exception:
            logger.error(_("Cannot get audio volume"), exc_info=True)
            v=0
        return v

    def open_url(self, url):
        """Open an URL in the most appropriate browser.

        Cf http://cweiske.de/howto/launch/ for details.
        """
        if (url.startswith(self.get_urlbase()) and
                           (self.server is None or not self.server.is_running())):
            # Cannot open a local URL: the webserver is not active
            logger.error(_("Cannot open Advene URL %s: the webserver is not running.") % url)
            return True
        if self.gui and self.gui.open_url_embedded(url):
            return True
        webbrowser.open(url)
        return True

    def get_url_for_alias (self, alias):
        """Return the URL for the given alias.
        """
        # FIXME: it should be more integrated with the webserver, in
        # order to use the same BaseURL as the calling context.
        if self.server:
            return urljoin(self.server.urlbase, "/packages/" + alias)
        else:
            return "/packages/" + alias

    def get_url_for_package (self, p):
        """Return the URL for the given package.
        """
        a=self.aliases[p]
        return self.get_url_for_alias(a)

    def get_default_url(self, root=False, alias=None):
        """Return the default package URL.

        If root, then return only the package URL even if it defines
        a default view.
        """
        if alias is None:
            try:
                alias=self.aliases[self.package]
            except KeyError:
                # self.package is not yet registered in self.aliases
                return None
        url = self.get_url_for_alias(alias)
        if not url:
            return None
        if root:
            return str(url)
        defaultview=self.package.getMetaData(config.data.namespace, 'default_utbv')
        if defaultview:
            url="%s/view/%s" % (url, defaultview)
        return url

    def get_urlbase(self):
        """Return the URL base.
        """
        if self.server is not None:
            return self.server.urlbase
        else:
            return "http:///"

    def get_title(self, element, representation=None, max_size=None):
        """Return the title for the given element.
        """
        def trim_size(s):
            if max_size is not None and len(s) > max_size:
                return s[:max_size]+helper.chars.ellipsis
            else:
                return s

        def cleanup(s):
            if not isinstance(s, str):
                s = str(s)
            i=s.find('\n')
            if i > 0:
                return trim_size(s[:i])
            else:
                return trim_size(s)

        if element is None:
            return _("None")
        if isinstance(element, str):
            return trim_size(element)
        if isinstance(element, Annotation) or isinstance(element, Relation):
            if representation is not None and representation != "":
                c=self.build_context(here=element)
                try:
                    r=c.evaluateValue(representation)
                except AdveneTalesException:
                    r=element.content.data
                if not r:
                    r=element.id
                return cleanup(r)

            expr=element.type.getMetaData(config.data.namespace, "representation")
            if expr is None or expr == '' or re.match('^\s+', expr):
                r=element.content.data
                if element.content.mimetype == 'image/svg+xml':
                    return "SVG graphics"
                elif not element.content.isTextual():
                    return "Data"
                if not r:
                    r=element.id
                return cleanup(r)
            else:
                c=self.build_context(here=element)
                try:
                    r=c.evaluateValue(expr)
                except AdveneTalesException:
                    r=element.content.data
                if not r:
                    r=element.id
                return cleanup(r)
        if isinstance(element, RelationType):
            arrow = helper.chars.arrow_to
            return arrow + str(cleanup(element.title))
        if hasattr(element, 'title') and element.title:
            return cleanup(element.title)
        if hasattr(element, 'id') and element.id:
            return str(element.id)
        return cleanup(str(element))

    def snapshot_taken(self, snap):
        """Callback for async-snapshot.

        Keep this method as an instance method so that it is not garbage collected.
        """
        if snap is not None and snap.height != 0:
            ic = self.imagecache.get(snap.media)
            if ic is None:
                logger.error("Cannot find %s media in imagecache (keys: %s).", snap.media, list(self.imagecache.keys()))
                return
            t = ic.round_timestamp(snap.date)
            ic[t] = helper.snapshot2png(snap)
            self.notify('SnapshotUpdate', position=t, media=snap.media)
            if t >= self.cached_duration - 2000 * ic.framerate:
                # Also store this same data for the very last frame,
                # which cannot be fetched normally.
                snap.date = self.cached_duration - 1000 * ic.framerate
                ic[ic.round_timestamp(snap.date)] = helper.snapshot2png(snap)
                self.notify('SnapshotUpdate', position=t, media=snap.media)

    def update_snapshot (self, position=None, media=None, force=False):
        """Event handler used to take a snapshot for the given position.

        @return: a boolean (~desactivation)
       """
        if position is None:
            position = self.player.current_position_value

        if media is None:
            media == self.package.getMedia()

        ic = self.imagecache.get(media, self.package.imagecache)
        if position >= self.cached_duration - 1000 * ic.framerate:
            position = self.round_timestamp(self.cached_duration - 1000 * ic.framerate - 10)

        if not config.data.player['snapshot'] or position < 0:
            return True

        # Refresh not forced, check before that it is needed.
        if not force and not self.get_snapshot(position=position, media=media, auto_update=False).is_default:
            return True

        # Check if the player has async_snapshot capability.
        if 'async-snapshot' in self.player.player_capabilities:
            logger.debug("Calling async_snapshot %d", position)
            self.player.async_snapshot(position, self.snapshot_taken)
            return True
        elif 'snapshot' in self.player.player_capabilities:
            # only 0-relative position for the moment
            try:
                i = self.player.snapshot(position)
            except:
                logger.exception("Exception in snapshot", exc_info=True)
                return True
            if i is not None and i.height != 0:
                ic = self.imagecache.get(i.media)
                if ic is None:
                    logger.error("Cannot find %s media in imagecache (keys: %s).", i.media, list(self.imagecache.keys()))
                    return
                ic[i.date] = helper.snapshot2png(i)
                self.notify('SnapshotUpdate', position=self.imagecache.round_timestamp(i.date), media=i.media)
        else:
            logger.debug("Player does not support snapshotting.")
        return True

    def round_timestamp(self, t, media=None):
        """Round the given timestamp to the appropriate time wrt. framerate.
        """
        ic = self.imagecache.get(media, self.package.imagecache)
        if (t >= self.cached_duration - 1000 * ic.framerate):
            # Fetching the very last frame seems to cause issues for
            # many/all movies. Cap the value to the previous one.
            t = self.cached_duration - 1000 * ic.framerate - 1

        return ic.round_timestamp(t)

    def frame2time(self, n, media=None):
        """Convert a frame number to a time in ms.

        based on the current video framerate.
        """
        ic = self.imagecache.get(media, self.package.imagecache)
        return int(n * 1000 * ic.video_info['framerate'])

    def get_snapshot(self, position=None, annotation=None, media=None, precision=None, auto_update=True):
        """Return the snapshot for a given position or annotation.

        If position is specified without a media, then the default
        (current) media will be used.
        """
        # Determine appropriate imagecache:
        # In any case, fallback on current imagecache if nothing is specified
        if media:
            # Media explicitly defined by the user
            imagecache = self.imagecache.get(media, self.package.imagecache)
        elif annotation is not None:
            # Media implicitly defined by the annotation
            media = annotation.ownerPackage.getMedia()
            imagecache = annotation.ownerPackage.imagecache
        else:
            media = self.package.getMedia()
            imagecache = self.package.imagecache

        # Use annotation begin only if position was not explictly defined
        if position is None and annotation is not None:
            position = annotation.fragment.begin

        position = self.round_timestamp(position, media)
        snapshot = imagecache.get(position, precision=precision)
        if auto_update and position >= 0 and snapshot.is_default and media == self.get_default_media():
            self.update_snapshot(position, media=media, force=True)
        return snapshot

    def get_default_media (self, package=None):
        """Return the current media for the given package.
        """
        if package is None:
            package = self.package

        mediafile = package.media
        if mediafile is None or mediafile == "":
            return ""
        m=self.dvd_regexp.match(mediafile)
        if m:
            title,chapter=m.group(1, 2)
            mediafile=self.player.dvd_uri(title, chapter)
        elif mediafile.startswith('http:'):
            # FIXME: check for the existence of the file
            pass
        else:
            mediafile=self.locate_mediafile(mediafile)

        package.setMedia(mediafile)
        return mediafile

    def locate_mediafile(self, mediafile):
        """Locate the given media file.
        """
        if not os.path.exists(mediafile):
            # It is a file. It should exist. Else check for a similar
            # one in moviepath
            # UNIX/Windows interoperability: convert pathnames
            n=mediafile.replace('\\', os.sep).replace('/', os.sep)

            name=os.path.basename(n)
            for d in config.data.path['moviepath'].split(os.pathsep):
                if d == '_':
                    # Get package dirname
                    d=self.package.uri
                    # And convert it to a pathname (for Windows)
                    if d.startswith('file:'):
                        d=d.replace('file://', '')
                    d=urllib.request.url2pathname(d)
                    d=os.path.dirname(d)
                if '~' in d:
                    # Expand userdir
                    d=str(os.path.expanduser(d), sys.getfilesystemencoding())

                n=os.path.join(d, name)
                # FIXME: if d is a URL, use appropriate method (urllib.??)
                if os.path.exists(n):
                    mediafile=n
                    logger.info(_("Found matching video file in moviepath: %s") % n)
                    break
        else:
            # Path exists. It may be a relative path, so convert it to
            # absolute path.
            mediafile=os.path.abspath(mediafile)

        return mediafile

    def get_defined_tags(self, p=None):
        """Return the set of existing tags.
        """
        if p is None:
            p=self.package
        tags=set()
        # Populate with annotations, relations tags
        for e in itertools.chain(p.annotations, p.relations):
            tags.update(e.tags)
        return tags

    def update_package_title(self):
        """Generate a default package title if none was set.
        """
        if (len(self.package.annotations)
            and (not self.package.title
                 or self.package.title == "Template package"
                 or self.package.title.startswith(_("Analysis of ")))
            and self.get_default_media()):
            self.package.title = _("Analysis of ") + str(os.path.basename(self.get_default_media()))
            self.notify("PackageEditEnd", package=self.package)
            return True
        else:
            return False

    def set_media(self, uri=None):
        """Set the current media in the video player.
        """
        p = self.player
        if p.is_playing():
            p.stop()
        video_info = p.set_uri(uri)
        # Reset cached_duration so that it will be updated on play
        self.pending_duration_update = True
        self.notify("MediaChange", uri=uri)
        return video_info

    def set_default_media (self, uri, package=None):
        """Set the default media for the package.
        """
        if package is None:
            package = self.package
        m = self.dvd_regexp.match(uri)
        if m:
            title,chapter = m.group(1,2)
            uri="dvd@%s:%s" % (title, chapter)
        package.setMedia(uri)
        if m:
            uri = self.player.dvd_uri(title, chapter)
        video_info = self.set_media(uri)
        try:
            framerate = video_info.get('framerate_denom', 0) / video_info.get('framerate_num', 1)
        except ZeroDivisionError:
            framerate = 0
        if framerate == 0:
            framerate = 1 / config.data.prefix['default-fps']
            logger.warn("Cannot determine video FPS. Using default value %.02f", framerate)
        # Reset the imagecache
        if uri not in self.imagecache:
            self.imagecache[uri] = ImageCache(uri, framerate=framerate)
            id_ = helper.mediafile2id(uri)
            self.imagecache[uri].load(id_)
        package.imagecache = self.imagecache[uri]

        # Store video info in the ImageCache
        video_info['framerate'] = framerate
        package.imagecache.video_info = video_info

        # Update package title and description if necessary
        self.update_package_title()

    def delete_element (self, el, immediate_notify=False, batch=None, undone=False):
        """Delete an element from its package.

        Take care of all dependencies (for instance, annotations which
        have relations.
        """
        p=el.ownerPackage
        if isinstance(el, Annotation):
            # We iterate on a copy of relations, since it may be
            # modified during the loop
            self.notify('EditSessionStart', element=el, immediate=True, undone=undone)
            for r in el.relations[:]:
                [ a.relations.remove(r) for a in r.members if r in a.relations ]
                self.delete_element(r, immediate_notify=immediate_notify, batch=batch, undone=undone)
            p.annotations.remove(el)
            self.notify('AnnotationDelete', annotation=el, immediate=immediate_notify, batch=batch, undone=undone)
        elif isinstance(el, Relation):
            for a in el.members:
                if el in a.relations:
                    a.relations.remove(el)
            p.relations.remove(el)
            self.notify('RelationDelete', relation=el, immediate=immediate_notify, undone=undone)
        elif isinstance(el, AnnotationType):
            for a in el.annotations:
                self.delete_element(a, immediate_notify=True, batch=batch, undone=undone)
            el.schema.annotationTypes.remove(el)
            self.notify('AnnotationTypeDelete', annotationtype=el, immediate=immediate_notify, undone=undone)
        elif isinstance(el, RelationType):
            for r in el.relations:
                self.delete_element(r, immediate_notify=True, batch=batch, undone=undone)
            el.schema.relationTypes.remove(el)
            self.notify('RelationTypeDelete', relationtype=el, immediate=immediate_notify, undone=undone)
        elif isinstance(el, Schema):
            for at in el.annotationTypes:
                self.delete_element(at, immediate_notify=True, batch=batch, undone=undone)
            for rt in el.relationTypes:
                self.delete_element(rt, immediate_notify=True, batch=batch, undone=undone)
            p.schemas.remove(el)
            self.notify('SchemaDelete', schema=el, immediate=immediate_notify, undone=undone)
        elif isinstance(el, View):
            self.notify('EditSessionStart', element=el, immediate=True, undone=undone)
            p.views.remove(el)
            self.notify('ViewDelete', view=el, immediate=immediate_notify, batch=batch, undone=undone)
        elif isinstance(el, Query):
            self.notify('EditSessionStart', element=el, immediate=True, undone=undone)
            p.queries.remove(el)
            self.notify('QueryDelete', query=el, immediate=immediate_notify, batch=batch, undone=undone)
        elif isinstance(el, Resources) or isinstance(el, ResourceData):
            if isinstance(el, Resources):
                for c in el.children():
                    self.delete_element(c, immediate_notify=True, batch=batch, undone=undone)
            p=el.parent
            del(p[el.id])
            self.notify('ResourceDelete', resource=el, immediate=immediate_notify, undone=undone)
        return True

    def transmute_annotation(self, annotation, annotationType, delete=False, position=None, notify=True):
        """Transmute an annotation to a new type.

        If delete is True, then delete the source annotation.

        If position is not None, then set the new annotation begin to position.
        """
        if annotation.type == annotationType:
            # Transmuting on the same type.
            if position is None:
                # Do not just duplicate the annotation
                return None
            elif delete:
                # If delete, then we can simply move the annotation
                # without deleting it.
                if notify:
                    self.notify('EditSessionStart', element=annotation, immediate=True)
                d=annotation.fragment.duration
                annotation.fragment.begin=position
                annotation.fragment.end=position+d
                if notify:
                    self.notify("AnnotationEditEnd", annotation=annotation, comment="Transmute annotation")
                    self.notify('EditSessionEnd', element=annotation)
                return annotation
        ident=self.package._idgenerator.get_id(Annotation)
        an = self.package.createAnnotation(type = annotationType,
                                           ident=ident,
                                           fragment=annotation.fragment.clone())
        if position is not None:
            an.fragment.begin=position
            an.fragment.end=position+annotation.fragment.duration
        self.package.annotations.append(an)
        an.author=config.data.userid
        # Check if types are compatible.
        # FIXME: should be made more generic, but we need more metadata for this.
        if (an.type.mimetype == annotation.type.mimetype
            or an.type.mimetype == 'text/plain'):
            # We consider that text/plain can hold anything
            an.content.data=annotation.content.data
        elif an.type.mimetype == 'application/x-advene-zone':
            # we want to define a zone.
            if annotation.type.mimetype == 'text/plain':
                d={ 'name': annotation.content.data.replace('\n', '\\n') }
            elif annotation.type.mimetype == 'application/x-advene-structured':
                r=re.compile('^(\w+)=(.*)')
                d=dict([ (r.findall(l) or [ ('_error', l) ])[0] for l in annotation.content.data.split('\n') ])
                name="Unknown"
                for n in ('name', 'title', 'content'):
                    if n in d:
                        name=d[n]
                        break
                d['name']=name.replace('\n', '\\n')
            else:
                d={'name': 'Unknown'}
            d.setdefault('x', 50)
            d.setdefault('y', 50)
            d.setdefault('width', 10)
            d.setdefault('height', 10)
            d.setdefault('shape', 'rect')
            an.content.data="\n".join( [ "%s=%s" % (k, v) for k, v in d.items() ] )
        elif an.type.mimetype == 'application/x-advene-structured':
            if annotation.type.mimetype == 'text/plain':
                an.content.data = "title=" + annotation.content.data.replace('\n', '\\n')
            elif annotation.type.mimetype == 'application/x-advene-structured':
                an.content.data = annotation.content.data
            else:
                logger.warn("Cannot convert %s to %s" % (annotation.type.mimetype,
                                                          an.type.mimetype))
                an.content.data = annotation.content.data
        elif an.type.mimetype == 'image/svg+xml':
            # Use a template for text->SVG conversion.
            # FIXME: we should be able to propose a variety of templates, passed as parameter from the GUI
            an.content.data = """<svg:svg height="320pt" preserveAspectRatio="xMinYMin meet" version="1" viewBox="0 0 400 320" width="400pt" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="http://www.w3.org/2000/svg">
  <text fill="green" name="Content" stroke="green" style="stroke-width:1; font-family: sans-serif; font-size: 22" x="8" y="290">%s</text>
</svg:svg>""" % self.get_title(annotation)
        else:
            logger.warn("Do not know how to convert %s to %s" % (annotation.type.mimetype,
                                                              an.type.mimetype))
            an.content.data = annotation.content.data
        an.setDate(self.get_timestamp())

        if delete and not annotation.relations:
            if notify:
                self.notify('EditSessionStart', element=annotation, immediate=True)
            self.package.annotations.remove(annotation)
            if notify:
                self.notify('AnnotationMove', annotation=annotation, comment="Transmute annotation")
                self.notify('AnnotationDelete', annotation=annotation, comment="Transmute annotation")
        if notify:
            self.notify("AnnotationCreate", annotation=an, comment="Transmute annotation")

        return an

    def quick_completion_fill_annotation(self, annotation, index):
        """Quickly edit an annotation by using a completion at the given index.

        Index is a number, usually between 0 and 9
        Return False if the edition could not be done.
        Return True if the edition was successful.
        """
        if not config.data.preferences['completion-quick-fill']:
            return False
        comps = annotation.ownerPackage._indexer.get_completions("", context=annotation, predefined_only=True)
        try:
            val = comps[index]
            new_content = helper.title2content(val,
                                               annotation.content,
                                               annotation.type.getMetaData(config.data.namespace, "representation"))
            if new_content is None:
                logger.error("Cannot update annotation content - too complex representation")
                return False
            self.notify('EditSessionStart', element=annotation, immediate=True)
            annotation.content.data = new_content
            self.notify('AnnotationEditEnd', annotation=annotation)
            self.notify('EditSessionEnd', element=annotation)
        except IndexError:
            return False
        return True

    def duplicate_annotation(self, annotation):
        """Duplicate an annotation.
        """
        ident=self.package._idgenerator.get_id(Annotation)
        an = self.package.createAnnotation(type = annotation.type,
                                           ident=ident,
                                           fragment=annotation.fragment.clone())
        an.fragment.begin = annotation.fragment.end
        an.fragment.end = an.fragment.begin + annotation.fragment.duration
        if an.fragment.end > self.cached_duration:
            an.fragment.end = self.cached_duration
        self.package.annotations.append(an)
        an.author=config.data.userid
        an.content.data=annotation.content.data
        an.setDate(self.get_timestamp())
        self.notify("AnnotationCreate", annotation=an, comment="Duplicate annotation")
        return an

    def split_annotation(self, annotation, position):
        """Split an annotation at the given position
        """
        if (position <= annotation.fragment.begin
            or position >= annotation.fragment.end):
            logger.warn(_("Cannot split the annotation: the given position is outside."))
            return annotation

        # Create the new one
        ident=self.package._idgenerator.get_id(Annotation)
        an = self.package.createAnnotation(type = annotation.type,
                                           ident=ident,
                                           fragment=annotation.fragment.clone())

        # Shorten the first one.
        self.notify('EditSessionStart', element=annotation, immediate=True)
        annotation.fragment.end = position
        self.notify("AnnotationEditEnd", annotation=annotation, comment="Split annotation")
        self.notify('EditSessionEnd', element=annotation)

        # Shorten the second one
        an.fragment.begin = position

        self.package.annotations.append(an)
        an.author=config.data.userid
        an.content.data=annotation.content.data
        an.setDate(self.get_timestamp())
        self.notify("AnnotationCreate", annotation=an, comment="Split annotation")
        return an

    def merge_annotations(self, s, d, extend_bounds=False):
        """Merge annotation s into annotation d.
        """
        batch_id=object()
        self.notify('EditSessionStart', element=d, immediate=True)
        if extend_bounds:
            # Extend the annotation bounds (mostly used for same-type
            # annotations)
            begin=min(s.fragment.begin, d.fragment.begin)
            end=max(s.fragment.end, d.fragment.end)
            d.fragment.begin=begin
            d.fragment.end=end
        # Merging data
        mts=s.type.mimetype
        mtd=d.type.mimetype
        if mtd == 'text/plain':
            d.content.data=d.content.data + '\n' + s.content.data
        elif ( mtd == mts and mtd == 'application/x-advene-structured' ):
            # Compare fields and merge identical fields
            sdata=s.content.parsed()
            ddata=d.content.parsed()
            for k, v in sdata.items():
                if k in ddata:
                    # Merge fields
                    ddata[k] = "|".join( (sdata[k], ddata[k]) )
                else:
                    ddata[k] = sdata[k]
            # Re-encode ddata
            d.content.data="\n".join( [ "%s=%s" % (k, str(v).replace('\n', '%0A')) for (k, v) in ddata.items() if k != '_all' ] )
        elif mtd == 'application/x-advene-structured':
            d.content.data=d.content.data + '\nmerged_content="' + urllib.parse.quote(s.content.data)+'"'
        self.notify("AnnotationMerge", annotation=d,comment="Merge annotations", batch=batch_id)
        self.delete_element(s, batch=batch_id)
        self.notify("AnnotationEditEnd", annotation=d, comment="Merge annotations", batch=batch_id)
        self.notify('EditSessionEnd', element=d)
        return d

    def split_package_by_type(self, atype, callback=None):
        """Generate packages corresponding to annotations in the given annotation type.

        @param atype: the annotation type used for splitting
        @type atype: AnnotationType
        @param callback: a callback method for progress report
        @param callback: a function which will take as parameters (name, filename, annotation_count, index)
        """
        baseuri, extension = os.path.splitext(urllib.parse.unquote(self.package.uri))
        for index, segment in enumerate(sorted(atype.annotations)):
            # Create a new package
            p = Package(uri="new_pkg", source=None)
            p._idgenerator = advene.core.idgenerator.Generator(p)
            differ = Differ(self.package, p, self)
            # Copy its structure
            for name, s, d, action in differ.diff_structure():
                try:
                    action(s, d)
                except:
                    logger.error("Error when splitting package (%s)", name, exc_info=True)
            # Copy relevant annotations (contained in segment)
            count = 0
            for a in self.package.annotations:
                if segment.fragment.begin < a.fragment.end and segment.fragment.end > a.fragment.begin:
                    differ.copy_annotation(a)
                    count += 1
            # Copy package metadata
            differ.update_meta(self.package, p, 'advenetool', 'duration')
            differ.update_meta(self.package, p, 'advenetool', 'mediafile')
            differ.update_meta(self.package, p, 'advenetool', 'tag_colors')
            differ.update_meta(self.package, p, 'dc', 'title')
            differ.update_meta(self.package, p, 'dc', 'creator')
            differ.update_meta(self.package, p, 'dc', 'description')
            p.date = self.get_timestamp()

            title = self.get_title(segment)
            fname = "%s-split-%03d-%s%s" % (baseuri, index + 1, helper.title2id(title), extension)
            p.save(fname)
            if callback:
                if not callback(title, fname, count, index + 1):
                    # Action was cancelled
                    return
            logger.info("Saving %s with %d annotations.", fname, count)

    def select_player(self, p):
        """Activate the given player.
        """
        # Stop the current player.
        self.player.stop()
        self.player.exit()
        if 'record' in self.player.player_capabilities:
            # The old player was a recorder. Chances are that we
            # recorded something. In this case, set the default_media
            # to the recorded file path.
            uri = self.player.get_uri()
            if uri and not self.get_default_media():
                self.set_default_media(uri)

        # Start the new one
        self.player=p()
        if 'record' not in p.player_capabilities:
            # Store the selected player if it is not a recorder.
            config.data.player['plugin']=p.player_id
        self.notify('PlayerChange', player=p)
        mediafile = self.get_default_media()
        self.set_media(mediafile)

    def restart_player (self):
        """Restart the media player."""
        self.player.restart_player ()
        mediafile = self.get_default_media()
        self.set_media(mediafile)
        self.notify('PlayerChange', player=self.player)

    def get_timestamp(self):
        """Return a formatted timestamp for the current date.
        """
        return datetime.datetime.now().replace(microsecond=0).isoformat()

    def get_tag_color_for_element(self, element):
        """Given an element, return a color based on tags set.
        """
        try:
            tags = element.tags
        except AttributeError:
            return None
        try:
            d = element.rootPackage._tag_colors
        except AttributeError:
            return None
        for t in tags:
            try:
                return d[t]
            except KeyError:
                pass
        return None

    STATIC_STRING_RE = re.compile('string:[^$]*')
    def get_element_color(self, element, metadata='color'):
        """Return the color for the given element.

        Return None if no color is defined.

        It will first check if a 'color' metadata is set on the
        element, and try to evaluate is as a TALES expression. If no
        color is defined, or if the result of evaluation is None, it
        will then try to use the 'item_color' metadata from the container type
        (annotation type for annotations, schema for types).

        If not defined (or evaluating to None), it will try to use the
        'color' metadata of the container (annotation-type for
        annotations, schema for types).
        """

        def shortcut_evaluateValue(element, expr):
            """Optimized version of evaluateValue

            Common expressions (static strings, here/tag_color
            expression) are evaluated without using the AdveneContext.
            """
            val = None

            if not expr:
                return None

            if self.STATIC_STRING_RE.match(expr):
                # Static value.
                return expr[7:]

            if expr == u'here/tag_color':
                return self.get_tag_color_for_element(element)

            if val is None:
                # Previous shortcuts did not work. Go the slow way
                # through a AdveneContext evaluation
                logger.debug("unoptimized evaluation - %s", expr)
                c = self.build_context(here=element)
                try:
                    val = c.evaluateValue(expr)
                except Exception:
                    logger.debug("Exception in color evaluation for %s", exc_info=True)
                    val = None
            return val

        # First try the 'color' metadata from the element itself.
        color = None
        try:
            expr = element.getMetaData(config.data.namespace, metadata)
        except AttributeError:
            return None
        if expr:
            color = shortcut_evaluateValue(element, expr)

        if not color:
            # Not found in element. Try item_color from the container.
            if hasattr(element, 'type'):
                container=element.type
            elif hasattr(element, 'schema'):
                container=element.schema
            else:
                container=None
            if container:
                expr = container.getMetaData(config.data.namespace, 'item_color')
                if expr:
                    color = shortcut_evaluateValue(element, expr)
                if not color:
                    # Really not found. So use the container color.
                    color = self.get_element_color(container)
        return color

    def load_package (self, uri=None, alias=None, activate=True):
        """Load a package.

        This method is esp. used as a callback for webserver. If called
        with no argument, or an empty string, it will create a new
        empty package.

        @param uri: the URI of the package
        @type uri: string
        @param alias: the name of the package (ignored in the GUI, always "advene")
        @type alias: string
        """
        if uri is None or uri == "":
            try:
                self.package = Package (uri="new_pkg",
                                        source=config.data.advenefile(config.data.templatefilename))
            except Exception:
                logger.error(_("Cannot find the template package %(filename)s")
                             % {'filename': config.data.advenefile(config.data.templatefilename)}, exc_info=True)

                alias='new_pkg'
                self.package = Package (alias, source=None)
            self.package.author = config.data.userid
            self.package.date = self.get_timestamp()
        elif uri.lower().endswith('.apl'):
            # Advene package list. Parse it and call 'load_package' for each package
            def tag(i):
                return ET.QName(config.data.namespace, i)

            tree=ET.parse(uri)
            root=tree.getroot()
            if root.tag != tag('package-list'):
                raise Exception('Invalid XML element for session: ' + root.tag)
            default_alias=None
            for node in root:
                if node.tag == tag('package'):
                    u=node.attrib['uri']
                    a=node.attrib['alias']
                    d='default' in node.attrib
                    self.load_package(u, a, activate=False)
                    if d:
                        default_alias=a
                if not default_alias:
                    # If no default package was specified, use the last one
                    default_alias=a
            if activate:
                self.activate_package(default_alias)
            return
        else:
            t = time.time()
            try:
                p = Package (uri=uri)
            except Exception:
                logger.error("Cannot load package %s", uri, exc_info=True)
                return
            dur = time.time() - t
            logger.info("Loaded package in %f seconds" % dur)
            # Check if the imported package was found. Else it will
            # fail when accessing elements...
            imp = []
            for i in p.imports:
                try:
                    imp.append(i.package)
                except Exception as e:
                    raise Exception(_("Cannot read the imported package %(uri)s: %(error)s") % {
                            'uri': i.uri,
                            'error': str(e)})
            self.package=p

        if alias is None:
            # Autogenerate the alias
            if uri:
                alias, ext = os.path.splitext(os.path.basename(uri))
            else:
                alias = 'new_pkg'

        # Replace forbidden characters. The GUI is responsible for
        # letting the user specify a valid alias.
        alias = re.sub('[^a-zA-Z0-9_]', '_', alias)

        # This will initialize the package imagecache
        self.set_default_media(self.package.getMedia(), self.package)
        self.package._idgenerator = advene.core.idgenerator.Generator(self.package)
        self.package._modified = False

        # State dictionary
        self.package.state=DefaultDict(default=0)

        # Initialize the color palette for the package
        # Remove already used colors
        l=list(config.data.color_palette)
        for at in self.package.annotationTypes:
            try:
                l.remove(at.getMetaData(config.data.namespace, 'color'))
            except ValueError:
                pass
        if not l:
            # All colors were used.
            l=list(config.data.color_palette)
        self.package._color_palette=helper.CircularList(l)

        # Parse tag_colors attribute
        cols = self.package.getMetaData (config.data.namespace, "tag_colors")
        if cols:
            d = dict(cgi.parse_qsl(cols))
        else:
            d={}
        self.package._tag_colors=d

        self.pending_duration_update = True
        duration = self.package.getMetaData (config.data.namespace, "duration")
        if duration is not None:
            try:
                v=int(float(duration))
                self.pending_duration_update = False
            except ValueError:
                v=0
            self.cached_duration = v
        else:
            self.cached_duration = 0

        self.register_package(alias, self.package)

        # Compatibility issues in ruleset/queries: since r4503, we are
        # stricter wrt. namespaces. Fix common problems.
        for q in self.package.queries:
            if 'http://liris.cnrs.fr/advene/ruleset' in q.content.data:
                logger.debug("Fixing query %s", q.id)
                q.content.data = q.content.data.replace('http://liris.cnrs.fr/advene/ruleset',
                                                        config.data.namespace)
        for v in self.package.views:
            if (v.content.mimetype == 'application/x-advene-ruleset'
                and '<ruleset>' in v.content.data):
                logger.debug("Fixing view %s", v.id)
                v.content.data = v.content.data.replace('<ruleset>',
                                                        '<ruleset xmlns="http://experience.univ-lyon1.fr/advene/ns/advenetool">')

        # Notification must be immediate, since at application startup, package attributes
        # (_indexer, imagecache) are initialized by events, and may be needed by
        # default views
        self.notify("PackageLoad", package=self.package, immediate=True)
        if activate:
            self.activate_package(alias)

    def remove_package(self, package=None):
        """Unload the package.
        """
        if package is None:
            package=self.package
        alias=self.aliases[package]
        self.unregister_package(alias)
        del(package)
        return True

    def register_package (self, alias, package):
        """Register a package in the server loaded packages lists.

        @param alias: the package's alias
        @type alias: string
        @param package: the package itself
        @type package: advene.model.Package
        """
        # If we load a new file and only the template package was present,
        # then remove the template package
        if len(self.packages) <= 2 and 'new_pkg' in self.packages:
            self.unregister_package('new_pkg')
        self.packages[alias] = package
        self.aliases[package] = alias

    def unregister_package (self, alias):
        """Remove a package from the loaded packages lists.

        @param alias: the  package alias
        @type alias: string
        """
        # FIXME: check if the unregistered package was the current one
        p = self.packages[alias]
        del (self.aliases[p])
        del (self.packages[alias])
        if self.package == p:
            l=[ a for a in self.packages.keys() if a != 'advene' ]
            # There should be at least 1 key
            if l:
                self.activate_package(l[0])
            else:
                # We removed the last package. Create a new empty one.
                self.load_package()
                #self.activate_package(None)

    def activate_package(self, alias=None):
        """Activate the package.
        """
        if alias:
            self.package = self.packages[alias]
            self.current_alias = alias
        else:
            self.package = None
            self.current_alias = None
            return
        self.packages['advene']=self.package

        # Reset the cached duration
        duration = self.package.getMetaData (config.data.namespace, "duration")
        self.cached_duration = int(float(duration or 0))
        if not self.cached_duration:
            self.pending_duration_update = True

        mediafile = self.get_default_media()
        if mediafile != self.player.get_uri():
            # Update the player info
            self.set_media(mediafile)

        # Activate the default STBV
        default_stbv = self.package.getMetaData (config.data.namespace, "default_stbv")
        if default_stbv:
            view=helper.get_id( self.package.views, default_stbv )
            if view:
                self.activate_stbv(view)

        self.notify ("PackageActivate", package=self.package)

    def reset(self):
        """Reset all packages.
        """
        logger.error("FIXME: reset not implemented yet")
        #FIXME: remove all packages from self.packages
        # and
        # recreate a template package
        pass

    def save_session(self, name=None):
        """Save a session as a package list.

        Note: this does *not* save individual packages, only their
        list.
        """

        def tag(i):
            return ET.QName(config.data.namespace, i)

        root=ET.Element(tag('package-list'))
        for a, p in self.packages.items():
            if a == 'advene' or a == 'new_pkg':
                # Do not write the default or template package
                continue
            n=ET.SubElement(root, tag('package'), uri=p.uri, alias=a)
            if a == self.current_alias:
                n.attrib['default']=''

        f=open(name, 'w', encoding='utf-8')
        helper.indent(root)
        ET.ElementTree(root).write(f, encoding='unicode')
        f.close()
        return True

    def save_package (self, name=None, alias=None):
        """Save the package (current or specified)

        @param name: the URI of the package
        @type name: string
        """
        if alias is None:
            p=self.package
        else:
            p=self.packages[alias]

        if name is None:
            name=urllib.parse.unquote(p.uri)
        old_uri = p.uri

        # Handle tag_colors
        # Parse tag_colors attribute.
        self.package.setMetaData (config.data.namespace,
                                  "tag_colors",
                                  urllib.parse.urlencode(self.package._tag_colors))

        # Check if we know the stream duration. If so, save it as
        # package metadata
        d=self.cached_duration
        if d > 0:
            p.setMetaData (config.data.namespace,
                           "duration", str(d))

        if p == self.package:
            # Set if necessary the mediafile metadata
            if self.get_default_media() == "":
                uri = self.player.get_uri()
                if uri:
                    self.set_default_media(uri)

        p.save(name=name)
        p._modified = False

        self.notify ("PackageSave", package=p)
        if old_uri != name:
            # Reload the package with the new name
            logger.info(_("Package URI has changed. Reloading package with new URI."))
            self.load_package(uri=name)
            # FIXME: we keep here the old and the new package.
            # Maybe we could autoclose the old package

    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.

        self.package should be defined.

        @return: a boolean (~desactivation)
        """
        p=context.evaluateValue('package')
        # Check that all fragments are Millisecond fragments.
        l = [a.id for a in p.annotations
             if not isinstance (a.fragment, MillisecondFragment)]
        if l:
            self.package = None
            logger.error(_("Cannot load package: the following annotations do not have Millisecond fragments: %s"), ", ".join(l))
            return True

        # Cache common fieldnames for structured content
        for at in p.annotationTypes:
            if at.mimetype.endswith('/x-advene-structured'):
                at._fieldnames=helper.common_fieldnames(at.annotations)
            else:
                at._fieldnames=set()

        p.imagecache.clear ()
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            # Load the imagecache
            id_ = helper.mediafile2id (mediafile)
            p.imagecache.load (id_)
            # Populate imagecache for defined annotations
            for a in p.annotations:
                self.get_snapshot(annotation=a)

        # Handle 'auto-import' meta-attribute
        master_uri=p.getMetaData(config.data.namespace, 'auto-import')
        if master_uri:
            i=[ pk for pk in p.imports if pk.getUri(absolute=False) == master_uri ]
            if not i:
                logger.warn(_("Cannot handle master attribute, the package %s is not imported.") % master_uri)
            else:
                logger.info(_("Checking master package %s for not yet imported elements.") % master_uri)
                self.handle_auto_import(p, i[0].package)

        return True

    def handle_auto_import(self, p, i):
        """Ensure that all views, schemas, queries are imported from i in p.
        """
        for source in ('views', 'schemas', 'queries'):
            uris=[ e.uri for e in getattr(p, source) ]
            for e in getattr(i, source):
                if not e.uri in uris:
                    logger.info("Missing %s: importing it" % str(e))
                    helper.import_element(p, e, self, notify=False)
        return True

    def get_stbv_list(self):
        """Return the list of current dynamic views.
        """
        if self.package:
            return [ v
                     for v in self.package.views
                     if helper.get_view_type(v) == 'dynamic' ]
        else:
            return []

    def get_utbv_list(self):
        """Return the list of valid UTBV for the current package.

        Returns a list of tuples (title, url) for each UTBV in the
        current package that is appliable on the package.
        """
        res=[]
        if not self.package:
            return res

        url=self.get_default_url(root=True, alias='advene')

        # Add defaultview first if it exists
        if self.package.views.get_by_id('_index_view'):
            res.append( (_("Standard summary"), "%s/view/%s" % (url, '_index_view')) )

        defaultview=self.package.getMetaData(config.data.namespace,
                                             'default_utbv')
        if defaultview and self.package.views.get_by_id(defaultview):
            res.append( (_("Default view"), self.get_default_url(alias='advene')) )

        for utbv in self.package.views:
            if (utbv.matchFilter['class'] == 'package'
                and helper.get_view_type(utbv) == 'static'):
                res.append( (self.get_title(utbv), "%s/view/%s" % (url, utbv.id)) )
        return res

    def activate_stbv(self, view=None, force=False):
        """Activates a given STBV.

        If view is None, then reset the user STBV.  The force
        parameter is used to handle the ViewEditEnd case, where the
        view may already be active, but must be reloaded anyway since
        its contents changed.
        """
        if view == self.current_stbv and not force:
            return
        self.current_stbv=view
        if view is None:
            self.event_handler.clear_ruleset(type_='user')
            self.notify("ViewActivation", view=None, comment="Deactivate STBV")
            return

        parsed_views=[]

        rs=RuleSet()
        rs.from_xml(view.content.stream,
                    catalog=self.event_handler.catalog,
                    origin=view.uri)

        parsed_views.append(view)

        # Handle subviews
        subviews=rs.filter_subviews()
        while subviews:
            # Danger: possible infinite recursion.
            for s in subviews:
                for v in s.as_views(self.package):
                    if v in parsed_views:
                        # Already parsed view. In order to avoid an
                        # infinite loop, ignore it.
                        logger.warn(_("Infinite loop in STBV %(name)s: the %(imp)s view is invoked multiple times.") % { 'name': self.get_title(view),
                                                                                                                         'imp': self.get_title(v) })
                    else:
                        rs.from_xml(v.content.stream,
                                    catalog=self.event_handler.catalog,
                                    origin=v.uri)
                        parsed_views.append(v)
                subviews=rs.filter_subviews()

        self.event_handler.set_ruleset(rs, type_='user')
        for v in parsed_views:
            if v == view:
                # Avoid double notification of ViewActivation. We need
                # to keep it in parsed_views though, in order to
                # prevent recursion.
                continue
            self.notify("ViewActivation", view=v, comment="Activate subview of %s" % view.id)
        self.notify("ViewActivation", view=view, comment="Activate STBV")
        return

    def log (self, msg, level=None):
        """Add a new log message.

        Should be overriden by the application (GUI for instance)

        @param msg: the message
        @type msg: string
        """
        try:
            self.gui.log(msg, level)
        except AttributeError:
            print(str(msg))

    def message_log (self, context, parameters):
        """Event Handler for the message action.

        Essentialy a wrapper for the X{log} method.

        @param context: the action context
        @type context: TALContext
        @param parameters: the parameters (should have a 'message' one)
        @type parameters: dict
        """
        if 'message' in parameters:
            message=context.evaluateValue(parameters['message'])
        else:
            message="No message..."
        self.log(message)
        return True

    def on_exit (self, *p, **kw):
        """General exit callback."""
        if not self.cleanup_done:
            # Stop the event handler
            if config.data.debug:
                start=self._state
                end=self.event_handler.dump()
                import difflib
                diff=difflib.Differ()
                logger.debug("-----------")
                for l in diff.compare(start, end):
                    logger.debug(l)
                logger.debug("-----------")
            self.event_handler.reset_queue()
            self.event_handler.clear_state()
            self.event_handler.update_rulesets()

            # Save preferences
            config.data.save_preferences()

            # Cleanup the ZipPackage directories
            ZipPackage.cleanup()

            # Terminate the web server
            try:
                self.server.stop()
            except Exception:
                pass
            # closing tracers Threads puting exit_coding in queue
            for tr in self.tracers:
                tr.equeue.put(tr.exit_code)
                tr.join()
            # Terminate the video player
            try:
                self.player.exit()
            except:
                logger.error(_("Got exception when stopping player."), exc_info=True)
            self.cleanup_done = True
        return True

    def move_frame(self, number_of_frames=1):
        """Pseudo-frame-by-frame navigation.

        @param number_of_frames: the number of frames to advance (possibly negative).
        """
        p=self.player
        if p.status == p.PlayingStatus:
            self.update_status('pause')
        self.update_status("seek_relative", self.frame2time(number_of_frames), notify=False)
        return True

    def update_status (self, status=None, position=None, notify=True):
        """Update the player status.

        Wrapper for the player.update_status method, used to notify the
        AdveneEventHandler.

        @param status: the status (cf advene.core.mediacontrol.Player)
        @type status: string
        @param position: an optional position
        @type position: Position
        """
        if isinstance(position, Annotation):
            position = position.fragment.begin
        position_before=self.player.current_position_value
        logger.debug("update status: %s %s", status, position)
        if (status == 'seek' or status == 'start' or status == 'stop'):
            if position != position_before:
                self.reset_annotation_lists()
            if notify:
                # Bit of a hack... In a loop context, setting the
                # position is done with notify=False, so we do not
                # want to remove videotime_bookmarks
                self.videotime_bookmarks = []

            # It was defined in a rule, but this prevented the snapshot
            # to be taken *before* moving
            self.update_snapshot(position_before)
        try:
            if self.player.get_uri() or 'record' in self.player.player_capabilities:
                self.player.update_status(status, position)
                for p in self.slave_players:
                    p.update_status(status, position)
                # Update the destination screenshot
                self.update_snapshot(position)
        except Exception:
            # FIXME: we should catch more specific exceptions and
            # devise a better feedback than a simple print
            logger.error(_("Video player problem"), exc_info=True)
        en=self.status2eventname.get(status, None)
        if en and notify:
            self.notify (en,
                         position=position,
                         position_before=position_before,
                         immediate=True)
        return

    def position_update (self):
        """Updates the current_position_value.

        This method, regularly called, restarts the player in case of
        a communication failure.

        It updates the slider range if necessary.

        @return: the current position in ms
        @rtype: a long
        """
        try:
            self.player.position_update ()
        except:
            # The player is down. Restart it.
            logger.info("Restarting player...", exc_info=True)
            self.player_restarted += 1
            if self.player_restarted > 5:
                raise Exception (_("Unable to start the player."))
            self.restart_player ()

        return self.player.current_position_value

    def player_scrub(self, pos):
        """Scrub to a given position.
        """
        p=self.player
        if p.status == p.PauseStatus and 'frame-by-frame' in p.player_capabilities:
            self.update_status("seek", pos, notify=True)
        return False

    def player_delayed_scrub(self, pos):
        """Scrub to a given position.

        To avoid too fast scrubbing, we set a timeout. The actual
        scrubbing is done with the last value given when the timeout expires.
        """
        def do_scrub():
            if self.scrub_lastvalue is not None:
                # FIXME: there is a concurrency issue here.
                self.player_scrub(self.scrub_lastvalue)
                self.scrub_lastvalue = None
            return False

        p=self.player
        if p.status == p.PauseStatus and 'frame-by-frame' in p.player_capabilities:
            if self.scrub_lastvalue is None:
                # Not in a scrubbing state.
                GObject.timeout_add(250, do_scrub)
            self.scrub_lastvalue = pos

        return True

    def generate_sorted_lists (self, position):
        """Return two sorted lists and a list of active annotations valid for a given position.

        (i.e. all annotations beginning or ending after the
        position). The lists are sorted according to the begin and end
        position respectively.

        The elements of the begin/end lists are (annotation, begin,
        end). The elements of active_annotations are annotations.

        The update_display method only has to check the first element
        of each list. If there is a match, it should trigger the
        events and pop the element.

        If there is a seek operation, we should regenerate the lists.

        @param position: the current position
        @type position: int
        @return: a tuple of three lists containing triplets or simple annotations
        @rtype: tuple
        """
        # Substract 20ms to the current position, so that in case the
        # generate_sorted_lists is triggered due to selecting an
        # annotation, the annotation is put in future_begins and its
        # AnnotatioBegin gets correctly notified.
        position -= 20

        future_begins = []
        future_ends = []
        active = []

        for a in self.package.annotations:
            begin = a.fragment.begin
            end = a.fragment.end
            if begin >= position:
                future_begins.append( (a, begin, end) )
                future_ends.append( (a, begin, end) )
            elif end >= position:
                future_ends.append( (a, begin, end) )
                active.append(a)
        future_begins.sort(key=operator.itemgetter(1))
        future_ends.sort(key=operator.itemgetter(2))

        #logger.debug("Position: %s" % helper.format_time(position))
        #logger.debug("Begins: %s\nEnds: %s" % ([ a[0].id for a in future_begins[:4] ],
        #                                [ a[0].id for a in future_ends[:4] ]))
        return future_begins, future_ends, active

    def reset_annotation_lists (self):
        """Reset the future annotations lists."""
        self.future_begins = None
        self.future_ends = None
        self.active_annotations = []

    def update (self):
        """Update the information.

        This method is regularly called by the upper application (for
        instance a Gtk mainloop).

        Hence, it is a critical execution path and care should be
        taken with the code used here.

        @return: the current position value
        """
        # Process the event queue
        self.process_queue()

        p = self.player

        pos=self.position_update ()

        if pos < self.last_position or pos > self.last_position + 1000:
            # We did a seek compared to the last time (backward, or
            # more than 1s forward), so we invalidate the
            # future_begins and future_ends lists as well as the
            # active_annotations
            self.reset_annotation_lists()

        self.last_position = pos

        if self.videotime_bookmarks:
            t, a = self.videotime_bookmarks[0]
            while t and t <= pos:
                self.videotime_bookmarks.pop(0)
                a(self, pos)
                if self.videotime_bookmarks:
                    t, a = self.videotime_bookmarks[0]
                else:
                    t = 0

        if self.usertime_bookmarks:
            t, a = self.usertime_bookmarks[0]
            v=time.time()
            while t and t <= v:
                self.usertime_bookmarks.pop(0)
                a(self, v)
                if self.usertime_bookmarks:
                    t, a = self.usertime_bookmarks[0]
                else:
                    t = 0

        if self.future_begins is None or self.future_ends is None:
            self.future_begins, self.future_ends, self.active_annotations = self.generate_sorted_lists(pos)
            #logger.debug("New lists %s %s", [a.id for a in self.active_annotations], [t[0].id for t in self.future_begins ])

        if self.future_begins and p.is_playing():
            a, b, e = self.future_begins[0]
            #logger.debug("Future begin %s %d %d", a.id, b, pos)
            while b <= pos:
                # Ignore if we were after the annotation end
                self.future_begins.pop(0)
                if e > pos:
                    self.notify ("AnnotationBegin",
                                 annotation=a,
                                 immediate=True)
                    self.active_annotations.append(a)
                if self.future_begins:
                    a, b, e = self.future_begins[0]
                else:
                    break

        if self.future_ends and p.is_playing():
            a, b, e = self.future_ends[0]
            while e <= pos:
                try:
                    self.active_annotations.remove(a)
                except ValueError:
                    pass
                self.future_ends.pop(0)
                self.notify ("AnnotationEnd",
                             annotation=a,
                             immediate=True)
                if self.future_ends:
                    a, b, e = self.future_ends[0]
                else:
                    break

        if p.stream_duration > self.cached_duration + 2000:
            # Something wrong here. Can be a live stream, or a unknown
            # length movie.  The "+ 2000" is here to make sure that we
            # do not spend our time updating, since it could be a live
            # stream played/recorded.
            self.cached_duration=int(p.stream_duration)
            self.notify('DurationUpdate', duration=self.cached_duration)
        # Update the cached duration if necessary
        elif self.pending_duration_update and p.stream_duration > 0:
            self.cached_duration=int(p.stream_duration)
            self.notify('DurationUpdate', duration=self.cached_duration)
            self.pending_duration_update = False

        return pos

    def create_static_view(self, elements=None):
        """Create a static view from the given elements.
        """
        p=self.package
        ident=p._idgenerator.get_id(View)
        v=p.createView(
            ident=ident,
            author=config.data.userid,
            date=self.get_timestamp(),
            clazz='package',
            content_mimetype='text/html'
            )
        p.views.append(v)
        p._idgenerator.add(ident)
        if not elements:
            self.notify('ViewCreate', view=v, immediate=True)
            return v
        if isinstance(elements[0], Annotation):
            if len(elements) > 1:
                v.title=_("Comment on set of %d annotations") % len(elements)
            else:
                v.title=_("Comment on %s") % self.get_title(elements[0])
            data=[]
            for element in elements:
                ctx=self.build_context(element)
                data.append(_("""<h1>Comment on %(title)s</h1>
<span class="advene:annotation" advene:annotation="%(id)s" advene:presentation="link:snapshot"><a title="Click to play the movie in Advene" tal:attributes="href package/annotations/%(id)s/player_url" href="%(href)s"><img title="Click here to play" width="160" height="100" tal:attributes="src package/annotations/%(id)s/snapshot_url" src="%(imgurl)s" ></img></a></span>""") % {
                    'title': self.get_title(element),
                    'id': element.id,
                    'href': 'http://localhost:1234' + ctx.evaluateValue('here/player_url'),
                    'imgurl': 'http://localhost:1234' + ctx.evaluateValue('here/snapshot_url'),
                    })
            v.content.data="\n".join(data)
        elif isinstance(elements[0], AnnotationType):
            at_title=self.get_title(elements[0])
            v.title=_("List of %s annotations") % at_title
            # FIXME: the template should not be duplicated here, but
            # only in the HTML widget. Maybe add a new attribut
            # advene:rendering="TODO" to indicate to the editor that
            # it should insert the template?
            v.content.data="""<div tal:define="at package/annotationTypes/%(id)s">
                  <h1>List of <em tal:content="at/representation">%(title)s</em> annotations</h1>
                  <span class="advene:annotationtype" advene:annotationtype="%(id)s" advene:presentation="grid">
<div class="screenshot_container" style="text-align: center; float: left; width: 200; height: 170; font-size: 0.8em;" tal:repeat="a package/annotationTypes/%(id)s/annotations/sorted">
<a title="Play this annotation" tal:attributes="href a/player_url">
        <img class="screenshot" style="border:1px solid #FFCCCC; height:100px; width:160px;" alt="" tal:attributes="src a/snapshot_url" />
	<br />
	<strong tal:content="a/content/data">Nom</strong>
</a><br />
<span>(<span tal:content="a/fragment/formatted/begin">Debut</span> - <span tal:content="a/fragment/formatted/end">Fin</span>)</span>
<br />
</div></span>""" % { 'id': elements[0].id,
                     'title': at_title,
                     }
        self.notify('ViewCreate', view=v, immediate=True)
        return v

    def get_export_filters(self):
        exporter_package=Package(uri=config.data.advenefile('exporters.xml'))
        return sorted( ( v
                         for v in exporter_package.views
                         if v.id != 'index' ), key=lambda v: v.title )

    def apply_export_filter(self, element, filter, filename):
        """Apply the given export filename to the element and output the result to filename.
        """
        ctx=self.build_context(here=element)
        try:
            stream=open(filename, 'wb')
        except Exception:
            logger.error(_("Cannot export to %(filename)s"), exc_info=True)
            return True

        if filter.content.mimetype is None or filter.content.mimetype.startswith('text/'):
            compiler = simpleTAL.HTMLTemplateCompiler ()
            compiler.parseTemplate (filter.content.stream, 'utf-8')
            if filter.content.mimetype == 'text/plain':
                # Convert HTML entities to their values
                output = io.BytesIO()
            else:
                output = stream
            try:
                compiler.getTemplate ().expand (context=ctx, outputFile=output, outputEncoding='utf-8')
            except simpleTALES.ContextContentException:
                logger.error(_("Error when exporting text template"), exc_info=True)
            if filter.content.mimetype == 'text/plain':
                stream.write(output.getvalue().replace(b'&lt;', b'<').replace(b'&gt;', b'>').replace(b'&amp;', b'&'))
        else:
            compiler = simpleTAL.XMLTemplateCompiler ()
            compiler.parseTemplate (filter.content.stream)
            try:
                compiler.getTemplate ().expand (context=ctx, outputFile=stream, outputEncoding='utf-8', suppressXMLDeclaration=True)
            except simpleTALES.ContextContentException:
                logger.error(_("Error when exporting XML template"), exc_info=True)
        stream.close()
        logger.info(_("Data exported to %s") % filename)
        return True

    def website_export(self, destination='/tmp/n', views=None, max_depth=3, progress_callback=None, video_url=None):
        exporter=WebsiteExporter(self, destination, views, max_depth, progress_callback, video_url)
        # FIXME
        exporter.website_export()
        return True

if __name__ == '__main__':
    cont = AdveneController()
    try:
        cont.self_loop()
    except Exception:
        logger.error("Got exception %s. Stopping services...", exc_info=True)
        cont.on_exit()
