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
name="Motioncell detection filter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from math import isinf, isnan

from advene.util.gstimporter import GstImporter

def register(controller=None):
    controller.register_importer(MotionCellImporter)
    return True

class MotionCellImporter(GstImporter):
    name = _("Motion cell detection")

    def __init__(self, *p, **kw):
        super(MotionCellImporter, self).__init__(*p, **kw)

        ## Internal data structures
        self.buffer = [ ]
        self.sensitivity = 1.0
        self.is_finalized = False

        self.optionparser.add_option("-s", "--sensitivity",
                                     action="store", type="float", dest="sensitivity", default=self.sensitivity,
                                     help=_("Sensitivity [0..1]"))
        self.buffer_list = []
        self.min = 0
        self.max = 0
        self.count = 100
        # Time of the first buffer sample
        self.first_item_time = 0
        self.buffer = []
        self.lastval = 0

    def generate_normalized_annotations(self):
        n = 1.0 * len(self.buffer_list)
        if self.max - self.min == 0:
            # Constant value. We will then generate a single 0 value
            factor = 0
        else:
            factor = 100.0 / (self.max - self.min)
        m = self.min
        self.progress(0, _("Generating annotations"))
        for i, tup in enumerate(self.buffer_list):
            self.progress(i / n)
            self.convert( [ {
                'begin': tup[0],
                'end': tup[1],
                'content': " ".join("%.02f" % (factor * (f - m)) for f in tup[2]),
            } ])

    def do_finalize(self):
        # Add last buffer data
        if self.buffer:
            # There is some data left.
            pos = self.get_current_position() or (self.first_item_time + 100)
            self.buffer_list.append((self.first_item_time,
                                     pos,
                                     list(self.buffer)))
        self.generate_normalized_annotations()
        return True

    def do_process_message(self, message, bus):
        if message.get_name() == 'motion':
            pos = self.get_current_position()
            if not self.buffer:
                self.first_item_time = pos

            # motion seems to be a constantly increasing value
            # val = message['motion'] or message['motion_begin']
            # Use the length of indices refs as an indicator
            val = len(message['motion_cells_indices'])
            v = val

            if isinf(v) or isnan(v):
                v = self.lastval
            if v < self.min:
                self.min = v
            elif v > self.max:
                self.max = v
            self.lastval = v
            self.buffer.append(v)
            if len(self.buffer) >= self.count:
                self.buffer_list.append((self.first_item_time, pos, list(self.buffer)))
                self.buffer = []
        return True

    def setup_importer(self, filename):
        self.ensure_new_type('motion',
                             title=_("Motion"),
                             mimetype = 'application/x-advene-values',
                             description = _("Motion"))

        return "videoconvert ! motioncells postallmotion=true gridx=32 gridy=32 sensitivity=%.02f" % self.sensitivity
