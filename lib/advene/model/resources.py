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
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Resources access classes
========================

    Resources are available when using a .azp package file::

      resources/: associated resources,
                  available through the TALES expression /package/advene/resources/...

"""
import os
import mimetypes
import urllib
import base64

import xml.dom.ext.reader.PyExpat

from advene.model.util.auto_properties import auto_properties
import advene.model.viewable as viewable

class ResourceData(viewable.Viewable.withClass('data', 'getMimetype')):
    """Class accessing a resource data (file).

    FIXME: should fully implement advene.model.content.Content API
    """
    __metaclass__ = auto_properties

    def __init__(self, package, resourcepath, parent=None):
        self.package = package
        self.rootPackage = parent.rootPackage
        self.ownerPackage = parent.ownerPackage
        self.resourcepath = resourcepath
        self.parent = parent

        self.author=None
        self.date=None

        self.file_ = self.package.tempfile('resources', resourcepath.replace('/', os.path.sep, -1) )
        self._mimetype = None
        self.title = str(self)

    def __str__(self):
        return "Resource %s" % self.resourcepath

    def getId(self):
        return self.resourcepath.split('/')[-1]

    def getData(self):
        return open(self.file_, 'rb').read()

    def setData(self, data):
        f=open(self.file_, 'wb')
        f.write(data)
        f.close()

    def getMimetype(self):
        if self._mimetype is None:
            (mimetype, encoding) = mimetypes.guess_type(self.file_)
            if mimetype is None:
                mimetype = "text/plain"
            self._mimetype=mimetype
        return self._mimetype

    def getModel(self):
        data = self.getData()
        # FIXME: We should ensure that we can parse it as XML
        reader = xml.dom.ext.reader.PyExpat.Reader()
        element = reader.fromString(data)._get_documentElement()
        return element

    def getUri (self):
        """Return the URI of the element.
        """
        p=urllib.quote(self.resourcepath, safe='')
        return "%s#data_%s" % (self.package.uri, p)

    def getStream(self):
        return open(self.file_, 'rb')

    def getDataBase64(self):
        data = self.getData()
        data = base64.encodestring(data)
        return data

class Resources:
    """Class accessing a resource dir.
    """
    __metaclass__ = auto_properties

    DIRECTORY_TYPE=object()

    def __init__(self, package, resourcepath, parent=None):
        self.package = package
        self.rootPackage = parent.rootPackage
        self.ownerPackage = parent.ownerPackage
        self.parent = parent

        self._children_cache = {}

        # Resource path name
        self.resourcepath = resourcepath

        # Real directory
        self.dir_ = self.package.tempfile( 'resources', resourcepath.replace('/', os.path.sep, -1) )
        self.filenames=None
        self.title = str(self)

    def init_filenames(self):
        if self.filenames is None:
            self.filenames=os.listdir(self.dir_)

    def __str__(self):
        if self.resourcepath == "":
            return "ResourceFolder root"
        else:
            return "ResourceFolder %s" % self.resourcepath

    def children (self):
        return [ self[n] for n in self.keys() ]

    def has_key(self, key):
        self.init_filenames()
        return (key in self.filenames)

    def keys(self):
        self.init_filenames()
        return self.filenames

    def __contains__(self, key):
        fname=os.path.join( self.dir_, key )
        return os.path.exists(fname)

    def __getitem__(self, key):
        fname=os.path.join( self.dir_, key )
        if not os.path.exists(fname):
            raise KeyError

        # resource path for the new resource
        if self.resourcepath == '':
            p=key
        else:
            p='/'.join( (self.resourcepath, key) )

        if p in self._children_cache:
            return self._children_cache[p]

        if os.path.isdir(fname):
            r=Resources(self.package, p, parent=self)
        else:
            # It is a file. Return its ResourceData
            r=ResourceData(self.package, p, parent=self)
        self._children_cache[p]=r
        return r

    def __setitem__(self, key, item):
        """Create a new item.

        To create a new directory, use item == Resources.DIRECTORY_TYPE
        """
        self.filenames = None
        fname=os.path.join( self.dir_, key )

        if item == self.DIRECTORY_TYPE:
            os.mkdir(fname)
        else:
            # Some content
            f=open(fname, 'wb')
            f.write(item)
            f.close()


    def __delitem__(self, key):

        # resource path for the new resource
        if self.resourcepath == '':
            p=key
        else:
            p='/'.join( (self.resourcepath, key) )
        try:
            del self._children_cache[p]
        except KeyError:
            pass
        self.filenames = None
        fname=os.path.join( self.dir_, key )
        if os.path.isdir(fname):
            os.rmdir(fname)
        else:
            os.unlink(fname)

    def getUri (self):
        """Return the URI of the element.
        """
        p=urllib.quote(self.resourcepath, safe='')
        return "%s#data_%s" % (self.package.uri, p)

    def getId(self):
        return self.resourcepath.split('/')[-1]

    def __iter__(self):
        """Recursively iter over all non-directory descendants."""
        for c in self.children():
            if hasattr(c, "DIRECTORY_TYPE"):
                for c2 in c:
                    yield c2
            else:
                yield c

