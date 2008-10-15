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

    def do_or_postpone(self, id, function, *args, **kw):
        """If id has been created in backend, execute function,
           else postpone its execution.

        This is useful because some elements in the serialization may refer to
        other elements that are defined further.
        """
        if ":" in id or self.backend.has_element(self.package_id, id):
            function(*args, **kw)
        else:
            self._postponed.append((function, args, kw))

    def optional_sequence(self, tag, *args, **kw):
        items_name = kw.pop("items_name", None)
        if items_name is None:
            items_name = tag[:-1] # remove terminal 's'
        stream = self.stream

        stream.forward()
        elem = stream.elem
        if stream.event == "start" \
        and elem.tag == self.tag_template % tag:
            self.required(items_name, *args, **kw)
            self.sequence(items_name, *args, **kw)
            self._check_end(elem)
        else:
            stream.pushback()

    def handle_package(self):
        be = self.backend
        pid = self.package_id
        namespaces = "\n".join([ " ".join(el)
                                for el in self.ns_stack if el[0] ])
        if namespaces:
            be.set_meta(pid, "", "",
                        PARSER_META_PREFIX+"namespaces", namespaces, False)
        uri = self.current.get("uri")
        if uri is not None:
            be.update_uri(pid, uri)
        self.optional("meta", "", "")
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
        for f, a, k in self._postponed:
            f(*a, **k)

    def handle_import(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        url = self.get_attribute("url")
        uri = self.get_attribute("uri", "")
        be.create_import(pid, id, url, uri)
        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, IMPORT)

    def handle_tag(self, element_id=None):
        be = self.backend
        pid = self.package_id
        if element_id is None:
            # tag definition in package
            id = self.get_attribute("id")
            be.create_tag(pid, id)
            self.optional_sequence("imported-elements", items_name="element",
                                   tag_id=id)
            self.optional_sequence("tags", element_id=id)
            self.optional("meta", id, TAG)
        else:
            # tag association in element
            id = self.get_attribute("id-ref")
            self.do_or_postpone(id, be.associate_tag, pid, element_id, id)

    def handle_media(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        url = self.get_attribute("url")
        foref = self.get_attribute("frame-of-reference")
        be.create_media(pid, id, url, foref)

        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, MEDIA)
        
    def handle_resource(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        self.required("content", RESOURCE, be.create_resource, id)
        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, RESOURCE)

    def handle_annotation(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        media = self.get_attribute("media")
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
        self.required("content", ANNOTATION, be.create_annotation, id, media,
                      begin, end)
        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, ANNOTATION)

    def handle_relation(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        be.create_relation(pid, id, "x-advene/none", "", "")
        self.optional_sequence("members", id, [0])
        self.optional("content", RELATION, be.update_content_info, id,
                      RELATION)
        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, RELATION)

    def handle_view(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        self.required("content", VIEW, be.create_view, id)
        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, VIEW)

    def handle_query(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        self.required("content", QUERY, be.create_query, id)
        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, QUERY)

    def handle_list(self):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id")
        be.create_list(pid, id)
        self.optional_sequence("items", id, [0])
        self.optional_sequence("tags", element_id=id)
        self.optional("meta", id, LIST)
        
    # utility methods
            
    def handle_meta(self, owner_id, typ):
        elem = self.complete_current()
        be = self.backend
        pid = self.package_id
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
               be.set_meta(pid, owner_id, typ, key, child.text, False)
            else:
               is_id = True
               self.do_or_postpone(val,
                   be.set_meta, pid, owner_id, typ, key, val, True)

    def handle_content(self, typ, backend_method, element_id, *args):
        be = self.backend
        pid = self.package_id
        mimetype = self.get_attribute("mimetype")
        url = self.get_attribute("url", "")
        model = self.get_attribute("model", "")
        backend_method(pid, element_id, *args + (mimetype, model, url))
        elem = self.complete_current()
        if len(elem):
            raise ParserError("no XML tag allowed in content; use &lt;tag>")
        data = elem.text
        if url and data and data.strip():
            raise ParserError("content can not have both url (%s) and data" %
                              url)
        elif data:
            be.update_content_data(pid, element_id, typ, data)

    def handle_member(self, relation_id, count):
        # NB: count is a *list* containing the count, that is passed and
        # updated through all members, so as to keep track of the number of
        # members already added
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id-ref")
        be.insert_member(pid, relation_id, id, -1, count[0])
        count[0] += 1

    def handle_item(self, list_id, count):
        # NB: count is a *list* containing the count, that is passed and
        # updated through all members, so as to keep track of the number of
        # members already added
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id-ref")
        self.do_or_postpone(id, be.insert_item, pid, list_id, id, -1, count[0])
        count[0] += 1

    def handle_element(self, tag_id):
        be = self.backend
        pid = self.package_id
        id = self.get_attribute("id-ref")
        be.associate_tag(pid, id, tag_id)

    def handle_association(self):
        be = self.backend
        pid = self.package_id
        elt_id = self.get_attribute("element")
        tag_id = self.get_attribute("tag")
        be.associate_tag(pid, elt_id, tag_id)


#
