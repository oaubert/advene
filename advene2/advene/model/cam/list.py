from advene.model.cam.consts import CAMSYS_TYPE
from advene.model.cam.element import CamElement
from advene.model.cam.group import CamGroupMixin
from advene.model.core.list import List as CoreList

class List(CamGroupMixin, CoreList, CamElement) :
    def __iter__(self):
        # necessary to override CamGroupMixin __iter__
        return CoreList.__iter__(self)

List.make_metadata_property(CAMSYS_TYPE, "system_type")
