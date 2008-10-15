"""I define class AllGroup.
"""

from advene.model.core.group import GroupMixin
from advene.util.autoproperty import autoproperty
from advene.util.itertools import interclass

class AllGroup(GroupMixin, object):
    """FIXME: missing docstring.
    """

    # TODO filtering parameters in iter_X and count_X have not been all added
    # because of a lack of time, not for some good reason.
    # So they shall be added whenever needed, or systematically when someone
    # get the time to do it.

    def __init__(self, owner):
        self._owner = owner

    @autoproperty
    def _get_owner(self):
        return self._owner

    def __contains__(self, element):
        if not hasattr(element, "ADVENE_TYPE"):
            return False
        eo = element._owner
        so = self._owner
        if so is eo:
            return element._id in so._elements
        else:
            be = eo._backend
            id = eo._id
            ids = so._backends_dict.get(be)
            if ids and id in ids:
                assert be.has_element(element._id), "Internal error: %s is not in the backend." % element._id
                # since the instance is there and working,
                # it must be in the backend
                return True
            else:
                return False

    def iter_medias(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_medias(pdict):
                yield pdict[i[1]].get_element(i)

    def iter_annotations(self, media=None,
                               begin=None, begin_min=None, begin_max=None,
                               end=None, end_min=None, end_max=None,
                               at=None):
        """FIXME: missing docstring.
        """
        o = self._owner

        if hasattr(media, '_get_uriref'):
            media = media._get_uriref()
        elif media is not None:
            # It should be a sequence/iterator of medias
            media = (m._get_uriref() for m in media)
        if at is not None:
            begin_max = end_min = at
        def annotation_iterator(be, pdict):
            for i in be.iter_annotations(pdict, None, media,
                                                begin, begin_min, begin_max,
                                                end, end_min, end_max):
                yield pdict[i[1]].get_element(i)
        all_annotation_iterators = [ annotation_iterator(be, pdict)
                                     for be, pdict
                                     in o._backends_dict.items() ]
        return interclass(*all_annotation_iterators)

    def iter_relations(self, member=None, position=None):
        """FIXME: missing docstring.
        """
        assert position is None or member, "If position is specified, member should be specified too."
        o = self._owner
        if member is None:
            for be, pdict in o._backends_dict.items():
                for i in be.iter_relations(pdict):
                    yield pdict[i[1]].get_element(i)
        else:
            member = member._get_uriref()
            for be, pdict in o._backends_dict.items():
                for i in be.iter_relations_with_member(pdict, member,
                                                       position):
                    yield pdict[i[1]].get_element(i)

    def iter_lists(self, item=None, position=None):
        """FIXME: missing docstring.
        """
        assert position is None or item, "If position is specified, item should be specified too."

        o = self._owner
        if item is None:
            for be, pdict in o._backends_dict.items():
                for i in be.iter_lists(pdict):
                    yield pdict[i[1]].get_element(i)
        else:
            item = item._get_uriref()
            for be, pdict in o._backends_dict.items():
                for i in be.iter_lists_with_item(pdict, item, position):
                    yield pdict[i[1]].get_element(i)

    def iter_tags(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_tags(pdict):
                yield pdict[i[1]].get_element(i)

    def iter_imports(self, url=None, uri=None):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_imports(pdict, None, url, uri):
                yield pdict[i[1]].get_element(i)

    def iter_queries(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_queries(pdict):
                yield pdict[i[1]].get_element(i)

    def iter_views(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_views(pdict):
                yield pdict[i[1]].get_element(i)

    def iter_resources(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_resources(pdict):
                yield pdict[i[1]].get_element(i)

    def count_medias(self):
        o = self._owner
        return sum( be.count_medias(pdict)
                    for be, pdict in o._backends_dict.items() )

    def count_annotations(self, media=None,
                               begin=None, begin_min=None, begin_max=None,
                               end=None, end_min=None, end_max=None,
                               at=None):
        o = self._owner
        if hasattr(media, '_get_uriref'):
            media = media._get_uriref()
        elif media is not None:
            # It should be a sequence/iterator of medias
            media = (m._get_uriref() for m in media)
        if at is not None:
            begin_max = end_min = at
        return sum( be.count_annotations(pdict, None, media,
                                               begin, begin_min, begin_max,
                                               end, end_min, end_max)
                    for be, pdict in o._backends_dict.items() )

    def count_relations(self):
        o = self._owner
        return sum( be.count_relations(pdict)
                    for be, pdict in o._backends_dict.items() )

    def count_views(self):
        o = self._owner
        return sum( be.count_views(pdict)
                    for be, pdict in o._backends_dict.items() )

    def count_resources(self):
        o = self._owner
        return sum( be.count_resources(pdict)
                    for be, pdict in o._backends_dict.items() )

    def count_tags(self):
        o = self._owner
        return sum( be.count_tags(pdict)
                    for be, pdict in o._backends_dict.items() )

    def count_lists(self):
        o = self._owner
        return sum( be.count_lists(pdict)
                    for be, pdict in o._backends_dict.items() )

    def count_queries(self):
        o = self._owner
        return sum( be.count_queries(pdict)
                    for be, pdict in o._backends_dict.items() )

    def count_imports(self, url=None, uri=None):
        o = self._owner
        return sum( be.count_imports(pdict, url, uri)
                    for be, pdict in o._backends_dict.items() )

