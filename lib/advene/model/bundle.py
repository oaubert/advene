"""
A bundle is a collection of objects implementing the _getUri_ method, returning
a URI which is supposed to uniquely identify the corresponding instance.

A bundle is homogeneous to both a list and a dictionary: every element of the
list is also indexed by its URI.  Hence the 'bundle[index]' notation can be
used with integers or strings.

Since bundle may list/dict views of complex underlying data, many operations
which are usual with simple python lists, are just meaningless for bundles. 

Permitted list operations are
 - len(b)
 - b.append
 - b.insert
 - b.pop
 - b.remove
 - b[x]
 - b[x:y]
 - del b[x]
 - del b[x:y]
 - v in b
 - b1 + b2

Permitted dict operations are
 - b.clear
 - b.get
 - b.has_key
 - b.items
 - b.iteritems
 - b.iterkeys
 - b.itervalues
 - b.keys
 - b.popitem
 - values
 - k in b
 - b[k]


Note also that iter(b) iterates over its values (as for lists). Iterating over keys required the _iterkeys_ method.
"""

import advene.model.util.uri

import advene.model.modeled as modeled
import advene.model.viewable as viewable

from advene.model.constants import *
from advene.model.exception import AdveneException

from gettext import gettext as _

class AbstractBundle (object):
    """
    Base class of all Bundles.
    
    Implements all the read-only methods.
    """

    def uris(self):
        """
        Return the uris of the objects in the bundle.

        Note that items in the bundle are indexed by their keys. Hence, this
        method is equivalent to _keys_.
        """
        return self._dict.keys ()

    def getQName (self, key, namespaces, default=None):
        """
        Resolve the given key as a QName with regard to the given namespaces.

        _namespaces_ is a dict whose keys are qname prefices and values are
        URIs. QName is resolved by concatenating the URI, '#' and the suffix.
        """
        try:
            colon = key.index (':')
            prefix = key[:colon]
            suffix = key[colon+1:]
        except ValueError:
            prefix = ''
            suffix = key

        uri = namespaces.get (prefix)
        if uri is None:
            return default
        else:
            real_key = '%s#%s' % (uri, suffix)
            return self.get (real_key, default=default)


    #
    # list implementation
    #

    def __add__ (self, other):
        assert isinstance (other, AbstractBundle)
        return SumBundle (self, other)

    def __contains__ (self, v):
        return (v is self._dict.get(v.getUri (absolute=True), None)
             or v in self._dict) 

    def __getitem__ (self, index):
        if isinstance (index,int):
            return self._list[index]
        else:
            return self._dict[index]

    def index (self, element):
        return self._list.index (element)
    
    def __getslice__ (self, begin, end):
        """
        b.__getslice__(i, j) <==> b[i:j]
        Note that the slice is a copy of this bundle.
        """
        return ListBundle (self._list[begin:end])

    def __iter__ (self):
        return iter (self._list)

    def __len__ (self):
        return len (self._list)

    #
    # dict implementation
    #

    def get (self, id, default=None):
        return self._dict.get (id, default)
    
    def has_key (self, key):
        return self._dict.has_key (key)

    def items (self):
        return self._dict.items ()

    def iteritems (self):
        return self._dict.iteritems ()

    def iterkeys (self):
        return self._dict.iterkeys ()

    def itervalues (self):
        return self._dict.itervalues ()

    def ids (self):
        return [ e.id for e in self._dict.itervalues() ]
    
    def keys (self):
        """
        Return the keys of this bundle.

        Note that items in the bundle are indexed by their keys. Hence, this
        method is equivalent to _uris_.
        """
        return self._dict.keys ()

    def values (self):
        return self._dict.values ()


class ListBundle (AbstractBundle):
    """
    A class of bundle constructed from a list of items.
    Prerequisite: all items must have a getUri(absolute) method.
    """

    def __init__ (self, the_list):
        super(ListBundle, self).__init__ ()
        self._list = the_list[:]
        self._dict = dict (
          [ (i.getUri (absolute=True), i) for i in the_list ]
        )

class SumBundle (AbstractBundle):
    """
    The concatenation of several bundles.

    A sum bundle is a read-only buffer resulting from the concatenation of
    several bundles.
    """

    def __init__ (self, *bundles):
        super(SumBundle, self).__init__ ()
        self._list = []
        self._dict = {}
        for b in bundles:
            self.__iadd__ (b)

    def __add__ (self, bundle):
        r = SumBundle (*(self.__bundle))
        r += bundle
        return r

    def __iadd__ (self, bundle):
        assert isinstance (bundle, AbstractBundle)
        self._list += bundle._list
        self._dict.update (bundle._dict)
        return self
        

class WritableBundle (AbstractBundle):
    """
    Superclass of read-write bundles.

    When specializing this class, it is only necessary to override the following
    methods: __delitem__ and insert. All other methods rely on these two 
    methods.
    Note also that the method _assert_add_item is invoked whenever an item is to
    be added, and can therefore be overridden to add more checking.
    """

    def __init__ (self):
        self._list = []
        self._dict = {}

    #
    # list implementation
    #

    def __delitem__ (self, index):
        if isinstance (index, int):
            item =  self._list.pop(index)
            del self._dict[item.getUri (absolute=True)]
        else:
            item = self._dict[index]
            self._list.remove (item)
            del self._dict[index]

    def __delslice__(self, begin, end):
        length = len (self)
        if begin < 0:
            begin += length
        if end < 0:
            end += length

        for i in range (max (0, begin),
                        min (end, length)):
            del self[begin]
            # YES, del self[begin] and NOT del self[i]
            # Indeed, deleting translate indices in the process!

    def append(self, item):
        length = len (self)
        self.insert (length, item)

    def insert(self, index, item):
        assert self._assert_add_item (item)
        
        length = len(self)
        if not (-length <= index <= length):
            raise IndexError, (index, self._list)

        self._list.insert(index, item)
        self._dict[item.getUri (absolute=True)] = item

    def remove (self, item):
        uri = item.getUri (absolute=True)
        check = self._dict.get (uri, None)
        if check is item:
            del self[uri]
            return
        raise ValueError, _('%s not in bundle') % item

    def pop(self, index=0):
        r = self[index]
        del self[index]
        return r

    #
    # dict implementation
    #

    def clear (self):
        del self[:]

    def popitem (self):
        """
        Pops the first element of this bundle,
        and returns both its URI and the item itself.
        """
        r = self.pop (0)
        return r.getUri (absolute=True), r

    #
    # specific methods
    #

    def _assert_add_item (self, item):
        """
        This method is check before any item addition.

        It returns True so that it can be asserted itself (so that outside
        debug mode, it is not even called), but it also asserts every clause so
        that the stacktrace is more explicit.
        """
        assert item not in self, \
               "item %s already in bundle" % item
        assert item.getUri (absolute=True) not in self._dict, \
               ("uri %s already in bundle (but another instance)"
                % item.getUri (absolute=True))
        return True


class AbstractXmlBundle(WritableBundle, modeled.Modeled,
                        viewable.Viewable.withClass('list')):
    """
    This class implements a bundle wraping XML elements.

    This abstract method requires a number of methods:
     * _get_namespace_uri : returning the NS URI of the elements to be included
     * _get_local_name : returning the local name of the elements to be included
     * _make_item : a callable taking a parent and an element and returning an 
       item
     * _get_element : a callable taking an element and returning its item
     * _getViewableType : a method returning the viewable type
    """

    def __init__ (self, parent, element):
        WritableBundle.__init__ (self)
        modeled.Modeled.__init__ (self, element, parent)

        self._update ()


    def __str__ (self):
        t = self.viewableType
        if t is None:
            return _("List of non-typed elements")
        else:
            # Viewable-type should be of the form type-list
            if t.endswith("-list"):
                t = t[:-5]
            return _("List of elements of type %s") % t
        
    def _update (self):
        """
        FIXME
        """
        del self._list[:]
        self._dict.clear ()

        # caching a number of objects to reduce resolving overhead
        ns = self._get_namespace_uri ()
        ln = self._get_local_name ()
        parent = self._getParent ()
        make_item = self._make_item 
        list_append = self._list.append
        dict_append = self._dict.__setitem__

        for e in self._getModelChildren ():
            if e._get_namespaceURI () != ns \
            or e._get_localName () !=ln:
                continue
            item = make_item (parent, e)
            list_append (item)

            uri = item.getUri (absolute=True)
            assert uri not in self._dict, "item %s already in bundle" % item
            dict_append (uri, item)

    #
    # Viewable specific implementation
    #

    def getViewableTypeGetterName ():
        """
        Override the name of the method to get ViewableType
        """
        return '_getViewableType'
    getViewableTypeGetterName = staticmethod (getViewableTypeGetterName)

    #
    # overridden methods
    #

    def __delitem__ (self, index):
        item = self[index]
        super (AbstractXmlBundle, self).__delitem__ (index)
        self._getModel ().removeChild (self._get_element (item))

    def insert(self, index, item):

        assert self._assert_add_item (item)
        # FIXME: this will be performed again by 'super' call,
        # but we must check it before doing anything,
        # and on the other hand, 'super' call alters _list and _dict
        # so it is more readable to perform it in the end

        length = len (self)
        model = self._getModel ()
        elt_list = model._get_childNodes ()

        # The model element of the bundle may have child elements which
        # are ignored by the bundle. If this is the case, the bundle elements
        # should be kept as grouped as possible.
        if length == 0:
            elt_list.insert (0, self._get_element (item))
        elif index != length:
            ref_elt = self._get_element (self._list[index])
            true_index = elt_list.index (ref_elt)
            elt_list.insert (true_index, self._get_element (item))
        else:
            ref_elt = self._get_element (self._list[-1])
            ref_index = elt_list.index (ref_elt)
            elt_list.insert (ref_index + 1, self._get_element (item))

        super (AbstractXmlBundle, self).insert (index, item)
        

    def _assert_add_item (self, item):
        assert ( item._getParent ().getRootPackage ()
             is  self._getParent ().getRootPackage () ), \
             "item has wrong parent %s" % item._getParent()
        return super (AbstractXmlBundle, self)._assert_add_item (item)


class StandardXmlBundle(AbstractXmlBundle):
    """
    This class implements a bundle wraping XML elements.

    The constructor takes a parent package, an element containing the list, and
    a class to be used to construct items. Furthermore, this class must have
    staticmethods getNamespaceUri and getLocalName to indicate which elements
    to look for, and a _getModel instance method returning a DOM element.
    Note that this bundle is writable, and that write operations are commited
    on the underlying XML structure.
    """

    def __init__ (self, parent, element, cls):
        """
        FIXME
        """
        self.__cls = cls
        AbstractXmlBundle.__init__ (self, parent, element)

    def _get_namespace_uri (self):
        return self.__cls.getNamespaceUri ()

    def _get_local_name (self):
        return self.__cls.getLocalName ()

    def _make_item (self, *args, **kw):
        return self.__cls (*args, **kw)

    def _get_element (self, item):
        return item._getModel ()

    def _assert_add_item (self, item):
        assert isinstance (item, self.__cls), \
               "item has wrong type %s" % type(item)
        return super (StandardXmlBundle, self)._assert_add_item (item)

    def _getViewableType (self):
        if hasattr (self.__cls, 'getViewableClass'):
            return self.__cls.getViewableClass () + '-list'
        else:
            return None



class ImportBundle (StandardXmlBundle):
    """
    This extension of StandardXmlBundle is able to manage imported item as well
    as defined items. An imported item has the same QName as other items, but
    contains an xlink:href attribute pointing to the item to be imported.
    """

    def __init__ (self, parent, element, cls):
        """
        FIXME
        """
        StandardXmlBundle.__init__ (self, parent, element, cls)

    def _get_element (self, item):
        """
        FIXME
        """
        if item.isImported ():
            return item.getImportator ()._getModel ()
        else:
            return item._getModel ()



class RefBundle (AbstractXmlBundle):
    """
    This kind of bundle is constructed with a Modeled class and the 
    corresponding namespace URI and local name. Elements are expected to have a
    xlink:href attribute pointing to the references item inside the bundle's
    package.
    """

    def __init__ (self, parent, element, namespaceUri, localName, source):
        self.__ns_uri = namespaceUri
        self.__local_name = localName
        self.__source = source
        self.__elt_dict = {}

        AbstractXmlBundle.__init__ (self, parent, element)

    def _get_namespace_uri (self):
        return self.__ns_uri

    def _get_local_name (self):
        return self.__local_name

    def _make_item (self, parent, element):
        href = element.getAttributeNS (xlinkNS, 'href')
        base_uri = self._getParent ().getUri (absolute=True)
        uri = advene.model.util.uri.urljoin(base_uri, href)
        try:
            r = self.__source[uri]
        except KeyError:
            # INTEGRITY CONSTRAINT: xxx
            raise AdveneException, \
                  '%s does not belong to the package' % href
        self.__elt_dict[r] = element
        return r

    def _get_element (self, item):
        try:
            return self.__elt_dict[item]
            # ok, element was known
        except KeyError:
            # element must be constructed
            doc = self._getModel ()._get_ownerDocument ()
            elt = doc.createElementNS (self._get_namespace_uri (),
                                       self._get_local_name ())
            pkg = self._getParent ().getOwnerPackage ()
            elt.setAttributeNS (xlinkNS, 'xlink:href',
                                item.getUri (absolute=False, context=pkg))
            self.__elt_dict [item] = elt
            return elt

    def __delitem__ (self, index):
        item = self[index]
        super (RefBundle, self).__delitem__ (index)
        del self.__elt_dict[item]

    def _assert_add_item (self, item):
        # INTEGRITY CONSTRAINT: xxx
        assert item in self.__source, \
               '%s does not belong to the package' % item
        return super (RefBundle, self)._assert_add_item (item)

    def _getViewableType (self):
        if hasattr (self.__source, '_getViewableType'):
            return self.__source._getViewableType ()
        else:
            return None

class InverseDictBundle (StandardXmlBundle):
    """
    This extension of StandardXmlBundle maintains an inverse dictionnary,
    i.e. a dict whose values are URIs and whose keys are given by the function
    inverse_key provided to the constructor. If None is provided, items
    themselves are used as keys.
    """

    def __init__ (self, parent, element, cls, inverse_key=None):
        """
        FIXME
        """
        self.__inverse_dict = {}
        if inverse_key is None:
            def identity (x):
                return x
            inverse_key = identity
        self.__inverse_key = inverse_key
        StandardXmlBundle.__init__ (self, parent, element, cls)

    def __delitem__ (self, index):
        item = self[index]
        super (InverseDictBundle, self).__delitem__ (index)
        del self.__inverse_dict[self.__inverse_key (item)]        

    def insert (self, item, index):
        super (InverseDictBundle, self).insert (self, item, index=index)
        self.__inverse_dict[self.__inverse_key (item)] = item.getUri (
                                                                  absolute=True)

    def _make_item (self, parent, element):
        item = super (InverseDictBundle, self)._make_item (parent, element)
        self.__inverse_dict[self.__inverse_key (item)] = item.getUri (
                                                                  absolute=True)
        return item

    def getInverseDict (self):
        return dict (self.__inverse_dict)
