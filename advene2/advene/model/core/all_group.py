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

    def iter_annotations(self):
        o = self._owner
        def annotation_iterator(be, pdict):
            for i in be.iter_annotations(pdict):
                yield pdict[i[1]].get_element(i)
        all_annotation_iterators = [ annotation_iterator(be, pdict)
                                     for be, pdict
                                     in o._backends_dict.items() ]
        return interclass(*all_annotation_iterators)

    def iter_relations(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_relations(pdict):
                yield pdict[i[1]].get_element(i)

    def iter_lists(self):
        o = self._owner
        for be, pdict in o._backends_dict.items():
            for i in be.iter_lists(pdict):
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
 
