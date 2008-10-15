"""
Unstable and experimental parser implementation.
"""

from os import path
from os.path import exists
from xml.etree.ElementTree import iterparse
from xml.parsers.expat import ExpatError

from advene.model.consts import ADVENE_XML, PARSER_META_PREFIX, PACKAGED_ROOT
from advene.model.core.element import MEDIA, ANNOTATION, RELATION, LIST, TAG, \
                                      VIEW, QUERY, RESOURCE, IMPORT
from advene.model.parsers.base_xml import XmlParserBase
from advene.model.parsers.exceptions import ParserError
import advene.model.serializers.advene_xml as serializer
from advene.utils.files import get_path, is_local

NAME = serializer.NAME

EXTENSION = serializer.EXTENSION

MIMETYPE = serializer.MIMETYPE

SERIALIZER = serializer # may be None for some parsers

def claims_for_parse(file_):
    """Is this parser likely to parse that file-like object?

    `file_` is a readable file-like object. It is the responsability of the
    caller to close it.

    Return an int between 00 and 99, indicating the likelyhood of this parser
    to handle correctly the given URL. 70 is used as a standard value when the
    parser is pretty sure it can handle the URL.
    """
    r = 0

    if hasattr(file_, "seek"):
        # try to open it as xml file and get the root element
        t = file_.tell()
        file_.seek(0)
        it = iterparse(file_, events=("start",))
        try:
            ev, el = it.next()
        except ExpatError, e:
            return 0
        else:
            if el.tag == "{%s}package" % ADVENE_XML:
                return 80
            else:
                return 0
        file_.seek(0)
        
    info = getattr(file_, "info", lambda: {})()
    mimetype = info.get("content-type", "")
    if mimetype.startswith(MIMETYPE):
        r = 80
    else:
        if mimetype.startswith("application/xml") \
        or mimetype.startswith("text/xml"):
            r += 20
        fpath = get_path(file_)
        if fpath.endswith(EXTENSION):
            r += 50
        elif fpath.endswith(".xml"):
            r += 20
    return r

def make_parser(file_, package):
    """Return a parser that will parse `file_` into `package`.

    `file_` is a writable file-like object. It is the responsability of the
    caller to close it.

    The returned object must implement the interface for which
    :class:`_Parser` is the reference implementation.
    """
    return _Parser(file_, package)

def parse_into(file_, package):
    """A shortcut for ``make_parser(file_, package).parse()``.

    See also `make_parser`.
    """
    _Parser(file_, package).parse()


class _Parser(XmlParserBase):

    def parse(self):
        "Do the actual parsing."
        file_ = self.file
        fpath = get_path(file_)
        if is_local(file_) and fpath.endswith("content.xml"):
            # looks like this is a manually-unzipped package,
            dirname = path.split(fpath)[0]
            mfn = path.join(dirname, "mimetype")
            if exists(mfn):
                f = open(mfn)
                mimetype = f.read()
                f.close()
                if mimetype == MIMETYPE:
                    self.package.set_meta(PACKAGED_ROOT, dirname)
        XmlParserBase.parse(self)

    # end of public interface

    def __init__(self, file_, package, namespace_uri=ADVENE_XML,
                                       root="package"):
        assert claims_for_parse(file_) > 0
        XmlParserBase.__init__(self, file_, package, namespace_uri, root)
        self._postponed = []

    def do_or_postpone(self, id, function, function2=None):
        """
        If `identified` an imported element, function is invoked with `id` as
        its argument.

        If `id` is a plain identifier, it is checked whether `self.package` has
        such an element. If so, function is invoked with that element as its
        argument; else, its execution is postponed.

        This is useful because some elements in the serialization may refer to
        other elements that are defined further.

        If function2 is provided and the invocation is postponed, then it will
        be function2 rather than function that will be invoked.
        """
        if ":" in id:
            elt = id
        else:
            elt = self.package.get(id, None)
        if elt is not None:
            function(elt)
        else:
            self._postponed.append((function2 or function, id))

    def optional_sequence(self, tag, *args, **kw):
        items_name = kw.pop("items_name", None)
        if items_name is None:
            items_name = tag[:-1] # remove terminal 's'
        stream = self.stream

        stream.forward()
        elem = stream.elem
        if stream.event == "start" \
        and elem.tag == self.tag_template % tag:
            self.sequence(items_name, *args, **kw)
            self._check_end(elem)
        else:
            stream.pushback()

    def handle_package(self):
        pa = self.package
        namespaces = "\n".join([ " ".join(el)
                                for el in self.ns_stack if el[0] ])
        if namespaces:
            pa.set_meta(PARSER_META_PREFIX+"namespaces", namespaces)
        uri = self.current.get("uri")
        if uri is not None:
            pa.uri = uri
        self.optional("meta", pa)
        self.optional_sequence("imports")
        self.optional_sequence("tags")
        self.optional_sequence("medias")
        self.optional_sequence("resources")
        self.optional_sequence("annotations")
        self.optional_sequence("relations")
        self.optional_sequence("views")
        self.optional_sequence("queries", items_name="query")
        self.optional_sequence("lists")
        self.optional_sequence("external-tag-associations",
                               items_name="association")
        for f, id in self._postponed:
            elt = self.package.get(id)
            f(elt)

    def handle_import(self):
        id = self.get_attribute("id")
        url = self.get_attribute("url")
        uri = self.get_attribute("uri", "")
        elt = self.package._create_import_in_parser(id, url, uri)
        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)

    def handle_tag(self, element=None):
        if element is None:
            # tag definition in package
            id = self.get_attribute("id")
            elt = self.package.create_tag(id)
            self.optional_sequence("imported-elements", items_name="element",
                                   advene_tag=elt)
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        else:
            # tag association in element
            id = self.get_attribute("id-ref")
            self.do_or_postpone(id,
                lambda tag: self.package.associate_tag(element, tag))

    def handle_media(self):
        id = self.get_attribute("id")
        url = self.get_attribute("url")
        foref = self.get_attribute("frame-of-reference")
        elt = self.package.create_media(id, url, foref)

        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)
        
    def handle_resource(self):
        id = self.get_attribute("id")
        elt = self.required("content", self.package.create_resource, id)
        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)

    def handle_annotation(self):
        id = self.get_attribute("id")
        media = self.get_attribute("media")
        if not ":" in media:
            media = self.package.get(media)
        begin = self.get_attribute("begin")
        try:
            begin = int(begin)
        except ValueError:
            raise ParserError("wrong begin value for %s" % id)
        end = self.get_attribute("end")
        try:
            end = int(end)
        except ValueError:
            raise ParserError("wrong end value for %s" % id)
        if end < begin:
            raise ParserError("end is before begin in %s" % id)
        elt = self.required("content", self.package.create_annotation,
                                       id, media, begin, end)
        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)

    def handle_relation(self):
        id = self.get_attribute("id")
        elt = self.package.create_relation(id, "x-advene/none")
        self.optional_sequence("members", elt, [0])
        def update_content_info(mimetype, model, url):
            elt.content_mimetype = mimetype
            elt.content_model = model
            elt.content_url = url
            return elt
        self.optional("content", update_content_info)
        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)

    def handle_view(self):
        id = self.get_attribute("id")
        elt = self.required("content", self.package.create_view, id)
        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)

    def handle_query(self):
        id = self.get_attribute("id")
        elt = self.required("content", self.package.create_query, id)
        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)

    def handle_list(self):
        id = self.get_attribute("id")
        elt = self.package.create_list(id)
        self.optional_sequence("items", elt, [0])
        self.optional_sequence("tags", element=elt)
        self.optional("meta", elt)
        
    # utility methods
            
    def handle_meta(self, obj):
        elem = self.complete_current()
        for child in elem:
            key = child.tag
            if key.startswith("{"):
                cut = key.find("}")
                key = key[1:cut] + key[cut+1:]
            if len(child):
                raise ParserError("Unexpected sub-element in metadata %s" %
                                  key)
            val = child.get("id-ref")
            if val is None:
                obj.set_meta(key, child.text, False)
            elif ":" in val:
                obj.set_meta(key, val, True)
            else:
                self.do_or_postpone(val, lambda val: obj.set_meta(key, val))

    def handle_content(self, creation_method, *args):
        mimetype = self.get_attribute("mimetype")
        url = self.get_attribute("url", "")
        model = self.get_attribute("model", "")
        elt = creation_method(*args + (mimetype, "", url))
        self.do_or_postpone(model, elt._set_content_model)
        elem = self.complete_current()
        if len(elem):
            raise ParserError("no XML tag allowed in content; use &lt;tag>")
        data = elem.text
        if url and data and data.strip():
            raise ParserError("content can not have both url (%s) and data" %
                              url)
        elif data:
            elt.content_data = data
        return elt

    def handle_member(self, relation, c):
        # c is a 1-length list containing the virtual length of the list,
        # i.e. the length counting the postponed elements
        a = self.get_attribute("id-ref")
        if ":" not in a:
            a = self.package.get(a)
        relation.append(a)
        c[0] += 1

    def handle_item(self, lst, c):
        # c is a 1-length list containing the virtual length of the list,
        # i.e. the length counting the postponed elements
        id = self.get_attribute("id-ref")
        self.do_or_postpone(id, lambda e: lst.insert(c[0], e))
        c[0] += 1

    def handle_element(self, advene_tag):
        id = self.get_attribute("id-ref")
        # should only be imported, so no check
        self.package.associate_tag(id, advene_tag)

    def handle_association(self):
        elt_id = self.get_attribute("element")
        tag_id = self.get_attribute("tag")
        # both tag and element should be imported, so no check
        self.package.associate_tag(elt_id, tag_id)


#
