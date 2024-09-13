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

# ShotDetect XML output importer.

name="ShotDetect XML importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import advene.core.config as config
from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ET

def register(controller=None):
    controller.register_importer(ShotdetectImporter)
    return True

class ShotdetectImporter(GenericImporter):
    name = _("Shotdetect XML importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname == 'shotdetect':
            return 100
        elif fname.endswith('.xml'):
            return 80
        return 0

    def process_file(self, filename, dest=None):
        tree=ET.parse(filename)
        root=tree.getroot()

        p, at=self.init_package(filename=dest,
                                schemaid='shotdetect', annotationtypeid='shots')
        at.mimetype='application/x-advene-structured'
        at.setMetaData(config.data.namespace, "representation", 'here/content/parsed/num')

        self.package=p
        self.annotationtype=at

        video=root.find('content/head/media')
        if video is not None:
            mediafile=video.attrib['src']
            p.setMedia(mediafile)
        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package

    def iterator(self, root):
        if root.tag != 'shotdetect':
            logger.error("Invalid Shotdetect file format: %s", root.tag)
            return

        progress = 0.01
        self.progress(progress)

        shots = root.findall('content/body/shots/shot')
        if not shots:
            self.progress(1.0, label=_("No shots"))
            return
        incr = 0.98 / len(shots)
        for an in shots:
            progress += incr
            self.progress(progress)
            yield {
                'type': self.annotationtype,
                'content': "num=" + an.attrib['id'],
                'begin': int(an.attrib['msbegin']),
                'duration': int(an.attrib['msduration']),
                }
        self.progress(1.0)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys
    if len(sys.argv) < 3:
        logger.error("Should provide a file name and a package name")
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = ShotdetectImporter()

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    logger.info("Converting %s to %s using %s", fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    logger.info(i.statistics_formatted())
