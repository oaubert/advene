#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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

# AnnotationGraph importer.

name="AnnotationGraph importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import advene.core.config as config
from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ET

def register(controller=None):
    controller.register_importer(AnnotationGraphImporter)
    return True

XLINKURI='http://www.w3.org/1999/xlink'
AGURI='http://www.ldc.upenn.edu/atlas/ag/'
def tag(n):
    return ET.QName(AGURI, n)

class AnnotationGraphImporter(GenericImporter):
    name = _("AnnotationGraph importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.ag'):
            return 100
        elif fname.endswith('.xml'):
            return 30
        return 0

    def process_file(self, filename, dest=None):
        tree=ET.parse(filename)
        root=tree.getroot()

        p, at=self.init_package(filename=dest,
                                schemaid='ag', annotationtypeid=None)
        self.package=p

        video=root.find('%s/%s' % (tag('Timeline'), tag('Signal')))
        if video is not None:
            mediafile=video.attrib[ET.QName(XLINKURI, 'href')]
            p.setMedia(mediafile)
        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package

    def iterator(self, root):
        schema=self.package.get_element_by_id('ag')
        if root.tag != tag('AGSet'):
            logger.error("Invalid AnnotationGraph file format: %s", root.tag)
            return

        # Import anchors
        self.anchors={}
        for anchor in root.findall('%s/%s' % (tag('AG'), tag('Anchor'))):
            # FIXME: in multisignal version, use the appropriate signal
            if anchor.attrib['unit'] != 'milliseconds':
                logger.error("Unhandled anchor unit (%s) Positioning will be wrong.", anchor.attrib['unit'])
            self.anchors[anchor.attrib['id']]=int(anchor.attrib['offset'])
        ats = {}
        attribs = {}

        progress = 0.01
        self.progress(progress)
        annotations = root.findall('%s/%s' % (tag('AG'), tag('Annotation')))
        incr = 0.98/len(annotations)
        for an in annotations:
            progress += incr
            self.progress(progress)
            t = an.attrib['type']
            if t not in ats:
                ats[t] = self.create_annotation_type (schema, t)
            at = ats[t]

            attribnames = attribs.setdefault(an.attrib['type'], set())
            content = "\n".join( [ "%s=%s" % (f.attrib['name'], f.text)
                                   for f in an.findall(str(tag('Feature'))) ] )
            attribnames.update([ f.attrib['name'] for f in an.findall(tag('Feature')) ])

            yield {
                'id': an.attrib['id'],
                'type': at,
                'content': content,
                'begin': self.anchors[an.attrib['start']],
                'end': self.anchors[an.attrib['end']],
                }

        for typename, atnames in attribs.items():
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
    logging.basicConfig(level=logging.DEBUG)
    import sys
    if len(sys.argv) < 3:
        logger.error("Should provide a file name and a package name")
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = AnnotationGraphImporter()

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    logger.info("Converting %s to %s using %s", fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    logger.info(i.statistics_formatted())
