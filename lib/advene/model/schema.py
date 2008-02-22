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
import advene.model._impl as _impl
import advene.model.content as content
import advene.model.modeled as modeled
import advene.model.viewable as viewable

import advene.model.util.mimetype

from advene.model.bundle import ImportBundle
from advene.model.constants import *

from advene.model.util.auto_properties import auto_properties

import xml.dom
ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE

class AbstractType(modeled.Importable,
                   _impl.Uried, _impl.Authored, _impl.Dated, _impl.Titled):

    __metaclass__ = auto_properties

    def __init__(self, parent, element, locator):
        modeled.Importable.__init__(self, element, parent, locator)
        _impl.Uried.__init__(self, parent=self.getOwnerPackage())

    # dom dependant methods

    def getSchema(self):
        """Return the schema containing this type"""
        return self._getParent()

    def getId (self):
        """
        Handle a special case when a type is defined in an imported schema.
        The type does not consider itself to be imported (which is true wrt the
        schema) but is (indirectly) imported wrt to the package.
        """
        ident = super (AbstractType, self).getId ()
        schema = self.getSchema()
        if not self.isImported () and schema.isImported ():
            prefix = self.getRootPackage ().getQnamePrefix (schema._getParent())
            return "%s:%s" % (prefix, ident)
        else:
            return ident


    # contentv type implementation

    def __get_content_type_element (self):
        return self._getChild (match=(adveneNS, 'content-type'))

    def getMimetype (self):
        """If this annotation type has a content-type, return its
        mime-type, else return None."""
        cte = self.__get_content_type_element ()
        if cte is not None:
            return cte.getAttributeNS (None, 'mime-type')
        return None

    def setMimetype (self, value):
        """Set the mime-type of this type's content-type. Create the content
        type if necessary. If value is None, remove the content-type. """
        cte = self.__get_content_type_element ()
        if value is not None:
            advene.model.util.mimetype.MimeType (value)
            if cte is None:
                cte = self._getDocument ().createElementNS (adveneNS, "content-type")
                self._getModel ().appendChild (cte)
            cte.setAttributeNS (None, 'mime-type', unicode (value))
        else:
            if cte is not None:
                self._getModel ().removeChild (cte)

    def delMimetype (self):
        """Remove this annotation-type's content-type."""
        self.setMimetype (None)


    def __get_content_schema_element (self, cte = None):
        if cte is None:
            cte = self.__get_content_type_element ()
        if cte is None:
            raise TypeError ('schema has not content-type, cannot have content-schema')
        cselist = cte.getElementsByTagNameNS (adveneNS, 'content-schema')
        if len (cselist) > 0:
            return cselist[0]
        return None


    __content_schema = None

    def getContentSchema (self):
        if self.__content_schema is None:
            cse = self.__get_content_schema_element ()
            if cse is not None:
                self.__content_schema = content.Content (self, cse)
        return self.__content_schema

    def delContentSchema (self):
        cte = self.__get_content_type_element ()
        if cte is None:
            return
        if self.__content_schema is not None:
            cse = self.__content_schema._getModel ()
            del self.__content_schema
        else:
            cse = self.__get_content_schema_element (cte)
        cte.removeChild (cse)

    def addContentSchema (self, mimetype):
        cte = self.__get_content_type_element ()
        if cte is None:
            raise TypeError ('schema has not content-type, cannot have content-schema')
        cse = self._getDocument ().createElementNS (adveneNS, 'content-schema')
        cte.appendChild (cse)
        self.getContentSchema ().setMimetype (mimetype)


class AnnotationType(AbstractType,
                     viewable.Viewable.withClass('annotation-type')):
    """Annotation Type element. Is Viewable and has a content."""
    #__metaclass__ = auto_properties

    def __init__(self, # mode 1 & 2
                 parent, # mode 1 & 2,
                 element = None, # mode 1
                 ident = None, # mode 2
                ):
        """
        The constructor has two modes of calling
         - giving it a DOM element (constructing from XML)
         - giving it ident (constructing from scratch)
        """
        if element is not None:
            # should be mode 1, checking parameter consistency
            if ident is not None:
                raise TypeError("incompatible parameter 'ident'")
            # mode 1 initialization
            AbstractType.__init__(self, parent, element,
                            parent.getOwnerPackage().getAnnotationTypes.im_func)

        else:
            # should be mode 2, checling parameter consistency
            if ident is None:
                raise TypeError("parameter 'ident' required")

            # mode 2 initialization
            doc = parent._getDocument()
            element = doc.createElementNS(self.getNamespaceUri(),
                                          self.getLocalName())
            AbstractType.__init__(self, parent, element,
                            parent.getOwnerPackage().getAnnotationTypes.im_func)
            self.setId(ident)


    def __str__(self):
        """Return a nice string representation of the element"""
        return "AnnotationType <%s>" % self.getUri()

    def create (self, fragment, **kw):
        """
        FIXME
        """
        pkg = self.getRootPackage ()
        a = pkg.createAnnotation (type=self, fragment=fragment, **kw)
        return a

    # dom dependant methods

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "annotation-type"
    getLocalName = staticmethod(getLocalName)

    def getAnnotations (self):
        # FIXME: return an iterator instead of a full fledged list
        return [ a for a in self.getRootPackage ().getAnnotations ()
                   if a.getType() == self ]



class RelationType(AbstractType,
                   viewable.Viewable.withClass('relation-type')):
    """Relation Type element. Is Viewable and has a content."""

    #__metaclass__ = auto_properties

    def __init__(self, # mode 1 & 2
                 parent, # mode 1 & 2,
                 element = None, # mode 1
                 ident = None, # mode 2
                ):
        """
        The constructor has two modes of calling
         - giving it a DOM element (constructing from XML)
         - giving it ident (constructing from scratch)
        """
        if element is not None:
            # should be mode 1, checking parameter consistency
            if ident is not None:
                raise TypeError("incompatible parameter 'ident'")
            # mode 1 initialization
            AbstractType.__init__(self, parent, element,
                            parent.getOwnerPackage().getRelationTypes.im_func)

        else:
            # should be mode 2, checling parameter consistency
            if ident is None:
                raise TypeError("parameter 'ident' required")

            # mode 2 initialization
            doc = parent._getDocument()
            element = doc.createElementNS(self.getNamespaceUri(),
                                          self.getLocalName())
            AbstractType.__init__(self, parent, element,
                            parent.getOwnerPackage().getRelationTypes.im_func)
            self.setId(ident)

    def __str__(self):
        """Return a nice string representation of the element"""
        return "RelationType <%s>" % self.getUri()

    # dom dependant methods

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "relation-type"
    getLocalName = staticmethod(getLocalName)

    def getRelations (self):
        # FIXME: return an iterator instead of a full fledged list
        return [ a for a in self.getRootPackage ().getRelations ()
                   if a.getType() == self ]

    def getHackedMemberTypes (self):
        """
        Return a tuple of the member type's URIs
        TODO: remove this method.
        As its name implies, this is an awful, temporary hack.
        However, I do not have time to do better now, and Olivier needs it.
        Ideally, I should use a bundle here, but bundles do not accept multiple
        occurences of the same element, which can happen here.
        So bundle.py should be improved, with a basic Bundle class behaving only like a list, and an advanced Bundle, behaving like both a list and a dict.
        """
        e = self._getChild((adveneNS, "member-types"))
        if e is None:
            return []
        l = []
        for i in e._get_childNodes ():
            if i._get_nodeType() is ELEMENT_NODE:
                try:
                    uri = i.getAttributeNS (xlinkNS, 'href')
                    l.append (uri)
                except:
                    l.append (None)
        return tuple (l)

    def setHackedMemberTypes (self, membertypes):
        """Update the membertypes of a relationtype.

        membertypes is a list of URIs
        """
        e = self._getChild((adveneNS, "member-types"))
        if e is None:
            # we have to create it
            e = self._getDocument ().createElementNS (adveneNS, "member-types")
            self._getModel ().appendChild (e)
        else:
            # we have to empty it
            while e._get_childNodes ():
                c=e._get_firstChild()
                e.removeChild(c)
        # Create the children nodes
        for m in membertypes:
            c = self._getDocument ().createElementNS (adveneNS, "member-type")
            if m is not None:
                c.setAttributeNS (xlinkNS, 'xlink:href', unicode(m))
            e.appendChild (c)
        return True

# simple way to do it,
# AnnotationTypeFactory = modeled.Factory.of (AnnotationType)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class AnnotationTypeFactory (modeled.Factory.of (AnnotationType)):
    """
    FIXME
    """
    pass

# simple way to do it,
# RelationTypeFactory = modeled.Factory.of (RelationType)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class RelationTypeFactory (modeled.Factory.of (RelationType)):
    """
    FIXME
    """
    pass




class Schema(modeled.Importable,
             viewable.Viewable.withClass('schema'),
             _impl.Uried, _impl.Authored, _impl.Dated, _impl.Titled,
             AnnotationTypeFactory, RelationTypeFactory):
    """A Schema defines Annotation types and Relation types."""
    __metaclass__ = auto_properties

    def __init__(self, parent, element=None, ident=None):
        """
        The constructor has two modes of calling
         - giving it a DOM element (constructing from XML)
         - giving it ident (constructing from scratch)
        """

        if element is not None:
            # should be mode 1, checking parameter consistency
            if ident is not None:
                raise TypeError("incompatible parameters 'element' and 'ident'")
        else:
            # should be mode 2, checking parameter consistency
            if ident is None:
                raise TypeError("parameter 'element' or 'ident' is required")
            # mode 2 initialization
            doc = parent._getDocument()
            element = doc.createElementNS(self.getNamespaceUri(),
                                          self.getLocalName())
            _impl.Ided._set_id (element, ident)

            e = doc.createElementNS(self.getNamespaceUri(), "annotation-types")
            element.appendChild(e)
            e = doc.createElementNS(self.getNamespaceUri(), "relation-types")
            element.appendChild(e)

        # common to mode 1 and mode 2
        modeled.Importable.__init__(self, element, parent,
                                    locator=parent.getSchemas.im_func)

        _impl.Uried.__init__(self, parent=self._getParent())

        self.__annotation_types = None
        self.__relation_types = None

    def __str__(self):
        """Return a nice string representation for the Schema"""
        return "Schema <%s>" % self.getUri()

    # dom dependant methods

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "schema"
    getLocalName = staticmethod(getLocalName)

    def getAnnotationTypes(self):
        """Return a collection of this schema's annotation types"""
        if self.__annotation_types is None:
            e = self._getChild((adveneNS, "annotation-types"))
            self.__annotation_types = ImportBundle(self, e, AnnotationType)
        return self.__annotation_types

    def getRelationTypes(self):
        """Return a collection of this schema's relation types"""
        if self.__relation_types is None:
            e = self._getChild((adveneNS, "relation-types"))
            self.__relation_types = ImportBundle(self, e, RelationType)
        return self.__relation_types

# simple way to do it,
# SchemaFactory = modeled.Factory.of (Schema)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class SchemaFactory (modeled.Factory.of (Schema)):
    """
    FIXME
    """
    pass



