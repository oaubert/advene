"""
I define the class Import.
"""

from PackageElement import PackageElement, IMPORT

class Import (PackageElement):

    ADVENE_TYPE = IMPORT 

    def __init__ (self, owner, id):
        PackageElement.__init__ (self, owner, id)
        self._imported = owner._imported[id]

    def __in__ (self, element):
        return element in self._imported._all

    @property
    def streams (self):
        return self._imported._all.streams

    @property
    def annotations (self):
        return self._imported._all.annotations

    @property
    def relations (self):
        return self._imported._all.relations

    @property
    def views (self):
        return self._imported._all.views

    @property
    def resources (self):
        return self._imported._all.resources

    @property
    def filters (self):
        return self._imported._all.filters

    @property
    def bags (self):
        return self._imported._all.bags

    @property
    def imports (self):
        return self._imported._all.imports
