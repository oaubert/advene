"""
I define the class Filter.
"""
from PackageElement   import PackageElement, QUERY
from WithContentMixin import WithContentMixin

class Query (PackageElement, WithContentMixin):

    ADVENE_TYPE = QUERY 

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
