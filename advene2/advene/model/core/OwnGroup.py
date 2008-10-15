"""
I define the class OwnGroup.

This class is intended to be used only inside class Package.
"""

from advene.model.core.PackageElement \
  import MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.core.Media import Media
from advene.model.core.Annotation import Annotation
from advene.model.core.Relation import Relation
from advene.model.core.View import View
from advene.model.core.Resource import Resource
from advene.model.core.Tag import Tag
from advene.model.core.List import List
from advene.model.core.Query import Query
from advene.model.core.Import import Import

class OwnGroup(object):

    # TODO : methods giving access to filters,
    # e.g. def get_medias(id=None, id_alt=None, url=None, url_alt=None)

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
                for i in o._backend.get_medias((o._id,)):
                    yield Media(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == MEDIA and e in owngroup
        return OwnMedias()

    @property
    def annotations(owngroup):
        o = owngroup._owner
        class OwnAnnotations(object):
            def __iter__(self):
                for i in o._backend.get_annotations((o._id,)):
                    yield Annotation(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == ANNOTATION and e in owngroup
        return OwnAnnotations()

    @property
    def relations(owngroup):
        o = owngroup._owner
        class OwnRelations(object):
            def __iter__(self):
                for i in o._backend.get_relations((o._id,)):
                    yield Relations(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == RELATION and e in owngroup
        return OwnRelations()

    @property
    def views(owngroup):
        o = owngroup._owner
        class OwnViews(object):
            def __iter__(self):
                for i in o._backend.get_views((o._id,)):
                    yield View(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == VIEW and e in owngroup
        return OwnViews()

    @property
    def resources(owngroup):
        o = owngroup._owner
        class OwnResources(object):
            def __iter__(self):
                for i in o._backend.get_resources((o._id,)):
                    yield Resource(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == RESOURCE and e in owngroup
        return OwnResources()

    @property
    def tags(owngroup):
        o = owngroup._owner
        class OwnTags(object):
            def __iter__(self):
                for i in o._backend.get_tags((o._id,)):
                    yield Tag(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG and e in owngroup
        return OwnTags()

    @property
    def lists(owngroup):
        o = owngroup._owner
        class OwnLists(object):
            def __iter__(self):
                for i in o._backend.get_lists((o._id,)):
                    yield List(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST and e in owngroup
        return OwnLists()

    @property
    def queries(owngroup):
        o = owngroup._owner
        class OwnQueries(object):
            def __iter__(self):
                for i in o._backend.get_queries((o._id,)):
                    yield Query(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == QUERY and e in owngroup
        return OwnQueries()

    @property
    def imports(owngroup):
        o = owngroup._owner
        class OwnImports(object):
            def __iter__(self):
                for i in o._backend.get_imports((o._id,)):
                    yield Imports(o, *i[2:])
            def __contains__(self, e):
                return e.ADVENE_TYPE == IMPORT and e in owngroup
        return OwnImports()

