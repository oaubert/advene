"""I define `GroupMixin`, a helper class to implement groups."""

from itertools import chain

from advene.model.core.element import MEDIA, ANNOTATION, RELATION, LIST, \
                                      TAG, VIEW, QUERY, RESOURCE, IMPORT, \
                                      ElementCollection

class GroupMixin(object):
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
            if i.ADVENE_TYPE == RESOURCE:
                yield i

    def iter_imports(self):
        for i in self:
            if i.ADVENE_TYPE == IMPORT:
                yield i


    def count_medias(self):
        return len(list(self.iter_medias()))

    def count_annotations(self):
        return len(list(self.iter_annotations()))

    def count_relations(self):
        return len(list(self.iter_relations()))

    def count_lists(self):
        return len(list(self.iter_lists()))

    def count_tags(self):
        return len(list(self.iter_tags()))

    def count_views(self):
        return len(list(self.iter_views()))

    def count_queries(self):
        return len(list(self.iter_queries()))

    def count_resources(self):
        return len(list(self.iter_resources()))

    def count_imports(self):
        return len(list(self.iter_imports()))

    @property
    def medias(group):
        class GroupMedias(ElementCollection):
            __iter__ = group.iter_medias
            __len__ = group.count_medias
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == MEDIA and e in group
        return GroupMedias(group.owner)

    @property
    def annotations(group):
        class GroupAnnotations(ElementCollection):
            __iter__ = group.iter_annotations
            __len__ = group.count_annotations
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == ANNOTATION \
                   and e in group
        return GroupAnnotations(group.owner)

    @property
    def relations(group):
        class GroupRelations(ElementCollection):
            __iter__ = group.iter_relations
            __len__ = group.count_relations
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == RELATION \
                   and e in group
        return GroupRelations(group.owner)

    @property
    def views(group):
        class GroupViews(ElementCollection):
            __iter__ = group.iter_views
            __len__ = group.count_views
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == VIEW and e in group
        return GroupViews(group.owner)

    @property
    def resources(group):
        class GroupResources(ElementCollection):
            __iter__ = group.iter_resources
            __len__ = group.count_resources
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == RESOURCE \
                   and e in group
        return GroupResources(group.owner)

    @property
    def tags(group):
        class GroupTags(ElementCollection):
            __iter__ = group.iter_tags
            __len__ = group.count_tags
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == TAG and e in group
        return GroupTags(group.owner)

    @property
    def lists(group):
        class GroupLists(ElementCollection):
            __iter__ = group.iter_lists
            __len__ = group.count_lists
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == LIST and e in group
        return GroupLists(group.owner)

    @property
    def queries(group):
        class GroupQueries(ElementCollection):
            __iter__ = group.iter_queries
            __len__ = group.count_queries
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == QUERY and e in group
        return GroupQueries(group.owner)

    @property
    def imports(group):
        class GroupImports(ElementCollection):
            __iter__ = group.iter_imports
            __len__ = group.count_imports
            def __contains__(self, e):
                return getattr(e, "ADVENE_TYPE", None) == IMPORT and e in group
        return GroupImports(group.owner)



