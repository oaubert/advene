#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
import logging
logger = logging.getLogger(__name__)

import codecs
from collections import OrderedDict
from io import StringIO
import json
import re
import urllib.request, urllib.parse, urllib.error

import advene.core.config as config
import advene.model.modeled as modeled
import advene.model.viewable as viewable

from advene.util.expat import PyExpat

from advene.model.constants import adveneNS, xlinkNS, TEXT_NODE, ELEMENT_NODE

import advene.model.util.dom
import advene.model.util.uri

from advene.model.util.auto_properties import auto_properties
from advene.model.util.mimetype import MimeType

class StructuredContent(dict):
    """Dict-like object representing structured data.

    It provides methods for parsing from/unparsing to Advene
    simple-structured content.

    Note that it cannot do synchronous updates when writing since:
       - it should do a content update after each attribute
         modification, which would not be efficient.
       - it should have a reference to the controller ECAEngine,
         which is not available here.
    So prefer a more verbose but explicit behaviour.
    """
    def __init__(self, *p, **kw):
        if p and isinstance(p[0], str):
            # Initialize with a content.
            self.parse(p[0])
        else:
            dict.__init__(self, *p, **kw)

    def parse(self, data):
        """Parse a data string.
        """
        self.clear()
        self['_all']=data
        for l in data.splitlines():
            if not l:
                # Ignore empty lines
                continue
            if '=' in l:
                (k, v) = l.split('=', 1)
                self[k] = urllib.parse.unquote(v)
            else:
                self['_error']=l
                logger.warning("Syntax error in content: >%s<", l)

    def unparse(self):
        """Return the encoded version of the dictionary.
        """
        def quote(v):
            """Poor man's urllib.quote.

            It should preserve the readability of the content while
            being compatible with RFC2396 when decoding.
            """
            return v.replace('\n', '%0A').replace('=', '%3D').replace('%', '%25')

        return "\n".join( ("%s=%s" % (k, quote(v)))
                          for (k, v) in self.items()
                          if not k.startswith('_') )

COMMA_REGEXP = re.compile(r'\s*,\s*', re.UNICODE)
COMMENT_REGEXP = re.compile(r'\((.*?)\)', re.UNICODE)
class KeywordList:
    """Set-like object representing a keyword list.

    They are stored as a comma-separated list of keywords. The parent
    type MAY have a value-metadata dict that holds metadata about each
    keyword.

    KeywordList implements array-like features (__contains__).
    The .get(keyword) returns metadata (as dict) about the keyword.

    Comments may be specified between parentheses. There may be multiple
    comments, but in case of modification through the API, they will
    all be merged into a single one, placed at the end.

    It provides methods for parsing from/unparsing to Advene
    x-advene-keyword-list
    """
    def __init__(self, data=None, parent=None, **kw):
        # Initialize with a content.
        self._values, self._comment = self.parse(data)
        self._parent = parent

    def get(self, kw=None, key=None, default=None):
        """Return metadata about the keyword.

        If kw is not specified, return the value_metadata for all
        keywords.

        If key is not specified, return the whole value_metadata
        object for kw.

        Else return the value corresponding to key from the
        kw value_metadata.

        In case of error or missing value, return default.
        """
        metadata = {}
        meta_str = self._parent.getMetaData(config.data.namespace, 'value_metadata')
        if meta_str:
            try:
                metadata = json.loads(meta_str)
            except ValueError:
                logger.warning("Cannot parse metadata %s", metadata)
                return None
        if kw is None:
            return metadata
        else:
            if key is None:
                return metadata.get(kw, {})
            else:
                return metadata.get(kw, {}).get(key, default)

    def parse(self, data=None):
        """Parse a data string.
        """
        val = []
        comment = ""
        if not data:
            return val, comment
        comment = "".join(COMMENT_REGEXP.findall(data))
        # Strip all comments
        data, count = COMMENT_REGEXP.subn('', data)
        # Split values
        val = [ k.strip() for k in COMMA_REGEXP.split(data) ]
        return val, comment

    def add(self, kw):
        """Add a keyword to the list.
        """
        self._values.append(kw)
        return self._values

    def remove(self, kw):
        """Remove a keyword from the list.
        """
        try:
            self._values.remove(kw)
        except:
            pass
        return self._values

    def get_comment(self):
        return self._comment

    def __contains__(self, kw):
        return kw in self._values

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __getitem__(self, i):
        return self._values[i]

    def __str__(self):
        return self.unparse()

    def __bytes__(self):
        return self.unparse().encode('utf-8')

    def as_dict(self):
        """Return the keyword list as an ordered dict.

        The keys are the list items, the values are fetched from
        metadata_value from the type.
        """
        res = OrderedDict()
        for kw in self._values:
            res[kw] = self.get(kw)
        return res

    def as_values(self):
        """Return the keyword list indexed by value name.
        """
        res = dict()
        for k in self._values:
            for name, value in self.get(k).items():
                res.setdefault(name, []).append(value)
        return res

    def unparse(self):
        """Return the encoded version of the set

        Note that it does not handle metadata.
        """
        res = ",".join(self._values)
        if self._comment:
            res = "%s [%s]" % (res, self._comment)
        return res

class Content(modeled.Modeled,
              viewable.Viewable.withClass('content', 'getMimetype'), metaclass=auto_properties):
    """
    Represents the Content of an element (mainly of Annotation and
    Relation elements)

    TODO: handle content types more complex than TEXT_NODE
    """

    def __init__(self, parent, element):
        modeled.Modeled.__init__(self, element, parent)

    def getDomElement (self):
        """Return the DOM element representing this content."""
        # FIXME: is this what we need? is this what we want?
        return self._getModel ()

    def isTextual(self):
        """Check if the data is textual, according to mimetype
        """
        mt = self.mimetype
        return mt is not None and (mt.startswith('text')
                                   or 'x-advene' in mt
                                   or 'xml' in mt
                                   or 'javascript' in mt
                                   or mt in config.data.text_mimetypes)

    def getData(self):
        """Return the data associated to the Content"""
        nodes = self._getModel().childNodes
        if len(nodes) == 1 and nodes[0].nodeType == nodes[0].TEXT_NODE:
            d = nodes[0].wholeText
        else:
            data = StringIO()
            advene.model.util.dom.printElementText(self._getModel(), data)
            d = data.getvalue()
        if self._getModel().hasAttributeNS(None, 'encoding'):
            encoding = self._getModel().getAttributeNS(None, 'encoding')
        else:
            encoding = 'utf-8'
        if isinstance(d, bytes):
            return d.decode(encoding)
        else:
            return d

    def setData(self, data):
        """Set the content's data"""
        # TODO: parse XML if any
        for n in self._getModel().childNodes:
            if n.nodeType in (TEXT_NODE, ELEMENT_NODE):
                self._getModel().removeChild(n)
        if data:
            self.delUri()
            if not self.isTextual():
                encoding = 'base64'
                data = codecs.encode(bytes(data, 'utf-8'), encoding)
            else:
                encoding = 'utf-8'
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
            self._getModel().setAttributeNS(None, 'encoding', encoding)
            new = self._getDocument().createTextNode(data)
            self._getModel().appendChild(new)

    def delData(self):
        """Delete the content's data"""
        self.setData(None)

    def getModel(self):
        data = self.getData()
        # FIXME: We should ensure that we can parse it as XML
        reader = PyExpat.Reader()
        element = reader.fromString(data).documentElement
        return element

    def getUri (self, absolute=True):
        """
        Return the content's URI.

        If parameter absolute is set to _false_, the URI will *not* be
        absolutized, it will be returned in its stored form (which could
        be absolute).

        You would probably rather use the uri read-only property, unless you
        want to set the parameter _absolute_.
        """
        if self._getModel().hasAttributeNS(xlinkNS, 'href'):
            r = self._getModel().getAttributeNS(xlinkNS, 'href')
            if absolute:
                url_base =self._getParent().getOwnerPackage().getUri (absolute)
                return advene.model.util.uri.urljoin(url_base, r)
            else:
                return r
        else:
            return None

    def setUri(self, uri):
        """Set the content's URI"""
        if uri is not None:
            self.delData()
            self._getModel().setAttributeNS(xlinkNS, 'xlink:href', uri)
        else:
            if self._getModel().hasAttributeNS(xlinkNS, 'href'):
                self._getModel().removeAttributeNS(xlinkNS, 'href')

    def delUri(self):
        """Delete the content's URI"""
        self.setUri(None)

    def getStream(self):
        """Return a stream to access the content's data
        FIXME: read/write ?
        """
        uri = self.getUri(absolute=True)
        if not uri:
            # TODO: maybe find a better way to get a stream from the DOM
            return StringIO(self.getData())
        return advene.model.util.uri.open(uri)

    def getMimetype(self):
        """Return the content's mime-type"""
        if self._getModel().hasAttributeNS(None, 'mime-type'):
            return self._getModel().getAttributeNS(None, 'mime-type')
        else:
            try:
                mt=self._getParent().getType().getMimetype()
            except AttributeError:
                # The type does not define a mimetype (Query for instance)
                mt=None
            return mt

    def setMimetype(self, value):
        """Set the content's mime-type"""
        if value is None and self._getModel().hasAttributeNS(None, 'mime-type'):
            self._getModel().removeAttributeNS(None, 'mime-type')
        else:
            self._getModel().setAttributeNS(None, 'mime-type', value)

    def getPlugin (self):
        """
        Return an object provided by the appropriate plugin.
        See ContentPlugin
        """
        return ContentPlugin.find_plugin (self)

    def parsed (self):
        """Parse the content.

        This method parses the data of the content according to its
        mime-type. The most common parser is an structured text
        parser, but there is also a basic XML parser.

        a.content.parsed.key1

        Simple structured data
        ======================

        This is a simple-minded format for structured information (waiting
        for a better solution based on XML):

        The structure of the data consists in 1 line per information:

        key1=value1
        key2=value2

        The values are on 1 line only. URL-style escape conventions are
        used (mostly to represent the linefeed as %0a).

        It returns a dict with key/values.

        Keywords
        ========

        Data is represented as a comma-separated list of
        keywords. Optional metadata may be specified at the type
        level.

        It return a dict with key/values (where keys are the keywords
        themselves, and values are dicts holding metadata)

        XML data
        ========

        It returns a Node object whose attributes are the different
        attributes and children of the node.

        JSON data
        =========

        It returns the structure corresponding to the JSON data.

        @return: a data structure

        """
        # FIXME: the right way to implement this would be to subclass the Content
        # into SimpleStructuredContent, XMLContent...
        # but this would require changes all over the place. Use this for the moment.
        if self.mimetype is None or self.mimetype == 'text/plain':
            # If nothing is specified, assume text/plain and return the content data
            return self.data

        if (self.mimetype in ( 'application/x-advene-structured',
                               'text/x-advene-structured',
                               'application/x-advene-zone' ) ):
            return StructuredContent(self.data)
        elif self.mimetype == 'text/x-advene-keyword-list':
            # Return a dictionary?
            return KeywordList(self.data, parent=self._getParent().getType())
        elif self.mimetype == 'application/json':
            if json is not None:
                try:
                    return json.loads(self.data)
                except ValueError:
                    logger.error("Cannot interpret content as json: %s", self.data)
                    return self.data
            else:
                return {'data': self.data}
        elif self.mimetype == 'application/x-advene-values':
            def convert(v):
                try:
                    r=float(v)
                except ValueError:
                    r=0
                return r
            return [ convert(v) for v in self.data.split() ]
        #FIXME: we parse x-advene-ruleset as xml for the moment
        elif self.mimetype in ('text/xml',
                               'application/x-advene-ruleset',
                               'application/x-advene-simplequery'):
            import advene.util.handyxml
            h=advene.util.handyxml.xml(self.stream)
            # FIXME: use a cache of DOM trees in order to avoid to
            # repeatdly parse the same data in the case of repetitive
            # access to the same element.
            # FIXME: use ElementTree.iterparse

            return h

        # Last fallback:
        return self.data

class WithContent(metaclass=auto_properties):
    """An implementation for the 'content' property and related properties.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
    """

    __content = None

    def _createContent(self):
        elt = self._getDocument().createElementNS(adveneNS, 'content')
        self._getModel().appendChild(elt)
        return Content(self, elt)

    def getContent(self):
        if self.__content is None:
            elt = self._getChild((adveneNS, 'content'))
            if elt is None:
                self.__content = self._createContent ()
            else:
                self.__content = Content (self, elt)
        return self.__content

    def delContent(self):
        elt = self._getChild((adveneNS, 'content'))
        if elt is not None:
            self._getModel ().removeChild (elt)
        del self.__content

    def getContentData(self):
        # TODO deprecate this
        return self.getContent().getData()

    def setContentData(self, data):
        # TODO deprecate this
        self.getContent().setData(data)


_content_plugin_registry = {}

class ContentPlugin:
    """
    TODO
    """

    def __init__ (self, content):
        """
        Does nothing.
        Only here to give the signature of a ContentPlugin.
        """
        pass

    @staticmethod
    def register (a_class, uri):
        assert issubclass(a_class, ContentPlugin)
        _content_plugin_registry[uri] = a_class

    @staticmethod
    def find_plugin (content):
        mimetype = MimeType(content.getMimetype())
        found = None
        found_type = None

        for p in _content_plugin_registry.values ():
            plugin_type = MimeType(p.getMimetype())
            if plugin_type >= mimetype:
                if found is None or found_type >= plugin_type:
                    found = p
                    found_type = plugin_type

        return found(content)

    @staticmethod
    def withType (mimetype):
        assert MimeType (mimetype)
        class _content_plugin_class (ContentPlugin):
            @staticmethod
            def getMimetype ():
                return mimetype
        return _content_plugin_class


class TestPlugin (ContentPlugin.withType ('text/*')):
    """
    A 'proof of concept' test plugin.
    """
    def __init__ (self, content):
        super().__init__(self, content)
        self.__content = content

    def hello(self):
        return "TEST (%s)" % self.__content.data

ContentPlugin.register (TestPlugin, 'http://advene.org/plugins/test')
