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
"""
Advene controller
=================

This is the core of the Advene framework. It holds the various
components together (data model, webserver, GUI, event handler...),
and can be seen as a Facade design pattern for these components.

The X{AdveneEventHandler} is used by the application to handle events
notifications and actions triggering.
"""

import sys, time
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

import advene.core.config as config

from gettext import gettext as _

import advene.core.plugin
from advene.core.mediacontrol import PlayerFactory
from advene.core.imagecache import ImageCache
import advene.core.idgenerator

from advene.rules.elements import RuleSet, RegisteredAction
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

import advene.model.tal.context

import advene.util.helper as helper
import advene.util.importer
import advene.util.ElementTree as ET
import advene.rules.importer

if config.data.webserver['mode']:
    from advene.core.webcherry import AdveneWebServer

import threading

class AdveneController:
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
        self.player.get_default_media = self.get_default_media
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
        if self.package is not None:
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
                self.log("Registering " + p.name)
                p.register(controller=self)
            except AttributeError:
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
            #print "Process action: %s" % str(method)
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
                    self.queue_action(self.update_status, 'set', l[0][1])
                else:
                    # No next annotation. Return to the start
                    if self.restricted_annotations:
                        l=self.restricted_annotations
                    else:
                        l=[ a.fragment.begin for a in at.annotations ]
                        l.sort()
                    self.queue_action(self.update_status, "set", position=l[0])
            return True

        if at is not None:
            # New annotation-type restriction
            self.restricted_rule=self.event_handler.internal_rule(event="AnnotationEnd",
                                                                  method=restricted_play)
            p=self.player
            if p.status == p.PauseStatus or p == p.PlayingStatus:
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
            source=p.annotations
        elif source == 'tags':
            source=itertools.chain( p.annotations, p.relations )
            if case_sensitive:
                data_func=lambda e: e.tags
            else:
                data_func=lambda e: [ normalize_case(t) for t in e.tags ]
        else:
            c=self.build_context()
            source=c.evaluateValue(source)
        
        words=shlex.split(searched)

        mandatory=[ w[1:] for w in words if w.startswith('+') ]
        exceptions=[ w[1:] for w in words if w.startswith('-') ]
        normal=[ w for w in words if not w.startswith('+') and not w.startswith('-') ]

        for w in mandatory:
            w=normalize_case(w)
            source=[ e for e in source if w in data_func(e) ]
        for w in exceptions:
            w=normalize_case(w)
            source=[ e for e in source if w not in data_func(e) ]
        res=[]
        for e in source:
            data=data_func(e)
            for w in normal:
                if w in data:
                    res.append(e)
                    break
        return res
        
    def build_context(self, here=None, alias=None, baseurl=None):
        """Build a context object with additional information.
        """
        if baseurl is None:
            baseurl=self.get_default_url(root=True, alias=alias)
        if here is None:
            here=self.package
        c=advene.model.tal.context.AdveneContext(here,
                                                 options={
                u'package_url': baseurl,
                u'snapshot': self.package.imagecache,
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
        self.event_handler.read_ruleset_from_file(config.data.advenefile('default_rules.xml'),
                                                  type_='default', priority=100)

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
                if ext.lower() in ('.xml', '.azp', '.apl'):
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
            self.load_package ()
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
            el=event_name.lower().replace('create','').replace('editend','').replace('delete', '')
            p=kw[el].ownerPackage
            p._modified = True
        
        immediate=False
        if immediate in kw:
            immediate=kw['immediate']
            del kw['immediate']
        if immediate:
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
        if (config.data.player['snapshot'] 
            and not self.package.imagecache.is_initialized (position)):
            # FIXME: only 0-relative position for the moment
            # print "Update snapshot for %d" % position
            try:
                i = self.player.snapshot (self.player.relative_position)
            except self.player.InternalException, e:
                print "Exception in snapshot: %s" % e
                return True
            if i is not None and i.height != 0:
                self.package.imagecache[position] = helper.snapshot2png (i)
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
        defaultview=self.package.getMetaData(config.data.namespace, 'default_utbv')
        if defaultview:
            url=u"%s/view/%s" % (url, defaultview)
        return url

    def get_title(self, element, representation=None):
        """Return the title for the given element.
        """
        return helper.get_title(self, element, representation)

    def get_default_media (self, package=None):
        """Return the current media for the given package.
        """
        if package is None:
            package=self.package

        mediafile = package.getMetaData (config.data.namespace,
                                         "mediafile")
        if mediafile is None or mediafile == "":
            return ""
        m=self.dvd_regexp.match(mediafile)
        if m:
            title,chapter=m.group(1, 2)
            mediafile=self.player.dvd_uri(title, chapter)
        elif mediafile.startswith('http:'):
            # FIXME: check for the existence of the file
            pass
        elif not os.path.exists(mediafile):
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
                if os.path.exists(n):
                    mediafile=n
                    self.log(_("Found matching video file in moviepath: %s") % n)
                    break
        return mediafile

    def set_media(self, uri=None):
        """Set the current media in the video player.
        """
        if isinstance(uri, unicode):
            uri=uri.encode('utf8')
        if self.player.status in (self.player.PlayingStatus, self.player.PauseStatus):
            self.player.stop(0)
        self.player.playlist_clear()
        if uri is not None:
            self.player.playlist_add_item (uri)
        self.notify("MediaChange", uri=uri)

    def set_default_media (self, uri, package=None):
        """Set the default media for the package.
        """
        if package is None:
            package=self.package
        m=self.dvd_regexp.match(uri)
        if m:
            title,chapter=m.group(1,2)
            uri="dvd@%s:%s" % (title, chapter)
        if isinstance(uri, unicode):
            uri=uri.encode('utf8')
        package.setMetaData (config.data.namespace, "mediafile", uri)
        if m:
            uri=self.player.dvd_uri(title, chapter)
        self.set_media(uri)
        # Reset the imagecache
        self.package.imagecache=ImageCache()
        if uri is not None and uri != "":
            id_ = helper.mediafile2id (uri)
            self.package.imagecache.load (id_)

    def delete_element (self, el):
        """Delete an element from its package.
        
        Take care of all dependencies (for instance, annotations which
        have relations.
        """
        p=el.ownerPackage
        if isinstance(el, Annotation):
            # We iterate on a copy of relations, since it may be
            # modified during the loop
            for r in el.relations[:]:
                [ a.relations.remove(r) for a in r.members if r in a.relations ]
                self.delete_element(r)
            p.annotations.remove(el)
            self.notify('AnnotationDelete', annotation=el)
        elif isinstance(el, Relation):
            for a in el.members:
                if el in a.relations:
                    a.relations.remove(el)
            p.relations.remove(el)
            self.notify('RelationDelete', relation=el)
        elif isinstance(el, AnnotationType):
            for a in el.annotations:
                self.delete_element(a)
            el.schema.annotationTypes.remove(el)
            self.notify('AnnotationTypeDelete', annotationtype=el)
        elif isinstance(el, RelationType):
            for r in el.relations:
                self.delete_element(r)
            el.schema.relationTypes.remove(el)
            self.notify('RelationTypeDelete', relationtype=el)
        elif isinstance(el, Schema):
            for at in el.annotationTypes:
                self.delete_element(at)
            for rt in el.relationTypes:
                self.delete_element(rt)
            p.schemas.remove(el)
            self.notify('SchemaDelete', schema=el)
        elif isinstance(el, View):
            p.views.remove(el)
            self.notify('ViewDelete', view=el)
        elif isinstance(el, Query):
            p.queries.remove(el)
            self.notify('QueryDelete', query=el)
        elif isinstance(el, Resources) or isinstance(el, ResourceData):
            if isinstance(el, Resources):
                for c in el.children():
                    self.delete_element(c)
            p=el.parent
            del(p[el.id])
            self.notify('ResourceDelete', resource=el)
        return True

    def transmute_annotation(self, annotation, annotationType, delete=False, position=None):
        """Transmute an annotation to a new type.

        If delete is True, then delete the source annotation.

        If position is not None, then set the new annotation begin to position.
        """
        if annotation.type == annotationType:
            # Tranmuting on the same type.
            if position is None:
                # Do not just duplicate the annotation
                return None
            elif delete:
                # If delete, then we can simply move the annotation
                # without deleting it.
                d=annotation.fragment.duration
                annotation.fragment.begin=position
                annotation.fragment.end=position+d
                self.notify("AnnotationEditEnd", annotation=annotation, comment="Transmute annotation")
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
                    if d.has_key(n):
                        name=d[n]
                        break
                d['name']=name.replace('\n', '\\n')
            else:
                d['name']='Unknown'
            d.setdefault('x', 50)
            d.setdefault('y', 50)
            d.setdefault('width', 10)
            d.setdefault('height', 10)
            d.setdefault('shape', 'rect')
            an.content.data="\n".join( [ "%s=%s" % (k, v) for k, v in d.iteritems() ] )
        elif an.type.mimetype == 'application/x-advene-structured':
            if annotation.type.mimetype == 'text/plain':
                an.content.data = "title=" + annotation.content.data.replace('\n', '\\n')
            elif annotation.type.mimetype == 'application/x-advene-structured':
                an.content.data = annotation.content.data
            else:
                self.log("Cannot convert %s to %s" % (annotation.type.mimetype,
                                                      an.type.mimetype))
                an.content.data = annotation.content.data
        else:
            self.log("Do not know how to convert %s to %s" % (annotation.type.mimetype,
                                                              an.type.mimetype))
            an.content.data = annotation.content.data
        an.setDate(self.get_timestamp())

        self.notify("AnnotationCreate", annotation=an, comment="Transmute annotation")

        if delete and not annotation.relations:
            self.package.annotations.remove(annotation)
            self.notify('AnnotationDelete', annotation=annotation, comment="Transmute annotation")

        return an

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
            self.log(_("Cannot split the annotation: the given position is outside."))
            return annotation

        # Create the new one
        ident=self.package._idgenerator.get_id(Annotation)
        an = self.package.createAnnotation(type = annotation.type,
                                           ident=ident,
                                           fragment=annotation.fragment.clone())

        # Shorten the first one.
        annotation.fragment.end = position
        self.notify("AnnotationEditEnd", annotation=annotation, comment="Duplicate annotation")

        # Shorten the second one
        an.fragment.begin = position

        self.package.annotations.append(an)
        an.author=config.data.userid
        an.content.data=annotation.content.data
        an.setDate(self.get_timestamp())
        self.notify("AnnotationCreate", annotation=an, comment="Duplicate annotation")
        return an

    def restart_player (self):
        """Restart the media player."""
        self.player.restart_player ()
        mediafile = self.get_default_media()
        if mediafile != "":
            self.set_media(mediafile)

    def get_timestamp(self):
        """Return a formatted timestamp for the current date.
        """
        return time.strftime("%Y-%m-%d")

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
    
        # First try the 'color' metadata from the element itself.
        color=None
        col=element.getMetaData(config.data.namespace, metadata)
        if col:
            c=self.build_context(here=element)
            try:
                color=c.evaluateValue(col)
            except Exception:
                color=None

        if not color:
            # Not found in element. Try item_color from the container.
            if hasattr(element, 'type'):
                container=element.type
            elif hasattr(element, 'schema'):
                container=element.schema
            else: 
                container=None
            if container:
                col=container.getMetaData(config.data.namespace, 'item_color')
                if col:
                    c=self.build_context(here=element)
                    try:
                        color=c.evaluateValue(col)
                    except Exception:
                        color=None
                if not color:
                    # Really not found. So use the container color.
                    color=self.get_element_color(container)
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
            except Exception, e:
                self.log(_("Cannot find the template package %(filename)s: %(error)s") 
                         % {'filename': config.data.advenefile(config.data.templatefilename),
                            'error': unicode(e)})
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
            p = Package (uri=uri)
            # Check if the imported package was found. Else it will
            # fail when accessing elements...
            for i in p.imports:
                try:
                    imp=i.package
                except Exception, e:
                    raise Exception(_("Cannot read the imported package %(uri)s: %(error)s") % {
                            'uri': i.uri,
                            'error': unicode(e)})
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

        self.package.imagecache=ImageCache()
        self.package._idgenerator = advene.core.idgenerator.Generator(self.package)
        self.package._modified = False

        # Initialize the color palette for the package
        self.package._color_palette=helper.CircularList(config.data.color_palette[:])

        # Parse tag_colors attribute
        cols = self.package.getMetaData (config.data.namespace, "tag_colors")
        if cols:
            d = dict(cgi.parse_qsl(cols))
        else:
            d={}
        self.package._tag_colors=d
         
        duration = self.package.getMetaData (config.data.namespace, "duration")
        if duration is not None:
            try:
                v=long(float(duration))
            except ValueError:
                v=0
            self.package.cached_duration = v
        else:
            self.package.cached_duration = 0

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
        @param imagecache: the imagecache associated to the package
        @type imagecache: advene.core.ImageCache
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

        # Reset the cached duration
        duration = self.package.getMetaData (config.data.namespace, "duration")
        if duration is not None:
            self.package.cached_duration = long(float(duration))
        else:
            self.package.cached_duration = 0

        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            if self.player.is_active():
                if mediafile not in self.player.playlist_get_list ():
                    # Update the player playlist
                    self.set_media(mediafile)
        else:
            self.set_media(None)

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
        self.log("FIXME: reset not implemented yet")
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
            name=p.uri
        old_uri = p.uri

        # Handle tag_colors
        # Parse tag_colors attribute.
        self.package.setMetaData (config.data.namespace, 
                                  "tag_colors", 
                                  cgi.urllib.urlencode(self.package._tag_colors))

        # Check if we know the stream duration. If so, save it as
        # package metadata
        d=p.cached_duration
        if d > 0:
            p.setMetaData (config.data.namespace,
                           "duration", unicode(d))

        if p == self.package:
            # Set if necessary the mediafile metadata
            if self.get_default_media() == "":
                pl = self.player.playlist_get_list()
                if pl and pl[0]:
                    self.set_default_media(pl[0])

        p.save(name=name)
        p._modified = False

        self.notify ("PackageSave", package=p)
        if old_uri != name:
            # Reload the package with the new name
            self.log(_("Package URI has changed. Reloading package with new URI."))
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
            self.log (_("Cannot load package: the following annotations do not have Millisecond fragments:"))
            self.log (", ".join(l))
            return True

        p.imagecache.clear ()
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            # Load the imagecache
            id_ = helper.mediafile2id (mediafile)
            p.imagecache.load (id_)
            # Populate the missing keys
            for a in p.annotations:
                p.imagecache.init_value (a.fragment.begin)
                p.imagecache.init_value (a.fragment.end)

        # Handle 'auto-import' meta-attribute
        master_uri=p.getMetaData(config.data.namespace, 'auto-import')
        if master_uri:
            i=[ p for p in p.imports if p.getUri(absolute=False) == master_uri ]
            if not i:
                self.log(_("Cannot handle master attribute, the package %s is not imported.") % master_uri)
            else:
                self.log(_("Checking master package %s for not yet imported elements.") % master_uri)
                self.handle_auto_import(self.package, i[0].package)

        return True

    def handle_auto_import(self, p, i):
        """Ensure that all views, schemas, queries are imported from i in p.
        """
        for source in ('views', 'schemas', 'queries'):
            uris=[ e.uri for e in getattr(p, source) ]
            for e in getattr(i, source):
                if not e.uri in uris:
                    print "Missing %s: importing it" % str(e)
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
        defaultview=self.package.getMetaData(config.data.namespace,
                                             'default_utbv')
        if defaultview:
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
        rs.from_dom(catalog=self.event_handler.catalog,
                    domelement=view.content.model,
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
                        rs.from_dom(catalog=self.event_handler.catalog,
                                    domelement=v.content.model,
                                    origin=v.uri)
                        parsed_views.append(v)
                subviews=rs.filter_subviews()

        self.event_handler.set_ruleset(rs, type_='user')
        for v in parsed_views:
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
        else:
            # FIXME: handle the level parameter
            print msg
        return

    def message_log (self, context, parameters):
        """Event Handler for the message action.

        Essentialy a wrapper for the X{log} method.

        @param context: the action context
        @type context: TALContext
        @param parameters: the parameters (should have a 'message' one)
        @type parameters: dict
        """
        if parameters.has_key('message'):
            message=context.evaluateValue(parameters['message'])
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

            # Cleanup the ZipPackage directories
            ZipPackage.cleanup()

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
        l = [ (a, a.fragment.begin, a.fragment.end)
              for a in self.package.annotations
              if a.fragment.begin >= position or a.fragment.end >= position ]
        future_begins = list(l)
        future_ends = l
        future_begins.sort(key=operator.itemgetter(1))
        future_ends.sort(key=operator.itemgetter(1))

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
        except Exception, e:
            # FIXME: we should catch more specific exceptions and
            # devise a better feedback than a simple print
            import traceback
            s=StringIO.StringIO()
            traceback.print_exc (file = s)
            self.log(_("Raised exception in update_status: %s") % str(e), s.getvalue())
        else:
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
            print _("Restarting player...")
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
        if self.package.cached_duration <= 0 and self.player.stream_duration > 0:
            print "updating cached duration"
            self.package.cached_duration = long(self.player.stream_duration)

        return pos

    def delete_annotation(self, annotation):
        """Remove the annotation from the package."""
        self.package.annotations.remove(annotation)
        self.notify('AnnotationDelete', annotation=annotation)
        return True

    def import_event_history(self):
        """Import the event history in the current package.
        """
        i=advene.rules.importer.EventHistoryImporter(package=self.package)
        i.process_file(self.event_handler.event_history)
        self.notify("PackageActivate", package=self.package)
        return True

if __name__ == '__main__':
    cont = AdveneController()
    try:
        cont.main ()
    except Exception, e:
        print _("Got exception %s. Stopping services...") % str(e)
        import code
        e, v, tb = sys.exc_info()
        code.traceback.print_exception (e, v, tb)
        cont.on_exit ()
        print _("*** Exception ***")
