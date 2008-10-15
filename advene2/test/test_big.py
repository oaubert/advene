from time import time

from advene.model.core.diff import diff_packages
from advene.model.core.media import FOREF_PREFIX
from advene.model.core.package import Package
import advene.model.serializers.advene_xml as xml
import advene.model.serializers.advene_zip as zip

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
La = [ ("a%s" % i, Lm[i%NBM][0], (i//NBM)*10, (i//NBM)*10+9)
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
    xml.serialize_to(p, f)
    measure_time("serializing XML")
    f.close()

    measure_time() # take origin
    q = Package("file:test/test_big.bxp")
    measure_time("parsing XML")

    diff = diff_packages(p, q)
    measure_time("checking parsed package")
    assert len(diff) == 0, diff

    f = open("test/test_big.bzp", "w")
    measure_time() # take origin
    zip.serialize_to(p, f)
    measure_time("serializing ZIP")
    f.close()

    measure_time() # take origin
    r = Package("file:test/test_big.bzp")
    measure_time("parsing ZIP")

    diff = diff_packages(p, r)
    measure_time("checking parsed package")
    assert len(diff) == 1, diff # the PACKAGED_ROOT metadata is different

    list(p.all.annotations)
    measure_time("building annotations list")

    m7 = r["m7"]
    m8 = r["m8"]
 
    measure_time() # take origin
    l1 = len([ a for a in r.all.iter_annotations(media=(m7, m8), at=100) ])
    measure_time("building annotations sublist (efficient)")

    l2 =  len([ a for a in r.all.annotations
                 if a.media in (m7,m8) and a.begin <= 100 <= a.end ])
    measure_time("building annotations sublist (less efficient)")

    assert l1==l2, (l1, l2)
    print "(sublist was %s element(s) long)" % l1

    p.close()
    q.close()
    r.close()
