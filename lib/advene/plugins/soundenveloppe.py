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
import logging
logger = logging.getLogger(__name__)

name="Sound enveloppe importer"

from gettext import gettext as _

import sys
from gi.repository import Gst

from advene.util.gstimporter import GstImporter

from math import isinf, isnan

def register(controller=None):
    controller.register_importer(SoundEnveloppeImporter)
    return True

class SoundEnveloppeImporter(GstImporter):
    name = _("Sound enveloppe")

    def __init__(self, *p, **kw):
        super(SoundEnveloppeImporter, self).__init__(*p, **kw)

        ## Setup attributes
        # Interval in ms at which to take samples
        self.interval = 100
        # Max. number of samples in an annotation
        self.count = 1000
        self.channel = 'both'
        self.value = 'peak'

        # Lower bound for db values, to avoid a too large value range
        self.lower_db_limit = -80

        ## Corresponding optionparser object definition
        self.optionparser.add_option("-i", "--interval",
                                     action="store", type="int", dest="interval", default=self.interval,
                                     help=_("Interval (in ms) at which to take samples."))
        self.optionparser.add_option("-n", "--number-of-samples",
                                     action="store", type="int", dest="count", default=self.count,
                                     help=_("Maximum number of samples per annotation."))
        self.optionparser.add_option("-c", "--channel",
                                     action="store", type="choice", dest="channel", choices=("both", "left", "right"), default=self.channel,
                                     help=_("Channel selection."))
        self.optionparser.add_option("-v", "--value",
                                     action="store", type="choice", dest="value", choices=("rms", "peak"), default=self.channel,
                                     help=_("Value to consider (peak or RMS)."))
        self.optionparser.add_option("-l", "--lower-db-limit",
                                     action="store", type="int", dest="lower_db_limit", default=self.lower_db_limit,
                                     help=_("Lower dB limit"))

        ## Internal data structures
        self.buffer = []
        self.buffer_list = []
        self.min = sys.maxsize
        self.max = -sys.maxsize
        self.first_item_time = 0
        # initial value (in dB).
        self.lastval = self.lower_db_limit

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
            self.buffer_list.append((self.first_item_time,
                                     self.first_item_time + len(self.buffer) * self.interval,
                                     list(self.buffer)))
        self.generate_normalized_annotations()
        return True

    def do_process_message(self, message):
        if message.get_name() == 'level':
            if not self.buffer:
                self.first_item_time = message['stream-time'] / Gst.MSECOND

            val = message[self.value]
            v = val[0]
            if len(val) > 1:
                if self.channel == 'right':
                    v = val[1]
                elif self.channel == 'both':
                    v = (val[0] + val[1]) / 2
            if isinf(v) or isnan(v):
                v = self.lastval
            if v < self.lower_db_limit:
                v = self.lower_db_limit
            if v < self.min:
                self.min = v
            elif v > self.max:
                self.max = v
            self.lastval = v
            self.buffer.append(v)
            if len(self.buffer) >= self.count:
                self.buffer_list.append((self.first_item_time, message['endtime'] / Gst.MSECOND, list(self.buffer)))
                self.buffer = []
        return True

    def setup_importer(self, filename):
        self.ensure_new_type('sound_enveloppe',
                             title=_("Sound enveloppe"),
                             mimetype = 'application/x-advene-values',
                             description = _("Sound enveloppe"))

        return "audioconvert ! level name=level interval=%s" % str(self.interval * Gst.MSECOND)
