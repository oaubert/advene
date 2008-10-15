"""
I define class Content and a mixin class WithContentMixin for all types of
elements that can have a content.

Note that Content instances are just place-holder for content-related
attributes and methods, they do not store data about the content, the data is
stored in the element owning the content, thanks to WithContentMixin. This
makes their on-demand-generation relatively cheap (no data retrieving).

Note also attributes/methods of the form e.content.X are also accessible under
the form e.content_X, which might be slightly more efficient (less lookup). May
be the former should be eventually deprecated...
"""

from os import tmpfile
from urllib import url2pathname
from weakref import ref

from advene import _RAISE
from advene.model import PARSER_META_PREFIX, ModelError
from advene.model.core.dirty import DirtyMixin
from advene.utils.autoproperty import autoproperty

PACKAGED_ROOT = "%spackage_root" % PARSER_META_PREFIX


class Content(object):
    """A class for content objects.

    This class may be deprecated in the future. All attributes and methods have
    equivalent ones in WithContentMixin, with prefix "content_".
    """

    def __init__(self, owner_element):
        self._owner_elt = owner_element

    @autoproperty
    def _get_mimetype(self):
        return self._owner_elt._get_content_mimetype()

    @autoproperty
    def _set_mimetype(self, mimetype):
        return self._owner_elt._set_content_mimetype(mimetype)

    @autoproperty
    def _get_schema(self):
        return self._owner_elt._get_content_schema()

    @autoproperty
    def _set_schema(self, schema):
        return self._owner_elt._set_content_schema(schema)

    @autoproperty
    def _get_url(self):
        return self._owner_elt._get_content_url()

    @autoproperty
    def _set_url(self, url):
        return self._owner_elt._set_content_url(url)

    @autoproperty
    def _get_data(self):
        return self._owner_elt._get_content_data()

    @autoproperty
    def _set_data(self, data):
        return self._owner_elt._set_content_data(data)

    @autoproperty
    def _get_as_file(self):
        return self._owner_elt._get_content_as_file()


class WithContentMixin(DirtyMixin):
    """I provide functionality for elements with a content.

    This mixin assumes that it will be mixed in subclasses of PackageElement.
    """

    __mimetype     = None
    __schema_idref = None
    __schema_wref  = staticmethod(lambda: None)
    __url          = None
    __data         = None
    __as_file      = None

    __cached_content = staticmethod(lambda: None)

    def _load_content_info(self):
        """Load the content info (mimetype, schema, url)."""
        # should actually never be called
        o = self._owner
        self.__mimetype, self.__schema_idref, self.__url = \
            o._backend.get_content_info(o._id, self._id, self.ADVENE_TYPE)

    def __clean_info(self):
        o = self._owner
        o._backend.update_content_info(o._id, self._id, self.ADVENE_TYPE,
                                       self.__mimetype or "",
                                       self.__schema_idref or "",
                                       self.__url or "")

    def __clean_data(self):
        o = self._owner
        url = self.__url
        if url:
            assert url.startswith("packaged:")
            # special URL scheme, data is not really stored in the backend
            prefix = o.get_meta(PACKAGED_ROOT, None)
            assert prefix is not None
            filename = url2pathname(prefix + url[9:])
            f = open(filename, "w")
            f.write(self.__data)
            f.close()
        else:
            f = self.__as_file
            if f: self.__data = f._get_data()
            o._backend.update_content_data(o._id, self._id, self.ADVENE_TYPE,
                                           self.__data or "")

    @autoproperty
    def _get_content_mimetype(self):
        r = self.__mimetype
        if r is None: # should not happen, but that's safer
            self._load_content_info()
            r = self.__mimetype
        return r

    @autoproperty
    def _set_content_mimetype(self, mimetype, _init=False):
        if not _init and self.__mimetype is None: # should not happen
            self._load_content_info()
        self.__mimetype = mimetype
        if not _init:
            self.add_cleaning_operation_once(self.__clean_info)

    @autoproperty       
    def _get_content_schema(self, default=_RAISE):
        """
        Return the resource used as the schema of the content of this element,
        or None if that content has no schema.
        If the schema can not be retrieved, an exception is raised, unless the
        default parameter is provided, in which case it will be returned.
        """
        idref = self.__schema_idref
        if idref is None:
            self._load_content_info()
            idref = self.__schema_idref
        if idref:
            m = self.__schema_wref()
            if m is None:
                m = self._owner.get_element(self.__schema_idref, default)
                if m is not default:
                    self._media_wref = ref(m)
            return m

    @autoproperty
    def _set_content_schema(self, resource, _init=False):
        if not _init and self.__schema_idref is None:
            self._load_content_info()
        op = self._owner
        if resource is None:
            self.__schema_idref = ""
            if self.__schema_wref():
                del self.__schema_wref
        else:
            if not op._can_reference(resource):
                raise ModelError("Package %s can not reference resource %s" %
                                 op.uri, resource.make_idref_for(op))
            self.__schema_idref = resource.make_idref_for(op)
            self.__schema_wref  = ref(resource)
        if not _init:
            self.add_cleaning_operation_once(self.__clean_info)

    @autoproperty
    def _get_content_url(self):
        r = self.__url
        if r is None: # should not happen, but that's safer
            self._load_content_info()
            r = self.__url
        return r

    @autoproperty
    def _set_content_url(self, url, _init=False):
        if not _init and self.__url is None: # should not happen
            self._load_content_info()
        if url != self.__url: # prevents to erase the data cache for no reason
            assert not url.startswith("packaged:") \
                or self._owner.get_meta(PACKAGED_ROOT, None) is not None
            self.__url = url
            if not _init:
                self.add_cleaning_operation_once(self.__clean_info)
            if url and self.__data: # non-empty URL means no stored content
                del self.__data
                # NB: the backend must do it by itself,
                # so cleaning the data is not required

    @autoproperty       
    def _get_content_data(self):
        url = self.__url
        if url is None: # should not happen
            self._load_content_data()
            url = self.__data
        if url: # non-empty string
            r = self._get_content_as_file().read()
        else:
            f = self.__as_file
            if f is not None:
                r = f._get_data()
            else:
                r = self.__data
                if r is None:
                    op = self._owner
                    r = self.__data = op._backend. \
                        get_content_data(op._id, self._id, self.ADVENE_TYPE)
        return r

    @autoproperty
    def _set_content_data(self, data):
        url = self.__url
        if url is None: # should not happen, but that's safer
            self._load_content_info()
            url = self.__url
        self.__data = data
        self.add_cleaning_operation_once(self.__clean_data)
        if url and not url.startswith("packaged:"):
            del self.__url
            # NB: the backend must do it by itself,
            # so cleaning the info is not required

    @autoproperty
    def _get_content_as_file(self):
        url = self.__url
        if url is None: # should not happen
            self._load_content_data()
            url = self.__data
        if url: # non-empty string
            if url.startswith("packaged:"):
                # special URL scheme
                o = self._owner
                prefix = o.get_meta(PACKAGED_ROOT, None)
                assert prefix is not None
                filename = url2pathname(prefix + url[9:])
                f = open(filename, "r+")
            else:
                f = urlopen(url)
        else:
            f = self.__as_file
            if f is None:
                f = self.__as_file = ContentDataFile(self)
        return f
        
    @autoproperty
    def _get_content(self):
        c = self.__cached_content()
        if c is None:
            c = Content(self)
            self.__cached_content = ref(c)
        return c


class ContentDataFile(object):
    def __init__ (self, element):
        self._element = element
        self._file = f = tmpfile()
        self.flush = f.flush
        self.fileno = f.fileno
        self.isatty = f.isatty
        self.read = f.read
        self.readlines = f.readlines
        self.xreadlines = f.xreadlines
        self.seek = f.seek
        self.tell = f.tell

        f.write(element._WithContentMixin__data or "")
        f.seek(0)

    def _get_data(self):
        # WARNING: this is not thread safe
        f = self._file
        pos = f.tell()
        f.seek(0)
        r = f.read()
        f.seek(pos)
        return r

    def info(self):
        mimetype = self._element._get_content_mimetype()
        return {"content-type": mimetype,}

    def close(self):
        self._element._WithContentMixin__data = self._get_data()
        self._element._WithContentMixin__as_file = None
        self._file.close()
        self._element is None

    def truncate(self, *args):
        self._file.truncate(*args)
        self._element.add_cleaning_operation_once(
            self._element._WithContentMixin__clean_data)

    def write(self, str_):
        self._file.write(str_)
        self._element.add_cleaning_operation_once(
            self._element._WithContentMixin__clean_data)

    def writelines(self, seq):
        self._file.writelines(seq)
        self._element.add_cleaning_operation_once(
            self._element._WithContentMixin__clean_data)

    @property
    def closed(self): return self._file.closed

    @property
    def encoding(self): return self._file.encoding

    @property
    def mode(self): return self._file.mode

    @property
    def name(self): return self._file.name

    @property
    def newlines(self): return self._file.newlines

    def _get_softspace(self): return self._file.softspace
    def _set_softspace(self, val): self._file.softspace = val
    softspace = property(_get_softspace, _set_softspace)
    
