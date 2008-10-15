"""
I define the class of annotations.
"""

from PackageElement    import PackageElement, ANNOTATION
from WithContentMixin  import WithContentMixin

class Annotation (PackageElement, WithContentMixin):

    ADVENE_TYPE = ANNOTATION

    def __init__ (self, owner, id, media_id, begin, end):
        PackageElement.__init__ (self, owner, id)
        self._media_id = media_id
        self._begin    = begin
        self._end      = end

    def __cmp__ (self, other):
        return self._begin - other._begin \
            or self._end - other._end \
            or cmp (self._media_id, other._media_id)
