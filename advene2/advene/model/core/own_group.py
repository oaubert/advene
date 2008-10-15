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

class OwnGroup(object):

    # TODO : methods giving access to filters,
    # e.g. def iter_medias(id=None, id_alt=None, url=None, url_alt=None)

    def __init__(self, owner):
        self._owner = owner

    def __contains__(self, element):
        # the element is constructed, so if it belongs to the package, it must
        # be present in its _elements attribute
        return element._owner is self._owner \
           and element._id in self._owner._elements

    @property
    def medias(owngroup):
        o = owngroup._owner
        class OwnMedias(object):
            def __iter__(self):
                for i in o._backend.iter_medias((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == MEDIA and e in owngroup
        return OwnMedias()

    @property
    def annotations(owngroup):
        o = owngroup._owner
        class OwnAnnotations(object):
            def __iter__(self):
                for i in o._backend.iter_annotations((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == ANNOTATION and e in owngroup
        return OwnAnnotations()

    @property
    def relations(owngroup):
        o = owngroup._owner
        class OwnRelations(object):
            def __iter__(self):
                for i in o._backend.iter_relations((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == RELATION and e in owngroup
        return OwnRelations()

    @property
    def views(owngroup):
        o = owngroup._owner
        class OwnViews(object):
            def __iter__(self):
                for i in o._backend.iter_views((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == VIEW and e in owngroup
        return OwnViews()

    @property
    def resources(owngroup):
        o = owngroup._owner
        class OwnResources(object):
            def __iter__(self):
                for i in o._backend.iter_resources((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == RESOURCE and e in owngroup
        return OwnResources()

    @property
    def tags(owngroup):
        o = owngroup._owner
        class OwnTags(object):
            def __iter__(self):
                for i in o._backend.iter_tags((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG and e in owngroup
        return OwnTags()

    @property
    def lists(owngroup):
        o = owngroup._owner
        class OwnLists(object):
            def __iter__(self):
                for i in o._backend.iter_lists((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST and e in owngroup
        return OwnLists()

    @property
    def queries(owngroup):
        o = owngroup._owner
        class OwnQueries(object):
            def __iter__(self):
                for i in o._backend.iter_queries((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == QUERY and e in owngroup
        return OwnQueries()

    @property
    def imports(owngroup):
        o = owngroup._owner
        class OwnImports(object):
            def __iter__(self):
                for i in o._backend.iter_imports((o._id,)):
                    yield o.get_element(i)
            def __contains__(self, e):
                return e.ADVENE_TYPE == IMPORT and e in owngroup
        return OwnImports()

