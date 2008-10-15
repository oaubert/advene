"""
I define the class Filter.
"""
from advene.model.core.element import PackageElement, QUERY
from advene.model.core.content import WithContentMixin

class Query(PackageElement, WithContentMixin):

    ADVENE_TYPE = QUERY 

    def __init__(self, owner, id, mimetype, model, url):
        PackageElement.__init__(self, owner, id)
        self._set_content_mimetype(mimetype, _init=True)
        self._set_content_model(model, _init=True)
        self._set_content_url(url, _init=True)

