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
"""Dummy player interface.

This dummy player can be used to test the Advene GUI without any player dependency.

It also presents the API that should be implemented by alternative players.
"""

name="Dummy video player"

import logging
logger = logging.getLogger(__name__)

from time import time

import advene.core.config as config

def register(controller):
    controller.register_player(Player)
    return True

class StreamInformation:
    def __init__(self):
        self.status=None
        self.url=""
        self.position=0
        self.length=0

def debug(f):
    def wrapper(*param, **kwd):
        logger.debug("%s %s %s", f.__name__, " ".join(str(p) for p in param), " ".join("%s=%s" % (k, str(v)) for (k, v) in kwd.items()))
        return f(*param, **kwd)
    return wrapper

class Player:
    player_id='dummy'
    player_capabilities=[ 'seek', 'pause', 'caption', 'svg', 'frame-by-frame', 'set-rate', 'svg' ]

    # Status
    PlayingStatus=0
    PauseStatus=1
    InitStatus=2
    EndStatus=3
    UndefinedStatus=4

    def __init__(self):
        self.videofile = None
        self.relative_position = 0
        self.status=Player.UndefinedStatus
        self.basetime = None
        self.pausetime = None
        self.volume = 50
        self.mute_volume = None
        self.stream_duration = 0
        self.position_update()

    def current_position(self):
        if self.pausetime is not None:
            return self.pausetime
        elif self.basetime is None:
            return 0
        else:
            return time() * 1000 - self.basetime

    def dvd_uri(self, title=None, chapter=None):
        return "dvd@%s:%s" % (str(title),
                              str(chapter))

    def is_playing(self):
        """Is the player in Playing or Paused status?
        """
        s = self.get_stream_information ()
        return s.status == self.PlayingStatus or s.status == self.PauseStatus

    def log(self, *m):
        logger.warn(" ".join(str(i) for i in m))

    def get_position(self, origin=None, key=None):
        return self.current_position()

    @debug
    def set_position(self, position=0):
        self.basetime = time() * 1000 - position
        if self.pausetime is not None:
            self.pausetime = time() * 1000 - self.basetime
        return

    @debug
    def start(self, position = 0):
        self.status = Player.PlayingStatus
        self.basetime = time() * 1000 - position
        self.pausetime = None

    @debug
    def pause(self, position=0):
        if self.status == Player.PlayingStatus:
            self.pausetime = time() * 1000 - self.basetime
            self.status = Player.PauseStatus
        else:
            self.status = Player.PlayingStatus
            self.basetime = time() * 1000 - (self.pausetime or 0)
            self.pausetime = None

    @debug
    def resume(self, position=0):
        if self.status == Player.PlayingStatus:
            self.pausetime = time() * 1000 - self.basetime
            self.status = Player.PauseStatus
        else:
            self.status=Player.PlayingStatus
            self.basetime = time() * 1000 - (self.pausetime or 0)
            self.pausetime = None

    @debug
    def stop(self, position=0):
        self.status = Player.UndefinedStatus
        self.basetime = None
        self.pausetime = None

    @debug
    def exit(self):
        self.log("exit")

    @debug
    def set_uri(self, item):
        self.videofile = item
        # Simulate a 30 minutes movie
        self.stream_duration = 30 * 60000
        return self.get_video_info()

    def get_uri(self):
        return self.videofile

    @debug
    def get_video_info(self):
        """Return information about the current video.
        """
        return {
            'uri': self.get_uri(),
            'framerate_denom': 1,
            'framerate_num': config.data.preferences['default-fps'],
            'width': 640,
            'height': 480,
            'duration': self.stream_duration,
        }

    @debug
    def snapshot(self):
        return None

    @debug
    def display_text (self, message, begin, end):
        pass

    def get_stream_information(self):
        s = StreamInformation()
        s.url = self.get_uri()
        s.length = self.stream_duration
        s.position = self.get_position()
        s.status = self.status
        return s

    def sound_get_volume(self):
        return self.volume

    @debug
    def sound_set_volume(self, v):
        self.volume = v

    @debug
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
        if position is None:
            position = 0

        if status == "start" or status == "seek" or status == "seek_relative":
            self.position_update()
            if status == "seek_relative":
                position = self.current_position() + position
            if self.status in (self.EndStatus, self.UndefinedStatus):
                self.start(position)
            self.set_position(position)
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

    @debug
    def check_player(self):
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.status
        self.stream_duration = s.length
        self.current_position_value = s.position

    @debug
    def set_visual(self, xid):
        """Set the window id for the video output.

        It is widget.get_window().xid on X, widget.get_window().handle on Win32.
        """
        return True

    def restart_player(self):
        return True

    @debug
    def sound_mute(self):
        if self.mute_volume is None:
            self.mute_volume=self.sound_get_volume()
            self.sound_set_volume(0)
        return

    @debug
    def sound_unmute(self):
        if self.mute_volume is not None:
            self.sound_set_volume(self.mute_volume)
            self.mute_volume=None
        return

    def sound_is_muted(self):
        return (self.mute_volume is not None)
