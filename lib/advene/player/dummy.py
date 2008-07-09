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
"""Dummy player interface.

This dummy player can be used to test the Advene GUI without any player dependency.

It also presents the API that should be implemented by alternative players.
"""

from time import time

name="Dummy video player"

def register(controller):
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

class Player:
    player_id='dummy'
    player_capabilities=[ 'seek', 'pause', 'caption', 'svg', 'frame-by-frame' ]

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

    PositionKeyNotSupported=Exception()
    PositionOriginNotSupported=Exception()
    InvalidPosition=Exception()
    PlaylistException=Exception()
    InternalException=Exception()

    def __init__(self):
        self.playlist=[]
        self.relative_position=0
        self.status=Player.UndefinedStatus
        self.basetime=None
        self.pausetime=None
        self.volume=12
        self.mute_volume=None
        self.stream_duration = 0
        self.position_update()

    def position2value(self, p):
        if isinstance(p, Position):
            v=p.value
            if p.key != self.MediaTime:
                self.log("unsupported key ", p.key)
                return 0
            if p.origin == self.AbsolutePosition:
                v=p.value
            else:
                v=self.current_position() + p.value
        else:
            v=long(p)
        return v

    def current_position(self):
        if self.pausetime:
            return self.pausetime
        elif self.basetime is None:
            return 0
        else:
            return time() * 1000 - self.basetime

    def dvd_uri(self, title=None, chapter=None):
        return "dvd@%s:%s" % (str(title),
                              str(chapter))

    def log(self, *m):
        print "dummy plugin:", " ".join([str(i) for i in m])

    def get_media_position(self, origin=None, key=None):
        self.log("get_media_position")
        return self.current_position()

    def set_media_position(self, position=0):
        position = self.position2value(position)
        self.log("set_media_position %s" % str(position))
        self.basetime = time() * 1000 - position
        self.pausetime = None
        return

    def start(self, position=0):
        self.log("start %s" % str(position))
        self.status=Player.PlayingStatus
        self.basetime=time() * 1000 - position
        self.pausetime=None

    def pause(self, position=0):
        self.log("pause %s" % str(position))
        if self.status == Player.PlayingStatus:
            self.pausetime=time() * 1000 - self.basetime
            self.status=Player.PauseStatus
        else:
            self.status=Player.PlayingStatus
            self.basetime=time() * 1000 - self.pausetime
            self.pausetime=None

    def resume(self, position=0):
        self.log("resume %s" % str(position))
        if self.status == Player.PlayingStatus:
            self.pausetime=time() * 1000 - self.basetime
            self.status=Player.PauseStatus
        else:
            self.status=Player.PlayingStatus
            self.basetime=time() * 1000 - self.pausetime
            self.pausetime=None

    def stop(self, position=0):
        self.log("stop %s" % str(position))
        self.status=Player.UndefinedStatus
        self.basetime=None
        self.pausetime=None

    def exit(self):
        self.log("exit")

    def playlist_add_item(self, item):
        self.playlist.append(item)
        # Simulate a 30 minutes movie
        self.stream_duration = 30 * 60000

    def playlist_clear(self):
        del self.playlist[:]
        self.stream_duration = 0

    def playlist_get_list(self):
        return self.playlist[:]

    def snapshot(self, position):
        self.log("snapshot %s" % str(position))
        return None

    def all_snapshots(self):
        self.log("all_snapshots")
        return [ None ]

    def display_text (self, message, begin, end):
        self.log("display_text %s" % str(message))

    def get_stream_information(self):
        s=StreamInformation()
        s.url=''
        if self.playlist:
            s.url=self.playlist[0]
        s.length=self.stream_duration
        if self.pausetime:
            s.position=self.pausetime
        elif self.basetime:
            s.position=time() * 1000 - self.basetime
        else:
            s.position=0
        s.streamstatus=self.status
        return s

    def sound_get_volume(self):
        return self.volume

    def sound_set_volume(self, v):
        self.log("sound_set_volume %s" % str(v))
        self.volume = v

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
        self.log("update_status %s" % status)

        if position is None:
            position=0
        else:
            position=self.position2value(position)

        if status == "start" or status == "set":
            self.position_update()
            if self.status in (self.EndStatus, self.UndefinedStatus):
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
                self.log("******* Error : unknown status %s")
        self.position_update ()

    def is_active(self):
        return True

    def check_player(self):
        self.log("check player")
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.streamstatus
        self.stream_duration = s.length
        self.current_position_value = s.position

    def set_visual(self, xid):
        """Set the window id for the video output.

        It is widget.window.xid on X, widget.window.handle on Win32.
        """
        return True

    def restart_player(self):
        self.log("restart player")
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
