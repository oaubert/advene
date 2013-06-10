#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2013 Olivier Aubert <contact@olivieraubert.net>
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

name="Youtube Annotations XML importer"

from gettext import gettext as _

from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ET
import HTMLParser

def register(controller=None):
    controller.register_importer(XMLYoutubeImporter)
    return True

class XMLYoutubeImporter(GenericImporter):
    name = _("Youtube XML annotations importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.xml'):
            return 80
        return 0
    can_handle = staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        tree = ET.parse(filename)
        root = tree.getroot()

        p, at = self.init_package(filename=dest,
                                  schemaid='youtube', annotationtypeid='transcript')
        at.mimetype = 'text/plain'
        at.title = "Youtube Transcript"

        self.package=p

        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package

    def iterator(self, root):
        parser = HTMLParser.HTMLParser()

        if root.tag != 'transcript':
            print "Invalid Youtube XML file format: ", root.tag
            return

        progress = 0.01
        self.progress(progress)

        l = root.findall('.//text')
        if l:
            self.progress(progress, _("Importing annotations"))
            incr = 1.0 / len(l)
            for e in l:
                progress += incr
                self.progress(progress)
                yield {
                    'content': parser.unescape(e.text),
                    'begin': long(float(e.attrib.get('start')) * 1000),
                    'duration': long(float(e.attrib.get('dur')) * 1000),
                    }
        else:
            progress = 1.0

        self.progress(progress)
