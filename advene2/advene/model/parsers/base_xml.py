"""I provide base classes for XML parsers.

TODO: document the provided classes.
"""
from xml.etree.ElementTree import iterparse

from advene.model.consts import _RAISE
from advene.model.parsers.exceptions import ParserError

class XmlParserBase(object):
    """
    TODO write a better documentation

    The idea is that subclasses define ``handle_X`` methods where X is the
    unqualified tag.

    Property `package` holds the package to parse into.

    DEPRECATED: Property `backend` and `package_id` are useful to feed the
    package's backend.

    Property `current` always points to the current element (with the
    ElementTree API). Note that the element will have its attribute, but not
    its text nor its sub-elements. To wait for an element to be completely
    constructed, invoke method `complete_current`. However, to parse 
    subelements, you may prefer to use methods `required`, `optional` and
    `sequence`, that will check the structure of subelements, then invoke the
    corresponding `handle_X` methods. Note that `required` and `optional` will 
    return the value returned by `handle_X` (`optional` returns None if the
    element is not found).

    Method `get_attribute` is a shortcut for ``current.get(k[, d])`` but will
    raise a `ParseError` with the appopriate message if the attribute is
    missing and no default value is provided.

    Property `ns_stack` is a list of (prefix, uri) pairs used as a stack for
    namespaces.

    For advanced use, property `stream` holds the underlying `Stream` instance.

    See `advene.model.parsers.advene_xml` for an example.
    """

    def __init__(self, file_, package, namespace_uri, root):
        self.file = file_
        self.package = package
        self.namespace_uri = namespace_uri
        self.tag_template = "{%s}%%s" % namespace_uri
        self.root = root
        self.clear_after_handle = True
        self._completed = 0
        self.cut = len(namespace_uri)+2

    @property
    def current(self):
        return self.stream.elem

    @property
    def ns_stack(self):
        return self.stream.namespaces

    def get_attribute(self, key, default=_RAISE):
        e = self.stream.elem
        r = e.get(key, default)
        if r is _RAISE:
            raise ParserError("missing attribute %s in %s" %
                              (key, e.tag[self.cut:]))
        else:
            return r

    def parse(self):
        f = self.file
        self.backend = self.package._backend # TODO: remove (deprecated)
        self.package_id = self.package._id # TODO: remove (deprecated)
        self.stream = st = Stream(f)
        expected = self.tag_template % self.root
        if st.elem.tag != expected:
            raise ParserError("expecting %s, found %s" %
                              (expected, self.stream.elem.tag))
        self.package.enter_no_event_section()
        try:
            self._handle([], {})
        finally:
            self.package.exit_no_event_section()

    def required(self, tag, *args, **kw):
        stream = self.stream
        stream.forward()
        elem = stream.elem
        if stream.event != "start" or elem.tag != self.tag_template % tag:
            raise ParserError("expecting %s, found %s" %
                              (tag, self.stream.elem.tag))
        r = self._handle(args, kw)
        self._check_end(elem)
        return r

    def optional(self, tag, *args, **kw):
        stream = self.stream
        stream.forward()
        elem = stream.elem
        if stream.event == "start" and elem.tag == self.tag_template % tag:
            r = self._handle(args, kw)
            self._check_end(elem)
            return r
        else:
            self.stream.pushback()
            return None

    def sequence(self, tag, *args, **kw):
        """NB: this methods allows an *empty* sequence.

        If you want a sequence with at least 1 element, use the following
        pattern:::

            required(mytag)
            sequence(mytag)
        """
        stream = self.stream
        tag = self.tag_template % tag
        stream.forward()
        while stream.event == "start" and stream.elem.tag == tag:
            elem = stream.elem
            self._handle(args, kw)
            self._check_end(elem)
            stream.forward()
        stream.pushback()

    def complete_current(self):
        self._completed += 1
        tag = self.stream.elem.tag
        for ev, el in self.stream:
            if ev == "end" and el.tag == tag:
                break
        return el

    def _handle(self, args, kw, ):
        stream = self.stream
        elem = self.stream.elem
        assert elem.tag.startswith("{%s}" % self.namespace_uri)
        n = t = elem.tag[self.cut:]
        i = n.find("-")
        while i >= 0:
            n = n[:i] + "_" + n[i+1:]
            i = n[i+1:].find("-")
        h =  getattr(self, "handle_%s" % n, None)
        if h is None:
            raise NotImplementedError("don't know what to do with tag %s" % t)
        return h(*args, **kw)

    def _check_end(self, elem):
        stream = self.stream
        if self._completed:
            self._completed -= 1
        else:
            stream.forward()
        event = stream.event
        if event == "end" and stream.elem == elem:
            if self.clear_after_handle:
                # makes parsing less memory-consuming
                elem.clear()
        else:
            if event == "end":
                # meaning that stream.elem != elem, should not happen
                raise ParserError("unbalanced parsing of %s" %
                                  (elem.tag[self.cut:],))
            else:
                raise ParserError("unexpected child %s in %s" %
                                  (stream.elem.tag, elem.tag[self.cut:]))


class Stream(object):
    """
    Wrap the result of iterparse:
    * start-ns and end-ns are interpreted, (prefix, uri) pairs being pushed
      and popped accordingly in attribute `namespaces`
    * start and end events are accessible through the `event` and `elem`

    Unlike iterators, a `Stream` has a notion of "current" item (accessible
    through `event` and `elem`. To access the next element, the `forward`
    method must be explicitly invoked. If it reaches the end, `event` and
    `elem` will be None.

    Note that a `Stream` is also iterable. The first yielded item will be the
    current item. If the iteration is interrupted, the current item will be
    the last yielded item.
    """
    def __init__(self, filelike):
        if hasattr(filelike, "seek"):
            # may be required, because claims_for_url messes with seek
            filelike.seek(0)
        self._it = iterparse(filelike,
                             events=("start", "end", "start-ns", "end-ns",))
        self.namespaces = []
        self._event = None
        self._elem = None
        self._prev = None
        self._next = None
        self.forward()

    @property
    def event(self):
        return self._event

    @property
    def elem(self):
        return self._elem

    def forward(self):
        if self._it is None: return False
        if self._next:
            self._prev = self._event, self._elem
            self._event, self._elem = self._next
            self._next = None
            return True
        stop = False
        namespaces = self.namespaces
        try:
            while not stop:
                ev, el = self._it.next()
                if ev == "start-ns":
                    namespaces.append(el)
                elif ev == "end-ns":
                    namespaces.pop(-1)
                else:
                    stop = True
        except StopIteration:
            ev, el =  None, None
            self._it = None
        self._prev = self._event, self._elem
        self._event = ev
        self._elem  = el
        return ev is not None

    def pushback(self):
        """Push the last item back in the stream.

        Note that no more than one item can be pushed back.

        Limitation: this does not change `namespaces` accordingly!
        """
        if self._prev is None or self._prev[0] is None:
            raise ValueError("nothing to pushback")
        elif self._next is not None:
            raise Exception("can only pushback one step")
        else:
            self._next = self._event, self._elem
            self._event, self._elem = self._prev

    def __iter__(self):
        while self._event is not None:
            yield self._event, self._elem
            self.forward()
