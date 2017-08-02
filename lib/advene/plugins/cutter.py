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

import os

from gi.repository import GObject
from gi.repository import Gst

import advene.core.config as config
from advene.util.importer import GenericImporter
import advene.util.helper as helper

def register(controller=None):
    controller.register_importer(CutterImporter)
    return True

class CutterImporter(GenericImporter):
    name = _("Audio segmentation")

    def __init__(self, *p, **kw):
        super(CutterImporter, self).__init__(*p, **kw)

        self.threshold = -25
        self.channel = 'both'
        self.min_silence_duration = 0
        self.channel_mapping = {
            'both': 0,
            'left': -1,
            'right': 1,
            }
        self.optionparser.add_option("-t", "--threshold",
                                     action="store", type="int", dest="threshold", default=self.threshold,
                                     help=_("Volume threshold (in dB, can be negative) before trigger."))
        self.optionparser.add_option("-c", "--channel",
                                     action="store", type="choice", dest="channel", choices=("both", "left", "right"), default=self.channel,
                                     help=_("Channel selection."))
        self.optionparser.add_option("-s", "--silence-duration",
                                     action="store", type="int", dest="min_silence_duration", default=self.min_silence_duration,
                                     help=_("Length (in ms) of drop below threshold before silence is detected"))
        self.buffer = []
        self.last_above = None

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in config.data.video_extensions:
            return 80
        return 0
    can_handle=staticmethod(can_handle)

    def on_bus_message(self, bus, message):
        def finalize():
            GObject.idle_add(lambda: self.pipeline.set_state(Gst.State.NULL) and False)
            self.convert( {
                    'begin': begin,
                    'end': end,
                    'content': 'sound',
                    }
                          for begin, end in self.buffer )
            self.end_callback()
            return True

        s = message.get_structure()
        if message.type == Gst.MessageType.EOS:
            finalize()
        ##elif message.type == Gst.MessageType.STATE_CHANGED:
        ##    old, new, pending = message.parse_state_changed()
        ##    if old == Gst.State.READY and new == Gst.State.PAUSED:
        ##        # There has been a problem. Cancel.
        ##        self.progress(1.0, _("Problem when running detection"))
        ##        print "Undetermined problem when running silence detection."
        ##        self.end_callback()
        ##        GObject.idle_add(lambda: self.pipeline.set_state(Gst.State.NULL) and False)
        ##    #if new == Gst.State.NULL:
        ##    #    self.end_callback()
        elif s:
            logger.debug("MSG %s: %s", bus.get_name(), s.to_string())
            if s.get_name() == 'progress' and self.progress is not None:
                if not self.progress(s['percent-double'] / 100, _("Detected %(count)d segments until %(time)s") % { 'count': len(self.buffer),
                                                                                                                    'time': helper.format_time(s['current'] * 1000) }):
                    finalize()
            elif s.get_name() == 'cutter':
                t = s['timestamp'] / Gst.MSECOND
                if s['above']:
                    self.last_above = t
                else:
                    if self.last_above is not None:
                        self.buffer.append( (self.last_above, t) )
                    else:
                        logger.error("Error: not above without matching above")
                    self.last_above = t
        return True

    def async_process_file(self, filename, end_callback):
        self.end_callback = end_callback

        at = self.ensure_new_type('sound_segment', title=_("Sound segment"))
        at.setMetaData(config.data.namespace_prefix['dc'], "description", _("Sound segmentation with a threshold of %(threshold)d dB - channel: %(channel)s") % self.__dict__)

        # Build pipeline
        self.pipeline = Gst.parse_launch('uridecodebin name=decoder ! audioconvert ! audiopanorama method=1 panorama=%d ! audioconvert ! cutter threshold-dB=%s run-length=%d ! progressreport silent=true update-freq=1 name=report ! fakesink' % (self.channel_mapping[self.channel], str(self.threshold), self.min_silence_duration * Gst.MSECOND))
        self.decoder = self.pipeline.get_by_name('decoder')
        self.report = self.pipeline.get_by_name('report')
        bus = self.pipeline.get_bus()
        # Enabling sync_message_emission will in fact force the
        # self.progress call from a thread other than the main thread,
        # which surprisingly works better ATM.
        bus.enable_sync_message_emission()
        bus.connect('sync-message', self.on_bus_message)
        bus.connect('message', self.on_bus_message)

        if config.data.os == 'win32':
            self.decoder.props.uri = 'file:///' + os.path.abspath(str(filename))
        else:
            self.decoder.props.uri = 'file://' + os.path.abspath(str(filename))
        self.progress(.1, _("Starting silence detection"))
        self.pipeline.set_state(Gst.State.PLAYING)
        return self.package
