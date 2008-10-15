"""
I define the class of relations.
"""

from PackageElement   import PackageElement, RELATION
from WithContentMixin import WithContentMixin

class Relation (PackageElement, WithContentMixin):

    ADVENE_TYPE = RELATION

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
