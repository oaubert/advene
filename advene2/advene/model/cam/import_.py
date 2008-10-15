from advene.model.cam.group import CamGroupMixin
from advene.model.cam.element import CamElementMixin
from advene.model.core.import_ import Import as CoreImport

class Import(CoreImport, CamElementMixin, CamGroupMixin):
    pass

    # TODO when renaming is implemented: prevent "cam" from being renamed


