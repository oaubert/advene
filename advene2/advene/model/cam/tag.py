from advene.model.cam.consts import CAMSYS_TYPE, CAM_NS_PREFIX
from advene.model.cam.element import CamElementMixin
from advene.model.consts import _RAISE
from advene.model.core.tag import Tag as CoreTag
from advene.util.autoproperty import autoproperty

CAM_ELEMENT_CONSTRAINT = CAM_NS_PREFIX + "element-constraint"

class Tag(CoreTag, CamElementMixin):

    @classmethod
    def instantiate(cls, owner, id, *args):
        r = super(Tag, cls).instantiate(owner, id, *args)
        r._transtype()
        return r

    def _set_camsys_type(self, value, val_is_idref=False):
        super(Tag, self)._set_camsys_type(value, val_is_idref)
        self._transtype(value)

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
        # NB: the following is now delayed to the first get_meta
        #if newtype in (AnnotationType, RelationType):
        #    if self.element_constraint is None:
        #        c = self._owner.create_view(
        #                ":constraint:%s" % self._id,
        #                "application/x-advene-type-constraint",
        #        )
        #        self.element_constraint = c
        self.__class__ = newtype


class WithTypeConstraintMixin(object):
    """
    Implement shortcut attributes to the underlying type-constraint.
    """

    def _make_constraint(self):
        c = self._owner.create_view(
                ":constraint:%s" % self._id,
                "application/x-advene-type-constraint",
        )
        super(WithTypeConstraintMixin, self) \
                .set_meta(CAM_ELEMENT_CONSTRAINT, c)
        return c

    def get_meta(self, key, default=_RAISE):
        if key == CAM_ELEMENT_CONSTRAINT:
            r = super(WithTypeConstraintMixin, self).get_meta(key, None) \
                or self._make_constraint()
        else:
            r = super(WithTypeConstraintMixin, self).get_meta(key, default)
        return r

    def get_meta_id(self, key, default=_RAISE):
        if key == CAM_ELEMENT_CONSTRAINT:
            r = super(WithTypeConstraintMixin, self).get_meta_id(key, None) \
                or self._make_constraint().id
        else:
            r = super(WithTypeConstraintMixin, self).get_meta_id(key, default)
        return r

    def set_meta(self, key, value, val_is_idref=False):
        if key == CAM_ELEMENT_CONSTRAINT:
            # do not _make_constraint, since this could be the parser setting it
            expected_id = ":constraint:" + self._id
            if val_is_idref:
                got_id = value
                got = self._owner.get(value, None)
            else:
                got_id = getattr(value, "_id", None)
                got = value
            if got_id != expected_id \
            or got is None \
            or got.content_mimetype != "application/x-advene-type-constraint":
                raise TypeError, "element-constraint can not be changed"

        super(WithTypeConstraintMixin, self).set_meta(key, value, val_is_idref)

    def check_element(self, e):
        """
        Applies the element_constraint to the given element and returns the
        result.
        """
        return self.element_constraint.apply_to(e)

    def check_all(self, package=None):
        """
        Applies the element_constraint to all the elements in the given
        package (session.package) if None, and return the aggregated result.
        """
        check = self.element_constraint.apply_to
        r = True
        for e in self.iter_elements(package):
            r = r & check(e)
        return r

    @autoproperty
    def _get_mimetype(self):
        return self.element_constraint.content_parsed.get("mimetype", None) or "*/*"

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
Tag.make_metadata_property(CAM_ELEMENT_CONSTRAINT,
                           "element_constraint", default=None)
