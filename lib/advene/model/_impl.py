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
import xml.dom
import urllib.request, urllib.parse, urllib.error

from io import StringIO

import advene.model.util.uri

from advene.model.constants import adveneNS, dcNS, xlinkNS, TEXT_NODE, ELEMENT_NODE

# TODO: let in here only classes which have no __init__ methods
#       (i.e. which can be inherited without further adaptation to the
#        inheriting class)

class Metaed:
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
            doc = self._getModel().ownerDocument
            meta = doc.createElementNS(adveneNS,"meta")
            self._getModel().childNodes.insert(0, meta)
        return meta

    def _getMetaElement(self, namespace_uri, name, create=False):
        meta = self._getMeta(create)
        if meta is None:
            return None

        for e in meta.childNodes:
            if e.nodeType is ELEMENT_NODE \
            and e.namespaceURI == namespace_uri \
            and e.localName == name:
                return e

        if create:
            doc = meta.ownerDocument
            e = doc.createElementNS(namespace_uri, name)
            # TODO the following could be managed automatically (and better)
            # by the serialization, but with minidom it seems that there's no
            # smart serializer, so...
            e.setAttribute("xmlns", namespace_uri)
            meta.childNodes.insert(0, e)
            return e
        else:
            return None

    def elementValue(self, dom_element):
        """Return the text content of the DOM element.
        """
        r = StringIO()
        advene.model.util.dom.printElementText(dom_element, r)
        return r.getvalue()

    def getMetaData(self, namespace_uri, name):
        """Return the text content of metadata with given NS and name
        """
        n='{%s}%s' % (namespace_uri, name)
        if n in self.meta_cache:
            return self.meta_cache[n]
        e = self._getMetaElement(namespace_uri, name)
        if e is None:
            return None

        self.meta_cache[n]=self.elementValue(e)
        return self.meta_cache[n]

    def setMetaData(self, namespace_uri, name, value):
        """Set the metadata with given NS and name
        """
        n='{%s}%s' % (namespace_uri, name)
        create = (value is not None)
        e = self._getMetaElement(namespace_uri, name, create)

        if value is None:
            if e is not None:
                if n in self.meta_cache:
                    del self.meta_cache[n]
                self._getMeta ().removeChild (e)
            return

        for c in e.childNodes:
            if c.nodeType in (TEXT_NODE, ELEMENT_NODE):
                e.removeChild(c)
        if value is not None:
            new = e.ownerDocument.createTextNode(value)
            e.appendChild(new)
            self.meta_cache[n]=value

    def listMetaData(self):
        """Return a list of tuples (namespace_uri, name, value) for all defined metadata.
        """
        meta = self._getMeta()
        if meta is None:
            return []

        return [ (e.namespaceURI, e.localName, self.elementValue(e))
                 for e in meta.childNodes
                 if e.nodeType is ELEMENT_NODE ]

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
        for n in authorelt.childNodes:
            if n.nodeType==TEXT_NODE:
                s += n.data
                authorelt.removeChild (n)
        if s:
            author = s.replace (s.strip (), author) # try to keep layout
        return author

    def __setAuthorNode (self, author, authorUrl=None):
        attnode, eltnode = self.__prepareAuthorNodes ()

        if author is None:
            assert authorUrl is None, "authorUrl without author is impossible"
            if attnode:
                self._getModel ().removeAttributeNode (attnode)
            if eltnode:
                self._getMeta ().removeChild (eltnode)

        elif authorUrl is None:
            if eltnode is None:
                self._getModel ().setAttributeNS (dcNS, 'dc:creator', author)
            else:
                if eltnode.hasAttributeNS (xlinkNS, 'href'):
                    eltnode.removeAttributeNS (xlinkNS, 'href')
                author = self.__cleanAuthorElementAndGetLayout (eltnode, author)
                textnode = eltnode.ownerDocument.createTextNode (author)
                eltnode.appendChild (textnode)

        else: #authorUrl is not None
            if attnode:
                self._getModel ().removeAttributeNode (attnode)

            doc = self._getModel ().ownerDocument

            if eltnode is None:
                eltnode = self._getMetaElement (dcNS, 'creator', create=True)
            else:
                author = self.__cleanAuthorElementAndGetLayout (eltnode, author)

            textnode = doc.createTextNode(author)
            eltnode.appendChild(textnode)
            eltnode.setAttributeNS(xlinkNS, "xlink:href", str(authorUrl))
  #
  # public methods
  #
    def getAuthor(self):
        """Return the author or None.
           You would probably rather use the author property.
        """
        attnode, eltnode = self.__prepareAuthorNodes()
        if attnode:
            return attnode.value
        if eltnode:
            s = ""
            found = 0
            for n in eltnode.childNodes:
                if n.nodeType==TEXT_NODE:
                    found = 1
                    s += n.data
            if found:
                return s.strip()
        return None

    def getAuthorUrl(self):
        """Return the author URL or None.
           You would probably rather use the authorUrl property.
        """
        attnode, eltnode = self.__prepareAuthorNodes()
        if eltnode and eltnode.hasAttributeNS (xlinkNS, 'href'):
            return eltnode.getAttributeNS (xlinkNS, 'href')
        return None

    def setAuthor(self, value):
        """Set the author.
           You would probably rather use the author property.
        """
        if value or (self._getModel().parentNode
                     and self._getModel().parentNode.nodeType==ELEMENT_NODE):
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


class Tagged(Metaed):
    """Implementation of the tags support.

    Tags are stored as a comma-separated list of strings.  An optional
    namespace may be provided, in order to store different kinds of
    tags.

    Warning: the tags property returns a *copy* of the list of
    tags. To add or remove elements, use addTag and removeTag methods.
    """
    def _getTagsMeta(self, ns=None):
        """Returns a set of tags
        """
        if ns is None:
            ns=adveneNS
        tagmeta = self.getMetaData (ns, "tags")
        if tagmeta is None:
            return []
        else:
            return [ urllib.parse.unquote(t) for t in tagmeta.split(',') ]

    def _updateTagsMeta(self, tagset, ns=None):
        """Update the tags metadata.

        Expects a set of tags and a namespace-uri
        """
        if ns is None:
            ns=adveneNS
        if tagset:
            self.setMetaData (ns, "tags", ','.join( [ urllib.parse.quote(t) for t in tagset ] ))
        else:
            if self.getMetaData (ns, "tags"):
                self.setMetaData (ns, "tags", None)

    def addTag(self, tag, ns=None):
        """Add a new tag.
        """
        tagset = self._getTagsMeta(ns)
        if tag not in tagset:
            tagset.append(tag)
        self._updateTagsMeta(tagset, ns)
        return tagset

    def removeTag(self, tag, ns=None):
        """Remove a tag
        """
        tagset = self._getTagsMeta(ns)
        try:
            tagset.remove(tag)
        except ValueError:
            pass
        self._updateTagsMeta(tagset, ns)
        return tagset

    def hasTag(self, tag, ns=None):
        """Check for the presence of a tag
        """
        return tag in self._getTagsMeta(ns)

    def getTags(self, ns=None):
        """Return the list of tags.
        """
        return self._getTagsMeta(ns)

    def setTags(self, tagset, ns=None):
        self._updateTagsMeta(tagset, ns)
        return self.getTags()

    def delTags(self, ns=None):
        self._updateTagsMeta( [], ns )

    tags = property(getTags, setTags, delTags)

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
        if value is not None:
            self._getModel().setAttributeNS(dcNS, "dc:date", str(value))
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
        if value is not None:
            if self._getModel().hasAttributeNS(dcNS, "title"):
                self._getModel().setAttributeNS(dcNS, "dc:title",
                                                str(value))
            else:
                self.setMetaData(dcNS, "title", str(value))
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


class Ided:
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
            self._set_id (self._getModel(), value)
        else:
            raise AttributeError("id is a required attribute")

    id = property(getId, setId)

    @staticmethod
    def _set_id (element, value):
        element.setAttributeNS(None, "id", str(value))


class __dummy:
    def __init__(self, uri):
        self.__uri = uri

    def getUri(self, absolute=True, context=None):
        return self.__uri


class Uried(Ided):
    """An implementation for the id property interpreted as a URI fragment.
    """

    def __init__(self, base_uri="", parent=None):
        """The constructor of URIed takes either a base_uri parameter
           or a parent object providing the base URI with a getURI method.
           If both are given, base_uri is ignored.
        """
        self.meta_cache={}
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

class Aliased:
    """An implementation for the 'alias' property.
       Inheriting classes must have a _getModel method returning a DOM element
       (inheriting the modeled.Modeled class looks like a good idea).
       Note that this implementation consider 'alias' to be optional.

       Note: for historical reasons, this property is stored with the
       name "as" in the DOM tree. This original name introduced a
       clash in python2.6 with a reserved keyword. It has thus been
       renamed in the python code, but preserved in the DOM tree for
       compatibility issues.
    """
    def getAlias(self):
        """Return the 'alias' attribute.
           You would probably rather use the 'alias' property.
        """
        return self._getModel().getAttributeNS(None, "as")

    def setAlias(self, value):
        """Set the 'alias' attribute.
           You would probably rather use the 'alias' property.
        """
        if value:
            self._getModel().setAttributeNS(None, "as", str(value))
        else:
            self._getModel().removeAttributeNS(None, "as")

    def delAlias(self):
        """Unbind the 'alias' attribute.
           You would probably rather use the 'as' property.
        """
        self.setAlias(None)

    alias = property(getAlias, setAlias, delAlias)

class Hrefed:
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
            self._getModel().setAttributeNS(xlinkNS, "xlink:href", str(value))
        else:
            raise AttributeError("href is a required attribute")

    def delHref(self):
        """Always raises an exception since href is a required attribute.
        """
        self.setHref(None)

    href = property(getHref, setHref, delHref)
