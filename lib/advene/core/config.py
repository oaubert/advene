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

class Config(object):
    """Configuration information, platform specific.

    It is possible to override the configuration variables in a config
    file ($HOME/.advene/advene.ini on Linux/MacOSX,
    UserDir/advene/advene.ini on Windows) with a python syntax
    (I{warning}, it is evaluated so harmful instructions in it can do
    damage).

    Example advene.ini file::

      config.data.path['vlc']='/usr/local/src/vlc-0.5.0'
      config.data.path['plugins']='/usr/local/src/vlc-0.5.0'
      config.data.path['advene']='/usr/local/bin'

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
        if os.sys.platform in ( 'win32', 'darwin' ):
            self.os=os.sys.platform
        elif 'linux' in os.sys.platform:
            self.os='linux'
        else:
            print "Warning: undefined platform: ", os.sys.platform
            self.os=os.sys.platform

        if self.os != 'win32':
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
        else:
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

        self.path['settings'] = self.get_settings_dir()

        # Web-related preferences
        self.web = {
            'edit-width': 80,
            'edit-height': 25,
            }

        self.namespace = "http://experience.univ-lyon1.fr/advene/ns/advenetool"

        # These files are stored in the resources directory
        self.templatefilename = "template.xml"
        self.gladefilename = "advene.glade"

        # Generic options
	# They are automatically saved across sessions
	# in ~/.advene/advene.prefs
        self.preferences = {
            # Various sizes of windows.
            'windowsize': { 'main': (800, 600),
                            'editpopup': (640,480),
                            'evaluator': (800, 600),
                            'relationview': (640, 480),
                            'sequenceview': (640, 480),
                            'timelineview': (800, 400),
                            'transcriptionview': (640, 480),
                            'transcribeview': (640, 480),
                            'treeview': (800, 600),
                            'browserview': (800, 600),
			    'weblogview': (800, 600),
                            },
            'gui': { 'popup-textwidth': 40 },
            # File history
            'history': [],
            'history-size-limit': 5,
	    # User-defined paths. Will overwrite 
	    # config.data.path items
	    'path': {},
            'embed-logwindow': False,
            }

        # Player options
        self.player_preferences = {
            'osdtext': True,
            'default_caption_duration': 3000,
            'time_increment': 2000,
            }

        # Player options
        self.player = {
            'plugin': 'vlcnative',
            'embedded': True,
            'name': 'vlc',
            'vout': 'default',
            'osdfont': '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf',
            'verbose': None, # None, 0, 1, 2
            'snapshot': True,
            'caption': True,
            'snapshot-dimensions': (160,100),
            'snapshot-chroma': 'RV32',
            'dvd-device': 'dvd:///dev/dvd',
            }

        self.webserver = {
            'port': 1234,
            # Whether to launch the HTTP server in the gtk interface
            # 0 for no, 1 for gtk_input, 2 for threading
            'mode': 1,
            # 'admin' or 'raw'
            'displaymode': 'raw',
            }
        # Threading does not work correctly on Win32. Use gtk_input
        # method.
        if self.os == 'win32':
            self.webserver['mode'] = 1

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

	# Drag and drop parameters
        self.target_type = {
            'annotation' : 42,
            'rule' : 43,
            'view': 44,
            'schema': 45,
            'annotation-type': 46,
            'relation-type': 47,
            'relation': 48,
            }
        self.drag_type={}
        for t in self.target_type:
            self.drag_type[t] = [ ( "application/x-advene-%s-uri" % t,
                                    0,
                                    self.target_type[t] ) ]

	# Content-handlers
	self.content_handlers = []

	# Global methods (user-defined)
	self.global_methods = []

        if self.os == 'win32':
            self.win32_specific_config()

    def win32_specific_config(self):
        if self.os != 'win32':
            return
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

    def get_registry_value (self, subkey, name):
        if self.os != 'win32':
            return None
        try:
            a=_winreg.HKEY_LOCAL_MACHINE
        except NameError:
            import _winreg
        value = None
        for hkey in _winreg.HKEY_LOCAL_MACHINE, _winreg.HKEY_CURRENT_USER:
            try:
                reg = _winreg.OpenKey(hkey, subkey)
                value, type_id = _winreg.QueryValueEx(reg, name)
                _winreg.CloseKey(reg)
            except _winreg.error:
                pass
        return value

    def register_content_handler(self, handler):
	# FIXME: check signature ?
	if not handler in self.content_handlers:
	    self.content_handlers.append(handler)
	return True

    def register_global_method(self, method):
	# FIXME: check signature ?
	if not method in self.global_methods:
	    self.global_methods.append(method)
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
	    l.sort(lambda a, b: cmp(b[1], a[1]))
	    return l[0][0]

    def get_homedir(self):
        h=None
        try:
            h=os.path.expanduser('~')
        except:
            if os.environ.has_key('HOME'):
                h=os.environ['HOME']
            elif os.environ.has_key('HOMEPATH'):
                # Windows
                h=os.path.join(os.environ['HOMEDRIVE'],
                               os.environ['HOMEPATH'])
            else:
                raise Exception ('Unable to find homedir')
        return h

    def get_settings_dir(self):
        """Return the directory used to store Advene settings.
        """
        if self.os == 'win32':
            dirname='advene'
        else:
            dirname='.advene'

        return os.path.join( self.get_homedir(), dirname )

    def read_preferences(self):
        preffile=self.advenefile('advene.prefs', 'settings')
        try:
            f = open(preffile, "r")
        except IOError:
            return False
        try:
            prefs=cPickle.load(f)
        except:
            return False
        self.preferences.update(prefs)
	if prefs.has_key('path'):
	    self.path.update(prefs['path'])
        return True

    def save_preferences(self):
        preffile=self.advenefile('advene.prefs', 'settings')
        d=os.path.dirname(preffile)
        if not os.path.isdir(d):
            try:
                os.mkdir(d)
            except OSError, e:
                print "Error: ", str(e)
                return False
        try:
            f = open(preffile, "w")
        except IOError:
            return False
        try:
            cPickle.dump(self.preferences, f)
        except:
            return False
        return True

    def read_config_file (self):
        """Read the configuration file (advene.ini).
        """
        c=[ a for a in sys.argv if a.startswith('-c') ]
        if c:
            if len(c) > 1:
                print "Error: multiple config files are given on the command line"
                sys.exit(1)
            sys.argv.remove(c[0])
            conffile=c[0][2:]
        else:
            conffile=self.advenefile('advene.ini', 'settings')

        try:
            file = open(conffile, "r")
        except IOError:
            self.config_file=''
            return False

        print "Reading configuration from %s" % conffile
        config=sys.modules['advene.core.config']
        for li in file:
            if li.startswith ("#"):
                continue
            object = compile (li, conffile, 'single')
            try:
                exec object
            except Exception, e:
                print "Error in %s:\n%s" % (conffile, str(e))
        file.close ()

        self.config_file=conffile

    def get_player_args (self):
        """Build the VLC player argument list.

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
        if filters != []:
            # Some filters have been defined
            args.extend (['--vout-filter', ":".join(filters)])
        return [ str(i) for i in args ]

    def get_userid (self):
        """Return the userid (login name).

        @return: the user id
        @rtype: string
        """
        # FIXME: allow override via advene.ini
        id = "Undefined id"
        for name in ('USER', 'USERNAME', 'LOGIN'):
            if os.environ.has_key (name):
                id = os.environ[name]
                break
        return id

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

    userid = property (fget=get_userid,
                       doc="Login name of the user")
    player_args = property (fget=get_player_args,
                            doc="List of arguments for the VLC player")

data = Config ()
data.read_preferences()
# Config file (advene.ini) may override settings from preferences
data.read_config_file ()
