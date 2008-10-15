from advene.model.cam.consts import CAM_TYPE, CAMSYS_TYPE
from advene.model.cam.element import CamElementMixin
from advene.model.cam.exceptions import SemanticError
from advene.model.cam.group import CamGroupMixin
from advene.model.core.relation import Relation as CoreRelation
from advene.model.core.element import TAG

class Relation(CamGroupMixin, CoreRelation, CamElementMixin):
    def __iter__(self):
        # necessary to override CamGroupMixin __iter__
        return CoreRelation.__iter__(self)

    def set_meta(self, key, value, val_is_idref=False, _guard=True):
        if key == CAM_TYPE:
            advene_type = getattr(value, "ADVENE_TYPE", None)
            if advene_type:
                if advene_type is not TAG \
                or value.get_meta(CAMSYS_TYPE, None) != "relation-type":
                    raise SemanticError("not an relation type")
            else:
                if not val_is_idref:
                    raise SemanticError("not an relation type")

            old_type = self.get_meta(key, None)
            owner = self._owner
            if old_type:
                old_type = owner.get(old_type, old_type) # get element if we can
                owner.dissociate_tag(self, old_type, _guard=False)
            owner.associate_tag(self, value, _guard=False)

        return super(Relation, self).set_meta(key, value, val_is_idref, _guard)

    def del_meta(self, key, _guard=True):
        if key == CAM_TYPE:
            # TODO raise a user-warning, this is not good practice
            old_type = self.get_meta(key, None)
            if old_type:
                self._owner.dissociate_tag(self, old_type, _guard=False)
        return super(Relation, self).del_meta(key, _guard)

Relation.make_metadata_property(CAM_TYPE, "type", default=None, doc="""
The type of this relation, created with Package.create_relation_type.
""")
