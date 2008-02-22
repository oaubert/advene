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
"""OpenDocument style package format.
==================================

  This format is a transition from the plain xml Advene package format
  to a richer format inspired by OpenDocument (zip file with data + metadata).

  It is intented as a temporary measure before the complete rewrite of
  the Advene package format.

  File extension: .azp (Advene Zip Package) which will be followed by
  .aod (Advene OpenDocument)

  General layout::

    foo.azp/
            mimetype
            content.xml
            resources/
            meta.xml (optional)
            META-INF/manifest.xml

  Contents::

    mimetype: application/x-advene-zip-package
    content.xml: the previous package.xml format
    resources/: associated resources,
                available through the TALES expression /package/resources/...
    meta.xml: metadata (cf OpenDocument specification)
    META-INF/manifest.xml : Manifest (package contents)
  """

import zipfile
import os
import sys
import tempfile
import re
import shutil
import urllib
from advene.model.exception import AdveneException
from advene.model.resources import Resources
import mimetypes

import advene.util.ElementTree as ET

from gettext import gettext as _

# In some cases, sys.getfilesystemencoding returns None
_fs_encoding = sys.getfilesystemencoding() or 'ascii'

# Some constants
MIMETYPE='application/x-advene-zip-package'
# OpenDocument manifest file
MANIFEST="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
ET._namespace_map[MANIFEST]='manifest'

class ZipPackage:
    # Global method for cleaning up
    tempdir_list = []

    def cleanup():
        """Remove the temp. directories used during the session.

        No check is done to see wether it is in use or not. This
        method is intended to be used at the end of the application,
        to clean up the mess.
        """
        for d in ZipPackage.tempdir_list:
            # FIXME: there should be a way to determine wether it
            # is still used or not.
            print "Cleaning up %s" % d
            if os.path.isdir(d.encode(_fs_encoding)):
                shutil.rmtree(d, ignore_errors=True)

    cleanup = staticmethod(cleanup)

    def __init__(self, uri=None):
        self.uri = None
        # Temp. directory, a unicode string
        self._tempdir = None
        self.file_ = None

        if uri is not None:
            if uri.startswith('file:///'):
                n=uri[7:]
            else:
                n=uri
            if os.path.exists(n):
                # It is a real filename
                self.uri = uri
                self.file_ = n
            elif re.match('^[a-zA-Z]:', n):
                # Windows drive: notation. Convert it to
                # a more URI-compatible syntax
                self.uri=uri
                self.file_ = urllib.pathname2url(n)
            elif re.search('/[a-zA-Z]|', n):
                # It is a pathname2url encoded path
                self.uri = uri
                self.file_ = urllib.url2pathname(n)
            else:
                u=urllib.urlopen(uri)

                # Use the same extension
                self.uri = uri
                (n, e) = os.path.splitext(uri)
                print "Making a local copy of %s" % uri
                f, self.file_ = tempfile.mkstemp(e, 'adv')
                f.write(u.read())
                f.close()
                u.close()

        if self.file_ is not None:
            self.open(self.file_)

    def getContentsFile(self):
        """Return the path to the real XML file.

        @return: the XML filename
        @rtype: string
        """
        return self.tempfile(u'content.xml')

    def tempfile(self, *names):
        """Return a tempfile name in the filesystem encoding.

        Try to deal appropriately with filesystem encodings:

        self._tempdir is a unicode string.

        tempfile takes unicode parameters, and returns a path encoded
        in sys.getfilesystemencoding()
        """
        return os.path.join(self._tempdir, *names).encode(_fs_encoding)

    def new(self):
        """Prepare a new AZP expanded package.
        """
        self._tempdir=unicode(tempfile.mkdtemp('', 'adv'), _fs_encoding)
        self.tempdir_list.append(self._tempdir)

        open(self.tempfile(u'mimetype'), 'w').write(MIMETYPE)

        os.mkdir(self.tempfile(u'resources'))

    def extract(self, fname):
        """Extract the zip file to a temporary directory.

        Return the temporary directory name.
        """
        z=zipfile.ZipFile(fname, 'r')

        def recursive_mkdir(d):
            parent=os.path.dirname(d)
            if not os.path.exists(parent):
                recursive_mkdir(parent)
            os.mkdir(d)

        # Check the validity of mimetype
        try:
            typ = z.read('mimetype')
        except KeyError:
            raise AdveneException(_("File %s is not an Advene zip package.") % self.file_)
        if typ != MIMETYPE:
            raise AdveneException(_("File %s is not an Advene zip package.") % self.file_)

        # The file is an advene zip package. We can extract its contents
        # to a temporary directory
        self._tempdir=unicode(tempfile.mkdtemp('', 'adv'), _fs_encoding)
        os.mkdir(self.tempfile(u'resources'))
        self.tempdir_list.append(self._tempdir)

        # FIXME: check the portability (convert / to os.path.sep ?)
        for name in z.namelist():
            if name.endswith('/'):
                # It is a directory name. Strip the trailing /, so
                # that os.path.dirname(name) really returns the
                # containing directory
                name=name[:-1]
                d=self.tempfile(name)
                if not os.path.exists(d):
                    recursive_mkdir(d)
            else:
                fname=self.tempfile(name)
                if not os.path.isdir(os.path.dirname(fname)):
                    recursive_mkdir(os.path.dirname(fname))
                outfile = open(fname, 'wb')
                outfile.write(z.read(name))
                outfile.close()

        z.close()

        # Create the resources directory if necessary
        resource_dir = self.tempfile(u'resources' )
        if not os.path.exists(resource_dir):
            os.mkdir(resource_dir)
        return self._tempdir

    def open(self, fname=None):
        """Open the given AZP file.

        It can also be a directory name containing an expanded AZP tree.

        @param fname: the file name
        @type fname: string
        """
        if fname is None:
            fname=self.file_

        if os.path.isdir(fname):
            # Do not append the dir to tempdir_list, since we do not
            # want it to be removed upon application exit.
            self._tempdir=fname
            try:
                typ=open(self.tempfile(u'mimetype'), 'r').read()
            except IOError:
                typ=None
            if typ != MIMETYPE:
                raise AdveneException(_("Directory %s is not an extracted Advene zip package.") % fname)
        else:
            self._tempdir=self.extract(fname)

        # FIXME: Check against the MANIFEST file
        for (name, mimetype) in self.manifest_to_list(self.tempfile(u'META-INF', u'manifest.xml')):
            if name == u'/':
                pass
            n=name.replace('/', os.path.sep)
            if not os.path.exists( self.tempfile(n) ):
                print "Warning: missing file : %s" % name

        # FIXME: Make some validity checks (resources/ dir, etc)
        self.file_ = fname

    def save(self, fname=None):
        """Save the package.
        """
        if fname is None:
            fname=self.file_

        if fname.endswith('/') and not os.path.exists(fname):
            # We specified a directory that does not exist yet. Create
            # it.
            os.mkdir(fname)

        if os.path.isdir(fname):
            z=None
        else:
            z=zipfile.ZipFile(fname, 'w')

        manifest=[]

        for (dirpath, dirnames, filenames) in os.walk(self._tempdir):
            # Ignore RCS directory paths
            for d in ('.svn', 'CVS', '_darcs', '.bzr'):
                if d in dirnames:
                    dirnames.remove(d)

            # Remove tempdir prefix
            zpath=dirpath.replace(self._tempdir, '')

            # Normalize os.path.sep to UNIX pathsep (/)
            zpath=zpath.replace(os.path.sep, '/', -1)
            if zpath and zpath[0] == '/':
                # We should have only a relative subdir here
                zpath=zpath[1:]

            for f in filenames:
                if f == 'manifest.xml':
                    # We will write it later on.
                    continue
                if zpath:
                    name='/'.join( (zpath, f) )
                else:
                    name=f
                if isinstance(name, str):
                    name=unicode(name, _fs_encoding)
                manifest.append(name)
                if z is not None:
                    z.write( os.path.join(dirpath, f),
                             name.encode('utf-8') )

        # Generation of the manifest file
        fname=self.tempfile(u"META-INF", u"manifest.xml")
        tree=ET.ElementTree(self.list_to_manifest(manifest))
        tree.write(fname)
        if z is not None:
            # Generation of the manifest file
            z.write( fname,
                     "META-INF/manifest.xml" )
            z.close()

    def update_statistics(self, p):
        """Update the META-INF/statistics.xml file
        """
        d=self.tempfile(u'META-INF')
        if not os.path.isdir(d):
            os.mkdir(d)
        f=open(self.tempfile(u'META-INF', u'statistics.xml'), 'w')
        f.write(p.generate_statistics().encode('utf-8'))
        f.close()
        return True

    def list_to_manifest(self, manifest):
        """Generate the XML representation of the manifest.

        @param manifest: the list of files
        @type manifest: list
        @return: the XML representation of the manifest
        @rtype: string
        """
        root=ET.Element(ET.QName(MANIFEST, 'manifest'))
        ET.SubElement(root, ET.QName(MANIFEST, 'file-entry'),  {
                ET.QName(MANIFEST, 'full-path'): '/',
                ET.QName(MANIFEST, 'media-type'): MIMETYPE,
                })
        for f in manifest:
            if f == 'mimetype' or f == 'META-INF/manifest.xml':
                continue
            (mimetype, encoding) = mimetypes.guess_type(f)
            if mimetype is None:
                mimetype = 'text/plain'
            ET.SubElement(root, ET.QName(MANIFEST, 'file-entry'),  {
                    ET.QName(MANIFEST, 'full-path'): unicode(f),
                    ET.QName(MANIFEST, 'media-type'): unicode(mimetype),
                    })
        return root

    def manifest_to_list(self, name):
        """Convert the manifest.xml to a list.

        List of tuples : (name, mimetype)

        @param name: the manifest filename
        @type name: string
        @return: a list of typles (name, mimetype)
        """
        l=[]
        tree=ET.parse(name)
        for e in tree.getroot():
            if e.tag == ET.QName(MANIFEST, 'file-entry'):
                l.append( (e.attrib[ET.QName(MANIFEST, 'full-path')],
                           e.attrib[ET.QName(MANIFEST, 'media-type')]) )
        return l

    def close(self):
        """Close the package and remove temporary files.
        """
        shutil.rmtree(self._tempdir.encode(_fs_encoding), ignore_errors=True)
        self.tempdir_list.remove(self._tempdir)
        return True

    def getResources(self, package=None):
        """Return the root resources object for the package.

        @return: the root Resources object
        @rtype: Resources
        """
        return Resources( self, '', parent=package )
