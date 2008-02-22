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
import time

import util.uri

from util.auto_properties import auto_properties

import _impl
import content
import modeled
import viewable

from exception import AdveneException, AdveneValueError

from constants import *


class _match_filter_dict (dict):
    """
    A specific dictionnary meant to reflect the state of both attributes
    'viewable-class' and 'viewable-type' of a 'view' element. The corresponding
    keys are 'class' and 'type', respectively.

    It also has a _class_ and a _type_ property.
    """

    __metaclass__ = auto_properties

    __slots__ = ['view']

    __classes_w_uri_types = ('annotation', 'relation')
    __classes_w_mime_types = ('content',)
    __classes_w_types = (__classes_w_uri_types
                       + __classes_w_mime_types
                       + ('list',))

    def __init__ (self, view):
        sup = super (_match_filter_dict, self)
        sup.__init__ ()
        self.view = view
        setitem = sup.__setitem__

        v_class = view._getModel ().getAttributeNS (None, 'viewable-class');
        setitem ('class', v_class)

        if v_class in self.__classes_w_types:
            v_type = view._getModel ().getAttributeNS (None, 'viewable-type')
            #if (v_type not in ('', '*')
            #and v_class in self.__classes_w_uri_types):
            #    pkg_uri = view.getOwnerPackage ().getUri (absolute=True)
            #    v_type = util.uri.urljoin (pkg_uri, v_type)
            setitem ('type', v_type)
            self.__manage_values ()

    def __setitem__ (self, key, val):

        try:
            if self[key] == val: return
        except KeyError:
            pass

        if key == 'class':
            if val not in viewable.Viewable.getAllClasses() + ('*',):
                raise AdveneValueError ('unknown viewable-class %s' % val)
            else:
                self.view._getModel ().setAttributeNS (None, 'viewable-class',
                                                       val)
                super (_match_filter_dict, self).__setitem__ (key, val)
                try:
                    del self['type']
                except KeyError: pass

        elif key == 'type':
            if not self['class'] in self.__classes_w_types:
                raise AdveneValueError (
                         'viewable-class %s does cannot have a viewable-type' %
                         self['class'])
            self.view._getModel ().setAttributeNS (None, 'viewable-type', val)
            super (_match_filter_dict, self).__setitem__ (key, val)

        else:
            raise AdveneException ('invalid key "%s" for a matchFilter' % key)

        self.__manage_values ()

    def __delitem__ (self, key):
        if   key == 'class':
            raise AdveneException ('key "class" is mandatory in matchFilter')
        elif key == 'type':
            model = self.view._getModel ()
            if model.hasAttributeNS (None, 'type-class'):
                model.delAttributeNS (None, 'type-class')
        super (_match_filter_dict, self).__delitem__ (key)
        self.__manage_values ()

    def __manage_values (self):
        v_class = self['class']
        v_type = self.get ('type', None)

        if v_class in self.__classes_w_types:
            # default values
            if v_type is None or v_type == '':
                if v_class in  self.__classes_w_mime_types:
                    v_type = '*/*'
                else:
                    v_type = '*'
                super (_match_filter_dict, self).__setitem__ ('type',v_type)
            # resolve relative URIs
            elif v_type != '*' and v_class in self.__classes_w_uri_types:
                pkg_uri =self.view.getOwnerPackage ().getUri (absolute=True)
                v_type = util.uri.urljoin (pkg_uri, v_type)
                super (_match_filter_dict, self).__setitem__ ('type', v_type)

    def getClass (self):
        return self.get('class')

    def setClass (self, value):
        self['class'] = value

    def getType (self):
        return self.get('type')

    def setType (self, value):
        self['type'] = value



class View(modeled.Importable, content.WithContent,
           viewable.Viewable.withClass('view'),
           _impl.Uried, _impl.Authored, _impl.Dated, _impl.Titled):
    """
    An advene View.
    """

    __metaclass__ = auto_properties

    def __init__(self,                   # mode 1 & 2
                 parent,                 # mode 1 & 2
                 element = None,         # mode 1, required
                 clazz = None,           # mode 2, required
                 type = None,            # mode 2, optional
                 ident = None,           # mode 2, optional
                 title = None,           # mode 2, optional
                 date = None,            # mode 2, optional
                 author = None,          # mode 2, optional
                 authorUrl = None,       # mode 2, optional
                 content_data = None,    # mode 2, optional
                 content_stream = None,  # mode 2, optional
                 content_mimetype = None,# mode 2, optional
                 **kw  # only to manage parameter deprecation
                       # remove eventually
                 ):
        """
        The constructor has two modes of calling
         - giving it a DOM element (constructing from XML)
         - giving it clazz,[type],[ident],[title],[date],[author],[authorUrl],
           [content_data|content_stream],[content_mimetype] (constructing from
           scratch)
        """
        _impl.Uried.__init__(self, parent=parent)

        if element is not None:
            if clazz is not None:
                raise TypeError("incompatible parameter 'clazz'")
            if type is not None:
                raise TypeError("incompatible parameter 'type'")
            if ident is not None:
                raise TypeError("incompatible parameter 'ident'")
            if title is not None:
                raise TypeError("incompatible parameter 'title'")
            if date is not None:
                raise TypeError("incompatible parameter 'date'")
            if author is not None:
                raise TypeError("incompatible parameter 'author'")
            if authorUrl is not None:
                raise TypeError("incompatible parameter 'authorUrl'")
            if content_data is not None:
                raise TypeError("incompatible parameter 'content_data'")
            if content_stream is not None:
                raise TypeError("incompatible parameter 'content_stream'")
            if content_stream is not None:
                raise TypeError("incompatible parameter 'content_mimetype'")

            modeled.Importable.__init__(self, element, parent,
                                        parent.getViews.im_func)

            _impl.Uried.__init__(self, parent=self._getParent())

        else:
            if clazz is None:
                raise TypeError("parameter 'clazz' required")
            if len(kw):
                raise TypeError ('Unkown parameters: %s' % kw.keys ())

            doc = parent._getDocument()
            element = doc.createElementNS(self.getNamespaceUri(),
                                               self.getLocalName())
            modeled.Importable.__init__(self, element, parent,
                                        parent.getViews.im_func)

            mf = self.getMatchFilter ()
            mf.setClass (clazz)
            if type is not None:
                mf.setType (type)

            if ident is None:
                # FIXME: cf thread
                # Weird use of hash() -- will this work?
                # http://mail.python.org/pipermail/python-dev/2001-January/011794.html
                ident = u"v" + unicode(id(self)) + unicode(time.clock()).replace('.','')
            self.setId(ident)

            if title is not None: self.setTitle(date)
            if date is not None: self.setDate(date)
            if author is not None: self.setAuthor(author)
            if authorUrl is not None: self.setAuthorUrl(authorUrl)
            if content_data is not None: self.getContent().setData(content_data)
            #if content_stream is not None: #TODO

            if content_mimetype is None: content_mimetype = 'text/html'
            self.getContent().setMimetype(content_mimetype)


    # dom dependant methods

    def __str__(self):
        """Return a nice string representation of the element"""
        return "View <%s>" % self.getUri()

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "view"
    getLocalName = staticmethod(getLocalName)

    def getMatchFilter(self):
        if not hasattr (self, '_match_filter'):
            self._match_filter = _match_filter_dict (self)
        return self._match_filter

    def match(self, viewable):
        mf = self.getMatchFilter()
        v_class = mf['class']
        v_type = mf.get ('type', None)
        if  v_class != '*' and v_class != viewable.getViewableClass():
            return False
        if v_class in ('annotation', 'relation', 'list'):
            if v_type != '*' and v_type != viewable.getViewableType():
                return False
        elif v_class == 'content':
            if v_type:
                vt1, vt2 = v_type.split('/')
                ct1, ct2 = viewable.getViewableType().split('/')
                if vt1 != '*' and vt1 != ct1:
                    return False
                if vt2 != '*' and vt2 != ct2:
                    return False
        return True

    def isMoreSpecificThan(self, view):

        mf1 = self.getMatchFilter()
        v_class1 = mf1['class']
        v_type1 = mf1.get ('type', None)

        mf2 = view.getMatchFilter()
        v_class2 = mf2['class']
        v_type2 = mf2.get ('type', None)

        if v_class1 == '*':
            return False
        if v_class2 == '*':
            return True
        if v_class1 != v_class2:
            return False

        if v_type1 is None:
            return False
        if v_class1 == 'content':
            t1_a, t1_b = v_type1.split('/')
            t2_a, t2_b = v_type2.split('/')
            if t1_a == '*':
                return False
            if t2_a == '*':
                return True
            if t1_a != t2_a:
                return False
            return t1_b != '*' and t2_b == '*'

        return v_type1 != '*' and v_type2 == '*'


# simple way to do it,
# ViewFactory = modeled.Factory.of (View)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class ViewFactory (modeled.Factory.of (View)):
    """
    FIXME
    """
    pass



