from cStringIO import StringIO

import advene.model.modeled as modeled
import advene.model.viewable as viewable

import xml.dom.ext.reader.PyExpat

from advene.model.constants import *

import advene.model.util.dom
import advene.model.util.uri

from advene.model.util.auto_properties import auto_properties
from advene.model.util.mimetype import MimeType

class Content(modeled.Modeled,
              viewable.Viewable.withClass('content', 'getMimetype')):
    """
    Represents the Content of an element (mainly of Annotation and
    Relation elements)

    TODO: handle content types more complex than TEXT_NODE
    """
    
    __metaclass__ = auto_properties

    def __init__(self, parent, element):
        modeled.Modeled.__init__(self, element, parent)

    def getDomElement (self):
        """Return the DOM element representing this content."""
        # FIXME: is this what we need? is this what we want?
        return self._getModel ()
        
    def getData(self):
        """Return the data associated to the Content"""
        data = StringIO()
        advene.model.util.dom.printElementText(self._getModel(), data)
        d=data.getvalue().decode('utf-8')
        return d

    def setData(self, data):
        """Set the content's data"""
        # TODO: parse XML if any
        for n in self._getModel()._get_childNodes():
            if n.nodeType in (TEXT_NODE, ELEMENT_NODE):
                self._getModel().removeChild(n)
        if data:
            self.delUri()
            new = self._getDocument().createTextNode(data)
            self._getModel().appendChild(new)

    def delData(self):
        """Delete the content's data"""
        self.setData(None)

    def getModel(self):
        data = self.getData()
        # FIXME: We should ensure that we can parse it as XML
        reader = xml.dom.ext.reader.PyExpat.Reader()
        element = reader.fromString(data)._get_documentElement()
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
            return StringIO(self.getData().encode('utf-8'))
        return advene.model.util.uri.open(uri)

    def getMimetype(self):
        """Return the content's mime-type"""
        if self._getModel().hasAttributeNS(None, 'mime-type'):
            return self._getModel().getAttributeNS(None, 'mime-type')
        else:
            return self._getParent().getType().getMimetype()

    def setMimetype(self, value):
        """Set the content's mime-type"""
        if value is None and self._getModel().hasAttributeNS(None, 'mime-type'):
            self._getModel().removeAttributeNS(None, 'mime-type')
        else:
            MimeType (value)
            self._getModel().setAttributeNS(None, 'mime-type', unicode(value))

    def getPlugin (self):
        """
        Return an object provided by the appropriate plugin.
        See ContentPlugin
        """
        return ContentPlugin.find_plugin (self)


class WithContent(object):
    """An implementation for the 'content' property and related properties.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
    """

    __metaclass__ = auto_properties

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

class ContentPlugin (object):
    """
    TODO
    """

    def __init__ (self, content):
        """
        Does nothing.
        Only here to give the signature of a ContentPlugin.
        """
        pass

    def register (a_class, uri):
        assert issubclass(a_class, ContentPlugin)
        _content_plugin_registry[uri] = a_class

    register = staticmethod (register)

    def find_plugin (content):
        mimetype = MimeType(content.getMimetype())
        found = None
        foundtype = None

        for p in _content_plugin_registry.itervalues ():
            plugin_type = MimeType(p.getMimetype())
            if plugin_type >= mimetype:
                if found is None or found_type >= plugin_type:
                    found = p
                    found_type = plugin_type

        return found(content)

    find_plugin = staticmethod (find_plugin)

    def withType (mimetype):
        assert MimeType (mimetype)
        class _content_plugin_class (ContentPlugin):
            def getMimetype ():
                return mimetype
            getMimetype = staticmethod (getMimetype)
        return _content_plugin_class

    withType = staticmethod (withType)
        

class TestPlugin (ContentPlugin.withType ('text/*')):
    """
    A 'proof of concept' test plugin.
    """
    def __init__ (self, content):
        self.__content = content

    def hello(self):
        return "TEST (%s)" % self.__content.data

ContentPlugin.register (TestPlugin, 'http://advene.liris.cnrs.fr/plugins/test')
