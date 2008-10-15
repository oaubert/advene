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
    def medias (self):
        return self._imported._all.medias

    @property
    def annotations (self):
        return self._imported._all.annotations

    @property
    def relations (self):
        return self._imported._all.relations

    @property
    def bags (self):
        return self._imported._all.bags

    @property
    def imports (self):
        return self._imported._all.imports

    @property
    def queries (self):
        return self._imported._all.queries

    @property
    def views (self):
        return self._imported._all.views

    @property
    def resources (self):
        return self._imported._all.resources
