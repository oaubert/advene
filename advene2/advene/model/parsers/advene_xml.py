"""
Unstable and experimental parser implementation.
"""

import base64
from functools import partial
from os import path
from os.path import exists
from xml.etree.ElementTree import iterparse
from xml.parsers.expat import ExpatError

from advene.model.consts import ADVENE_XML, PARSER_META_PREFIX, PACKAGED_ROOT
from advene.model.parsers.base_xml import XmlParserBase
from advene.model.parsers.exceptions import ParserError
import advene.model.serializers.advene_xml as serializer
from advene.util.files import get_path, is_local

class Parser(XmlParserBase):

    NAME = serializer.NAME
    EXTENSION = serializer.EXTENSION
    MIMETYPE = serializer.MIMETYPE
    SERIALIZER = serializer # may be None for some parsers

    @classmethod
    def claims_for_parse(cls, file_):
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
                if el.tag == "{%s}package" % cls._NAMESPACE_URI:
                    return 80
                else:
                    return 0
            file_.seek(0)
            
        info = getattr(file_, "info", lambda: {})()
        mimetype = info.get("content-type", "")
        if mimetype.startswith(cls.MIMETYPE):
            r = 80
        else:
            if mimetype.startswith("application/xml") \
            or mimetype.startswith("text/xml"):
                r += 20
            fpath = get_path(file_)
            if fpath.endswith(cls.EXTENSION):
                r += 50
            elif fpath.endswith(".xml"):
                r += 20
        return r

    @classmethod
    def make_parser(cls, file_, package):
        """Return a parser that will parse `file_` into `package`.

        `file_` is a writable file-like object. It is the responsability of the
        caller to close it.

        The returned object must implement the interface for which
        :class:`_Parser` is the reference implementation.
        """
        return cls(file_, package)

    @classmethod
    def parse_into(cls, file_, package):
        """A shortcut for ``make_parser(file_, package).parse()``.

        See also `make_parser`.
        """
        cls(file_, package).parse()

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
                if mimetype == self.MIMETYPE:
                    self.package.set_meta(PACKAGED_ROOT, dirname)
        XmlParserBase.parse(self)

    # end of public interface

    _NAMESPACE_URI = ADVENE_XML

    def __init__(self, file_, package):
        assert self.__class__.claims_for_parse(file_) > 0
        XmlParserBase.__init__(self, file_, package, self._NAMESPACE_URI,
                               "package")
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
        colon = id.find(":")
        if colon > 0:
            elt = id
            do_it_now = self.package.get(id[:colon]) is not None
        else:
            elt = self.package.get(id)
            do_it_now = elt is not None
        if do_it_now:
            try_enter_no_event_section(elt, function)
            try:
                function(elt)
            finally:
                try_exit_no_event_section(elt, function)
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

    def manage_package_subelements(self):
        """
        This method may be overridden by application model parsers having a
        syntax simiar to the generic advene format - like the cinelab parser.
        """
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

    def handle_package(self):
        """
        Subclasses should normally not override this method, but rather
        `manage_package_subelements`.
        """
        pa = self.package
        namespaces = "\n".join([ " ".join(el)
                                for el in self.ns_stack if el[0] ])
        if namespaces:
            pa.set_meta(PARSER_META_PREFIX+"namespaces", namespaces)
        uri = self.current.get("uri")
        if uri is not None:
            pa.uri = uri
        self.optional("meta", pa)
        self.manage_package_subelements()
        for f, id in self._postponed:
            if id.find(":") > 0: # imported
                f(id)
            else:
                elt = self.package.get(id)
                try_enter_no_event_section(elt, f)
                try:
                    f(elt)
                finally:
                    try_exit_no_event_section(elt, f)

    def handle_import(self):
        id = self.get_attribute("id")
        url = self.get_attribute("url")
        uri = self.get_attribute("uri", "")
        elt = self.package._create_import_in_parser(id, url, uri)
        elt.enter_no_event_section()
        try:
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

    def handle_tag(self, element=None):
        if element is None:
            # tag definition in package
            id = self.get_attribute("id")
            elt = self.package.create_tag(id)
            elt.enter_no_event_section()
            try:
                self.optional_sequence(
                    "imported-elements", items_name="element", advene_tag=elt)
                self.optional_sequence("tags", element=elt)
                self.optional("meta", elt)
            finally:
                elt.exit_no_event_section()
        else:
            # tag association in element
            id = self.get_attribute("id-ref")
            self.do_or_postpone(id,
                                partial(self.package.associate_tag, element))

    def handle_media(self):
        id = self.get_attribute("id")
        url = self.get_attribute("url")
        foref = self.get_attribute("frame-of-reference")
        elt = self.package.create_media(id, url, foref)
        elt.enter_no_event_section()
        try:
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

    def handle_resource(self):
        id = self.get_attribute("id")
        elt = self.required("content", self.package.create_resource, id)
        elt.enter_no_event_section()
        try:
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

    def handle_annotation(self):
        id = self.get_attribute("id")
        media = self.get_attribute("media")
        if media.find(":") <= 0: # same package
            media = self.package.get(media)
        if media is None:
            raise ParserError("unknown media %s" % self.get_attribute("media"))
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
        elt.enter_no_event_section()
        try:
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

    def handle_relation(self):
        id = self.get_attribute("id")
        elt = self.package.create_relation(id, "x-advene/none")
        def update_content_info(mimetype, model, url):
            elt.content_mimetype = mimetype
            elt.content_model = model
            elt.content_url = url
            return elt
        elt.enter_no_event_section()
        try:
            self.optional_sequence("members", elt)
            self.optional("content", update_content_info)
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

    def handle_view(self):
        id = self.get_attribute("id")
        elt = self.required("content", self.package.create_view, id)
        elt.enter_no_event_section()
        try:
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

    def handle_query(self):
        id = self.get_attribute("id")
        elt = self.required("content", self.package.create_query, id)
        elt.enter_no_event_section()
        try:
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

    def handle_list(self):
        id = self.get_attribute("id")
        elt = self.package.create_list(id)
        elt.enter_no_event_section()
        try:
            self.optional_sequence("items", elt, [0])
            self.optional_sequence("tags", element=elt)
            self.optional("meta", elt)
        finally:
            elt.exit_no_event_section()

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
                obj.enter_no_event_section()
                try:
                    obj.set_meta(key, child.text, False)
                finally:
                    obj.exit_no_event_section()
            elif val.find(":") > 0: # imported
                obj.enter_no_event_section()
                try:
                    obj.set_meta(key, val, True)
                finally:
                    obj.exit_no_event_section()
            else:
                self.do_or_postpone(val, partial(obj.set_meta, key))

    def handle_content(self, creation_method, *args):
        mimetype = self.get_attribute("mimetype")
        url = self.get_attribute("url", "")
        model = self.get_attribute("model", "")
        encoding = self.get_attribute("encoding", "")
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
            if encoding:
                if encoding == "base64":
                    data = base64.decodestring(data)
                else:
                    raise ParserError("encoding %s is not supported", encoding)
            elt.enter_no_event_section()
            try:
                elt.content_data = data
            finally:
                elt.exit_no_event_section()
        return elt

    def handle_member(self, relation):
        a = self.get_attribute("id-ref")
        if ":" not in a:
            a = self.package.get(a)
        relation.append(a)

    def handle_item(self, lst, c):
        # c is a 1-item list containing the virtual length of the list,
        # i.e. the length taking into account the postponed elements
        # it is used to insert postponed elements at the right index
        id = self.get_attribute("id-ref")
        self.do_or_postpone(id, lst.append, partial(lst.insert, c[0]))
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

def try_enter_no_event_section(elt, function):
    getattr(elt, "enter_no_event_section", lambda: None)()
    # try to also find an element in 'function'
    function = getattr(function, "func", function) # unwrap partial function
    im_self = getattr(function, "im_self", None)
    getattr(im_self, "enter_no_event_section", lambda: None)()

def try_exit_no_event_section(elt, function):
    # try to find an element in 'function'
    function = getattr(function, "func", function) # unwrap partial function
    im_self = getattr(function, "im_self", None)
    getattr(im_self, "exit_no_event_section", lambda: None)()
    getattr(elt, "exit_no_event_section", lambda: None)()

#
