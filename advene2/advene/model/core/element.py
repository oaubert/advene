"""
I define the common super-class of all package element classes.
"""

from advene                    import _RAISE
from advene.model.core.dirty   import DirtyMixin
from advene.model.core.meta    import WithMetaMixin
from advene.utils.autoproperty import autoproperty

# the following constants must be used as values of a property ADVENE_TYPE
# in all subclasses of PackageElement
MEDIA      = 'm'
ANNOTATION = 'a'
RELATION   = 'r'
TAG        = 't'
LIST       = 'l'
IMPORT     = 'i'
QUERY      = 'q'
VIEW       = 'v'
RESOURCE   = 'R'

class PackageElement(object, WithMetaMixin, DirtyMixin):

    def __init__(self, owner, id):
        self._id    = id
        self._owner = owner
        self._destroyed = True
        owner._elements[id] = self # cache to prevent duplicate instanciation
        self._dirty = False

    def make_idref_for(self, pkg):
        """
        Compute the id-ref for this element in the context of the given
        package.
        """
        if self._owner is pkg:
            return self._id

        # breadth first search in the import graph
        queue   = pkg._imports_dict.items()
        current = 0 # use a cursor rather than actual pop
        visited = {pkg:True}
        parent  = {}
        found = False
        while not found and current < len(queue):
            prefix,p = queue[current]
            if p is self._owner:
                found = True
            else:
                visited[p] = True
                for prefix2,p2 in p._imports_dict.iteritems():
                    if p2 not in visited:
                        queue.append((prefix2,p2))
                        parent[(prefix2,p2)] = (prefix,p)
                current += 1
        if not found:
            raise ValueError("Element is not reachable from that package")
        r = self._id
        c = queue[current]
        while c is not None:
            r = "%s:%s" % (c[0], r)
            c = parent.get(c)
        return r

    def destroy(self):
        if self._destroyed: return
        #self._owner._backend.destroy(self._id) # TODO
        self._destroyed = True
        self.__class__ = DestroyedPackageElement

    @autoproperty        
    def _get_id(self):
        return self._id

    @autoproperty
    def _get_uriref(self):
        o = self._owner
        u = o._uri or o._url
        return "%s#%s" % (u, self._id)


# TODO: provide class DestroyedPackageElement.
