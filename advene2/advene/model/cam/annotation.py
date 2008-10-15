from advene.model.cam.consts import CAM_TYPE, CAMSYS_TYPE
from advene.model.cam.element import CamElementMixin
from advene.model.cam.exceptions import SemanticError
from advene.model.core.annotation import Annotation as CoreAnnotation
from advene.model.core.element import TAG

class Annotation(CoreAnnotation, CamElementMixin):

    def set_meta(self, key, value, val_is_idref=False):
        if key == CAM_TYPE:
            advene_type = getattr(value, "ADVENE_TYPE", None)
            if advene_type:
                if advene_type is not TAG \
                or value.get_meta(CAMSYS_TYPE, None) != "annotation-type":
                    raise SemanticError("not an annotation type")
            else:
                if not val_is_idref:
                    raise SemanticError("not an annotation type")

            old_type = self.get_meta_id(key, None)
            owner = self._owner
            if old_type:
                old_type = owner.get(old_type, old_type) # get element if we can
                owner._dissociate_tag_nowarn(self, old_type)
            owner._associate_tag_nowarn(self, value)

        return super(Annotation, self).set_meta(key, value, val_is_idref)

    def del_meta(self, key):
        if key == CAM_TYPE:
            # TODO raise a user-warning, this is not good practice
            old_type = self.get_meta(key, None)
            if old_type:
                self._owner._dissociate_tag_nowarn(self, old_type)
        return super(Annotation, self).del_meta(key)

Annotation.make_metadata_property(CAM_TYPE, "type", default=None, doc="""
The type of this annotation, created with Package.create_annotation_type(). May be None if undefined.
""")
