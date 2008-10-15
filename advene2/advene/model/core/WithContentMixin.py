"""
I define mixin class WithContentMixin for all types of elements that can have
a content.
"""

from Content import Content

class WithContentMixin:
    @property
    def content (self):
        # TODO manage schema and url
        c = getattr (self, "_cached_content", None)
        if c is None:
            mimetype, data = \
                self._owner._backend.get_content (self._id, self.ADVENE_TYPE)
            c = Content (self, mimetype, data)
            self._cached_content = c
        return c
