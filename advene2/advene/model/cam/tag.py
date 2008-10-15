from advene.model.cam.consts import CAMSYS_TYPE, CAM_NS_PREFIX
from advene.model.cam.element import CamElementMixin
from advene.model.core.tag import Tag as CoreTag
from advene.util.autoproperty import autoproperty

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
        if self.__class__ is newtype:
            return
        if newtype in (AnnotationType, RelationType):
            if self.element_constraint is None:
                c = self._owner.create_view(
                        ":constraint:%s" % self._id,
                        "application/x-advene-type-constraint",
                )
                self.element_constraint = c
        self.__class__ = newtype


class WithTypeConstraintMixin(object):
    """
    Implement shortcut attributes to the underlying type-constraint.
    """

    def set_meta(self, key, value, val_is_idref=False, _guard=True):
        if key == CAM_NS_PREFIX + "element-constraint":
             raise TypeError, "element-constraint can not be changed"

    @autoproperty
    def _get_mimetype(self):
        return self.element_constraint.content_parsed["mimetype"]

    @autoproperty
    def _set_mimetype(self, mimetype):
        c = self.element_constraint
        p = c.content_parsed
        p["mimetype"] = mimetype
        c.content_parsed = p

class AnnotationType(WithTypeConstraintMixin, Tag):
    """
    The class of annotation types.
    """
    # This class is automatically transtyped from Tag (and back) when
    # CAMSYS_TYPE is modified. See Tag.set_meta
    pass

class RelationType(WithTypeConstraintMixin, Tag):
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
