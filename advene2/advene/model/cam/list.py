from advene.model.cam.consts import CAMSYS_TYPE
from advene.model.cam.element import CamElement
from advene.model.cam.group import CamGroupMixin
from advene.model.core.list import List as CoreList

class List(CamGroupMixin, CoreList, CamElement) :
    def __iter__(self):
        # necessary to override CamGroupMixin __iter__
        return CoreList.__iter__(self)

    def set_meta(self, key, value, val_is_idref=False, _guard=True):
        # transtype List when CAMSYS_TYPE is updated
        if key == CAMSYS_TYPE:
            if value == "schema":
                newtype = Schema
            else:
                newtype = List
            if self.__class__ is not newtype:
                self.__class__ = newtype
        return super(List, self).set_meta(key, value, val_is_idref, _guard)

List.make_metadata_property(CAMSYS_TYPE, "system_type", default=None)

class Schema(List):
    """
    The class of annotation types.
    """
    # This class is automatically transtyped from List (and back) when 
    # CAMSYS_TYPE is changed. See List.set_meta
    pass
