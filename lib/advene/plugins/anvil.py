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

# Anvil importer.

name="Anvil importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import advene.core.config as config
from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ET

def register(controller=None):
    controller.register_importer(AnvilImporter)
    return True

class AnvilImporter(GenericImporter):
    name = _("Anvil importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.anvil'):
            return 100
        elif fname.endswith('.xml'):
            return 30
        return 0

    def process_file(self, filename):
        tree=ET.parse(filename)
        root=tree.getroot()

        p, at=self.init_package(filename=filename,
                                schemaid='anvil', annotationtypeid=None)
        video=root.find('head/video')
        if video is not None:
            mediafile=video.attrib['src']
            p.setMedia(mediafile)
        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package

    def iterator(self, root):
        schema = self.package.get_element_by_id('anvil')
        if root.tag != 'annotation':
            logger.error("Invalid Anvil file format: %s", root.tag)
            return

        progress = 0.01
        self.progress(progress)
        tracks = root.findall('.//track')
        type_incr = 0.98 / len(tracks)
        for track in tracks:
            at = self.create_annotation_type (schema, track.attrib['name'])
            self.progress(value=progress, label="Converting " + at.id)
            attribnames = set()
            elements = track.findall('.//el')
            el_incr = type_incr / len(elements)
            for el in elements:
                progress += el_incr
                self.progress(progress)
                content = "\n".join( [ "%s=%s" % (a.attrib['name'], a.text)
                                     for a in el.findall('attribute') ] )
                attribnames.update([ a.attrib['name'] for a in el.findall('attribute') ])
                yield {
                    'type': at,
                    'content': content,
                    'begin': int(float(el.attrib['start']) * 1000),
                    'end': int(float(el.attrib['end']) * 1000),
                    }
            if len(attribnames) == 1:
                n = list(attribnames)[0]
                # Only 1 attribute name. Define an appropriate
                # representation for the type.
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

    i = AnvilImporter()

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    logger.info("Converting %s to %s using %s", fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    logger.info(i.statistics_formatted())
