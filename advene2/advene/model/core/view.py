"""
I define the class of views.
"""

from advene.model.core.element import PackageElement, VIEW
from advene.model.core.content import WithContentMixin

class View(PackageElement, WithContentMixin):

    ADVENE_TYPE = VIEW

    def __init__(self, owner, id, mimetype, schema, url):
        PackageElement.__init__(self, owner, id)
        self._set_content_mimetype(mimetype, _init=True)
        self._set_content_schema(schema, _init=True)
        self._set_content_url(url, _init=True)

