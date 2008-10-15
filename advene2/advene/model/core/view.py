"""
I define the class of views.
"""

from advene.model.core.element import PackageElement, VIEW
from advene.model.core.content import WithContentMixin

class View(PackageElement, WithContentMixin):

    ADVENE_TYPE = VIEW

    def __init__(self, owner, id):
        PackageElement.__init__(self, owner, id)
