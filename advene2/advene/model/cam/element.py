from advene.model.consts import DC_NS_PREFIX, RDFS_NS_PREFIX
from advene.model.cam.consts import CAMSYS_NS_PREFIX
from advene.model.cam.exceptions import SemanticError
from advene.model.core.element import PackageElement

from warnings import warn

_cam_system_type = CAMSYS_NS_PREFIX + "type"

class CamElement(PackageElement):
    def set_meta(self, key, value, _guard=True):
        if _guard:
            if key == _cam_system_type:
                raise SemanticError("cam:system-type can not be changed")
        return super(CamElement, self).set_meta(key, value)

    def del_meta(self, key, _guard=True):
        if _guard:
            if key == _cam_system_type:
                raise SemanticError("cam:system-type can not be changed")
        return super(CamElement, self).del_meta(key)

    def iter_tags(self, package, inherited=True, _guard=True):
        """
        This method is inherited from core.Package but is unsafe on
        cam.Package. Use instead `iter_simple_tags`.
        """
        if _guard: warn("use iter_simple_tags instead", UnsafeUseWarning, 2)
        super(Package, self).associate_tag(element, tag)

    def iter_simple_tags(self, package, inherited=True):
        for t in self._iter_tags(package, inherited, _guard=False):
            if t.get_meta(_cam_system_type, None) is None:
                yield t

CamElement.make_metadata_property(DC_NS_PREFIX + "creator", "dc_creator")
CamElement.make_metadata_property(DC_NS_PREFIX + "description", 
                                  "dc_description")
CamElement.make_metadata_property(RDFS_NS_PREFIX + "seeAlso", "rdfs_seeAlso")
# TODO more
