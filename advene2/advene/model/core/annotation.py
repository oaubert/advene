"""
I define the class of annotations.
"""

from advene import _RAISE
from advene.model.core.element import PackageElement, ANNOTATION, MEDIA
from advene.model.core.content import WithContentMixin
from advene.utils.autoproperty import autoproperty

class Annotation(PackageElement, WithContentMixin):

    ADVENE_TYPE = ANNOTATION

    def __init__(self, owner, id, media, begin, end, mimetype, schema, url):
        PackageElement.__init__(self, owner, id)
        if not hasattr(media, "ADVENE_TYPE"):
            # internally, we sometimes pass backend data directly,
            # where media is an id-ref rather than a Media instance
            self._media_idref = media
            self._media = None
        else:
            self._set_media(media, _init=True)
        self._begin = begin
        self._end   = end
        self._set_content_mimetype(mimetype, _init=True)
        if schema:
            if not hasattr(schema, "ADVENE_TYPE"):
                # internally, we may sometimes pass backend data directly,
                # where schema is an id-ref rather than a Media instance
                schema = owner.get_element(schema)
        else:
            schema = None # could be an empty string
        self._set_content_schema(schema, _init=True)
        self._set_content_url(url, _init=True)

    def __str__(self):
        return "Annotation(%s,%s,%s)" % \
               (self._media_idref, self._begin, self._end)

    def __cmp__(self, other):
        return self._begin - other._begin \
            or self._end - other._end \
            or cmp(self._media_idref, other._media_idref)

    @autoproperty
    def _get_media(self, default=_RAISE):
        r = self._media
        if r is None:
            r = self._media = \
                self._owner.get_element(self._media_idref, default)
        return r

    @autoproperty
    def _set_media(self, media, _init=False):
        o = self._owner

        assert media.ADVENE_TYPE == MEDIA
        assert o._can_reference(media)

        midref = media.make_idref_for(o)
        self._media_idref = midref
        self._media = media
        if not _init:
            self.add_cleaning_operation_once(self.__clean)

    @autoproperty
    def _get_begin(self):
        return self._begin

    @autoproperty
    def _set_begin(self, val):
        self._begin = val
        self.add_cleaning_operation_once(self.__clean)

    @autoproperty
    def _get_end(self):
        return self._end

    @autoproperty
    def _set_end(self, val):
        self._end = val
        self.add_cleaning_operation_once(self.__clean)

    @autoproperty
    def _get_duration(self):
        """The duration of this annotation.

        This property is a shortcut for ``self.end - self.begin``. Setting it
        will update self.end accordingly, leaving self.begin unchanged.
        return self._end - self._begin.

        This property will also be changed by setting self.begin or self.end,
        since each of this property leaves the other one unchanged when set.
        """
        return self._end - self._begin

    @autoproperty
    def _set_duration(self, val):
        self._set_end(self._begin + val)

    def __clean(self):
        o = self._owner
        o._backend.update_annotation(o._id, self._id,
                                     self._media_idref, self._begin, self._end)
