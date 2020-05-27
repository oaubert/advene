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
name="Generic Gstreamer AV processing importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import os

from gi.repository import GObject
from gi.repository import Gst

import advene.core.config as config
from advene.util.importer import GenericImporter
from advene.util.tools import path2uri

class GstImporter(GenericImporter):
    """GstImporter - Gstreamer importer

    This plugin implements a generic API for importing data from
    Gstreamer pipelines. The imported data can be obtained either from
    gstreamer elements' messages, or from the frames themselves.

    The principle is to define your own processing pipeline, as a
    parse_launch string, without specifying either source or sink
    (which are setup by the plugin). You return this string by
    overriding the setup_importer() method.

    You can then either override `do_process_message` to get messages
    from elements (and generate data from them), or implement the
    `process_frame` method, which will then be called with the
    processed frame (which can be anything - video, audio... -
    depending on your pipeline) as parameter (python dict).

    The `do_finalize` method can be defined to implement any necessary
    postprocessing/cleanup. Since the `process_frame` should not take
    too much time to execute, it is a good idea to buffer annotation
    data, and call the `.convert` method only in the `do_finalize`
    method.

    You can see examples of usage in the `plugins.soundenveloppe`
    plugin (for audio, using Gstreamer message metadata) and
    `plugins.dominantcolor` (for video, using frame data).
    """
    name = _("GStreamer generic importer")

    def __init__(self, *p, **kw):
        super(GstImporter, self).__init__(*p, **kw)

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in config.data.video_extensions:
            return 80
        return 0

    def finalize(self):
        # Data finalization (EOS or user break):
        # stop pipeline, convert last buffered elements...
        GObject.idle_add(lambda: self.pipeline.set_state(Gst.State.NULL) and False)
        logger.warning("finalize")
        def wrapper():
            if hasattr(self, 'do_finalize'):
                self.do_finalize()
            self.end_callback()
            return False
        # Make sure finalize is called in the context of the main thread
        GObject.idle_add(wrapper)

    def on_bus_message_error(self, bus, message):
        s = message.get_structure()
        if s is None:
            return True
        title, message = message.parse_error()
        logger.error("%s: %s", title, message)
        return True

    def on_bus_message_warning(self, bus, message):
        s = message.get_structure()
        if s is None:
            return True
        title, message = message.parse_warning()
        logger.warning("%s: %s", title, message)
        return True

    def do_process_message(self, message):
        """Custom message handling.
        """
        return True

    def on_bus_message(self, bus, message):
        s = message.get_structure()
        if message.type == Gst.MessageType.EOS:
            self.finalize()
        elif s:
            logger.debug("MSG %s: %s", bus.get_name(), s.to_string())
            if s.get_name() == 'progress' and self.progress is not None:
                progress = s['percent-double'] / 100
                if not self.progress(progress, self.progress_message(progress, message)):
                    self.finalize()
            else:
                self.do_process_message(s)
        return True

    def setup_importer(self, filename):
        """Setup a new import session:
        - initialize annotation type/package
        - return the pipeline elements (apart from decoder and sink) as parse_launch string
        """
        self.ensure_new_type('imported_data', title=_("Imported data"))
        return "identity"

    def progress_message(self, progress, message):
        """Return a meaningful progress message
        """
        return "Processed %d%% of the video - %s" % (100 * progress, message)

    #def process_frame(self, frame):
    #    """Frame process method
    #    It will be called for each output frame, with a dict containing
    #      data: bytes, date: dts, pts: pts
    #    """
    #    return True

    def async_process_file(self, filename, end_callback):
        self.end_callback = end_callback

        sink = 'fakesink name=sink'
        if hasattr(self, 'process_frame'):
            # Note: we know that at this point in time the notifysink
            # has been defined, since it is used by the snapshotter.
            sink = 'notifysink name=sink'

        pipeline_elements = self.setup_importer(filename)

        # Build pipeline
        # Required elements:
        # - decoder -> uridecodebin
        # - report -> if present, it is expected to be a progressreport element
        self.pipeline = Gst.parse_launch(" ! ".join(['uridecodebin name=decoder',
                                                     pipeline_elements,
                                                     'progressreport silent=true update-freq=1 name=report',
                                                     sink]))
        self.decoder = self.pipeline.get_by_name('decoder')
        self.report = self.pipeline.get_by_name('report')
        self.sink = self.pipeline.get_by_name('sink')
        bus = self.pipeline.get_bus()
        if hasattr(self, 'process_frame'):
            self.sink.props.notify = self.process_frame

        # Enabling sync_message_emission will in fact force the
        # self.progress call from a thread other than the main thread,
        # which surprisingly works better ATM.
        bus.enable_sync_message_emission()
        bus.connect('sync-message', self.on_bus_message)
        bus.connect('message', self.on_bus_message)
        bus.connect('message::error', self.on_bus_message_error)
        bus.connect('message::warning', self.on_bus_message_warning)

        self.decoder.props.uri = path2uri(filename)
        self.progress(.1, _("Starting processing"))

        if hasattr(self, 'pipeline_postprocess'):
            self.pipeline_postprocess(self.pipeline)

        self.pipeline.set_state(Gst.State.PLAYING)
        return self.package
