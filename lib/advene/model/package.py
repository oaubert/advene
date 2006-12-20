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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""A package to manipulate elements from the Advene model.
"""

import os
import sys
import urllib
import sre

import xml.dom.ext.reader.PyExpat
import xml.sax

import util.uri

from util.auto_properties import auto_properties

import advene.core.config as config
import _impl
import advene.model.annotation as annotation
import advene.model.modeled as modeled
import advene.model.query as query
import advene.model.schema as schema
import advene.model.view as view
import advene.model.viewable as viewable
from advene.model.zippackage import ZipPackage

from advene.model.bundle import StandardXmlBundle, ImportBundle, InverseDictBundle, SumBundle
from advene.model.constants import *
from advene.model.exception import AdveneException

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
        if sre.match('[a-zA-Z]:', uri):
            # Windows drive: notation. Convert it to
            # a more URI-compatible syntax
           uri=urllib.pathname2url(uri)
        self.__uri = uri
        self.__importer = importer
        # Possible container
        self.__zip = None
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
                # Determine the package format (plain XML or AZP)
                # FIXME: should be done by content rather than extension
                if abs_uri.lower().endswith('.azp'):
                    # Advene Zip Package. Do some magic.
                    self.__zip = ZipPackage(abs_uri)
                    f=urllib.pathname2url(self.__zip.getContentsFile())
                    element = reader.fromUri("file://" + f)._get_documentElement()    
                else:
                    element = reader.fromUri(abs_uri)._get_documentElement()
            elif hasattr(source, 'read'):
                element = reader.fromStream(source)._get_documentElement()
            else:
		if sre.match('[a-zA-Z]:', source):
		    # Windows drive: notation. Convert it to
		    # a more URI-compatible syntax
		    source=urllib.pathname2url(source)
                source_uri = util.uri.urljoin (
                    'file:%s/' % urllib.pathname2url (os.getcwd ()),
                     str(source)
                )

                if source_uri.endswith('.azp') or source_uri.endswith('.AZP'):
                    # Advene Zip Package. Do some magic.
                    self.__zip = ZipPackage(source_uri)
                    f=urllib.pathname2url(self.__zip.getContentsFile())
                    element = reader.fromUri("file://" + f)._get_documentElement()    
                else:
                    element = reader.fromUri(source_uri)._get_documentElement()

        modeled.Modeled.__init__(self, element, None)

        self.__imports = None
        self.__annotations = None
        self.__queries = None
        self.__relations = None
        self.__schemas = None
        self.__views = None

    def close(self):
        if self.__zip:
            self.__zip.close()
        return

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

    def getResources(self):
        if self.__zip is None:
            return None
        else:
            return self.__zip.getResources(package=self)

    def get_element_by_id(self, i):
        for m in (self.getSchemas, self.getViews, self.getAnnotationTypes,
                  self.getRelationTypes, self.getAnnotations,
                  self.getRelations):
            for el in m():
                if el.id == i:
                    return el
        return None

    def generate_statistics(self):
        """Generate the statistics.xml file.
        """
        out=u"""<?xml version="1.0" encoding="UTF-8"?>
    <statistics:statistics xmlns:statistics="urn:advene:names:tc:opendocument:xmlns:manifest:1.0">
    """
        out += """<statistics:title value="%s" />""" % urllib.quote(self.title)
        out += """<statistics:description value="%s" />""" % urllib.quote(self.getMetaData(config.data.namespace_prefix['dc'], 'description'))
        for n, l in ( ('schema', len(self.schemas)),
                      ('annotation', len(self.annotations)),
                      ('annotation_type', len(self.annotationTypes)),
                      ('relation', len(self.relations)),
                      ('relation_type', len(self.relationTypes)),
                      ('query', len(self.queries)),
                      ('view', len(self.views)) ):
            out += """<statistics:item name="%s" value="%d" />""" % (n, l)
        out += """</statistics:statistics>"""
        return out
    
    def serialize(self, stream=sys.stdout):
        """Serialize the Package on the specified stream"""
        xml.dom.ext.PrettyPrint(self._getModel(), stream)
    
    def save(self, name=None):
        """Save the Package in the specified file"""
        if name is None:
            name=self.__uri
        if name.startswith('file:///'):
            name = name[7:]

        if sre.match('|/', name):
            # Windows drive: notation. Convert it from
            # a more URI-compatible syntax
            name=urllib.url2pathname(name)
	    
        # handle .azp files.
        if name.endswith('.azp') or name.endswith('.AZP'):
            # AZP format
            if self.__zip is None:
                # Conversion necessary: we are saving to the new format.
                z=ZipPackage()
                z.new()
                self.__zip = z

            # Save the content.xml 
            stream = open (self.__zip.getContentsFile(), "w")
            self.serialize(stream)
            stream.close ()
            
            # Generate the statistics
            self.__zip.update_statistics(self)

            # Save the whole .azp
            self.__zip.save(name)
        else:
            # Assuming plain XML format
            stream = open (name, "w")
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
	if self == item:
	    return None
        if isinstance (item, Package):
	    try:
		i=self.getImports()[item.uri]
		return i.getAs()
	    except KeyError:
		raise AdveneException ("item %s has no QName prefix in %s" %
				       (item, self))
	else:
	    return self.getQnamePrefix(item._getParent())


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

	    if sre.match('[a-zA-Z]:', uri):
		# Windows drive: notation. Convert it to
		# a more URI-compatible syntax
		uri=urllib.pathname2url(uri)

            # doc = self._getParent()._getDocument()
            doc = parent._getDocument()
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
            base_uri = self.getOwnerPackage().getUri(absolute=True)
            return util.uri.urljoin(base_uri, rel_uri)
        else:
            return rel_uri

    def setUri(self, uri):
        """Set the URI of the element"""
	if sre.match('[a-zA-Z]:', uri):
	    # Windows drive: notation. Convert it to
	    # a more URI-compatible syntax
	    uri=urllib.pathname2url(uri)
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

class StatisticsHandler(xml.sax.handler.ContentHandler):
    """Parse a statistics.xml file.
    """
    def __init__(self):
        # Data will contain parsed elements:
        # title, description, view, schema...
        self.data={}
 
    def startElement(self, name, attributes):
        if name == "statistics:title":
            self.data['title']=urllib.unquote(attributes['value'])
        elif name == 'statistics:description':
            self.data['description']=urllib.unquote(attributes['value'])
        elif name == 'statistics:item':
            self.data[attributes['name']]=int(attributes['value'])
    
    def parse_file(self, name):
        p=xml.sax.make_parser()
        p.setFeature(xml.sax.handler.feature_namespaces, False)
        p.setContentHandler(self)
        p.parse(name)
        return self.data
