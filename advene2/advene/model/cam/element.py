from advene.model.consts import DC_NS_PREFIX, RDFS_NS_PREFIX
from advene.model.cam.consts import CAM_TYPE, CAMSYS_TYPE
from advene.model.cam.exceptions import SemanticError, UnsafeUseWarning
from advene.model.core.element import PackageElement, ElementCollection
from advene.model.tales import tales_property, tales_use_as_context

from warnings import warn

class CamElementMixin(PackageElement):
    """
    This mixin class implement the behaviour specific to the Cinelab
    Application Model.
    It must necessarily be mixed in a subclass of PackageElement. To ensure
    correct MRO, it explicitly inherit PackageElement, but it is indeed a mixin
    class (having no implication in instance creation).
    """

    def set_meta(self, key, value, val_is_idref=False):
        if key == CAMSYS_TYPE:
            raise SemanticError("cam:system-type can not be modified")
        return super(CamElementMixin, self).set_meta(key, value, val_is_idref)

    def _set_camsys_type(self, value, val_is_idref=False):
        return super(CamElementMixin, self) \
                .set_meta(CAMSYS_TYPE, value, val_is_idref)

    def del_meta(self, key):
        if key == CAMSYS_TYPE:
            raise SemanticError("cam:system-type can not be modified")
        return super(CamElementMixin, self).del_meta(key)

    def iter_my_tags(self, package=None, inherited=True):
        """
        This method is inherited from core.Package but is unsafe on
        cam.Package. Use instead `iter_my_user_tags`.
        """
        warn("use iter_my_user_tags instead", UnsafeUseWarning, 2)
        return super(CamElementMixin, self).iter_my_tags(package, inherited)

    def _iter_my_tags_nowarn(self, package=None, inherited=True):
        """
        Allows to call iter_my_tags internally without raising a warning.
        """
        return super(CamElementMixin, self).iter_my_tags(package, inherited)

    def iter_my_user_tags(self, package=None, inherited=True):
        for t in super(CamElementMixin, self).iter_my_tags(package, inherited):
            if t.get_meta(CAMSYS_TYPE, None) is None:
                yield t

    def iter_my_tag_ids(self, package=None, inherited=True):
        """
        This method is inherited from core.Package but is unsafe on
        cam.Package. Use instead `iter_my_user_tag_ids`.
        """
        warn("use iter_my_user_tag_ids instead", UnsafeUseWarning, 2)
        return super(CamElementMixin, self).iter_my_tag_ids(package, inherited)

    def _iter_my_tag_ids_nowarn(self, package=None, inherited=True):
        """
        Allows to call iter_my_tag_ids internally without raising a warning.
        """
        return super(CamElementMixin, self).iter_my_tag_ids(package, inherited)

    def iter_my_user_tag_ids(self, package=None, inherited=True):
        """
        FIXME: missing docstring
        """
        # NB: the following is not general: it assumes that the only
        # non-user tag is the cam:type.
        # It has been chosen because it is very efficient, not requiring to
        # check tags metadata cam:system-type to decide that they are
        # user-tags.
        type = self.get_meta(CAM_TYPE, None)
        all = super(CamElementMixin, self).iter_my_tag_ids(package, inherited)
        if type is None:
            return all
        else:
            type_id = type.make_id_in(package)
            return ( i for i in all if i != type_id )

    @tales_property
    @tales_use_as_context("refpkg")
    def _tales_my_tags(self, context_package):
        """
        Iter over all the user-tags of this element in the context of the
        reference package.

        NB: This TAL function is overridden with a quite different semantics
        from the inherited version (only user-tags are iterated, instead of
        all tags). Since TAL is mostly user-oriented, this semantic shift is
        not considered harmful.
        """
        class TagCollection(ElementCollection):
            __iter__ = lambda s: self.iter_my_user_tags(context_package)
        return TagCollection(self._owner)


_make_meta = CamElementMixin.make_metadata_property

_make_meta(DC_NS_PREFIX + "creator", default="")
_make_meta(DC_NS_PREFIX + "contributor", default="")
_make_meta(DC_NS_PREFIX + "created", default="")
_make_meta(DC_NS_PREFIX + "modified", default="")

_make_meta(DC_NS_PREFIX + "title", default="")
_make_meta(DC_NS_PREFIX + "description", default="")

_make_meta(RDFS_NS_PREFIX + "seeAlso", default=None)

