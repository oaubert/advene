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
        self._imported = owner._imports_dict.get(id)

    def delete(self):
        super(Import, self).delete()
        o = self._owner
        del o._imports_dict[self._id]
        del self._imported._importers[o]
        o._update_backends_dict()

    @autoproperty
    def _get_url(self):
        """
        The URL to which this import fetches the imported package.
        """
        return self._url

    @autoproperty
    def _set_url(self, url):
        assert url
        self.emit("pre-changed::url", "url", url)
        self._url = url
        self.__store()
        self.emit("changed::url", "url", url)

    @autoproperty
    def _get_uri(self):
        """
        The URI identifying the imported package.

        It may be different from the physical URL from which the imported
        package has actually been fetched.
        """
        return self._uri

    @autoproperty
    def _set_uri(self, uri):
        self.emit("pre-changed::uri", "uri", uri)
        self._uri = uri
        self.__store()
        self.emit("changed::uri", "uri", uri)

    @autoproperty
    def _get_package(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        else:
            return self._imported

    def __store(self):
        o = self._owner
        o._backend.update_import(o._id, self._id, self._url, self._uri)

    # group interface

    def __contains__(self, element):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return element in self._imported.own

    @property
    def medias(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.medias

    @property
    def annotations(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.annotations

    @property
    def relations(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.relations

    @property
    def views(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.views

    @property
    def resources(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.resources

    @property
    def tags(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.tags

    @property
    def lists(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.lists

    @property
    def imports(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.imports

    @property
    def queries(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.queries

    # dict interface

    def __getitem__ (self, i):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported[i]

    def get(self, i, default=None):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.get(i, default)
