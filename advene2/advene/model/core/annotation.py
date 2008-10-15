"""
I define the class of annotations.
"""

from advene.model.consts import _RAISE
from advene.model.core.element import PackageElement, \
                                      ANNOTATION, MEDIA, RESOURCE
from advene.model.core.content import WithContentMixin
from advene.util.autoproperty import autoproperty


class Annotation(PackageElement, WithContentMixin):
    """FIXME: missing docstring.
    """

    ADVENE_TYPE = ANNOTATION

    @classmethod
    def instantiate(cls, owner, id,
                    media, begin, end, mimetype, model, url):
        """
        Factory method to create an instance based on backend data.
        """
        r = super(Annotation, cls).instantiate(owner, id)
        r._begin = begin
        r._end = end
        r._media_id = media
        r._media = None
        r._instantiate_content(mimetype, model, url)
        return r

    @classmethod
    def create_new(cls, owner, id,
                   media, begin, end, mimetype, model, url):
        """
        Factory method to create a new instance both in memory and backend.
        """
        media_id = PackageElement._check_reference(owner, media, MEDIA, True)
        begin = int(begin)
        end = int(end)
        model_id = PackageElement._check_reference(owner, model, RESOURCE)
        cls._check_content_cls(mimetype, model_id, url)
        owner._backend.create_annotation(owner._id, id, media_id, begin, end,
                                         mimetype, model_id, url)
        r = cls.instantiate(owner, id, media_id, begin, end,
                            mimetype, model_id, url)
        if media is not media_id:
            # we have the instance, let's cache it now
            r._media = media
        return r


    def __str__(self):
        return "Annotation(%s,%s,%s)" % \
               (self._media_id, self._begin, self._end)

    def _cmp(self, other):
        """
        Common implementation for __lt__, __gt__, __le__ and __ge__.

        Do not rename it to __cmp__ because it would be used for __eq__ as
        well, which is not what we want.
        """
        return self._begin - other._begin \
            or self._end - other._end \
            or cmp(self._media_id, other._media_id)

    def __lt__(self, other):
        return getattr(other, "ADVENE_TYPE", None) is ANNOTATION \
           and self._cmp(other) < 0

    def __le__(self, other):
        return getattr(other, "ADVENE_TYPE", None) is ANNOTATION \
           and self._cmp(other) <= 0

    def __gt__(self, other):
        return getattr(other, "ADVENE_TYPE", None) is ANNOTATION \
           and self._cmp(other) > 0

    def __ge__(self, other):
        return getattr(other, "ADVENE_TYPE", None) is ANNOTATION \
           and self._cmp(other) >= 0

    def get_media(self, default=None):
        """Return the media associated to this annotation.

        If the media is unreachable, the ``default`` value is returned.

        See also `media` and `media_id`.
        """
        r = self._media
        if r is None:
            r = self._media = \
                self._owner.get_element(self._media_id, default)
        return r

    @autoproperty
    def _get_media(self):
        """Return the media associated to this annotation.

        If the media instance is unreachable, an exception is raised.

        See also `get_media` and `media_id`.
        """
        return self.get_media(_RAISE)

    @autoproperty
    def _set_media(self, media):
        mid = self._check_reference(self._owner, media, MEDIA, True)
        self.emit("pre-changed::media", "media", media)
        self._media_id = mid
        self._media = media
        self.__store()
        self.emit("changed::media", "media", media)

    @autoproperty
    def _get_media_id(self):
        """The id-ref of this annotation's media.

        This is a read-only property giving the id-ref of the resource held
        by `media`.

        Note that this property is accessible even if the corresponding
        media is unreachable.

        See also `get_media` and `media`.
        """
        return self._media_id

    @autoproperty
    def _get_begin(self):
        return self._begin

    @autoproperty
    def _set_begin(self, val):
        self.emit("pre-changed::begin", "begin", val)
        self._begin = val
        self.__store()
        self.emit("changed::begin", "begin", val)

    @autoproperty
    def _get_end(self):
        return self._end

    @autoproperty
    def _set_end(self, val):
        self.emit("pre-changed::end", "end", val)
        self._end = val
        self.__store()
        self.emit("changed::end", "end", val)

    @autoproperty
    def _get_duration(self):
        """The duration of this annotation.

        This property is a shortcut for ``self.end - self.begin``. Setting it
        will update self.end accordingly, leaving self.begin unchanged.
        return self._end - self._begin.

        This property will also be changed by setting self.begin or self.end,
        since each one of these properties leaves the other one unchanged when set.
        """
        return self._end - self._begin

    @autoproperty
    def _set_duration(self, val):
        self._set_end(self._begin + val)

    def __store(self):
        o = self._owner
        o._backend.update_annotation(o._id, self._id,
                                     self._media_id, self._begin, self._end)
