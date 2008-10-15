from os import curdir
from os.path import abspath, exists
from sets import Set
from urlparse import urljoin, urlparse
from urllib import pathname2url, url2pathname
from urllib2 import URLError
from weakref import WeakKeyDictionary, WeakValueDictionary, ref

from advene.model.consts import _RAISE, PARSER_META_PREFIX
from advene.model.backends.exceptions import PackageInUse
from advene.model.backends.register import iter_backends
import advene.model.backends.sqlite as sqlite_backend
from advene.model.core.element import \
    MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.core.media import Media, DEFAULT_FOREF
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
from advene.model.core.meta import WithMetaMixin
from advene.model.exceptions import \
    NoClaimingError, NoSuchElementError, UnreachableImportError
from advene.model.events import PackageEventDelegate, WithEventsMixin
from advene.model.parsers.register import iter_parsers
from advene.model.serializers.register import iter_serializers
from advene.util.autoproperty import autoproperty
from advene.util.files import smart_urlopen


_constructor = {
    MEDIA: "media_factory",
    ANNOTATION: "annotation_factory",
    RELATION: "relation_factory",
    VIEW: "view_factory",
    RESOURCE: "resource_factory",
    TAG: "tag_factory",
    LIST: "list_factory",
    QUERY: "query_factory",
    IMPORT: "import_factory",
}

def _noop(*args, **kw): pass

class Package(object, WithMetaMixin, WithEventsMixin):
    """FIXME: missing docstring.
    """

    annotation_factory = Annotation
    all_factory = AllGroup
    import_factory = Import
    list_factory = List
    media_factory = Media
    relation_factory = Relation
    resource_factory = Resource
    own_factory = OwnGroup
    query_factory = Query
    tag_factory = Tag
    view_factory = View

    def __init__(self, url, create=False, readonly=False, force=False):
        """FIXME: missing docstring.
        
        @param url: the URL of the package
        @type url: string
        @param create: should the package be created ?
        @type create: boolean
        @param readonly: should the package be readonly (in the case of loading an existing package) ?
        @type readonly: boolean
        @param force: ???
        @type force: boolean
        """
        assert not (create and readonly), "Cannot create a read-only package"
        self._url = url = _make_absolute(url)
        self._readonly = readonly
        self._backend = None
        self._transient = False
        self._serializer = None
        parser = None
        if create:
            for b in iter_backends():
                claims = b.claims_for_create(url)
                if claims:
                    backend, package_id = b.create(self, force)
                    break
                elif claims.exception:
                    raise claims.exception
            else:
                backend, package_id = self._make_transient_backend()
        else: # bind or load
            for b in iter_backends():
                claims = b.claims_for_bind(url)
                if claims:
                    backend, package_id = b.bind(self, force)
                    break
                elif claims.exception:
                    raise claims.exception
            else:
                
                try:
                    f = smart_urlopen(url)
                except URLError:
                    raise NoClaimingError("bind %s (URLError)" % url)
                cmax = 0
                for p in iter_parsers():
                    c = p.claims_for_parse(f)
                    if c > cmax:
                        cmax = c
                        parser = p
                if cmax > 0:
                    self._serializer = parser.SERIALIZER
                    backend, package_id = self._make_transient_backend()
                else:
                    f.close()
                    raise NoClaimingError("bind %s" % url)

        self._backend        = backend
        self._id             = package_id
        self._elements       = WeakValueDictionary() # weakref cache
        self._heavy_elements = Set() # strong refs for heavy elements
        self._own_wref       = lambda: None
        self._all_wref       = lambda: None
        self._uri            = None
        self._event_delegate = PackageEventDelegate(self)
        self._imports_dict   = imports_dict = {}
        self._importers      = WeakKeyDictionary()
        self._backends_dict  = None


        if parser:
            parser.parse_into(f, self)
            f.close()

        # use self.__class__ as package_class (rather than Package directly)
        # so that application model subclasses do not mix with core packages.
        package_class = self.__class__
        for _, _, iid, url, uri in backend.iter_imports((package_id,)):
            p = None
            try:
                p = package_class(url)
            except NoClaimingError:
                if uri:
                    try:
                        p = package_class(url)
                    except NoClaimingError:
                        pass
            except PackageInUse, e:
                if isinstance(e.message, package_class):
                    p = e.message
            if p is None:
                pass # TODO: issue a warning, may be change automatically...
                     # I think a hook function would be the good solution
            else:
                if uri != p._uri:
                    pass # TODO: issue a warning, may be change automatically...
                         # I think a hook function would be the good solution
                p._importers[self] = iid
            imports_dict[iid] = p

        self._update_backends_dict(_firsttime=True)

    def _make_transient_backend(self):
        """FIXME: missing docstring.
        """
        claimed = False
        i = 0
        while not claimed:
            url = "sqlite::memory:;transient-%s" % i
            i += 1
            claimed = sqlite_backend.claims_for_create(url)
        self._transient = True
        return sqlite_backend.create(self, url=url)

    def _update_backends_dict(self, _firsttime=False):
        """FIXME: missing docstring.
        """
        def signature(d):
            return dict( (k, v.keys()) for k, v in d.items() )
        if not _firsttime:
            oldsig = signature(self._backends_dict)
        self._backends_dict = None # not yet constructed
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
                        d = in_construction[backend] = WeakValueDictionary()
                    for i,q in ids.items():
                        if i not in d:
                            d[i] = q
                queue.pop(-1)
            else:
                # not yet constructed, add p information for p itself...
                d = in_construction.get(p._backend)
                if d is None:
                    d = in_construction[p._backend] = WeakValueDictionary()
                d[p._id] = p
                # ... and recurse into unvisited imports
                for q in p._imports_dict.itervalues():
                    if q is not None and q not in visited:
                        queue.append(q)
                        break
                else:
                    queue.pop(-1)
        self._backends_dict = in_construction
        if not _firsttime:
            newsig = signature(self._backends_dict)
            if oldsig != newsig:
                for p in self._importers:
                    p._update_backends_dict()

    def close (self):
        """Free all external resources used by the package's backend.

        It is an error to close a package that is imported by another one,
        unless they are part of an import cycle. In the latter case, this
        package will be closed, and the other packages in the cycle will
        be closed as well.

        It is an error to use a package or any of its elements or attributes
        when the package has been closed. The behaviour is undefined.
        """
        imp = self._importers
        if not imp:
            self._do_close()
            self._finish_close()
        else:
            cycles = {}
            for be, pdict in self._backends_dict.iteritems():
                for pid, p in pdict.items():
                    if self._id in p._backends_dict.get(self._backend, ()):
                        cycles[p] = True
            for i in imp:
                if i not in cycles:
                    raise ValueError(
                        "Can not close, package is imported by <%s>" %
                        (i.uri or i.url,)
                    )
            for p in cycles:
                p._do_close()
            for p in cycles:
                p._finish_close()

    def _do_close(self):
        if self._transient:
            self._backend.delete(self._id)
        else:
            self._backend.close(self._id)
        self._backend = None
        self.emit("closed", self._url, self._uri)

    def _finish_close(self):
        """FIXME: missing docstring.
        """
        # remove references to imported packages
        self._backends_dict = None
        for p in self._imports_dict.itervalues():
            if p is not None:
                p._importers.pop(self, None)
        self._imports_dict = None

    def save(self, serializer=None):
        """Save the package to disk if its URL is in the "file:" scheme.

        A specific serializer module can be provided, else if the package was
        parsed and the parser had a corresponding serializer, that one will be
        used; else, the extension of the filename will be used to guess the
        serializer to use.

        Note that the file will be silently erased if it already exists.
        """
        p = urlparse(self._url)
        if p.scheme != "file":
            raise ValueError("Can not save to URL %s" % self._url)
        filename = url2pathname(p.path)

        self.save_as(filename, serializer=serializer or self._serializer,
                     change_url=True, erase=True)
        # above, change_url is set to force to remember the serializer

    def save_as(self, filename, change_url=False, serializer=None,
                      erase=False):
        """Save the package under the given `filename`.

        If `change_url` is set, the URL of the package will be changed to the
        corresponding ``file:`` URL.

        A specific serializer module can be provided, else the extension of the
        filename will be used to guess the serializer to use.

        Note that if the file exists, an exception will be raised.
        """
        if exists(filename) and not erase:
            raise Exception("File already exists %s" % filename) 

        s = serializer
        if s is None:
            for s in iter_serializers():
                if filename.endswith(s.EXTENSION):
                    break
            else:
                raise Exception("Can not guess correct serializer for %s" %
                                filename)

        f = open(filename, "w")
        s.serialize_to(self, f)
        f.close()

        if change_url:
            filename = abspath(filename)
            self._url = url = "file:" + pathname2url(filename)
            self._backend.update_url(self._id, self._url)
            self._serializer = serializer
        

    @autoproperty
    def _get_url(self):
        """
        The URL from which this package has been fetched.
        """
        return self._url

    @autoproperty
    def _get_readonly(self):
        return self._readonly

    @autoproperty
    def _get_uri(self):
        """
        The URI identifying this package.

        It may be different from the URL from which the package has actually
        been fetched.
        """
        r = self._uri
        if r is None:
            r = self._uri = self._backend.get_uri(self._id) 
        return r

    @autoproperty
    def _set_uri(self, uri):
        if uri is None: uri = ""
        self.emit("pre-changed::uri", "uri", uri)
        self._uri = uri
        self._backend.update_uri(self._id, self._uri)
        self.emit("changed::uri", "uri", uri)
        # TODO the following could be replaced by event handlers in imports
        for pkg, iid in self._importers.iteritems():
            imp = pkg[iid]
            imp._set_uri(uri)

    @autoproperty
    def _get_own(self):
        r = self._own_wref()
        if r is None:
            r = self.own_factory(self)
            self._own_wref = ref(r)
        return r

    @autoproperty
    def _get_all(self):
        r = self._all_wref()
        if r is None:
            r = self.all_factory(self)
            self._all_wref = ref(r)
        return r

    @property
    def closed(self):
        return self._backend is None

    # element retrieval

    def has_element(self, id, element_type=None):
        if element_type is None:
            return id in self._elements \
                or self._backend.has_element(self._id, id)
        else:
            e = self._elements.get(id)
            return (e is not None and e.ADVENE_TYPE == element_type) \
                or self._backend.has_element(self._id, id, element_type)

    def get_element(self, id, default=_RAISE):
        """Get the element with the given id-ref.

        If the element does not exist, an exception is raised (see below) 
        unless ``default`` is provided, in which case its value is returned.
        
        An `UnreachableImportError` is raised if the given id involves an
        nonexistant or unreachable import. A `NoSuchElementError` is raised if
        the last item of the id-ref is not the id of an element in the 
        corresponding package.

        Note that packages are also similar to python dictionaries, so 
        `__getitem__` and `get` can also be used to get elements.
        """
        # The element is first searched in self._elements, and if not found
        # it is constructed from backend data and cached in self._elements.
        # This prevents multiple instances representing the same backend
        # element. Note that self._elements is a WeakValueDictionary, so
        # elements automatically disappear from it whenever they are not
        # referenced anymore (in which case it is safe to construct a new
        # instance).

        # NB: internally, get_element can be passed a tuple instead of a
        # string, in which case the tuple will be used to create the element
        # instead of retrieving it from the backend.

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
                    raise UnreachableImportError(imp)
                else:
                    return default
            else:
                return pkg.get_element(id[colon+1:], default)

    def get(self, id, default=None):
        return self.get_element(id, default)

    def get_element_by_uriref(self, uriref, default_RAISE):
        """Get the element with the given uri-ref.

        If the element does not exist, an exception is raised (see below) 
        unless ``default`` is provided, in which case its value is returned.
        
        FIXME: copied from get_element, but not adapted.
        An `UnreachableImportError` is raised if the given id involves an
        nonexistant or unreachable import. A `NoSuchElementError` is raised if
        the last item of the id-ref is not the id of an element in the 
        corresponding package.

        Note that packages are also similar to python dictionaries, so 
        `__getitem__` and `get` can also be used to get elements.
        """
        sharp = uriref.index("#")
        raise NotImplementedError

    __getitem__ = get_element

    def _get_own_element(self, id, tuple=None, default=_RAISE):
        """Get the element whose id is given from the own package's elements.

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
                    raise NoSuchElementError(id)
                r = default
            else:
                type, init = c[0], c[2:]
                factory = getattr(self, _constructor[type])
                r = factory(self, *init)
                # NB: PackageElement.__init__ stores instances in _elements
        return r

    def _can_reference(self, element):
        """
        Return True iff element is owned or directly imported by this package.

        element can be either an instance of PackageElement or an id-ref.
        Note that if element is the id-ref of an imported element, its
        existence in the imported package is *not* checked (but it is checked
        that the import exists).
        """
        if hasattr(element, "_owner"):
            o = element._owner
            return o is self  or  o in self._imports_dict.values()
        else:
            path = unicode(element).split(":")
            if len(path) > 2:
                return False
            elif len(path) == 2:
                return self.has_element(path[0], IMPORT)
            else:
                return self.has_element(path[0])

    def make_id_for (self, pkg, id):
        """Compute an id-ref in this package for an element.

        The element is identified by ``id`` in the package ``pkg``. It is of
        course assumed that pkg is imported by this package.

        See also `PackageElement.make_id_in`.
        """
        if self is pkg:
            return id

        # breadth first search in the import graph
        queue   = self._imports_dict.items()
        current = 0 # use a cursor rather than actual pop
        visited = {self:True}
        parent  = {}
        found = False
        while not found and current < len(queue):
            prefix,p = queue[current]
            if p is pkg:
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
        r = id
        c = queue[current]
        while c is not None:
            r = "%s:%s" % (c[0], r)
            c = parent.get(c)
        return r

    def __iter__(self):
        # even if it is not implemented, defining __iter__ is useful, because
        # otherwise, python will try to iter passing integers to __getitem__,
        # and that makes very strange error messages...
        raise ValueError("not iterable, use X.own or X.all instead")

    # element creation

    # NB: the element constructor is called *before* the backend method
    # because the former makes some conversion between elements and id-refs,
    # that we need to property invoke the backend method.
    # This is why elements have an _initialize method, invoked after they have
    # been actually created in the backend.

    def create_media(self, id, url, frame_of_reference=DEFAULT_FOREF):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        r = self.media_factory(self, id, url, frame_of_reference)
        self._backend.create_media(self._id, id, url, frame_of_reference)
        self.emit("created::media", r)
        r._initialize()
        return r

    def create_annotation(self, id, media, begin, end,
                                mimetype, model=None, url=""):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        r = self.annotation_factory(self, id, media, begin, end,
                                              mimetype, model, url)
        self._backend.create_annotation(self._id, id, r.media_id, begin, end,
                                        mimetype, r.content_model_id, url)
        self.emit("created::annotation", r)
        r._initialize()
        return r

    def create_relation(self, id, mimetype="x-advene/none", model=None,
                        url="", members=()):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        r = self.relation_factory(self, id, mimetype, model, url, True)
        self._backend.create_relation(self._id, id,
                                      mimetype, r.content_model_id, url)
        r.extend(members) # let r do it, with all the checking it needs
        self.emit("created::relation", r)
        r._initialize()
        return r

    def create_view(self, id, mimetype, model=None, url=""):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        r = self.view_factory(self, id, mimetype, model, url)
        self._backend.create_view(self._id, id,
                                  mimetype, r.content_model_id, url)
        self.emit("created::view", r)
        r._initialize()
        return r

    def create_resource(self, id, mimetype, model=None, url=""):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        r =  self.resource_factory(self, id, mimetype, model, url)
        self._backend.create_resource(self._id, id,
                                      mimetype, r.content_model_id, url)
        self.emit("created::resource", r)
        r._initialize()
        return r

    def create_tag(self, id):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        r = self.tag_factory(self, id)
        self._backend.create_tag(self._id, id)
        self.emit("created::tag", r)
        r._initialize()
        return r

    def create_list(self, id, items=()):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        L = self.list_factory(self, id, True)
        self._backend.create_list(self._id, id)
        L.extend(items) # let L do it, with all the checking it needs
        self.emit("created::list", L)
        return L

    def create_query(self, id, mimetype, model=None, url=""):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        r = self.query_factory(self, id, mimetype, model, url)
        self._backend.create_query(self._id, id,
                                   mimetype, r.content_model_id, url)
        self.emit("created::query", r)
        r._initialize()
        return r

    def create_import(self, id, package):
        """FIXME: missing docstring.
        """
        assert not self.has_element(id), "The identifier %s already exists" % id
        assert package is not self, "A package cannot import itself"
        assert not [ p for p in self._imports_dict.itervalues()
                     if p is not None and
                      (p.url == package.url or p.uri and p.uri == package.uri)
                   ], "Package already imported"
        uri = package.uri # may access the backend
        self._backend.create_import(self._id, id, package._url, package.uri)

        self._imports_dict[id] = package
        self._update_backends_dict()
        package._importers[self] = id
        r = self.import_factory(self, id, package._url, uri)
        self.emit("created::import", r)
        return r

    def _create_import_in_parser(self, id, url, uri):
        """
        As it name implies, this method is stricly reserced to parsers for
        creating imports without actually loading them. It *must not* be
        called elsewhere (it would corrupt the package w.r.t. imports).
        """
        self._backend.create_import(self._id, id, url, uri)
        r = self.get(id)
        r._initialize()
        return r

    # tags management

    def associate_tag(self, element, tag):
        """
        Associate the given element to the given tag on behalf of this package.

        `element` must normally be a PackageElement instance and `tag` a TAG
        instance. In the case one of them is an imported element, the id-ref
        can actually be given instead of the actual element, but this should be
        used only in situation where robustness to unreachable elements is
        desirable (e.g. parsers).
        """
        assert self._can_reference(element), element
        assert self._can_reference(tag), tag
        assert getattr(tag, "ADVENE_TYPE", TAG) == TAG, "The tag should be a Tag"

        elt_owner = getattr(element, "_owner", None)
        if elt_owner:
            if elt_owner is self:
                id_e = element._id
            else:
                id_e = element.make_id_in(self)
        else:
            assert ":" in element, "Only strict id-refs are allowed (no :)"
            id_e = unicode(element)
        tag_owner = getattr(tag, "_owner", None)
        if tag_owner:
            if tag_owner is self:
                id_t = tag._id
            else:
                id_t = tag.make_id_in(self)
        else:
            assert ":" in tag, "Only strict id-refs are allowed (no :)"
            id_t = unicode(tag)

        self._backend.associate_tag(self._id, id_e, id_t)
        getattr(element, "emit", _noop)("added-tag", tag)
        getattr(tag, "emit", _noop)("added", element)

    def dissociate_tag(self, element, tag):
        """Dissociate the given element to the given tag on behalf of this package.
        """
        assert self._can_reference(element), element
        assert self._can_reference(tag), tag
        assert getattr(tag, "ADVENE_TYPE", TAG) == TAG, "The tag should be a Tag"

        elt_owner = getattr(element, "_owner", None)
        if elt_owner:
            if elt_owner is self:
                id_e = element._id
            else:
                id_e = element.make_id_in(self)
        else:
            assert ":" in element, "Only strict id-refs are allowed (no :)"
            id_e = unicode(element)
        tag_owner = getattr(tag, "_owner", None)
        if tag_owner:
            if tag_owner is self:
                id_t = tag._id
            else:
                id_t = tag.make_id_in(self)
        else:
            assert ":" in tag, "Only strict id-refs are allowed (no :)"
            id_t = unicode(tag)

        self._backend.dissociate_tag(self._id, id_e, id_t)
        getattr(element, "emit", _noop)("removed-tag", tag)
        getattr(tag, "emit", _noop)("removed", element)

    # reference finding (find all the own or imported elements referencing a
    # given element) -- combination of several backend methods
    # TODO -- or is this 

    # namespaces management

    def _get_namespaces_as_dict(self):
        """
        Return a dict representing the parser-meta:namespaces metadata, with
        URIs as keys and prefixes as values.

        Note that changing this dict does not affect the metadata. For this,
        use ``_set_namespaces_with_dict``.
        """
        r = {}
        prefixes = self.get_meta(PARSER_META_PREFIX+"namespaces" , "")
        for line in prefixes.split("\n"):
            if line:
                prefix, uri = line.split(" ")
                r[uri] = prefix
        return r

    def _set_namespaces_with_dict(self, d):
        """
        Set the parser-meta:namespaces metadata with a dict like the one
        returned by ``_get_namespaces_as_dict``.
        """
        s = "\n".join( "%s %s" % (prefix, uri)
                       for uri, prefix in d.iteritems() )
        self.set_meta(PARSER_META_PREFIX+"namespaces", s)

def _make_absolute(url):
    abscurdir = abspath(curdir)
    abslocal = "file:" + pathname2url(abscurdir) + "/"
    return urljoin(abslocal, url)
