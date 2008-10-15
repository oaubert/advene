from os import unlink
from os.path import exists, join, split
import gc
import sys
from urllib import pathname2url
from weakref import ref

import advene.model.core.dirty as dirty
## uncomment the following to disable differed cleaning
#dirty.DirtyMixin = dirty.DirtyMixinInstantCleaning

import advene.model.backends.sqlite as backend_sqlite
from advene.model.core.content import PACKAGED_ROOT
from advene.model.core.element import PackageElement
from advene.model.core.package import Package



base = split(__file__)[0]

package_url = "sqlite:%s" % (join (base, "test1.db"))
#package_url = "sqlite::memory:"

backend_sqlite._set_module_debug(False)

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

if __name__ == "__main__":


    if exists (package_url[7:]): unlink (package_url[7:])
    content_file = join(base, "a1.txt")
    if exists (content_file): unlink (content_file)

    Package.make_metadata_property ("http://purl.org/dc/elements/1.1/creator",
                                    "dc_creator")
    PackageElement.make_metadata_property (
        "http://purl.org/dc/elements/1.1/creator",
        "dc_creator")

    p = Package(package_url, create=True)
    #trace_wrap_all (p._backend)

    advene_ns = "http://advene.liris.cnrs.fr/ns/%s"

    p.dc_creator = "pchampin"
    m1 = p.create_media("m1", "http://champin.net/stream.avi",
        advene_ns % "frame_of_reference/ms;o=0")
    a1 = p.create_annotation("a1", m1, 20, 30, "text/plain")
    a2 = p.create_annotation("a2", m1, 0, 20, "text/plain")
    r1 = p.create_relation("r1", "text/plain")
    try:
        a2 = p.create_annotation("a2", m1, 0, 20, "text/plain")
    except AssertionError:
        pass
        # note: no backend call is needed to check that id "a2" is in use,
        # because annotation a2 is cached in the packaged (variable a2)
    else:
        raise Exception, "duplicate ID did raise any ModelException..."

    p.meta[advene_ns % "meta/main_media"] = m1

    a1.begin += 1
    a1.duration += 1
    p.set_meta(PACKAGED_ROOT, pathname2url(base))
    a1.content_url = "packaged:/a1.txt"
    a1.content_data = "You, stupid woman!"
    a1.dc_creator = "rartois"

    a2.set_meta(advene_ns % "meta/created_from", a1)

    a1.set_meta(advene_ns % "meta/foo", "bar")
    a2.meta[advene_ns % "meta/foo"] = "bar"
    
    print [a._id for a in p.own.annotations]
    print p.get("a1") # no backend call, since a1 is cached (variable a1)
    print p["a2"] # no backend call, since a2 is cached (variable a2)
    print m1.unit, m1.origin

    NB = 10
    print "creating %s annotations" % NB
    for i in range(NB):
        p.create_annotation("aa%s" % i, m1, i*10, i*10+9, "text/plain")
    print "done"

    r1.insert(1, p.get("aa1"))

    bw = ref(p._backend)
    p.close()
    print

    print "about to re-load package"
    p = Package(package_url)
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
    print p.get_meta(advene_ns % "meta/main_media")
    print a1.begin, a1.duration, a1.end
    print a1.dc_creator
    print a2.meta[advene_ns % "meta/created_from"]
    a2.del_meta(advene_ns % "meta/foo")
    print list(a2.iter_meta())
    p.create_resource("eraseme", "text/plain").delete()
    print list(p.own.resources)

    l = None; a1 = None; a2 = None; p.close(); p = None
