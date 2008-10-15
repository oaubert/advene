"""
I define the class of views.
"""

from PackageElement   import PackageElement, VIEW
from WithContentMixin import WithContentMixin

class View (PackageElement, WithContentMixin):

    ADVENE_TYPE = VIEW

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
        self._content   = None
