"""
I define the class of annotations.
"""

from PackageElement    import PackageElement, ANNOTATION
from WithContentMixin  import WithContentMixin

class Annotation (PackageElement, WithContentMixin):

    ADVENE_TYPE = ANNOTATION

    def __init__ (self, owner, id, stream_id, begin, end):
        PackageElement.__init__ (self, owner, id)
        self._stream_id = stream_id
        self._begin     = begin
        self._end       = end

    def __cmp__ (self, other):
        return self._begin - other._begin \
            or self._end - other._end \
            or cmp (self._stream_id, other._stream_id)
