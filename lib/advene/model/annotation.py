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
import time

import util.uri

from util.auto_properties import auto_properties

import _impl
import bundle
import content
import modeled
import viewable

from constants import *
from exception import AdveneException
from fragment import fragmentFactory, unknownFragment

# From ASPN python cookbook
import copy

class DefaultDict(dict):
    """Dictionary with a default value for unknown keys."""
    def __init__(self, default=None, **items):
        dict.__init__(self, **items)
        self.default = default

    def __getitem__(self, key):
        if key in self: 
            return self.get(key)
        else:
            ## Need copy in case self.default is something like []
            return self.setdefault(key, copy.deepcopy(self.default))

    def __copy__(self):
        return DefaultDict(self.default, **self)

class Annotation(modeled.Importable, content.WithContent,
                 viewable.Viewable.withClass('annotation','_get_type_uri'),
                 _impl.Authored, _impl.Dated, _impl.Uried, _impl.Tagged):

    __metaclass__ = auto_properties

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "annotation"
    getLocalName = staticmethod(getLocalName)

    def __init__(self,                 # mode 1 & 2
                 parent,               # mode 1 & 2
                 element = None,       # mode 1, required
                 type = None,          # mode 2, required
                 fragment = None,      # mode 2, required
                 ident = None,         # mode 2, optional
                 date = None,          # mode 2, optional
                 author = None,        # mode 2, optional
                 authorUrl = None,     # mode 2, optional
                 context = None,       # mode 2, optional
                 content_data = None,  # mode 2, optional
                 content_stream = None,# mode 2, optional
                 ):
        """
        The constructor has two modes of calling
         - giving it a DOM element (constructing from XML)
         - giving it type,fragment,[ident],[date],[author],[authorUrl],
           [context],[content_data|content_stream] (constructing from scratch)
        """

        _impl.Uried.__init__(self, parent=parent)
        self.__fragment = None

        self._relations = [] # backrefs cache for relations

        if element is not None:
            # should be mode 1, checking parameter consistency
            if type is not None:
                raise TypeError("incompatible parameter 'type'")
            if fragment is not None:
                raise TypeError("incompatible parameter 'fragment'")
            if ident is not None:
                raise TypeError("incompatible parameter 'ident'")
            if date is not None:
                raise TypeError("incompatible parameter 'date'")
            if author is not None:
                raise TypeError("incompatible parameter 'author'")
            if authorUrl is not None:
                raise TypeError("incompatible parameter 'authorUrl'")
            if context is not None:
                raise TypeError("incompatible parameter 'context'")
            if content_data is not None:
                raise TypeError("incompatible parameter 'content_data'")
            if content_stream is not None:
                raise TypeError("incompatible parameter 'content_stream'")

            # mode 1 initialization
            modeled.Importable.__init__(self, element, parent)
            _impl.Uried.__init__(self, parent=self.getOwnerPackage())

        else:
            # should be mode 2, checking parameter consistency
            if type is None:
                raise TypeError("parameter 'type' required")
            if fragment is None:
                raise TypeError("parameter 'fragment' required")

            # mode 2 initialization
            doc = parent._getDocument()
            element = doc.createElementNS(Annotation.getNamespaceUri(),
                                          Annotation.getLocalName())
            modeled.Importable.__init__(self, element, parent)

            e = doc.createElementNS(None,"dummyFragment")
            self._getModel().appendChild(e)

            self.setType(type)
            # TODO: check that type is referenced in package
            self.setFragment(fragment)

            if ident is None:
                # FIXME: cf thread
                # Weird use of hash() -- will this work?
                # http://mail.python.org/pipermail/python-dev/2001-January/011794.html
                ident = u"a" + unicode(id(self)) + unicode(time.clock()).replace('.','')
            self.setId(ident)

            if date is not None: self.setDate(date)
            if author is not None: self.setAuthor(author)
            if authorUrl is not None: self.setAuthorUrl(authorUrl)
            if context is not None: self.setContext(context)
            if content_data is not None: self.getContent().setData(content_data)
            #if content_stream is not None: #TODO

    def __str__(self):
        """Return a nice string representation of the object."""
        return "Annotation %s:\"%s\"" % (self.getFragment(),
                                          self.getContent().getData())

    def __getFragmentElement(self):
        """Return the fragment element linked to this annotation"""
        return self._getChild(after=self._getMeta())

    def _get_type_uri(self, absolute=True):
        """Return the type URI - used to retrieve the viewable-type"""
        return self.getType().getUri(absolute)

    def getType(self):
        """Return the type of this annotation"""
        type_uri = self._getModel().getAttributeNS(None, "type")
        pkg_uri = self.getOwnerPackage ().getUri (absolute=True)
        type_uri = util.uri.urljoin (pkg_uri, type_uri)
        return self.getOwnerPackage().getAnnotationTypes()[type_uri]

    def setType(self, type):
        """Set the type of this annotation"""
        op = self.getOwnerPackage ()
        if type is None:
            raise AttributeError("type is a required attribute")
        elif type in op.getAnnotationTypes():
            type_uri = type.getUri (absolute=False, context=op)
            self._getModel().setAttributeNS(None, "type", type_uri)
        else:
            raise AdveneException("%s is not imported" % type.getUri ())

    def delType(self):
        """Always raises an exception since type is a required attributes"""
        self.setType(None)

    def getFragment(self):
        """Return the fragment associated to this annotation"""
        if self.__fragment is None:
            elt = self.__getFragmentElement()
            self.__fragment = fragmentFactory.makeFragment(elt,self)
        return self.__fragment

    def setFragment(self, fragment):
        """Set the fragment associated to this annotation"""
        if fragment is None:
            raise TypeError("fragment is required")
        if fragment is unknownFragment:
            raise TypeError("can not set fragment to unknownFragment")
        if fragment.isBounded():
            raise TypeError("can not affect bounded fragment "+\
                            "(you probably want to clone it before)")
        old = self.__getFragmentElement()
        fragment._bound(old)

    def delFragment(self):
        """Delete the fragment associated to this annotation"""
        self.setFragment(None)

    def getContext(self):
        pass

    def setContext(self, value):
        pass

    def delContext(self):
        self.setContext(None)

    def getRelations (self, rank=None, order=None):
        """
        Return all the relations involving this annotation.
        If parameter =rank= is given, only the relations where this annotation
        is the rank'th member are returned.
        If parameter =order= is given, only the relations with exactly =order=
        members are returned.
        """
        # ensure that relation objects have been created,
        # since it's them who populate self._relations
        self.getRootPackage ().getRelations ()

        if rank is None:
            if order is None:
                return self._relations
            else:
                return [
                  r for r in self._relations if len (r.getMembers ()) == order
                ]
        else:
            if order is None:
                return [
                  r for r in self._relations if r.getMembers ()[rank] is self
                ]
            else:
                return [
                  r for r in self._relations
                  if r.getMembers ()[rank] is self
                  and len (r.getMembers ()) == order
                ]
        # Cannot happen
        return []

    def getRelationsWith (self, other, rank=None, order=None):
        """
        Return all the relations involving both this annotation and the =other=
        given annotation. Parameters =rank= and =order=, if provided, are
        applied for this annotation as they would be for =getRelation=.
        """
        r = []
        for rel in self.getRelations (rank=rank, order=order):
            for m in rel.getMembers ():
                if m == other:
                    r.append (rel)
        return r

    def getOutgoingRelations (self):
        """
        Return all the binary relations having this annotation as their first
        member.
        """
        return self.getRelations (rank=0, order=2)

    def getIncomingRelations (self):
        """
        Return all the binary relations having this annotation as their second
        member.
        """
        return self.getRelations (rank=1, order=2)

    def getTypedOutgoingRelations(self):
        """Return the outgoing relations  sorted by relation type ids.
        """

        d=DefaultDict(default=[])
        for r in self.outgoingRelations:
            d[r.type.id].append(r)
        return d

    def getTypedIncomingRelations(self):
        """Return the incoming relations  sorted by relation type ids.
        """

        d=DefaultDict(default=[])
        for r in self.incomingRelations:
            d[r.type.id].append(r)
        return d

    def getRelated(self):
        """Return the related annotation.

        This is a shortcut for the case where there is only 1 binary
        relation.

        We search first outgoingRelations. If none exist, we check
        incomingRelations.
        """
        r=self.outgoingRelations
        if r:
            return r[0].members[-1]
        r=self.incomingRelations
        if r:
            return r[0].members[0]
        return None

    def getRelatedOut(self):
        """Return the list of related outgoing annotations.
        """
        return [ r.members[-1] for r in self.outgoingRelations ]

    def getRelatedIn(self):
        """Return the list of related incoming annotations.
        """
        return [ r.members[0] for r in self.incomingRelations ]

    def getTypedRelatedOut(self):
        """Return the related outgoing annotations sorted by relation type ids.
        """

        d=DefaultDict(default=[])
        for r in self.outgoingRelations:
            d[r.type.id].append(r.members[-1])
        return d

    def getTypedRelatedIn(self):
        """Return the related incoming annotations sorted by relation type ids.
        """
        d=DefaultDict(default=[])
        for r in self.incomingRelations:
            d[r.type.id].append(r.members[0])
        return d

class Relation(modeled.Importable, content.WithContent,
               viewable.Viewable.withClass('relation', '_get_type_uri'),
               _impl.Authored, _impl.Dated, _impl.Uried, _impl.Tagged):
    """Relation between annotations"""
    __metaclass__ = auto_properties

    def __init__(self,                 # mode 1 & 2
                 parent,               # mode 1 & 2
                 element = None,       # mode 1, required
                 type = None,          # mode 2, required
                 members = (),         # mode 2, required
                 ident = None,         # mode 2, optional
                 date = None,          # mode 2, optional
                 author = None,        # mode 2, optional
                 authorUrl = None,     # mode 2, optional
                 context = None,       # mode 2, optional
                 content_data = None,  # mode 2, optional
                 content_stream = None,# mode 2, optional
                 ):
        """
        The constructor has two modes of calling
         - giving it a DOM element (constructing from XML)
         - giving it type,members,[ident],[date],[author],[authorUrl],
           [context],[content_data|content_stream] (constructing from scratch)
        """

        _impl.Uried.__init__(self, parent=parent)
        self.__members = None

        if element is not None:
            # should be mode 1, checking parameter consistency
            if type is not None:
                raise TypeError("incompatible parameter 'type'")
            if len(members) > 0:
                raise TypeError("incompatible parameter 'members'")
            if ident is not None:
                raise TypeError("incompatible parameter 'ident'")
            if date is not None:
                raise TypeError("incompatible parameter 'date'")
            if author is not None:
                raise TypeError("incompatible parameter 'author'")
            if authorUrl is not None:
                raise TypeError("incompatible parameter 'authorUrl'")
            if context is not None:
                raise TypeError("incompatible parameter 'context'")
            if content_data is not None:
                raise TypeError("incompatible parameter 'content_data'")
            if content_stream is not None:
                raise TypeError("incompatible parameter 'content_stream'")

            # mode 1 initialization
            modeled.Importable.__init__(self, element, parent)
            _impl.Uried.__init__(self, parent=self.getOwnerPackage())
            for a in self.getMembers ():
                a._relations.append (self)

        else:
            # should be mode 2, checking parameter consistency
            if type is None:
                raise TypeError("parameter 'type' required")
            if len(members) == 0:
                raise TypeError("parameter 'members' required and should not"
                                +" be empty")

            # mode 2 initialization
            doc = parent._getDocument()
            element = doc.createElementNS(self.getNamespaceUri(),
                                               self.getLocalName())
            modeled.Importable.__init__(self, element, parent)

            e = doc.createElementNS(adveneNS, "members")
            self._getModel().appendChild(e)

            self.setType(type)
            # TODO: check that type is referenced in package

            members_bundle = self.getMembers ()
            for m in members:
                # TODO: check integrity when adding members
                members_bundle.append (m)
                m._relations.append (self)

            if ident is None:
                # FIXME: cf thread
                # Weird use of hash() -- will this work?
                # http://mail.python.org/pipermail/python-dev/2001-January/011794.html
                ident = u"r" + unicode(id(self)) + unicode(time.clock()).replace('.','')
            self.setId(ident)

            if date is not None: self.setDate(date)
            if author is not None: self.setAuthor(author)
            if authorUrl is not None: self.setAuthorUrl(authorUrl)
            if context is not None: self.setContext(context)
            if content_data is not None: self.getContent().setData(content_data)
            #if content_stream is not None: #TODO

    def __str__(self):
        return "Relation of type <%s>" % self.getType()

    # dom dependant methods

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "relation"
    getLocalName = staticmethod(getLocalName)

    def _get_type_uri(self, absolute=True):
        """Return the type URI - used to retrieve the viewable-type"""
        return self.getType().getUri(absolute)

    def getType(self):
        """Return the type of this relation"""
        type_uri = self._getModel().getAttributeNS(None, "type")
        pkg_uri = self.getOwnerPackage ().getUri (absolute=True)
        type_uri = util.uri.urljoin (pkg_uri, type_uri)
        return self.getOwnerPackage().getRelationTypes()[type_uri]

    def setType(self, type):
        """Set the type of this relation"""
        op = self.getOwnerPackage ()
        if type is None:
            raise AttributeError("type is a required attribute")
        elif type in op.getRelationTypes():
            type_uri = type.getUri (absolute=False, context=op)
            self._getModel().setAttributeNS(None, "type", type_uri)
        else:
            raise AdveneException("type %s is not imported" % type.getUri())

    def delType(self):
        """Delete the type of this relation"""
        self.setId(None)

    def getMembers (self):
        """Return a collection of this relation's members"""
        if self.__members is None:
            e = self._getChild((adveneNS, "members"))
            self.__members = bundle.RefBundle(self, e, adveneNS, 'member',
                                     self.getOwnerPackage (). getAnnotations ())
        return self.__members



# simple way to do it,
# AnnotationFactory = modeled.Factory.of (Annotation)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class AnnotationFactory (modeled.Factory.of (Annotation)):
    """
    FIXME
    """
    pass


# simple way to do it,
# RelationFactory = modeled.Factory.of (Relation)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class RelationFactory (modeled.Factory.of (Relation)):
    """
    FIXME
    """
    pass
