from advene.model.cam.consts import CAM_NS_PREFIX, CAMSYS_NS_PREFIX
from advene.model.cam.element import CamElement
from advene.model.cam.exceptions import SemanticError
from advene.model.cam.group import CamGroupMixin
from advene.model.core.relation import Relation as CoreRelation
from advene.model.core.element import TAG

_cam_type = CAM_NS_PREFIX + "type"
_cam_system_type = CAMSYS_NS_PREFIX + "type"

class Relation(CamGroupMixin, CoreRelation, CamElement):
    def __iter__(self):
        # necessary to override CamGroupMixin __iter__
        return CoreList.__iter__(self)

    def set_meta(self, key, value, _guard=True):
        if key == _cam_type:
            if getattr(value, "ADVENE_TYPE", None) is not TAG \
            and value.get_meta(_cam_system_type, None) != "relation-type":
                raise SemanticError("not a relation type")
            old_type = self.get_meta(key, None)
            owner = self._owner
            if old_type:
                owner.dissociate_tag(self, old_type, _guard=False)
            owner.associate_tag(self, value, _guard=False)
        return super(Relation, self).set_meta(key, value, _guard)

    def del_meta(self, key, _guard=True):
        if key == _cam_type:
            # TODO raise a user-warning, this is not good practice
            old_type = self.get_meta(key, None)
            if old_type:
                self._owner.dissociate_tag(self, old_type, _guard=False)
        return super(Annotation, self).del_meta(key, _guard)

Relation.make_metadata_property(_cam_type, "type", default=None)
