from bisect import insort
from itertools import chain
from weakref import ref

from advene import _RAISE
from advene.utils.sorted_dict import SortedDict
from advene.model.core.dirty import DirtyMixin
from advene.model.exceptions import ModelError

class WithMetaMixin(DirtyMixin):
    """Metadata access mixin.

    I factorize all metradata-related code for classes Package and
    PackageElement.

    I also provide an alias mechanism to make frequent metadata easily
    accessible as python properties.
    """

    # NB: unlike other collections in the Advene model, metadata no not provide
    # meands to get id-ref *only* for unreachable elements. Since metadata
    # already require a test (is the value a string value or an element value)
    # mixing "pure" strings, id-refs and elements would seem too cumbersome...

    __cache = None # SortedDict of all known metadata
                   # values are either string or (weakref, idref)
    __dirty = None # dict of dirty metadata
                   # values are (val_as_string, val_is_idref)
    __cache_is_complete = False # is self.__cache complete?

    def iter_meta(self):
        """Iter over all the metadata of this object.

        Yields (key, value) pairs, where the value is either a string or an
        element. An exception will be raised whenever an unreachable element is
        to be yielded.

        See also `iter_meta_idrefs`.
        """
        if hasattr(self, "ADVENE_TYPE"):
            p = self._owner
            eid = self._id
            typ = self.ADVENE_TYPE
        else:
            p = self
            eid = ""
            typ = ""

        if self.__cache_is_complete:
            # then rely completely on cache
            for k, v in self.__cache.iteritems():
                if v is KeyError:
                    continue
                if isinstance(v, tuple):
                    tpl = v
                    v = tpl[0]()
                    if v is None:
                        v = p.get_element(tpl[1], _RAISE)
                yield k, v
        else:
            # retrieve data from backend *and __dirty*, and cache them
            iter_backend = p._backend.iter_meta(p._id, eid, typ)
            iter_all = self._mix_dirty_and_backend(iter_backend)
            cache = self.__cache
            if cache is None:
                cache = self.__cache = SortedDict()
            for k, v, v_is_idref in iter_all:
                if v_is_idref:
                    # it is no use looking in the cache: if the element is in
                    # the meta cache, it will also be in the package cache,
                    # and the retrieval from the package will be as efficient
                    e = p.get_element(v, _RAISE)
                    cache[k] = (ref(e), v)
                    v = e
                else:
                    cache[k] = v
                yield k, v
            self.__cache_is_complete = True

    def iter_meta_idrefs(self):
        """Iter over all the metadata of this object.

        Yields (key, value) pairs, where the value is a string with a special
        attribute ``is_idref`` indicating if it represents the id-ref of an
        element.

        See also `iter_meta`.
        """
        if hasattr(self, "ADVENE_TYPE"):
            p = self._owner
            eid = self._id
            typ = self.ADVENE_TYPE
        else:
            p = self
            eid = ""
            typ = ""

        if self.__cache_is_complete:
            # then rely completely on cache
            for k, v in self.__cache.iteritems():
                if v is KeyError:
                    continue
                if isinstance(v, tuple):
                    v = metadata_value(v[1], True)
                else:
                    v = metadata_value(v, False)
                yield k, v
        else:
            # retrieve data from backend *and __dirty*
            iter_backend = p._backend.iter_meta(p._id, eid, typ)
            iter_all = self._mix_dirty_and_backend(iter_backend)
            for k, v, v_is_idref in iter_all:
                yield k, metadata_value(v, v_is_idref)

    def get_meta(self, key, default=_RAISE):
        """Return the metadata (string or element) associated to the given key.

        If no metadata is associated to the given key, a KeyError is raised.
        If the given key references an unreachable element, a 
        `NoSuchEllementError` or `UnreachableImportError` is raised.

        All exceptions can be avoided by providing a ``default`` value, that
        will be returned instead of raising an exception.
        """
        return self.get_meta_idref(key, default, False)

    def get_meta_idref(self, key, default=_RAISE, _return_idref=True):
        """Return the metadata (string or element) associated to the given key.

        The returned value is a string with a special attribute ``is_idref``
        indicating if it represents the id-ref of an element.

        If no metadata is associated to the given key, a KeyError is raised,
        unless ``default`` is provideded, in which case its value is returned
        instead.
        """
        # NB: this method actually implement both get_meta and get_meta_idrefs,
        # with the flag _return_idref to choose between the two.

        if hasattr(self, "ADVENE_TYPE"):
            p = self._owner
            eid = self._id
            typ = self.ADVENE_TYPE
        else:
            p = self
            eid = ""
            typ = ""
        cache = self.__cache
        if cache is None:
            cache = self.__cache = SortedDict()

        val = cache.get((key))
        if isinstance(val, tuple):
            if _return_idref:
                val = metadata_value(val[1], True)
            else:
                wref, the_idref = val
                val = wref()
                if val is None:
                    val = p.get_element(the_idref, default)
                    if val is not default:
                        cache[key] = (ref(val), the_idref)
        elif isinstance(val, basestring):
            if _return_idref:
                val = metadata_value(val, False)
        elif val is None: # could also be KeyError
            tpl = p._backend.get_meta(p._id, eid, typ, key)
            if tpl is None:
                val = cache[key] = KeyError
            else:
                if _return_idref:
                    val = metadata_value(*tpl)
                elif tpl[1]:
                    the_idref = tpl[0]
                    val = p.get_element(the_idref, default)
                    if val is not default:
                        cache[key] = (ref(val), tpl[0])
                else:
                    val = cache[key] = tpl[0]

        if val is KeyError: # from cache or set above
            if default is _RAISE:
                raise KeyError(key)
            else:
                val = default
        return val

    def set_meta(self, key, val):
        """Set the metadata.

        ``val`` can either be a PackageElement or a string. If an element, it
        must be directly imported by the package of self, or a ModelError will
        be raised.
        """
        if hasattr(self, "ADVENE_TYPE"):
            p = self._owner
            eid = self._id
            typ = self.ADVENE_TYPE
        else:
            p = self
            eid = ""
            typ = ""
        if hasattr(val, "ADVENE_TYPE"):
            if not p._can_reference(val):
                raise ModelError, "Element should be directy imported"
            vstr = val.make_idref_in(p)
            vstr_is_idref = True
            val = (ref(val), vstr)
        else:
            vstr = str(val)
            vstr_is_idref = False
        cache = self.__cache
        if cache is None:
            cache = self.__cache = SortedDict()
        cache[key] = val
        dirty = self.__dirty
        if dirty is None:
            dirty = self.__dirty = SortedDict()
        dirty[key] = vstr, vstr_is_idref
        self.add_cleaning_operation_once(self.__clean)

    def del_meta(self, key):
        """Delete the metadata.

        Note that if the given key is not in used, this will have no effect.
        """
        if hasattr(self, "ADVENE_TYPE"):
            p = self._owner
            eid = self._id
            typ = self.ADVENE_TYPE
        else:
            p = self
            eid = ""
            typ = ""
        cache = self.__cache
        if cache is not None and key in cache:
            del cache[key]
        dirty = self.__dirty
        if dirty is None:
            dirty = self.__dirty = SortedDict()
        dirty[key] = None, False
        self.add_cleaning_operation_once(self.__clean)

    @property
    def meta(self):
        return _MetaDict(self)

    def __clean(self):
        dirty = self.__dirty
        if dirty:
            if hasattr(self, "ADVENE_TYPE"):
                p = self._owner
                eid = self._id
                typ = self.ADVENE_TYPE
            else:
                p = self
                eid = ""
                typ = ""
        while dirty:
            k,v = dirty.popitem()
            val, val_is_idref = v
            try:
                p._backend.set_meta(p._id, eid, typ, k, val, val_is_idref)
            except:
                dirty[k] = v
                raise

    def _mix_dirty_and_backend(self, iter_backend):
        """
        This method is used in iter_meta.

        It yields values of the form (key, stringvalue, val_is_idref),
        homogeneous to what the backend method returns.

        However, this method takes into account the __dirty dict, inserting
        new keys at the right place, overriding changed values, and avoiding
        deleted keys.
        """
        dirty = self.__dirty
        if dirty is None:
            dirty = self.__dirty = SortedDict()
        iter_dirty = ( (k,v[0],v[1]) for k,v in dirty.iteritems() )

        iter_dirty = chain(iter_dirty, [None,]) # eschew StopIteration
        iter_backend = chain(iter_backend, [None,]) # idem

        next_dirty = iter_dirty.next()
        next_backend = iter_backend.next()
        while next_dirty and next_backend:
            if next_dirty[0] <= next_backend[0]:
                if next_dirty[0] == next_backend[0]:
                    # dirty overrides backend
                    next_backend = iter_backend.next()
                if next_dirty[1] is not None: # avoid deleted keys
                    yield next_dirty
                next_dirty = iter_dirty.next()
            else:
                yield next_backend
                next_backend = iter_backend.next()
        # flush non-empty one
        if next_dirty:
            yield next_dirty
            for i in iter_dirty:
                if i is not None:
                    yield i
        elif next_backend:
            yield next_backend
            for i in iter_backend:
                if i is not None:
                    yield i

    @classmethod
    def make_metadata_property(cls, key, alias=None):
        """
        Attempts to create a python property in cls mapping to metadata key.

        If alias is None, key is considered as a URI, and the last part of
        that URI (after # or /) is used.

        Raises an AttributeError if cls already has a member with that name.
        """
        if alias is None:
            cut = max(key.rfind("#"), key.rfind("/"))
            alias = key[cut+1:]

        if hasattr(cls, alias):
            raise AttributeError(alias)

        def getter(obj):
            return obj.get_meta(key)

        def setter(obj, val):
            return obj.set_meta(key, val)

        def deller(obj):
            return self.del_meta(key)

        setattr(cls, alias, property(getter, setter, deller))


class _MetaDict(object):
    """A dict-like object representing the metadata of an object.

    Note that many methods have an equivalent with suffix ``_idref`` or 
    ``_idrefs`` which use `get_meta_idref` instead of `get_meta` and 
    `iter_meta_idrefs` instead of `iter_meta`, respectively.
    """ 

    __slots__ = ["_owner",]

    def __init__ (self, owner):
        self._owner = owner

    def __contains__(self, k):
        return self.get_meta(k, None) is not None

    def __delitem__(self, k):
        return self._owner.del_meta(k)

    def __getitem__(self, k):
        return self._owner.get_meta(k)

    def __iter__(self):
        return ( k for k, _ in self._owner.iter_meta_idrefs() )

    def __len__(self):
        return len(list(iter(self)))

    def __setitem__(self, k, v):
        return self._owner.set_meta(k, v)

    def clear(self):
        for k in self.keys():
            self._owner.del_meta(k)

    def copy(self):
        return dirt(self)

    def get(self, k, v=None):
        return self._owner.get_meta(k, v)

    def get_idref(self, k, v=None):
        return self._owner.get_meta_idref(k, v)

    def has_key(self, k):
        return self._owner.get_meta(k, None) is not None

    def items(self):
        return list(self._owner.iter_meta())

    def items_idrefs(self):
        return list(self._owner.iter_meta_idrefs())

    def iteritems(self):
        return self._owner.iter_meta()

    def iteritems_idrefs(self):
        return self._owner.iter_meta_idrefs()

    def iterkeys(self):
        return ( k for k, _ in self._owner.iter_meta_idrefs() )

    def itervalues(self):
        return ( v for _, v in self._owner.iter_meta() )

    def itervalues_idrefs(self):
        return ( v for _, v in self._owner.iter_meta_idrefs() )

    def keys(self):
        return [ k for k, _ in self._owner.iter_meta_idrefs() ]

    def pop(self, k, d=_RAISE):
        v = self._owner.get_meta(k, None)
        if v is None:
            if d is _RAISE:
                raise KeyError, k
            else:
                v = d
        else:
            self._owner.del_meta(k)
        return v

    def pop_idref(self, k, d=_RAISE):
        v = self._owner.get_meta_idref(k, None)
        if v is None:
            if d is _RAISE:
                raise KeyError, k
            else:
                v = d
        else:
            self._owner.del_meta(k)
        return v

    def popitem(self):
        it = self._owner.iter_meta()
        try:
            k, v = it.next()
        except StopIteration:
            raise KeyError()
        else:
            self._owner.del_meta(k)
            return v

    def popitem_idref(self):
        it = self._owner.iter_meta_idrefs()
        try:
            k, v = it.next()
        except StopIteration:
            raise KeyError()
        else:
            self._owner.del_meta(k)
            return v

    def setdefault(self, k, d=""):
        assert isinstance(d, basestring) or hasattr(d, "ADVENE_TYPE")
        v = self._owner.get_meta(k, None)
        if v is None:
            self._owner.set_meta(k, d)
            v = d
        return v

    def update(self, e=None, **f):
        e_keys = getattr(e, "keys", None)
        if callable(e_keys):
            for k in e_keys():
                self._owner.set_meta(k, e[k])
        elif e is not None:
            for k, v in e:
                self._owner.set_meta(k, v)
        for k, v in f.iteritems():
            self._owner.set_meta(k, v)

    def values(self):
        return [ v for _, v in self._owner.iter_meta() ]

    def values_idrefs(self):
        return [ v for _, v in self._owner.iter_meta_idrefs() ]


class metadata_value(str):
    def __new__ (cls, val, is_idref):
        return str.__new__(cls, val)
    def __init__ (self, val, is_idref):
        self.is_idref = is_idref
