from advene.model.cam.element import CamElement
from advene.model.cam.group import CamGroupMixin
from advene.model.core.list import List as CoreList

class List(CamGroupMixin, CoreList, CamElement) :
    pass
