from advene.model.consts import DC_NS_PREFIX, RDFS_NS_PREFIX
from advene.model.cam.consts import CAM_TYPE, CAMSYS_TYPE
from advene.model.cam.exceptions import SemanticError, UnsafeUseWarning
from advene.model.core.element import PackageElement
from advene.model.tales import tales_context_function

from datetime import datetime
from warnings import warn

class CamElement(PackageElement):
    def _initialize(self):
        now = datetime.now().isoformat()
        self.created = now
        self.modified = now

    def set_meta(self, key, value, val_is_idref=False, _guard=True):
        if _guard:
            if key == CAMSYS_TYPE:
                raise SemanticError("cam:system-type can not be changed")
        return super(CamElement, self).set_meta(key, value, val_is_idref)

    def del_meta(self, key, _guard=True):
        if _guard:
            if key == CAMSYS_TYPE:
                raise SemanticError("cam:system-type can not be changed")
        return super(CamElement, self).del_meta(key)

    def iter_my_tags(self, package=None, inherited=True, _guard=True):
        """
        This method is inherited from core.Package but is unsafe on
        cam.Package. Use instead `iter_my_user_tags`.
        """
        if _guard: warn("use iter_my_user_tags instead", UnsafeUseWarning, 2)
        return super(CamElement, self).iter_my_tags(package, inherited)

    def iter_my_user_tags(self, package=None, inherited=True):
        for t in self.iter_my_tags(package, inherited, _guard=False):
            if t.get_meta(CAMSYS_TYPE, None) is None:
                yield t

    def iter_my_tag_ids(self, package=None, inherited=True, _guard=True):
        """
        This method is inherited from core.Package but is unsafe on
        cam.Package. Use instead `iter_my_user_tag_ids`.
        """
        if _guard: warn("use iter_my_user_tag_ids instead", UnsafeUseWarning, 2)
        return super(CamElement, self).iter_my_tag_ids(package, inherited)

    def iter_my_user_tag_ids(self, package=None, inherited=True, _guard=True):
        """
        FIXME: missing docstring
        """
        # NB: the following is not general: it assumes that the only
        # non-user tag is the cam:type.
        # It has been chosen because it is very efficient, not requiring to
        # check tags metadata cam:system-type to decide that they are
        # user-tags.
        type = self.get_meta(CAM_TYPE, None)
        all = super(CamElement, self).iter_my_tag_ids(package, inherited)
        if type is None:
            return all
        else:
            type_id = type.make_id_in(package)
            return ( i for i in all if i != type_id )

    @tales_context_function
    def _tales_my_tags(self, context):
        """
        Iter over all the user-tags of this element in the context of the
        reference package.

        NB: This TAL function is overridden with a quite different semantics
        from the inherited version (only user-tags are iterated, instead of
        all tags). Since TAL is mostly user-oriented, this semantic shift is
        not considered harmful.
        """
        refpkg = context.globals["refpkg"]
        return self.iter_my_user_tags(refpkg)


CamElement.make_metadata_property(DC_NS_PREFIX + "creator", default="")
CamElement.make_metadata_property(DC_NS_PREFIX + "contributor", default="")
CamElement.make_metadata_property(DC_NS_PREFIX + "created", default=None)
CamElement.make_metadata_property(DC_NS_PREFIX + "modified", default=None)

CamElement.make_metadata_property(DC_NS_PREFIX + "title", default=None)
CamElement.make_metadata_property(DC_NS_PREFIX + "description", default=None)

CamElement.make_metadata_property(RDFS_NS_PREFIX + "seeAlso", default=None)

