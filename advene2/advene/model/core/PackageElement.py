"""
I define the common super-class of all package element classes.

Note that package element have a 3-states life cylcle:
 0: constructed, but not yet fully initialized by the backend
 1: initialized and ready to be used and/or modified
 2: destroyed, so not usable anymore
"""

# TODO maybe the notion of state is no more relevant

from sets import Set

from advene import RAISE
from advene.utils.AutoPropertiesMetaclass import AutoPropertiesMetaclass

from WithMetaMixin import WithMetaMixin

# the following constants must be used as values of a property ADVENE_TYPE
# in all subclasses of PackageElement
STREAM     = 3
ANNOTATION = 1
RELATION   = 2
VIEW       = 4
RESOURCE   = 5
BAG        = 6
FILTER     = 7
IMPORT     = 8

class PackageElement (object, WithMetaMixin):

    __metaclass__ = AutoPropertiesMetaclass

    def __init__ (self, owner, id):
        self._id    = id
        self._owner = owner
        self._destroyed = True

    def make_id_for (self, pkg):
        """
        Compute the extended id for this element in the context of the given
        package.
        """
        if self in pkg._own:
            return self._id

        # breadth first search in the import graph
        queue   = pkg._imports_dict.items()
        current = -1
        visited = Set()
        parent  = {}
        found = False
        while not found and current < len(queue):
            # it is important that current is incremented at the *beginning*,
            # because it is used *outside* the loop. The value after exiting
            # the loop must be the index of the last used element in queue.
            current += 1
            prefix,p = queue[current]
            visited.append (p)

            for prefix2,p2 in p._imports_dict.iteritems():
                if p2 not in visited:
                    queue.append ((prefix2,p2))
                    parent[(prefix2,p2)] = (prefix,p)
                    if self in p2._own:
                        found = True
                        break

        if not found:
            raise ValueError, "Element is not reachable from that package"

        r = self._id
        c = queue[current]
        while c is not None:
            r = "%s/%s" % (c[0], r)
            c = parent.get (c)
        return r

    def destroy (self):
        if self._destroyed: return
        self._owner._backend.destroy (self._id)
        self._destroyed = True
        self.__class__ = DestroyedPackageElement
        
    def __cmp__ (self, other):
        """
        Implements a global order over package elements.

        That order guarantees that annotations will be sorted in temporal order.
        """        
        if not isinstance (other, PackageElement): return -1
        if self._state is DESTROYED: return 1
        if other._state is DESTROYED: return -1

        t = self.ADVENE_TYPE
        d = t - other.ADVENE_TYPE
        if d: return d
        if t is ANNOTATION:
            d = self._begin - other._begin
            if d: return d
            d = self._end   - other._end
            if d: return d
            d = cmp (self._stream_id, other._stream_id)
            if d: return d
        d = cmp (self._id, other._id)
        if d: return d
        return cmp (self._owner._uri, other._owner._uri)

    def _get_id(self):
        return self._id

    def _get_meta (self, key, default):
        "will be wrapped by the WithMetaMixin"
        r = self._owner._backend.get_meta (self._id, self.ADVENE_TYPE , key)            
        if r is None:
            if default is RAISE: raise KeyError, key
            r = default
        return r

    def _set_meta (self, key, val):
        "will be wrapped by the WithMetaMixin"
        self._owner._backend.set_meta (self._id, self.ADVENE_TYPE, key, val)


# TODO: provide class DestroyedPackageElement.
