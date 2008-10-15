from weakref import WeakValueDictionary, ref

from advene import _RAISE
from advene.model.backends import iter_backends, NoBackendClaiming
from advene.model import ModelError
from advene.model.core.element import PackageElement, MEDIA, ANNOTATION, \
  RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
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

    def __init__(self, url, create=False, readonly=False, force=False,
                 _imported_by=None):
        assert not (create and readonly)
        self._url      = url
        self._readonly = readonly
        self._backend = None
        if create:
            for b in iter_backends():
                claims = b.claims_for_create(url)
                if claims:
                    backend, package_id = b.create(self, force)
                    break
                elif claims.exception:
                    raise claims.exception
            else:
                raise NoBackendClaiming("create %s" % url)
        else: # bind
            for b in iter_backends():
                claims = b.claims_for_bind(url)
                if claims:
                    backend, package_id = b.bind(self, force)
                    break
                elif claims.exception:
                    raise claims.exception
            else:
                raise NoBackendClaiming("bind %s" % url)

        self._backend  = backend
        self._id       = package_id
        self._elements = WeakValueDictionary()
        self._own_wref = lambda: None
        self._all_wref = lambda: None
        self._uri      = None

        if _imported_by is None:
            _imported_by = []
        self._imports_dict = imports_dict = {}
        self._backends_dict = None # not yet constructed
        for _, _, iid, url, uri in backend.iter_imports((package_id,)):
            for importer in _imported_by:
                if importer.url == url or uri and importer.uri == uri:
                    p = importer
                    break
            else:
                _ib = _imported_by + [self,]
                p = Package(url, _imported_by=_ib)
                if p is None: p = Package(uri, _imported_by=_ib)
            if p is None:
                pass # TODO: issue a warning, may be change automatically...
                     # I think a hook function would be the good solution
            elif uri != p._uri:
                pass # TODO: issue a warning, may be change automatically...
                     # I think a hook function would be the good solution
            imports_dict[iid] = p

        in_construction = {}
        # iterative depth-first exploration of the import graph
        visited = {}; queue = [self,]
        while queue:
            p = queue[-1]
            visited[p] = 1
            if p._backends_dict is not None:
                # already constructed, reuse it
                for backend, ids in p._backends_dict.iteritems():
                    d = in_construction.get(backend)
                    if d is None:
                        d = in_construction[backend] = {}
                    for i,q in ids.items():
                        if i not in d:
                            d[i] = q
                queue.pop(-1)
            else:
                # not yet constructed, add p information for p itself...
                d = in_construction.get(p._backend)
                if d is None:
                    d = in_construction[p._backend] = {}
                d[p._id] = p
                # ... and recurse into unvisited imports
                for q in p._imports_dict.itervalues():
                    if q not in visited:
                        queue.append(q)
                        break
                else:
                    queue.pop(-1)
        self._backends_dict = in_construction
        

    def close (self):
        """Free all external resources used by the package's backend.

        If the package has dirty elements, clean them (since they are dirty,
        they can not be garbage collected, so they must be in _elements).

        It is an error to use a package or any of its elements or attributes
        when the package has been closed. The behaviour is undefined.
        """
        # use values instead of itervalues below, because cleaning may cause
        # elements to vanish from the WeakValueDictionary, and dict to not
        # like to be changed while being iterated
        for e in self._elements.values():
            if e.dirty:
                e.clean()
        self.clean()
        self._backend.close(self._id)
        self._backend = None

    def _get_url(self):
        return self._url

    def _get_readonly(self):
        return self._readonly

    def _get_uri(self):
        r = self._uri
        if r is None:
            r = self._uri = self._backend.get_uri(self._id) 
        return r

    def _set_uri(self, uri):
        if uri is None: uri = ""
        self._uri = uri
        self.add_cleaning_operation_once(self._backend.set_uri,
                                         self._id, self._uri)

    def __eq__(self, other):
        return isinstance(other, Package) and (
            (self._uri != "" and self._uri == other._uri) or
            (self._uri == "" and self._url == other._url)
        )

    def has_element(self, id):
        return id in self._elements or self._backend.has_element(self._id, id)

    def get_element(self, id, default=_RAISE):
        """
        Get the element whose id is given; it can be either a simple id or a
        path id.

        If necessary, it is made from backend data, then stored (as a weak ref)
        in self._elements to prevent several instances of the same element to
        be produced.

        NB: internally, get_emement can be passed a tuple instead of a string,
        in which case the tuple will be used to create the element instead
        of retrieving it from the backend.
        """
        if not isinstance(id, basestring):
            tuple = id
            id = tuple[2]
        else:
            tuple = None
        colon = id.find(":")
        if colon <= 0:
            return self._get_own_element(id, tuple, default)
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

    def _get_own_element(self, id, tuple=None, default=_RAISE):
        """
        Get the element whose id is given.
        Id may be a simple id or a path id.

        If necessary, it is made from backend data, then stored (as a weak ref)
        in self._elements to prevent several instances of the same element to
        be produced.
        """
        r = self._elements.get(id)
        if r is None:
            c = tuple or self._backend.get_element(self._id, id)
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
        tpl = self._backend.get_meta(self._id, "", None, key)            
        if tpl is None:
            if default is _RAISE: raise KeyError(key)
            r = default
        elif tpl[1]:
            r = self.get_element(tpl[0], default)
        else:
            r = tpl[0]
        return r

    def _set_meta(self, key, val):
        "will be wrapped by the WithMetaMixin"
        if isinstance(val, PackageElement):
            assert self._can_reference(val) # guaranteed by meta.py
            val = val.make_idref_for(self)
            val_is_idref = True
        else:
            val_is_idref = False
        self._backend.set_meta(self._id, "", None, key, val, val_is_idref)

    def create_media(self, id, url, frame_of_reference):
        assert not self.has_element(id)
        self._backend.create_media(self._id, id, url, frame_of_reference)
        return Media(self, id, url, frame_of_reference)

    def create_annotation(self, id, media, begin, end,
                                mimetype, schema=None, url=""):
        assert not self.has_element(id)
        media_idref = media.make_idref_for(self)
        if schema is not None:
            schema_idref = schema.make_idref_for(self)
        else:
            schema_idref = ""
        self._backend.create_annotation(self._id, id, media_idref, begin, end,
                                        mimetype, schema_idref, url)
        return Annotation(self, id, media, begin, end, mimetype, schema, url)

    def create_relation(self, id, mimetype, schema=None, url=""):
        assert not self.has_element(id)
        if schema is not None:
            schema_idref = schema.make_idref_for(self)
        else:
            schema_idref = ""
        self._backend.create_relation(self._id, id,
                                      mimetype, schema_idref, url)
        return Relation(self, id, mimetype, schema, url)

    def create_view(self, id, mimetype, schema=None, url=""):
        assert not self.has_element(id)
        if schema is not None:
            schema_idref = schema.make_idref_for(self)
        else:
            schema_idref = ""
        self._backend.create_view(self._id, id, mimetype, schema_idref, url)
        return View(self, id, mimetype, schema, url)

    def create_resource(self, id, mimetype, schema=None, url=""):
        assert not self.has_element(id)
        if schema is not None:
            schema_idref = schema.make_idref_for(self)
        else:
            schema_idref = ""
        self._backend.create_resource(self._id, id,
                                      mimetype, schema_idref, url)
        return Resource(self, id, mimetype, schema, url)

    def create_tag(self, id):
        assert not self.has_element(id)
        self._backend.create_tag(self._id, id)
        return Tag(self, id)

    def create_list(self, id):
        assert not self.has_element(id)
        self._backend.create_list(self._id, id)
        return List(self, id)

    def create_query(self, id, mimetype, schema=None, url=""):
        assert not self.has_element(id)
        if schema is not None:
            schema_idref = schema.make_idref_for(self)
        else:
            schema_idref = ""
        self._backend.create_query(self._id, id, mimetype, schema_idref, url)
        return Query(self, id, mimetype, schema, url)

    def create_import(self, id, package):
        assert not self.has_element(id)
        assert package is not self
        assert not [ p for p in self._imports_dict.itervalues()
                     if p.url == package.url
                     or p.uri and p.uri == package.uri ]
        uri = package.uri # may access the backend
        self._backend.create_import(self._id, id, package._url, package.uri)
        self._imports_dict[id] = package
        return Import(self, id, package._url, uri)

    def _get_own(self):
        r = self._own_wref()
        if r is None:
            r = OwnGroup(self)
            self._own_wref = ref(r)
        return r

    def _get_all(self):
        r = self._all_wref()
        if r is None:
            r = AllGroup(self)
            self._al_wref = ref(r)
        return r

    # reference finding (find all the own or imported elements referencing a
    # given element) -- combination of several backend methods
    # TODO


class UnreachableImport(Exception):
    pass

