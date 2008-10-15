"""
I define the class of views.
"""

from advene.model.core.PackageElement   import PackageElement, VIEW
from advene.model.core.WithContentMixin import WithContentMixin

class View(PackageElement, WithContentMixin):

    ADVENE_TYPE = VIEW

    def __init__(self, owner, id):
        PackageElement.__init__(self, owner, id)
