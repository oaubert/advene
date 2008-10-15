"""
I define the class Tag.
"""

from advene.model.consts import _RAISE
from advene.model.core.element import PackageElement, TAG

class Tag(PackageElement):

    ADVENE_TYPE = TAG 

    def __init__(self, owner, id):
        PackageElement.__init__(self, owner, id)

    def iter_elements(self, package, inherited=True, yield_idrefs=False):
        """Iter over the elements associated with this tag in ``package``.

        If ``inherited`` is set to False, the elements associated by imported
        packages of ``package`` will not be yielded.

        If an element is unreachable, an exception will be raised at the time
        it must be yielded, unless yield_idrefs is set to True, in which case
        the id-ref of the element is yielded instead.

        See also `iter_elements_idrefs`.
        """
        return self.iter_elements_idrefs(package, inherited,
                                         yield_idrefs and 1 or 2)

    def iter_elements_idrefs(self, package, inherited=True, _try_get=0):
        """Iter over the id-refs of the elements associated with this tag in
        ``package``.

        If ``inherited`` is set to False, the elements associated by imported
        packages of ``package`` will not be yielded.

        See also `iter_elements`.
        """
        # this actually also implements iter_elements
        if _try_get == 1: # yield_idrefs is true
            default = None
        else: # yield_idrefs is false
            default = _RAISE
        u = self._get_uriref()
        if not inherited:
            pids = (package._id,)
            get_element = package.get_element
            for pid, eid in package._backend.iter_elements_with_tag(pids, u):
                if _try_get:
                    y = package.get_element(eid, default)
                    if y is None: # only possible when yield_idrefs is true
                        y = eid
                else:
                    y = eid
                yield y
        else:
            for be, pdict in package._backends_dict.iteritems():
                for pid, eid in be.iter_elements_with_tag(pdict, u):
                    p = pdict[pid]
                    if _try_get:
                        y = p.get_element(eid, default)
                        if y is None: # only possible when yield_idrefs is true
                            y = package.make_idref_for(p, eid)
                    else:
                        y = package.make_idref_for(p, eid)
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
 
