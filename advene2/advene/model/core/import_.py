"""
I define the class Import.
"""

from advene.model.exceptions import UnreachableImportError
from advene.model.core.element import PackageElement, IMPORT
from advene.utils.autoproperty import autoproperty
 

class Import(PackageElement):

    ADVENE_TYPE = IMPORT 

    def __init__(self, owner, id, url, uri):
        PackageElement.__init__(self, owner, id)
        self._url = url
        self._uri = uri
        self._imported = owner._imports_dict[id]

    def delete(self):
        super(Import, self).delete()
        o = self._owner
        del o._imports_dict[self._id]
        del self._imported._importers[o]
        o._update_backends_dict()

    @autoproperty
    def _get_url(self):
        return self._url

    @autoproperty
    def _set_url(self, url):
        assert url
        self._url = url
        self.__store()

    @autoproperty
    def _get_uri(self):
        return self._uri

    @autoproperty
    def _set_uri(self, uri):
        self._uri = uri
        self.__store()

    @autoproperty
    def _get_package(self):
        return self._imported

    def __store(self):
        o = self._owner
        o._backend.update_import(o._id, self._id, self._url, self._uri)

    # group interface

    def __contains__(self, element):
        if self._imported:
            raise UnreachableImportError(self._id)
        return element in self._imported._all

    @property
    def medias(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.medias

    @property
    def annotations(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.annotations

    @property
    def relations(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.relations

    @property
    def views(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.views

    @property
    def resources(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.resources

    @property
    def tags(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.tags

    @property
    def lists(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.lists

    @property
    def imports(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.imports

    @property
    def queries(self):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported._all.queries

    # dict interface

    def __getitem__ (self, i):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported[i]

    def get(self, i, default=None):
        if self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.get(i, default)
