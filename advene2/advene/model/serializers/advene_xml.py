"""
Unstable and experimental serializer implementation.

Note that the order chosen for XML elements (imports, tags, medias, resources,
annotations, relations, views, queries, lists) is designed to limit the number
of forward references, which makes the work of the parser more difficult.
Forward references are nevetheless still possible in meta-data, tag associated to another tag, list containing another list
"""

from itertools import chain
from xml.etree.cElementTree import Element, ElementTree, SubElement

from advene.model.consts import ADVENE_XML, PARSER_META_PREFIX
from advene.model.serializers.unserialized import iter_unserialized_meta_prefix

NAME = "Generic Advene XML"

EXTENSION = ".bxp" # Advene-2 Xml Package

MIMETYPE = "application/x-advene-bxp"

def make_serializer(package, file_):
    """Return a serializer that will serialize `package` to `file_`.

    `file_` is a writable file-like object. It is the responsability of the
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


class _Serializer(object):

    def serialize(self):
        """Perform the actual serialization."""
        namespaces = self.namespaces = {}
        root = self.root = Element("package", xmlns=ADVENE_XML)
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
        # tags
        xtags = SubElement(self.root, "tags")
        for t in package.own.tags:
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
        # lists
        xlists = SubElement(self.root, "lists")
        for L in package.own.lists:
            self._serialize_list(L, xlists)
        if len(xlists) == 0:
            self.root.remove(xlists)
        # external tag associations
        self._serialize_external_tagging(self.root)

        _indent(self.root)
        ElementTree(self.root).write(self.file)

    # end of the public interface

    def __init__(self, package, file_):

        # this will be ugly, because ElementTree in python 2.5 does not handle
        # custom namespace prefix, so we just handle them ourselves

        self.package = package
        self.file = file_

    # element serializers

    def _serialize_media(self, m, xmedias):
        xm = SubElement(xmedias, "media", id=m.id, url=m.url,
                        **{"frame-of-reference": m.frame_of_reference})
        self._serialize_element_tags(m, xm)
        self._serialize_meta(m, xm)

    def _serialize_annotation(self, a, xannotations):
        mid = a.media_id
        xa = SubElement(xannotations, "annotation", id=a.id,
                       media=mid, begin=str(a.begin), end=str(a.end))
        self._serialize_content(a, xa)
        self._serialize_element_tags(a, xa)
        self._serialize_meta(a, xa)

    def _serialize_relation(self, r, xrelations):
        xr = SubElement(xrelations, "relation", id=r.id)
        xmembers = SubElement(xr, "members")
        for m in r.iter_member_ids():
            SubElement(xmembers, "member", {"id-ref":m})
        if len(xmembers) == 0:
            xr.remove(xmembers)
        self._serialize_content(r, xr)
        self._serialize_element_tags(r, xr)
        self._serialize_meta(r, xr)

    def _serialize_list(self, L, xlists):
        xL = SubElement(xlists, "list", id=L.id)
        xitems = SubElement(xL, "items")
        for i in L.iter_item_ids():
            SubElement(xitems, "item", {"id-ref":i})
        if len(xitems) == 0:
            xL.remove(xitems)
        self._serialize_element_tags(L, xL)
        self._serialize_meta(L, xL)

    def _serialize_tag(self, t, ximports):
        xt = SubElement(ximports, "tag", id=t.id)
        L = [ id for id in t.iter_element_ids(self.package, False)
                    if id.find(":") > 0 ]
        if L:
            ximp = SubElement(xt, "imported-elements")
            for i in L:
                SubElement(ximp, "element", {"id-ref":i})
        self._serialize_element_tags(t, xt)
        self._serialize_meta(t, xt)

    def _serialize_view(self, v, xviews):
        xv = SubElement(xviews, "view", id=v.id)
        self._serialize_content(v, xv)
        self._serialize_element_tags(v, xv)
        self._serialize_meta(v, xv)

    def _serialize_query(self, q, xqueries):
        xq = SubElement(xqueries, "query", id=q.id)
        self._serialize_content(q, xq)
        self._serialize_element_tags(q, xq)
        self._serialize_meta(q, xq)

    def _serialize_resource(self, r, xresources):
        xr = SubElement(xresources, "resource", id=r.id)
        self._serialize_content(r, xr)
        self._serialize_element_tags(r, xr)
        self._serialize_meta(r, xr)

    def _serialize_import(self, i, ximports):
        xi = SubElement(ximports, "import", id=i.id, url=i.url)
        if i.uri:
            xi.set("uri", i.uri)
        self._serialize_element_tags(i, xi)
        self._serialize_meta(i, xi)

    # common methods

    def _serialize_content(self, elt, xelt):
        if elt.content_mimetype != "x-advene/none":
            xc = SubElement(xelt, "content",
                           mimetype=elt.content_mimetype)
            if elt.content_model_id:
                xc.set("model", elt.content_model_id)
            if elt.content_url:
                # TODO manage packaged: URLs
                xc.set("url", elt.content_url)
            else:
                xc.text = elt.content_data

    def _serialize_meta(self, obj, xobj):
        xm = SubElement(xobj, "meta")
        umps = chain(iter_unserialized_meta_prefix(), [None,])
        ump = umps.next() # there is at least one (PARSER_META_PREFIX)
        for k,v in obj.iter_meta_ids():
            if ump and k.startswith(ump):
                continue
            while ump and k > ump: ump = umps.next()
            if ump and k.startswith(ump):
                continue # also necessary

            ns, tag = _split_uri_ref(k)
            prefix = self.namespaces.get(ns)
            if prefix is None:
                xkeyval = SubElement(xm, tag, xmlns=ns)
            else:
                xkeyval = SubElement(xm, "%s:%s" % (prefix, tag))
            if v.is_id:
                xkeyval.set("id-ref", v)
            else:
                xkeyval.text = v
        if len(xm) == 0:
            xobj.remove(xm)
            
    def _serialize_element_tags(self, elt, xelt):
        xtags = SubElement(xelt, "tags")
        for t in elt.iter_tag_ids(self.package, inherited=False):
            SubElement(xtags, "tag", {"id-ref":t})
        if len(xtags) == 0:
            xelt.remove(xtags)

    def _serialize_external_tagging(self, xpackage):
        xx = SubElement(xpackage, "external-tag-associations")
        pairs = self.package._backend.iter_external_tagging(self.package._id)
        for e, t in pairs:
            xxt = SubElement(xx, "association", element=e, tag=t)
        if len(xx) == 0:
            xpackage.remove(xx)
            

def _indent(elem, level=0):
    """from http://effbot.org/zone/element-lib.htm#prettyprint"""
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent(child, level+1)
            if not child.tail or not child.tail.strip():
                child.tail = i + "  "
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def _split_uri_ref(uriref):
    sharp = uriref.rfind("#")
    slash = uriref.rfind("/")
    cut = max(sharp, slash)
    return uriref[:cut+1], uriref[cut+1:]
