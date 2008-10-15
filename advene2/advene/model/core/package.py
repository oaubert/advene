from weakref import WeakValueDictionary, ref

from advene import _RAISE
from advene.model.backends import iter_backends, NoBackendClaiming
from advene.model.core.element \
  import MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.core.media import Media
from advene.model.core.annotation import Annotation
from advene.model.core.relation import Relation
from advene.model.core.view import View
from advene.model.core.resource import Resource
from advene.model.core.tag import Tag
from advene.model.core.list import List
from advene.model.core.query import Query
from advene.model.core.import_ import Import
from advene.model.core.all_group import AllGroup
from advene.model.core.own_group import OwnGroup
from advene.model.core.dirty import DirtyMixin
from advene.model.core.meta import WithMetaMixin
from advene.utils.autoproperties import AutoPropertiesMetaclass


_constructor = {
    MEDIA: Media,
    ANNOTATION: Annotation,
    RELATION: Relation,
    VIEW: View,
    RESOURCE: Resource,
    TAG: Tag,
    LIST: List,
    QUERY: Query,
    IMPORT: Import,
}

class Package(object, WithMetaMixin, DirtyMixin):

    __metaclass__ = AutoPropertiesMetaclass

    def __init__(self, url, create=False, readonly=False, force=False):
        assert not (create and readonly)
        self._url      = url
        self._readonly = readonly
        self._backend = None
        if create:
            for b in iter_backends():
                if b.claims_for_create(url):
                    backend, package_id = b.create(self, force)
                    break
            else:
                raise NoBackendClaiming("create %s" % url)
        else: # bind
            for b in iter_backends():
                if b.claims_for_bind(url):
                    backend, package_id = b.bind(self, force)
                    break
            else:
                raise NoBackendClaiming("bind %s" % url)

        self._backend  = backend
        self._id       = package_id
        self._elements = WeakValueDictionary()
        self._own      = lambda: None
        self._all      = lambda: None
        self._uri      = backend.get_uri(package_id)

        self._imports_dict = imports_dict = {}
        for _, id, url, uri in backend.get_imports((package_id,)):
            p = Package(url)
            if p is None: p = Package(uri)
            # NB: even there, p could still be None
            if p is not None and uri != p._uri:
                pass # TODO: issue a warning, may be change automatically...
                     # I think a hook function would be the good solution
            imports_dict[id] = p

    def close (self):
        """Free all external resources used by the package's backend.

        If the package has dirty elements, clean them (since they are dirty,
        they can not be garbage collected, so they must be in _elements).

        It is an error to use a package or any of its elements or attributes
        when the package has been closed. The behaviour is undefined.
        """
        for e in self._elements:
            if e.dirty:
                e.clean()
        self.clean()
        self._backend.close(self._id)

    def _get_url(self):
        return self._url

    def _get_readonly(self):
        return self._readonly

    def _get_uri(self):
        return self._uri

    def _set_uri(self, uri):
        if uri is None: uri = ""
        self._uri = uri
        self._backend.set_uri(self._id, uri)

    def __eq__(self, other):
        return isinstance(other, Package) and (
            (self._uri != "" and self._uri == other._uri) or
            (self._uri == "" and self._url == other._url)
        )

    def has_element(self, id):
        return self._backend.has_element(self._id, id)

    def get_element(self, id, default=_RAISE):
        """
        Get the element whose id is given; it can be either a simple id or a
        path id.

        If necessary, it is made from backend data, then stored (as a weak ref)
        in self._elements to prevent several instances of the same element to
        be produced.
        """
        colon = id.find(":")
        if colon <= 0:
            return self._get_own_element(id, default)
        else:
            imp = id[:colon]
            pkg = self._imports_dict.get(imp)
            if pkg is None:
                if default is _RAISE:
                    raise UnreachableImport(imp)
                else:
                    return default
            else:
                return pkg.get_element(id[colon+1:], default)

    get = get_element

    __getitem__ = get_element

    def _get_own_element(self, id, default=_RAISE):
        """
        Get the element whose id is given.
        Id may be a simple id or a path id.

        If necessary, it is made from backend data, then stored (as a weak ref)
        in self._elements to prevent several instances of the same element to
        be produced.
        """
        r = self._elements.get(id)
        if r is None:
            c = self._backend.get_element(self._id, id)
            if c is None:
                if default is _RAISE:
                    raise KeyError(id)
                r = default
            else:
                type, init = c[0], c[2:]
                r = _constructor[type] (self, *init)
                # NB: PackageElement.__init__ stores instances in _elements
        return r

    def _can_reference(self, element):
        """
        Return True iff elements is owned or directly imported by this
        package.
        """
        o = element._owner
        return o is self  or  o in self._imports_dict.values()

    def _get_meta(self, key, default=_RAISE):
        "will be wrapped by the WithMetaMixin"
        r = self._backend.get_meta(self._id, "", None, key)            
        if r is None:
            if default is _RAISE: raise KeyError(key)
            r = default
        return r

    def _set_meta(self, key, val):
        "will be wrapped by the WithMetaMixin"
        self._backend.set_meta(self._id, "", None, key, val)

    def create_media(self, id, url):
        assert not self.has_element(id)
        self._backend.create_media(self._id, id, url)
        return Media(self, id, url)

    def create_annotation(self, id, media, begin, end=None):
        assert not self.has_element(id)
        media_idref = media.make_idref_for(self)
        if end is None:
            end = begin
        self._backend.create_annotation(self._id, id, media_idref, begin, end)
        return Annotation(self, id, media, begin, end)

    def create_relation(self, id):
        assert not self.has_element(id)
        self._backend.create_relation(self._id, id)
        return Relation(self, id)

    def create_view(self, id):
        assert not self.has_element(id)
        self._backend.create_view(self._id, id)
        return View(self, id)

    def create_resource(self, id):
        assert not self.has_element(id)
        self._backend.create_resource(self._id, id)
        return Resource(self, id)

    def create_tag(self, id):
        assert not self.has_element(id)
        self._backend.create_tag(self._id, id)
        return Tag(self, id)

    def create_list(self, id):
        assert not self.has_element(id)
        self._backend.create_list(self._id, id)
        return List(self, id)

    def create_query(self, id):
        assert not self.has_element(id)
        self._backend.create_query(self._id, id)
        return Query(self, id)

    def create_import(self, id, url):
        assert not self.has_element(id)
        p = Package.bind(url) or Package.bind(uri)

        if p is not None:
            uri = ""
            # TODO raise a warning? an exception?
        else:
            uri = p._uri
        self._backend.create_import(self._id, id, url, uri)
        self._imports_dict[id] = p
        return Import(self, id, uri)

    def _get_own(self):
        r = self._own()
        if r is None:
            r = OwnGroup(self)
            self._own = ref(r)
        return r

    def _get_all(self):
        r = self._all()
        if r is None:
            r = AllGroup(self)
            self._own = ref(r)
        return r


class UnreachableImport(Exception):
    pass

