"""
I define the class OwnGroup.

This class is intended to be used only inside class Package.
"""

from advene.model.core.group import GroupMixin
from advene.util.autoproperty import autoproperty

class OwnGroup(GroupMixin, object):

    # TODO filtering parameters in iter_X and count_X have not been all added
    # because of a lack of time, not for some good reason.
    # So they shall be added whenever needed, or systematically when someone
    # get the time to do it

    def __init__(self, owner):
        self._owner = owner

    @autoproperty
    def _get_owner(self):
        return self._owner

    def __contains__(self, element):
        # the element is constructed, so if it belongs to the package, it must
        # be present in its _elements attribute
        return getattr(element, "_owner", None) is self._owner \
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
        assert position is None or member, "If position is specified, member should be specified too."
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
        assert position is None or item, "If position is specified, item should be specified too."
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

    def iter_imports(self, url=None, uri=None):
        o = self._owner
        for i in o._backend.iter_imports((o._id,), None, url, uri):
            yield o.get_element(i)

    def count_medias(self):
        o = self._owner
        return o._backend.count_medias((o._id,))

    def count_annotations(self, media=None,
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
        return o._backend.count_annotations((o._id,), None,
                                           media,
                                           begin, begin_min, begin_max,)

    def count_relations(self, member=None, position=None):
        assert position is None or member is not None
        o = self._owner
        if member is None:
            return o._backend.count_relations((o._id,))
        else:
            uri = member.uriref
            return o._backend.count_relations_with_member((o._id,),
                                                          uri, position)

    def count_views(self):
        o = self._owner
        return o._backend.count_views((o._id,))

    def count_resources(self):
        o = self._owner
        return o._backend.count_resources((o._id,))

    def count_tags(self):
        o = self._owner
        return o._backend.count_tags((o._id,))

    def count_lists(self):
        o = self._owner
        return o._backend.count_lists((o._id,))

    def count_queries(self):
        o = self._owner
        return o._backend.count_queries((o._id,))

    def count_imports(self, url=None, uri=None):
        o = self._owner
        return o._backend.count_imports((o._id,), url, uri)
