from os import unlink
from os.path import exists, join, split
import gc
import sys
from weakref import ref

import advene.model.core.dirty as dirty

## uncomment the following to disable differed cleaning
#dirty.DirtyMixin = dirty.DirtyMixinInstantCleaning

from advene.model.core.package import Package

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

    Package.make_metadata_property ("dc#Creator", "dc_creator")



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

    for p in [p1, p2, p3, p4, p5, p6, p7]: p.close()

    # reconnect backends
    dummya = Package("sqlite:%s" % filea)
    dummyb = Package("sqlite:%s" % fileb)
    #trace_wrap_all(dummya._backend)
    #trace_wrap_all(dummyb._backend)

    print

    p1 = Package(url1)
    p3 = p1["p3"].package
    p4 = p3["p4"].package
    p5 = p3["p5"].package
    p6 = p5["p6"].package

    m4 = p4.create_media("m4", "http://example.com/m4.ogm")
    m6 = p6.create_media("m6", "http://example.com/m6.ogm")
    a3 = p3.create_annotation("a3", m4, 30, 39, "text/plain")
    a5 = p5.create_annotation("a5", m6, 50, 59, "text/plain")

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
