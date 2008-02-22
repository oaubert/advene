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
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
import xml.dom

import util.uri

import _impl

from advene.model.constants import xlinkNS, ELEMENT_NODE

from exception import AdveneException

from util.auto_properties import auto_properties

class Modeled(object):
    """An implementation for objects being _views_ of a DOM element.

       This DOM element is called the _model_ of the object.
       Every Modeled instance can also have a _parent_, which is, when not None,
       a Modeled instance whose model is the parent element of 'element'.
    """

    __metaclass__ = auto_properties

    def __init__(self, element, parent):
        """The parameter element is the DOM model of this object.
        """
        assert element is not None
        self.__model = element
        self.__parent = parent

    def _getModel(self):
        """Return this objects's model (a DOM element).
        """
        return self.__model

    def _getParent(self):
        """Return this objects's parent (a Modeled instance, or None).
        """
        return self.__parent

    def _getDocument(self):
        """Return this object's model owner document.
        """
        return self.__model._get_ownerDocument()

    def _getModelChildren(self):
        """Return a DOM NodeList of the element children of this object's model.
           Note that this is not equivalent to x.getModel()._get_childNodes()
           since only Element children are returned (and not, for example,
           Text children or Comment children).
        """
        source = self.__model._get_childNodes()
        i = 0
        start = -1
        r = []
        for e in self.__model._get_childNodes():
            if e.nodeType == ELEMENT_NODE:
                if start == -1: start = i
            else:
                r = r + source[start:i]
                start = -1
            i += 1
        if start != -1:
            r = r + source[start:]
        return r

    def _getChild(self, match=None, before=None, after=None):
        """Looks for the first Element child matching the parameters.

        The meaning of each parameter follows (note that qname must be
        represented by a pair (ns_uri, local_name)).

           - match: the qname of the searched element
                     or the element itself
           - before: the qname of the element to be found just afterwards
                     or the element to be found just beforehand
           - after : the qname of the element to be found just
                     or the element to be found just afterwards

        If no element is found matching, None is returned.
        """
        list_ = self._getModelChildren()
        length = len(list_)

        for index in range(length):
            if match:
                if not self.__match(list_[index], match):
                    continue
            if after:
                if index == 0 \
                       or not self.__match(list_[index - 1], after):
                    continue
            if before:
                if index == length - 1 \
                       or not self.__match(list_[index + 1], before):
                    continue
            return list_[index]
        return None

    def __match(element, matcher):
        if isinstance(matcher, xml.dom.Node):
            return element == matcher
        else:
            return matcher[0] == element._get_namespaceURI() \
               and matcher[1] == element._get_localName()
    __match = staticmethod(__match)

    def getOwnerPackage(self):
        return self._getParent().getOwnerPackage()

    def getRootPackage(self):
        """
        Modeled which are not Importable rely on their parent for the access path.
        """
        return self._getParent().getRootPackage()

    def getAccessPath(self):
        """
        Modeled which are not Importable rely on their parent for the access path.
        """
        return self._getParent().getAccessPath()


class Importable(Modeled, _impl.Ided):
    """Common superclass of for every element which can be imported in a
       package.
    """
    # TODO: manage read-only'ness for imported elements

    __metaclass__ = auto_properties

    def __init__(self, element, parent, locator=None):
        if hasattr(parent, 'getAccessPath'):
            self.__access_path = list(parent.getAccessPath())
        else:
            self.__access_path = [parent.getOwnerPackage()]
        self.__importator = None

        # this is for schemas, types, queries, views
        if locator is not None \
        and element.hasAttributeNS(xlinkNS, 'href'):

            self.__importator = Importator(parent, element, self)

            href = self.__importator.getHref()
            base_uri= parent.getOwnerPackage ().getUri (absolute=True)
            uri = util.uri.urljoin(base_uri, href)
            pkg_uri = util.uri.no_fragment(uri)

            imports = parent.getOwnerPackage().getImports()
            if not imports.has_key(pkg_uri):
                raise AdveneException(
                         "Tried to use element from non imported package: %s" %
                         pkg_uri)
            pkg = imports.get(pkg_uri).getPackage()
            self.__access_path.append(pkg)

            parent = pkg
            self.__original = locator(pkg)[uri]
            element = self.__original._getModel()

        Modeled.__init__(self, element, parent)

    __access_path = None

    def getAccessPath(self):
        """Return the access path for this element"""
        return tuple(self.__access_path)

    def isImported(self):
        return self.__importator is not None

    def getImportator(self):
        return self.__importator

    def getOriginal(self):
        if self.isImported():
            return self.__original
        else:
            return self

    def getRootPackage(self):
        return self.__access_path[0]

    def getId(self):
        plain_id = super(Importable, self).getId()
        if not self.isImported ():
            return plain_id
        else:
            prefix = self.getRootPackage ().getQnamePrefix(self)
            if prefix is None:
                return plain_id
            else:
                return "%s:%s" % (prefix, plain_id)

    # pa: 030328
    # This method is not safe, since it does not update self.__importator
    # Since I don't use it for the moment, I just removed it
    #
    #def _importIn(self, package):
    #    self.__access_path.insert(0, package)



class Importator(Modeled, _impl.Hrefed):
    """ FIXME """
    __metaclass__ = auto_properties

    def __init__(self, parent, element, target):
        Modeled.__init__(self, element, parent)
        self.__target = target

    def getTarget(self):
        return self.__target

    def getBy(self):
        return self._getParent()


class Factory:
    """
    Abstract superclass of every Factory class.

    This class is an abstract class to be used as a base for every factory of
    Modeled subclasses. An actual factory class is produced with the static
    method Factory.of(cls).

    Subclasses of Factory must have a _getDocument method returning a DOM
    document.

    Factored classes must have
     - a _getModel method returning a DOM element node
     - a getUri method
     - a constructor accepting parameters _parent_ and _element_
    """

    def _make_import_element (self, modeled):
        """
        Make the XML element importing _modeled_.

        This method implements the common behaviour of every factory for
        importing an instance.
        """
        uri = modeled.getUri (absolute=False, context=self)
        e1 = modeled._getModel ()
        ns_uri = e1._get_namespaceURI ()
        local_name = e1._get_localName ()

        e2 = self._getDocument ().createElementNS (ns_uri, local_name)
        e2.setAttributeNS (xlinkNS, 'xlink:href', uri)

        return e2

    def _make_copy_element (self, modeled):
        """
        Make the XML element copying _modeled_.

        This method implements the common behaviour of every factory for
        copying an instance.
        """
        e1 = modeled._getModel ()
        canCopy = ('newOwner' in e1.cloneNode.im_func.func_code.co_varnames)
        if not canCopy:
            # FIXME: find a way to do it
            raise AdveneException, \
                      'Can not copy %s in this implementation of DOM' % modeled
        return e1.cloneNode (deep=True, newOwner=e1._get_ownerDocument ())

    def of (theClass):
        class_name = theClass.__name__
        class concreteFactory (Factory):
            def _create (self, *args, **kw):
                """
                Used to create a new element belonging to the current factory.
                You should refer to the constructor of the corresponind class
                to know the exact parameters of this function (which provides
                automatically parameter _parent_).
                """
                if args:
                    raise AdveneException, ('createX factory methods only accept keyword arguments')
                return theClass (parent=self, **kw)
            setattr(_create, '__doc__', theClass.__init__.__doc__)

            def _import (self, instance):
                """
                FIXME
                """
                if not isinstance (instance, theClass):
                    raise AdveneException, ("%s is not an instance of %s" %
                                            (instance, theClass.__name__))
                e = self._make_import_element (instance)
                return theClass (parent=self, element=e)

            def _copy (self, instance, id):
                """
                FIXME
                """
                # TODO: implement default id
                if not isinstance (instance, theClass):
                    raise AdveneException, ("%s is not an instance of %s" %
                                            (instance, theClass.__name__))
                e = self._make_copy_element (instance)
                e.setAttributeNS (None, 'id', id)
                return theClass (parent=self, element=e)


        setattr (concreteFactory,
                 'create%s' % class_name,
                 concreteFactory._create)
        del concreteFactory._create
        setattr (concreteFactory,
                 'import%s' % class_name,
                 concreteFactory._import)
        del concreteFactory._import
        setattr (concreteFactory,
                 'copy%s' % class_name,
                 concreteFactory._copy)
        del concreteFactory._copy

        return concreteFactory

    of = staticmethod(of)
