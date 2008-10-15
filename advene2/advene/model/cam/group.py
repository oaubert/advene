from advene.model.cam.consts import CAMSYS_NS_PREFIX
from advene.model.core.group import GroupMixin, _GroupCollection

_camsys_type = CAMSYS_NS_PREFIX+"type"

class CamGroupMixin(GroupMixin):
    def iter_user_tags(self):
        for t in self.iter_tags():
            if t.get_meta(_cam_system_type, None) is None:
                yield t

    def iter_annotation_types(self):
        for t in self.iter_tags():
            if t.get_meta(_cam_system_type, None) == "annotation-type":
                yield t

    def iter_relation_types(self):
        for t in self.iter_tags():
            if t.get_meta(_cam_system_type, None) == "relation-type":
                yield t

    def iter_user_lists(self):
        for t in self.iter_lists():
            if t.get_meta(_cam_system_type, None) is None:
                yield t

    def iter_schemas(self):
        for t in self.iter_lists():
            if t.get_meta(_cam_system_type, None) == "schema":
                yield t

    def count_user_tags(self):
        return len(list(iter_user_tags()))

    def count_annotation_types(self):
        return len(list(iter_user_tags()))

    def count_relation_types(self):
        return len(list(iter_user_tags()))

    @property
    def user_tags(group):
        class GroupUserTags(_GroupCollection):
            __iter__ = group.iter_user_tags
            __len__ = group.count_user_tags
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.get_meta(_cam_system_type, None) is None \
                       and e in self._g
        return GroupUserTags(group)

    @property
    def annotation_types(group):
        class GroupAnnotationTypes(_GroupCollection):
            __iter__ = group.iter_annotation_types
            __len__ = group.count_annotation_types
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.get_meta(_cam_system_type, None) \
                           == "annotation-type" \
                       and e in self._g
        return GroupAnnotationTypes(group)

    @property
    def relation_types(group):
        class GroupRelationTypes(_GroupCollection):
            __iter__ = group.iter_relation_types
            __len__ = group.count_relation_types
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.get_meta(_cam_system_type, None) \
                           == "relation-type" \
                       and e in self._g
        return GroupRelationTypes(group)

    @property
    def user_lists(group):
        class GroupUserLists(_GroupCollection):
            __iter__ = group.iter_user_lists
            __len__ = group.count_user_lists
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST \
                       and e.get_meta(_cam_system_type, None) is None \
                       and e in self._g
        return GroupUserLists(group)

    @property
    def schemas(group):
        class GroupSchemas(_GroupCollection):
            __iter__ = group.iter_schemas
            __len__ = group.count_schemas
            def __contains__(self, e):
                return e.ADVENE_TYPE == LIST \
                       and e.get_meta(_cam_system_type, None) == "schema" \
                       and e in self._g
        return GroupSchemas(group)
