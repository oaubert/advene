#! /usr/bin/python

# Subtitle to XML (advene) converter
# Converts subtitle formats to advene XML annotations

# Based on
# vlc/modules/demux/util/sub.c
# for the subtitles decoding part

import sys
import re
import time

import optparse

from advene.model.package import Package
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment

def frame2ts (f, fps=25.0, offset=0):
    """
    Converts a frame number into a timestamp in milliseconds, taking
    the offset into account.
    """
    return  long(f * 1e3 / fps) + offset

def create_annotation (package, type_, alpha, omega, data):
    """
    Creates an annotation in the package
    """
    a=package.createAnnotation(
        type=type_,
        author="sub2xml",
        date=time.strftime("%F"),
        fragment=MillisecondFragment (begin=alpha, end=omega))
    a.title=data[:20]
    a.content.data = data
    package.annotations.append(a)

def microdvd (file, p, options):
    """
    Converts the subtitles from file and put them into the package p
    """
    t = [ t for t in p.annotationTypes
          if t.id == 'subtitle-annotation' ]
    if len(t) == 1:
        type_ = t[0]
    else:
        print "Error: cannot find subtitle-annotation annotation type"
        sys.exit(1)

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
            create_annotation (p, type_,
                               frame2ts (begin, fps=options.fps, offset=options.offset),
                               frame2ts (end, fps=options.fps, offset=options.offset),
                               unicode(data, 'iso8859-1'))
        else:
            print "Incorrect line :\n%s" % l
    f.close ()

def main ():
    parser = optparse.OptionParser(usage="Usage: %prog [options] subtitles-file package-file")
    parser.add_option("-f", "--fps",
                      action="store", type="float", dest="fps", default=25.0,
                      help="Specify the fps parameter")
    parser.add_option("-o", "--offset",
                      action="store", type="int", dest="offset", default=0,
                      help="Specify the offset in ms")
    (options, args) = parser.parse_args()
    
    try:
        subtitles_file = args[0]
        package_file = args[1]
    except:
        parser.print_help()
        sys.exit (1)

    print "Converting subtitles from %s to package %s..." % (subtitles_file,
                                                             package_file)
    # FIXME: autodetect the format    
    p = Package (uri="", source="file:subtitles.xml")
    microdvd (subtitles_file, p, options=options)
    p.save (as=package_file)
    

if __name__ == '__main__':
    main ()
