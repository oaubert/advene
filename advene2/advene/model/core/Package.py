from weakref import WeakValueDictionary

from advene import RAISE
from advene.model.backends import iter_backends
from advene.model.core.PackageElement \
  import MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.core.Media import Media
from advene.model.core.Annotation import Annotation
from advene.model.core.Relation import Relation
from advene.model.core.View import View
from advene.model.core.Resource import Resource
from advene.model.core.Tag import Tag
from advene.model.core.List import List
from advene.model.core.Query import Query
from advene.model.core.Import import Import
from advene.model.core.AllGroup import AllGroup
from advene.model.core.OwnGroup import OwnGroup
from advene.model.core.WithMetaMixin import WithMetaMixin
from advene.utils.AutoPropertiesMetaclass import AutoPropertiesMetaclass


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


class Package(object, WithMetaMixin):

    __metaclass__ = AutoPropertiesMetaclass

    @staticmethod
    def create(url):
        for b in iter_backends():
            if b.claims_for_create(url):
                be, pid = b.create(url)
                return Package(url, be, pid)

    @staticmethod
    def bind(url, readonly=False, force=False):
        for b in iter_backends():
            if b.claims_for_bind(url):
                be, pid = b.bind(url, readonly, force)
                return Package(url, be, pid)


    def __init__(self, url, backend, package_id):
        "DO NOT USE IT. Use Package.bind or Package.create instead"
        self._url          = url
        self._backend      = backend
        self._id           = package_id
        self._imports_dict = {}

        for _, id, url, uri in backend.get_imports((package_id,)):
            p = Package.bind(url)
            if p is None: p = Package.bind(uri)
            # NB: even there, p could still be None
            if p is not None and uri != p._uri:
                pass # TODO: issue a warning, may be change automatically...
                     # I think a hook function would be the good solution
            dict[id] = p

        self._elements     = WeakValueDictionary()
        self._own          = OwnGroup(self)
        self._all          = AllGroup(self)
        self._uri          = backend.get_uri(package_id)

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

    def get_element(self, id, default=None):
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
                if default is RAISE:
                    raise UnreachableImport(imp)
                else:
                    return default
            else:
                return pkg.get_element(id[colon+1:], default)

    get = get_element

    __getitem__ = get_element

    def _get_own_element(self, id, default=None):
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
                if default is RAISE:
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

    def _get_meta(self, key, default):
        "will be wrapped by the WithMetaMixin"
        r = self._backend.get_meta(self._id, "", None, key)            
        if r is None:
            if default is RAISE: raise KeyError(key)
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
        return self._own

    def _get_all(self):
        return self._all


class UnreachableImport(Exception):
    pass

