#!/usr/bin/python 

import sys
from distutils.core import setup
from distutils.extension import Extension
import os
import string
import re
import sys

# We define the main script name here (file in bin), since we have to change it for MacOS X
SCRIPTNAME='advene'

def check_changelog(maindir, version):
    """Check that the changelog for maindir matches the given version."""
    f=open(os.path.join( maindir, "debian", "changelog" ), 'r')
    l=f.readline()
    f.close()
    if not l.startswith('advene (' + version + ')'):
        print "The changelog does not seem to correspond to version " + version
        print l
        print "Update either the changelog or the lib/advene/core/version.py file"
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
    platform_options['console'] = [ "bin/advene" ]
    platform_options['options'] = {
	"py2exe": {
	    "includes": "pango,pangocairo,cairo,atk,gtk,gtk.keysyms,gobject,xml.sax.drivers2.drv_pyexpat,encodings,encodings.latin_1,encodings.utf_8,encodings.cp850,encodings.cp437,encodings.cp1252,encodings.utf_16_be," + ",".join( get_plugin_list('plugins') + get_plugin_list('gui', 'plugins') + get_plugin_list('gui', 'views') + get_plugin_list('gui', 'edit') ),
	    "excludes": [ "Tkconstants","Tkinter","tcl" ],
	    "dll_excludes": ["libvlc.dll","libvlc-control.dll"],
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
                    includes="pango,pangocairo,cairo,atk,gtk,gtk.keysyms,gobject,xml.sax.drivers2.drv_pyexpat,encodings,encodings.latin_1,encodings.utf_8,encodings.cp850,encodings.cp437,encodings.cp1252,encodings.utf_16_be,cPickle,optparse,sets,pprint,cgi,webbrowser,xml.dom.ext.reader.PyExpat,sgmllib,zipfile,shutil,sched,imghdr,BaseHTTPServer,Cookie,ConfigParser,xmlrpclib,Queue,csv,filecmp," + ",".join( get_plugin_list('plugins') + get_plugin_list('gui', 'plugins') + get_plugin_list('gui', 'views') + get_plugin_list('gui', 'edit') ),
                    argv_emulation=True,
                    site_packages=True,
                    #resources=['resources/License.txt'],
                    #frameworks='foo.framework',
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
    l=[]
    def ispackage(pl, dirname, fnames):
        if sys.platform == 'linux2' and ('cherrypy' in dirname or dirname.endswith('simpletal')):
            # On linux (at least, Debian and Ubuntu), cherrypy and
            # simpletal are packaged. So do not consider them in the
            # packages list.
            fnames[:]=[]
        elif '__init__.py' in fnames:
            l.append(dirname)
    os.path.walk('lib', ispackage, l)
    res=[ ".".join(name.split(os.path.sep)[1:]) for name in l ]
    return res

                 
def generate_data_dir(dir_, prefix="", postfix=""):
    """Return a structure suitable for datafiles from a directory.

    It will return a sequence of (directory, files) corresponding to the
    data in the given directory.

    prefix and postfix are dumbly added to dirname, so do not forget
    the trailing / for prefix, and leading / for postfix if necessary.
    """
    l = []
    installdir=prefix+dir_+postfix
    def store(pl, dirname, fnames):
	if dirname.find('.svn') < 0 and fnames:
            if dirname.startswith(dir_):
                installdirname=dirname.replace(dir_, installdir, 1)
            pl.append((installdirname, [ absf
                                         for absf in [ os.path.sep.join((dirname,f)) 
                                                       for f in fnames  ]
                                         if not os.path.isdir(absf) ]))
    os.path.walk(dir_, store, l)
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
        raise Exception("""**WARNING** You should generate the locales with "cd po; make mo".""")
    if sys.platform == 'linux2':
        # Install specific data files
        r.append( ( 'share/applications', [ 'debian/advene.desktop' ] ) )
    return r

myname = "Olivier Aubert"
myemail = "olivier.aubert@liris.cnrs.fr"

setup (name = "advene",
       version = _version,
       description = "Annotate DVds, Exchange on the NEt",
       keywords = "dvd,video,annotation",
       author = "Advene project team",
       author_email = "advene@liris.cnrs.fr",
       maintainer = myname,
       maintainer_email = myemail,
       url = "http://liris.cnrs.fr/advene/",
       license = "GPL",
       long_description = """Annotate DVds, Exchange on the NEt

 The Advene (Annotate DVd, Exchange on the NEt) project is aimed
 towards communities exchanging discourses (analysis, studies) about
 audiovisual documents (e.g. movies) in DVD format. This requires that
 audiovisual content and hypertext facilities be integrated, thanks to
 annotations providing explicit structures on  audiovisual streams, upon
 which hypervideo documents can be engineered.
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
    'Development Status :: 3 - Alpha',
    'License :: OSI Approved :: GNU General Public License (GPL)',
    'Programming Language :: Python',
    'Intended Audience :: End Users/Desktop',
    'Operating System :: OS Independent',
    'Topic :: Multimedia :: Video :: Non-Linear Editor'
    ],
 
    **platform_options
)
