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

Based on gst >= 1.0 API.
"""
import logging
logger = logging.getLogger(__name__)

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
    from gi.repository import Gst
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
        self.streamstatus=None
        self.url=""
        self.position=0
        self.length=0

class Position:
    def __init__(self, value=0):
        self.value=value
        # See Player attributes below...
        self.origin=0
        self.key=2

    def __str__(self):
        return "Position " + str(self.value)

class PositionKeyNotSupported(Exception):
    pass

class PositionOrigin(Exception):
    pass

class InvalidPosition(Exception):
    pass

class PlaylistException(Exception):
    pass

class InternalException(Exception):
    pass

# Placeholder
class Caption:
    pass

class Player:
    player_id='gstrecorder'
    player_capabilities=[ 'record' ]

    # Class attributes
    AbsolutePosition=0
    RelativePosition=1
    ModuloPosition=2

    ByteCount=0
    SampleCount=1
    MediaTime=2

    # Status
    PlayingStatus=0
    PauseStatus=1
    InitStatus=2
    EndStatus=3
    UndefinedStatus=4

    PositionKeyNotSupported=Exception("Position key not supported")
    PositionOriginNotSupported=Exception("Position origin not supported")
    InvalidPosition=Exception("Invalid position")
    PlaylistException=Exception("Playlist error")
    InternalException=Exception("Internal player error")

    def __init__(self):
        self.mute_volume=None

        self.player=None
        self.pipeline=None
        self.videofile=time.strftime("/tmp/advene_record-%Y%m%d-%H%M%S.ogg")
        self.build_pipeline()

        self.status=Player.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 0 # 60 * 60 * 1000
        self.relative_position=self.create_position(0,
                                                    origin=self.RelativePosition)
        self.position_update()

    def build_pipeline(self):
        if self.videofile is None:
            return
        videofile=self.videofile
        if config.data.player['audio-record-device'] not in ('default', ''):
            audiosrc = 'alsasrc device=' + config.data.player['audio-record-device']
        else:
            audiosrc = 'alsasrc'
        videosrc='autovideosrc'
        videosink='autovideosink'

        if not config.data.player['record-video']:
            # Generate black image
            videosrc = 'videotestsrc pattern=2'

        self.pipeline=Gst.parse_launch('%(videosrc)s name=videosrc ! video/x-raw,width=352,pixel-aspect-ratio=(fraction)1/1 ! queue ! tee name=tee ! videoconvert ! theoraenc drop-frames=1 ! queue ! oggmux name=mux ! filesink location=%(videofile)s  %(audiosrc)s name=audiosrc ! audioconvert ! audiorate ! queue ! vorbisenc quality=0.5 ! mux.  tee. ! queue ! %(videosink)s name=sink sync=false' % locals())
        self.imagesink=self.pipeline.get_by_name('sink')
        self.videosrc=self.pipeline.get_by_name('videosrc')
        self.audiosrc=self.pipeline.get_by_name('audiosrc')
        self.player=self.pipeline

        # Asynchronous XOverlay support.
        bus = self.pipeline.get_bus()
        bus.enable_sync_message_emission()
        def on_sync_message(bus, message):
            s = message.get_structure()
            if s is None:
                return
            logger.warn("Sync %s", s.get_name())
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
            logger.warn("%s: %s", title, message)
            return True

        bus.connect('sync-message::element', on_sync_message)
        bus.add_signal_watch()
        bus.connect('message::error', on_bus_message_error)
        bus.connect('message::warning', on_bus_message_warning)

    def position2value(self, p):
        """Returns a position in ms.
        """
        if isinstance(p, Position):
            v=p.value
            if p.key != self.MediaTime:
                logger.error("gstrecorder: unsupported key %s", p.key)
                return 0
            if p.origin != self.AbsolutePosition:
                v += self.current_position()
        else:
            v=p
        return int(v)

    def current_status(self):
        if self.player is None:
            return self.UndefinedStatus
        st=self.player.get_state(100)[1]
        if st == Gst.State.PLAYING:
            return self.PlayingStatus
        elif st == Gst.State.PAUSED:
            return self.PauseStatus
        else:
            return self.UndefinedStatus

    def current_position(self):
        """Returns the current position in ms.
        """
        if self.player is None:
            return 0
        try:
            pos = self.player.query_position(Gst.Format.TIME)[1]
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
        logger.warn("gstrecorder: %s", str(p))

    def get_media_position(self, origin, key):
        return self.current_position()

    def set_media_position(self, position):
        # No navigation
        return

    def start(self, position=None):
        if self.current_status() == self.PlayingStatus:
            # Already started
            return
        self.videofile=time.strftime("/tmp/advene_record-%Y%m%d-%H%M%S.ogg")
        self.build_pipeline()
        if self.player is None:
            return
        self.player.set_state(Gst.State.PLAYING)

    def pause(self, position=None):
        # Ignore
        return

    def resume(self, position=None):
        # Ignore
        return

    def stop(self, position=None):
        self.stream_duration=self.current_position
        if self.player is None:
            return
        self.player.set_state(Gst.State.NULL)

    def exit(self):
        if self.player is None:
            return
        self.player.set_state(Gst.State.NULL)

    def playlist_add_item(self, item):
        if item is None:
            self.videofile=tempfile.mktemp('.ogg', 'record_')
        elif os.path.exists(item):
            # tempfile.mktemp should not be used for security reasons.
            # But the probability of a tempfile attack against Advene
            # is rather low at the time of writing this comment.
            self.videofile=tempfile.mktemp('.ogg', 'record_')
            logger.warn("%s already exists. We will not overwrite, so using %s instead ", item, self.videofile)
        else:
            self.videofile=item
        self.build_pipeline()

    def playlist_clear(self):
        self.videofile=None

    def playlist_get_list(self):
        if self.videofile is None:
            return [ ]
        else:
            return [ self.videofile  ]

    def snapshot(self, position):
        return None

    def all_snapshots(self):
        self.log("all_snapshots %s")
        return [ None ]

    def display_text (self, message, begin, end):
        self.log("Display text", message)

    def get_stream_information(self):
        s=StreamInformation()
        if self.videofile:
            s.url=''
        else:
            s.url=self.videofile

        s.position=self.current_position()
        # Round length to the nearest second. This way, the timeline
        # should correctly update.
        s.length=s.position / 1000 * 1000
        s.status=self.current_status()
        return s

    def sound_get_volume(self):
        """Get the current volume.

        The result is a long value in [0, 100]
        """
        # FIXME: should handle this properly
        return 50

    def sound_set_volume(self, v):
        return 50

    # Helper methods
    def create_position (self, value=0, key=None, origin=None):
        """Create a Position.
        """
        if key is None:
            key=self.MediaTime
        if origin is None:
            origin=self.AbsolutePosition

        p=Position()
        p.value = value
        p.origin = origin
        p.key = key
        return p

    def update_status (self, status=None, position=None):
        """Update the player status.

        Defined status:
           - C{start}
           - C{pause}
           - C{resume}
           - C{stop}
           - C{set}

        If no status is given, it only updates the value of self.status

        If C{position} is None, it will be considered as zero for the
        "start" action, and as the current relative position for other
        actions.

        @param status: the new status
        @type status: string
        @param position: the position
        @type position: long
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

    def is_active(self):
        return True

    def check_player(self):
        logger.debug("check player")
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.status
        self.stream_duration = s.length
        self.current_position_value = int(s.position)

    def set_widget(self, widget):
        self.set_visual( widget.get_id() )

    def set_visual(self, xid, realsink=None):
        if realsink is None:
            realsink = self.imagesink
        self.xid = xid
        if xid and hasattr(realsink, 'set_window_handle'):
            logger.info("Reparent " + hex(xid))
            Gdk.Display().get_default().sync()
            realsink.set_window_handle(xid)
        if hasattr(realsink.props, 'force-aspect-ratio'):
            realsink.set_property('force-aspect-ratio', True)
        return True

    def restart_player(self):
        # FIXME: destroy the previous player
        self.player.set_state(Gst.State.READY)
        # Rebuilt the pipeline
        self.build_pipeline()
        self.playlist_add_item(self.videofile)
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
        return (self.mute_volume is not None)

    def disp(self, e, indent="  "):
        l=[str(e)]
        if hasattr(e, 'elements'):
            i=indent+"  "
            l.extend( [ self.disp(c, i) for c in e.elements() ])
        return ("\n"+indent).join(l)

    def fullscreen(self, *p):
        # Not implemented
        return

