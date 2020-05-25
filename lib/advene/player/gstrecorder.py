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
"""Gstreamer recorder interface.

Using gstreamer 1.0 API.
"""
import logging
logger = logging.getLogger(__name__)

import ctypes
import math
import tempfile
import time

import advene.core.config as config

import gi
from gi.repository import GObject
GObject.threads_init()

if config.data.os == 'linux':
    from gi.repository import GdkX11
elif config.data.os == 'win32':
    gi.require_version('GdkWin32', '3.0')
    from gi.repository import GdkWin32
from gi.repository import Gdk

try:
    gi.require_version('Gst', '1.0')
    gi.require_version('GstPbutils', '1.0')
    from gi.repository import Gst
    from gi.repository import GstPbutils
    Gst.init(None)
except ImportError:
    Gst=None

import os

name="GStreamer video recorder"

def register(controller=None):
    if Gst is None:
        return False
    controller.register_player(Player)
    return True

class StreamInformation:
    def __init__(self):
        self.status=None
        self.url=""
        self.position=0
        self.length=0

# Placeholder
class Caption:
    pass

class Player:
    player_id='gstrecorder'
    player_capabilities=[ 'record' ]

    # Status
    PlayingStatus=0
    PauseStatus=1
    InitStatus=2
    EndStatus=3
    UndefinedStatus=4

    def __init__(self):
        self.mute_volume=None

        self.pipeline=None
        self.videofile = time.strftime("/tmp/advene_record-%Y%m%d-%H%M%S.ogg")
        self.build_pipeline()

        self.status=Player.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 0
        self.position_update()

    def build_pipeline(self):
        if not self.videofile:
            logger.error("Undefined videofile")
            return
        videofile=self.videofile
        if config.data.player['audio-record-device'] not in ('default', ''):
            audiosrc = 'pulsesrc device=' + config.data.player['audio-record-device']
        else:
            audiosrc = 'autoaudiosrc'
        videosrc='autovideosrc'
        videosink='autovideosink'

        if not config.data.player['record-video']:
            # Generate black image
            videosrc = 'videotestsrc pattern=2'

        pipeline_def = '%(videosrc)s name=videosrc ! tee name=tee ! queue ! videoconvert ! video/x-raw,width=352,pixel-aspect-ratio=(fraction)1/1 ! theoraenc drop-frames=1 ! queue ! oggmux name=mux ! filesink location=%(videofile)s  %(audiosrc)s name=audiosrc ! audioconvert ! audiorate ! queue ! vorbisenc quality=0.5 ! mux.  tee. ! queue ! videoconvert ! %(videosink)s name=sink sync=false' % locals()
        logger.debug("Launching pipeline %s", pipeline_def)
        self.pipeline = Gst.parse_launch(pipeline_def)
        self.imagesink = self.pipeline.get_by_name('sink')
        self.videosrc = self.pipeline.get_by_name('videosrc')
        self.audiosrc = self.pipeline.get_by_name('audiosrc')

        # Asynchronous XOverlay support.
        bus = self.pipeline.get_bus()
        bus.enable_sync_message_emission()
        def on_sync_message(bus, message):
            s = message.get_structure()
            if s is None:
                return
            logger.debug("sync message %s", s.get_name())
            if s.get_name() == 'prepare-window-handle':
                self.set_visual(self.xid, message.src)

        def on_bus_message_error(bus, message):
            s = message.get_structure()
            if s is None:
                return True
            title, message = message.parse_error()
            logger.error("%s: %s", title, message)
            return True

        def on_bus_message_warning(bus, message):
            s = message.get_structure()
            if s is None:
                return True
            title, message = message.parse_warning()
            logger.warning("%s: %s", title, message)
            return True

        bus.connect('sync-message::element', on_sync_message)
        bus.add_signal_watch()
        bus.connect('message::error', on_bus_message_error)
        bus.connect('message::warning', on_bus_message_warning)

    def current_status(self):
        if self.pipeline is None:
            return self.UndefinedStatus
        st = self.pipeline.get_state(100)[1]
        if st == Gst.State.PLAYING:
            return self.PlayingStatus
        elif st == Gst.State.PAUSED:
            return self.PauseStatus
        else:
            return self.UndefinedStatus

    def current_position(self):
        """Returns the current position in ms.
        """
        if self.pipeline is None:
            return 0
        try:
            pos = self.pipeline.query_position(Gst.Format.TIME)[1]
        except Exception:
            position = 0
        else:
            position = pos * 1.0 / Gst.MSECOND
        return position

    def dvd_uri(self, title=None, chapter=None):
        return ""

    def check_uri(self):
        return True

    def log(self, *p):
        logger.warning("gstrecorder: %s", str(p))

    def get_position(self, origin, key):
        return self.current_position()

    def set_position(self, position):
        # No navigation
        return

    def start(self, position=None):
        logger.debug("start")
        if self.current_status() == self.PlayingStatus:
            # Already started
            return
        self.videofile = time.strftime("/tmp/advene_record-%Y%m%d-%H%M%S.ogg")
        self.build_pipeline()
        if self.pipeline is None:
            return
        self.pipeline.set_state(Gst.State.PLAYING)

    def pause(self, position=None):
        # Ignore
        return

    def resume(self, position=None):
        # Ignore
        return

    def stop(self, position=None):
        self.stream_duration = self.current_position
        if self.pipeline is None:
            return
        self.pipeline.set_state(Gst.State.NULL)

    def exit(self):
        if self.pipeline is None:
            return
        self.pipeline.set_state(Gst.State.NULL)

    def set_uri(self, item):
        logger.debug("set_uri %s", item)
        if not item:
            self.videofile = tempfile.mktemp('.ogg', 'record_')
        elif os.path.exists(item):
            # tempfile.mktemp should not be used for security reasons.
            # But the probability of a tempfile attack against Advene
            # is rather low at the time of writing this comment.
            self.videofile = tempfile.mktemp('.ogg', 'record_')
            logger.warning("%s already exists. We will not overwrite, so using %s instead ", item, self.videofile)
        else:
            self.videofile = item
        self.build_pipeline()
        return self.get_video_info()

    def get_uri(self):
        return self.videofile

    def get_video_info(self):
        """Return information about the current video.
        """
        uri = self.get_uri()
        if not Gst.uri_is_valid(uri):
            # Let's try to interpret it as a filename
            uri = Gst.filename_to_uri(uri)
        d = GstPbutils.Discoverer()
        try:
            info = d.discover_uri(uri)
        except Exception as e:
            logger.error("Cannot find video info: %s", e.message)
            info = None
        default = {
            'uri': uri,
            'framerate_denom': 1,
            'framerate_num': config.data.preferences['default-fps'],
            'width': 640,
            'height': 480,
            'duration': 0,
        }
        if info is None:
            # Return default data.
            logger.warning("Could not find information about video, using absurd defaults.")
            return default
        if not info.get_video_streams():
            # Could be an audio file.
            default['duration'] = info.get_duration() / Gst.MSECOND
            return default

        stream = info.get_video_streams()[0]
        return {
            'uri': uri,
            'framerate_denom': stream.get_framerate_denom(),
            'framerate_num': stream.get_framerate_num(),
            'width': stream.get_width(),
            'height': stream.get_height(),
            'duration': info.get_duration() / Gst.MSECOND,
        }

    def snapshot(self, position):
        return None

    def display_text (self, message, begin, end):
        self.log("Display text", message)

    def get_stream_information(self):
        s=StreamInformation()
        s.url = self.get_uri()

        s.position = self.current_position()
        # Round length to the nearest second. This way, the timeline
        # should correctly update.
        s.length = math.ceil(s.position / 1000) * 1000
        s.status = self.current_status()
        return s

    def sound_get_volume(self):
        """Get the current volume.

        The result is a long value in [0, 100]
        """
        # FIXME: should handle this properly
        return 50

    def sound_set_volume(self, v):
        return 50

    def update_status (self, status=None, position=None):
        """Update the player status.

        Defined status:
           - C{start}
           - C{pause}
           - C{resume}
           - C{stop}
           - C{seek}
           - C{seek_relative}

        If no status is given, it only updates the value of self.status

        If C{position} is None, it will be considered as the current
        position.

        @param status: the new status
        @type status: string
        @param position: the position
        @type position: int
        """
        logger.debug("update_status %s %s", status, str(position))

        # We only handle "start" and "stop".
        if status == "start":
            self.position_update()
            if self.status not in (self.PlayingStatus, self.PauseStatus):
                self.start()
        elif status == "stop":
            self.stop ()
        self.position_update ()

    def is_playing(self):
        """Is the player in Playing or Paused status?
        """
        s = self.get_stream_information ()
        return s.status == self.PlayingStatus or s.status == self.PauseStatus

    def check_player(self):
        logger.debug("check player")
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.status
        self.stream_duration = s.length
        self.current_position_value = int(s.position)

    def set_widget(self, widget, container):
        handle = None

        if config.data.player['vout'] == 'gtk':
            # Special case: we use a gtk sink, so we get a Gtk widget
            # and not the XOverlay API
            try:
                container.pack_start(self.imagesink.props.widget, True, True, 0)
                self.imagesink.props.widget.show()
                widget.hide()
            except:
                logger.exception("Embedding error")
            return

        if config.data.os == "win32":
            # From
            # http://stackoverflow.com/questions/25823541/get-the-window-handle-in-pygi
            if not widget.ensure_native():
                logger.error("Cannot embed video player - it requires a native window")
                return
            ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
            ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object]
            drawingarea_gpointer = ctypes.pythonapi.PyCapsule_GetPointer(widget.__gpointer__, None)
            gdkdll = ctypes.CDLL("libgdk-3-0.dll")
            handle = gdkdll.gdk_win32_window_get_handle(drawingarea_gpointer)
        else:
            handle = widget.get_id()

        widget.show()
        self.set_visual(handle)

    def set_visual(self, xid, realsink=None):
        if realsink is None:
            realsink = self.imagesink
        self.xid = xid
        if xid and hasattr(realsink, 'set_window_handle'):
            logger.info("Reparent %s", hex(xid))
            Gdk.Display().get_default().sync()
            realsink.set_window_handle(xid)
        if hasattr(realsink.props, 'force-aspect-ratio'):
            realsink.set_property('force-aspect-ratio', True)
        return True

    def restart_player(self):
        # FIXME: destroy the previous player
        self.pipeline.set_state(Gst.State.READY)
        # Rebuild the pipeline
        self.build_pipeline()
        self.set_uri(self.videofile)
        self.position_update()
        return True

    def sound_mute(self):
        if self.mute_volume is None:
            self.mute_volume=self.sound_get_volume()
            self.sound_set_volume(0)
        return

    def sound_unmute(self):
        if self.mute_volume is not None:
            self.sound_set_volume(self.mute_volume)
            self.mute_volume=None
        return

    def sound_is_muted(self):
        return self.mute_volume is not None

    def disp(self, e, indent="  "):
        l=[str(e)]
        if hasattr(e, 'elements'):
            i=indent+"  "
            l.extend( [ self.disp(c, i) for c in e.elements() ])
        return ("\n"+indent).join(l)

    def fullscreen(self, *p):
        # Not implemented
        return
