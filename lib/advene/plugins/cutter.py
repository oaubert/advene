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
name="Audio segmentation importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from gi.repository import Gst

from advene.util.gstimporter import GstImporter

def register(controller=None):
    controller.register_importer(CutterImporter)
    return True

class CutterImporter(GstImporter):
    name = _("Audio segmentation")

    def __init__(self, *p, **kw):
        super(CutterImporter, self).__init__(*p, **kw)

        ## Setup attributes
        self.threshold = -25
        self.channel = 'both'
        self.min_silence_duration = 0
        self.channel_mapping = {
            'both': 0,
            'left': -1,
            'right': 1,
            }

        ## Corresponding optionparser object definition
        self.optionparser.add_option("-t", "--threshold",
                                     action="store", type="int", dest="threshold", default=self.threshold,
                                     help=_("Volume threshold (in dB, can be negative) before trigger."))
        self.optionparser.add_option("-c", "--channel",
                                     action="store", type="choice", dest="channel", choices=("both", "left", "right"), default=self.channel,
                                     help=_("Channel selection."))
        self.optionparser.add_option("-s", "--silence-duration",
                                     action="store", type="int", dest="min_silence_duration", default=self.min_silence_duration,
                                     help=_("Length (in ms) of drop below threshold before silence is detected"))

        ## Internal data structures
        self.buffer = []
        self.last_above = None

    def do_finalize(self):
        self.convert( { 'begin': begin,
                        'end': end,
                        'content': 'sound' }
                      for begin, end in self.buffer )

    def do_process_message(self, message):
        if message.get_name() == 'cutter':
            t = message['timestamp'] / Gst.MSECOND
            if message['above']:
                self.last_above = t
            else:
                if self.last_above is not None:
                    self.buffer.append( (self.last_above, t) )
                else:
                    logger.error("Error: not above without matching above")
                self.last_above = t
        return True

    def setup_importer(self, filename):
        at = self.ensure_new_type('sound_segment',
                                  title=_("Sound segment"),
                                  description=_("Sound segmentation with a threshold of %(threshold)d dB - channel: %(channel)s") % self.__dict__)

        return "audioconvert ! audiopanorama method=1 panorama=%d ! audioconvert ! cutter threshold-dB=%s run-length=%d" % (self.channel_mapping[self.channel], str(self.threshold), self.min_silence_duration * Gst.MSECOND)
