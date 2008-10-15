"""
I define the class of streams.
"""

from PackageElement import PackageElement, STREAM

class Stream (PackageElement):

    ADVENE_TYPE = STREAM

    def __init__ (self, owner, id, uri):
        PackageElement.__init__ (self, owner, id)
        self._uri = uri
