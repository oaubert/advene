"""
I define the common super-class of all package element classes.
"""

from itertools import chain

from advene.model.consts       import _RAISE
from advene.model.core.events  import ElementEventDelegate, WithEventsMixin
from advene.model.core.meta    import WithMetaMixin
from advene.model.tales        import tales_context_function
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

class PackageElement(object, WithMetaMixin, WithEventsMixin):

    def __init__(self, owner, id):
        self._id    = id
        self._owner = owner
        self._deleted = False
        owner._elements[id] = self # cache to prevent duplicate instanciation
        self._event_delegate = ElementEventDelegate(self)

    def make_id_in(self, pkg):
        """Compute an id-ref for this element in the context of the given package.
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
                if p is not None:
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

    def delete(self):
        if self._deleted: return
        self._deleted = True
        #self.__class__ = DestroyedPackageElement
        self._owner._backend.delete_element(self._owner._id, self._id,
                                            self.ADVENE_TYPE)
        # TODO the following is a quick and dirty solution to have the rest of
        # the implementation work once an element has been deleted.
        # This should be reconsidered, and maybe improved.
        del self._owner._elements[self._id]

    @autoproperty        
    def _get_id(self):
        return self._id

    @autoproperty
    def _get_uriref(self):
        o = self._owner
        u = o._uri or o._url
        return "%s#%s" % (u, self._id)

    # tag management

    def iter_tags(self, package, inherited=True):
        """Iter over the tags associated with this element in ``package``.

        If ``inherited`` is set to False, the tags associated by imported
        packages of ``package`` will not be yielded.

        If a tag is unreachable, None is yielded.

        See also `iter_tag_ids`.
        """
        return self.iter_tag_ids(package, inherited, True)

    def iter_tag_ids(self, package, inherited=True, _get=0):
        """Iter over the id-refs of the tags associated with this element in
        ``package``.

        If ``inherited`` is set to False, the tags associated by imported
        packages of ``package`` will not be yielded.

        See also `iter_tags`.
        """
        # this actually also implements iter_tags
        u = self._get_uriref()
        if not inherited:
            pids = (package._id,)
            get_element = package.get_element
            for pid, tid in package._backend.iter_tags_with_element(pids, u):
                if _get:
                    y = package.get_element(tid, None)
                else:
                    y = tid
                yield y
        else:
            for be, pdict in package._backends_dict.iteritems():
                for pid, tid in be.iter_tags_with_element(pdict, u):
                    p = pdict[pid]
                    if _get:
                        y = p.get_element(tid, None)
                    else:
                        y = package.make_id_for(p, tid)
                    yield y

    def iter_taggers(self, tag, package):
        """Iter over all the packages associating this element to ``tag``.

        ``package`` is the top-level package.
        """
        eu = self._get_uriref()
        tu = tag._get_uriref()
        for be, pdict in package._backends_dict.iteritems():
            for pid in be.iter_taggers(pdict, eu, tu):
                yield pdict[pid]

    def has_tag(self, tag, package, inherited=True):
        """Is this element associated to ``tag`` by ``package``.

        If ``inherited`` is set to False, only return True if ``package`` 
        itself associates this element to ``tag``; else return True also if
        the association is inherited from an imported package.
        """
        if not inherited:
            eu = self._get_uriref()
            tu = tag._get_uriref()
            it = package._backend.iter_taggers((package._id,), eu, tu)
            return bool(list(it))
        else:
            return list(self.iter_taggers(tag, package))

    @tales_context_function
    def _tales_tags(self, context):
        refpkg = context.globals["refpkg"]
        return self.iter_tags(refpkg)

# TODO: provide class DestroyedPackageElement.
