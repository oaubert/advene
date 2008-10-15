"""
I define the class List.
"""

from PackageElement import PackageElement, LIST

class List (PackageElement):

    ADVENE_TYPE = LIST 

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
