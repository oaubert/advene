"""I define `GroupMixin`, a helper class to implement groups."""

from itertools import chain

from advene.model.core.element import MEDIA, ANNOTATION, RELATION, LIST, \
                                      TAG, VIEW, QUERY, RESOURCE, IMPORT

class GroupMixin:
    """I provide default implementation for all methods of the Group interface.

    Note that at least __iter__ or all the iter_* methods must be implemented
    by subclasses, for in this implementation, they depend on each other.
    """

    def __iter__(self):
        return chain(*(
            self.iter_medias(),
            self.iter_annotations(),
            self.iter_relations(),
            self.iter_lists(),
            self.iter_tags(),
            self.iter_views(),
            self.iter_queries(),
            self.iter_resources(),
            self.iter_imports(),
        ))

    def iter_medias(self):
        for i in self:
            if i.ADVENE_TYPE == MEDIA:
                yield i

    def iter_annotations(self):
        for i in self:
            if i.ADVENE_TYPE == ANNOTATION:
                yield i

    def iter_relations(self):
        for i in self:
            if i.ADVENE_TYPE == RELATION:
                yield i

    def iter_lists(self):
        for i in self:
            if i.ADVENE_TYPE == LIST:
                yield i

    def iter_tags(self):
        for i in self:
            if i.ADVENE_TYPE == TAG:
                yield i

    def iter_views(self):
        for i in self:
            if i.ADVENE_TYPE == VIEW:
                yield i

    def iter_queries(self):
        for i in self:
            if i.ADVENE_TYPE == QUERY:
                yield i

    def iter_resources(self):
        for i in self:
            if i.ADVENE_TYPE == RESOURCES:
                yield i

    def iter_imports(self):
        for i in self:
            if i.ADVENE_TYPE == IMPORTS:
                yield i


    def media_count(self):
        return len(list(self.iter_medias))

    def annotation_count(self):
        return len(list(self.iter_annotations))

    def relation_count(self):
        return len(list(self.iter_relations))

    def list_count(self):
        return len(list(self.iter_lists))

    def tag_count(self):
        return len(list(self.iter_tags))

    def view_count(self):
        return len(list(self.iter_views))

    def query_count(self):
        return len(list(self.iter_queries))

    def resource_count(self):
        return len(list(self.iter_resources))

    def import_count(self):
        return len(list(self.iter_imports))

    @property
    def medias(group):
        class GroupMedias(_GroupCollection):
            __iter__ = group.iter_medias
            __len__ = group.media_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == MEDIA and e in self._g
        return GroupMedias(group)

    @property
    def annotations(group):
        class GroupAnnotations(_GroupCollection):
            __iter__ = group.iter_annotations
            __len__ = group.annotation_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == ANNOTATION and e in self._g
        return GroupAnnotations(group)

    @property
    def relations(group):
        class GroupRelations(_GroupCollection):
            __iter__ = group.iter_relations
            __len__ = group.relation_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == RELATION and e in self._g
        return GroupRelations(group)

    @property
    def views(group):
        class GroupViews(_GroupCollection):
            __iter__ = group.iter_views
            __len__ = group.view_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == VIEW and e in self._g
        return GroupViews(group)

    @property
    def resources(group):
        class GroupResources(_GroupCollection):
            __iter__ = group.iter_resources
            __len__ = group.resource_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == RESOURCE and e in self._g
        return GroupResources(group)

    @property
    def tags(group):
        class GroupTags(_GroupCollection):
            __iter__ = group.iter_tags
            __len__ = group.tag_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG and e in self._g
        return GroupTags(group)

    @property
    def lists(group):
        class GroupLists(_GroupCollection):
            __iter__ = group.iter_lists
            __len__ = group.list_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST and e in self._g
        return GroupLists(group)

    @property
    def queries(group):
        class GroupQueries(_GroupCollection):
            __iter__ = group.iter_queries
            __len__ = group.query_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == QUERY and e in self._g
        return GroupQueries(group)

    @property
    def imports(group):
        class GroupImports(_GroupCollection):
            __iter__ = group.iter_imports
            __len__ = group.import_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == IMPORT and e in self._g
        return GroupImports(group)



class _GroupCollection(object):
    def __init__(self, group):
        self._g = group

    def get(self, key):
        e = self._g._owner.get(key)
        if e in self:
            return e
        else:
            return None

    def __getitem__(self, key):
        if isinstance(key, int) or isinstance(key, slice):
            # TODO optimize this ?
            return list(self)[key]
        else:
            r = self.get(key)
            if r is None:
                raise KeyError(key)
            return r
