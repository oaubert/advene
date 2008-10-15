"""
I define mixin class WithContentMixin for all types of elements that can have
a content.
"""

from Content import Content

class WithContentMixin:
    @property
    def content (self):
        c = getattr (self, "_cached_content", None)
        if c is None:
            o = self._owner
            mimetype, data, schema_idref = \
                o._backend.get_content (o._id, self._id, self.ADVENE_TYPE)
            c = Content (self, mimetype, data, schema_idref)
            self._cached_content = c
        return c
