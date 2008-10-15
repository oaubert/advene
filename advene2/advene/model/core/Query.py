"""
I define the class Filter.
"""
from advene.model.core.PackageElement   import PackageElement, QUERY
from advene.model.core.WithContentMixin import WithContentMixin

class Query(PackageElement, WithContentMixin):

    ADVENE_TYPE = QUERY 

    def __init__(self, owner, id):
        PackageElement.__init__(self, owner, id)
