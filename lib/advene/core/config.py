"""Configuration module.

It provides data, an instance of Config class.

It is meant to be used this way::

  import config
  print "Userid: %s" % config.data.userid

@var data: an instance of Config (Singleton)
"""
import sys
import os

class Config(object):
    """Configuration information, platform specific.

    It is possible to override the configuration variables in a config
    file ($HOME/.advenerc), with a python syntax (I{warning}, it is
    evaluated so harmful instructions in it can do damage).

    Example .advenerc file::

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
    
    @ivar orb_max_tries: maximum number of tries for VLC launcher
    @type orb_max_tries: int
    """

    def __init__ (self):
        if os.sys.platform == 'win32':
            self.os='win32'
        else:
            self.os='linux'

        self.path = {
            # VLC binary path
            'vlc': '/usr/bin',
            # VLC plugins path
            'plugins': '/usr/lib/vlc',
            # Advene modules path
            'advene': '/usr/lib/advene',
            # Advene resources (.glade, template, ...) path
            'resources': '/usr/share/advene',
            # Advene data files default path
            'data': '/tmp',
            # Imagecache save directory
            'imagecache': '/tmp/advene',
            # Web data files
            'web': '/usr/share/advene/web',
            }

        # Web-related preferences
        self.web = {
            'edit-width': 80,
            'edit-height': 25,
            }
        
        self.namespace = "http://experience.univ-lyon1.fr/advene/ns/advenetool"

        # These files are stored in the resources directory
        self.templatefilename = "template.xml"
        self.gladefilename = "advene.glade"

        # GUI options
        self.preferences = {
            'osdtext': True,
            'default_caption_duration': 3000,
            'time_increment': 2000,
            }

        # Player options
        self.player = {
            'name': 'vlc',
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
            'mode': 2
            }
        # Global context options
        self.namespace_prefix = {'advenetool': self.namespace,
                                 'dc': 'http://purl.org/dc/elements/1.1/'}

        # Internal options. These should generally not be modified.

        # Used to memorize the volume level
        self.sound_volume=0
        

        # How many times do we try to read the iorfile before quitting ?
        self.orb_max_tries=7
        # Update delay for position marker in views (in ms)
        self.slow_update_delay=200

        # DragNDrop data
        self.TARGET_TYPE_ANNOTATION=42
        self.annotation_drag_type=[ ( "application/x-advene-annotation-id",
                                      0,
                                      self.TARGET_TYPE_ANNOTATION ) ]


    def read_config_file (self):
        """Read the configuration file ~/.advenerc.
        """
        # FIXME: The conffile name could be a command-line option
        if os.environ.has_key('HOME'):
            homedir=os.environ['HOME']
            file='.advenerc'
        elif os.environ.has_key('HOMEDRIVE'):
            # Windows
            homedir=os.sep.join((os.environ['HOMEDRIVE'],
                                 os.environ['HOMEPATH']))
            file='advene.ini'
        else:
            raise Exception ('Unable to find homedir')

        conffile=os.sep.join((homedir, file))
        try:
            file = open(conffile, "r")
        except IOError:
            self.config_file=''
            return False
        
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
        args = [ '--intf', 'corba', '--plugin-path', self.path['plugins'] ]
        if self.player['verbose'] is not None:
            args.append ('--verbose')
            args.append (self.player['verbose'])
        filters=[]
        if self.player['snapshot']:
            filters.append("clone")
            args.extend (['--clone-vout-list', 'snapshot,x11',
                          '--snapshot-width',
                          self.player['snapshot-dimensions'][0],
                          '--snapshot-height',
                          self.player['snapshot-dimensions'][1],
                          '--snapshot-chroma', self.player['snapshot-chroma']
                          ])
        if filters != []:
            # Some filters have been defined
            args.extend (['--filter', ":".join(filters)])
        return [ str(i) for i in args ]

    def get_userid (self):
        """Return the userid (login name).

        @return: the user id
        @rtype: string
        """
        # FIXME: allow override via .advenerc
        id = "Undefined id"
        for name in ('USER', 'USERNAME', 'LOGIN'):
            if os.environ.has_key (name):
                id = os.environ[name]
                break
        return id

    def get_typelib (self):
        """Return the name (absolute path) of the typelib file.

        @return: the absolute pathname of the typelib
        @rtype: string
        """
        if sys.platform == 'win32':
            file='MediaControl.dll'
        else:
            file='MediaControl.so'
        return self.advenefile(file, category='advene')

    def get_iorfile (self):
        """Return the absolute name of the IOR file.

        @return: the absolute pathname of the IOR file
        @rtype: string
        """
        if sys.platform == 'win32':
            if os.environ.has_key ('TEMP'):
                d = os.environ['TEMP']
            else:
                d = "\\"
        else:
            d="/tmp"
        return os.path.join (d, 'vlc-ior.ref')

    def advenefile(self, filename, category='resources'):
        """Return an absolute pathname for the given file.

        @return: an absolute pathname
        @rtype: string
        """
        return os.sep.join ( ( self.path[category], filename ) )

    userid = property (fget=get_userid,
                       doc="Login name of the user")
    typelib = property (fget=get_typelib,
                        doc="Typelib module library")
    iorfile = property (fget=get_iorfile,
                        doc="Location of the IOR file for the VLC corba interface")
    player_args = property (fget=get_player_args,
                            doc="List of arguments for the VLC player")

data = Config ()
data.read_config_file ()
#print "Read config file %s" % data.config_file
