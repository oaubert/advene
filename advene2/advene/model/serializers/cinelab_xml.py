"""
Cinelab serializer implementation.
"""
from bisect import insort
from xml.etree.cElementTree import Element, ElementTree, SubElement

from advene.model.cam.consts import CAM_XML, CAMSYS_NS_PREFIX
from advene.model.serializers.advene_xml import _indent
from advene.model.serializers.advene_xml import _Serializer as _AdveneSerializer

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


class _Serializer(_AdveneSerializer):
    # this implementation tries to maximize the reusing of code from 
    # _AdveneSerializer. It does so by "luring" it into using some methods
    # of an element instead of others. This is a bit of a hack, but works
    # well... It assumes, however, that the parser is *not* multithreaded.

    def serialize(self):
        """Perform the actual serialization."""
        namespaces = self.namespaces = {}
        root = self.root = Element("package", xmlns=self.default_ns)
        package = self.package
        namespaces = package._get_namespaces_as_dict()
        for uri, prefix in namespaces.iteritems():
            root.set("xmlns:%s" % prefix, uri)
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
        _AdveneSerializer.__init__(self, package, file_)
        insort(self.unserialized_meta_prefixes, CAMSYS_NS_PREFIX)
        self.default_ns = CAM_XML

    # luring methods (cf. comment at top of that class)
    
    def _serialize_element_tags(self, elt, xelt):
        # lure `_AdveneXmlParser.handle_tag` into using
        # `iter_my_user_tag_ids` instead of `iter_my_tag_ids`
        # by overridding method at instance level
        elt.iter_my_tag_ids = elt.iter_my_user_tag_ids
        _AdveneSerializer._serialize_element_tags(self, elt, xelt)
        # restore class level method
        del elt.iter_my_tag_ids

