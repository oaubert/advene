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

from weakref import ref

from advene import _RAISE
from advene.model.core.dirty import DirtyMixin
from advene.utils.autoproperties import AutoPropertiesMetaclass

class Content(object):
    """A class for content objects.

    This class may be deprecated in the future. All attributes and methods have
    equivalent ones in WithContentMixin, with prefix "content_".
    """

    __metaclass__ = AutoPropertiesMetaclass

    def __init__(self, owner_element):
        self._owner_elt = owner_element

    def _get_mimetype(self):
        return self._owner_elt._get_content_mimetype()

    def _set_mimetype(self, mimetype):
        return self._owner_elt._set_content_mimetype(mimetype)

    def _get_data(self):
        return self._owner_elt._get_content_data()

    def _set_data(self, data):
        return self._owner_elt._set_content_data(data)


class WithContentMixin(DirtyMixin):
    """I provide functionality for elements with a content.

    This mixin assumes that it will be mixed in subclasses of PackageElement.
    """

    __mimetype     = None
    __schema_idref = None
    __schema_wref  = staticmethod(lambda: None)
    __data         = None

    __cached_content = staticmethod(lambda: None)

    def _load_content_metadata(self):
        """Load the content metadata (mimetype, schema, url)."""
        if self.__mimetype is None:
            o = self._owner
            self.__mimetype, self.__data, self.__schema_idref = \
                o._backend.get_content(o._id, self._id, self.ADVENE_TYPE)

    def _load_content_data(self):
        """Load the content data."""
        if self.__mimetype is None:
            self._load_content_metadata() # not distinguished for the moment

    def __clean_metadata(self):
        o = self._owner
        o._backend.update_content(o._id, self._id, self.__mimetype,
                                  self.__data, self.__schema_idref)

    __clean_data = __clean_metadata # not distinguished for the moment

    def _get_content_mimetype(self):
        r = self.__mimetype
        if r is None:
            self._load_content_metadata()
            r = self.__mimetype
        return r

    def _set_content_mimetype(self, mimetype):
        if self.__mimetype is None:
            self._load_content_metadata()
        self.__mimetype = mimetype
        self.add_cleaning_operation(self.__clean_metadata)
       
    def _get_content_schema(self, default=_RAISE):
        """
        Return the resource used as the schema of the content of this element,
        or None if that content has no schema.
        If the schema can not be retrieved, an exception is raised, unless the
        default parameter is provided, in which case it will be returned.
        """
        idref = self.__schema_idref
        if idref is None:
            self._load_content_metadata()
            idref = self.__schema_idref
        if idref:
            m = self.__schema_wref()
            if m is None:
                m = self._owner.get_element(self.__schema_idref, default)
                if m is not default:
                    self._media_wref = ref(m)
            return m

    def _set_content_schema(self, resource):
        if self.__schema_idref is None:
            self._load_content_metadata()
        op = self._owner
        if resource is None:
            self.__schema_idref = ""
            del self.__schema_wref
        else:
            assert op._can_reference(resource)
            self.__schema_idref = resource.make_idref_for(op)
            self.__schema_wref  = ref(resource)
        self.add_cleaning_operation(self.__clean_metadata)

    def _get_content_data(self):
        r = self.__data
        if r is None:
            self._load_content_data()
            r = self.__data
        return r

    def _set_content_data(self, data):
        if self.__data is None:
            self._load_content_data()
        self.__data = data
        self.add_cleaning_operation(self.__clean_data)

    content_mimetype = property(_get_content_data, _set_content_data)
    content_schema   = property(_get_content_schema, _set_content_schema)
    content_data     = property(_get_content_data, _set_content_data)

    @property
    def content(self):
        c = self.__cached_content()
        if c is None:
            c = Content(self)
            self.__cached_content = ref(c)
        return c
