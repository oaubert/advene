import xml.dom

from cStringIO import StringIO

import advene.model.util.uri

ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE
TEXT_NODE = xml.dom.Node.TEXT_NODE

from constants import *

# TODO: let in here only classes which have no __init__ methods
#       (i.e. which can be inherited without further adaptation to the
#        inheriting class)

class Metaed(object):
    """An implementation for the meta element.
       Inheriting classes must have a _getModel method returning a DOM element,
       and a _getChild method as the one from modeled.Modeled
       (inheriting the modeled.Modeled class is the best idea by far).
       Note that the meta elements is always supposed to be the first element
       child.
    """
    def _getMeta(self, create=False):
        """Return the meta element, creating it if required.
           If not present and 'create' is False, return None.
        """
        meta = self._getChild((adveneNS, 'meta'))
        if meta is None and create:
            doc = self._getModel()._get_ownerDocument()
            meta = doc.createElementNS(adveneNS,"meta")
            self._getModel()._get_childNodes().insert(0,meta)
        return meta

    def _getMetaElement(self, namespace_uri, name, create=False):
        meta = self._getMeta(create)
        if meta is None: return None

        for e in meta._get_childNodes():
            if e._get_nodeType() is ELEMENT_NODE \
            and e._get_namespaceURI() == namespace_uri \
            and e._get_localName() == name:
                return e

        if create:
            doc = meta._get_ownerDocument()
            e = doc.createElementNS(namespace_uri, name)
            meta._get_childNodes().insert(0,e)
            return e
        else:
            return None

    def getMetaData(self, namespace_uri, name):
        """Return the text content of metadata with given NS and name
        """
        e = self._getMetaElement(namespace_uri, name)
        if e is None: return None

        r = StringIO()
        advene.model.util.dom.printElementText(e, r)
        return r.getvalue()
                

    def setMetaData(self, namespace_uri, name, value):
        """Set the metadata with given NS and name
        """
        create = (value is not None)
        e = self._getMetaElement(namespace_uri, name, create)

        if e is not None and value is None:
            self._getMeta ().removeChild (e)
            return

        for n in e._get_childNodes():
            if n.nodeType in (TEXT_NODE, ELEMENT_NODE):
                e.removeChild(n)
        if value is not None:
            new = e._get_ownerDocument().createTextNode(value)
            e.appendChild(new)


class Authored(Metaed):
    """An implementation for the author property.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
       Note that this implementation consider author to be optional.
    """
  #
  # private methods
  #
    def __prepareAuthorNodes (self):
        """Return a 2-uple containing the attribute node and the model node
           with qname 'dc:creator' in the model (possibly None)
        """
        an = self._getModel ().getAttributeNodeNS (dcNS, 'creator')
        en = self._getMetaElement (dcNS, 'creator', create=False)
        return an, en

    def __cleanAuthorElementAndGetLayout (self, authorelt, author):
        """Remove every child of the given element, and try to locate the text
           content of it (actually takes the first found text node).
           Then return the given author string by reproducing the layout
           (leadind and trailing whitespaces) of the previous text content.
        """
        s = ""
        for n in authorelt._get_childNodes ():
            if n.nodeType==TEXT_NODE:
                s += n._get_data ()
                authorelt.removeChild (n)
        if s: author = s.replace (s.strip (), author) # try to keep layout
        return author

    def __setAuthorNode (self, author, authorUrl=None):
        attnode, eltnode = self.__prepareAuthorNodes ()
    
        if author is None:
            assert authorUrl==None, "authorUrl without author is impossible"
            if attnode: self._getModel ().removeAttributeNode (attnode)
            if eltnode: self._getMeta ().removeChild (eltnode)
        
        elif authorUrl is None:
            if eltnode is None:
                self._getModel ().setAttributeNS (dcNS, 'dc:creator', author)
            else:
                if eltnode.hasAttributeNS (xlinkNS, 'href'):
                    eltnode.removeAttributeNS (xlinkNS, 'href')
                author = self.__cleanAuthorElementAndGetLayout (eltnode, author)
                textnode = eltnode._get_ownerDocument ().createTextNode (author)
                eltnode.appendChild (textnode)

        else: #authorUrl is not None
            if attnode:
                self._getModel ().removeAttributeNode (attnode)
            
            doc = self._getModel ()._get_ownerDocument ()
        
            if eltnode is None:
                eltnode = self._getMetaElement (dcNS, 'creator', create=True)
            else:
                author = self.__cleanAuthorElementAndGetLayout (eltnode, author)
            
            textnode = doc.createTextNode(author)
            eltnode.appendChild(textnode)
            eltnode.setAttributeNS(xlinkNS, "xlink:href", unicode(authorUrl))
  #
  # public methods
  #
    def getAuthor(self):
        """Return the author or None.
           You would probably rather use the author property.
        """
        attnode, eltnode = self.__prepareAuthorNodes()
        if attnode:
            return attnode._get_value()
        if eltnode:
            s = ""
            found = 0
            for n in eltnode._get_childNodes():
                if n.nodeType==TEXT_NODE:
                    found = 1
                    s += n._get_data()
            if found: return s.strip()
        return None

    def getAuthorUrl(self):
        """Return the author URL or None.
           You would probably rather use the authorUrl property.
        """
        attnode, eltnode = self.__prepareAuthorNodes()
        if eltnode and eltnote.hasAttributeNS (xlinkNS, 'href'):
            return eltnode.getAttributeNS (xlinkNS, 'href')
        return None

    def setAuthor(self, value):
        """Set the author.
           You would probably rather use the author property.
        """
        if value or self._getModel()._get_parentNode().nodeType==ELEMENT_NODE:
            self.__setAuthorNode(value, self.getAuthorUrl())
        else:
            raise AttributeError("author is a required attribute here")

    def setAuthorUrl(self, value):
        """Set the author URL.
           You would probably rather use the authorUrl property.
        """
        self.__setAuthorNode(self.getAuthor(), value)

    def delAuthor(self):
        """Unbind the author.
           You would probably rather del the author property.
        """
        self.setAuthor(None)

    def delAuthorUrl(self):
        """Unbind the author URL.
           You would probably rather del the authorUrl property.
        """
        self.setAuthorUrl(None)

    author = property(getAuthor, setAuthor, delAuthor)
    authorUrl = property(getAuthorUrl, setAuthorUrl, delAuthorUrl)


# TODO: take into account cases where dc:date is an element in the meta element
#       rather than an attribute
class Dated(Metaed):
    """An implementation for the date property.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
    """
    def getDate(self):
        """Return the date.
           You would probably rather use the date property.
        """
        return self._getModel().getAttributeNS(dcNS, "date")

    def setDate(self, value):
        """Set the date.
           You would probably rather use the date property.
        """
        if value:
            self._getModel().setAttributeNS(dcNS, "dc:date", unicode(value))
        else:
            self._getModel().removeAttributeNS(dcNS, "date")

    def delDate(self):
        """Unbind the date.
           You would probably rather del the date property.
        """
        self.setDate(None)

    date = property(getDate, setDate, delDate)


# TODO: take into account cases where dc:title is an element in the meta element
#       rather than an attribute
class Titled(Metaed):
    """An implementation for the title property.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
    """
    def getTitle(self):
        """Return the title.
           You would probably rather use the title property.
        """
        return ( self._getModel().getAttributeNS(dcNS, "title")
              or self.getMetaData(dcNS, "title") )

    def setTitle(self, value):
        """Set the Title.
           You would probably rather use the title property.
        """
        if value:
            if self._getModel().hasAttributeNS(dcNS, "title"):
                self._getModel().setAttributeNS(dcNS, "dc:title",
                                                unicode(value))
            else:
                self.setMetaData(dcNS, "title", unicode(value))
        else:
            if self._getModel().hasAttributeNS(dcNS, "title"):
                self._getModel().removeAttributeNS(dcNS, "title")
            else:
                self.setMetaData(dcNS, "title", None)

    def delTitle(self):
        """Unbind the title.
           You would probably rather del the title property.
        """
        self.setTitle(None)

    title = property(getTitle, setTitle, delTitle)


class Ided(object):
    """An implementation for the id property.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
       The 'id' attribute is not mutable, since many references in the model
       rely on it.
    """
    def getId(self):
        """Return the id.
           You would probably rather use the id property.
        """
        return self._getModel().getAttributeNS(None, "id")

    def setId(self, value):
        """Set the id.
        You would probably rather use the id property.
        """
        if value:
            self._getModel().setAttributeNS(None, "id", unicode(value))
        else:
            raise AttributeError("id is a required attribute")
 
    id = property(getId, setId)

class Uried(Ided):
    """An implementation for the id property interpreted as a URI fragment.
    """

    class __dummy:
        def __init__(self,uri):
            self.__uri = uri
        def getUri(self, absolute=True, context=None):
            return self.__uri

    def __init__(self, base_uri="", parent=None):
        """The constructor of URIed takes either a base_uri parameter
           or a parent object providing the base URI with a getURI method.
           If both are given, base_uri is ignored.
        """
        if parent is not None:
            self.__base = parent
        else:
            # TODO: check that base_uri is a valid absolute uri
            self.__base = __dummy(base_uri)

    def __repr__(self):
        """Return a string representation of the object."""
        return "<%s.%s('%s')>" % (self.__class__.__module__,
                                  self.__class__.__name__,
                                  self.getUri ())

    def getUri (self, absolute=True, context=None):
        """
        Return the URI.
        The getId() method, inherited from class Ided will be used to get it
        (note that overridden versions of getId will *not* be used for that).

        Parameter if _absolute_ is _True_, the URI will be forced absolute.
        If not, and if _context_ is _None_, the URI will be resolved with
        respect to the root package URI, whatever its stored form (absolute or
        relative).
        If context is given and is a (direct or indirect) importer package,
        the URI will be resolved with respect to the context URI, whatever its
        stored form (absolute or relative).

        You would probably rather use the uri read-only property, unless you
        want to set the parameter _absolute_.
        """
        base = self.__base.getUri (absolute, context)
        id_ = Ided.getId (self) # avoid overridden versions of getId
        return advene.model.util.uri.push (base, id_)

    uri = property(getUri)

class Ased(object):
    """An implementation for the 'as' property.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
       Note that this implementation consider 'as' to be optional.
    """
    def getAs(self):
        """Return the 'as' attribute.
           You would probably rather use the 'as' property.
        """
        return self._getModel().getAttributeNS(None, "as")

    def setAs(self, value):
        """Set the 'as' attribute.
           You would probably rather use the 'as' property.
        """
        if value:
            self._getModel().setAttributeNS(None, "as", unicode(value))
        else:
            self._getModel().removeAttributeNS(None, "as")

    def delAs(self):
        """Unbind the 'as' attribute.
           You would probably rather use the 'as' property.
        """
        self.setAs(None)

    as = property(getAs, setAs, delAs)

class Hrefed(object):
    """An implementation for the 'href' property.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
       Note that this implementation consider 'href' to be required.
    """
    def getHref(self):
        """Return the 'href' attribute.
           You would probably rather use the 'href' property.
        """
        return self._getModel().getAttributeNS(xlinkNS, "href")

    def setHref(self, value):
        """Set the 'href' attribute.
           You would probably rather use the 'href' property.
        """
        if value:
            self._getModel().setAttributeNS(xlinkNS, "xlink:href", unicode(value))
        else:
            raise AttributeError("href is a required attribute")

    def delHref(self):
        """Always raises an exception since href is a required attribute.
        """
        self.setHref(None)

    href = property(getHref, setHref, delHref)
