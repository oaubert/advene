from advene.model.cam.consts import CAM_NS_PREFIX
from advene.model.cam.element import CamElement
from advene.model.consts import DC_NS_PREFIX
from advene.model.core.media import Media as CoreMedia

class Media(CoreMedia, CamElement):
    pass

Media.make_metadata_property(DC_NS_PREFIX + "extent", "duration", default=None)
Media.make_metadata_property(CAM_NS_PREFIX + "uri", default=None)
