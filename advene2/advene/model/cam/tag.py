from advene.model.cam.consts import CAMSYS_TYPE, CAM_NS_PREFIX
from advene.model.cam.element import CamElementMixin
from advene.model.core.tag import Tag as CoreTag

class Tag(CoreTag, CamElementMixin):

    @classmethod
    def instantiate(cls, owner, id):
        r = super(Tag, cls).instantiate(owner, id)
        r._transtype()
        return r

    def set_meta(self, key, value, val_is_idref=False, _guard=True):
        if key == CAMSYS_TYPE:
            self._transtype(value)
        return super(Tag, self).set_meta(key, value, val_is_idref, _guard)

    def _transtype(self, systype=None):
        """
        Transtypes this Tag to the appropriate subclass according to the given
        systype (assumed to be the current or future systype).

        If systype is omitted, it is retrieved from the metadata.
        """
        if systype is None:
            systype = self.get_meta(CAMSYS_TYPE, None)
        if systype == "annotation-type":
            newtype = AnnotationType
        elif systype == "relation-type":
            newtype = RelationType
        else:
            newtype = Tag
        if self.__class__ is not newtype:
            self.__class__ = newtype



class AnnotationType(Tag):
    """
    The class of annotation types.
    """
    # This class is automatically transtyped from Tag (and back) when
    # CAMSYS_TYPE is modified. See Tag.set_meta
    pass

class RelationType(Tag):
    """
    The class of annotation types.
    """
    # This class is automatically transtyped from Tag (and back) when
    # CAMSYS_TYPE is modified. See Tag.set_meta
    pass

Tag.make_metadata_property(CAMSYS_TYPE, "system_type", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "representation", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "color", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "element-color",
                           "element_color", default=None)
Tag.make_metadata_property(CAM_NS_PREFIX + "element-constraint",
                           "element_constraint", default=None)
