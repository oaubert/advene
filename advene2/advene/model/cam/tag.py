from advene.model.cam.consts import CAMSYS_TYPE, CAM_NS_PREFIX
from advene.model.cam.element import CamElement
from advene.model.core.tag import Tag as CoreTag

class Tag(CoreTag, CamElement):
    def set_meta(self, key, value, val_is_idref=False, _guard=True):
        # transtype Tag when CAMSYS_TYPE is updated
        if key == CAMSYS_TYPE:
            if value == "annotation-type":
                newtype = AnnotationType
            elif value == "relation-type":
                newtype = RelationType
            else:
                newtype = Tag
            if self.__class__ is not newtype:
                self.__class__ = newtype
        return super(Tag, self).set_meta(key, value, val_is_idref, _guard)

class AnnotationType(Tag):
    """
    The class of annotation types.
    """
    # This class is automatically transtyped from Tag (and back) when 
    # CAMSYS_TYPE is changed. See Tag.set_meta
    pass

class RelationType(Tag):
    """
    The class of annotation types.
    """
    # This class is automatically transtyped from Tag (and back) when 
    # CAMSYS_TYPE is changed. See Tag.set_meta
    pass

Tag.make_metadata_property(CAMSYS_TYPE, "system_type", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "representation", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "color", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "element-color", default=None)
