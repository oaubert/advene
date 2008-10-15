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
"""
Advene controller
=================

This is the core of the Advene framework. It holds the various
components together (data model, webserver, GUI, event handler...),
and can be seen as a Facade design pattern for these components.

The X{AdveneEventHandler} is used by the application to handle events
notifications and actions triggering.
"""

import sys
import time
import os
import cgi
import socket
import re
import webbrowser
import urllib
import StringIO
import gobject
import shlex
import itertools
import operator
import tempfile

import advene.core.config as config

from gettext import gettext as _

import advene.core.plugin
from advene.core.mediacontrol import PlayerFactory
from advene.core.imagecache import ImageCache
import advene.core.idgenerator

from advene.rules.elements import RuleSet, RegisteredAction, SimpleQuery, Quicksearch
import advene.rules.ecaengine
import advene.rules.actions

from advene.model.cam.package import Package
from advene.model.cam.annotation import Annotation
from advene.model.cam.relation import Relation
from advene.model.cam.tag import AnnotationType, RelationType
from advene.model.consts import DC_NS_PREFIX, ADVENE_NS_PREFIX
import advene.util.session
from advene.model.cam.view import View
from advene.model.cam.query import Query
from advene.util.defaultdict import DefaultDict

from advene.model.tales import AdveneContext, AdveneTalesException

import advene.util.helper as helper
#import advene.util.importer
import xml.etree.ElementTree as ET
#import advene.rules.importer

if config.data.webserver['mode']:
    from advene.server.webcherry import AdveneWebServer

import threading
gobject.threads_init()

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
      - L{imagecache} : the associated imagecache (dictionary indexed by Media id)
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
        # Reverse mapping indexed by package
        self.aliases = {}
        self.current_alias = None

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

        self.restricted_annotation_type=None
        self.restricted_annotations=None
        self.restricted_rule=None

        # Useful for debug in the evaluator window
        self.config=config.data

        # STBV
        self.current_stbv = None

        self.package = None

        self.playerfactory=PlayerFactory()
        self.player = self.playerfactory.get_player()
        self.player.get_default_media = self.get_current_mediafile
        self.player_restarted = 0

        # Some player can define a cleanup() method
        try:
            self.player.cleanup()
        except AttributeError:
            pass

        # Event handler initialization
        self.event_handler = advene.rules.ecaengine.ECAEngine (controller=self)
        self.modifying_events = self.event_handler.catalog.modifying_events
        self.event_queue = []

        # Load default actions
        advene.rules.actions.register(self)

        # Used in update_status to emit appropriate notifications
        self.status2eventname = {
            'pause':  'PlayerPause',
            'resume': 'PlayerResume',
            'start':  'PlayerStart',
            'stop':   'PlayerStop',
            'set':    'PlayerSet',
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
        if self.package is not None and hasattr(self.package, 'cached_duration'):
            return self.package.cached_duration
        else:
            return 0

    def set_cached_duration(self, value):
        if self.package is not None:
            self.package.cached_duration = long(value)

    cached_duration = property(fget=get_cached_duration,
                               fset=set_cached_duration,
                               doc="Cached duration for the current package")

    def self_loop(self):
        """Autonomous gobject loop for GUI-less controller.
        """
        self.mainloop = gobject.MainLoop()

        def update_wrapper():
            """Wrapper for the application update.

            This is necessary, since update() returns a position, that
            may be 0, thus interpreted as False by the loop handler if
            we directly invoke it.
            """
            self.update()
            return True

        gobject.timeout_add (100, update_wrapper)
        self.notify ("ApplicationStart")
        self.mainloop.run ()
        self.notify ("ApplicationEnd")

    def load_plugins(self, directory, prefix="advene_plugins"):
        """Load the plugins from the given directory.
        """
        #print "Loading plugins from ", directory
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
                    self.log("Could not register " + p.name)
                else:
                    self.log("Registering " + p.name)
            except AttributeError, e:
                print "AttributeError in", p.name, ":", str(e)
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
            #print "Scheduling %s" % method
            #import traceback
            #traceback.print_stack()
            #print "Process action: %s" % str(method), str(args), str(kw)
            try:
                method(*args, **kw)
            except Exception, e:
                import traceback
                s=StringIO.StringIO()
                traceback.print_exc (file = s)
                self.queue_action(self.log, _("Exception (traceback in console):") + str(e))
                print str(e)
                print s.getvalue()

        return True

    def register_gui(self, gui):
        """Register the GUI for the controller.
        """
        self.gui=gui

    def register_view(self, view):
        """Register a view.
        """
        if self.gui:
            self.gui.register_view(view)
        else:
            self.log(_("No available GUI"))

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
            self.log(_("No available event handler"))

    def register_viewclass(self, viewclass, name=None):
        """Register an adhoc view.
        """
        if self.gui:
            self.gui.register_viewclass(viewclass, name)
        else:
            self.log(_("No available gui"))

    def register_importer(self, imp):
        """Register an importer.
        """
        advene.util.importer.register(imp)

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
            self.restricted_annotations=sorted(annotations, key=lambda a: a.begin)

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
                    l=[(an, an.begin, an.end)
                       for an in self.restricted_annotations
                       if an.begin > a.end ]
                else:
                    l=[an
                       for an in self.future_begins
                       if an[0].type == t ]
                if l and l[0][1] > a.end:
                    self.queue_action(self.update_status, 'set', l[0][1])
                else:
                    # No next annotation. Return to the start
                    if self.restricted_annotations:
                        l=self.restricted_annotations
                    else:
                        l=[ a.begin for a in at.annotations ]
                        l.sort()
                    self.queue_action(self.update_status, "set", position=l[0])
            return True

        if at is not None:
            # New annotation-type restriction
            self.restricted_rule=self.event_handler.internal_rule(event="AnnotationEnd",
                                                                  method=restricted_play)
            p=self.player
            if p.status == p.PauseStatus or p.status == p.PlayingStatus:
                if [ a for a in self.active_annotations if a.type == at ]:
                    # We are in an annotation of the right type. Do
                    # not move the player, just play from here.
                    pass
                self.update_status("resume")
            else:
                l=[ a.begin for a in at.annotations ]
                if l:
                    l.sort()
                    self.update_status("start", position=l[0])

        self.notify('RestrictType', annotationtype=at)
        return True

    def search_string(self, searched=None, source=None, case_sensitive=False):
        """Search a string in the given source (TALES expression).

        A special source value is 'tags', which will then return the
        elements that are tagged with the searched string.

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

        if source is None:
            source=p.all.annotations
        elif source == 'tags':
            source=p.all.user_tags
            if case_sensitive:
                data_func=lambda e: e.title
            else:
                data_func=lambda e: normalize_case(e.title)
        else:
            c=self.build_context()
            source=c.evaluate(source)

        try:
            words=[ unicode(w, 'utf8') for w in shlex.split(searched.encode('utf8')) ]
        except ValueError:
            # Unbalanced quote. Just do a split along whitespace, the
            # user may be looking for a string with a quote and not
            # know it should be escaped.
            words=searched.split()

        mandatory=[ w[1:] for w in words if w.startswith('+') ]
        exceptions=[ w[1:] for w in words if w.startswith('-') ]
        normal=[ w for w in words if not w.startswith('+') and not w.startswith('-') ]

        for w in mandatory:
            w=normalize_case(w)
            source=[ e for e in source if w in data_func(e) ]
        for w in exceptions:
            w=normalize_case(w)
            source=[ e for e in source if w not in data_func(e) ]
        if not normal:
            # No "normal" search terms. Return the result.
            return source
        normal=[ normalize_case(w) for w in normal ]
        res=[]
        for e in source:
            data=data_func(e)
            for w in normal:
                if w in data:
                    res.append(e)
                    break
        return res

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
                source=context.evaluate(expr)
                context=self.build_context(here=source)

        result=None
        if query.content.mimetype == 'application/x-advene-simplequery':
            qexpr=SimpleQuery()
            # FIXME: content.model is not a DOMelement anymore!!
            qexpr.from_dom(query.content.model)
            result=qexpr.execute(context=context)
        elif query.content.mimetype == 'application/x-advene-quicksearch':
            # Parse quicksearch query
            qexpr=Quicksearch(controller=self)
            # FIXME: content.model is not a DOMelement anymore!!
            qexpr.from_dom(query.content.model)
            if expr is not None:
                # Override the source... Is it a good idea ?
                qexpr.source=expr
            result=qexpr.execute(context=context)
        else:
            raise Exception("Unsupported query type for %s" % query.id)
        return result, qexpr

    def build_context(self, here=None, alias=None, baseurl=None):
        """Build a context object with additional information.
        """
        if baseurl is None:
            baseurl=self.get_default_url(root=True, alias=alias)
        if here is None:
            here=self.package
        if self.current_media:
            ic=self.package.imagecache[self.current_media.id]
        else:
            ic=None
        c=AdveneContext(here,
                        options={
                u'package_url': baseurl,
                u'snapshot': ic,
                u'namespace_prefix': config.data.namespace_prefix,
                u'config': config.data.web,
                u'aliases': self.aliases,
                u'controller': self,
                })
        c.addGlobal(u'package', self.package)
        c.addGlobal(u'packages', self.packages)
        c.addGlobal(u'player', self.player)
        for name, method in config.data.global_methods.iteritems():
            c.addMethod(name, method)
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
        self.log(_("Cannot start the webserver\nThe following processes seem to use the %(port)s port: %(processes)s") % { 'port': pat,
                                                                                                                           'processes':  processes})

    def init(self, args=None):
        """Initialize the controller.
        """
        if args is None:
            args=[]

        try:
            self.player_plugins=self.load_plugins(os.path.join(os.path.dirname(advene.__file__), 'player'),
                                                  prefix="advene_player_plugins")
        except OSError, e:
            print "Error while loading player plugins", str(e).encode('utf-8')
            pass

        try:
            self.user_plugins=self.load_plugins(config.data.advenefile('plugins', 'settings'),
                                                prefix="advene_user_plugins")
        except OSError:
            pass

        try:
            self.app_plugins=self.load_plugins(os.path.join(os.path.dirname(advene.__file__), 'plugins'),
                                               prefix="advene_app_plugins")
        except OSError:
            pass

        # Read the default rules
        try:
            self.event_handler.read_ruleset_from_file(config.data.advenefile('default_rules.xml'),
                                                      type_='default', priority=100)
        except IOError, e:
            self.log(_("Cannot read default ruleset %(file)s: %(error)s") % {
                    'error': unicode(e),
                    'file': config.data.advenefile('default_rules.xml') })
            

        self.event_handler.internal_rule (event="PackageLoad",
                                          method=self.manage_package_load)

        if config.data.webserver['mode']:
            try:
                self.server = AdveneWebServer(controller=self, port=config.data.webserver['port'])
                serverthread = threading.Thread (target=self.server.start)
                serverthread.setName("Advene webserver")
                serverthread.start ()
            except socket.error:
                if config.data.os != 'win32':
                    self.busy_port_info()
                self.log(_("Deactivating web server"))
        media=None
        # Arguments handling
        for uri in args:
            if '=' in uri:
                # alias=uri syntax
                alias, uri = uri.split('=', 2)
                alias = re.sub('[^a-zA-Z0-9_]', '_', alias)
                try:
                    self.load_package (uri=uri, alias=alias)
                    self.log(_("Loaded %(uri)s as %(alias)s") % {'uri': uri, 'alias': alias})
                except Exception, e:
                    self.log(_("Cannot load package from file %(uri)s: %(error)s") % {
                            'uri': uri,
                            'error': unicode(e)})
            else:
                name, ext = os.path.splitext(uri)
                if ext.lower() in ('.xml', '.azp', '.apl', '.czp'):
                    alias = re.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))
                    try:
                        self.load_package (uri=uri, alias=alias)
                        self.log(_("Loaded %(uri)s as %(alias)s") % {
                                'uri': uri, 'alias':  alias})
                    except Exception, e:
                        self.log(_("Cannot load package from file %(uri)s: %(error)s") % {
                                'uri': uri,
                                'error': unicode(e)})
                else:
                    # Try to load the file as a video file
                    if ('dvd' in name
                        or ext.lower() in config.data.video_extensions):
                        media = uri

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

        return True

    def create_position (self, value=0, key=None, origin=None):
        """Create a new player-specific position.
        """
        if key is None:
            key=self.player.MediaTime
        if origin is None:
            origin=self.player.AbsolutePosition
        return self.player.create_position(value=value, key=key, origin=origin)

    def notify (self, event_name, *param, **kw):
        """Notify the occurence of an event.

        This method will trigger the corresponding actions. If the
        named parameter immediate=True is present, then execute the
        actions in the same thread of execution. Else, the actions
        will be triggered through queue_action in the application
        mainloop (main thread).
        """
        if False:
            print "Notify %s (%s): %s" % (
                event_name,
                helper.format_time(self.player.current_position_value),
                str(kw))

        # Set the package._modified state
        # This does not really belong here, but it is the more convenient and
        # maybe more effective way to implement it
        if event_name in self.modifying_events:
            # Find the element's package
            # Kind of hackish... This information should be clearly available somewhere
            el_name=event_name.lower().replace('create','').replace('editend','').replace('delete', '')
            el=kw[el_name]
            p=el.owner
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
        except Exception, e:
            self.log(_("Cannot get audio volume: %s") % unicode(e))
            v=0
        return v

    def update_snapshot (self, position=None):
        """Event handler used to take a snapshot for the given position.

        !!! For the moment, the position parameter is ignored, and the
            snapshot is taken for the current position.

        @return: a boolean (~desactivation)
        """
        if self.current_media:
            ic=self.package.imagecache[self.current_media.id]
        else:
            ic=None
        if (config.data.player['snapshot']
            and ic and not ic.is_initialized (position)):
            # FIXME: only 0-relative position for the moment
            # print "Update snapshot for %d" % position
            try:
                i = self.player.snapshot (self.player.relative_position)
            except self.player.InternalException, e:
                print "Exception in snapshot: %s" % e
                return True
            if ic is not None and i is not None and i.height != 0:
                ic[position] = helper.snapshot2png (i)
        else:
            # FIXME: do something useful (warning) ?
            pass
        return True

    def open_url(self, url):
        """Open an URL in the most appropriate browser.

        Cf http://cweiske.de/howto/launch/ for details.
        """
        if self.gui and self.gui.open_url_embedded(url):
            return True
        if config.data.os == 'win32' or config.data.os == 'darwin':
            # webbrowser is not broken on win32 or Mac OS X
            webbrowser.get().open(url)
            return True
        # webbrowser is broken on UNIX/Linux : if the browser
        # does not exist, it does not always launch it in the
        # background, so it can freeze the GUI.
        web_browser = os.getenv("BROWSER", None)
        if web_browser == None:
            # Try to guess if we are running a Gnome/KDE desktop
            if os.environ.has_key('KDE_FULL_SESSION'):
                web_browser = 'kfmclient exec'
            elif os.environ.has_key('GNOME_DESKTOP_SESSION_ID'):
                web_browser = 'gnome-open'
            else:
                term_command = os.getenv("TERMCMD", "xterm")
                browser_list = ('xdg-open', "firefox", "firebird", "epiphany", "galeon", "mozilla", "opera", "konqueror", "netscape", "dillo", ("links", "%s -e links" % term_command), ("w3m", "%s -e w3m" % term_command), ("lynx", "%s -e lynx" % term_command), "amaya", "gnome-open")
                breaked = 0
                for browser in browser_list:
                    if type(browser) == str:
                        browser_file = browser_cmd = browser
                    elif type(browser) == tuple and len(browser) == 2:
                        browser_file = browser[0]
                        browser_cmd = browser[1]
                    else:
                        continue

                    for directory in os.getenv("PATH", "").split(os.path.pathsep):
                        if os.path.isdir(directory):
                            browser_path = os.path.join(directory, browser_file)
                            if os.path.isfile(browser_path) and os.access(browser_path, os.X_OK):
                                web_browser = browser_cmd
                                breaked = 1
                                break
                    if breaked:
                        break
        if web_browser != None:
            os.system("%s \"%s\" &" % (web_browser, url))

        return True

    def get_url_for_alias (self, alias):
        """Return the URL for the given alias.
        """
        # FIXME: it should be more integrated with the webserver, in
        # order to use the same BaseURL as the calling context.
        if self.server:
            return urllib.basejoin(self.server.urlbase, "/packages/" + alias)
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
            return unicode(url)
        defaultview=self.package.meta.get( '/'.join( (config.data.namespace, 'default_utbv') ) )
        if defaultview:
            url=u"%s/view/%s" % (url, defaultview)
        return url

    def get_title(self, element, representation=None):
        """Return the title for the given element.
        """
        def cleanup(s):
            i=s.find('\n')
            if i > 0:
                return s[:i]
            else:
                return s

        if element is None:
            return _("None")
        if isinstance(element, unicode) or isinstance(element, str):
            return element
        if isinstance(element, Annotation) or isinstance(element, Relation):
            if representation:
                c=self.build_context(here=element)
                try:
                    r=c.evaluate(representation)
                except AdveneTalesException:
                    r=element.content.data
                if not r:
                    r=element.id
                return cleanup(r)

            representation=element.type.representation
            if not representation or re.match('^\s+', representation):
                r=element.content.data
                if element.content.mimetype == 'image/svg+xml':
                    return "SVG graphics"
                if not r:
                    r=element.id
                return cleanup(r)
            else:
                c=self.build_context(here=element)
                try:
                    r=c.evaluate(representation)
                except (AdveneTalesException, KeyError, AttributeError), e:
                    print "Exception in get_title for ", element.id, '(', representation, '):', unicode(e).encode('utf-8')
                    r=element.content.data.splitlines()[0]
                if not r:
                    r=element.id
                return cleanup(r)
        if isinstance(element, RelationType):
            if config.data.os == 'win32':
                arrow=u'->'
            else:
                arrow=u'\u2192'
            return arrow + unicode(cleanup(element.title))
        if hasattr(element, 'title') and element.title:
            return unicode(cleanup(element.title))
        if hasattr(element, 'id') and element.id:
            return unicode(element.id)
        return cleanup(unicode(element))

    @property
    def max_duration(self):
        """Maximum duration.
        """
        return max( m.duration for m in self.package.all.medias )

    @property
    def current_media(self):
        """Current media instance.
        """
        try:
            return self.package._current_media
        except AttributeError:
            return None
        
    def get_current_mediafile(self, package=None):
        """Return the current mediafile for the given package.

        FIXME: this should be removed in a multiple-media context
        """
        if package is None:
            package=self.package

        media=self.current_media
        if media is None:
            return ''
        mediafile=media.url
        if not mediafile:
            return ''

        m=self.dvd_regexp.match(mediafile)
        if m:
            title,chapter=m.group(1, 2)
            mediafile=self.player.dvd_uri(title, chapter)
        elif mediafile.startswith('http:'):
            # FIXME: check for the existence of the file?
            pass
        elif not os.path.exists(mediafile.encode(sys.getfilesystemencoding(), 'ignore')):
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
                    d=urllib.url2pathname(d)
                    d=os.path.dirname(d)
                if '~' in d:
                    # Expand userdir
                    d=os.path.expanduser(d)

                n=os.path.join(d, name)
                # FIXME: if d is a URL, use appropriate method (urllib.??)
                if os.path.exists(n.encode(sys.getfilesystemencoding(), 'ignore')):
                    mediafile=n
                    self.log(_("Found matching video file in moviepath: %s") % n)
                    break
        return mediafile

    def get_defined_tags(self, p=None):
        """Return the set of existing tags.
        """
        if p is None:
            p=self.package
        return list(p.all.tags)

    def set_mediafile(self, uri=None):
        """Set the current mediafile in the video player.
        """
        p=self.player
        if isinstance(uri, unicode):
            uri=uri.encode('utf8')
        if p.status == p.PlayingStatus or p.status == p.PauseStatus:
            p.stop(0)
        p.playlist_clear()
        if uri is not None:
            p.playlist_add_item (uri)
        self.notify("MediaChange", uri=uri)

    def set_default_media (self, uri, package=None):
        """Set the default media for the package.

        FIXME: cannot work in a multi-media context
        """
        if package is None:
            package=self.package
        m=self.dvd_regexp.match(uri)
        if m:
            title,chapter=m.group(1,2)
            uri="dvd@%s:%s" % (title, chapter)
        uri=unicode(uri).encode('utf8')
        if package.own.medias:
            # There is 1 defined media, overwrite its url
            media=package.own.medias[0]
            media.url=uri
        else:
            # FIXME: possibility of id clash here
            media=package.create_media('m1', uri)
        if m:
            uri=self.player.dvd_uri(title, chapter)
        self.set_mediafile(uri)
        # Reset the imagecache
        package.imagecache[media.id]=ImageCache()
        if uri:
            self.package.imagecache[media.id].load (helper.mediafile2id (uri))

    def delete_element (self, el, immediate_notify=False):
        """Delete an element from its package.

        Take care of all dependencies (for instance, annotations which
        have relations.
        
        FIXME: to rewrite completely.
        FIXMEFIXME: a toolkit should be provided by the model for this
        """
        print "FIXME: element suppression is not implemented"
        self.log("FIXME: element suppression is not implemented")
        return True

    def transmute_annotation(self, annotation, annotationType, move=False, position=None, notify=True):
        """Transmute an annotation to a new type.

        If delete is True, then delete the source annotation.

        If position is not None, then set the new annotation begin to position.
        """
        if annotation.type == annotationType:
            # Transmuting to the same type.
            if position is None:
                # Do not just duplicate the annotation
                return None
            elif move:
                # If move, then we can simply move the annotation
                d=annotation.duration
                annotation.begin=position
                annotation.end=position+d
                if notify:
                    self.notify("AnnotationEditEnd", annotation=annotation, comment="Transmute annotation")
                    self.notify('ElementEditCancel', element=annotation)
                return annotation
        if move:
            an = annotation
            an.type = annotationType
        else:
            # We want to make a copy. Create a new annotation
            ident=self.package._idgenerator.get_id(Annotation)
            an = self.package.create_annotation(id=ident,
                                                media=annotation.media,
                                                begin=annotation.begin,
                                                end=annotation.end,
                                                mimetype='FIXME',
                                                type = annotationType)

        if position is not None:
            # Change the position
            d=annotation.duration
            an.begin=position
            an.end=position+d
            
        # Check if types are compatible.
        # FIXME: we need a generic type conversion framework here
        an.content.data=annotation.content.data

        if notify:
            if move:
                self.notify('AnnotationEditEnd', annotation=an, comment="Transmute annotation")
            else:
                self.notify("AnnotationCreate", annotation=an, comment="Transmute annotation")
        return an

    def duplicate_annotation(self, annotation):
        """Duplicate an annotation.
        """
        ident=self.package._idgenerator.get_id(Annotation)
        an = self.package.create_annotation(id=ident,
                                            media=annotation.media,
                                            begin=annotation.end,
                                            end=annotation.end + annotation.duration,
                                            mimetype='FIXME',
                                            type=annotation.type)
        if an.end > annotation.media.duration:
            an.end = annotation.media.duration
        an.content.data=annotation.content.data
        self.notify("AnnotationCreate", annotation=an, comment="Duplicate annotation")
        return an

    def split_annotation(self, annotation, position):
        """Split an annotation at the given position
        """
        if (position <= annotation.begin
            or position >= annotation.end):
            self.log(_("Cannot split the annotation: the given position is outside."))
            return annotation

        # Create the new one
        ident=self.package._idgenerator.get_id(Annotation)
        an = self.package.create_annotation(ident=ident,
                                            media=annotation.media,
                                            type=annotation.type,
                                            begin=position,
                                            end=annotation.end)
        an.content.data=annotation.content.data

        # Shorten the first one.
        annotation.end = position

        self.notify("AnnotationEditEnd", annotation=annotation, comment="Duplicate annotation")
        self.notify("AnnotationCreate", annotation=an, comment="Duplicate annotation")
        return an

    def merge_annotations(self, s, d, extend_bounds=False):
        """Merge annotation s into annotation d.
        """
        batch_id=object()
        self.notify('ElementEditBegin', element=d, immediate=True)
        if extend_bounds:
            # Extend the annotation bounds (mostly used for same-type
            # annotations)
            begin=min(s.begin, d.begin)
            end=max(s.end, d.end)
            d.begin=begin
            d.end=end
        # Merging data
        # FIXME: handle differing mimetypes
        d.content.data=d.content.data + '\n' + s.content.data

        self.notify("AnnotationMerge", annotation=d,comment="Merge annotations", batch=batch_id)
        self.delete_element(s, batch_id=batch_id)
        self.notify("AnnotationEditEnd", annotation=d, comment="Merge annotations", batch=batch_id)
        self.notify('ElementEditCancel', element=d)
        return d

    def select_player(self, p):
        """Activate the given player.
        """
        # Stop the current player.
        self.player.stop(0)
        self.player.exit()
        # Start the new one
        self.player=p()
        if not 'record' in p.player_capabilities:
            # Store the selected player if it is not a recorder.
            config.data.player['plugin']=p.player_id
        self.notify('PlayerChange', player=p)
        mediafile = self.get_current_mediafile()
        if mediafile != "":
            self.set_media(mediafile)
        
    def restart_player (self):
        """Restart the media player."""
        self.player.restart_player ()
        mediafile = self.get_current_mediafile()
        if mediafile:
            self.set_mediafile(mediafile)
        self.notify('PlayerChange', player=p)

    def get_element_color(self, element):
        """Return the color for the given element.

        Return None if no color is defined, else return a 
        string representation of the color (color name, or #RRGGBB value).

        If the element is a tag, use its 'color' property. 

        If the element has any associated user tag with a
        'element_color' property or a 'color_property' that evaluates
        to non-None, then use the result.

        If the element is an annotation or a relation, try to use the
        'element_color' property of the element type. If it is None or
        evaluates to None, then try to use the 'color' property of the
        element type.
        """
        # First try the 'color' property from the element itself.
        color=None
        try:
            col=element.color
            if col is not None:
                c=self.build_context(here=element)
                try:
                    color=c.evaluate(col)
                except Exception:
                    color=None
        except AttributeError:
            pass

        if not color and hasattr(element, 'type'):
            # Not found in element. Try element_color from the container.
            col=element.type.element_color
            if col:
                c=self.build_context(here=element)
                try:
                    color=c.evaluate(col)
                except Exception:
                    color=None
            if not color:
                # Really not found. So use the container color.
                color=self.get_element_color(element.type)
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
            uri=tempfile.mkstemp(suffix='.czp')[1]
            self.package = Package(url=uri,
                                   create=True)
            alias='new_pkg'
            self.package.creator = config.data.userid
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
                    d=node.attrib.has_key('default')
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
            t=time.time()
            p = Package(url=uri)
            dur=time.time()-t
            self.log("Loaded package in %f seconds" % dur)
            # FIXME: some sanity checks about imported packages ?
            self.package=p

        # Store the current media instance.
        self.package._current_media=None

        if alias is None:
            # Autogenerate the alias
            if uri:
                alias, ext = os.path.splitext(os.path.basename(uri))
            else:
                alias = 'new_pkg'

        # Replace forbidden characters. The GUI is responsible for
        # letting the user specify a valid alias.
        alias = re.sub('[^a-zA-Z0-9_]', '_', alias)

        self.package.imagecache={}
        # Instanciate imagecaches for all medias
        for m in self.package.all.medias:
            self.package.imagecache[m.id]=ImageCache()

        self.package._idgenerator = advene.core.idgenerator.Generator(self.package)
        self.package._modified = False

        # State dictionary
        self.package.state=DefaultDict(default=0)

        # Initialize the color palette for the package
        # Remove already used colors
        l=list(config.data.color_palette)
        for at in self.package.all.annotation_types:
            try:
                l.remove(at.color)
            except ValueError:
                pass
        if not l:
            # All colors were used.
            l=list(config.data.color_palette)
        self.package._color_palette=helper.CircularList(l)

        duration = self.package.meta.get("/".join((config.data.namespace, "duration")))
        if duration is not None:
            try:
                v=long(float(duration))
            except ValueError:
                v=0
            self.cached_duration = v
        elif len(self.package.all.annotations):
            self.cached_duration = max(a.end for a in self.package.all.annotations)
        else:
            self.cached_duration = 30000
        
        self.register_package(alias, self.package)

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
        if len(self.packages) <= 2 and 'new_pkg' in self.packages.keys():
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

        # Define the package as root package for the model layer
        advene.util.session.session.package=self.package
        advene.util.session.session.user=config.data.userid

        mediafile = self.get_current_mediafile()
        if mediafile:
            if self.player.is_active():
                if mediafile not in self.player.playlist_get_list ():
                    # Update the player playlist
                    self.set_mediafile(mediafile)
        else:
            self.set_mediafile(None)

        # Activate the default STBV
        default_stbv = self.package.meta.get(ADVENE_NS_PREFIX + "default_stbv", None)
        if default_stbv:
            view=self.package.get_element(default_stbv)
            if view and helper.get_view_type(view) == 'dynamic':
                self.activate_stbv(view)
        self.notify ("PackageActivate", package=self.package)

    def save_session(self, name=None):
        """Save a session as a package list.

        Note: this does *not* save individual packages, only their
        list.
        """

        def tag(i):
            return ET.QName(config.data.namespace, i)

        root=ET.Element(tag('package-list'))
        for a, p in self.packages.iteritems():
            if a == 'advene' or a == 'new_pkg':
                # Do not write the default or template package
                continue
            n=ET.SubElement(root, tag('package'), uri=p.uri, alias=a)
            if a == self.current_alias:
                n.attrib['default']=''

        f=open(name, 'w')
        helper.indent(root)
        ET.ElementTree(root).write(f, encoding='utf-8')
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
            name=p.url
        old_url = p.url

        p.save_as(name)
        p._modified = False

        self.notify ("PackageSave", package=p)
        if old_url != name:
            # Reload the package with the new name
            self.log(_("Package URL has changed. Reloading package with new URL."))
            self.load_package(uri=name)
            # FIXME: we keep here the old and the new package.
            # Maybe we could autoclose the old package

    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.

        self.package should be defined.

        @return: a boolean (~desactivation)
        """
        p=context.evaluate('package')

        # Cache common fieldnames for structured content
        for at in p.all.annotation_types:
            if at.mimetype.endswith('/x-advene-structured'):
                at.meta[config.data.transientns+'fieldnames']=helper.common_fieldnames(at.annotations)
            else:
                at.meta[config.data.transientns+'fieldnames']=[]

        for m in p.all.medias:
            ic=self.package.imagecache[m.id]
            ic.clear()

            # Load the imagecache
            ic.load (helper.mediafile2id (m.url))

            # Populate the missing keys
            for a in p.all.iter_annotations(media=m):
                ic.init_value (a.begin)
                ic.init_value (a.end)

        return True

    @property
    def stbv_list(self):
        """List of current dynamic views.
        """
        if self.package:
            return [ v
                     for v in self.package.all.views
                     if helper.get_view_type(v) == 'dynamic' ]
        else:
            return []

    @property
    def utbv_list(self):
        """Return the list of valid UTBV for the current package.

        Returns a list of tuples (title, url) for each UTBV in the
        current package that is appliable on the package.
        """
        res=[]
        if not self.package:
            return res

        url=self.get_default_url(root=True, alias='advene')

        # Add defaultview first if it exists
        if self.package.get_element('_index_view'):
            res.append( (_("Standard summary"), "%s/view/%s" % (url, '_index_view')) )

        defaultview=self.package.meta.get( ADVENE_NS_PREFIX + 'default_utbv',
                                           None)
        if defaultview and self.package.get_element(defaultview):
            res.append( (_("Default view"), self.get_default_url(alias='advene')) )

        for utbv in self.package.all.views:
            #FIXME: should return only toplevel views.
            if helper.get_view_type(utbv) == 'static':
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
        rs.from_xml(view.content.get_as_file(),
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
                        self.log(_("Infinite loop in STBV %(name)s: the %(imp)s view is invoked multiple times.") % { 'name': self.get_title(view),
                                                                                                                      'imp': self.get_title(v) })
                    else:
                        rs.from_xml(v.content.get_as_file(),
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
        if self.gui:
            self.gui.log(msg, level)
            if config.data.preferences['log-to-terminal']:
                print unicode(msg).encode('utf-8')
        else:
            # FIXME: handle the level parameter
            print unicode(msg).encode('utf-8')

    def message_log (self, context, parameters):
        """Event Handler for the message action.

        Essentialy a wrapper for the X{log} method.

        @param context: the action context
        @type context: TALContext
        @param parameters: the parameters (should have a 'message' one)
        @type parameters: dict
        """
        if parameters.has_key('message'):
            message=context.evaluate(parameters['message'])
        else:
            message="No message..."
        self.log (message)
        return True

    def on_exit (self, *p, **kw):
        """General exit callback."""
        if not self.cleanup_done:
            # Stop the event handler
            self.event_handler.reset_queue()
            self.event_handler.clear_state()
            self.event_handler.update_rulesets()

            # Save preferences
            config.data.save_preferences()

            # Cleanup the temporary directories
            advene.util.session.cleanup()

            # Terminate the web server
            try:
                self.server.stop()
            except Exception:
                pass

            # Terminate the VLC server
            try:
                #print "Exiting vlc player"
                self.player.exit()
            except Exception, e:
                import traceback
                s=StringIO.StringIO()
                traceback.print_exc (file = s)
                self.log(_("Got exception %s when stopping player.") % str(e), s.getvalue())
            self.cleanup_done = True
        return True

    def move_frame(self, number_of_frames=1):
        """Pseudo-frame-by-frame navigation.

        @param number_of_frames: the number of frames to advance (possibly negative).
        """
        p=self.player
        if p.status == p.PlayingStatus:
            self.update_status('pause')
        elif p.status != p.PauseStatus:
            self.update_status('start')
            self.update_status('pause')
        self.move_position (int(1000 / 25.0 * number_of_frames), notify=False)
        return True

    def move_position (self, value, relative=True, notify=True):
        """Helper method : fast forward or rewind by value milliseconds.

        @param value: the offset in milliseconds
        @type value: int
        """
        if relative:
            self.update_status ("set", self.create_position (value=value,
                                                             key=self.player.MediaTime,
                                                             origin=self.player.RelativePosition),
                                notify=notify)
        else:
            self.update_status ("set", self.create_position (value=value,
                                                             key=self.player.MediaTime,
                                                             origin=self.player.AbsolutePosition),
                                notify=notify)

    def generate_sorted_lists (self, position):
        """Return two sorted lists valid for a given position.

        (i.e. all annotations beginning or ending after the
        position). The lists are sorted according to the begin and end
        position respectively.

        The elements of the list are (annotation, begin, end).

        The update_display method only has to check the first element
        of each list. If there is a match, it should trigger the
        events and pop the element.

        If there is a seek operation, we should regenerate the lists.

        @param position: the current position
        @type position: int
        @return: a tuple of two lists containing triplets
        @rtype: tuple
        """
        if self.current_media is None:
            return None, None
        
        l = [ (a, a.begin, a.end)
              for a in self.package.all.iter_annotations(media=self.current_media)
              if a.begin >= position or a.end >= position ]
        future_begins = list(l)
        future_ends = l
        future_begins.sort(key=operator.itemgetter(1))
        future_ends.sort(key=operator.itemgetter(2))

        #print "Position: %s" % helper.format_time(position)
        #print "Begins: %s\nEnds: %s" % ([ a[0].id for a in future_begins[:4] ],
        #                                [ a[0].id for a in future_ends[:4] ])
        return future_begins, future_ends

    def reset_annotation_lists (self):
        """Reset the future annotations lists."""
        #print "reset annotation lists"
        self.future_begins = None
        self.future_ends = None
        self.active_annotations = []

    def update_status (self, status=None, position=None, notify=True):
        """Update the player status.

        Wrapper for the player.update_status method, used to notify the
        AdveneEventHandler.

        @param status: the status (cf advene.core.mediacontrol.Player)
        @type status: string
        @param position: an optional position
        @type position: Position
        """
        position_before=self.player.current_position_value
        #print "update status:", status, position
        if status == 'set' or status == 'start' or status == 'stop':
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
            # if hasattr(position, 'value'):
            #     print "update_status %s %i" % (status, position.value)
            # else:
            #     print "update_status %s %s" % (status, position)
            if self.player.playlist_get_list():
                self.player.update_status (status, position)
                # Update the destination screenshot
                if hasattr(position, 'value'):
                    # It is a player.Position. Do a simple conversion
                    # (which will fail in many cases)
                    position=position.value
                self.update_snapshot(position)
        except Exception, e:
            # FIXME: we should catch more specific exceptions and
            # devise a better feedback than a simple print
            import traceback
            s=StringIO.StringIO()
            traceback.print_exc (file = s)
            self.log(_("Raised exception in update_status: %s") % str(e), s.getvalue())
        if self.status2eventname.has_key (status) and notify:
            self.notify (self.status2eventname[status],
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
        except self.player.InternalException:
            # The server is down. Restart it.
            print "Restarting player..."
            self.player_restarted += 1
            if self.player_restarted > 5:
                raise Exception (_("Unable to start the player."))
            self.restart_player ()

        return self.player.current_position_value

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

        pos=self.position_update ()

        if pos < self.last_position:
            # We did a seek compared to the last time, so we
            # invalidate the future_begins and future_ends lists
            # as well as the active_annotations
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
            self.future_begins, self.future_ends = self.generate_sorted_lists (pos)

        if self.future_begins and self.player.status == self.player.PlayingStatus:
            a, b, e = self.future_begins[0]
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

        if self.future_ends and self.player.status == self.player.PlayingStatus:
            a, b, e = self.future_ends[0]
            while e <= pos:
                #print "Comparing %d < %d for %s" % (e, pos, a.content.data)
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

        # Update the cached duration if necessary
        if self.current_media and self.current_media.duration <= 0 and self.player.stream_duration > 0:
            self.current_media.duration = long(self.player.stream_duration)

        return pos

    def create_event_history_package(self, fname=None):
        """Import the event history in a new package.
        """
        self.load_package(alias="Event history")
        self.import_event_history(fname, offset=0)
        return True

    def export_event_history(self, fname=None):
        """Export the current history to text file.
        """
        history = self.event_handler.event_history
        if fname is None:
            fname="event.evt"
        fname = os.path.join( config.data.path['settings'], fname )
        try:
            stream=open(fname, 'wb')
        except (OSError, IOError), e:
            self.log(_("Cannot export to %(fname)s: %(e)s") % locals())
            return True
        start=history[0]['timestamp']
        num=0
        events=ET.Element('events')
        for e in history:
            num=num+1
            try:
                begin=e['timestamp']-start
            except KeyError:
                stream.close()
                raise Exception("Begin is mandatory")
            end=begin+50
            if e.has_key('content'):
                content=e['content']+'\nposition='+str(e['movietime'])
            else:
                content='position='+str(e['movietime'])
            type=e['event_name']
            timestamp=e['timestamp']
            ET.SubElement(events, 'event', id='e'+str(num), begin=str(long(begin)), end=str(long(end)), type=type).text=content
        helper.indent(events)
        ET.ElementTree(events).write(stream, encoding='utf-8')
        stream.close()
        self.log(_("Data exported to %s") % fname)
        return True

    def import_event_history(self, fname=None, offset=0):
        """Import the event history in the current package.
        """
        if fname is None:
            i=advene.rules.importer.EventHistoryImporter(package=self.package)
            nbEv = i.process_file(self.event_handler.event_history)
        else:
            if not os.path.exists(fname):
                oldfname=fname
                fname = os.path.join(config.data.path['settings'],oldfname)
                print "%s not found, trying %s" % (oldfname,fname)
                if not os.path.exists(fname):
                    print "%s not found, giving up." % fname
                    return False
            imp = advene.util.importer.EventImporter(package=self.package)
            nbEv = imp.process_file(fname, offset)
            # print "offset : %s" % nbEv
            # nbEv = offset for futur imports
            # need to stock this number somewhere
        self.notify("PackageActivate", package=self.package)
        self.package._modified=True
        return nbEv

    def enrich_event_package(self):
        """Apply transformations to an event package
           to generate high level annotations
        """

        def find_action(annot):
            atid = annot.type.id
            a = ["AnnotationCreate"]#bookmark
            r = ["AnnotationEditEnd","AnnotationDelete",
                "RelationCreate","AnnotationMerge","AnnotationMove"]
            n = ["PlayerStart","PlayerStop","PlayerPause",
                "PlayerResume","PlayerSet","ViewActivation"]#player
            c = ["AnnotationTypeCreate","RelationTypeCreate",
                "RelationTypeDelete", "AnnotationTypeDelete",
                "AnnotationTypeEditEnd", "RelationTypeEditEnd"]#schema
            v = ["ViewCreate","ViewEditEnd"] # view
            multi = ["ElementEditBegin","ElementEditEnd","ElementEditDestroy","ElementEditCancel"] # r, c or v
            if atid in a:
                return "Annotation"
            if atid in r:
                return "Restructuration"
            if atid in n:
                return "Navigation"
            if atid in c:
                return "Classification"
            if atid in v:
                return "View_building"
            if atid in multi:
                # need to test something else in annot
                return "Multi"
            return "Undefined"

        # FIXME: to rewrite
#        schema=self.package.get_element("Traces")
#        actions={}
#        ac_t = ["Annotation","Restructuration","Navigation","Classification","View_building"]
#        for t in ac_t:
#            action_type = self.package.get_element(t)
#            if (action_type is None):
#                #Annotation type creation
#                self.package._idgenerator.add(t)
#                action_type=schema.createAnnotationType(
#                    ident=t)
#                action_type.author=config.data.userid
#                action_type.date=time.strftime("%Y-%m-%d")
#                action_type.title="Action "+t
#                action_type.mimetype='application/x-advene-structured'
#                action_type.setMetaData(config.data.namespace, 'color', self.package._color_palette.next())
#                action_type.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
#                schema.annotationTypes.append(action_type)
#            actions[t]=action_type
#        last_act="None" # annotation, restructuration, navigation, classification, viw_biulding
#        an_nav = None # current navigation action
#        an_c = None # current action
#        last_evt = None # last event
#        move = 0 # if a move occurs, skip the next 2 events ( create/delete )
#        tmp_annots = [ (a, a.fragment.begin) for a in self.package.getAnnotations() ]
#        tmp_annots.sort(key=operator.itemgetter(1))
#        # need to sort annotations by start time
#        for (an, beg) in tmp_annots:
#            act = find_action(an)
#            if last_evt is not None:
#                last_act = find_action(last_evt)
#            #print "an : %s \ncat : %s \ntype : %s" % (an, act, an.type.id)
#            #undefined or still not recognized event.
#            if act == "Multi" or act == "Undefined":
#                print "undefined action for %s" % an.type.id
#                if last_act !=  "Multi" and last_act != "Undefined" and an_c is not None and an_c.fragment.end < an.fragment.begin:
#                    an_c.fragment.end = an.fragment.begin
#                #last_evt = an
#                continue
#            #navigation event
#            if act == "Navigation":
#                if an_nav is None:
#                    ident=self.package._idgenerator.get_id(Annotation)
#                    an_nav = self.package.createAnnotation(type = actions[act],
#                                            ident = ident,
#                                            fragment=MillisecondFragment(begin=an.fragment.begin,end=an.fragment.end))
#                    an_nav.content.data = "TODO NAV"
#                    self.package.annotations.append(an_nav)
#                else:
#                    an_nav.fragment.end = an.fragment.end
#                    if an.type.id == "PlayerStop" or an.type.id == "PlayerPause":
#                        an_nav=None
#                last_evt = an
#                continue
#            if an.type.id == "AnnotationMove":
#                move = 2
#            if move > 0 and (an.type.id == "AnnotationCreate" or an.type.id == "AnnotationDelete"):
#                an_c.fragment.end = an.fragment.begin #an_c exists, created with move or earlier
#                move = move-1
#                continue
#            #other event from a different type than last one
#            if act != last_act:
#                if an_nav is not None:
#                    an_nav.fragment.end = an.fragment.end
#                if an_c is not None and an_c.fragment.end < an.fragment.begin:
#                    an_c.fragment.end = an.fragment.begin
#                ident=self.package._idgenerator.get_id(Annotation)
#                an_c = self.package.createAnnotation(type = actions[act],
#                                            ident = ident,
#                                            fragment=MillisecondFragment(begin=an.fragment.begin,end=an.fragment.end))
#                an_c.content.data = "TODO"
#                self.package.annotations.append(an_c)
#                last_evt = an
#            #same type of event
#            last_evt = an
        return True

    def main(self):
        """Standalone controller mainloop.
        """
        self.init(sys.argv[1:])
        self.self_loop()
        return True

if __name__ == '__main__':
    # Try to find if we are in a development tree.
    (moduledir, subdir) = os.path.split(os.path.dirname(os.path.abspath(sys.argv[0])))
    maindir = os.path.dirname(moduledir)
    print "=========", maindir, moduledir, subdir
    if subdir == 'core' and  os.path.exists(os.path.join(maindir, "share")):
        # Chances are that we were in a development tree...
        print "You seem to have a development tree at:\n%s." % maindir
        import advene.core.config as config
        config.data.fix_paths(maindir)

    cont = AdveneController()
    try:
        cont.main ()
    except Exception, e:
        print "Got exception %s. Stopping services..." % str(e)
        import code
        e, v, tb = sys.exc_info()
        code.traceback.print_exception (e, v, tb)
        cont.on_exit ()
        print "*** Exception ***"
