"""
I define the common super-class of all package element classes.
"""

from advene.model.consts import _RAISE
from advene.model.core.meta import WithMetaMixin
from advene.model.events import ElementEventDelegate, WithEventsMixin
from advene.model.exceptions import ModelError, UnreachableImportError, \
                                    NoSuchElementError
from advene.model.tales import tales_property, tales_use_as_context
from advene.util.alias import alias
from advene.util.autoproperty import autoproperty
from advene.util.session import session

from itertools import islice

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

_package_event_template = {
        MEDIA      : 'media::%s',
        ANNOTATION : 'annotation::%s',
        RELATION   : 'relation::%s',
        TAG        : 'tag::%s',
        LIST       : 'list::%s',
        IMPORT     : 'import::%s',
        QUERY      : 'query::%s',
        VIEW       : 'view::%s',
        RESOURCE   : 'resource::%s',
}

class PackageElement(WithMetaMixin, WithEventsMixin, object):
    """
    I am the common subclass of all package element.


    Package elements are unique volatile instances:

    * unique, because it is enforced that the same element will never
      be represented at a given time by two distinct instances; hence,
      elements can be compared with the ``is`` operator as well as
      ``==``

    * volatile, because it is not guaranteed that, at two instants, the
      instance representing a given element will be the same; unused instances
      may be freed at any time, and a new instance will be created on demand.

    This should normally normally be transparent for the user.

    Developper note
    ===============
    So that volatility is indeed transparent to users, the `__setattr__` method
    has been overridden: since custom attributes are not stored in the backend,
    the instance should be kept in memory as long as it has custom attributes.

    As a consequence, all "non-custom" attributes (i.e. those that will be
    correctly re-generated when the element is re-instantiated) must be
    declared as class attribute (usually with None as their default value).

    This must also be true of subclasses of elements (NB: mixin classes should
    normally already do that).
    """

    # the __setattr__ overridding requires that all attributs relying on the
    # backend are always present:
    _id = None
    _owner = None
    _weight = 0

    def __init__(self, owner, id):
        """
        Must not be used directly, nor overridden.
        Use class methods instantiate or create_new instead.
        """
        self._id = id
        self._owner = owner
        self._weight = 0
        owner._elements[id] = self # cache to prevent duplicate instanciation

    @classmethod
    def instantiate(cls, owner, id, *args):
        """
        Factory method to create an instance from backend data.

        This method expect the exact data from the backend, so it does not
        need to be tolerant or to check consistency (the backend is assumed to
        be sane).
        """
        r = cls(owner, id)
        return r

    def __setattr__(self, name, value):
        """
        Make instance heavier when a new custom attribute is created.
        """
        if name not in self.__dict__ and not hasattr(self.__class__, name):
            #print "=== weightening", self.id, "because of", name
            self._increase_weight()
        super(PackageElement, self).__setattr__(name, value)

    def __delattr__(self, name):
        """
        Make instance lighter when a custom attribute is deleted.
        """
        super(PackageElement, self).__delattr__(name)
        if not hasattr(self.__class__, name):
            self._decrease_weight()

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

        if isinstance(element, basestring):
            assert ":" in element and element[0] != ":" # imported
            element_id = element
            element = pkg.get(element_id)
            if element is not None and element.ADVENE_TYPE != type:
                raise ModelError("type mismatch", element, type)
            else:
                # silently succeed, for the sake of parsers
                return element_id

        assert isinstance(element, PackageElement)
        if type is not None:
            elttype = element.ADVENE_TYPE
            if elttype != type:
                raise ModelError("type mismatch", element, type)
        if not pkg._can_reference(element):
            raise ModelError("can not reference", pkg, element)
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
        packages that are currently loaded and directly importing this
        packages.
        """
        o = self._owner
        if package is None:
            referrers = o._get_referrers()
        else:
            referrers = {package._backend : {package._id : package}}
        for be, d in referrers.iteritems():
            for pid, eid, rel in be.iter_references(d, self._get_uriref()):
                yield Reference(self, d[pid], eid, rel)

    def delete(self):
        """
        Delete this element.

        If the element is known to be referenced by other elements,
        all remaining references are cut (but the referer elements are
        not deleted). Note that this does not guarantees that some
        references the the deleted element will not continue to exist in
        packages that are not currently loaded.
        """
        for r in self.iter_references():
            r.cut()
        self._owner._backend.delete_element(self._owner._id, self._id,
                                            self.ADVENE_TYPE)
        self.__class__ = DeletedPackageElement
        del self._owner._elements[self._id]

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
        importers = o._importers
        assert not o.has_element(new_id)
        old_id = self._id
        # renaming in the owner package
        o._backend.rename_element(o._id, old_id, self.ADVENE_TYPE, new_id)
        # best effort renaming in all (known) importing packages
        old_uriref = self.uriref
        ibe_dict = o._get_referrers()
        for be, d in ibe_dict.iteritems():
            be.rename_references(d, old_uriref, new_id)
        # actually renaming
        del o._elements[old_id]
        o._elements[new_id] = self
        self._id = new_id
        # updating caches of packages and instantiated elements
        new_uriref = self._get_uriref()
        for be, d in ibe_dict.iteritems():
            for pid, eid, rel in be.iter_references(d, new_uriref):
                p = d[pid]
                prefix = importers.get(p, "") # p may be the owner package
                old_idref = prefix and "%s:%s" % (prefix, old_id) or old_id
                new_idref = prefix and "%s:%s" % (prefix, new_id) or new_id
                if eid == "":
                    p._update_caches(old_idref, new_idref, self, rel)
                else:
                    e = p._elements.get(eid) # only update *instantiated* elts
                    if e is not None:
                        e._update_caches(old_idref, new_idref, self, rel)
        # furthermore, if this element is an import, all id-refs using this
        # import must be updated
        # NB: since this method is embeded in a property, it can not easily
        # be overloaded, that is why we implement this here rather than in
        # import_.py
        if self.ADVENE_TYPE is not IMPORT: return
        del o._imports_dict[old_id]
        o._imports_dict[new_id] = self._imported
        self._imported._importers[o] = new_id
        for eid, rel, ref \
        in o._backend.iter_references_with_import(o._id, new_id):
            old_idref = "%s:%s" % (old_id, ref)
            new_idref = "%s:%s" % (new_id, ref)
            if eid == "":
                o._update_caches(old_idref, new_idref, None, rel)
            else:
                e = o._elements.get(eid) # only update *instantiated* elts
                if e is not None:
                    e._update_caches(old_idref, new_idref, None, rel)

    def _update_caches(self, old_idref, new_idref, element, relation):
        """
        This cooperative method is used to update all caches when an element
        in the cache is renamed. The old_idref and new_idref are provided,
        as well as the relation (as represented by backend methods
        `iter_references` and `iter_references_with_import`) with this element.
        The renamed element may be provided or be None, depending on the
        situation.
        """
        super(PackageElement, self) \
            ._update_caches(old_idref, new_idref, element, relation)


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

    # events management

    def _make_event_delegate(self):
        """
        Required by WithEventsMixin
        """
        return ElementEventDelegate(self)

    def emit(self, detailed_signal, *args):
        """
        Override WithEventsMixin.emit in order to automatically emit the
        package signal corresponding to each element signal.
        """
        WithEventsMixin.emit(self, detailed_signal, *args)
        def lazy_params():
            colon = detailed_signal.find(":")
            if colon > 0: s = detailed_signal[:colon]
            else: s = detailed_signal
            yield _package_event_template[self.ADVENE_TYPE] % s
            yield self
            yield s
            yield args
        self._owner.emit_lazy(lazy_params)

    def connect(self, detailed_signal, handler, *args):
        """
        Connect a handler to a signal.

        Note that an element with connected signals becomes heavier (i.e. less
        volatile).

        :see: `WithEventsMixin.connect`
        """
        r = super(PackageElement, self).connect(detailed_signal, handler, *args)
        self._increase_weight()
        return r

    def disconnect(self, handler_id):
        """
        Disconnect a handler from a signal.

        :see: `connect`
        :see: `WithMetaMixin.disconnect`
        """
        r = super(PackageElement, self).disconnect(handler_id)
        self._decrease_weight()
        return r

    def _self_connect(self, detailed_signal, handler, *args):
        """
        This alternative to `connect` can only be used by the element itself.
        It connects the handler to the signal but *does not* make the element
        heavier (since if the handler will disappear at the same time as the
        element...).
        """
        return super(PackageElement, self) \
                .connect(detailed_signal, handler, *args)


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

    def __eq__(self, other):
        return tuple(self) == tuple(other)

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
                key = key.indices(self.__len__())
                return list(islice(self, *key))
            else:
                return list(self)[key]
        else:
            r = self.get(key)
            if r is None:
                raise KeyError(key)
            return r

    def __repr__(self):
        return "[" + ",".join(self.keys()) + "]"

    def get(self, key, default=None):
        e = self._owner.get(key)
        if e is None:
            return default
        elif e in self:
            return e
        else:
            return default

    def keys(self):
        return [ e.make_id_in(self._owner) for e in self ]

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
        try:
            return self.__iter__().next()
        except StopIteration:
            return None

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


class Reference(object):
    """
    An object representing a reference from an element or package to an
    element.
    """
    def __init__(self, referree, package, element_id, relation):
        self._f = referree
        self._p = package
        self._e = element_id
        self._r = relation

    @property
    def referrer(self):
        eid = self._e
        if eid == "":
            return self._p
        else:
            return self._p.get(eid, _RAISE)

    @property
    def reference_type(self):
        return self._r.split(" ")[0]

    @property
    def reference_parameter(self):
        L = self._r.split(" ")
        if len(L) == 1:
            return None
        elif L[0] in (":item", ":member"):
            return int(L[1])
        elif L[0].startswith(":tag"): # :tag or :tagged
            try:
                return self._p.get(L[1])
            except UnreachableImportError:
                return L[1]
            except NoSuchElementError:
                return L[1]
        else:
            return L[1]

    def cut(self):
        L = self._r.split(" ")
        typ = L[0]
        referrer = self.referrer
        if typ in (":item", ":member"):
            del referrer[int(L[1])]
        elif typ == ":tag":
            p = self._p
            tagged = p.get(L[1]) or L[1]
            p.dissociate_tag(tagged, self._f)
        elif typ == ":tagged":
            p = self._p
            tag = p.get(L[1]) or L[1]
            p.dissociate_tag(self._f, tag)
        elif typ == ":meta":
            referrer.del_meta(L[1])
        else:
            setattr(referrer, typ, None)

    def replace(self, other):
        raise NotImplementedError()
