#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2023 Olivier Aubert <contact@olivieraubert.net>
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
name="DTMF Tone detector"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from statistics import median

from gi.repository import Gst

from advene.util.gstimporter import GstImporter

def register(controller=None):
    controller.register_importer(DTMFImporter)
    return True

class DTMFImporter(GstImporter):
    name = _("DTMF Tone detector")

    def __init__(self, *p, **kw):
        super().__init__(*p, **kw)

        ## Internal data structures
        self.buffer = []
        self.max_duration = 500
        self.optionparser.add_option("-m", "--max-duration",
                                     action="store", type="int", dest="max_duration", default=self.max_duration,
                                     help=_("Maximum duration of tones."))

    def do_finalize(self):
        # Process the structure (position, number) structure to
        # create a plausible durations
        # We assume sequences
        def plausible_end(b1, b2):
            if b2 - b1 < self.max_duration:
                return b2 - 1
            else:
                return b1 + self.max_duration
        segments = [ (b1, plausible_end(b1, b2), n1)
                     for (b1, n1), (b2, n2) in zip(self.buffer, self.buffer[1:])
                    ]
        if len(self.buffer) > 1:
            # Last tone has not been output yet.
            # Define it using median duration from previous samples.
            duration = median( (end - begin) for begin, end, content in segments )
            last = self.buffer[-1]
            segments.append( (last[0], last[0] + duration, last[1]) )
        self.convert( { 'begin': begin,
                        'end': end,
                        'content': number }
                      for begin, end, number in segments )

    def do_process_message(self, message, bus=None):
        if message.get_name() == 'dtmf-event':
            # dtmf-event does not have any timestamp information.
            # Get it from the player
            position = self.pipeline.query_position(Gst.Format.TIME)[1] / Gst.MSECOND
            self.buffer.append( (position, message['number'] ) )
        return True

    def setup_importer(self, filename):
        # gst-launch-1.0 -m uridecodebin uri=file://$(pwd)/xemotion.wav  ! audioconvert ! audiorate ! audioresample ! dtmfdetect ! autoaudiosink
        self.ensure_new_type('dtmf',
                             title=_("DTMF code"),
                             description=_("DTMF signals"))
        return "audioconvert ! audioresample ! dtmfdetect"
