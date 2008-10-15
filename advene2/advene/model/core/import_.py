"""
I define the class Import.
"""

from advene.model.core.element import PackageElement, IMPORT
from advene.utils.autoproperty import autoproperty
 

class Import(PackageElement):

    ADVENE_TYPE = IMPORT 

    def __init__(self, owner, id, url, uri):
        PackageElement.__init__(self, owner, id)
        self._url = url
        self._uri = uri
        self._imported = owner._imports_dict[id]

    @autoproperty
    def _get_url(self):
        return self._url

    @autoproperty
    def _set_url(self, url):
        assert url
        self._url = url
        self.add_cleaning_operation_once(self.__clean)

    @autoproperty
    def _get_uri(self):
        return self._uri

    @autoproperty
    def _set_uri(self, uri):
        self._uri = uri
        self.add_cleaning_operation_once(self.__clean)

    @autoproperty
    def _get_package(self):
        return self._imported

    def __clean(self):
        o = self.owner
        o._backend.update_import(o._id, self._id, url, uri)

    # group interface

    def __contains__(self, element):
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

    # dict interface

    def __getitem__ (self, i):
        return self._imported[i]

    def get(self, i, default=None):
        return self._imported.get(i, default)
