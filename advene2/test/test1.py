from advene.model.backends.sqlite.SqliteBackend import SqliteBackend
from advene.model.core.Package import Package

from os import unlink
from os.path import exists, join, split
import sys

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

if __name__ == "__main__":


    if exists (uri[7:]): unlink (uri[7:])

    Package.make_metadata_property ("dc#Creator", "dc_creator")

    p = Package.create (uri)
    trace_wrap_all (p._backend)

    #sys.exit(0)

    p.create_stream("s1", "http://champin.net/stream.avi")
    p.create_annotation("a1", "s1", 20, 30)
    p.create_annotation("a2", "s1", 0, 20)
    p.create_relation("r1")
    p.create_bag("b1")
    print [a._id for a in p.own.annotations]
    print p.get_element ("a1")
    print p.get_element ("a2")
    p.get_element("a1").content._set_data ("hello")
    p.dc_creator = "pchampin"

    p.close()
    print


    p = Package.bind (uri)
    trace_wrap_all (p._backend)

    l = list (p.own.annotations)
    print [a._id for a in p.own.annotations]
    a1 = p.get_element ("a1")
    a2 = p.get_element ("a2")
    print a1, p.get_element ("a1")
    print a1.content._get_data()
    print p.dc_creator
    p.close()
    print

    p = Package.bind (uri)
    trace_wrap_all (p._backend)
    print p.get_element ("a1")
    print p.get_element ("a1").content
    print p.get_element ("a1")
