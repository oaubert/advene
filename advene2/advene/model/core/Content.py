from advene.utils.AutoPropertiesMetaclass import AutoPropertiesMetaclass

# TODO check that the reference to the owner element does not provide
# it to be garbaged-collected when not used...

class Content (object):

    __metaclass__ = AutoPropertiesMetaclass

    def __init__ (self, owner_element, mimetype, data):
        self._backend       = owner_element._owner._backend
        self._backend_id    = owner_element._owner._backend_id
        self._owner_element = owner_element
        self._mimetype      = mimetype
        self._data          = data

    def _get_owner_element (self):
        return self._owner_element

    def _get_mimetype (self):
        return self._mimetype

    def _set_mimetype (self, mimetype):
        self._mimetype = mimetype
        self._backend.update_content (self._backend_id, self)

    def _get_data (self):
        return self._data

    def _set_data (self, data):
        self._data = data
        self._backend.update_content (self._backend_id, self)
