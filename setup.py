#!/usr/bin/python 

from distutils.core import setup
from distutils.dist import Distribution
from distutils.extension import Extension

import os, string, re, sys

def get_version():
    """Get the version number of the package."""
    maindir = os.path.dirname(os.path.abspath(sys.argv[0]))
    if os.path.exists(os.sep.join((maindir, "setup.py"))):
        # Chances are that we were in a development tree...
        libpath=os.sep.join((maindir, "lib"))
        sys.path.insert (0, libpath)
        import advene.core.version
        version=advene.core.version.version
    else:
        raise Exception("Unable to determine advene version number.")
    check_changelog(maindir, version)
    return version

def check_changelog(maindir, version):
    """Check that the changelog for maindir matches the given version."""
    f=open(os.sep.join( (maindir, "debian", "changelog") ), 'r')
    l=f.readline()
    f.close()
    if not l.startswith('advene (' + version + ')'):
        print "The changelog does not seem to correspond to version " + version
        print l
        print "Update either the changelog or the lib/advene/core/version.py file"
        sys.exit(1)
    return True
           
def build_doc():
    try:
        import docutils.core
    except:
        print "Cannot build documentation. Install docutils package."
        return

    source=os.path.sep.join( ('doc', 'user.txt') )
    dest=os.path.sep.join( ('share', 'web', 'user.html') )

    if not os.path.exists(dest) or (os.path.getmtime(source) >
                                    os.path.getmtime(dest)):
        print "Generating HTML user documentation."
        docutils.core.publish_file(source_path=source, destination_path=dest,
                                   writer_name='html')

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
    r=generate_data_dir("share", postfix=os.path.sep+"advene")
    r.extend(generate_data_dir("doc", prefix="share"+os.path.sep, postfix=os.path.sep+"advene"))
    if os.path.isdir("locale"):
        r.extend(generate_data_dir("locale", prefix="share"+os.path.sep))
    else:
        print """**WARNING** You should generate the locales with "cd po; make mo"."""
    return r

myname = "Olivier Aubert"
myemail = "olivier.aubert@liris.cnrs.fr"

setup (name = "advene",
       version = get_version(),
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
