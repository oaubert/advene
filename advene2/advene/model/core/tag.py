"""
I define the class Tag.

Note that Tag inherits GroupMixin, but can only be considered a group in the
context of a package in which tag-element associations are considered. That
implicit context-package is given by the ``package`` session variable in
`advene.util.session`. If that session variable is not set, using a tag as
a group will raise a TypeError.
"""

from advene.model.core.element import PackageElement, TAG
from advene.model.core.group import GroupMixin
from advene.util.alias import alias
from advene.util.session import session

class Tag(PackageElement, GroupMixin):

    ADVENE_TYPE = TAG 

    def __init__(self, owner, id, *a):
        super(Tag, self).__init__(owner, id, *a)

    @classmethod
    def create_new(cls, owner, id):
        owner._backend.create_tag(owner._id, id)
        return cls.instantiate(owner, id)

    def __iter__(self):
        # required by GroupMixin
        return self.iter_elements()

    def iter_elements(self, package=None, inherited=True):
        """Iter over the elements associated with this tag in ``package``.

        If ``inherited`` is set to False, the elements associated by imported
        packages of ``package`` will not be yielded.

        If an element is unreachable, None is yielded.

        See also `iter_element_ids`.
        """
        return self._iter_elements_or_element_ids(package, inherited, True)

    def iter_element_ids(self, package=None, inherited=True, _get=False):
        """Iter over the id-refs of the elements associated with this tag in
        ``package``.

        If ``package`` is not provided, the ``package`` session variable is
        used. If the latter is unset, a TypeError is raised.

        If ``inherited`` is set to False, the elements associated by imported
        packages of ``package`` will not be yielded.

        See also `iter_elements`.
        """
        # this actually also implements iter_elements
        if package is None:
            package = session.package
        if package is None:
            raise TypeError("no package set in session, must be specified")
        u = self._get_uriref()
        if not inherited:
            pids = (package._id,)
            get_element = package.get_element
            for pid, eid in package._backend.iter_elements_with_tag(pids, u):
                if _get:
                    y = package.get_element(eid, None)
                else:
                    y = eid
                yield y
        else:
            for be, pdict in package._backends_dict.iteritems():
                for pid, eid in be.iter_elements_with_tag(pdict, u):
                    p = pdict[pid]
                    if _get:
                        y = p.get_element(eid, None)
                    else:
                        y = package.make_id_for(p, eid)
                    yield y

    @alias(iter_element_ids)
    def _iter_elements_or_element_ids(self):
        # iter_element_ids and iter_elements have a common implementation.
        # Normally, it should be located in a "private" method named
        # _iter_elements_or_element_ids.
        # However, for efficiency reasons, that private method and
        # iter_element_ids have been merged into one. Both names are necessary
        # because the "public" iter_elements_ids may be overridden while the
        # "private" method should not. Hence that alias.
        pass

    def has_element(self, element, package=None, inherited=True):
        """Is this tag associated to ``element`` by ``package``.

        If ``package`` is not provided, the ``package`` session variable is
        used. If the latter is unset, a TypeError is raised.

        If ``inherited`` is set to False, only returns True if ``package`` 
        itself associates this tag to ``element``; else returns True also if
        the association is inherited from an imported package.
        """
        if not inherited:
            return element.has_tag(self, package, False)
        else:
            return list(element.iter_taggers(self, package))

    def __wrap_with_tales_context__(self, context):
        """
        This method is used by adveve.model.tales, when the TALES processor
        wants to traverse the given object.
        """
        return ContextualizedTag(self, context)


class ContextualizedTag(GroupMixin, object):
    def __init__(self, tag, context):
        self._t = tag
        self._p = context.locals.get("refpkg") or context.globals.get("refpkg")

    def __iter__(self):
        return self._t.iter_elements(package=self._p)

    def __getattr__(self, name):
        if name[0] != "_" or name.startswith("_tales_"):
            return getattr(self._t, name)
        else:
            raise AttributeError(name)

    def __repr__(self):
        return repr(self._t) + "#contextualized#"
