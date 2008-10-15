"""
I define the class of resources.
"""

from advene.model.core.element import PackageElement, RESOURCE
from advene.model.core.content import WithContentMixin

class Resource(PackageElement, WithContentMixin):

    ADVENE_TYPE = RESOURCE

    def __init__(self, owner, id, mimetype, schema, url):
        PackageElement.__init__(self, owner, id)
        if schema:
            if not hasattr(schema, "ADVENE_TYPE"):
                # internally, we may sometimes pass backend data directly,
                # where schema is an id-ref rather than a Media instance
                schema = owner.get_element(schema)
        else:
            schema = None # could be an empty string
        self._set_content_mimetype(mimetype, _init=True)
        self._set_content_schema(schema, _init=True)
        self._set_content_url(url, _init=True)

