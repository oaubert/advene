#
# This file is part of Advene.
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

# Simple MPEG7 importer. It only handles FreeTextAnnotations in simple
# segments (no TemporalDecomposition)

name="MPEG7 importer"

from gettext import gettext as _

import re
import time

import advene.core.config as config
from advene.util.importer import GenericImporter
import advene.util.ElementTree as ET

def register(controller=None):
    print "Registering ", name
    controller.register_importer(MPEG7Importer)
    # Also register time formatting global methods for MPEG7 export
    controller.register_global_method(mpeg7_time)
    controller.register_global_method(mpeg7_duration)
    return True

# Should be handled by xml.utils.iso8601.parse(repr), but it fails with
# some samples.
# Cf http://www-nlpir.nist.gov/projects/tv2005/master.shot.boundaries/time.elements
# T00:00:00:0F14112000
timepoint_regexp=re.compile('T(?P<h>\d+):(?P<m>\d+):(?P<s>\d+):(?P<ms>\d+)(F(?P<fraction>\d+))?')
# PT00H00M27S11854080N14112000
duration_regexp=re.compile('P?T(?P<h>\d+)H(?P<m>\d+)M(?P<s>\d+)S(?P<ms>\d+)(N(?P<fraction>\d+))?')

MPEG7URI='urn:mpeg:mpeg7:schema:2001'
def tag(n):
    return ET.QName(MPEG7URI, n)

class MPEG7Importer(GenericImporter):
    name = _("MPEG7 importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.mp7'):
            return 100
        elif fname.endswith('.xml'):
            return 30
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename):
        tree=ET.parse(filename)
        root=tree.getroot()

        p, at=self.init_package(filename=filename,
                                schemaid='mpeg7',
                                annotationtypeid='freetext')
        if self.package is None:
            self.package=p
            # FIXME: should specify title
            p.setMetaData (config.data.namespace, "mediafile", "dvd@1,1")
        self.defaulttype=at
        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package

    def iterator(self, root):
        if root.tag != tag('Mpeg7'):
            print "Invalid MPEG7 file format: ", root.tag
            return

        for s in (root.findall('.//%s' % tag('AudioVisualSegment'))
                  + root.findall('.//%s' % tag('VideoSegment'))
                  + root.findall('.//%s' % tag('AudioSegment'))):
            content='No content'
            tp=''
            td=''
            freetext=s.findall(".//%s" % str(tag('FreeTextAnnotation')))
            if freetext:
                content="\n".join( [ f.text for f in freetext ] )
            tp=s.findall(".//%s" % str(tag('MediaTimePoint')))
            if tp:
                tp=tp[0].text
            else:
                tp=''
            td=s.findall(".//%s" % str(tag('MediaDuration')))
            if td:
                td=td[0].text
            else:
                td=''
            # Parse timepoint and duration
            m=timepoint_regexp.search(tp)
            if m:
                d=m.groupdict()
                for k in d:
                    if d[k] is not None:
                        d[k]=long(d[k])
                if d['fraction'] is None:
                    d['fraction']=1.0
                begin=d['ms']/d['fraction']+d['s']*1000+d['m']*60000+d['h']*3600000
            else:
                begin=0
            m=duration_regexp.search(td)
            if m:
                d=m.groupdict()
                for k in d:
                    if d[k] is not None:
                        d[k]=long(d[k])
                if d['fraction'] is None:
                    d['fraction']=1.0
                duration=d['ms']/d['fraction']+d['s']*1000+d['m']*60000+d['h']*3600000
            else:
                duration=0
            yield {
                'content': content,
                'begin': begin,
                'duration': duration
                }


def mpeg7_time(target, context):
    """Formats a time (in ms) into a MPEG7-compatible representation.
    """
    return "T%s:%03dF1000" % (time.strftime("%H:%M:%S", time.gmtime(target / 1000)), target % 1000)

def mpeg7_duration(target, context):
    """Formats a duration (in ms) into a MPEG7-compatible representation.
    """
    return "PT%s%03dN1000" % (time.strftime("%HH%MM%SS", time.gmtime(target / 1000)), target % 1000)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = MPEG7Importer()

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    print "Converting %s to %s using %s" % (fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    print i.statistics_formatted()
