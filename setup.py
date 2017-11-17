#! /usr/bin/env python3

import sys
from distutils.core import setup
from distutils import log
from setuptools import find_packages
import os

# We define the main script name here (file in bin), since we have to change it for MacOS X
SCRIPTNAME='advene'

def check_changelog(maindir, version):
    """Check that the changelog for maindir matches the given version."""
    with open(os.path.join( maindir, "CHANGES.txt" ), 'r') as f:
        l=f.readline()
    if not l.startswith('advene (' + version + ')'):
        log.error("The CHANGES.txt does not seem to match version %s\n%s\nUpdate either the CHANGES.txt or the lib/advene/core/version.py file", version, l)
        sys.exit(1)
    return True

def get_plugin_list(*package):
    """Return a plugin list from the given package.

    package is in fact a list of path/module path elements.
    No recursion is done.
    """
    package= [ 'advene' ] + list(package)
    path=os.path.sep.join(package)
    prefix='.'.join(package)
    plugins=[]
    d=os.path.join('lib', path)
    if not os.path.exists(d):
        raise Exception("%s does not match a directory (%s does not exist)" % (prefix, d))
    for n in os.listdir(d):
        name, ext = os.path.splitext(n)
        if ext != '.py':
            continue
        # Poor man's grep.
        if [ l for l in  open(os.path.join(d, n)).readlines() if 'def register' in l ]:
            # It may be a plugin. Include it.
            plugins.append('.'.join((prefix, name)))
    return plugins

def get_version():
    """Get the version number of the package."""
    maindir = os.path.dirname(os.path.abspath(sys.argv[0]))
    if os.path.exists(os.path.join(maindir, "setup.py")):
        # Chances are that we were in a development tree...
        libpath=os.path.join(maindir, "lib")
        sys.path.insert (0, libpath)
        import advene.core.version
        version=advene.core.version.version
    else:
        raise Exception("Unable to determine advene version number.")
    check_changelog(maindir, version)
    return version

_version=get_version()

platform_options={}

if sys.platform == 'win32':
    import py2exe
    # to be able to import gst
    import pygst
    pygst.require('0.10')

    platform_options['windows'] = [ "bin/advene" ]
    platform_options['options'] = {
	"py2exe": {
	    "includes": "email.header,pango,pangocairo,cairo,atk,gtk,gio,pygst,gst,gtk.keysyms,gobject,encodings,encodings.latin_1,encodings.utf_8,encodings.cp850,encodings.cp437,encodings.cp1252,encodings.utf_16_be," + ",".join( get_plugin_list('plugins') + get_plugin_list('gui', 'plugins') + get_plugin_list('gui', 'views') + get_plugin_list('gui', 'edit') ),
	    "excludes": [ "Tkconstants","Tkinter","tcl" ],
	    "dll_excludes": ["libgstvideo-0.10.dll","libgstpbutils-0.10.dll","libgstinterfaces-0.10.dll","libgstdataprotocol-0.10.dll","libgstbase-0.10.dll","libgstnet-0.10.dll","libgstcontroller-0.10.dll","libgstaudio-0.10.dll","libgsttag-0.10.dll","libgstreamer-0.10.dll","libvlc.dll","libvlc-control.dll", "libglade-2.0-0.dll"],
	    #         		 ["iconv.dll","intl.dll","libatk-1.0-0.dll",
	    #                          "libgdk_pixbuf-2.0-0.dll","libgdk-win32-2.0-0.dll",
	    #                          "libglib-2.0-0.dll","libgmodule-2.0-0.dll",
	    #                          "libgobject-2.0-0.dll","libgthread-2.0-0.dll",
	    #                          "libgtk-win32-2.0-0.dll","libpango-1.0-0.dll",
	    #                          "libpangowin32-1.0-0.dll"],

         }
	}
elif sys.platform == 'darwin':
    import py2app
    SCRIPTNAME='advene_gui.py'
    platform_options['app'] = [ 'bin/%s' % SCRIPTNAME ]
    platform_options['options'] = dict(py2app=dict(
                    iconfile='mac/Advene.icns',
                    #includes=",".join( [ l.strip() for l in open('mac_includes.txt') ]),
                    includes="AppKit,_hashlib,hashlib,email.header,pango,cairo,ctypes,gtk,gtk.keysyms,atk,gobject,encodings,encodings.latin_1,encodings.utf_8,encodings.cp850,encodings.cp437,encodings.cp1252,encodings.utf_16_be,cPickle,optparse,sets,pprint,cgi,webbrowser,sgmllib,zipfile,shutil,sched,imghdr,BaseHTTPServer,Cookie,ConfigParser,xmlrpclib,Queue,csv,filecmp," + ",".join( get_plugin_list('plugins') + get_plugin_list('gui', 'plugins') + get_plugin_list('gui', 'views') + get_plugin_list('gui', 'edit') ),
                    argv_emulation=True,
                    site_packages=True,
                    #frameworks='Cairo.framework,Glib.framework,Gtk.framework',
                    plist=dict(
                       CFBundleName               = "Advene",
                       CFBundleShortVersionString = _version,     # must be in X.X.X format
                       CFBundleGetInfoString      = "Advene " + _version,
                       CFBundleExecutable         = "Advene",
                       CFBundleIdentifier         = "com.oaubert.advene",
                   ),
                 )
               )

def get_packages_list():
    """Recursively find packages in lib.

    Return a list of packages (dot notation) suitable as packages parameter
    for distutils.
    """
    if 'linux' in sys.platform:
        return find_packages('lib', exclude=["cherrypy.*"])
    else:
        return find_packages('lib')

def generate_data_dir(dir_, prefix="", postfix=""):
    """Return a structure suitable for datafiles from a directory.

    It will return a sequence of (directory, files) corresponding to the
    data in the given directory.

    prefix and postfix are dumbly added to dirname, so do not forget
    the trailing / for prefix, and leading / for postfix if necessary.
    """
    l = []
    installdir=prefix+dir_+postfix
    for dirname, dnames, fnames in os.walk(dir_):
        if fnames:
            if dirname.startswith(dir_):
                installdirname=dirname.replace(dir_, installdir, 1)
            l.append((installdirname, [ absf
                                        for absf in [ os.path.sep.join((dirname,f))
                                                      for f in fnames  ]
                                        if not os.path.isdir(absf) ]))
    return l

def generate_data_files():
    # On Win32, we will install data files in
    # \Program Files\Advene\share\...
    # On MacOS X, it will be in Advene.app/Contents/Resources
    # On Unix, it will be
    # /usr/share/advene/...
    if sys.platform == 'win32' or sys.platform == 'darwin':
        prefix=''
        postfix=''
    else:
        prefix="share"+os.path.sep
        postfix=os.path.sep+"advene"
    r=generate_data_dir("share", postfix=postfix)
    r.extend(generate_data_dir("doc", prefix=prefix, postfix=postfix))
    if os.path.isdir("locale"):
        r.extend(generate_data_dir("locale", prefix=prefix))
    else:
        log.warn("""**WARNING** You should generate the locales with "cd po; make mo".""")
    if sys.platform.startswith('linux'):
        # Install specific data files
        r.append( ( 'share/applications', [ 'share/advene.desktop' ] ) )
    return r

myname = "Olivier Aubert"
myemail = "contact@olivieraubert.net"

setup (name = "advene",
       version = _version,
       description = "Annotate DVds, Exchange on the NEt",
       keywords = "dvd,video,annotation",
       author = "Advene project team",
       author_email = "contact@olivieraubert.net",
       maintainer = myname,
       maintainer_email = myemail,
       url = "http://www.advene.org/",
       license = "GPL",
       long_description = """Annotate DVds, Exchange on the NEt

 The Advene (Annotate DVd, Exchange on the NEt) project is aimed
 towards communities exchanging discourses (analysis, studies) about
 audiovisual documents (e.g. movies) in DVD format. This requires that
 audiovisual content and hypertext facilities be integrated, thanks to
 annotations providing explicit structures on  audiovisual streams, upon
 which hypervideo documents can be engineered.
 .
 The cross-platform Advene application allows users to easily
 create comments and analyses of video comments, through the
 definition of time-aligned annotations and their mobilisation
 into automatically-generated or user-written comment views (HTML
 documents). Annotations can also be used to modify the rendition
 of the audiovisual document, thus providing virtual montage,
 captioning, navigation... capabilities. Users can exchange their
 comments/analyses in the form of Advene packages, independently from
 the video itself.
 .
 The Advene framework provides models and tools allowing to design and reuse
 annotations schemas; annotate video streams according to these schemas;
 generate and create Stream-Time Based (mainly video-centred) or User-Time
 Based (mainly text-centred) visualisations of the annotations. Schemas
 (annotation- and relation-types), annotations and relations, queries and
 views can be clustered and shared in units called packages. Hypervideo
 documents are generated when needed, both from packages (for annotation and
 view description) and DVDs (audiovisual streams).
""",

       package_dir = {'': 'lib'},

       packages = get_packages_list(),

       scripts = [ 'bin/%s' % SCRIPTNAME ],

       data_files = generate_data_files(),

       classifiers = [
    'Environment :: X11 Applications :: GTK',
    'Environment :: Win32 (MS Windows)',
    'Development Status :: 5 - Production/Stable',
    'License :: OSI Approved :: GNU General Public License (GPL)',
    'Programming Language :: Python',
    'Intended Audience :: End Users/Desktop',
    'Operating System :: OS Independent',
    'Topic :: Multimedia :: Video :: Non-Linear Editor'
    ],

    **platform_options
)
