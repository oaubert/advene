"""I define `GroupMixin`, a helper class to implement groups."""

from itertools import chain, islice

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
            if i.ADVENE_TYPE == RESOURCE:
                yield i

    def iter_imports(self):
        for i in self:
            if i.ADVENE_TYPE == IMPORT:
                yield i


    def count_medias(self):
        return len(list(self.iter_medias))

    def count_annotations(self):
        return len(list(self.iter_annotations))

    def count_relations(self):
        return len(list(self.iter_relations))

    def count_lists(self):
        return len(list(self.iter_lists))

    def count_tags(self):
        return len(list(self.iter_tags))

    def count_views(self):
        return len(list(self.iter_views))

    def count_queries(self):
        return len(list(self.iter_queries))

    def count_resources(self):
        return len(list(self.iter_resources))

    def count_imports(self):
        return len(list(self.iter_imports))

    @property
    def medias(group):
        class GroupMedias(_GroupCollection):
            __iter__ = group.iter_medias
            __len__ = group.count_medias
            def __contains__(self, e):
                return e.ADVENE_TYPE == MEDIA and e in self._g
        return GroupMedias(group)

    @property
    def annotations(group):
        class GroupAnnotations(_GroupCollection):
            __iter__ = group.iter_annotations
            __len__ = group.count_annotations
            def __contains__(self, e):
                return e.ADVENE_TYPE == ANNOTATION and e in self._g
        return GroupAnnotations(group)

    @property
    def relations(group):
        class GroupRelations(_GroupCollection):
            __iter__ = group.iter_relations
            __len__ = group.count_relations
            def __contains__(self, e):
                return e.ADVENE_TYPE == RELATION and e in self._g
        return GroupRelations(group)

    @property
    def views(group):
        class GroupViews(_GroupCollection):
            __iter__ = group.iter_views
            __len__ = group.count_views
            def __contains__(self, e):
                return e.ADVENE_TYPE == VIEW and e in self._g
        return GroupViews(group)

    @property
    def resources(group):
        class GroupResources(_GroupCollection):
            __iter__ = group.iter_resources
            __len__ = group.count_resources
            def __contains__(self, e):
                return e.ADVENE_TYPE == RESOURCE and e in self._g
        return GroupResources(group)

    @property
    def tags(group):
        class GroupTags(_GroupCollection):
            __iter__ = group.iter_tags
            __len__ = group.count_tags
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG and e in self._g
        return GroupTags(group)

    @property
    def lists(group):
        class GroupLists(_GroupCollection):
            __iter__ = group.iter_lists
            __len__ = group.count_lists
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST and e in self._g
        return GroupLists(group)

    @property
    def queries(group):
        class GroupQueries(_GroupCollection):
            __iter__ = group.iter_queries
            __len__ = group.count_queries
            def __contains__(self, e):
                return e.ADVENE_TYPE == QUERY and e in self._g
        return GroupQueries(group)

    @property
    def imports(group):
        class GroupImports(_GroupCollection):
            __iter__ = group.iter_imports
            __len__ = group.count_imports
            def __contains__(self, e):
                return e.ADVENE_TYPE == IMPORT and e in self._g
        return GroupImports(group)

class _GroupCollection(object):
    """
    A collection of elements contained in a group.
    """
    def __init__(self, group, can_be_filtered=True):
        self._g = group

    def __repr__(self):
        return "[" + ",".join(e.id for e in self) + "]"

    def get(self, key):
        e = self._g._owner.get(key)
        if e in self:
            return e
        else:
            return None

    def __getitem__(self, key):
        if isinstance(key, int):
            if key >= 0:
                for i,j in enumerate(self):
                    if i == key:
                        return j
                raise IndexError, key
            else:
                return list(self)[key]
        elif isinstance(key, slice):
            if key.step is None or key.step > 0:
                print "===", key.start, key.stop, key.step
                key = key.indices(self.__len__())
                return list(islice(self, *key))
            else:
                return list(self)[key]
        else:
            r = self.get(key)
            if r is None:
                raise KeyError(key)
            return r

    def __contains__(self, item):
        """
        Default and unefficient implementation of __contains__.
        Override if possible.
        """
        for i in self:
            if item == i:
                return True

    def filter(self, **kw):
        """
        Use underlying iter method with the given keywords to make a filtered
        version of that collection.
        """
        class FilteredCollection(_GroupCollection):
            def __iter__ (self):
                return self._g.__iter__(**kw)
            def __len__(self):
                return self._g.__len__(**kw)
            def filter(self, **kw):
                raise NotImplementedError("can not filter twice")
        return FilteredCollection(self)

    @property
    def _tales_size(self):
        """Return the size of the group.
        """
        return self.__len__()

    @property
    def _tales_first(self):
        return self.__iter__().next()

    @property
    def _tales_rest(self):
        class RestCollection(_GroupCollection):
            def __iter__(self):
                it = self._g.__iter__()
                it.next()
                for i in it: yield i
            def __len__(self):
                return self._g.__len__()-1
            def filter(self, **kw):
                raise NotImplementedError("RestCollection can not be filtered")
        return RestCollection(self)
