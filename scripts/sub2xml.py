#! /usr/bin/python

# Subtitle to XML (advene) converter
# Converts subtitle formats to advene XML annotations

# Based on
# vlc/modules/demux/util/sub.c
# for the decoding part

import sys
import re

from advene.package import Package, Annotation
from advene.fragment import ByteCountFragment


def frame2ts (f):
    """
    Converts a frame number into a timestamp in microseconds
    """
    # 4000 microseconds per frame (25 fps)
    return  f * 4000

def ts2bc (t):
    """Converts a timestamp into a bytecount"""
    mux_rate = 10.08 * 1024 * 1024   # the rate we read the stream (in bytes/s)
    ratio = long(mux_rate / 1000000)
    return t * ratio

def frame2bc (f):
    """
    Converts a frame number into a bytecount
    """
    return ts2bc (frame2ts (f))

def create_annotation (package, alpha, omega, data):
    """
    Creates an annotation in the package
    """
    t = package.schemas['subtitle'].annotationTypes['annotation']
    t.create (fragment = ByteCountFragment (begin=alpha,
                                            end=omega),
              contentData = data)

    
def microdvd (file, p):
    """
    Converts the subtitles from file and put the into the package p
    """
    f = open(file, "r")
    reg = re.compile (r"""{(\d+)}{(\d+)}(.*)""")
    for l in f.readlines():
        l = l.strip()
        m = reg.match (l)
        if m:
            (begin, end, data) = m.groups()
            begin = long(begin)
            end = long(end)
            sys.stdout.write('.')
            sys.stdout.flush ()
            create_annotation (p, frame2bc (begin), frame2bc (end), unicode(data, 'iso8859-1'))
        else:
            print "Incorrect line :\n%s" % l
    f.close ()

def main ():
    try:
        subtitles_file = sys.argv[1]
        package_file = sys.argv[2]
    except:
        print "Syntax: %s subtitles-file package-file" % sys.argv[0]
        sys.exit (1)

    print "Converting subtitles from %s to package %s..." % (subtitles_file,
                                                             package_file)
    # FIXME: autodetect the format
    
    p = Package (uri="", source="file:subtitles.xml")
    microdvd (subtitles_file, p)
    p.save (as=package_file)
    

if __name__ == '__main__':
    main ()
