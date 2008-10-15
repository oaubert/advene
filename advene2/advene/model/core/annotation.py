"""
I define the class of annotations.
"""

from weakref import ref

from advene import _RAISE
from advene.model.core.element import PackageElement, ANNOTATION, MEDIA
from advene.model.core.content import WithContentMixin

class Annotation(PackageElement, WithContentMixin):

    ADVENE_TYPE = ANNOTATION

    def __init__(self, owner, id, media, begin, end):
        PackageElement.__init__(self, owner, id)
        if not hasattr(media, "ADVENE_TYPE"):
            # internally, we sometimes pass backend data directly,
            # where media is an id-ref rather than a Media instance
            media = owner.get_element(media)
        self._set_media(media, _init=True)
        self._begin = begin
        self._end   = end

    def __str__(self):
        return "Annotation(%s,%s,%s)" % \
               (self._media_idref, self._begin, self._end)

    def __cmp__(self, other):
        return self._begin - other._begin \
            or self._end - other._end \
            or cmp(self._media_idref, other._media_idref)

    def _get_media(self, default=_RAISE):
        m = self._media_wref()
        if m is None:
            m = self._owner.get_element(self.media_idref, default)
            if m is not default:
                self._media_wref = ref(m)
        return m

    def _set_media(self, media, _init=False):
        o = self._owner

        assert media.ADVENE_TYPE == MEDIA
        assert o._can_reference(media)

        midref = media.make_idref_for(o)
        self._media_idref = midref
        self._media_wref  = ref(media)
        if not _init:
            self.add_cleaning_operation_once(self.__clean)

    def _get_begin(self):
        return self._begin

    def _set_begin(self, val):
        self._begin = val
        self.add_cleaning_operation_once(self.__clean)

    def _get_end(self):
        return self._end

    def _set_end(self, val):
        self._end = val
        self.add_cleaning_operation_once(self.__clean)

    def __clean(self):
        o = self._owner
        o._backend.update_annotation(o._id, self._id,
                                     self._media_idref, self._begin, self._end)
