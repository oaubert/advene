"""
I define the common super-class of all package element classes.
"""

from advene.model.core.meta   import WithMetaMixin
from advene.model.events      import ElementEventDelegate, WithEventsMixin
from advene.model.tales       import tales_context_function
from advene.util.alias        import alias
from advene.util.autoproperty import autoproperty
from advene.util.session      import session

from itertools import chain

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

def get_advene_type_label(typ):
    return {
        MEDIA      : 'media',
        ANNOTATION : 'annotation',
        RELATION   : 'relation',
        TAG        : 'tag',
        LIST       : 'list',
        IMPORT     : 'import',
        QUERY      : 'query',
        VIEW       : 'view',
        RESOURCE   : 'resource',
    }[typ]


class PackageElement(object, WithMetaMixin, WithEventsMixin):

    def __init__(self, owner, id):
        """
        Element basic initialization.

        NB: __init__ is usually invoked *before* the element has been added to
        the backend, so no operation should be performed that require the
        backend to *know* the element. For this, see `_initialize`.
        """
        self._id             = id
        self._owner          = owner
        self._weight         = 0
        self._event_delegate = ElementEventDelegate(self)
        owner._elements[id] = self # cache to prevent duplicate instanciation

    def _initialize(self):
        """
        This method is invoked once after the element has been created *and*
        stored in the backend.
        """
        pass

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

    def iter_references(self, package=None):
        """
        Iter over all references that are made to this element.

        A reference is represented by a tuple of the form
        * ('item', list)
        * ('member', relation)
        * ('meta', package_or_element, key)
        * ('tagged', package, tag)
        * ('tagging', package, element) -- for tags only
        * (attribute_name, other_element)

        References are searched in the given package. If no package is given,
        references are searched in this element's owner package and in all
        packages that are currently loaded and directly importing 
        imported packages if ``inherited`` is True.
        """
        o = self._owner
        if package is None:
            it = self.iter_references
            # FIXME: possible optimisation:
            # this could be optimized by factorizing calls to the
            # same backend (in the same fashion as AllGroup).
            # However, this would complicate implementation, so let's wait
            # and see if performande is critical here.
            for i in chain(it(o), *( it(p) for p in o._importers.iterkeys() )):
                yield i
            return

        typ = self.ADVENE_TYPE
        grp = package.own
        be = package._backend
        pids = [package._id,]

        # meta references
        for (_,e,k) in be.iter_meta_refs(pids, self.uriref, typ):
            if e: e = package.get(e)
            yield ("meta", e or package, k)
        # tags
        for t in self.iter_my_tags(package, inherited=False):
            yield ("tagged", package, t)
        # tagged elements
        if typ is TAG:
            for e in self.iter_elements(package, inherited=False):
                yield ("tagging", package, e)
        # lists
        for L in grp.iter_lists(item=self):
            yield ("item", L)
        # relation
        if self.ADVENE_TYPE is ANNOTATION:
            for r in grp.iter_relations(member=self):
                yield ("member", r)
        # media
        if self.ADVENE_TYPE is MEDIA:
            for a in grp.iter_annotations(media=self):
                yield ("media", a)
        # content_model
        if self.ADVENE_TYPE is RESOURCE:
            for (_,e) in be.iter_contents_with_model(pids, self.uriref):
                e = package.get(e)
                yield ("content_model", e)

    def delete(self):
        self._owner._backend.delete_element(self._owner._id, self._id,
                                            self.ADVENE_TYPE)
        self.__class__ = DeletedPackageElement
        del self._owner._elements[self._id]

    def emit(self, detailed_signal, *args):
        """
        Override WithEventsMixin.emit in order to automatically emit the
        package signal corresponding to each element signal.
        """
        WithEventsMixin.emit(self, detailed_signal, *args)
        colon = detailed_signal.find(":")
        if colon > 0: detailed_signal = detailed_signal[:colon]
        s = "%s::%s" % (get_advene_type_label(self.ADVENE_TYPE),
                        detailed_signal)
        self._owner.emit(s, self, detailed_signal, args)

    @autoproperty
    def _get_id(self):
        """
        The identifier of this element in the context of its owner package.
        """
        return self._id

    # TODO implement renaming by setting id

    @autoproperty
    def _get_uriref(self):
        """
        The URI-ref identifying this element.

        It is built from the URI of its owner package, suffixed with the id
        of the element as a fragment-id (#).
        """
        o = self._owner
        u = o._uri or o._url
        return "%s#%s" % (u, self._id)

    @autoproperty
    def _get_owner(self):
        """
        The package containing (or owner package) this element.
        """
        return self._owner

    # tag management

    def iter_my_tags(self, package=None, inherited=True):
        """Iter over the tags associated with this element in ``package``.

        If ``package`` is not set, the session variable ``package`` is used
        instead. If the latter is not set, a TypeError is raised.

        If ``inherited`` is set to False, the tags associated by imported
        packages of ``package`` will not be yielded.

        If a tag is unreachable, None is yielded.

        See also `iter_my_tag_ids`.
        """
        return self._iter_my_tags_or_tag_ids(package, inherited, True)

    def iter_my_tag_ids(self, package=None, inherited=True, _get=0):
        """Iter over the id-refs of the tags associated with this element in
        ``package``.

        If ``package`` is not set, the session variable ``package`` is used
        instead. If the latter is not set, a TypeError is raised.

        If ``inherited`` is set to False, the tags associated by imported
        packages of ``package`` will not be yielded.

        See also `iter_my_tags`.
        """
        # this actually also implements iter_my_tags
        # see _iter_my_tags_or_tag_ids below
        if package is None:
            package = session.package
        if package is None:
            raise TypeError("no package set in session, must be specified")
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

    @alias(iter_my_tag_ids)
    def _iter_my_tags_or_tag_ids(self):
        # iter_my_tag_ids and iter_my_tags have a common implementation.
        # Normally, it should be located in a "private" method named
        # _iter_my_tags_or_tag_id.
        # However, for efficiency reasons, that private method and
        # iter_my_tag_ids have been merged into one. Both names are necessary
        # because the "public" iter_my_tag_ids may be overridden while the
        # "private" method should not. Hence that alias.
        pass

    def iter_taggers(self, tag, package=None):
        """Iter over all the packages associating this element to ``tag``.

        ``package`` is the top-level package. If not provided, the ``package``
        session variable is used. If the latter is unset, a TypeError is
        raised.
        """
        if package is None:
            package = session.package
        if package is None:
            raise TypeError("no package set in session, must be specified")
        eu = self._get_uriref()
        tu = tag._get_uriref()
        for be, pdict in package._backends_dict.iteritems():
            for pid in be.iter_taggers(pdict, eu, tu):
                yield pdict[pid]

    def has_tag(self, tag, package=None, inherited=True):
        """Is this element associated to ``tag`` by ``package``.

        If ``package`` is not provided, the ``package`` session variable is
        used. If the latter is unset, a TypeError is raised.

        If ``inherited`` is set to False, only return True if ``package``
        itself associates this element to ``tag``; else return True also if
        the association is inherited from an imported package.
        """
        if package is None:
            package = session.package
        if package is None:
            raise TypeError("no package set in session, must be specified")
        if not inherited:
            eu = self._get_uriref()
            tu = tag._get_uriref()
            it = package._backend.iter_taggers((package._id,), eu, tu)
            return bool(list(it))
        else:
            return list(self.iter_taggers(tag, package))

    # reference management

    def _increase_weight(self):
        """
        Elements are created with weight 0. Increasing its weight is equivalent
        to creating a strong reference to it, making it not volatile. Once the
        reason for keeping the element is gone, the weight should be decreased
        again with `_decrease_weight`.
        """
        # FIXME: this is not threadsafe !
        self._weight += 1
        if self._weight == 1:
            self._owner._heavy_elements.add(self)

    def _decrease_weight(self):
        """
        :see: _increase_weight
        """
        # FIXME: this is not threadsafe !
        self._weight -= 1
        if self._weight == 0:
            self._owner._heavy_elements.remove(self)

    def connect(self, detailed_signal, handler, *args):
        """
        Connect a handler to a signal.

        Note that an element with connected signals becomes heavier (i.e. less
        volatile).

        :see: `WithMetaMixin.connect`
        """
        self._increase_weight()
        return super(PackageElement, self)\
               .connect(detailed_signal, handler, *args)

    def disconnect(self, handler_id):
        """
        Disconnect a handler from a signal.

        :see: `connect`
        :see: `WithMetaMixin.disconnect`
        """
        self._decrease_weight()
        return super(PackageElement, self).disconnect(handler_id)

    @tales_context_function
    def _tales_my_tags(self, context):
        refpkg = context.globals["refpkg"]
        return self.iter_my_tags(refpkg)


class DeletedPackageElement(object):
    """
    I am just a dummy class to which deleted elements are mutated.

    That way, they are no longer usable, preventing their owner from
    unknowingly handling an element that has actually been deleted.

    Note however that good practices should be to register to the deletion
    event on the elements you reference, so as to be notified as soon as they
    are deleted.
    """
    pass
