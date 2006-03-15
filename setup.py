#!/usr/bin/python 

import sys
from distutils.core import setup
from distutils.extension import Extension

if sys.platform == 'win32':
    import py2exe

import os, string, re, sys

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
           
def build_doc():
    print "Do not forget to get the user manual from the TWiki"

def get_packages_list():
    """Recursively find packages in lib.

    Return a list of packages (dot notation) suitable as packages parameter
    for distutils.
    """
    l=[]
    def ispackage(pl, dirname, fnames):
        if '__init__.py' in fnames:
            l.append(dirname)
    os.path.walk('lib', ispackage, l)
    return [ ".".join(name.split(os.path.sep)[1:]) for name in l ]

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
    build_doc()
    # On Win32, we will install data files in
    # \Program Files\Advene\share\...
    # On Unix, it will be
    # /usr/share/advene/...
    if sys.platform == 'win32':
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
        print """**WARNING** You should generate the locales with "cd po; make mo"."""
    return r

myname = "Olivier Aubert"
myemail = "olivier.aubert@liris.cnrs.fr"

if sys.platform == 'win32':
    opts = {
	"py2exe": {
	    "includes": "pango,pangocairo,cairo,atk,gtk,gobject,xml.sax.drivers2.drv_pyexpat,encodings,encodings.latin_1,encodings.utf_8,encodings.cp850,encodings.cp437,encodings.cp1252,encodings.utf_16_be,PngImagePlugin",
	    "excludes": [ "Tkconstants","Tkinter","tcl" ],
	    #         "dll_excludes": ["iconv.dll","intl.dll","libatk-1.0-0.dll", 
	    #                          "libgdk_pixbuf-2.0-0.dll","libgdk-win32-2.0-0.dll",
	    #                          "libglib-2.0-0.dll","libgmodule-2.0-0.dll",
	    #                          "libgobject-2.0-0.dll","libgthread-2.0-0.dll",
	    #                          "libgtk-win32-2.0-0.dll","libpango-1.0-0.dll",
	    #                          "libpangowin32-1.0-0.dll"],
	    
         }
	}
else:
    opts = {}

setup (name = "advene",
       version = get_version(),
       options = opts,
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

       scripts = ['bin/advene'],
       
       console = [ "bin/advene" ],

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
)
