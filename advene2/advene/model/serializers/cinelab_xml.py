"""
Cinelab serializer implementation.
"""
from bisect import insort
from xml.etree.cElementTree import Element, ElementTree, SubElement

from advene.model.cam.consts import CAM_XML, CAMSYS_NS_PREFIX
from advene.model.consts import PARSER_META_PREFIX
from advene.model.serializers.advene_xml import _indent
from advene.model.serializers.advene_xml import _Serializer as _BaseSerializer

NAME = "Cinelab Advene XML"

EXTENSION = ".cxp" # Cinelab Xml Package

MIMETYPE = "application/x-cinelab-package+xml"

def make_serializer(package, file_):
    """Return a serializer that will serialize `package` to `file_`.

    `file_` is a writable file-like object. It is the responsibility of the
    caller to close it.

    The returned object must implement the interface for which
    :class:`_Serializer` is the reference implementation.
    """
    return _Serializer(package, file_)

def serialize_to(package, file_):
    """A shortcut for ``make_serializer(package, file_).serialize()``.

    See also `make_serializer`.
    """
    return _Serializer(package, file_).serialize()

class _Serializer(_BaseSerializer):

    def serialize(self):
        """Perform the actual serialization."""
        namespaces = self.namespaces = {}
        root = self.root = Element("package", xmlns=self.default_ns)
        package = self.package
        prefixes = package.get_meta(PARSER_META_PREFIX + "namespaces", "")
        for line in prefixes.split("\n"):
            if line:
                prefix, uri = line.split(" ")
                root.set("xmlns:%s" % prefix, uri)
                namespaces[uri] = prefix
        if package.uri:
            root.set("uri", package.uri)
        # package meta-data
        self._serialize_meta(package, self.root)
        # imports
        ximports = SubElement(self.root, "imports")
        for i in package.own.imports:
            self._serialize_import(i, ximports)
        if len(ximports) == 0:
            self.root.remove(ximports)
        # annotation-type
        xannotation_types = SubElement(self.root, "annotation-types")
        for t in package.own.annotation_types:
            self._serialize_tag(t, xannotation_types, "annotation-type")
        if len(xannotation_types) == 0:
            self.root.remove(xannotation_types)
        # relation-type
        xrelation_types = SubElement(self.root, "relation-types")
        for t in package.own.relation_types:
            self._serialize_tag(t, xrelation_types, "relation-type")
        if len(xrelation_types) == 0:
            self.root.remove(xrelation_types)
        # tags
        xtags = SubElement(self.root, "tags")
        for t in package.own.user_tags:
            self._serialize_tag(t, xtags)
        if len(xtags) == 0:
            self.root.remove(xtags)
        # media
        xmedias = SubElement(self.root, "medias")
        for m in package.own.medias:
            self._serialize_media(m, xmedias)
        if len(xmedias) == 0:
            self.root.remove(xmedias)
        # resources
        xresources = SubElement(self.root, "resources")
        for r in package.own.resources:
            self._serialize_resource(r, xresources)
        if len(xresources) == 0:
            self.root.remove(xresources)
        # annotations
        xannotations = SubElement(self.root, "annotations")
        for a in package.own.annotations:
            self._serialize_annotation(a, xannotations)
        if len(xannotations) == 0:
            self.root.remove(xannotations)
        # relations
        xrelations = SubElement(self.root, "relations")
        for r in package.own.relations:
            self._serialize_relation(r, xrelations)
        if len(xrelations) == 0:
            self.root.remove(xrelations)
        # views
        xviews = SubElement(self.root, "views")
        for v in package.own.views:
            self._serialize_view(v, xviews)
        if len(xviews) == 0:
            self.root.remove(xviews)
        # queries
        xqueries = SubElement(self.root, "queries")
        for q in package.own.queries:
            self._serialize_query(q, xqueries)
        if len(xqueries) == 0:
            self.root.remove(xqueries)
        # schemas
        xschemas = SubElement(self.root, "schemas")
        for L in package.own.schemas:
            self._serialize_list(L, xschemas, "schema")
        if len(xschemas) == 0:
            self.root.remove(xschemas)
        # lists
        xlists = SubElement(self.root, "lists")
        for L in package.own.user_lists:
            self._serialize_list(L, xlists)
        if len(xlists) == 0:
            self.root.remove(xlists)
        # external tag associations
        self._serialize_external_tagging(self.root)

        _indent(self.root)
        ElementTree(self.root).write(self.file)


    # end of the public interface

    def __init__(self, package, file_):
        _BaseSerializer.__init__(self, package, file_)
        insort(self.unserialized_meta_prefixes, CAMSYS_NS_PREFIX)
        self.default_ns = CAM_XML

    def _serialize_element_tags(self, elt, xelt):
        xtags = SubElement(xelt, "tags")
        for t in elt.iter_user_tag_ids(self.package, inherited=False):
            SubElement(xtags, "tag", {"id-ref":t})
        if len(xtags) == 0:
            xelt.remove(xtags)

