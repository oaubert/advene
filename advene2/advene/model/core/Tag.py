"""
I define the class Tag.
"""

from PackageElement import PackageElement, TAG

class Tag (PackageElement):

    ADVENE_TYPE = TAG 

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
