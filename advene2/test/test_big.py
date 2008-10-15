from os import unlink, path
from time import time

from advene.model.core.diff import diff_packages
from advene.model.core.media import FOREF_PREFIX
from advene.model.core.package import Package
from advene.model.serializers.advene_xml import serialize_to

_t = 0

def measure_time(label=None):
    global _t
    nt = time()
    if label:
        print "%s: %0.3fs" % (label, nt-_t)
    _t = nt

NBM = 100
NBA = 10000
Lm = [ ("m%s" % i, "http://example.com/m%s" % i) for i in xrange(NBM) ]
La = [ ("a%s" % i, Lm[i%NBM][0], (i//NBA)*10, (i//NBA)*10+9)
       for i in xrange(NBA) ]
foref = FOREF_PREFIX + "ms;o=0"

if __name__ == "__main__":
    p = Package("file:test/test_big.bxp", create=True)
    
    measure_time() # take origin
    for m, u in Lm:
        p.create_media(m, u, foref)
    for a, m, b, e in La:
        p.create_annotation(a, p[m], b, e, "text/plain")
    measure_time("creating %s medias and %s annotations" %(NBM, NBA))

    f = open("test/test_big.bxp", "w")
    measure_time() # take origin
    serialize_to(p, f)
    measure_time("serializing")
    f.close()

    measure_time() # take origin
    q = Package("file:test/test_big.bxp")
    measure_time("parsing")

    diff = diff_packages(p, q)
    measure_time("checking parsed package")
    assert len(diff) == 0

    list(q.all.annotations)
    measure_time("building annotations list")
