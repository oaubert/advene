"""A package to manipulate elements from the Advene model.

See http://experience.univ-lyon1.fr:81/advene/
"""

import os
import sys
import urllib

import xml.dom.ext.reader.PyExpat

import util.uri

from util.auto_properties import auto_properties

import _impl
import annotation
import content
import modeled
import query
import schema
import view
import viewable

from bundle import StandardXmlBundle, ImportBundle, InverseDictBundle, SumBundle
from constants import *


# the following constant is used as a default value in in Package.__init__
# to know whether the passed uri must be used to get a stream.
# (source=None has a different meaning)
# FIXME: should be a "new" parameter in Package.__init__
_get_from_uri = object()

class Package(modeled.Modeled, viewable.Viewable.withClass('package'),
             _impl.Authored, _impl.Dated, _impl.Titled,
             annotation.AnnotationFactory,
             annotation.RelationFactory,
             schema.SchemaFactory,
             query.QueryFactory,
             view.ViewFactory,
             ):

    """A package is the container of all the elements of an annotation
    (schemas, types, annotations, relations, views, queries). It
    provides factory methods to create attached annotations, views, ..."""

    __metaclass__ = auto_properties
    
    def __init__(self, uri, source=_get_from_uri, importer=None):
        """Calling the constructor with just a URI tries to read the package
           from this URI. This can be overidden by providing explicitly the
           source parameter (a URL or a stream).
           Providing None for the source parameter creates a new Package.
        """
        self.__uri = uri
	self.__importer = importer
        abs_uri = self.getUri (absolute=True)

        if importer:
            importer.__pkg_cache[abs_uri] = self
            self.__pkg_cache = importer.__pkg_cache
        else:
            self.__pkg_cache = {abs_uri:self}

        element = None
        if source is None:
            element = self._make_model()
        else:
            reader = xml.dom.ext.reader.PyExpat.Reader()
            if source is _get_from_uri:
                element = reader.fromUri(abs_uri)._get_documentElement()
            elif hasattr(source,'read'):
                element = reader.fromStream(source)._get_documentElement()
            else:
                source_uri = util.uri.urljoin (
                    'file:%s/' % urllib.pathname2url (os.getcwd ()),
                     str(source)
                )
                element = reader.fromUri(source_uri)._get_documentElement()

        modeled.Modeled.__init__(self, element, None)

        self.__imports = None
        self.__annotations = None
        self.__queries = None
        self.__relations = None
        self.__schemas = None
        self.__views = None

    
    def __str__(self):
        """Return a nice string representation of the object."""
        return "Package (%s)" % self.__uri

    def _make_model(self):
        """Build a new empty annotation model"""
        di = xml.dom.DOMImplementation.DOMImplementation()
        doc = di.createDocument(adveneNS, "package", None)

        elt = doc._get_documentElement()
        elt.setAttributeNS(xmlNS,   "xml:base", unicode(self.__uri))
        elt.setAttributeNS(xmlnsNS, "xmlns", adveneNS)
        elt.setAttributeNS(xmlnsNS, "xmlns:xlink", xlinkNS)
        elt.setAttributeNS(xmlnsNS, "xmlns:dc", dcNS)
        elt.setAttributeNS(dcNS,    "dc:creator", "")

        elt.appendChild(doc.createElementNS(adveneNS, "imports"))
        elt.appendChild(doc.createElementNS(adveneNS, "annotations"))
        elt.appendChild(doc.createElementNS(adveneNS, "queries"))
        elt.appendChild(doc.createElementNS(adveneNS, "schemas"))
        elt.appendChild(doc.createElementNS(adveneNS, "views"))
        return elt

    def _get_cached(self, uri):
        """Return a cached version of the package designated by "uri" """
        return self.__pkg_cache.get(uri,None)

    def getOwnerPackage(self):
        """Return this package. Used for breaking recursivity in the parenthood tree."""
        return self

    def getAccessPath(self):
        if self.__importer:
	    r = list(self.__importer.getAccessPath())
	    r.append(self)
	    return tuple(r)
	else:
	    return (self,)

    def getRootPackage(self):
        if self.__importer:
	    return self.__importer.getRootPackage()
	else:
	    return self
	   
    def getUri(self, absolute=True, context=None):
        """
        Return the URI of the package.

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
        uri = self.__uri

        if not absolute and context is self:
            return ''

        importer = self.__importer
        if importer is not None:
            uri = util.uri.urljoin (importer.getUri (absolute, context), uri)
        if absolute:
            base_uri = 'file:%s/' % urllib.pathname2url (os.getcwd ())
            uri = util.uri.urljoin(base_uri, uri)
            
        return uri

    def getImports (self):
        """Return a collection of this package's imports"""
        if self.__imports is None:
            e = self._getChild ( (adveneNS, "imports") )
            self.__imports = InverseDictBundle (self, e, Import, Import.getAs)
        return self.__imports

    def getAnnotations(self):
        """Return a collection of this package's annotations"""
        if self.__annotations is None:
            e = self._getChild((adveneNS, "annotations"))
            self.__annotations = StandardXmlBundle(self, e, annotation.Annotation)
        return self.__annotations

    def getRelations(self):
        """Return a collection of this package's relations"""
        if self.__relations is None:
            e = self._getChild((adveneNS, "annotations"))
            # yes, "annotations"!
            #relations are under the same element as annotations
            # FIXME: is this always the case ?
            self.__relations = StandardXmlBundle(self, e, annotation.Relation)
        return self.__relations

    def getSchemas(self):
        """Return a collection of this package's schemas"""
        if self.__schemas is None:
            e = self._getChild((adveneNS, "schemas"))
            self.__schemas = ImportBundle(self, e, schema.Schema)
        return self.__schemas

    def getViews(self):
        """Return a collection of this package's view"""
        if self.__views is None:
            e = self._getChild((adveneNS, "views"))
            self.__views = ImportBundle(self, e, view.View)
        return self.__views

    def getQueries(self):
        """Return a collection of this package's queries"""
        if self.__queries is None:
            e = self._getChild((adveneNS, "queries"))
            self.__queries = ImportBundle(self, e, query.Query)
        return self.__queries

    def getAnnotationTypes (self):
        """Return a collection of this package's annotation types"""
        r = SumBundle ()
        for s in self.getSchemas ():
            r += s.getAnnotationTypes ()
        return r

    def getRelationTypes(self):
        """Return a collection of this package's relation types"""
        r = SumBundle ()
        for s in self.getSchemas ():
            r += s.getRelationTypes ()
        return r

    def serialize(self, stream=sys.stdout):
        """Serialize the Package on the specified stream"""
        xml.dom.ext.PrettyPrint(self._getModel(), stream)
    
    def save(self, as=None):
        """Save the Package in the specified file"""
        if as is None:
            as=self.__uri
        if as.startswith('file:///'):
            as = as[7:]

        stream = open (as, "w")
        self.serialize(stream)
        stream.close ()

    def _recursive_save (self):
        """Save recursively this packages with all its imported packages"""
        try:
            self.save ()
        except:
            pass
        for i in self.getImports ():
            i.getPackage ()._recursive_save ()

    def getQnamePrefix (self, item):
        if isinstance (item, Package):
            for i in self.getImports():
                if item == i.getPackage():
                    return i.getAs()
        elif isinstance (item, Schema):
            for s in self.getSchemas():
                if item == s:
                    return s.getId()
        raise AdveneException ("item %s has no QName prefix in %s" %
                               (item, self))


class Import(modeled.Modeled, _impl.Ased):
    """Import represents the different imported elements"""
    __metaclass__ = auto_properties

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "import"
    getLocalName = staticmethod(getLocalName)

    __loaded_package = None

    def __init__(self, parent, element = None, uri = None):
        """FIXME"""
        if element is None:
            if uri is None:
                raise TypeError("parameter 'uri' required")
            doc = self._getParent()._getDocument()
            element = doc.createElementNS(adveneNS, 'import')
            element.setAttributeNS(xlinkNS, 'xlink:href', uri)
        else:
            if uri is not None:
                raise TypeError("incompatible parameter 'uri'")
        modeled.Modeled.__init__(self, element, parent)

    def getUri(self, absolute=True):
        """
        Return the URI of the element.

        If parameter absolute is set to _true_, the URI will be forced
        absolute, else it will be returned in its stored form (which could
        be absolute or relative).

        You would probably rather use the uri read-only property, unless you
        want to set the parameter _absolute_.
        """
        rel_uri =  self._getModel().getAttributeNS(xlinkNS, 'href')
        if absolute:
            base_uri = self.getOwnerPackage().getUri(absolute)
            return util.uri.urljoin(base_uri, rel_uri)
        else:
            return rel_uri

    def setUri(self, uri):
        """Set the URI of the element"""
        return self._getModel().setAttributeNS(xlinkNS, 'xlink:href', uri)

    def getSources(self):
        """Return the different sources of imported elements"""
        r = []
        for i in self._getModelChildren():
            r.append(i.getAttributeNS(xlinkNS, 'href'))
        return tuple(r)

    def setSources(self, list):
        """Set the sources of imported elements"""
        for i in self._getModelChildren():
            self._getModel().removeChild(i)
        for i in list:
            e = self._getDocument().createElementNS(adveneNS, 'source')
            e.setAttributeNS(xlinkNS, 'xlink:href', i)
            self._getModel().appendChild(e)

    def getPackage(self):
        """Return the imported package"""
        cached = self._getParent ()._get_cached (self.getUri (absolute=True))
        if cached is None:
            uri = self.getUri (absolute=False)
            for url in self.getSources():
                try:
                    base_url = self._getParent ().getUri (absolute=True)
                    url = util.uri.urljoin (base_url, url)
                    cached = Package(uri, source=url,
                                     importer=self._getParent())
                    break
                except:
                    pass
            if cached is None:
                cached = Package(uri, importer=self._getParent())
            # NB: creating the package with parameter 'importer' DOES put it
            #     in the importer's cache. So we don't need to do it here.
        return cached

    def getId(self):
        """
        The 'as' attribute is used as the import's ID, including when 
        populating bundle.
        """
        return self.getAs()
