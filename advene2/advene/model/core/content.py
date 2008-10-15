"""
I define class Content and a mixin class WithContentMixin for all types of
elements that can have a content.
"""

from weakref import ref

from advene import RAISE
from advene.utils.autoproperties import AutoPropertiesMetaclass

class Content(object):

    __metaclass__ = AutoPropertiesMetaclass

    def __init__(self, owner_element, mimetype, data, schema_idref):
        self._owner_pkg      = owner_element._owner
        self._owner_elt_wref = ref(owner_element)
        self._owner_elt_id   = owner_element._id
        self._mimetype       = mimetype
        self._data           = data
        self._schema_wref    = lambda: None
        self._schema_idref   = schema_idref
        # contents are never created from scratch, always from backend data,
        # so we may assume the data is consistent

    def _get_owner_element(self):
        r = self._owner_elt_wref()
        if r is None:
            r = self._owner_pkg.get_element(self._owner_elt_id)
            self._owner_elt_wref = ref(r)
        return r

    def _get_mimetype(self):
        return self._mimetype

    def _set_mimetype(self, mimetype):
        oe = self._get_owner_element()
        op = self._owner_pkg
        op._backend.update_content(op._id, oe._id,
                                   mimetype, self._data, self._schema_idref)
        self._mimetype = mimetype

    def _get_data(self):
        return self._data

    def _set_data(self, data):
        oe = self._get_owner_element()
        op = self._owner_pkg
        op._backend.update_content(op._id, oe._id,
                                   self._mimetype, data, self._schema_idref)
        self._data = data

    def _get_schema(self, default=RAISE):
        """
        Return the resource used as the schema of that content, or None.
        Note that the default behaviour is to raise an exception if the schema
        can not be retrieved, because None is a possible value (some contents
        do not define a schema).
        """
        m = self._schema_wref()
        if m is None and self._schema_idref != "":
            m = self._owner_pkg.get_element(self.schema_idref, default)
            if m is not default:
                self._media_wref = ref(m)
        return m

    def _set_schema(self, resource):
        oe = self._get_owner_element()
        op = self._owner_pkg
        if resource is None:
            idref = ""
            wref  = lambda: None
        else:
            assert op._can_reference(resource)
            idref = resource.make_idref_for(op)
            wref  = ref(resource)
        self._backend.update_content(op._id, oe._id,
                                     self.mimetype, self.data, idref)
        self._schema_idref = idref
        self._schema_wref  = wref

class WithContentMixin:
    @property
    def content(self):
        c = getattr(self, "_cached_content", None)
        if c is None:
            o = self._owner
            mimetype, data, schema_idref = \
                o._backend.get_content(o._id, self._id, self.ADVENE_TYPE)
            c = Content(self, mimetype, data, schema_idref)
            self._cached_content = c
        return c
