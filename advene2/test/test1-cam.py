from os import unlink, getcwd
from os.path import exists, join

import advene.model.backends.sqlite as backend_sqlite
from advene.model.cam.package import Package



#base = split(__file__)[0]
base = join(getcwd(), "test")

package_url1 = "file:%s" % (join (base, "test1-cam1.czp"))
package_url2 = "file:%s" % (join (base, "test1-cam2.czp"))
advene_ns = "http://advene.liris.cnrs.fr/ns/%s"


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

def print_elements(p):
    print [(k,id(v)) for k,v in p._elements.items()]


def main():
    if exists (package_url1[5:]): unlink (package_url1[5:])
    if exists (package_url2[5:]): unlink (package_url2[5:])

    p1 = Package(package_url1, create=True)
    p1.dc_creator = "pchampin"

    at1 = p1.create_annotation_type("at1")
    at2 = p1.create_annotation_type("at2")
    rt1 = p1.create_relation_type("rt1")
    rt2 = p1.create_relation_type("rt2")
    sc1 = p1.create_schema("sc1", (at1, rt1))
    li1 = p1.create_user_list("li1", (at1, at2, rt2))
    t1 = p1.create_user_tag("t1")
    t2 = p1.create_user_tag("t2")

    m1 = p1.create_media("m1", "http://example.com/foo.avi")
    a1 = p1.create_annotation("a1", m1, 0, 100, "text/plain", type=at1)
    a2 = p1.create_annotation("a2", m1, 10, 20, "text/plain", type=at1)
    a3 = p1.create_annotation("a3", m1, 20, 30, "text/plain", type=at2)
    r1 = p1.create_relation("r1", members=(a1, a2))
    r2 = p1.create_relation("r2", members=(a3, a2))

    p1.associate_user_tag(m1, t1)
    p1.associate_user_tag(a1, t1)

    for i in p1.own:
        i.dc_creator = "pchampin"

    p2 = Package(package_url2, create=True)
    p2.dc_creator = "oaubert"

    i1 = p2.create_import("i1", p1)
    a4 = p2.create_annotation("a4", m1, 30, 40, "text/plain", type=at2)
    r3 = p2.create_relation("r3", members=(a4, a1))
    m2 = p2.create_media("m2", "http://example.com/bar.avi")
    a5 = p2.create_annotation("a5", m1, 40, 50, "text/plain", type=at2)
    r4 = p2.create_relation("r4", members=(a5, a2))

    t3 = p2.create_user_tag("t3")
    p2.associate_user_tag(a1, t3)
    p2.associate_user_tag(a2, t3)
    p2.associate_user_tag(a5, t1)
    p2.associate_user_tag(a5, t2)

    print [ i.id for i in p1.own ]
    print [ i.id for i in p1.all ]
    print [ i.id for i in p2.own ]
    print [ i.id for i in p2.all ]
    print

    print p2.own.medias, len(p2.own.medias), p2.all.medias, len(p2.all.medias)
    print p2.own.annotations, len(p2.own.annotations), \
          p2.all.annotations, len(p2.all.annotations)
    print p2.own.relations, len(p2.own.relations), \
          p2.all.relations, len(p2.all.relations)
    print p2.own.annotation_types, len(p2.own.annotation_types), \
          p2.all.annotation_types, len(p2.all.annotation_types)
    print p2.own.relation_types, len(p2.own.relation_types), \
          p2.all.relation_types, len(p2.all.relation_types)
    print p2.own.user_tags, len(p2.own.user_tags), \
          p2.all.user_tags, len(p2.all.user_tags)
    print p2.own.schemas, len(p2.own.schemas), \
          p2.all.schemas, len(p2.all.schemas)
    print p2.own.user_lists, len(p2.own.user_lists), \
          p2.all.user_lists, len(p2.all.user_lists)
    print


    print "at1", [ e.id for e in at1.iter_elements(p1) ], \
                 [ e.id for e in at1.iter_elements(p2) ]
    print "at2", [ e.id for e in at2.iter_elements(p1) ], \
                 [ e.id for e in at2.iter_elements(p2) ]
    print "t1 ", [ e.id for e in t1.iter_elements(p1) ], \
                 [ e.id for e in t1.iter_elements(p2) ]
    print "t2 ", [ e.id for e in t2.iter_elements(p1) ], \
                 [ e.id for e in t2.iter_elements(p2) ] 
    print "t3 ", [ e.id for e in t3.iter_elements(p1) ], \
                 [ e.id for e in t3.iter_elements(p2) ]
    print

    print "NB: the following warnings are normal when serializing CAM "\
          "package to .bzp (.czp will be the prefered format)"

    p1.save()
    p2.save()

    return p1, p2

if __name__ == "__main__":
    p1, p2 = main()

 
