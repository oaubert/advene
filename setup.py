#!/usr/bin/python 

from distutils.core import setup
from distutils.dist import Distribution
from distutils.extension import Extension

import os, string, re, sys

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
       version = "0.4",
       description = "Annotate DVds, Exchange on the NEt",
       keywords = "dvd,video,annotation",
       author = myname,
       author_email = myemail,
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
