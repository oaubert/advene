#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""VLC access using the native python module.
"""

import time

import advene.core.config as config

from gettext import gettext as _


# Alias the vlc module so that we can happily copy/paste from
# vlcorbit.py
import vlc as VLC

class Snapshot:
    def __init__(self, d=None):
        if d is not None:
            self.width=d['width']
            self.height=d['height']
            self.data=d['data']
            self.type=d['type']
#            code=self.type
#            t="%c%c%c%c" % (code & 0xff,
#                          code >> 8 & 0xff,
#                          code >> 16 & 0xff,
#                          code >> 24)
#            print "Snapshot: (%d,%d) %s" % (self.width, self.height, t)

class Player(object):
    """Wrapper class for a native vlc.MediaControl object.

    It provides some helper methods, and forwards other requests to
    the VLC.MediaControl object.

    @ivar mc: the VLC.MediaControl player
    @type mc: VLC.MediaControl

    @ivar relative_position: a predefined position (0-relative)
    @type relative_position: VLC.Position

    Status attributes :

    @ivar current_position_value: the current player position (in ms)
    @type current_position_value: int
    @ivar stream_duration: the current stream duration
    @type stream_duration: long
    @ivar status: the player's current status
    @type status: VLC.Status
    """
    # Class attributes
    AbsolutePosition=VLC.AbsolutePosition
    RelativePosition=VLC.RelativePosition
    ModuloPosition=VLC.ModuloPosition

    ByteCount=VLC.ByteCount
    SampleCount=VLC.SampleCount
    MediaTime=VLC.MediaTime

    # Status
    PlayingStatus=VLC.PlayingStatus
    PauseStatus=VLC.PauseStatus
    ForwardStatus=VLC.ForwardStatus
    BackwardStatus=VLC.BackwardStatus
    InitStatus=VLC.InitStatus
    EndStatus=VLC.EndStatus
    UndefinedStatus=VLC.UndefinedStatus
    
    # Exceptions
    PositionKeyNotSupported=VLC.PositionKeyNotSupported
    PositionOriginNotSupported=VLC.PositionOriginNotSupported
    InvalidPosition=VLC.InvalidPosition
    PlaylistException=VLC.PlaylistException
    InternalException=VLC.InternalException

    def __getattribute__ (self, name):
        """
        Use the defined method if necessary. Else, forward the request
        to the mc object
        """
        try:
            return object.__getattribute__ (self, name)
        except AttributeError, e:
            return self.mc.__getattribute__ (name)
            raise self.InternalException(e)

    def is_active (self):
        """Checks whether the player is active.

        @return: True if the player process is active.
        @rtype: boolean
        """
        return True

    def stop_player(self):
        """Stop the player."""
        return

    def restart_player (self):
        """Restart (cleanly) the player."""
        del self.mc
        self.mc = VLC.MediaControl()
        return True

    def exit (self):
        self.stop_player()

    def get_default_media (self):
        """Return the default media path (used when starting the player).

        This method should be overriden by the mediacontrol parent.
        """
        return None

    def __init__ (self):
        """Wrapper initialization.
        """
        if config.data.os == 'win32':
            args=[ "--filter", "clone", "--plugin-path", config.data.path['plugins'] ]
        else:
            args=[ "--filter", "clone" ]
        self.mc = VLC.MediaControl( args )

        # 0 relative position
        pos = VLC.Position ()
        pos.origin = VLC.RelativePosition
        pos.key = VLC.MediaTime
        pos.value = 0
        self.relative_position = pos

        o=VLC.Object(0)
        self.dvd_device = o.config_get("dvd")

        # Workaround the fact that parameter passing is broken for
        # the moment in MediaControl (stack corruption): we
        # set the options via config_set. Anyway, it is cleaner
        # this way.
        if config.data.player['snapshot']:
            o.config_set("clone-vout-list", "default,snapshot")
            w, h = config.data.player['snapshot-dimensions']
            o.config_set("snapshot-width", w)
            o.config_set("snapshot-height", h)
            o.config_set("snapshot-chroma", config.data.player["snapshot-chroma"])
                         
        o.config_set("repeat", True)
        o.config_set("loop", True)

        # For debug purposes, it can be interesting to directly
        # deal with the VLC.Object
        self.o=o

        # Current position value (updated by self.position_update ())
        self.status = VLC.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 0

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
        @type position: VLC.Position
        """
        if status == "start":
            if position is None:
                position = VLC.Position ()
                position.origin = VLC.AbsolutePosition
                position.key = VLC.MediaTime
                position.value = 0
            elif not isinstance(position, VLC.Position):
                p=long(position)
                position = VLC.Position ()
                position.origin = VLC.AbsolutePosition
                position.key = VLC.MediaTime
                position.value = p
            self.check_player ()
            self.mc.start (position)
        else:
            if position is None:
                position = self.relative_position
            elif not isinstance(position, VLC.Position):
                p=long(position)
                position = VLC.Position ()
                position.origin = VLC.AbsolutePosition
                position.key = VLC.MediaTime
                position.value = p
            if status == "pause":
                self.check_player ()
                if self.status == VLC.PlayingStatus:
                    self.mc.pause (position)
                elif self.status == VLC.PauseStatus:
                    self.mc.resume (position)                   
            elif status == "resume":
                self.check_player()
                if self.status == VLC.PauseStatus:
                    self.mc.resume (position)
                else:
                    self.mc.start (position)
            elif status == "stop":
                self.check_player()
                if not self.status in (VLC.EndStatus, VLC.UndefinedStatus):
                    self.mc.stop (position)
            elif status == "set":
                self.check_player()
                if self.status in (VLC.EndStatus, VLC.UndefinedStatus):
                    self.mc.start (position)
                else:
                    self.mc.set_media_position (position)
            elif status == "" or status == None:
                pass
            else:
                print "******* Error : unknown status %s in mediacontrol.py" % status

        self.position_update ()

    def position_update (self):
        """Updates the current status information."""
        if self.mc is not None:
            try:
                s = self.mc.get_stream_information (VLC.MediaTime)
            except:
                raise self.InternalException()
            self.status = s['status']
            self.stream_duration = s['length']
            self.current_position_value = s['position']
            self.url=s['url']
            # FIXME: the returned values are wrong just after a player start
            # (pressing Play button)
            # Workaround for now:
            # If the duration is larger than 24h, then set it to 0
            if self.stream_duration > 86400000:
                self.stream_duration = 0
                self.current_position_value = 0
        else:
            self.status = VLC.UndefinedStatus
            self.stream_duration = 0
            self.current_position_value = 0
            self.url=''

    def dvd_uri(self, title=None, chapter=None):
        if self.dvd_device is None:
            return ""
        else:
            return "dvdsimple://%s@%s:%s" % (self.dvd_device,
                                             str(title),
                                             str(chapter))

    def create_position (self, value=0, key=None, origin=None):
        """Create a Position.
        
        Returns a Position object initialized to the right value, by
        default using a MediaTime in AbsolutePosition.

        @param value: the value
        @type value: int
        @param key: the Position key
        @type key: VLC.Key
        @param origin: the Position origin
        @type origin: VLC.Origin
        @return: a position
        @rtype: VLC.Position
        """
        if key is None:
            key=VLC.MediaTime
        if origin is None:
            origin=VLC.AbsolutePosition
        p = VLC.Position ()
        p.origin = origin
        p.key = key
        p.value=long(value)
        return p

    def check_player(self):
        # FIXME: correctly implement this
        print "Check player"
        return True

    def snapshot(self, position):
        d=self.mc.snapshot(position)
        return Snapshot(d)

    def set_visual(self, xid):
        try:
            self.mc.set_visual(xid)
        except AttributeError:
            # Old vlc API. Use the old way            
            o=VLC.Object(0)
            o.set('drawable', xid)
        return
    
