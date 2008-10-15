"""
I define the class Import.
"""

from advene.model.core.element import PackageElement, IMPORT

class Import(PackageElement):

    ADVENE_TYPE = IMPORT 

    def __init__(self, owner, id, url, uri):
        PackageElement.__init__(self, owner, id)
        self._url = url
        self._uri = uri
        self._imported = owner._imports_dict[id]

    def __in__(self, element):
        return element in self._imported._all

    @property
    def medias(self):
        return self._imported._all.medias

    @property
    def annotations(self):
        return self._imported._all.annotations

    @property
    def relations(self):
        return self._imported._all.relations

    @property
    def views(self):
        return self._imported._all.views

    @property
    def resources(self):
        return self._imported._all.resources

    @property
    def tags(self):
        return self._imported._all.tags

    @property
    def lists(self):
        return self._imported._all.lists

    @property
    def imports(self):
        return self._imported._all.imports

    @property
    def queries(self):
        return self._imported._all.queries
