from time import time

from advene.model.cam.package import Package
import advene.util.session as session

import hotshot, os, sys

_t = 0

def measure_time(label=None):
    global _t
    nt = time()
    if label:
        print >> sys.stderr, "%s: %0.3fs" % (label, nt-_t)
    _t = nt

if __name__ == "__main__":

    measure_time() # take origin
    p = Package("file:examples/nosferatu.czp")
    measure_time("loading time")

    session.package = p

    measure_time() # take origin
    prof = hotshot.Profile("test/nosferatu.prof", lineevents=1)
    prof.run("[ a.count_relations(p) for a in p.own.iter_annotations() ]")
    prof.close()
    measure_time("counting all relations")

    p.close()

    os.system("hotshot2calltree -o test/cachegrind.out test/nosferatu.prof")
    os.system("kcachegrind test/cachegrind.out")
