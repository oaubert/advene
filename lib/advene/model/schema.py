import _impl
import annotation
import modeled
import viewable

import util.mimetype
import util.uri

from bundle import ImportBundle
from constants import *

from util.auto_properties import auto_properties

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

    def getMimetype(self):
        """Return the mime type of the element (None if not defined)"""
        content_type = self._getChild((adveneNS, 'content-type'))
        if content_type:
            return content_type.getAttributeNS(None, 'mime-type')
        else:
            return None

    def setMimetype(self, value):
        """
        FIXME
        """
        util.mimetype.MimeType (value)
        content_type = self._getChild((adveneNS, 'content-type'))
        if content_type is None:
            model = self._getModel ()
            content_type = model.createElementNS (adveneNS, 'content-type')
            model.appendChild (content_type)
            
        content_type.setAttributeNS(None, 'mime-type', value)

    def getId (self):
        """
        Handle a special case when a type is defined in an imported schema.
        The type does not consider itself to be imported (which is true wrt the
        schema) but is (indirectly) imported wrt to the package.
        """
        id = super (AbstractType, self).getId ()
        schema = self.getSchema()
        if not self.isImported () and schema.isImported ():
            prefix = self.getRootPackage ().getQnamePrefix (schema._getParent())
            return "%s:%s" % (prefix, id)
        else:
            return id
            

class AnnotationType(AbstractType,
                     viewable.Viewable.withClass('annotation-type')):
    """Annotation Type element. Is Viewable and has a content."""
    #__metaclass__ = auto_properties

    def __init__(self, parent, element):
        AbstractType.__init__(self, parent, element,
                            parent.getOwnerPackage().getAnnotationTypes.im_func)

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

    def __init__(self, parent, element):
        AbstractType.__init__(self, parent, element,
                            parent.getOwnerPackage().getRelationTypes.im_func)

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

    def __init__(self, parent, element):
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



