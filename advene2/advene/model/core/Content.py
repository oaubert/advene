from weakref import ref

from advene.utils.AutoPropertiesMetaclass import AutoPropertiesMetaclass

class Content (object):

    __metaclass__ = AutoPropertiesMetaclass

    def __init__ (self, owner_element, mimetype, data, schema_idref):
        self._backend            = owner_element._owner._backend
        self._package_id         = owner_element._owner._id
        self._owner_element_wref = ref (owner_element)
        self._owner_element_id   = owner_element._id
        self._mimetype           = mimetype
        self._data               = data
        self._schema_wref        = lambda: None
        self._schema_idref       = schema_idref
        # contents are never created from scratch, always from backend data,
        # so we may assume the data is consistent

    def _get_owner_element (self, default=None):
        m = self._media_wref()
        if m is None:
            m = self._owner.get_element (self.media_id, default)
            if m is not default:
                self._media_wref = ref(m)
        return m

    def _get_mimetype (self):
        return self._mimetype

    def _set_mimetype (self, mimetype):
        self._backend.update_content (self._package_id, self._owner_element_id,
                                      mimetype, self._data, self._schema_idref)
        self._mimetype = mimetype

    def _get_data (self):
        return self._data

    def _set_data (self, data):
        self._backend.update_content (self._package_id, self._owner_element_id,
                                      self._mimetype, data, self._schema_idref)
        self._data = data

    def _get_schema (self, default=None):
        if self.schema_idref == "": return None
        m = self._schema_wref()
        if m is None:
            m = self._owner.get_element (self.schema_idref, default)
            if m is not default:
                self._media_wref = ref(m)
        return m

    def _set_schema (self, resource):
        if resource is None:
            idref = ""
            wref  = lambda: None
        else:
            op = self.owner_element._owner
            assert op._can_reference (resource)
            idref = resource.make_idref_for (op)
            wref  = ref (resource)
        self._backend.update_content (self._package_id, self._owner_element_id,
                                      self.mimetype, self.data, idref)
        self._schema_idref = idref
        self._schema_wref  = wref
        
