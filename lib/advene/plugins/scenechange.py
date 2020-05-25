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
name="Scenechange detection filter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from advene.util.gstimporter import GstImporter

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

def register(controller=None):
    controller.register_importer(SceneChangeImporter)
    return True

class SceneChangeImporter(GstImporter):
    name = _("Scene change detection")

    def __init__(self, *p, **kw):
        super(SceneChangeImporter, self).__init__(*p, **kw)

        ## Internal data structures
        self.buffer = [ 0 ]

    def do_finalize(self):
        self.convert({ 'begin': int(begin / Gst.MSECOND),
                       'end': int(end / Gst.MSECOND) }
                     for (begin, end) in zip(self.buffer, self.buffer[1:]))
        self.buffer = []

    def pipeline_postprocess(self, pipeline):
        def event_handler(pad, event):
            if event is not None:
                logger.debug("****** Event %s", event.get_structure().to_string())
                if event.type == Gst.EventType.STREAM_GROUP_DONE:
                    # End of stream.
                    self.finalize()
                    return None
                if event.type == Gst.EventType.CUSTOM_DOWNSTREAM:
                    s = event.get_structure()
                    if s.get_name() == 'GstForceKeyUnit':
                        # Get stream time
                        self.buffer.append(s.get_uint64('timestamp').value)
            return event
        pad = self.sink.get_static_pad('sink')
        pad.set_event_function(event_handler)

    def setup_importer(self, filename):
        at = self.ensure_new_type('scenechange',
                                  title=_("Scene change"),
                                  description = _("Scene change"))

        return "videoconvert ! videoscale ! scenechange"
