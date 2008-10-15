"""
I define the class Bag.
"""

from PackageElement import PackageElement, BAG

from warnings import warn

class Bag (PackageElement):

    ADVENE_TYPE = BAG 

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
        warn ("Bag not implemented yet")
