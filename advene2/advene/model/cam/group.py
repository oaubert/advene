from advene.model.cam.consts import CAMSYS_TYPE
from advene.model.core.element import LIST, TAG, ElementCollection
from advene.model.core.group import GroupMixin

from itertools import chain

class CamGroupMixin(GroupMixin):
    def __iter__(self):
        return chain(*(
            self.iter_schemas(),
            self.iter_annotation_types(),
            self.iter_relation_types(),
            self.iter_medias(),
            self.iter_annotations(),
            self.iter_relations(),
            self.iter_user_lists(),
            self.iter_user_tags(),
            self.iter_views(),
            self.iter_queries(),
            self.iter_resources(),
            self.iter_imports(),
        ))

    def iter_user_tags(self):
        for t in self.iter_tags():
            if t.get_meta(CAMSYS_TYPE, None) is None:
                yield t

    def iter_annotation_types(self):
        for t in self.iter_tags():
            if t.get_meta(CAMSYS_TYPE, None) == "annotation-type":
                yield t

    def iter_relation_types(self):
        for t in self.iter_tags():
            if t.get_meta(CAMSYS_TYPE, None) == "relation-type":
                yield t

    def iter_user_lists(self):
        for t in self.iter_lists():
            if t.get_meta(CAMSYS_TYPE, None) is None:
                yield t

    def iter_schemas(self):
        for t in self.iter_lists():
            if t.get_meta(CAMSYS_TYPE, None) == "schema":
                yield t

    def count_user_tags(self):
        return len(list(self.iter_user_tags()))

    def count_annotation_types(self):
        return len(list(self.iter_annotation_types()))

    def count_relation_types(self):
        return len(list(self.iter_relation_types()))

    @property
    def user_tags(group):
        class GroupUserTags(ElementCollection):
            __iter__ = group.iter_user_tags
            __len__ = group.count_user_tags
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.get_meta(CAMSYS_TYPE, None) is None \
                       and e in group
        return GroupUserTags(group)

    @property
    def annotation_types(group):
        class GroupAnnotationTypes(ElementCollection):
            __iter__ = group.iter_annotation_types
            __len__ = group.count_annotation_types
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.get_meta(CAMSYS_TYPE, None) \
                           == "annotation-type" \
                       and e in group
        return GroupAnnotationTypes(group)

    @property
    def relation_types(group):
        class GroupRelationTypes(ElementCollection):
            __iter__ = group.iter_relation_types
            __len__ = group.count_relation_types
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.get_meta(CAMSYS_TYPE, None) \
                           == "relation-type" \
                       and e in group
        return GroupRelationTypes(group)

    @property
    def user_lists(group):
        class GroupUserLists(ElementCollection):
            __iter__ = group.iter_user_lists
            __len__ = group.count_user_lists
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST \
                       and e.get_meta(CAMSYS_TYPE, None) is None \
                       and e in group
        return GroupUserLists(group)

    @property
    def schemas(group):
        class GroupSchemas(ElementCollection):
            __iter__ = group.iter_schemas
            __len__ = group.count_schemas
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST \
                       and e.get_meta(CAMSYS_TYPE, None) == "schema" \
                       and e in group
        return GroupSchemas(group)
