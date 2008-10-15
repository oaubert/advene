from advene.model.core.group import GroupMixin, _GroupCollection

class CamGroupMixin(GroupMixin):
    def iter_simple_tags(self):
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

    def simple_tags_count(self):
        return len(list(iter_simple_tags()))

    def annotation_types_count(self):
        return len(list(iter_simple_tags()))

    def relation_types_count(self):
        return len(list(iter_simple_tags()))

    @property
    def simple_tags(group):
        class GroupUserTags(_GroupCollection):
            __iter__ = group.iter_simple_tags
            __len__ = group.simple_tags_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.type.id == "user-tag" \
                       and e in self._g
        return GroupUserTags(group)

    @property
    def annotation_types(group):
        class GroupAnnotationTypes(_GroupCollection):
            __iter__ = group.iter_annotation_types
            __len__ = group.annotation_types_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.type.id == "annotation-type" \
                       and e in self._g
        return GroupAnnotationTypes(group)

    @property
    def relation_types(group):
        class GroupRelationTypes(_GroupCollection):
            __iter__ = group.iter_relation_types
            __len__ = group.relation_types_count
            def __contains__(self, e):
                return e.ADVENE_TYPE == TAG \
                       and e.type.id == "relation-type" \
                       and e in self._g
        return GroupRelationTypes(group)
