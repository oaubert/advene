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

from os import tmpfile, path
from urllib2 import urlopen, url2pathname
from urlparse import urlparse
from weakref import ref

from advene import _RAISE
from advene.model.core.dirty import DirtyMixin
from advene.model.exceptions import ModelError
from advene.model.parsers import PARSER_META_PREFIX
from advene.utils.autoproperty import autoproperty

PACKAGED_ROOT = "%spackage_root" % PARSER_META_PREFIX

class WithContentMixin(DirtyMixin):
    """I provide functionality for elements with a content.

    This mixin assumes that it will be mixed in subclasses of PackageElement.
    """

    __mimetype     = None
    __schema_idref = None
    __schema_wref  = staticmethod(lambda: None)
    __url          = None
    __data         = None # backend data, unless __as_file is not None
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
        # NB: its is possible that data has been modified, then that a URL
        # has been set; in that case, we do need to actually clean the data.
        if not self.__url:
            o._backend.update_content_data(o._id, self._id, self.ADVENE_TYPE,
                                           self.__data or "")

    def get_content_schema(self, default=None):
        """
        Return the resource used as the schema of the content of this element,
        or None if that content has no schema.
        If the schema can not be retrieved, the default value is returned.

        See also `content_schema` and `content_schema_idref`.
        """
        # NB: if the default value is _RAISE and the schema is unreachable,
        # and exception will be raised.

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
    def _get_content_mimetype(self):
        r = self.__mimetype
        if r is None: # should not happen, but that's safer
            self._load_content_info()
            r = self.__mimetype
        return r

    @autoproperty
    def _set_content_mimetype(self, mimetype, _init=False):
        if not _init and self.__mimetype is None: # shouldn't happen, but safer
            self._load_content_info()
        self.__mimetype = mimetype
        if not _init:
            self.add_cleaning_operation_once(self.__clean_info)

    @autoproperty       
    def _get_content_schema(self):
        """
        The resource used as the schema of the content of this element, or None
        if that content has no schema.
        If the schema can not be retrieved, an exception is raised.

        See also `get_content_schema` and `content_schema_idref`.
        """
        return self.get_content_schema(_RAISE)

    @autoproperty
    def _set_content_schema(self, resource, _init=False):
        # if _init is True, no backend operation is performed,
        # and resource may be an id-ref rather than an element
        if not _init and self.__schema_idref is None:
            self._load_content_info()
        op = self._owner
        if resource is None or _init and resource == "":
            self.__schema_idref = ""
            if self.__schema_wref():
                del self.__schema_wref
        elif _init and isinstance(resource, basestring):
            self.__schema_idref = resource
        else:
            if not op._can_reference(resource):
                raise ModelError("Package %s can not reference resource %s" %
                                 op.uri, resource.make_idref_in(op))
            self.__schema_idref = resource.make_idref_in(op)
            self.__schema_wref  = ref(resource)
        if not _init:
            self.add_cleaning_operation_once(self.__clean_info)

    @autoproperty
    def _get_content_schema_idref(self):
        """The id-ref of the content schema, or None.

        This is a read-only property giving the id-ref of the resource held
        by `content_schema`, or None if there is no schema.

        Note that this property is accessible even if the corresponding
        schema is unreachable.

        See also `get_content_schema` and `content_schema`.
        """
        return self.__schema_idref or None

    @autoproperty
    def _get_content_url(self):
        r = self.__url
        if r is None: # should not happen, but that's safer
            self._load_content_info()
            r = self.__url
        return r

    @autoproperty
    def _set_content_url(self, url, _init=False):
        if not _init and self.__url is None: # should not happen, but safer
            self._load_content_info()
        if url != self.__url: # prevents to erase the data cache for no reason
            assert not url.startswith("packaged:") \
                or self._owner.get_meta(PACKAGED_ROOT, None) is not None
            self.__url = url
            if not _init:
                self.add_cleaning_operation_once(self.__clean_info)
            if self.__data is not None:
                del self.__data

    @autoproperty       
    def _get_content_data(self):
        url = self.__url
        if url is None: # should not happen, but that's safer
            self._load_content_info()
            url = self.__url
        f = self.__as_file
        if f: # backend data or "packaged:" url
            # NB: this is not threadsafe
            pos = f.tell()
            f.seek(0)
            r = f.read()
            f.seek(pos)
        elif url: # non-empty string
            f = self._get_content_as_file()
            r = f.read()
            f.close()
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
        if url.startswith("packaged:"):
            f = self._get_content_as_file()
            f.truncate()
            f.write(data)
            f.close()
            # no cleaning required since the backend sees no change
        else:
            if url:
                self.__url = ""
                # NB: the backend must do it by itself,
                # so cleaning the info is not required
            elif self.__as_file:
                # NB: an existing __as_file on the old url is not a problem
                raise IOError, "content already opened as a file"
            self.__data = data
            self.add_cleaning_operation_once(self.__clean_data)

    @autoproperty
    def _get_content_as_file(self):
        url = self.__url
        if url is None: # should not happen, but that's safer
            self._load_content_info()
            url = self.__url
        packaged = url.startswith("packaged:")

        if url: # non-empty string
            if url.startswith("packaged:"):
                # special URL scheme
                if self.__as_file:
                    raise IOError("content already opened as a file")
                o = self._owner
                prefix = o.get_meta(PACKAGED_ROOT, None)
                assert prefix is not None
                base = url2pathname(urlparse(prefix)[2])
                filename = path.join(base, url2pathname(url[10:]))
                f = self.__as_file = PackagedDataFile(filename, self)
            else:
                f = urlopen(url)
        else:
            if self.__as_file:
                raise IOError("content already opened as a file")
            f = self.__as_file = ContentDataFile(self)
        return f
        
    @autoproperty
    def _get_content(self):
        c = self.__cached_content()
        if c is None:
            c = Content(self)
            self.__cached_content = ref(c)
        return c


class Content(object):
    """A class for content objects.

    This class may be deprecated in the future. All attributes and methods have
    equivalent ones in WithContentMixin, with prefix "content_".
    """

    def __init__(self, owner_element):
        self._owner_elt = owner_element

    def get_schema(self, default=None):
        return self._owner_elt.get_content_schema(default)

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
    def _get_schema_idref(self):
        """The id-ref of the schema, or None.

        This is a read-only property giving the id-ref of the resource held
        by `schema`, or None if there is no schema.

        Note that this property is accessible even if the corresponding
        schema is unreachable.
        """
        return self._owner_elt._get_content_schema_idref()

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


class PackagedDataFile(file):
    __slots__ = ["_element",]
    def __init__(self, filename, element):
        if path.exists(filename):
            file.__init__ (self, filename, "r+")
        else:
            file.__init__ (self, filename, "w+")
        self._element = element

    def close(self):
        self.seek(0)
        self._element._WithContentMixin__data = self.read()
        self._element._WithContentMixin__as_file = None
        file.close(self)
        self._element = None
    

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

    def info(self):
        mimetype = self._element._get_content_mimetype()
        return {"content-type": mimetype,}

    def close(self):
        self.seek(0)
        self._element._WithContentMixin__data = self.read()
        self._element._WithContentMixin__as_file = None
        self._file.close()
        self._element = None

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

    @autoproperty
    def _get_softspace(self): return self._file.softspace

    @autoproperty
    def _set_softspace(self, val): self._file.softspace = val
