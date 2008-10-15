"""
I define the class OwnGroup.

This class is intended to be used only inside class Package.
"""

from advene.model.core.element \
  import MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.core.group import GroupMixin

class OwnGroup(GroupMixin):

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

    def iter_annotations(self, media=None, medias=None,
                               begin=None, begin_min=None, begin_max=None,
                               end=None, end_min=None, end_max=None,
                               at=None):
        if media is not None:
            media = media._get_uriref()
        if medias is not None:
            medias = (m._get_uriref() for m in medias)
        if at is not None:
            begin_max = end_min = at
        o = self._owner
        for i in o._backend.iter_annotations((o._id,), None, None,
                                              media, medias,
                                              begin, begin_min, begin_max,
                                              end, end_min, end_max):
            yield o.get_element(i)

    def iter_relations(self, member=None, position=None):
        assert position is None or member
        o = self._owner
        if member is None:
            for i in o._backend.iter_relations((o._id,)):
                yield o.get_element(i)
        else:
            member = member._get_uriref()
            for i in o._backend.iter_relations_with_member((o._id,), member,
                                                           position):
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

    def iter_lists(self, item=None, position=None):
        assert position is None or item
        o = self._owner
        if item is None:
            for i in o._backend.iter_lists((o._id,)):
                yield o.get_element(i)
        else:
            item = item._get_uriref()
            for i in o._backend.iter_lists_with_item((o._id,), item, position):
                yield o.get_element(i)

    def iter_queries(self):
        o = self._owner
        for i in o._backend.iter_queries((o._id,)):
            yield o.get_element(i)

    def iter_imports(self):
        o = self._owner
        for i in o._backend.iter_imports((o._id,)):
            yield o.get_element(i)

