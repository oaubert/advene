"""
I define the class OwnGroup.

This class is intended to be used only inside class Package.
"""

from advene.model.core.element \
  import MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.core.group import GroupMixin

class OwnGroup(GroupMixin, object):

    # TODO filtering parameters in iter_X and count_X have not been all added
    # because of a lack of time, not for some good reason.
    # So they shall be added whenever needed, or systematically when someone
    # get the time to do it

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

    def iter_annotations(self, media=None,
                               begin=None, begin_min=None, begin_max=None,
                               end=None, end_min=None, end_max=None,
                               at=None):
        if hasattr(media, '_get_uriref'):
            media = media._get_uriref()
        elif media is not None:
            # It should be a sequence/iterator of medias
            media = (m._get_uriref() for m in media)
        if at is not None:
            begin_max = end_min = at
        o = self._owner
        for i in o._backend.iter_annotations((o._id,), None,
                                              media,
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

    def media_count(self):
        o = self._owner
        return o._backend.media_count((o._id,))

    def annotation_count(self, media=None,
                                begin=None, begin_min=None, begin_max=None,
                                end=None, end_min=None, end_max=None,
                                at=None):
        if hasattr(media, '_get_uriref'):
            media = media._get_uriref()
        elif media is not None:
            # It should be a sequence/iterator of medias
            media = (m._get_uriref() for m in media)
        if at is not None:
            begin_max = end_min = at
        o = self._owner
        return o._backend.annotation_count((o._id,), None,
                                           media,
                                           begin, begin_min, begin_max,)

    def relation_count(self):
        o = self._owner
        return o._backend.relation_count((o._id,))

    def view_count(self):
        o = self._owner
        return o._backend.view_count((o._id,))

    def resource_count(self):
        o = self._owner
        return o._backend.resource_count((o._id,))

    def tag_count(self):
        o = self._owner
        return o._backend.tag_count((o._id,))

    def list_count(self):
        o = self._owner
        return o._backend.list_count((o._id,))

    def query_count(self):
        o = self._owner
        return o._backend.query_count((o._id,))

    def import_count(self):
        o = self._owner
        return o._backend.import_count((o._id,))
