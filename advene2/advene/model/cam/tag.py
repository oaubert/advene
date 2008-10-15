from advene.model.cam.consts import CAM_NS_PREFIX
from advene.model.cam.element import CamElement
from advene.model.core.tag import Tag as CoreTag

class Tag(CoreTag, CamElement):
    # TODO synchronize metadata cam:type with meta-tag tagging
    pass

Tag.make_metadata_property(CAM_NS_PREFIX + "type", "type")
