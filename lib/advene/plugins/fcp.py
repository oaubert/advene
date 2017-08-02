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

name="Final Cut Pro XML importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ET

def register(controller=None):
    controller.register_importer(XMLFCPImporter)
    return True

class XMLFCPImporter(GenericImporter):
    name = _("Final Cut Pro XML importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.xml'):
            return 80
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        tree=ET.parse(filename)
        root=tree.getroot()

        p, at = self.init_package(filename=dest,
                                schemaid='fcp', annotationtypeid='fcp_subtitle')
        at.mimetype='text/plain'
        at.title = "FCP Subtitle"

        self.at = {
            'clipitem': self.create_annotation_type(at.schema, 'fcp_clipitem', title=_("FCP clipitem")),
            'subtitle': at,
            }

        self.package=p

        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package

    def iterator(self, root):
        if root.tag != 'xmeml':
            logger.error("Invalid FCP XML file format: %s", root.tag)
            return

        progress=0.01
        self.progress(progress)

        l=root.findall('.//generatoritem')
        if l:
            self.progress(progress, _("Importing subtitles"))
            incr = 0.5 / len(l)
            for e in l:
                progress += incr
                self.progress(progress)
                invrate = 1000 / int(e.findtext('rate/timebase'))
                yield {
                    'type': self.at['subtitle'],
                    'content': "\n".join([ p.findtext('value') for p in e.findall('.//parameter') if p.findtext('parameterid').startswith('str') and p.findtext('value') ]),
                    'begin': int(e.find('in').text) * invrate,
                    'end': int(e.find('out').text) * invrate,
                    }
        else:
            progress = .5

        self.progress(progress, _("Importing clips"))
        l = root.findall('.//clipitem')
        if not l:
            self.progress(1.0, label=_("No clip"))
            return
        incr = 0.48 / len(l)
        for e in l:
            progress += incr
            self.progress(progress)
            invrate = 1000 / int(e.findtext('rate/timebase'))
            yield {
                'type': self.at['clipitem'],
                'content': "\n".join([ p.text.strip() for p in e.find('comments') if p.text and p.text.strip() ]),
                'begin': int(e.findtext('start')) * invrate,
                'end': int(e.findtext('end')) * invrate,
                }

        self.progress(1.0)
