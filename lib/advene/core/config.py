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
"""Configuration module.

It provides data, an instance of Config class.

It is meant to be used this way::

  import config
  default_userid = config.data.userid

@var data: an instance of Config (Singleton)
"""
import logging
logger = logging.getLogger(__name__)

import collections.abc
import sys
import os
import pickle
import json
from argparse import ArgumentParser
import mimetypes
import operator
from pathlib import Path
import subprocess
import time
import xml.dom

APP='advene'

def init_gettext():
    import gettext
    gettext.bindtextdomain(APP, str(data.path['locale']))
    gettext.textdomain(APP)
    gettext.install(APP, localedir=str(data.path['locale']))

def find_in_path(name):
    """Return the fullpath of the filename name if found in $PATH

    Return None if name cannot be found.
    """
    for d in os.environ['PATH'].split(os.path.pathsep):
        fullname = Path(d) / name
        if fullname.exists():
            return fullname
    return None

def deep_update(d, u):
    """Utility function to deep_update dicts.
    Used for preferences updating.

    It assumes that source key types are stable (i.e. a integer value
    will not be updated to a dict)
    """
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Path):
            return str(o)
        return json.JSONEncoder.default(self, o)

class Config:
    """Configuration information, platform specific.

    It is possible to override the configuration variables in a config
    file ($HOME/.config/advene/advene.ini on Linux,
    $HOME/Library/Preferences/Advene/advene.ini on MacOSX,
    UserDir/advene/advene.ini on Windows) with a python syntax
    (I{warning}, it is evaluated so harmful instructions in it can do
    damage).

    Example advene.ini file::

      config.data.path['data']=Path('/home/foo/advene/examples')

    @ivar path: dictionary holding path values. The keys are:
      - advene : path to the Advene modules
      - resources : path to the Advene resources (template, ...)
      - data : default path to the Advene data files

    @ivar namespace: the XML namespace for Advene extensions.

    @ivar templates: dict (alias, filename) for the template files

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

        self.debug=False

        # Set this to True (through the evaluator) to launch
        # post-mortem pdb upon exception
        self.livedebug = False

        self.startup_time=time.time()

        self.config_file=''
        self.parse_options()

        if os.sys.platform in ( 'win32', 'darwin' ):
            self.os = os.sys.platform
        elif 'linux' in os.sys.platform:
            self.os = 'linux'
        else:
            logger.warning("Warning: undefined platform: %s", os.sys.platform)
            self.os = os.sys.platform

        # Default values
        if self.os == 'win32':
            prgdir = Path(os.environ.get('PROGRAMFILES', 'c:/Program Files'))
            advenedir = prgdir / 'Advene'
            self.path = {
                # Advene modules path
                'advene': advenedir,
                # Advene resources (template, ...) path
                'resources': advenedir / 'share',
                # Advene data files default path
                'data': Path.home(),
                # Imagecache save directory
                'imagecache': Path(os.getenv('TEMP', 'c:/')),
                # Web data files
                'web': advenedir / 'share' / 'web',
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_',
                'locale': advenedir / 'locale',
                'shotdetect': advenedir / 'share' / 'shotdetect.exe'
                }
        elif self.os == 'darwin':
            advenedir = Path('/Applications/Advene.app')
            resourcesdir = advenedir / 'Contents' / 'Resources'
            self.path = {
                # Advene modules path
                'advene': advenedir,
                # Advene resources (template, ...) path
                'resources': resourcesdir / 'share',
                # Advene data files default path
                'data': Path.home() / "Documents",
                # Imagecache save directory
                'imagecache': Path('/tmp'),
                # Web data files
                'web': resourcesdir / 'share' / 'web',
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_:%s' % (Path.home() / 'Movies'),
                # Locale dir
                'locale': resourcesdir / 'locale',
                'shotdetect': ""
                }
        else:
            imagecache = os.environ.get('XDG_CACHE_HOME', None)
            if imagecache:
                imagecache = imagecache / 'advene'
            else:
                imagecache = Path.home() / '.cache' / 'advene'
            imagecache.mkdir(parents=True, exist_ok=True)
            self.path = {
                # Advene modules path
                'advene': Path('/usr/lib/advene'),
                # Advene resources (template, ...) path
                'resources': Path('/usr/share/advene'),
                # Advene data files default path
                'data': Path.home(),
                # Imagecache save directory
                'imagecache': imagecache,
                # Web data files
                'web': Path('/usr/share/advene/web'),
                # Movie files search path. _ is the
                # current package path
                'moviepath': '_',
                'locale': Path('/usr/share/locale'),
                'shotdetect': Path('shotdetect'),
                }

        self.path['settings'] = self.get_settings_dir()

        # Web-related preferences
        self.web = {
            'edit-width': 80,
            'edit-height': 25,
            }

        self.namespace = "http://experience.univ-lyon1.fr/advene/ns/advenetool"

        # These files are stored in the resources directory
        self.templates = {
            'basic': "template.azp",
            'remind': "remind-template.azp",
            'ada': "ada-template.azp"
        }

        # Generic options
        # They are automatically saved across sessions
        # in ~/.config/advene/advene.prefs
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
            # Fallback screen dimensions - we need a fallback on
            # Gtk3/wayland, hopefully it will not be needed in
            # Gtk4/wayland
            'fallback-screen-width': 1920,
            'fallback-screen-height': 1600,
            'remember-window-size': True,
            'gui': { 'popup-textwidth': 40,
                     # Enforce this min-pane-size when opening views
                     'min-pane-size': 40 },
            # Timestamp format. Extended notation with %.S to display
            # seconds as floating-point data, with milliseconds.
            'timestamp-format': '%H:%M:%.S',
            # Scroll increment in ms (for Control-Scroll)
            'scroll-increment': 100,
            # Scroll increment in ms (for Control-Shift-Scroll)
            'second-scroll-increment': 1000,
            # Time increment in ms (FF/REW, Control-Left/Right)
            'time-increment': 2000,
            # Time increment (Control-Shift-Left/Right)
            'second-time-increment': 5000,
            # Time increment (Control-Shift-Up/Down)
            'third-time-increment': 1,
            # Custom up/down: use third-time-increment for up/down, do
            # not require Shift
            'custom-updown-keys': False,
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
            # quicksearch sources. If [], it is all package's annotations.
            # Else it is a list of TALES expression applied to the current package
            'quicksearch-sources': [],
            # Display advanced options
            'expert-mode': False,
            # Package auto-save : 'never', 'ask' or 'always'
            'package-auto-save': 'never',
            # auto-save interval in ms. Every 5 minutes by default.
            'package-auto-save-interval': 5 * 60 * 1000,
            # slave player automatic synchronization delay. 0 to disable.
            'slave-player-sync-delay': 3000,
            # Interface language. '' means system default.
            'language': '',
            'save-default-workspace': 'always',
            'restore-default-workspace': 'always',
            # Weekly check for updates on the Advene website ?
            'update-check': True,
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
            # Encoding for data sent to the TTS engine.
            'tts-encoding': 'utf8',
            # Engine
            'tts-engine': 'auto',
            'edition-history-size': 5,
            # popup views may be popup or opened into a specific viewbook,
            'popup-destination': 'east',
            'embedded': True,
            'abbreviation-mode': True,
            'completion-mode': True,
            # Complete with predefined terms only if they are defined
            'completion-predefined-only': False,
            # Quick entry of predefined values through 1-9 shortcuts
            'completion-quick-fill': False,
            'text-abbreviations': '',
            # Automatically start the player when loading a media file
            # (either directly or through a package)
            'player-autostart': False,
            'prefer-wysiwyg': True,
            'player-shortcuts-in-edit-windows': True,
            # See Gtk.accelerator_parse for possible values
            'player-shortcuts-modifier':'<Control>',
            # Default FPS, used for smpte-style timestamp display
            'default-fps': 25,
            'apply-edited-elements-on-save': True,
            'frameselector-width': 140,
            'frameselector-count': 8,
            # Cache settings for import filters
            'filter-options': {},
            # Use UUIDs for element ids. If false, generate readable ids.
            'use-uuid': True
            }

        # Player options
        self.player_preferences = {
            'default_caption_duration': 3000,
            }

        # Player options
        self.player = {
            'plugin': 'gstreamer',
            'bundled': True,
            'embedded': True,
            'vout': 'gtk',
            'svg': True,
            'osdfont': '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
            'verbose': None, # None, 0, 1, 2
            'snapshot': True,
            'caption': True,
            'snapshot-width': 160,
            'dvd-device': '/dev/dvd',
            'fullscreen-timestamp': False,
            # Name of audio device for gstrecorder
            'audio-record-device': 'default',
            'record-video': True,
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
        self.namespace_prefix = { 'advene': "http://experience.univ-lyon1.fr/advene/ns",
                                  'advenetool': self.namespace,
                                  'dc': 'http://purl.org/dc/elements/1.1/',
                                  'svg': 'http://www.w3.org/2000/svg',
                                  'xlink': "http://www.w3.org/1999/xlink",
                                  'xml': xml.dom.XML_NAMESPACE,
                                  'xmlnsNS': xml.dom.XMLNS_NAMESPACE }
        self.reverse_namespace_prefix = dict( (v, k) for (k, v) in self.namespace_prefix.items() )

        # Internal options. These should generally not be modified.

        # Used to memorize the volume level
        self.sound_volume=0

        # Update delay for position marker in views (in ms)
        self.slow_update_delay=10

        # Reaction time offset (in ms) used when setting annotations
        self.reaction_time=200

        # MIMEtypes that can be edited by the TextContentHandler
        self.text_mimetypes = (
            'text/x-advene-keyword-list',
            'application/x-advene-sparql-query',
            'application/x-javascript',
            'application/javascript',
            'application/x-advene-adhoc-view',
            'application/x-advene-workspace-view',
            'application/x-advene-quicksearch',
            'application/x-advene-values',
            'application/x-advene-structured',
            'application/json',
            )

        # Drag and drop parameters for URIed element and other elements
        self.target_type = {}
        self.drag_type = {}
        self.target_entry = {}
        for name, typ, mime in (
                ('text-plain',           0, 'text/plain'),
                ('TEXT',                 1, 'TEXT'),
                ('STRING',               2, 'UTF8_STRING'),
                ('annotation',          42, None),
                ('rule',                43, None),
                ('view',                44, None),
                ('schema',              45, None),
                ('annotation-type',     46, None),
                ('relation-type',       47, None),
                ('relation',            48, None),
                ('adhoc-view',          49, 'application/x-advene-adhoc-view'),
                ('annotation-resize',   50, None),
                ('timestamp',           51, 'application/x-advene-timestamp'),
                ('tag',                 52, None),
                ('color',               53, 'application/x-color'),
                ('adhoc-view-instance', 54, 'application/x-advene-adhoc-view-instance'),
                ('bookmark',            55, 'application/x-advene-bookmark'),
                ('query',               56, None),
                ('uri-list',            80, 'text/uri-list'),
            ):
            self.target_type[name] = typ
            if mime is None:
                mime = "application/x-advene-%s-uri" % name
            self.drag_type[name] = [ ( mime, 0, typ) ]
            self.target_entry[name] = None

        self.video_extensions = (
            '.264',
            '.3gp',
            '.asf',
            '.avi',
            '.dv',
            '.flv',
            '.m4v', '.m4a',
            '.mjpg', '.mjpg',
            '.mkv',
            '.mov',
            '.mp3',
            '.mpg', '.mpeg',  '.mp4', '.mp4v',
            '.mts',
            '.ogg', '.ogm', '.ogv', '.ogx',
            '.opus',
            '.ps',
            '.qt', '.qtm',
            '.rm', '.rmd', '.rmvb', '.rv',
            '.ts',
            '.vfw',
            '.vob',
            '.vp6', '.vp7', '.vp8',
            '.wav',
            '.webm',
            '.wmv',
            '.xvid',
            )

        self.color_palette = (
            'string:#cccc99',
            'string:#AAAAEE',
            'string:#ccaaaa',
            'string:#ffcc52',
            'string:#AACCAA',
            'string:#deadbe',
            'string:#fedcba',
            'string:#abcdef',
            'string:#ff6666',
            'string:#66ff66',
            'string:#FFFF88',
            'string:#CDEB8B',
            'string:#C3D9FF',
            'string:#FF1A00',
            'string:#CC0000',
            'string:#FF7400',
            'string:#008C00',
            'string:#006E2E',
            'string:#4096EE',
            'string:#F0C5ED',
            'string:#B02B2C',
            'string:#D15600',
            'string:#C79810',
            'string:#73880A',
            'string:#6BBA70',
            'string:#3F4C6B',
            'string:#356AA0',
            'string:#D01F3C',
            )

        # Content-handlers
        self.content_handlers = []

        # Players, indexed by plugin name
        self.players = {}

        # Global methods (user-defined)
        self.global_methods = {}

        # Try to fix paths when necessary
        if not self.path['resources'].exists() or not self.path['web'].exists():
            self.autodetect_paths()
        # Second check
        if not self.path['resources'].exists() or not self.path['web'].exists():
            logger.error("Cannot determine paths.")

        if self.os == 'win32':
            self.win32_specific_config()
        elif self.os == 'darwin':
            self.darwin_specific_config()

    def autodetect_paths(self):
        package_dir = Path(__file__).resolve().parent.parent.parent
        app_dir = package_dir.parent

        # 1st hypothesis: module is loaded from sources
        if (app_dir / "setup.py").exists():
            # Chances are that we are using a development tree
            logger.warning("You seem to use a development tree at:\n%s." % app_dir)
            self.fix_paths(app_dir)
            return

        # 2nd hypothesis: we are running from an egg dir
        if (package_dir / "EGG-INFO").exists():
            # egg-info install. The locale/share/doc files are in the same dir.
            self.fix_paths(str(package_dir))
            return

        # 3rd hypothesis (Mac OS app): we are running from a packaged MacOS app,
        # and we can infer the installation directory from GTK_DATA_PREFIX
        # (XDG_DATA_DIRS would also be possible, but it would require splitting)

    def check_settings_directory(self):
        """Check if the settings directory is present, and create it if necessary.
        """
        if not self.path['settings'].is_dir():
            self.path['settings'].mkdir(parents=True)
            self.first_run=True
        else:
            self.first_run=False
        return True

    def parse_options(self):
        """Parse command-line options.
        """
        parser = ArgumentParser("Advene - annotate digital videos, exchange on the Net.")
        # %prog [options] [file.azp|file.xml|alias=uri]""")

        parser.add_argument("-d", "--debug", action="store_true",
                            help="Display debugging messages.")

        parser.add_argument("-i", "--info", action="store_true",
                            help="Display info messages.")

        parser.add_argument("-v", "--version", action="store_true",
                            help="Display version number and exit.")

        parser.add_argument("-s", "--settings-dir", dest="settings", action="store",
                            default=None, metavar="SETTINGSDIR",
                            help="Alternate configuration directory (default: ~/.config/advene).")

        parser.add_argument("-u", "--user-id", dest="userid", action="store",
                            default=None, metavar="LOGIN-NAME",
                            help="User name (used to set the author field of elements).")

        parser.add_argument("-n", "--dry-run", dest="dry_run", action="store_true")

        parser.add_argument("-o", "--option", dest="options", action="append",
                            default=None, metavar="OPTION-STRING",
                            help="Filter specific options, as a key=value item.")

        parser.add_argument("--no-embedded",
                            dest="embedded", action="store_false", default=True,
                            help="Do not embed the video player.")

        parser.add_argument("-p", "--player",
                            dest="player",
                            action="store",
                            # FIXME: we should register player plugins
                            # and use introspection, but plugin loading
                            # happens later.
                            choices=("dummy", "gstreamer", "gstrecorder"),
                            default=None,
                            help="Video player selection")

        parser.add_argument("-w", "--webserver-port", dest="port", action="store",
                            type=int, default=None, metavar="PORT_NUMBER",
                            help="Webserver port number (default 1234).")

        parser.add_argument("-m", "--webserver-mode", dest="mode", action="store",
                            type=int, default=None, metavar="WEBSERVER_MODE",
                            help="0: deactivated ; 1: threaded mode.")

        parser.add_argument("-f", "--filter",
                            dest="filter",
                            action="store",
                            default=None,
                            help="Export filter. If specified, input files will be automatically converted. Use 'help' to get a list of valid export filters.")

        parser.add_argument("positional_args",
                            nargs="*")
        self.options = parser.parse_args()
        self.args = self.options.positional_args
        # Convert the options array into a dict
        self.options.options = dict((i.split('=', 1) if '=' in i else (i, ""))
                                    for i in (self.options.options or []))
        if self.options.version:
            logger.warning(self.get_version_string())
            sys.exit(0)
        if self.options.info:
            logging.getLogger().setLevel(logging.INFO)
        if self.options.debug:
            self.debug = True
            logging.getLogger().setLevel(logging.DEBUG)

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

        # Force once svg to True, to ensure that most people will
        # have SVG enabled. If they choose to disable it
        # beforehand through Edit/Preferences, the setting will be
        # respected.
        if 'forced-svg' not in self.player:
            self.player['svg']=True
            self.player['forced-svg']=True
        return True

    def win32_specific_config(self):
        """Win32 specific configuration.
        """
        if self.os != 'win32':
            return
        self.player['dvd-device']='E:'

    def darwin_specific_config(self):
        """MacOS X specific tweaks.
        """
        if self.os != 'darwin':
            return

    def get_registry_value (self, subkey, name):
        """(win32) get a value from the registry.
        """
        if self.os != 'win32':
            return None
        import winreg
        value = None
        for hkey in winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER:
            try:
                reg = winreg.OpenKey(hkey, subkey)
                value, type_id = winreg.QueryValueEx(reg, name)
                winreg.CloseKey(reg)
            except winreg.error:
                #value=None
                pass
        return value

    def register_content_handler(self, handler):
        """Register a content handler.
        """
        # FIXME: check signature ?
        if handler not in self.content_handlers:
            self.content_handlers.append(handler)
        return True

    def register_global_method(self, method, name=None):
        """Register a global method.
        """
        # FIXME: check signature ?
        if name is None:
            name=method.__name__
        self.global_methods[name]=method
        return True

    def register_player(self, player):
        """Register a player plugin.
        """
        self.players[player.player_id] = player
        return True

    def get_target_types(self, *names):
        return [ self.target_entry[n]
                 for n in names ]

    def get_content_handler(self, mimetype):
        """Return a valid content handler for the given mimetype.

        Return None if no content handler is valid (should not happen, as
        TextContentHandler is builtin).
        """
        handlers = [ (c, c.can_handle(mimetype)) for c in self.content_handlers ]
        if not handlers:
            return None
        else:
            handlers.sort(key=operator.itemgetter(1), reverse=True)
            return handlers[0][0]

    def get_homedir(self):
        """Return the user's homedir.
        """
        return Path.home()

    def get_settings_dir(self):
        """Return the directory used to store Advene settings.
        """
        if self.options.settings is not None:
            return self.options.settings

        h = Path.home()

        if self.os == 'win32':
            dirname = h / 'advene3'
        elif self.os == 'darwin':
            dirname = h / 'Library' / 'Preferences' / 'Advene3'
        else:
            dirname = h / '.config' / 'advene'

        return dirname

    def read_preferences(self):
        """Update self.preferences from the preferences file.
        """
        prefs = self.read_preferences_file(d=self.preferences, name='advene')
        if prefs and 'path' in prefs:
            for k, v in prefs['path'].items():
                self.path[k] = Path(v)
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
            d = self.preferences
        preffile = self.advenefile(name+'.json', 'settings')
        try:
            f = open(preffile, "r", encoding='utf-8')
            prefs = json.load(f)
        except IOError:
            # No json file. Use old cPickle .prefs
            preffile=self.advenefile(name+'.prefs', 'settings')
            try:
                f = open(preffile, "r", encoding='utf-8')
            except IOError:
                return None
            try:
                prefs=pickle.load(f)
            except EOFError:
                logger.error("Cannot load old prefs file", exc_info=True)
                return None
        # There may be nested dicts in the structure, so use the deep_update utility
        deep_update(d, prefs)
        return prefs

    def save_preferences_file(self, d=None, name='advene'):
        """Generic preferences saving.

        Save as json.
        """
        if d is None:
            d = self.preferences
        preffile = Path(self.advenefile(name+'.json', 'settings'))
        dp = preffile.parent
        if not dp.is_dir():
            try:
                dp.mkdir(parents=True)
            except OSError as e:
                logger.error("Error: %s", str(e))
                return False
        try:
            f = open(str(preffile), "w", encoding='utf-8')
        except IOError:
            return False
        try:
            json.dump(d, f, indent=2, cls=JSONEncoder)
        except EOFError:
            logger.error("Cannot save prefs file", exc_info=True)
            return False
        return True

    def read_config_file (self):
        """Read the configuration file (advene.ini).
        """
        conffile = self.advenefile('advene.ini', 'settings')

        try:
            fd=open(conffile, "r", encoding='utf-8')
        except IOError:
            self.config_file=''
            return False

        logger.info("Reading configuration from %s", conffile)
        for li in fd:
            if li.startswith ("#"):
                continue
            obj = compile (li, conffile, 'single')
            try:
                exec(obj)
            except Exception as e:
                logger.error("Error in %s:\n%s", conffile, str(e))
        fd.close ()

        self.config_file=conffile

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
            if name in os.environ:
                id_ = os.environ[name]
                break
        return id_

    def advenefile(self, filename, category='resources', as_uri=False):
        """Return an absolute path for the given file.

        @param filename: a filename or a path to a file (tuple)
        @type filename: string or tuple
        @param category: the category of the file
        @type category: string

        @return: an absolute pathname
        @rtype: string
        """
        if isinstance(filename, (list, tuple)):
            filename  = Path(*filename)
        f = self.path[category] / filename
        if as_uri:
            return f.as_uri()
        else:
            return str(f)

    def get_version_string(self):
        """Return the version string.
        """
        git_version = None
        git_dir = Path(__file__).parents[3].joinpath('.git')
        if git_dir.is_dir():
            # We are in a git tree. Let's get the version information
            # from there if we can
            try:
                git_version = subprocess.check_output(["git", "--git-dir=%s" % git_dir.as_posix(), "describe"]).strip().decode('utf-8')
            except subprocess.CalledProcessError:
                pass
            if git_version is None:
                # Cannot call git. Let's try the manual approach...
                try:
                    with open((git_dir / "HEAD").as_posix(), "r") as f:
                        head = f.read().strip()
                    if head.startswith('ref: '):
                        ref = git_dir / head[5:]
                        # Using a ref.
                        with open(ref.as_posix(), "r") as f:
                            git_version = f.read().strip()
                    else:
                        # Not using a ref. Assume it is a sha1
                        git_version = head
                except FileNotFoundError:
                    pass
        if git_version is not None:
            v = "Advene development version %s" % git_version
        else:
            try:
                import advene.core.version as version
                v = "Advene v. %s release %s" % (version.version,
                                                 version.date)
            except ImportError:
                v = "Advene v. ??? (cannot get version number)"
        return v
    userid = property (fget=get_userid,
                       doc="Login name of the user")

    version_string = property(fget=get_version_string,
                              doc="Version string")

    def register_mimetype_file(self, fname):
        """Register a mimetype for a given extension.
        """
        for ext, t in mimetypes.read_mime_types(fname).items():
            mimetypes.add_type(t, ext)

    def fix_paths(self, maindir=None):
        """Adjust paths according to the given main directory.
        """
        if maindir is None:
            return
        maindir = Path(maindir)
        # We override any modification that could have been made in
        # .advenerc. Rationale: if the .advenerc was really correct, it
        # would have set the correct paths in the first place.
        logger.info("Overriding 'resources', 'locale', 'advene' and 'web' config paths")
        self.path['resources'] = maindir / 'share'
        self.path['locale'] = maindir / 'locale'
        self.path['web'] = maindir  / 'share' / 'web'
        self.path['advene'] = maindir

        if not self.path['shotdetect'].exists():
            if self.os == 'win32':
                sdname='shotdetect.exe'
            else:
                sdname='shotdetect'
            sd = find_in_path(sdname)
            if sd is not None:
                self.path['shotdetect'] = sd
            else:
                sd = Path(self.advenefile(sdname, 'resources'))
                if sd.exists():
                    self.path['shotdetect'] = sd

data = Config ()
data.check_settings_directory()
data.read_preferences()
# Config file (advene.ini) may override settings from preferences
data.read_config_file ()
# We process options last, so that command-line options can
# override preferences and .ini file.
data.process_options()
