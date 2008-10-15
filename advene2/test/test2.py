from os import unlink
from os.path import exists, join, split
import gc
import sys
from weakref import ref

import advene.model.core.dirty as dirty

## uncomment the following to disable differed cleaning
#dirty.DirtyMixin = dirty.DirtyMixinInstantCleaning

from advene.model import DC_NS_PREFIX, RDFS_NS_PREFIX
from advene.model.core.package import Package
from advene.model.parsers import PARSER_META_PREFIX

_indent = []
def trace_wrapper (f):
    def wrapped (*args, **kw):
        global _indent
        print "===%s" % "".join(_indent), f.__name__, (args or ""), (kw or "")
        _indent.append("  ")
        r = f (*args, **kw)
        _indent.pop()
        print "===%s" % "".join(_indent), f.__name__, "->", r
        return r
    return wrapped

def trace_wrap_all (obj):
    cd = obj.__class__.__dict__
    od = obj.__dict__
    for k,v in cd.iteritems():
        if k[0] != "_" and callable (v):
            f = getattr (obj, k)
            od[k] = trace_wrapper (f)

def print_lastchance(mode=0):
    if mode == 0:
        print dirty.DirtyMixin._DirtyMixin__lastchance.keys()
    elif mode == 1:
        print dirty.DirtyMixin._DirtyMixin__lastchance.values()
    else:
        print dirty.DirtyMixin._DirtyMixin__lastchance.items()

def print_elements(p):
    print [(k,id(v)) for k,v in p._elements.items()]

dir  = split(__file__)[0]
filea = join(dir, "test2a.db")
fileb = join(dir, "test2b.db")
url1 = "sqlite:%s;p1" % filea
url2 = "sqlite:%s;p2" % filea
url3 = "sqlite:%s;p3" % filea
url4 = "sqlite:%s;p4" % fileb
url5 = "sqlite:%s;p5" % fileb
url6 = "sqlite:%s;p6" % fileb
url7 = "sqlite:%s;p7" % fileb

if __name__ == "__main__":

    # testing cyclic import and backend multiplexing

    if exists (filea): unlink (filea)
    if exists (fileb): unlink (fileb)

    Package.make_metadata_property (DC_NS_PREFIX+"creator", "dc_creator")

    p1 = Package(url1, create=True)
    p2 = Package(url2, create=True)
    p3 = Package(url3, create=True)
    p4 = Package(url4, create=True)
    p5 = Package(url5, create=True)
    p6 = Package(url6, create=True)
    p7 = Package(url7, create=True)

    assert p1._backend is p2._backend is p3._backend
    assert p4._backend is p5._backend is p6._backend is p7._backend
    assert p1._backend is not p4._backend

    p1.create_import("p2", p2)
    p1.create_import("p3", p3)
    p3.create_import("p4", p4)
    p3.create_import("p5", p5)
    p5.create_import("p6", p6)
    p5.create_import("p3", p3)
    p7.create_import("p5", p5) # will not be loaded again; just a decoy

    #trace_wrap_all(p1._backend)
    #trace_wrap_all(p4._backend)

    foref = "http://advene.liris.cnrs.fr/ns/frame_of_reference/ms;o=0"
    m4 = p4.create_media("m4", "http://example.com/m4.ogm", foref)
    m6 = p6.create_media("m6", "http://example.com/m6.ogm", foref)
    a3 = p3.create_annotation("a3", m4, 30, 39, "text/plain")
    a5 = p5.create_annotation("a5", m6, 50, 59, "text/plain")
    t2 = p2.create_tag("t2")
    t3 = p3.create_tag("t3")
    t4 = p4.create_tag("t4")
    t6 = p6.create_tag("t6")
    p3.associate_tag(a5, t4)
    p3.associate_tag(a5, t3)
    p3.associate_tag(a3, t3)
    p5.associate_tag(a3, t6)
    p5.associate_tag(a5, t6)
    p1.associate_tag(a3, t2)

    m3 = p3.create_media("m3", "urn:xyz", foref)
    r3 = p3.create_relation("r3", "text/plain", members=[a5, a3])
    L3 = p3.create_list("L3", items=[a5, r3, a3])
    v3 = p3.create_view("v3", "text/plain")
    q3 = p3.create_query("q3", "text/plain")
    R3 = p3.create_resource("R3", "text/plain")

    print
    print [i.id for i in p3.own.annotations]
    print [i.id for i in p4.own.medias]
    print [i.id for i in p5.own.annotations]
    print [i.id for i in p6.own.medias]
    print
    print [i.id for i in p3.all.medias]
    print [i.id for i in p3.all.annotations]
    print [i.id for i in p5.all.medias]
    print [i.id for i in p5.all.annotations]
    print [i.id for i in p1.all.medias]
    print [i.id for i in p1.all.annotations]
    print
    print [t.id for t in a3.iter_tags(p5)]
    print [t.id for t in a3.iter_tags(p1, False)]
    print [t.id for t in a3.iter_tags(p1)]
    print [i for i in a3.iter_tags_idrefs(p1)]
    print
    print [ e.id for e in t6.iter_elements(p5, False) ]
    print [ e.id for e in t6.iter_elements(p5) ]
    print [ i for i in t6.iter_elements_idrefs(p5) ]

    print a3.content_mimetype
    a3.content_mimetype = "text/html"
    a3.content_data = "<em>hello</em>\n"
    print a3.content_mimetype
    print "\n\n"


    ################

    from advene.model.serializers.advene_xml import make_serializer
    from sys import stdout

    p3.set_meta(PARSER_META_PREFIX + "namespaces", """\
dc %s
rdfs %s"""
    % (DC_NS_PREFIX, RDFS_NS_PREFIX))

    # testing metadata, including to unreachable element
    p3.dc_creator = "pchampin"
    trap = p4.create_resource("trap", "text/plain")
    p3.set_meta(RDFS_NS_PREFIX+"seeAlso", trap)
    trap.delete()
    del trap

    make_serializer(p3, stdout).serialize()
    print

    p1.close()
    p7.close()
    p2.close()
    p3.close()
    p4.close()
    p6.close()
    assert p5.closed
