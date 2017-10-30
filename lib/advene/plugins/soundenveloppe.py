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

import os
import sys
from gi.repository import GObject
from gi.repository import Gst

import advene.core.config as config
from advene.util.importer import GenericImporter
import advene.util.helper as helper

from math import isinf, isnan

def register(controller=None):
    controller.register_importer(SoundEnveloppeImporter)
    return True

class SoundEnveloppeImporter(GenericImporter):
    name = _("Sound enveloppe")

    def __init__(self, *p, **kw):
        super(SoundEnveloppeImporter, self).__init__(*p, **kw)

        # Interval in ms at which to take samples
        self.interval = 100
        # Max. number of samples in an annotation
        self.count = 1000
        self.channel = 'both'

        # Lower bound for db values, to avoid a too large value range
        self.lower_db_limit = -80

        self.optionparser.add_option("-i", "--interval",
                                     action="store", type="int", dest="interval", default=self.interval,
                                     help=_("Interval (in ms) at which to take samples."))
        self.optionparser.add_option("-n", "--number-of-samples",
                                     action="store", type="int", dest="count", default=self.count,
                                     help=_("Maximum number of samples per annotation."))
        self.optionparser.add_option("-c", "--channel",
                                     action="store", type="choice", dest="channel", choices=("both", "left", "right"), default=self.channel,
                                     help=_("Channel selection."))

        self.buffer = []
        self.buffer_list = []
        self.min = sys.maxsize
        self.max = -sys.maxsize
        self.first_item_time = 0
        self.lastval = 0

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in config.data.video_extensions:
            return 80
        return 0
    can_handle=staticmethod(can_handle)

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

    def on_bus_message(self, bus, message):
        def finalize():
            GObject.idle_add(lambda: self.pipeline.set_state(Gst.State.NULL) and False)
            # Add last buffer data
            if self.buffer:
                # There is some data left.
                self.buffer_list.append((self.first_item_time,
                                         self.first_item_time + len(self.buffer) * self.interval,
                                         list(self.buffer)))
            self.generate_normalized_annotations()
            self.end_callback()
            return True

        s = message.get_structure()
        if message.type == Gst.MessageType.EOS:
            finalize()
        elif message.type == Gst.MessageType.ERROR:
            title, message = message.parse_error()
            logger.error("%s: %s", title, message)
        elif message.type == Gst.MessageType.WARNING:
            title, message = message.parse_warning()
            logger.warn("%s: %s", title, message)
        elif s:
            if s.get_name() == 'progress' and self.progress is not None:
                if not self.progress(s['percent-double'] / 100, _("At %s") % helper.format_time(s['current'] * 1000)):
                    finalize()
            elif s.get_name() == 'level':
                if not self.buffer:
                    self.first_item_time = s['stream-time'] / Gst.MSECOND
                rms = s['rms']
                v = rms[0]
                if len(rms) > 1:
                    if self.channel == 'right':
                        v = rms[1]
                    elif self.channel == 'both':
                        v = (rms[0] + rms[1]) / 2
                if isinf(v) or isnan(v) or v < self.lower_db_limit:
                    v = self.lastval
                if v < self.min:
                    self.min = v
                elif v > self.max:
                    self.max = v
                self.lastval = v
                self.buffer.append(v)
                if len(self.buffer) >= self.count:
                    self.buffer_list.append((self.first_item_time, s['endtime'] / Gst.MSECOND, list(self.buffer)))
                    self.buffer = []
        return True

    def async_process_file(self, filename, end_callback):
        self.end_callback = end_callback

        at = self.ensure_new_type('sound_enveloppe', title=_("Sound enveloppe"))
        at.mimetype = 'application/x-advene-values'
        at.setMetaData(config.data.namespace_prefix['dc'], "description", _("Sound enveloppe"))

        # Build pipeline
        self.pipeline = Gst.parse_launch('uridecodebin name=decoder ! audioconvert ! level name=level interval=%s ! progressreport silent=true update-freq=1 name=report ! fakesink' % str(self.interval * Gst.MSECOND))
        self.decoder = self.pipeline.get_by_name('decoder')
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
            self.decoder.props.uri = 'file://' + os.path.abspath(filename)
        self.progress(0, _("Extracting sound enveloppe"))
        self.pipeline.set_state(Gst.State.PLAYING)
        return self.package
