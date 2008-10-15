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
"""Configuration module.

It provides data, an instance of Config class.

It is meant to be used this way::

  import config
  print "Userid: %s" % config.data.userid

@var data: an instance of Config (Singleton)
"""
# FIXME: cf http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/473846
# for windows-specific paths
import sys
import os
import cPickle
from optparse import OptionParser
import mimetypes
import operator
import time

class Config(object):
    """Configuration information, platform specific.

    It is possible to override the configuration variables in a config
    file ($HOME/.advene/advene.ini on Linux/MacOSX,
    UserDir/advene/advene.ini on Windows) with a python syntax
    (I{warning}, it is evaluated so harmful instructions in it can do
    damage).

    Example advene.ini file::

      config.data.path['plugins']='/usr/local/src/vlc-0.8.5'
      config.data.path['data']='/home/foo/advene/examples'

    @ivar path: dictionary holding path values. The keys are:
      - vlc : path to the VLC binary
      - plugins : path to the VLC plugins
      - advene : path to the Advene modules
      - resources : path to the Advene resources (glade, template, ...)
      - data : default path to the Advene data files

    @ivar namespace: the XML namespace for Advene extensions.

    @ivar templatefilename: the filename for the XML template file
    @ivar gladefilename: the filename for the Glade XML file

    @ivar preferences: the GUI preferences
    @type preferences: dict

    @ivar options: the player options
    @type options: dict

    @ivar namespace_prefix: the list of default namespace prefixes (with alias)
    @type namespace_prefix: dict

    @ivar webserver: webserver options (port number and running mode)
    @type webserver: dict
    """

    def __init__ (self):

        self.startup_time=time.time()

        self.config_file=''
        self.parse_options()

        if os.sys.platform in ( 'win32', 'darwin' ):
            self.os=os.sys.platform
        elif 'linux' in os.sys.platform:
            self.os='linux'
        else:
            print "Warning: undefined platform: ", os.sys.platform
            self.os=os.sys.platform

        if self.os == 'win32':
            self.path = {
                # VLC binary path
                'vlc': 'c:\\Program Files\\VideoLAN\\VLC',
                # VLC additional plugins path
                'plugins': 'c:\\Program Files\\Advene\\lib',
                # Advene modules path
                'advene': 'c:\\Program Files\\Advene',
                # Advene resources (.glade, template, ...) path
                'resources': 'c:\\Program Files\\Advene\\share',
                # Advene data files default path
                'data': self.get_homedir(),
                # Imagecache save directory
                'imagecache': os.getenv('TEMP') or 'c:\\',
                # Web data files
                'web': 'c:\\Program Files\\Advene\\share\\web',
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_',
                'locale': 'c:\\Program Files\\Advene\\locale',
                }
        elif self.os == 'darwin':
            self.path = {
                # VLC binary path
                'vlc': '/Applications/VLC.app',
                # VLC additional plugins path
                'plugins': '/Applications/VLC.app',
                # Advene modules path
                'advene': '/Applications/Advene.app',
                # Advene resources (.glade, template, ...) path FIXME
                'resources': '/Applications/Advene.app/share',
                # Advene data files default path
                'data': self.get_homedir(),
                # Imagecache save directory
                'imagecache': '/tmp',
                # Web data files FIXME
                'web': '/Applications/Advene.app/share/advene/web',
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_',
                # Locale dir FIXME
                'locale': '/Applications/Advene.app/locale',
                }
        else:
            self.path = {
                # VLC binary path
                'vlc': '/usr/bin',
                # VLC additional plugins path
                'plugins': '/usr/lib/vlc',
                # Advene modules path
                'advene': '/usr/lib/advene',
                # Advene resources (.glade, template, ...) path
                'resources': '/usr/share/advene',
                # Advene data files default path
                'data': self.get_homedir(),
                # Imagecache save directory
                'imagecache': '/tmp',
                # Web data files
                'web': '/usr/share/advene/web',
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_',
                'locale': '/usr/share/advene/locale',
                }

        self.path['settings'] = self.get_settings_dir()

        # Web-related preferences
        self.web = {
            'edit-width': 80,
            'edit-height': 25,
            }

        self.namespace="http://advene.org/ns/advene-application/2.0"
        self.transientns="http://advene.liris.cnrs.fr/ns/transient/"
        #advene.model.serializers.unserialized.register_unzerialized_meta_prefix(ton_prefixe)

        # These files are stored in the resources directory
        self.templatefilename = "template.azp"
        self.gladefilename = "advene.glade"

        # Generic options
        # They are automatically saved across sessions
        # in ~/.advene/advene.prefs
        self.preferences = {
            # Various sizes of windows.
            'windowsize': { 'main': (800, 600),
                            'editpopup': (640,480),
                            'editaccumulator': (100, 800),
                            'evaluator': (800, 600),
                            'relationview': (640, 480),
                            'sequenceview': (640, 480),
                            'timeline': (800, 400),
                            'transcriptionview': (640, 480),
                            'transcribeview': (640, 480),
                            'history': (640, 480),
                            'linksview': (640, 480),
                            'tree': (800, 600),
                            'browser': (800, 600),
                            'weblogview': (800, 600),
                            },
            'windowposition': {},
            'remember-window-size': True,
            'gui': { 'popup-textwidth': 40 },
            # Scroll increment in ms (for Control-Scroll)
            'scroll-increment': 100,
            # Scroll increment in ms (for Control-Shift-Scroll)
            'second-scroll-increment': 1000,
            # Time increment in ms (FF/REW, Control-Left/Right)
            'time-increment': 2000,
            # Time increment (Control-Shift-Left/Right)
            'second-time-increment': 5000,
            'timeline': {
                'font-size': 10,
                'button-height': 20,
                'interline-height': 6
                },
            # File history
            'history': [],
            'history-size-limit': 5,
            # User-defined paths. Will overwrite
            # config.data.path items
            'path': {},
            # Default adhoc views to open.
            # Syntax: timeline:tree:transcribe
            'adhoc-south': 'timeline',
            'adhoc-west': '',
            'adhoc-east': 'tree',
            'adhoc-fareast': '',
            'adhoc-popup': '',
            'display-scroller': False,
            'display-caption': False,
            'record-actions': False,
            # Imagecache save on exit: 'never', 'ask' or 'always'
            'imagecache-save-on-exit': 'ask',
            'quicksearch-ignore-case': True,
            # quicksearch source. If None, it is all package's annotations.
            # Else it is a TALES expression applied to the current package
            'quicksearch-source': None,
            # Display advanced options
            'expert-mode': False,
            # Package auto-save : 'never', 'ask' or 'always'
            'package-auto-save': 'never',
            # auto-save interval in ms. Every 5 minutes by default.
            'package-auto-save-interval': 5 * 60 * 1000,
            # Interface langugage. '' means system default.
            'language': '',
            'save-default-workspace': 'never',
            'restore-default-workspace': 'ask',
            # Daily check for updates on the Advene website ?
            'update-check': False,
            # Last update time
            'last-update': 0,
            # Width of the image used to display the snapshot of a bookmark
            'bookmark-snapshot-width': 80,
            # Precision in ms of the snapshot used for bookmarks.
            'bookmark-snapshot-precision': 150,
            # Width of the image used to display the snapshot drag icon
            'drag-snapshot-width': 50,
            # log messages also go to the terminal
            'log-to-terminal': False,
            # Language used for TTS. Standard 2 char. specification
            # (in fact, we use the espeak notation for simplicity).
            'tts-language': 'en',
            }

        # Player options
        self.player_preferences = {
            'default_caption_duration': 3000,
            'time_increment': 2000,
            }

        # Player options
        self.player = {
            'plugin': 'vlcnative',
            'bundled': True,
            'embedded': True,
            'name': 'vlc',
            'vout': 'default',
            'svg': False,
            'osdfont': '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
            'verbose': None, # None, 0, 1, 2
            'snapshot': True,
            'caption': True,
            'snapshot-dimensions': (160,100),
            'snapshot-chroma': 'RV32',
            'dvd-device': '/dev/dvd',
            }

        self.webserver = {
            'port': 1234,
            # Whether to launch the HTTP server in the gtk interface
            # True or False
            'mode': True,
            # 'navigation' or 'raw'
            'displaymode': 'raw',
            # engine: simple (for SimpleHTTPServer) or cherrypy (for CherryPy)
            'engine': 'simple',
            }

        # Global context options
        self.namespace_prefix = {'advenetool': self.namespace,
                                 'dc': 'http://purl.org/dc/elements/1.1/'}

        # Internal options. These should generally not be modified.

        # Used to memorize the volume level
        self.sound_volume=0

        # Update delay for position marker in views (in ms)
        self.slow_update_delay=200

        # Reaction time offset (in ms) used when setting annotations
        self.reaction_time=200

        # MIMEtypes that can be edited by the TextContentHandler
        self.text_mimetypes = (
            'application/x-advene-structured',
            'application/x-advene-sparql-query',
            'application/x-javascript',
            'application/x-advene-adhoc-view',
            'application/x-advene-workspace-view',
            'application/x-advene-quicksearch',
            'application/x-advene-values',
            )

        # Drag and drop parameters for URIed element and other elements
        self.target_type = {}
        self.drag_type = {}
        for name, typ, mime in (
            ('text-plain',         0, 'text/plain'),
            ('TEXT',               1, 'TEXT'),
            ('STRING',             2, 'UTF8_STRING'),
            ('annotation',        42, None),
            ('rule',              43, None),
            ('view',              44, None),
            ('schema',            45, None),
            ('annotation-type',   46, None),
            ('relation-type',     47, None),
            ('relation',          48, None),
            ('adhoc-view',        49, 'application/x-advene-adhoc-view'),
            ('annotation-resize', 50, None),
            ('timestamp',         51, 'application/x-advene-timestamp'),
            ('tag',               52, None),
            ('color',             53, 'application/x-color'),
            ('adhoc-view-instance', 54, 'application/x-advene-adhoc-view-instance'),
            ('bookmark',          55, 'application/x-advene-bookmark'),
            ('uri-list',          80, 'text/uri-list'),
            ):
            self.target_type[name] = typ
            if mime is None:
                mime = "application/x-advene-%s-uri" % name
            self.drag_type[name] = [ ( mime, 0, typ) ]

        self.video_extensions = (
            '.asf',
            '.avi',
            '.flv',
            '.mov',
            '.mpg', '.mpeg',  '.mp4',
            '.ogm',
            '.ogg',
            '.rm',
            '.vob',
            '.mkv',
            '.wmv',
            '.mp3',
            '.wav',
            )

        self.color_palette = (
            u'string:#cccc99',
            u'string:#AAAAEE',
            u'string:#ccaaaa',
            u'string:#ffcc52',
            u'string:#AACCAA',
            u'string:#deadbe',
            u'string:#fedcba',
            u'string:#abcdef',
            u'string:#ff6666',
            u'string:#66ff66',
            u'string:#FFFF88',
            u'string:#CDEB8B',
            u'string:#C3D9FF',
            u'string:#FF1A00',
            u'string:#CC0000',
            u'string:#FF7400',
            u'string:#008C00',
            u'string:#006E2E',
            u'string:#4096EE',
            u'string:#FF0084',
            u'string:#B02B2C',
            u'string:#D15600',
            u'string:#C79810',
            u'string:#73880A',
            u'string:#6BBA70',
            u'string:#3F4C6B',
            u'string:#356AA0',
            u'string:#D01F3C',
            )

        # Content-handlers
        self.content_handlers = []
        
        # Players, indexed by plugin name
        self.players = {}

        # Global methods (user-defined)
        self.global_methods = {}

        if self.os == 'win32':
            self.win32_specific_config()
        elif self.os == 'darwin':
            self.darwin_specific_config()

    @property
    def timestamp(self):
        """Formatted timestamp for the current date.
        """
        return datetime.now().isoformat()

    def check_settings_directory(self):
        """Check if the settings directory is present, and create it if necessary.
        """
        if not os.path.isdir(self.path['settings']):
            os.mkdir(self.path['settings'])
            self.first_run=True
        else:
            self.first_run=False
        return True

    def parse_options(self):
        """Parse command-line options.
        """
        parser=OptionParser(usage="""Advene - annotate digital videos, exchange on the Net.
    %prog [options] [file.czp|file.xml|alias=uri]""")

        parser.add_option("-v", "--version", dest="version", action="store_true",
                          help="Display version number and exit.")

        parser.add_option("", "--simple", dest="simple", action="store_true",
                          help="Use the simplified GUI.")

        parser.add_option("-s", "--settings-dir", dest="settings", action="store",
                          type="string", default=None, metavar="SETTINGSDIR",
                          help="Alternate configuration directory (default: ~/.advene).")

        parser.add_option("-u", "--user-id", dest="userid", action="store",
                          type="string", default=None, metavar="LOGIN-NAME",
                          help="User name (used to set the author field of elements).")

        parser.add_option("", "--no-embedded",
                          dest="embedded", action="store_false", default=True,
                          help="Do not embed the video player.")

        parser.add_option("-p", "--player",
                          dest="player",
                          action="store",
                          type="choice",
                          # FIXME: we should register player plugins and use introspection
                          choices=("vlcnative", "dummy", "vlcorbit",
                                   "xine", "gstreamer", "quicktime", "gstrecorder"),
                          default=None,
                          help="Video player selection")

        parser.add_option("-w", "--webserver-port", dest="port", action="store",
                          type="int", default=None, metavar="PORT_NUMBER",
                          help="Webserver port number (default 1234).")

        parser.add_option("-m", "--webserver-mode", dest="mode", action="store",
                          type="int", default=None, metavar="WEBSERVER_MODE",
                          help="0: deactivated ; 1: threaded mode.")

        parser.add_option("-f", "--filter",
                          dest="filter",
                          action="store",
                          type="string",
                          default=None,
                          help="Export filter. If specified, input files will be automatically converted. Use 'help' to get a list of valid export filters.")

        (self.options, self.args) = parser.parse_args()
        if self.options.version:
            print self.get_version_string()
            sys.exit(0)

    def process_options(self):
        """Process command-line options.

        This method is called after read_preferences() and
        read_config_file(), so that we can override from the command
        line options set in configuration files.
        """
        if self.options.port is not None:
            self.webserver['port'] = self.options.port
        if self.options.mode is not None:
            self.webserver['mode'] = self.options.mode

        if self.options.player is not None:
            self.player['plugin']=self.options.player
        self.player['embedded']=self.options.embedded

        h=self.preferences['history']
        if len(h) > self.preferences['history-size-limit']:
            self.preferences['history']=h[-self.preferences['history-size-limit']:]

        return True

    def win32_specific_config(self):
        """Win32 specific configuration.
        """
        if self.os != 'win32':
            return

        # Trying to get around win32's problems with threads...
        self.noplay_interval=10
        self.play_interval=57

        self.player['dvd-device']='E:'
        advenehome=self.get_registry_value('software\\advene','path')
        if advenehome is None:
            print "Cannot get the Advene location from registry"
            return
        print "Setting Advene paths from %s" % advenehome
        self.path['advene'] = advenehome
        self.path['locale'] = os.path.sep.join( (advenehome, 'locale') )
        self.path['plugins'] = os.path.sep.join( (advenehome, 'lib') )
        self.path['resources'] = os.path.sep.join( (advenehome, 'share') )
        self.path['web'] = os.path.sep.join( (advenehome, 'share', 'web') )

    def darwin_specific_config(self):
        """MacOS X specific tweaks.
        """
        if self.os != 'darwin':
            return
        # This one should go away sometime. But for the moment, the only way
        # to embed vlc is to use the X11 video output
        self.player['vout'] = 'x11'
        # There is still a pb with captioning, just use the workaround
        self.preferences['display-caption']=True

    def get_registry_value (self, subkey, name):
        """(win32) get a value from the registry.
        """
        if self.os != 'win32':
            return None
        import _winreg
        value = None
        for hkey in _winreg.HKEY_LOCAL_MACHINE, _winreg.HKEY_CURRENT_USER:
            try:
                reg = _winreg.OpenKey(hkey, subkey)
                value, type_id = _winreg.QueryValueEx(reg, name)
                _winreg.CloseKey(reg)
            except _winreg.error:
                #value=None
                pass
        return value

    def register_content_handler(self, handler):
        """Register a content handler.
        """
        # FIXME: check signature ?
        if not handler in self.content_handlers:
            self.content_handlers.append(handler)
        return True

    def register_global_method(self, method, name=None):
        """Register a global method.
        """
        # FIXME: check signature ?
        if name is None:
            name=method.func_name
        self.global_methods[name]=method
        return True

    def register_player(self, player):
        """Register a player plugin.
        """
        self.players[player.player_id] = player
        return True

    def get_content_handler(self, mimetype):
        """Return a valid content handler for the given mimetype.

        Return None if no content handler is valid (should not happen, as
        TextContentHandler is builtin).
        """
        l=[ (c, c.can_handle(mimetype)) for c in self.content_handlers ]
        if not l:
            return None
        else:
            l.sort(key=operator.itemgetter(1), reverse=True)
            return l[0][0]

    def get_homedir(self):
        """Return the user's homedir.
        """
        h=None
        if self.os == 'win32' and os.environ.has_key('USERPROFILE'):
            return os.environ['USERPROFILE']
        try:
            h=os.path.expanduser('~')
        except:
            # FIXME: find the appropriate exception to catch (on win32?)
            if os.environ.has_key('HOME'):
                h=os.environ['HOME']
            elif os.environ.has_key('HOMEPATH'):
                # Fallback for Windows
                h=os.path.join(os.environ['HOMEDRIVE'],
                               os.environ['HOMEPATH'])
            else:
                raise Exception ('Unable to find homedir')
        return h

    def get_settings_dir(self):
        """Return the directory used to store Advene settings.
        """
        if self.options.settings is not None:
            return self.options.settings

        if self.os == 'win32':
            dirname = 'advene'
        elif self.os == 'darwin':
            dirname = os.path.join( 'Library', 'Preferences', 'Advene' )
        else:
            dirname = '.advene'

        return os.path.join( self.get_homedir(), dirname )

    def read_preferences(self):
        """Update self.preferences from the preferences file.
        """
        prefs=self.read_preferences_file(d=self.preferences, name='advene')
        if prefs and prefs.has_key('path'):
            self.path.update(prefs['path'])
        self.read_preferences_file(d=self.player, name='player')
        return True

    def save_preferences(self):
        """Save self.preferences to the preferences file.
        """
        self.save_preferences_file(d=self.preferences, name='advene')
        self.save_preferences_file(d=self.player, name='player')
        return True

    def read_preferences_file(self, d=None, name='advene'):
        """Generic preferences reading.
        """
        if d is None:
            d=self.preferences
        preffile=self.advenefile(name+'.prefs', 'settings')
        try:
            f = open(preffile, "r")
        except IOError:
            return None
        try:
            prefs=cPickle.load(f)
        except (EOFError, cPickle.PickleError, cPickle.PicklingError):
            return None
        d.update(prefs)
        return prefs

    def save_preferences_file(self, d=None, name='advene'):
        """Generic preferences saving.
        """
        if d is None:
            d=self.preferences
        preffile=self.advenefile(name+'.prefs', 'settings')
        dp=os.path.dirname(preffile)
        if not os.path.isdir(dp):
            try:
                os.mkdir(dp)
            except OSError, e:
                print "Error: ", str(e)
                return False
        try:
            f = open(preffile, "w")
        except IOError:
            return False
        try:
            cPickle.dump(d, f)
        except (EOFError, cPickle.PickleError, cPickle.PicklingError):
            return False
        return True

    def read_config_file (self):
        """Read the configuration file (advene.ini).
        """
        conffile=self.advenefile('advene.ini', 'settings')

        try:
            fd=open(conffile, "r")
        except IOError:
            self.config_file=''
            return False

        print "Reading configuration from %s" % conffile
        config=sys.modules['advene.core.config']
        for li in fd:
            if li.startswith ("#"):
                continue
            obj = compile (li, conffile, 'single')
            try:
                exec obj
            except Exception, e:
                print "Error in %s:\n%s" % (conffile, str(e))
        fd.close ()

        self.config_file=conffile

    def get_player_args (self):
        """Build the VLC player argument list.

        FIXME: this is valid for VLC only, so this should belong
        to player.vlcnative.

        @return: the list of arguments
        """
        args=[]
        filters=[]

        args.extend( [ '--intf', 'dummy' ] )

        if os.path.isdir(self.path['plugins']):
            args.extend([ '--plugin-path', self.path['plugins'] ])
        if self.player['verbose'] is not None:
            args.append ('--verbose')
            args.append (self.player['verbose'])
        if self.player['vout'] != 'default':
            args.extend( [ '--vout', self.player['vout'] ] )
        if self.player['svg']:
            args.extend( [ '--text-renderer', 'svg' ] )
        if self.player['bundled']:
            args.append( '--no-plugins-cache' )
        if filters != []:
            # Some filters have been defined
            args.extend (['--vout-filter', ":".join(filters)])
        args.extend( '--snapshot-width 160 --snapshot-height 100'.split() )
        #print "player args", args
        return [ str(i) for i in args ]

    def get_userid (self):
        """Return the userid (login name).

        @return: the user id
        @rtype: string
        """
        # FIXME: allow override via advene.ini
        if self.options.userid is not None:
            return self.options.userid

        id_ = "Undefined id"
        for name in ('USER', 'USERNAME', 'LOGIN'):
            if os.environ.has_key (name):
                id_ = os.environ[name]
                break
        # Convert to unicode
        try:
            # If there are any accented characters and the encoding is
            # not UTF-8, this will fail
            id_ = unicode(id_, 'utf-8')
        except UnicodeDecodeError:
            # Decoding to latin1 will always work (but may produce
            # strange characters depending on the system charset).
            # This looks however like the best fallback for the moment
            # (even on win32)
            id_ = unicode(id_, 'latin1')
        return id_

    def advenefile(self, filename, category='resources'):
        """Return an absolute pathname for the given file.

        @param filename: a filename or a path to a file (tuple)
        @type filename: string or tuple
        @param category: the category of the file
        @type category: string

        @return: an absolute pathname
        @rtype: string
        """
        if isinstance(filename, list) or isinstance(filename, tuple):
            filename=os.sep.join(filename)
        return os.path.join ( self.path[category], filename )

    def get_version_string(self):
        """Return the version string.
        """
        try:
            import advene.core.version as version
            return "Advene v. %s release %s (svn %s)" % (version.version,
                                                         version.date,
                                                         version.svn)
        except ImportError:
            return "Advene v. ??? (cannot get version number)"

    userid = property (fget=get_userid,
                       doc="Login name of the user")
    player_args = property (fget=get_player_args,
                            doc="List of arguments for the VLC player")

    version_string = property(fget=get_version_string,
                              doc="Version string")

    def register_mimetype_file(self, fname):
        """Register a mimetype for a given extension.
        """
        for ext, t in mimetypes.read_mime_types(fname).iteritems():
            mimetypes.add_type(t, ext)

    def fix_paths(self, maindir):
        """Adjust paths according to the given main directory.
        """
        # We override any modification that could have been made in
        # .advenerc. Rationale: if the .advenerc was really correct, it
        # would have set the correct package path in the first place.
        print "Overriding 'resources', 'locale', 'advene' and 'web' config paths"
        data.path['resources']=os.path.sep.join((maindir, 'share'))
        data.path['locale']=os.path.sep.join( (maindir, 'locale') )
        data.path['web']=os.path.sep.join((maindir, 'share', 'web'))
        data.path['advene']=maindir
        #config.data.path['plugins']=os.path.sep.join( (maindir, 'vlc') )

data = Config ()
data.check_settings_directory()
data.read_preferences()
# Config file (advene.ini) may override settings from preferences
data.read_config_file ()
# We process options last, so that command-line options can
# override preferences and .ini file.
data.process_options()
