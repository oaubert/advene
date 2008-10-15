"""
I define the class OwnGroup.

This class is intended to be used only inside class Package.
"""

from advene.model.core.element \
  import MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.core.media import Media
from advene.model.core.annotation import Annotation
from advene.model.core.relation import Relation
from advene.model.core.view import View
from advene.model.core.resource import Resource
from advene.model.core.tag import Tag
from advene.model.core.list import List
from advene.model.core.query import Query
from advene.model.core.import_ import Import
from advene.model.core.group import GroupMixin

class OwnGroup(GroupMixin):

    # TODO : methods giving access to filters,
    # e.g. def iter_medias(id=None, id_alt=None, url=None, url_alt=None)

    def __init__(self, owner):
        self._owner = owner

    def __contains__(self, element):
        # the element is constructed, so if it belongs to the package, it must
        # be present in its _elements attribute
        return element._owner is self._owner \
           and element._id in self._owner._elements

    def iter_medias(self):
        o = self._owner
        for i in o._backend.iter_medias((o._id,)):
            yield o.get_element(i)

    def iter_annotations(self):
        o = self._owner
        for i in o._backend.iter_annotations((o._id,)):
            yield o.get_element(i)

    def iter_relations(self):
        o = self._owner
        for i in o._backend.iter_relations((o._id,)):
            yield o.get_element(i)

    def iter_views(self):
        o = self._owner
        for i in o._backend.iter_views((o._id,)):
            yield o.get_element(i)

    def iter_resources(self):
        o = self._owner
        for i in o._backend.iter_resources((o._id,)):
            yield o.get_element(i)

    def iter_tags(self):
        o = self._owner
        for i in o._backend.iter_tags((o._id,)):
            yield o.get_element(i)

    def iter_lists(self):
        o = self._owner
        for i in o._backend.iter_lists((o._id,)):
            yield o.get_element(i)

    def iter_queries(self):
        o = self._owner
        for i in o._backend.iter_queries((o._id,)):
            yield o.get_element(i)

    def iter_imports(self):
        o = self._owner
        for i in o._backend.iter_imports((o._id,)):
            yield o.get_element(i)

