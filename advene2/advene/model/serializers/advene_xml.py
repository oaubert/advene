"""
Unstable and experimental serializer implementation.
"""
from itertools import chain
from xml.etree.cElementTree import Element, ElementTree, SubElement

from advene.model import ADVENE_NS_PREFIX
from advene.model.core.element import MEDIA, ANNOTATION, RELATION, LIST, TAG, \
                                      VIEW, QUERY, RESOURCE, IMPORT
from advene.model.parsers import PARSER_META_PREFIX
from advene.model.serializers import iter_unserialized_meta_prefix

NAME = "Generic Advene XML"

ADVENE_XML = "%s%s" % (ADVENE_NS_PREFIX, "advene-xml/0.1")

def make_serializer(package, file):
    """Return a serializer that will serialize package into file.

    The returned object must implement the interface for which
    :class:`_Serializer` is the reference implementation.
    """
    return _Serializer(package, file)

def serialize(package, file):
    """A shortcut for ``make_serializer(package, file).serialize``.
    """
    return _Serializer(package, file).serialize()

class _Serializer(object):

    def serialize(self):
        """Perform the actual serialization."""
        prefixes = self.package.get_meta(PARSER_META_PREFIX + "namespaces", "")
        for line in prefixes.split("\n"):
            if line:
                prefix, uri = line.split(" ")
                self.root.set("xmlns:%s" % prefix, uri)
                self.namespaces[uri] = prefix
        # package meta-data
        self._serialize_meta(self.package, self.root)
        # media
        xmedias = SubElement(self.root, "medias")
        for m in self.package.own.medias:
            self._serialize_media(m, xmedias)
        if len(xmedias) == 0:
            self.root.remove(xmedias)
        # annotations
        xannotations = SubElement(self.root, "annotations")
        for a in self.package.own.annotations:
            self._serialize_annotation(a, xannotations)
        if len(xannotations) == 0:
            self.root.remove(xannotations)
        # relations
        xrelations = SubElement(self.root, "relations")
        for r in self.package.own.relations:
            self._serialize_relation(r, xrelations)
        if len(xrelations) == 0:
            self.root.remove(xrelations)
        # lists
        xlists = SubElement(self.root, "lists")
        for L in self.package.own.lists:
            self._serialize_list(L, xlists)
        if len(xlists) == 0:
            self.root.remove(xlists)
        # tags
        xtags = SubElement(self.root, "tags")
        for t in self.package.own.tags:
            self._serialize_tag(t, xtags)
        if len(xtags) == 0:
            self.root.remove(xtags)
        # views
        xviews = SubElement(self.root, "views")
        for v in self.package.own.views:
            self._serialize_view(v, xviews)
        if len(xviews) == 0:
            self.root.remove(xviews)
        # queries
        xqueries = SubElement(self.root, "queries")
        for q in self.package.own.queries:
            self._serialize_query(q, xqueries)
        if len(xqueries) == 0:
            self.root.remove(xqueries)
        # resources
        xresources = SubElement(self.root, "resources")
        for r in self.package.own.resources:
            self._serialize_resource(r, xresources)
        if len(xresources) == 0:
            self.root.remove(xresources)
        # imports
        ximports = SubElement(self.root, "imports")
        for i in self.package.own.imports:
            self._serialize_import(i, ximports)
        if len(ximports) == 0:
            self.root.remove(ximports)
        # external tag associations
        self._serialize_external_tagging(self.root)

        _indent(self.root)
        ElementTree(self.root).write(self.file)

    # end of the public interface

    def __init__(self, package, file):

        # this will be ugly, because ElementTree in python 2.5 does not handle
        # custom namespace prefix, so we just handle them ourselves

        self.package = package
        self.file = file
        self.namespaces = {
            
        }
        self.root = Element("package", xmlns=ADVENE_XML)

    # element serializers

    def _serialize_media(self, m, xmedias):
        xm = SubElement(xmedias, "media", id=m.id, url=m.url,
                        **{"frame-of-reference": m.frame_of_reference})
        self._serialize_element_tags(m, xm)
        self._serialize_meta(m, xm)

    def _serialize_annotation(self, a, xannotations):
        midref = a.media_idref
        xa = SubElement(xannotations, "annotation", id=a.id,
                       media=midref, begin=str(a.begin), end=str(a.end))
        self._serialize_content(a, xa)
        self._serialize_element_tags(a, xa)
        self._serialize_meta(a, xa)

    def _serialize_relation(self, r, xrelations):
        xr = SubElement(xrelations, "relation", id=r.id)
        xmembers = SubElement(xr, "members")
        for m in r.iter_members_idrefs():
            SubElement(xmembers, "member", idref=m)
        self._serialize_content(r, xr)
        self._serialize_element_tags(r, xr)
        self._serialize_meta(r, xr)

    def _serialize_list(self, L, xlists):
        xL = SubElement(xlists, "list", id=L.id)
        xitems = SubElement(xL, "items")
        for i in L.iter_items_idrefs():
            SubElement(xitems, "item", idref=i)
        self._serialize_element_tags(L, xL)
        self._serialize_meta(L, xL)

    def _serialize_tag(self, t, ximports):
        xt = SubElement(ximports, "tag", id=t.id)
        L = [ idref for idref in t.iter_elements_idrefs(self.package, False)
                    if idref.find(":") > 0 ]
        if L:
            ximp = SubElement(xt, "imported-elements")
            for i in L:
                SubElement(ximp, "element", idref=i)
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
        xc = SubElement(xelt, "content",
                       mimetype=elt.content_mimetype)
        if elt.content_url:
            # TODO manage packaged: URLs
            xc.set("url", elt.content_url)
        else:
            xc.text = elt.content_data

    def _serialize_meta(self, obj, xobj):
        xm = SubElement(xobj, "meta")
        umps = chain(iter_unserialized_meta_prefix(), [None,])
        ump = umps.next() # there is at least one (PARSER_META_PREFIX)
        for k,v in obj.iter_meta_idrefs():
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
            if v.is_idref:
                xkeyval.set("id-ref", v)
            else:
                xkeyval.text = v
        if len(xm) == 0:
            xobj.remove(xm)
            
    def _serialize_element_tags(self, elt, xelt):
        xtags = SubElement(xelt, "tags")
        for t in elt.iter_tags_idrefs(self.package, inherited=False):
            SubElement(xtags, "tag", idref=t)
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
    return uriref[:cut+1], uriref[cut:]
