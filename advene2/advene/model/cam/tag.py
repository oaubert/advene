from advene.model.cam.consts import CAMSYS_TYPE, CAM_NS_PREFIX
from advene.model.cam.element import CamElementMixin
from advene.model.cam.group import CamGroupMixin
from advene.model.core.element import LIST, ElementCollection
from advene.model.core.tag import Tag as CoreTag
from advene.model.tales import tales_property, tales_use_as_context
from advene.util.alias import alias
from advene.util.autoproperty import autoproperty
from advene.util.session import session


CAM_ELEMENT_CONSTRAINT = CAM_NS_PREFIX + "element-constraint"

class Tag(CoreTag, CamElementMixin, CamGroupMixin):

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
        if self.__class__ is not newtype:
            self.__class__ = newtype


class CamTypeMixin(object):
    """
    Implement features common to annotation and relation types.

    That includes shortcut attributes to the underlying type-constraint,
    and access to the schemas containing the type.
    """

    # constraint related

    def set_meta(self, key, value, val_is_idref=False):
        if key == CAM_ELEMENT_CONSTRAINT:
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
                raise TypeError("element-constraint can not be changed")

        super(CamTypeMixin, self).set_meta(key, value, val_is_idref)

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

    # schema related

    def iter_my_schemas(self, package=None, inherited=True):
        if package is None:
            package = session.package
        if package is None:
            raise TypeError("no package set in session, must be specified")
        if inherited:
            g = package.all
        else:
            g = package.own
        return g.iter_schemas(item=self)

    def count_my_schemas(self, package=None, inherited=True):
        if package is None:
            package = session.package
        if package is None:
            raise TypeError("no package set in session, must be specified")
        if inherited:
            g = package.all
        else:
            g = package.own
        u = self._get_uriref()
        return g.count_schemas(item=u)

    @autoproperty
    def _get_my_schemas(type_, package=None):
        """
        Return an ElementCollection of all the schemas containing this type.

        In python, property `my_schemas` uses ``session.package``.
        In TALES, property `my_schemas` uses ``package``.
        """
        if package is None:
            package = session.package
            if package is None:
                raise TypeError("no package set in session, must be specified")
        class TypeSchemas(ElementCollection):
            def __iter__(self):
                return type_.iter_my_schemas(package)
            def __len__(self):
                return type_.count_my_schemas(package)
            def __contains__(self, s):
                return getattr(s, "ADVENE_TYPE", None) == LIST \
                   and s.get_meta(CAMSYS_TYPE, None) == "schema" \
                   and type_ in s
        return TypeSchemas(package)

    @tales_property
    @tales_use_as_context("package")
    @alias(_get_my_schemas)
    def _tales_my_schemas(self, context):
        # recycle _get_my_schemas implementation
        pass


class AnnotationType(CamTypeMixin, Tag):
    """
    The class of annotation types.
    """
    # This class is automatically transtyped from Tag (and back) when
    # CAMSYS_TYPE is modified. See Tag.set_meta
    pass

class RelationType(CamTypeMixin, Tag):
    """
    The class of relation types.
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
