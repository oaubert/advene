from os import unlink
from os.path import exists, join, split
import gc
import sys
from weakref import ref

import advene.model.core.dirty as dirty

## uncomment the following to disable differed cleaning
#dirty.DirtyMixin = dirty.DirtyMixinInstantCleaning

from advene.model.core.package import Package

uri = "sqlite:%s" % (join (split (__file__)[0], "test1.db"))
#uri = "sqlite::memory:"

def trace_wrapper (f):
    def wrapped (*args, **kw):
        print "===", f.__name__, (args or ""), (kw or "")
        r = f (*args, **kw)
        print "===", f.__name__, "->", r
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

if __name__ == "__main__":


    if exists (uri[7:]): unlink (uri[7:])

    Package.make_metadata_property ("dc#Creator", "dc_creator")

    p = Package(uri, create=True)
    #trace_wrap_all (p._backend)

    p.dc_creator = "pchampin"
    m1 = p.create_media("m1", "http://champin.net/stream.avi")
    a1 = p.create_annotation("a1", m1, 20, 30)
    a1.begin += 1
    a2 = p.create_annotation("a2", m1, 0, 20)
    p.get_element("a1").content_data = "hello"
    r1 = p.create_relation("r1")
    r1.extend((a1, a2))
    print [a._id for a in p.own.annotations]
    print p.get("a1")
    print p["a2"]
    

    NB = 10
    print "creating %s annotations" % NB
    for i in range(NB):
        p.create_annotation("aa%s" % i, m1, i*10, i*10+9)
    print "done"
    r1.insert(1, p.get("aa1"))

    bw = ref(p._backend)
    p.close()
    print

    print "about to re-load package"
    p = Package(uri)
    # ensure that backend has changed
    assert p._backend is not bw()
    print "package loaded"
    #trace_wrap_all (p._backend)

    l = list (p.own.annotations)
    #print [a._id for a in p.own.annotations]
    a1 = p.get_element ("a1")
    a2 = p.get_element ("a2")
    print id(a1) == id(p.get_element ("a1"))
    print a1.content_data
    print p.dc_creator
    print a1.begin

    l = None; a1 = None; a2 = None; p.close(); p = None
