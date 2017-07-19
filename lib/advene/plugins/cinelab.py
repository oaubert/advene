#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2010-2017 Olivier Aubert <contact@olivieraubert.net>
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

# Cinelab importer.

name="Cinelab importer"

from gettext import gettext as _

import sys
import os
import zipfile
import tempfile
import re

import advene.core.config as config
from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ET
from advene.model.exception import AdveneException

MIMETYPE = "application/x-cinelab-zip-package"

# Namespaces definitions
DC = config.data.namespace_prefix['dc']
ADVENE = config.data.namespace
CINELAB = 'http://advene.org/ns/cinelab/'
prefixes = {
    'dc': DC,
    'advene': ADVENE,
    'cinelab': CINELAB,
    }
prefix_re = re.compile('(%s):' % "|".join( list(prefixes.keys()) ))

def ns(path):
    """Convert NS prefixes to {URL} in ET path expressions
    """
    return prefix_re.sub(lambda m: '{%s}' % prefixes.get(m.group(1), 'FIXME'),
                         path)

def meta(node, t):
    n = node.find(ns('cinelab:meta/%s' % t))
    if n is not None:
        return n.text
    else:
        return ''

_fs_encoding = sys.getfilesystemencoding()
# In some cases, sys.getfilesystemencoding returns None. And if the
# system is misconfigured, it will return ANSI_X3.4-1968
# (apparently). In these cases, fallback to a sensible default value
if _fs_encoding in ('ascii', 'ANSI_X3.4-1968', None):
    _fs_encoding='utf8'

def register(controller=None):
    controller.register_importer(CinelabImporter)
    return True


class CinelabImporter(GenericImporter):
    name = _("Cinelab importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.czp') or fname.endswith('.cxp'):
            return 100
        elif fname.endswith('.xml') or fname.endswith('.zip'):
            return 30
        return 0
    can_handle=staticmethod(can_handle)

    def tempfile(self, *names):
        """Return a tempfile name.

        self._tempdir is a unicode string.
        """
        return os.path.join(self._tempdir, *names)

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
            raise AdveneException(_("File %s is not an Advene2 zip package.") % self.file_)
        if typ != MIMETYPE:
            raise AdveneException(_("File %s is not an Advene2 zip package.") % self.file_)

        # The file is an advene2 zip package. We can extract its contents
        # to a temporary directory
        self._tempdir=str(tempfile.mkdtemp('', 'czp'), _fs_encoding)

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
        return self._tempdir

    def process_file(self, filename):
        self._tempdir = None
        if filename.endswith('.zip') or filename.endswith('.czp'):
            self.extract(filename)
            filename = self.tempfile('content.xml')

        tree=ET.parse(filename)
        root=tree.getroot()

        p, at = self.init_package(filename=filename)

        # Initialize Media data
        self.medias = {}
        for v in (root.find(ns('cinelab:medias')) or []):
            # FIXME: handle metadata
            self.medias[v.attrib['id']] = v.attrib['url']
        # Will be initialized when first referenced in source package
        self.default_media = None
        self.convert(self.iterator(root))

        package_author = meta(root, 'dc:creator')
        package_created = meta(root, 'dc:created')

        p.author = package_author
        p.date = package_created
        p.title = meta(root, 'dc:title')
        p.setMedia(self.default_media)

        # Finalize
        self.progress(.3, _("Converting annotation types"))
        ats = root.find(ns('cinelab:annotation-types'))
        # Note: do not use the shortcut ats = root.find(...) or [],
        # the result of root.find is always False
        if ats is None:
            return []
        views = root.find(ns('cinelab:views'))
        if views is None:
            return []
        size = len(ats)
        for (i, node) in enumerate(ats):
            if not self.progress(i / size):
                return
            at = self.package.get_element_by_id(node.attrib['id'])
            if at is None:
                # Not yet created
                at = self.ensure_new_type(node.attrib['id'])
            at.title = meta(node, 'dc:title')
            at.setMetaData(DC, 'description', meta(node, 'dc:description'))
            color = meta(node, 'cinelab:color')
            if color:
                at.setMetaData(ADVENE, 'color', 'string:' + color)
            icolor = meta(node, 'cinelab:element-color')
            if icolor:
                at.setMetaData(ADVENE, 'item_color', 'string:' + icolor)
            at.author = meta(node, 'dc:creator') or package_author
            at.date = meta(node, 'dc:created') or package_created
            # FIXME: tags/lists...
            cst = node.find(ns('cinelab:meta/cinelab:element-constraint'))
            if cst:
                cstid = cst.attrib['id-ref']
                v = [ v for v in views if v.attrib['id'] == cstid ]
                if v:
                    # Found the constraint view
                    c = v.find(ns('cinelab:content'))
                    if c and c.attrib['mimetype'] == 'application/x-advene-type-constraint':
                        # We know how to parse this
                        data = dict( l.split('=') for l in c.text.splitlines() )
                        if data.get('mimetype'):
                            at.mimetype = data.get('mimetype')

        self.progress(.6, _("Converting views"))
        size = len(views)
        for (i, node) in enumerate(views):
            if not self.progress(i / size):
                return
            if node.attrib['id'].startswith(':'):
                # Ignore internal views
                continue
            c = v.find(ns('cinelab:content'))
            if c:
                mt = c.get('mimetype')
            else:
                mt = 'text/plain'
            v = p.createView(ident = node.attrib['id'],
                             author = meta(node, 'dc:creator') or package_author,
                             date = meta(node, 'dc:created') or package_created,
                             clazz = 'package',
                             content_mimetype = mt)
            v.content.data = c.text
            p.views.append(v)

        self.progress(1.0)
        return self.package

    def iterator(self, root):
        package_author = meta(root, 'dc:creator')
        package_created = meta(root, 'dc:created')

        annotations = root.find(ns('cinelab:annotations'))
        if annotations is None:
            annotations = []
        size = 1.0 * len(annotations)
        self.progress(0, _("Importing annotations"))
        for i, a in enumerate(annotations):
            if not self.progress(i / size):
                return
            if self.default_media is None:
                self.default_media = self.medias.get(a.attrib['media'], None)
            # FIXME: add check for embedded content
            content = a.find(ns('cinelab:content'))
            if content is not None:
                content = content.text
            else:
                content = ""
            yield {
                'id': a.attrib['id'],
                'begin': a.attrib['begin'],
                'end': a.attrib['end'],
                'content': content,
                'type': a.find(ns('cinelab:meta/cinelab:type')).attrib['id-ref'],
                'author': meta(a, 'dc:creator') or package_author,
                'timestamp': meta(a, 'dc:created') or package_created,
                }
