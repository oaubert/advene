from advene.utils.AutoPropertiesMetaclass import AutoPropertiesMetaclass

class Content (object):

    __metaclass__ = AutoPropertiesMetaclass

    def __init__ (self, owner_element, mimetype, data):
        self._owner_element = owner_element
        self._mimetype      = mimetype
        self._data          = data

    def _get_owner_element (self):
        return self._owner_element

    def _get_mimetype (self):
        return self._mimetype

    def _set_mimetype (self, mimetype):
        self._mimetype = mimetype
        updater = self._owner_element._owner._backend.update_content
        updater (self)

    def _get_data (self):
        return self._data

    def _set_data (self, data):
        self._data = data
        updater = self._owner_element._owner._backend.update_content
        updater (self)
