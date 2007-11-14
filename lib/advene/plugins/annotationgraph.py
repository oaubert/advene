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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

# AnnotationGraph importer.

name="AnnotationGraph importer"

from gettext import gettext as _

import sets

import advene.core.config as config
from advene.util.importer import GenericImporter
import advene.util.ElementTree as ET

def register(controller=None):
    controller.register_importer(AnnotationGraphImporter)
    return True

XLINKURI='http://www.w3.org/1999/xlink'
AGURI='http://www.ldc.upenn.edu/atlas/ag/'
def tag(n):
    return ET.QName(AGURI, n)

class AnnotationGraphImporter(GenericImporter):
    name = _("AnnotationGraph importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.ag'):
            return 100
        elif fname.endswith('.xml'):
            return 30
        return 0
    can_handle=staticmethod(can_handle)
    
    def process_file(self, filename, dest=None):
        f=open(filename, 'r')
        tree=ET.parse(f)
        root=tree.getroot()

        p, at=self.init_package(filename=dest,
                                schemaid='ag', annotationtypeid=None)
        self.package=p

        video=root.find('%s/%s' % (tag('Timeline'), tag('Signal')))
        if video is not None:
            mediafile=video.attrib[ET.QName(XLINKURI, 'href')]
            p.setMetaData(config.data.namespace, 'mediafile', mediafile)
        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package
        
    def iterator(self, root):
        schema=self.package.get_element_by_id('ag')
        if root.tag != tag('AGSet'):
            print "Invalid AnnotationGraph file format: ", root.tag
            return
        
        # Import anchors
        self.anchors={}
        for anchor in root.findall('%s/%s' % (tag('AG'), tag('Anchor'))):
            # FIXME: in multisignal version, use the appropriate signal
            if anchor.attrib['unit'] != 'milliseconds':
                print "Unhandled anchor unit (", anchor.attrib['unit'], ") Positioning will be wrong."
            self.anchors[anchor.attrib['id']]=long(anchor.attrib['offset'])
        ats={}
        attribs={}

        progress=0.01
        self.progress(progress)
        l=root.findall('%s/%s' % (tag('AG'), tag('Annotation')))
        incr=0.98/len(l)
        for an in l:
            progress += incr
            self.progress(progress)
            t=an.attrib['type']
            if not t in ats:
                ats[t]=self.create_annotation_type (schema, t)
            at=ats[t]
            
            attribnames=attribs.setdefault(an.attrib['type'], sets.Set())
            content="\n".join( [ "%s=%s" % (f.attrib['name'], f.text)
                                 for f in an.findall(str(tag('Feature'))) ] )
            attribnames.update([ f.attrib['name'] for f in an.findall(tag('Feature')) ])
            
            yield {
                'id': an.attrib['id'],
                'type': at,
                'content': content,
                'begin': self.anchors[an.attrib['start']],
                'end': self.anchors[an.attrib['end']],
                }

        for typename, atnames in attribs.iteritems():
            if len(atnames) == 1:
                n=list(atnames)[0]
                # Only 1 attribute name. Define an appropriate
                # representation for the type.
                at=ats[typename]
                at.setMetaData(config.data.namespace, 'representation', 'here/content/parsed/' + n)
                at.mimetype='application/x-advene-structured'
                self.controller.notify('AnnotationTypeEditEnd', annotationtype=at)
        self.progress(1.0)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = AnnotationGraphImporter()

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    print "Converting %s to %s using %s" % (fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    print i.statistics_formatted()
