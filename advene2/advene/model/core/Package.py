from weakref import WeakValueDictionary

from advene import RAISE
from advene.model.backends import iter_backends

from PackageElement import STREAM, ANNOTATION, RELATION, BAG, IMPORT, QUERY, VIEW, RESOURCE 
from Stream import Stream
from Annotation import Annotation
from Relation import Relation
from View import View
from Resource import Resource
from Bag import Bag
from Query import Query
from Import import Import
from AllGroup import AllGroup
from OwnGroup import OwnGroup

from WithMetaMixin import WithMetaMixin

_constructor = {
    STREAM: Stream,
    ANNOTATION: Annotation,
    RELATION: Relation,
    VIEW: View,
    RESOURCE: Resource,
    BAG: Bag,
    QUERY: Query,
    IMPORT: Import,
}


class Package (object, WithMetaMixin):

    @staticmethod
    def create (url):
        for b in iter_backends():
            if b.claims_for_create (url):
                be = b.create (url)
                return Package (be)

    @staticmethod
    def bind (url, readonly=False, force=False):
        for b in iter_backends():
            if b.claims_for_bind (url):
                be = b.bind (url, readonly, force)
                return Package (be)

    def __init__ (self, backend):
        "DO NOT USE IT. Use Package.bind or Package.create instead"
        self._backend      = backend
        self._elements     = WeakValueDictionary()
        self._own          = OwnGroup(self)
        self._all          = AllGroup(self)
        self._imports_dict = {}
        for id, uri in backend.get_imports():
            dict[id] = Package.bind (uri)
            # TODO handle circular import
            # TODO use metadata/cache if URI can not be got?

    def close (self):
        self._backend.close()
        self.__class__ = ClosedPackage

    def get_element (self, id, default=None):
        """
        Get the element whose id is given; it can be either a simple id or a
        path id.

        If necessary, it is made by the backend, then stored (as a weak ref) in
        self._elements to prevent several instances of the same element to be
        produced.
        """
        colon = id.find (":")
        if colon <= 0:
            return self._get_own_element (id, default)
        else:
            imp = id[:colon]
            pkg = self._imported.get (imp)
            if pkg is None:
                if default is RAISE:
                    raise KeyError, id
                else:
                    return default
            else:
                return pkg.get_element (id[colon+1:], default)

    def _get_own_element (self, id, default=None):
        """
        Get the element whose id is given.
        Id may be a simple id or a path id.

        If necessary, it is made by the backend, then stored (as a weak ref) in
        self._elements to prevent several instances of the same element to be
        produced.
        """
        r = self._elements.get (id)
        if r is None:
            c = self._backend.construct_element (id)
            if c is None:
                if default is RAISE:
                    raise KeyError, id
                r = default
            else:
                type, init = c
                r = _constructor[type] (self, id, *init)
                self._elements[id] = r
        return r

    def _get_meta (self, key, default):
        "will be wrapped by the WithMetaMixin"
        r = self._backend.get_meta ("", None, key)            
        if r is None:
            if default is RAISE: raise KeyError, key
            r = default
        return r

    def _set_meta (self, key, val):
        "will be wrapped by the WithMetaMixin"
        self._backend.set_meta ("", None, key, val)

    def create_stream (self, id, uri):
        self._backend.create_stream (id, uri)
        return Stream (self, id, uri)

    def create_annotation (self, id, sid, begin, end=None):
        if end is None:
            end = begin
        self._backend.create_annotation (id, sid, begin, end)
        return Annotation (self, id, sid, begin, end)

    def create_relation (self, id):
        self._backend.create_relation (id)
        return Relation (self, id)

    def create_view (self, id):
        self._backend.create_view (id)
        return View (self, id)

    def create_resource (self, id):
        self._backend.create_resource (id)
        return Resource (self, id)

    def create_import (self, id, uri):
        self._backend.create_import (id, uri)
        self._imports_dict[id] = uri
        return Import (self, id, uri)

    def create_bag (self, id):
        self._backend.create_bag (id)
        return Bag (self, id)

    def create_query (self, id):
        self._backend.create_query (id)
        return Query (self, id)

    @property
    def own (self):
        return self._own

    @property
    def all (self):
        return self._all

class ClosedPackageException (Exception):
    pass

class ClosedPackage (object):
    def __getattribute__ (self, name):
        raise ClosedPackageException
