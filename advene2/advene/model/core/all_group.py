"""
I define class AllGroup.
"""

from advene.model.core.group import GroupMixin
from advene.utils.itertools import interclass

class AllGroup(GroupMixin):

    def __init__(self, owner):
        self._owner = owner

    def __contains__(self, element):
        eo = element._owner
        so = self._owner
        if so is eo:
            return element._id in so._elements
        else:
            be = eo._backend
            id = eo._id
            ids = so._backends_dict.get(be)
            if ids and id in ids:
                assert be.has_element(element._id)
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

    def iter_annotations(self, media=None, medias=None,
                               begin=None, begin_min=None, begin_max=None,
                               end=None, end_min=None, end_max=None,
                               at=None):
        o = self._owner
        if media is not None:
            media = media._get_uriref()
        if medias is not None:
            medias = (m._get_uriref() for m in medias)
        if at is not None:
            begin_max = end_min = at
        def annotation_iterator(be, pdict):
            for i in be.iter_annotations(pdict, None, None, media, medias,
                                                begin, begin_min, begin_max,
                                                end, end_min, end_max):
                yield pdict[i[1]].get_element(i)
        all_annotation_iterators = [ annotation_iterator(be, pdict)
                                     for be, pdict
                                     in o._backends_dict.items() ]
        return interclass(*all_annotation_iterators)

    def iter_relations(self, member=None, position=None):
        assert position is None or member
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
        assert position is None or item
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

    def iter_imports(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_imports(pdict):
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
 
