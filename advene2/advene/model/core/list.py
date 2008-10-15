"""
I define the class of lists.
"""
from weakref import ref

from advene.model.consts import _RAISE
from advene.model.core.element \
  import PackageElement, LIST
from advene.model.core.content import WithContentMixin
from advene.model.core.group import GroupMixin

class List(PackageElement, WithContentMixin, GroupMixin):
    """I expose the protocol of a basic collection, to give access to the items of a list. 

    I also try to efficiently cache the results I know.
    """

    # Caching is performed as follow:
    # __init__ retrieves the number of items, and builds self.__ids
    # and self._cache, a list of id-refs and weakrefs respectively.
    # Whenever an index is accessed, the item if retrieved from self._cache.
    # If None, its id-ref is retrieved from self.__ids and the item is
    # retrieved from the package. If the id-ref is None, the id-ref is
    # retrieved from the backend.

    ADVENE_TYPE = LIST

    def __init__(self, owner, id, _new=False):
        """FIXME: missing docstring.
        """
        PackageElement.__init__(self, owner, id)
        if _new:
            self._cache = []
            self._ids   = []
        else:
            c = owner._backend.item_count(owner._id, self._id)
            self._cache = [lambda: None,] * c
            self._ids = [None,] * c

    def __len__(self):
        return len(self._cache)

    def __iter__(self):
        """Iter over the items of this list.

        If the list contains unreachable items, None is yielded instead.

        See also `iter_item_ids`.
        """
        for i,y in enumerate(self._cache):
            y = y() # follow weak ref
            if y is None:
                y = self.get_item(i, None)
            yield y

    def __getitem__(self, i):
        """Return item with index i, or raise an exception if the item is
        unreachable.

        See also `get_item`  and `get_item_id`.
        """
        if isinstance(i, slice): return self._get_slice(i)
        else: return self.get_item(i, _RAISE)

    def __setitem__(self, i, a):
        if isinstance(i, slice): return self._set_slice(i, a)
        assert hasattr(a, "ADVENE_TYPE")
        o = self._owner
        assert o._can_reference(a)
        aid = a.make_id_in(o)
        self._ids[i] = aid
        self._cache[i] = ref(a)
        o._backend.update_item(o._id, self._id, aid, i)

    def __delitem__(self, i):
        if isinstance(i, slice): return self._del_slice(i)
        del self._ids[i] # also guarantees that is is a valid index
        del self._cache[i]
        o = self._owner
        o._backend.remove_item(o._id, self._id, i)

    def _get_slice(self, s):
        c = len(self._cache)
        return [ self.get_item(i, _RAISE) for i in range(c)[s] ]

    def _set_slice(self, s, elements):
        c = len(self._cache)
        indices = range(c)[s]
        same_length = (len(elements) == len(indices))
        if s.step is None and not same_length:
            self._del_slice(s)
            insertpoint = s.start or 0
            for e in elements:
                self.insert(insertpoint, e)
                insertpoint += 1
        else:
            if not same_length:
                raise ValueError("attempt to assign sequence of size %s to "
                                 "extended slice of size %s"
                                 % (len(elements), len(indices)))
            for i,j in enumerate(indices):
                self.__setitem__(j, elements[i])
        
    def _del_slice(self,s):
        c = len(self._cache)
        indices = range(c)[s]
        indices.sort()
        for offset, i in enumerate(indices):
            del self[i-offset]

    def insert(self, i, a):
        assert hasattr(a, "ADVENE_TYPE")
        o = self._owner
        assert o._can_reference(a)
        c = len(self._cache)
        if i > c : i = c
        if i < -c: i = 0
        if i < 0 : i += c 
        aid = a.make_id_in(o)
        self._ids.insert(i,aid)
        self._cache.insert(i,ref(a))
        o._backend.insert_item(o._id, self._id, aid, i, c)
        # NB: it is important to pass to the backend the length c computed
        # *before* inserting the item
        
    def append(self, a):
        assert hasattr(a, "ADVENE_TYPE")
        o = self._owner
        assert o._can_reference(a)
        aid = a.make_id_in(o)
        c = len(self._cache)
        self._ids.append(aid)
        self._cache.append(ref(a))
        o._backend.insert_item(o._id, self._id, aid, -1, c)
        # NB: it is important to pass to the backend the length c computed
        # *before* appending the item

    def extend(self, elements):
        for e in elements:
            self.append(e)

    def iter_item_ids(self):
        """Iter over the id-refs of the items of this list.

        See also `__iter__`.
        """
        for i,y in enumerate(self._ids):
            if y is not None:
                yield y
            else:
                yield self.get_item_id(i)

    def get_item(self, i, default=None):
        """Return item with index i, or default if it can not be retrieved.

        Note that if ``i`` is an invalid index, an IndexError will still be
        raised.

        See also `__getitem__` and `get_item_id`.
        """
        # NB: internally, default can be passed _RAISE to force exceptions
        assert isinstance(i, int)
        r = self._cache[i]()
        if r is None:
            o = self._owner
            rid = self._ids[i]
            if rid is None:
                c = len(self._cache)
                i = xrange(c)[i] # check index and convert negative
                rid = self._ids[i] = \
                    o._backend.get_item(o._id, self._id, i)
            r = o.get_element(rid, default)
            if r is not default:
                self._cache[i] = ref(r)
        return r

    def get_item_id(self, i):
        """Return id-ref of the item with index i.

        See also `__getitem__`  and `get_item`.
        """
        assert isinstance(i, int)
        r = self._ids[i]
        if r is None:
            o = self._owner
            c = len(self._ids)
            i = xrange(c)[i] # check index and convert negative
            r = self._ids[i] = o._backend.get_item(o._id, self._id, i)
        return r
