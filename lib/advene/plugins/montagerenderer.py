#! /usr/bin/env python3
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
"""Montage export module.

This filter exports a list of annotations as a video montage
"""

name="Video montage renderer"
shortname = 'montagerenderer'

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib
from gi.repository import Gst
try:
    gi.require_version('GstPbutils', '1.0')
    gi.require_version('GES', '1.0')
    from gi.repository import GstPbutils
    from gi.repository import GES
    Gst.init([])
    GES.init()
except ValueError:
    GES = None

import advene.util.helper as helper

def register(controller=None):
    if GES is not None:
        controller.register_generic_feature(shortname, MontageRenderer)
    return True

class MontageRenderer:
    """Video montage exporter.
    """
    name = _("Video montage exporter")

    def __init__(self, controller, elements=None):
        self.controller = controller
        self.elements = elements
        self.progress_cb = None
        self.pipeline = None
        self.total_duration = 1

    def finalize(self):
        if self.pipeline is not None:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None

    def bus_message_cb(self, unused_bus, message):
        if message.type == Gst.MessageType.EOS:
            logger.warning("End of encoding")
            self.progress_cb(None)

    def duration_querier(self):
        if self.pipeline is None:
            self.progress_cb(None)
            return True
        pos = self.pipeline.query_position(Gst.Format.TIME)[1] / self.total_duration
        if self.progress_cb:
            self.progress_cb(pos)
        return True

    def render(self, filename, progress_callback=None):
        # Works if source is a type
        self.progress_cb = progress_callback

        # FIXME: considering single-video for the moment
        media_uri = self.controller.get_default_media()
        media_uri = helper.path2uri(media_uri)

        logger.warning("Extracting clips from %s", media_uri)
        asset = GES.UriClipAsset.request_sync(media_uri)

        timeline = GES.Timeline.new_audio_video()
        layer = timeline.append_layer()

        start_on_timeline = 0

        self.total_duration = sum(a.fragment.duration * Gst.MSECOND for a in self.elements)
        clips = []
        for a in self.elements:
            start_position_asset = a.fragment.begin * Gst.MSECOND
            duration = a.fragment.duration * Gst.MSECOND
            # GES.TrackType.UNKNOWN => add every kind of stream to the timeline
            clips.append(layer.add_asset(asset, start_on_timeline, start_position_asset,
                                         duration, GES.TrackType.UNKNOWN))
            start_on_timeline += duration

        timeline.commit()

        # Build the encoding pipeline
        pipeline = GES.Pipeline()
        pipeline.set_timeline(timeline)

        container_profile = \
            GstPbutils.EncodingContainerProfile.new("montage-profile",
                                                    "Pitivi encoding profile",
                                                    Gst.Caps("video/webm"),
                                                    None)
        video_profile = GstPbutils.EncodingVideoProfile.new(Gst.Caps("video/x-vp8"),
                                                            None,
                                                            Gst.Caps("video/x-raw"),
                                                            0)

        container_profile.add_profile(video_profile)

        audio_profile = GstPbutils.EncodingAudioProfile.new(Gst.Caps("audio/x-vorbis"),
                                                            None,
                                                            Gst.Caps("audio/x-raw"),
                                                            0)

        container_profile.add_profile(audio_profile)

        pipeline.set_render_settings(helper.path2uri(filename), container_profile)
        pipeline.set_mode(GES.PipelineFlags.RENDER)

        self.pipeline = pipeline
        logger.warning("Starting encoding")
        self.pipeline.set_state(Gst.State.PLAYING)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.bus_message_cb)
        GLib.timeout_add(300, self.duration_querier)

if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.DEBUG)
    USAGE = "%prog package_file type_name"
    if sys.argv[2:]:
        packagename = sys.argv[1]
        atype = sys.argv[2]
    else:
        logger.warning(USAGE)
        sys.exit(1)

    from advene.model.package import Package

    logger.warning("Extracting from %s - type %s", packagename, atype)
    p = Package(packagename)
    at = p.get_element_by_id(atype)

    r = MontageRenderer(None, sorted(at.annotations))

    mainloop = GLib.MainLoop()
    def pg(value):
        if value is None:
            mainloop.quit()
            return
        logging.warning("Progress %d", value)

    r.render('/tmp/montage.webm', pg)
    mainloop.run()
