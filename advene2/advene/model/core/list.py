"""
I define the class of lists.
"""

from weakref import ref

from advene import _RAISE
from advene.model.core.element \
  import PackageElement, LIST
from advene.model.core.content import WithContentMixin

class List(PackageElement, WithContentMixin):
    """
    I expose the protocol of a basic collection, to give access to the items
    of a list. I also try to efficiently cache the results I know.
    """

    # The use of add_cleaning_operation is complicated here.
    # We could choose to have a single cleaning operation, performed once on
    # cleaning, completely rewriting the item list.
    # We have chosen to enqueue every atomic operation on the item list in
    # the cleaning operation pending list, and perform them all on cleaning,
    # which is more efficient that the previous solution if cleaning is 
    # performed often enough.
    #
    # A third solution would be to try to optimize the cleaning by not
    # executing atomic operations which will be cancelled by further
    # operations. For example:::
    #     r[1] = a1
    #     r[1] = a2
    # will execute backend.update_item twice, while only the second one
    # is actually useful. So...
    #
    # TODO: optimize cleaning as described above

    ADVENE_TYPE = LIST

    def __init__(self, owner, id):
        PackageElement.__init__(self, owner, id)
        self._count = owner._backend.count_items(owner._id, self._id)
        self._cache = None

    def __len__(self):
        if self._cache is None:
            return self._count
        else:
            return len(self._cache)

    def __iter__(self):
        if self._cache is not None:
            for e in iter(self._cache):
                yield e
        else:
            L = self._cache = [None,] * self._count
            o = self._owner
            it = o._backend.iter_items(o._id, self._id)
            for i,id in enumerate(it):
                e = L[i] = self._owner.get_element(id)
                yield e

    def __getitem__(self, i):
        if isinstance(i, slice): return self._get_slice(i)
        return self.get_item(i, _RAISE)

    def __setitem__(self, i, a):
        if isinstance(i, slice): return self._set_slice(i, a)
        assert hasattr(a, "ADVENE_TYPE")
        o = self._owner
        assert o._can_reference(a)
        L = self._cache
        if L is None:
            for i in self.__iter__(): pass # generate _cache
            L = self._cache
        L[i] = a # also guarantees that i is a valid index
        idref = a.make_idref_for(o)
        self.add_cleaning_operation(o._backend.update_item,
                                    o._id, self._id, idref, i)

    def __delitem__(self, i):
        if isinstance(i, slice): return self._del_slice(i)
        L = self._cache
        if L is None:
            for i in self.__iter__(): pass # generate _cache
            L = self._cache
        del L[i] # also guarantees that i is a valid index
        o = self._owner
        self.add_cleaning_operation(o._backend.remove_item,
                                    o._id, self._id, i)

    def _get_slice(self, s):
        L = self._cache
        if L is None:
            for i in self.__iter__(): pass # generate _cache
            L = self._cache
        return L[s]

    def _set_slice(self, s, elements):
        L = self._cache
        if L is None:
            for i in self.__iter__(): pass # generate _cache
            L = self._cache
        c = len(L)
        indices = range(c)[s]
        same_length = (len(elements) == len(indices))
        if s.step is None and not same_length:
            self._del_slice(s)
            insertpoint = s.start or 0
            for a in elements:
                self.insert(insertpoint, a)
                insertpoint += 1
        else:
            if not same_length:
                raise ValueError("attempt to assign sequence of size %s to "
                                 "extended slice of size %s"
                                 % (len(elements), len(indices)))
            for i,j in enumerate(indices):
                self.__setitem__(j, elements[i])
        
    def _del_slice(self,s):
        L = self._cache
        if L is None:
            for i in self.__iter__(): pass # generate _cache
            L = self._cache
        c = len(L)
        indices = range(c)[s]
        indices.sort()
        offset = 0
        for offset, i in enumerate(indices):
            del self[i-offset]

    def insert(self, i, a):
        assert hasattr(a, "ADVENE_TYPE")
        o = self._owner
        assert o._can_reference(a)
        L = self._cache
        if L is None:
            for i in self.__iter__(): pass # generate _cache
            L = self._cache
        c = len(L)
        if i > c : i = c
        if i < -c: i = 0
        if i < 0 : i += c 
        idref = a.make_idref_for(o)
        L.insert(i,a)
        self.add_cleaning_operation(o._backend.insert_item,
                                    o._id, self._id, idref, i, len(L))
        
    def append(self, a):
        assert hasattr(a, "ADVENE_TYPE")
        o = self._owner
        assert o._can_reference(a)
        L = self._cache
        if L is None:
            for i in self.__iter__(): pass # generate _cache
            L = self._cache
        idref = a.make_idref_for(o)
        L.append(a)
        self.add_cleaning_operation(o._backend.insert_item,
                                    o._id, self._id, idref, -1, len(L))

    def extend(self, elements):
        for a in elements:
            self.append(a)

    def get_item(self, i, default=None):
        """Return element with index i, or default if it can not be retrieved.

        Use self[i] instead, unless you want to avoid exceptions on retrieval
        errors. Note also that IndexErrors are not avoided by this method.
        """
        if self._cache is None:
            i = xrange(self._count)[i] # check index and convert negative
            id = o._backend.get_item(o._id, self._id, i)
            r = o.get_element(id, default)
            # TODO implement associative cache here? (in addition to _cache)
            return r
        else:
            return self._cache[i]

