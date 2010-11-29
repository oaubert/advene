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

name="Audio segmentation importer"

from gettext import gettext as _

import os
import urllib

import gobject
import gst

import advene.core.config as config
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(CutterImporter)
    return True

class CutterImporter(GenericImporter):
    name = _("Audio segmentation")

    def __init__(self, *p, **kw):
        super(CutterImporter, self).__init__(*p, **kw)

        self.threshold = -25
        self.channel = 'both'
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
        if message.type == gst.MESSAGE_EOS:
            self.end_callback()
            gobject.idle_add(lambda: self.pipeline.set_state(gst.STATE_NULL) and False)
        elif message.type == gst.MESSAGE_STATE_CHANGED:
            old, new, pending = message.parse_state_changed()
            if old == gst.STATE_READY and new == gst.STATE_PAUSED:
                # There has been a problem. Cancel.
                self.progress(1.0, _("Problem when running detection"))
                print "Undetermined problem when running silence detection."
                self.end_callback()
                gobject.idle_add(lambda: self.pipeline.set_state(gst.STATE_NULL) and False)
            #if new == gst.STATE_NULL:
            #    self.end_callback()
        elif message.structure:
            s=message.structure
            #print "MSG " + bus.get_name() + ": " + s.to_string()
            if s.get_name() == 'progress' and self.progress is not None:
                if not self.progress(s['percent-double'] / 100, _("Detected %d segments") % self.statistics['annotation']):
                    gobject.idle_add(lambda: self.pipeline.set_state(gst.STATE_NULL) and False)
                    self.end_callback()
            elif s.get_name() == 'cutter':
                t = s['timestamp'] / gst.MSECOND
                if s['above']:
                    self.last_above = t
                else:
                    if self.last_above is not None:
                        self.convert([ {
                                    'content': 'sound',
                                    'begin': self.last_above,
                                    'end': t,
                                    } ])
                    else:
                        print "Error: not above without matching above"
                    self.last_above = t
        return True

    def async_process_file(self, filename, end_callback):
        self.end_callback = end_callback

        at = self.ensure_new_type('sound_segment', title=_("Sound segment"))
        at.setMetaData(config.data.namespace_prefix['dc'], "description", _("Sound segmentation with a threshold of %(threshold)d dB - channel: %(channel)s") % self.__dict__)
        
        # Build pipeline
        self.pipeline = gst.parse_launch('uridecodebin name=decoder ! audiopanorama method=1 panorama=%d ! audioconvert ! cutter threshold-dB=%s ! progressreport silent=true update-freq=1 name=report ! fakesink' % (self.channel_mapping[self.channel], str(self.threshold)))
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
            self.decoder.props.uri = 'file:' + urllib.pathname2url(os.path.abspath(unicode(filename)))
        else:
            self.decoder.props.uri = 'file://' + os.path.abspath(unicode(filename))
        self.progress(.1, _("Starting silence detection"))
        self.pipeline.set_state(gst.STATE_PLAYING)
        return self.package
