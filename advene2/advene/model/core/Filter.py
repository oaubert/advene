"""
I define the class Filter.
"""
from PackageElement   import PackageElement, FILTER
from WithContentMixin import WithContentMixin

from warnings import warn

class Filter (PackageElement, WithContentMixin):

    ADVENE_TYPE = FILTER 

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
        warn ("Filter not implemented yet")
