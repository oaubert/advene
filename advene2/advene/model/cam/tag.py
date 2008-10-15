from advene.model.cam.consts import CAMSYS_TYPE, CAM_NS_PREFIX
from advene.model.cam.element import CamElement
from advene.model.core.tag import Tag as CoreTag

class Tag(CoreTag, CamElement):
    # TODO synchronize metadata cam:type with meta-tag tagging
    pass

Tag.make_metadata_property(CAMSYS_TYPE, "system_type")
Tag.make_metadata_property(CAM_NS_PREFIX + "representation", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "color", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "element-color", default=None)
