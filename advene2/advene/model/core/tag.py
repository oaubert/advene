"""
I define the class Tag.
"""

from advene.model.core.element import PackageElement, TAG

class Tag(PackageElement):

    ADVENE_TYPE = TAG 

    def __init__(self, owner, id):
        PackageElement.__init__(self, owner, id)

    def iter_elements(self, package, inherited=True):
        """Iter over the elements associated with this tag in ``package``.

        If ``inherited`` is set to False, the elements associated by imported
        packages of ``package`` will not be yielded.

        If an element is unreachable, None is yielded.

        See also `iter_element_ids`.
        """
        return self.iter_element_ids(package, inherited, True)

    def iter_element_ids(self, package, inherited=True, _get=False):
        """Iter over the id-refs of the elements associated with this tag in
        ``package``.

        If ``inherited`` is set to False, the elements associated by imported
        packages of ``package`` will not be yielded.

        See also `iter_elements`.
        """
        # this actually also implements iter_elements
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

    def has_element(self, element, package, inherited=True):
        """Is this tag associated to ``element`` by ``package``.

        If ``inherited`` is set to False, only returns True if ``package`` 
        itself associates this tag to ``element``; else returns True also if
        the association is inherited from an imported package.
        """
        if not inherited:
            return element.has_tag(self, package, False)
        else:
            return list(element.iter_taggers(self, package))
 
