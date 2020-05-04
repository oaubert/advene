#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2020 Olivier Aubert <contact@olivieraubert.net>
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
name="Dominant color importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from math import sqrt

import advene.core.config as config
from advene.util.gstimporter import GstImporter

def register(controller=None):
    controller.register_importer(DominantColorImporter)
    return True

class DominantColorImporter(GstImporter):
    name = _("Dominant color importer")

    def __init__(self, *p, **kw):
        super(DominantColorImporter, self).__init__(*p, **kw)

        self.buffer = []
        self.last_seen_color = None
        self.first_seen_time = 0
        self.last_seen_time = 0

    def do_finalize(self):
        # Process end, convert buffered data into annotations
        self.convert(f for f in self.buffer)

    def process_frame(self, frame):
        """Frame process method
            It will be called for each output frame, with a dict containing
            data: bytes, date: dts, pts: pts
        """
        # Pick the first pixel (ARGB format)
        c = frame['data'][1:4]
        if self.last_seen_color is None:
            self.last_seen_color = c
            self.first_seen_time = frame['date']
            return True
        lc = self.last_seen_color
        # From https://stackoverflow.com/a/9085524/2870028
        # who got it from https://www.compuphase.com/cmetric.htm:
        # typedef struct {
        #     unsigned char r, g, b;
        # } RGB;
        #
        # double ColourDistance(RGB e1, RGB e2)
        # {
        #     long rmean = ( (long)e1.r + (long)e2.r ) / 2;
        #     long r = (long)e1.r - (long)e2.r;
        #     long g = (long)e1.g - (long)e2.g;
        #     long b = (long)e1.b - (long)e2.b;
        #     return sqrt((((512+rmean)*r*r)>>8) + 4*g*g + (((767-rmean)*b*b)>>8));
        # }
        rmean = int((c[0] + lc[0]) / 2)
        r = c[0] - lc[0]
        g = c[1] - lc[1]
        b = c[2] - lc[2]
        d = sqrt((((512+rmean)*r*r)>>8) + 4*g*g + (((767-rmean)*b*b)>>8))
        if d > 20:
            # Color change. Buffer a new annotation
            self.buffer.append({
                'begin': self.first_seen_time,
                'end': self.last_seen_time,
                'content': "#" + self.last_seen_color.hex(),
            })
            self.last_seen_color = c
            self.first_seen_time = frame['date']
        self.last_seen_time = frame['date']
        return True

    def setup_importer(self, filename):
        at = self.ensure_new_type('dominant_color',
                                  title=_("Dominant color"),
                                  description=_("Dominant color"))
        at.setMetaData(config.data.namespace, "item_color", "here/content/data")

        return "videoconvert ! videoscale ! video/x-raw,width=80 ! frei0r-filter-pixeliz0r block-height=1 block_width=1 ! videoscale ! video/x-raw,format=ARGB,width=1"
