"""
I define the class List.
"""

from PackageElement import PackageElement, TAG

from warnings import warn

class List (PackageElement):

    ADVENE_TYPE = TAG 

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
        warn ("List not implemented yet")
