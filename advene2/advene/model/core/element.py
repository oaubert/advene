"""
I define the common super-class of all package element classes.
"""

from advene.model.core.meta import WithMetaMixin
from advene.model.events import ElementEventDelegate, WithEventsMixin
from advene.model.exceptions import ModelError
from advene.model.tales import tales_property, tales_use_as_context
from advene.util.alias import alias
from advene.util.autoproperty import autoproperty
from advene.util.session import session

from itertools import chain, islice

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
        Must not be used directly, nor overridden.
        Use class methods instantiate or create_new instead.
        """
        self._id = id
        self._owner = owner
        self._weight = 0
        self._event_delegate = ElementEventDelegate(self)
        owner._elements[id] = self # cache to prevent duplicate instanciation

    @classmethod
    def instantiate(cls, owner, id):
        """
        Factory method to create an instance from backend data.

        This method expect the exact data from the backend, so it does not
        need to be tolerant or to check consistency (the backend is assumed to
        be sane).
        """
        r = cls(owner, id)
        return r

    @classmethod
    def create_new(cls, owner, id):
        """
        Factory method to create a new instance both in memory and backend.

        This method will usually perform checks and conversions from its actual
        arguments to the data expected to the backend. It is responsible for
        1/ storing the data in the backend and 2/ initializing the instance
        (for which it may reuse instantiate to reduce redundancy).

        Note that this method *should* be tolerant w.r.t. its parameters,
        especially accepting both element instances or ID-refs.

        NB: this method does nothing and must not be invoked by superclasses
        (indeed, it raises an exception).
        """
        raise NotImplementedError("must be overridden in subclasses")

    @staticmethod
    def _check_reference(pkg, element, type=None, required=False):
        """
        Raise a ModelError if element is not referenceable by pkg, and (if
        provided) if it has not the given type. Furthermore, if required is set
        to True, raise a ModelError if element is None (else None is silently
        ignored).

        Note that element may be a strict ID-ref, in which case this method
        will do its best to check its type, but will *succeed silently* if the
        element is unreachable (because parsers need to be able to add
        unreachable elements).

        Also, return the ID-ref of that element in this element's owner package,
        for this information is usually useful in the situations where a check
        is performed. If element is None, return "".
        """
        if element is None or element == "":
            if required:
                raise ModelError("required element")
            else:
                return ""

        elttype = getattr(element, "ADVENE_TYPE", None)
        if elttype is not None and type is not None and elttype != type:
            raise ModelError("type mismatch", element, type)
        if not pkg._can_reference(element):
            raise ModelError("can not reference", pkg, element)
        if elttype is None and type is not None:
            element = pkg.get(element)
            if element is not None and element.ADVENE_TYPE != type:
                raise ModelError("type mismatch", element, type)
        # if no exception was raised
        if elttype is None:
            return element
        else:
            return element.make_id_in(pkg)


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

    @autoproperty
    def _set_id(self, new_id):
        """
        Rename this element to `new_id`, if it is not already in use in the
        package, else raises an AssertionError.
        """
        o = self._owner
        assert not o.has_element(new_id)
        old_id = self._id
        be = o._backend
        be.rename_element(o._id, old_id, self.ADVENE_TYPE, new_id)
        # FIXME: possible optimisation
        # we could factorize calls to the same backend, in the same fashion
        # as AllGroup does. Let us wait and see if it is necessary.
        old_uriref = self.uriref
        be.rename_references([o._id,], old_uriref, new_id)
        for p in o._importers.keys():
            p._backend.rename_references([p._id,], old_uriref, new_id)
        
        del o._elements[old_id]
        o._elements[new_id] = self
        self._id = new_id

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

    @tales_property
    @tales_use_as_context("refpkg")
    def _tales_my_tags(self, context_package):
        class TagCollection(ElementCollection):
            __iter__ = lambda s: self.iter_my_tags(context_package)
            __contains__ = lambda s,x: self.has_tag(x, context_package)
        return TagCollection(self._owner)


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


class ElementCollection(object):
    """
    A base-class for coder-friendly and TAL-friendly element collections.

    Subclasses must override either __iter__ or both __len__ and __getitem__.

    In most cases, it is a good idea to override __contains__, and __len__
    (even if the subclass is overriding __iter__).

    The class attribute _allow_filtering can also be overridden to disallow
    the use of the filter method.
    """
    def __init__(self, owner_package):
        """
        Initialise the element collection.

        `owner_package`is used only in the `get` method, to provide a context
        to the ID-ref.
        """
        self._owner = owner_package

    def __iter__(self):
        """
        Default implementation relying on __len__ and __getitem__.
        """
        for i in xrange(len(self)):
            yield self[i]

    def __len__(self):
        """
        Default (and inefficient) implementation relying on __iter__.
        """
        return len(list(self))

    def __getitem__(self, key):
        """
        Default implementation relying on __iter__.
        """
        if isinstance(key, int):
            if key >= 0:
                for i,j in enumerate(self):
                    if i == key:
                        return j
                raise IndexError, key
            else:
                return list(self)[key]
        elif isinstance(key, slice):
            if key.step is None or key.step > 0:
                print "===", key.start, key.stop, key.step
                key = key.indices(self.__len__())
                return list(islice(self, *key))
            else:
                return list(self)[key]
        else:
            r = self.get(key)
            if r is None:
                raise KeyError(key)
            return r

    def __contains__(self, item):
        """
        Default and inefficient implementation relying on __iter__.
        Override if possible.
        """
        for i in self:
            if item == i:
                return True

    def __repr__(self):
        return "[" + ",".join(e.id for e in self) + "]"

    def get(self, key):
        e = self._owner.get(key)
        if e in self:
            return e
        else:
            return None

    _allow_filter = True

    def filter(collection, **kw):
        """
        Use underlying iter method with the given keywords to make a filtered
        version of that collection.
        """
        if not collection._allow_filter:
            raise TypeError("filtering is not allowed on %r") % collection
        class FilteredCollection(ElementCollection):
            def __iter__ (self):
                return collection.__iter__(**kw)
            def __len__(self):
                return collection.__len__(**kw)
            def filter(self, **kw):
                raise NotImplementedError("can not filter twice")
        return FilteredCollection(collection._owner)

    @property
    def _tales_size(self):
        """Return the size of the group.
        """
        return self.__len__()

    @property
    def _tales_first(self):
        return self.__iter__().next()

    @property
    def _tales_rest(self):
        class RestCollection(ElementCollection):
            def __iter__(self):
                it = self.__iter__()
                it.next()
                for i in it: yield i
            def __len__(self):
                return self.__len__()-1
            def filter(self, **kw):
                raise NotImplementedError("RestCollection can not be filtered")
        return RestCollection(self)
