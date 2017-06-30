#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2016 Olivier Aubert <contact@olivieraubert.net>
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
name="Youtube XML importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ET

def register(controller=None):
    controller.register_importer(TranscriptImporter)
    return True

class TranscriptImporter(GenericImporter):
    name = _("Youtube XML importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.xml'):
            return 80
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        tree = ET.parse(filename)
        root = tree.getroot()

        p, at = self.init_package(filename=dest,
                                  annotationtypeid='transcript')
        at.mimetype='text/plain'
        at.title = "Transcript"

        self.at = at
        self.package = p
        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package

    def iterator(self, root):
        if root.tag != 'transcript':
            logger.error("Invalid Youtube XML file format: %s", root.tag)
            return

        progress=0.01
        self.progress(progress)

        l=root.findall('.//text')
        if l:
            self.progress(progress, _("Importing transcript"))
            incr = 0.5 / len(l)
            for e in l:
                progress += incr
                self.progress(progress)
                begin = int(float(e.attrib['start']) * 1000)
                end = begin + int(float(e.attrib['dur']) * 1000)
                yield {
                    'type': self.at,
                    'content': e.text,
                    'begin': begin,
                    'end': end
                    }
        else:
            progress = 1.0

        self.progress(1.0)
