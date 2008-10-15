"""
I define the class of medias.
"""

from PackageElement import PackageElement, MEDIA

class Media (PackageElement):

    ADVENE_TYPE = MEDIA

    def __init__ (self, owner, id, uri):
        PackageElement.__init__ (self, owner, id)
        self._uri = uri
