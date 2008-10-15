"""
I define class AllGroup.
"""

from advene.utils.itertools import interclass

class AllGroup(object):

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

    @property
    def medias(allgroup):
        o = allgroup._owner
        class AllMedias(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_medias(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == MEDIA and e in allgroup
        return AllMedias()

    @property
    def annotations(allgroup):
        o = allgroup._owner
        class AllAnnotations(object):
            def __iter__(self):
                def annotation_iterator(be, pdict):
                    for i in be.iter_annotations(pdict):
                        yield pdict[i[1]].get_element(i)
                all_annotation_iterators = [ annotation_iterator(be, pdict)
                                             for be, pdict
                                             in o._backends_dict.items() ]
                return interclass(*all_annotation_iterators)
            def __contains__(self, e):
                return e.ADVENE_TYPE == ANNOTATION and e in allgroup
        return AllAnnotations()

    @property
    def relations(allgroup):
        o = allgroup._owner
        class AllRelations(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_relations(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == RELATION and e in allgroup
        return AllRelations()

    @property
    def lists(allgroup):
        o = allgroup._owner
        class AllLists(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_lists(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST and e in allgroup
        return AllLists()

    @property
    def tags(allgroup):
        o = allgroup._owner
        class AllTags(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_tags(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG and e in allgroup
        return AllTags()

    @property
    def imports(allgroup):
        o = allgroup._owner
        class AllImports(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_imports(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == IMPORT and e in allgroup
        return AllImports()

    @property
    def queries(allgroup):
        o = allgroup._owner
        class AllQueries(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_queries(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == QUERY and e in allgroup
        return AllQueries()

    @property
    def views(allgroup):
        o = allgroup._owner
        class AllViews(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_views(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == VIEW and e in allgroup
        return AllViews()

    @property
    def resources(allgroup):
        o = allgroup._owner
        class AllResources(object):
            def __iter__(self):
                for be, pdict in o._backends_dict.items():
                    for i in be.iter_resources(pdict):
                        yield pdict[i[1]].get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == RESOURCE and e in allgroup
        return AllResources()
 
