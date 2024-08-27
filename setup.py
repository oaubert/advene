#! /usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

import os
from pathlib import Path
import re
from setuptools import setup, find_packages
import sys

# We define the main script name here (file in bin), since we have to change it for MacOS X
SCRIPTNAME='advene'

def check_changelog(maindir, version):
    """Check that the changelog for maindir matches the given version."""
    with open(os.path.join( maindir, "CHANGES.txt" ), 'r') as f:
        l=f.readline()
    if not l.startswith('advene (' + version + ')'):
        logger.warning("*" * 80 + "\nThe CHANGES.txt does not seem to match version %s\n%s\nUpdate either the CHANGES.txt or the lib/advene/core/version.py file", version, l)
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
    """Get the version number of the package.
    """
    maindir = Path(__file__).absolute().parent
    versionfile = maindir / "lib" / "advene" / "core" / "version.py"
    info = re.findall(r"version=.(\d+\.\d+)", versionfile.read_text())
    if info:
        version = info[0]
    else:
        raise Exception("Unable to determine advene version number.")
    check_changelog(maindir, version)
    return version

_version=get_version()

platform_options={}

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
    if not os.path.isdir("locale"):
        logger.warning("""**WARNING** Generating the locales with "cd po; make mo".""")
        os.system("pwd; cd po; make mo")
    if os.path.isdir("locale"):
        r.extend(generate_data_dir("locale", prefix=prefix))
    else:
        logger.warning("""**WARNING** Cannot find locale directory.""")
    if sys.platform.startswith('linux'):
        # Install specific data files
        r.append( ( 'share/applications', [ 'share/advene.desktop' ] ) )
    return r

myname = "Olivier Aubert"
myemail = "contact@olivieraubert.net"

# See pyproject.toml for static metadata
setup (version = _version,
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

       scripts = [ 'bin/%s' % SCRIPTNAME, 'bin/advene_import', 'bin/advene_export' ],

       data_files = generate_data_files(),

    **platform_options
)
