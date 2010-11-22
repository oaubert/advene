#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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

name="Sound enveloppe importer"

from gettext import gettext as _

import os
import sys
import urllib
import gobject
import gst

import advene.core.config as config
from advene.util.importer import GenericImporter
try:
    from math import isinf, isnan
except ImportError:
    # python <= 2.5
    def isnan(f):
        return repr(f) == 'nan'
    isinf = isnan

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
        self.min = sys.maxint
        self.max = -sys.maxint
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
        factor = 100.0 / (self.max - self.min)
        m = self.min
        self.progress(0, _("Generating annotations"))
        for i, tup in enumerate(self.buffer_list):
            self.progress(i / n)
            self.convert( [ {
                        'begin': tup[0],
                        'end': tup[1],
                        'content': " ".join("%.02f" % (factor * (f -m)) for f in tup[2]),
                        } ])

    def on_bus_message(self, bus, message):
        def finalize():
            pos = self.pipeline.query_position(gst.FORMAT_TIME)[0] / gst.MSECOND
            gobject.idle_add(lambda: self.pipeline.set_state(gst.STATE_NULL) and False)
            # Add last buffer data
            self.buffer_list.append((self.first_item_time, pos, list(self.buffer)))
            self.generate_normalized_annotations()
            self.end_callback()
            return True

        if message.type == gst.MESSAGE_EOS:
            finalize()
        elif message.structure:
            s=message.structure
            #print "MSG " + bus.get_name() + ": " + s.to_string()
            if s.get_name() == 'progress' and self.progress is not None:
                if not self.progress(s['percent-double'] / 100):
                    finalize()
            elif s.get_name() == 'level':
                if not self.buffer:
                    self.first_item_time = s['stream-time'] / gst.MSECOND
                rms = s['rms']
                v = rms[0]
                if len(rms) > 1:
                    if self.channel == 'right':
                        v = rms[1]
                    elif self.channel == 'both':
                        v = (rms[0] + rms[1]) / 2
                if isinf(v) or isnan(v):
                    v = self.lastval
                if v < self.min:
                    self.min = v
                elif v > self.max:
                    self.max = v
                self.lastval = v
                self.buffer.append(v)
                if len(self.buffer) >= self.count:
                    self.buffer_list.append((self.first_item_time, s['endtime'] / gst.MSECOND, list(self.buffer)))
                    self.buffer = []
        return True

    def async_process_file(self, filename, end_callback):
        self.end_callback = end_callback

        at = self.ensure_new_type('sound_enveloppe', title=_("Sound enveloppe"))
        at.mimetype = 'application/x-advene-values'
        at.setMetaData(config.data.namespace_prefix['dc'], "description", _("Sound enveloppe"))

        # Build pipeline
        self.pipeline = gst.parse_launch('uridecodebin name=decoder ! audioconvert ! level name=level interval=%s ! progressreport silent=true update-freq=1 name=report ! fakesink' % str(self.interval * gst.MSECOND))
        self.decoder = self.pipeline.get_by_name('decoder')
        bus = self.pipeline.get_bus()
        # Enabling sync_message_emission will in fact force the
        # self.progress call from a thread other than the main thread,
        # which surprisingly works better ATM.
        bus.enable_sync_message_emission()
        bus.connect('sync-message', self.on_bus_message)
        bus.connect('message', self.on_bus_message)

        if config.data.os == 'win32':
            self.decoder.props.uri = 'file:' + urllib.pathname2url(os.path.abspath(filename))
        else:
            self.decoder.props.uri = 'file://' + os.path.abspath(filename)
        self.progress(0, _("Extracting sound enveloppe"))
        self.pipeline.set_state(gst.STATE_PLAYING)
        return self.package
