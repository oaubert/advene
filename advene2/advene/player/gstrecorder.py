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
"""Gstreamer recorder interface.

Based on gst >= 0.10 API.
"""

import tempfile

import advene.core.config as config

import gobject
gobject.threads_init()

try:
    import pygst
    pygst.require('0.10')
    import gst
except ImportError:
    gst=None

import os
from threading import Condition

name="GStreamer video recorder"

def register(controller=None):
    if gst is None:
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
    ForwardStatus=2
    BackwardStatus=3
    InitStatus=4
    EndStatus=5
    UndefinedStatus=6

    PositionKeyNotSupported=Exception("Position key not supported")
    PositionOriginNotSupported=Exception("Position origin not supported")
    InvalidPosition=Exception("Invalid position")
    PlaylistException=Exception("Playlist error")
    InternalException=Exception("Internal player error")

    def __init__(self):
        self.mute_volume=None

        self.player=None
        self.pipeline=None
        self.videofile="/tmp/gstrecorder.mp3"
        self.build_pipeline()

        self.status=Player.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 60 * 60 * 1000
        self.relative_position=self.create_position(0,
                                                    origin=self.RelativePosition)
        self.position_update()

    def build_pipeline(self):
        if self.videofile is None:
            return
        self.pipeline=gst.parse_launch('v4l2src queue-size=4 ! video/x-raw-yuv,width=352,height=288 ! tee name=tee ! ffmpegcolorspace ! ffenc_mpeg4 bitrate=400000 ! queue ! avimux name=mux ! filesink location=%s  alsasrc device=hw:1,0 ! lame ! mux.  tee. ! queue ! xvimagesink name=sink sync=false' % self.videofile)
        #self.pipeline=gst.parse_launch('alsasrc name=source device=hw:1,0 ! lame ! filesink location=%s' % self.videofile)
        #self.player = self.pipeline.get_by_name('source')
        self.imagesink=self.pipeline.get_by_name('sink')
        self.player=self.pipeline


    def position2value(self, p):
        """Returns a position in ms.
        """
        if isinstance(p, Position):
            v=p.value
            if p.key != self.MediaTime:
                print "gstrecorder: unsupported key ", p.key
                return 0
            if p.origin != self.AbsolutePosition:
                v += self.current_position()
        else:
            v=p
        return long(v)

    def current_status(self):
        if self.player is None:
            return self.UndefinedStatus
        st=self.player.get_state()[1]
        if st == gst.STATE_PLAYING:
            return self.PlayingStatus
        elif st == gst.STATE_PAUSED:
            return self.PauseStatus
        else:
            return self.UndefinedStatus

    def current_position(self):
        """Returns the current position in ms.
        """
        if self.player is None:
            return 0
        try:
            pos, format = self.player.query_position(gst.FORMAT_TIME)
        except:
            position = 0
        else:
            position = pos * 1.0 / gst.MSECOND
        return position

    def dvd_uri(self, title=None, chapter=None):
        return ""

    def check_uri(self):
        return True

    def log(self, *p):
        print "gstrecorder player: %s" % p

    def get_media_position(self, origin, key):
        return self.current_position()

    def set_media_position(self, position):
        # No navigation
        return

    def start(self, position):
        if self.player is None:
            return
        self.player.set_state(gst.STATE_PLAYING)

    def pause(self, position):
        # Impossible to pause recording (it should be possible, but
        # gstreamer does not like it)
        return

    def resume(self, position):
        self.pause(position)

    def stop(self, position):
        if self.player is None:
            return
        self.player.set_state(gst.STATE_READY)

    def exit(self):
        if self.player is None:
            return
        self.player.set_state(gst.STATE_NULL)

    def playlist_add_item(self, item):
        if os.path.exists(item):
            # tempfile.mktemp should not be used for security reasons.
            # But the probability of a tempfile attack against Advene
            # is rather low at the time of writing this comment.
            self.videofile=tempfile.mktemp('.avi', 'record_')
            print "%s already exists. We will not overwrite, so use %s instead " % (item, self.videofile)
        else:
            self.videofile=item
        self.build_pipeline()

    def playlist_clear(self):
        self.videofile=None

    def playlist_get_list(self):
        return [ self.videofile ]

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

        duration = 60 * 60 * 1000

        s.length=duration
        s.position=self.current_position()
        s.status=self.current_status()
        return s

    def sound_get_volume(self):
        """Get the current volume.

        The result is a long value in [0, 100]
        """
        if self.player is None:
            return 0
        v = self.player.get_property('volume') * 100 / 4
        return long(v)

    def sound_set_volume(self, v):
        if self.player is None:
            return 0
        if v > 100:
            v = 100
        elif v < 0:
            v = 0
        v = v * 4.0 / 100
        self.player.set_property('volume', v)

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
        #print "gst - update_status ", status, str(position)
        if position is None:
            position=0
        else:
            position=self.position2value(position)

        if status == "start" or status == "set":
            self.position_update()
            if self.status not in (self.PlayingStatus, self.PauseStatus):
                self.start(position)
            else:
                self.set_media_position(position)
        else:
            if status == "pause":
                self.position_update()
                if self.status == self.PauseStatus:
                    self.resume (position)
                else:
                    self.pause(position)
            elif status == "resume":
                self.resume (position)
            elif status == "stop":
                self.stop (position)
            elif status == "" or status == None:
                pass
            else:
                print "******* Error : unknown status %s in gstrecorder player" % status
        self.position_update ()

    def is_active(self):
        return True

    def check_player(self):
        print "check player"
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.status
        self.stream_duration = s.length
        self.current_position_value = long(s.position)

    def set_visual(self, xid):
        self.xid = xid
        self.imagesink.set_xwindow_id(self.xid)
        self.imagesink.set_property('force-aspect-ratio', True)
        return True

    def restart_player(self):
        # FIXME: destroy the previous player
        self.player.set_state(gst.STATE_READY)
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
