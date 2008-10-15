"""
I define the class of resources.
"""

from PackageElement   import PackageElement, RESOURCE
from WithContentMixin import WithContentMixin

class Resource (PackageElement, WithContentMixin):

    ADVENE_TYPE = RESOURCE

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
