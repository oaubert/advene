from advene.model.cam.group import CamGroupMixin
from advene.model.cam.element import CamElementMixin
from advene.model.core.import_ import Import as CoreImport
from advene.model.exceptions import UnreachableImportError

class Import(CoreImport, CamElementMixin, CamGroupMixin):

    # group interface

    def iter_user_tags(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_user_tags()

    def iter_annotation_types(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_annotation_types()

    def iter_relation_types(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_relation_types()

    def iter_user_lists(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_user_lists()

    def iter_schemas(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.iter_schemas()

    def count_user_tags(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.count_user_tags()

    def count_annotation_types(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.count_annotation_types()

    def count_relation_types(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.count_relation_types()

    def count_user_lists(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.count_user_lists()

    def count_schemas(self):
        if not self._imported:
            raise UnreachableImportError(self._id)
        return self._imported.own.count_schemas()

    # TODO when renaming is implemented: prevent "cam" from being renamed


