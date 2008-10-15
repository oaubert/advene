from advene.model.core.group import GroupMixin, _GroupCollection

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

    def user_tag_count(self):
        return len(list(iter_user_tags()))

    def annotation_type_count(self):
        return len(list(iter_user_tags()))

    def relation_type_count(self):
        return len(list(iter_user_tags()))

    @property
    def user_tags(group):
        class GroupUserTags(_GroupCollection):
            __iter__ = group.iter_user_tags
            __len__ = group.user_tag_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.type.id == "user-tag" \
                       and e in self._g
        return GroupUserTags(group)

    @property
    def annotation_types(group):
        class GroupAnnotationTypes(_GroupCollection):
            __iter__ = group.iter_annotation_types
            __len__ = group.annotation_type_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.type.id == "annotation-type" \
                       and e in self._g
        return GroupAnnotationTypes(group)

    @property
    def relation_types(group):
        class GroupRelationTypes(_GroupCollection):
            __iter__ = group.iter_relation_types
            __len__ = group.relation_type_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.type.id == "relation-type" \
                       and e in self._g
        return GroupRelationTypes(group)
