"""
I define the class Import.
"""

from advene.model.exceptions import ModelError, UnreachableImportError
from advene.model.core.group import GroupMixin
from advene.model.core.element import PackageElement, IMPORT
from advene.util.autoproperty import autoproperty

class Import(PackageElement, GroupMixin):

    ADVENE_TYPE = IMPORT

    # attributes that do not prevent imports to be volatile
    _url = None
    _uri = None
    _imported = None

    @classmethod
    def instantiate(cls, owner, id, url, uri):
        r = super(Import, cls).instantiate(owner, id)
        r._url = url
        r._uri = uri
        r._imported = owner._imports_dict.get(id)
        return r

    @classmethod
    def create_new(cls, owner, id, package):
        if id in owner._imports_dict:
            # we can not wait for the backend to check that,
            # because we will only create the import element in the backend
            # when the internal structures of the packages are successfuly
            # updated, so we need to be sure everything is ok
            raise ModelError("Already have an import named %s" % id)
        if package is owner:
            raise ModelError("A package cannot import itself")
        if [ p for p in owner._imports_dict.itervalues()
                     if p is not None and
                      (p.url == package.url or p.uri and p.uri == package.uri)
        ]:
            raise ModelError("Package already imported", p)

        url, uri = package.url, package.uri # may access the backend
        owner._imports_dict[id] = package
        owner._update_backends_dict()
        package._importers[owner] = id

        owner._backend.create_import(owner._id, id, url, uri)
        r = cls.instantiate(owner, id, url, uri)
        return r

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
        assert url, "URL cannot be empty"
        self.emit("pre-modified::url", "url", url)
        self._url = url
        self.__store()
        self.emit("modified::url", "url", url)

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
        self.emit("pre-modified::uri", "uri", uri)
        self._uri = uri
        self.__store()
        self.emit("modified::uri", "uri", uri)

    @autoproperty
    def _get_package(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        else:
            return self._imported

    def __store(self):
        o = self._owner
        o._backend.update_import(o._id, self._id, self._url, self._uri)

    def __contains__(self, element):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return element in self._imported.own

    # group interface

    def iter_medias(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_medias()

    def iter_annotations(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_annotations()

    def iter_relations(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_relations()

    def iter_views(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_views()

    def iter_resources(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_resources()

    def iter_tags(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_tags()

    def iter_lists(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_lists()

    def iter_imports(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_imports()

    def iter_queries(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_queries()

    # dict interface

    def __getitem__ (self, i):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported[i]

    def get(self, i, default=None):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.get(i, default)
