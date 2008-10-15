"""
I define the class of relations.
"""

from advene.model.consts import _RAISE
from advene.model.core.element \
  import PackageElement, ANNOTATION, RELATION
from advene.model.core.content import WithContentMixin
from advene.model.core.group import GroupMixin

class Relation(PackageElement, WithContentMixin, GroupMixin):
    """
    I expose the protocol of a basic collection, to give access to the members
    of a relation. I also try to efficiently cache the results I know.
    """

    # Caching is performed as follow:
    # __init__ retrieves the number of members, and builds self.__ids
    # and self.__cache, a list of id-refs and instances respectively.
    # Whenever an index is accessed, the member if retrieved from self.__cache.
    # If None, its id-ref is retrieved from self.__ids and the element is
    # retrieved from the package. If the id-ref is None, the id-ref is
    # retrieved from the backend.

    ADVENE_TYPE = RELATION

    def __init__(self, owner, id, mimetype, model, url, _new=False):
        PackageElement.__init__(self, owner, id)
        self._set_content_mimetype(mimetype, _init=True)
        self._set_content_model(model, _init=True)
        self._set_content_url(url, _init=True)

        if _new:
            self._cache = []
            self._ids = []
        else:
            c = owner._backend.member_count(owner._id, self._id)
            self._cache = [None,] * c
            self._ids = [None,] * c

    def __len__(self):
        return len(self._cache)

    def __iter__(self):
        """Iter over the members of this relation.

        If the relation contains unreachable members, None is yielded.

        See also `iter_member_ids`.
        """
        for i,m in enumerate(self._cache):
            if m is None:
                m = self.get_member(i, None)
            yield m

    def __getitem__(self, i):
        """Return member with index i, or raise an exception if the item is
        unreachable.

        See also `get_member`  and `get_member_id`.
        """
        if isinstance(i, slice): return self._get_slice(i)
        else: return self.get_member(i, _RAISE)

    def __setitem__(self, i, a):
        if isinstance(i, slice): return self._set_slice(i, a)
        assert getattr(a, "ADVENE_TYPE", None) == ANNOTATION
        o = self._owner
        assert o._can_reference(a)
        aid = a.make_id_in(o)
        self._ids[i] = aid
        self._cache[i] = a
        o._backend.update_member(o._id, self._id, aid, i)

    def __delitem__(self, i):
        if isinstance(i, slice): return self._del_slice(i)
        del self._ids[i] # also guarantees that is is a valid index
        del self._cache[i]
        o = self._owner
        o._backend.remove_member(o._id, self._id, i)

    def _get_slice(self, s):
        c = len(self._cache)
        return [ self.get_member(i, _RAISE) for i in range(c)[s] ]

    def _set_slice(self, s, annotations):
        c = len(self._cache)
        indices = range(c)[s]
        same_length = (len(annotations) == len(indices))
        if s.step is None and not same_length:
            self._del_slice(s)
            insertpoint = s.start or 0
            for a in annotations:
                self.insert(insertpoint, a)
                insertpoint += 1
        else:
            if not same_length:
                raise ValueError("attempt to assign sequence of size %s to "
                                 "extended slice of size %s"
                                 % (len(annotations), len(indices)))
            for i,j in enumerate(indices):
                self.__setitem__(j, annotations[i])
        
    def _del_slice(self,s):
        c = len(self._cache)
        indices = range(c)[s]
        indices.sort()
        for offset, i in enumerate(indices):
            del self[i-offset]

    def insert(self, i, a):
        assert getattr(a, "ADVENE_TYPE", None) == ANNOTATION
        o = self._owner
        assert o._can_reference(a)
        c = len(self._cache)
        if i > c : i = c
        if i < -c: i = 0
        if i < 0 : i += c 
        aid = a.make_id_in(o)
        self._ids.insert(i,aid)
        self._cache.insert(i,a)
        o._backend.insert_member(o._id, self._id, aid, i, c)
        # NB: it is important to pass to the backend the length c computed
        # *before* inserting the member
        
    def append(self, a):
        assert getattr(a, "ADVENE_TYPE", None) == ANNOTATION
        o = self._owner
        assert o._can_reference(a)
        aid = a.make_id_in(o)
        c = len(self._cache)
        self._ids.append(aid)
        self._cache.append(a)
        o._backend.insert_member(o._id, self._id, aid, -1, c)
        # NB: it is important to pass to the backend the length c computed
        # *before* appending the member

    def extend(self, annotations):
        for a in annotations:
            self.append(a)

    def iter_member_ids(self):
        """Iter over the id-refs of the members of this relation.

        See also `__iter__`.
        """
        for i,m in enumerate(self._ids):
            if m is not None:
                yield m
            else:
                yield self.get_member_id(i)

    def get_member(self, i, default=None):
        """Return element with index i, or default if it can not be retrieved.

        The difference with self[i] is that, if the member is unreachable,
        None is returned (or whatever value is passed as ``default``).

        Note that if ``i`` is an invalid index, an IndexError will still be
        raised.

        See also `__getitem__`  and `get_member_id`.
        """
        # NB: internally, default can be passed _RAISE to force exceptions
        assert isinstance(i, int)
        r = self._cache[i]
        if r is None:
            o = self._owner
            rid = self._ids[i]
            if rid is None:
                c = len(self._cache)
                i = xrange(c)[i] # check index and convert negative
                rid = self._ids[i] = \
                    o._backend.get_member(o._id, self._id, i)
            r = self._cache[i] = o.get_element(rid, default)
        return r

    def get_member_id(self, i):
        """Return id-ref of the element with index i.

        See also `__getitem__`  and `get_member`.
        """
        assert isinstance(i, int)
        r = self._ids[i]
        if r is None:
            o = self._owner
            c = len(self._ids)
            i = xrange(c)[i] # check index and convert negative
            r = self._ids[i] = o._backend.get_member(o._id, self._id, i)
        return r

#
