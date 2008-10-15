"""
I define the class OwnGroup.

This class is intended to be used only inside class Package.
"""

class OwnGroup (object):

    def __init__ (self, owner):
        self._owner = owner

    def __contains__ (self, element):
        # the element is constructed, so if it belongs to the package, it must
        # be present in its _elements attribute
        return elements in self._owner._elements

    @property
    def medias (self):
        o = self._owner
        for id in o._backend.get_media_ids():
            yield o.get_element (id)

    @property
    def annotations (self):
        o = self._owner
        for id in o._backend.get_annotation_ids():
            yield o.get_element (id)

    @property
    def relations (self):
        o = self._owner
        for id in o._backend.get_relation_ids():
            yield o.get_element (id)

    @property
    def bags (self):
        o = self._owner
        for id in o._backend.get_bag_ids():
            yield o.get_element (id)

    @property
    def imports (self):
        o = self._owner
        for id in o._backend.get_import_ids():
            yield o.get_element (id)

    @property
    def queries (self):
        o = self._owner
        for id in o._backend.get_queries_ids():
            yield o.get_element (id)

    @property
    def views (self):
        o = self._owner
        for id in o._backend.get_view_ids():
            yield o.get_element (id)

    @property
    def resources (self):
        o = self._owner
        for id in o._backend.get_resource_ids():
            yield o.get_element (id)
