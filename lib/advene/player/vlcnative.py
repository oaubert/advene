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
"""VLC access using the native python module.
"""

import advene.core.config as config

try:
    import vlc
except ImportError:
    vlc=None

name="VLC video player"

def register(controller=None):
    if vlc is None:
        return False
    controller.register_player(Player)
    return True

class Snapshot:
    def __init__(self, d=None):
        if d is not None:
            for k in ('width', 'height', 'data', 'type', 'date'):
                try:
                    setattr(self, k, d[k])
                except KeyError:
                    setattr(self, k, None)

class Player(object):
    """Wrapper class for a native vlc.MediaControl object.

    It provides some helper methods, and forwards other requests to
    the vlc.MediaControl object.

    @ivar mc: the vlc.MediaControl player
    @type mc: vlc.MediaControl

    @ivar relative_position: a predefined position (0-relative)
    @type relative_position: vlc.Position

    Status attributes :

    @ivar current_position_value: the current player position (in ms)
    @type current_position_value: int
    @ivar stream_duration: the current stream duration
    @type stream_duration: long
    @ivar status: the player's current status
    @type status: vlc.Status
    """
    player_id='vlc'
    player_capabilities=[ 'seek', 'pause', 'caption', 'svg' ]

    if vlc is not None:
        # Class attributes
        AbsolutePosition=vlc.AbsolutePosition
        RelativePosition=vlc.RelativePosition
        ModuloPosition=vlc.ModuloPosition

        ByteCount=vlc.ByteCount
        SampleCount=vlc.SampleCount
        MediaTime=vlc.MediaTime

        # Status
        PlayingStatus=vlc.PlayingStatus
        PauseStatus=vlc.PauseStatus
        ForwardStatus=vlc.ForwardStatus
        BackwardStatus=vlc.BackwardStatus
        InitStatus=vlc.InitStatus
        EndStatus=vlc.EndStatus
        UndefinedStatus=vlc.UndefinedStatus

        # Exceptions
        PositionKeyNotSupported=vlc.PositionKeyNotSupported
        PositionOriginNotSupported=vlc.PositionOriginNotSupported
        InvalidPosition=vlc.InvalidPosition
        PlaylistException=vlc.PlaylistException
        InternalException=vlc.InternalException

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

    def playlist_add_item(self, name):
        try:
            self.mc.playlist_add_item(name)
        except AttributeError:
            self.mc.set_mrl(name)

    def playlist_clear(self):
        try:
            self.mc.playlist_clear()
        except AttributeError:
            self.mc.set_mrl('')

    def playlist_get_list(self):
        try:
            return self.mc.playlist_get_list()
        except AttributeError:
            return [ self.mc.get_mrl(name) ]

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

        self.args=config.data.get_player_args()

        self.mc = vlc.MediaControl( self.args )

        # 0 relative position
        pos = vlc.Position ()
        pos.origin = vlc.RelativePosition
        pos.key = vlc.MediaTime
        pos.value = 0
        self.relative_position = pos


        self.dvd_device = config.data.player['dvd-device']

        # Attributes updated by self.position_update
        self.status = vlc.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 0

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
        self.mc=None
        self.mute_volume=None
        self.restart_player()

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
        @type position: vlc.Position
        """
        if status == "start":
            if position is None:
                position = vlc.Position ()
                position.origin = vlc.AbsolutePosition
                position.key = vlc.MediaTime
                position.value = 0
            elif not isinstance(position, vlc.Position):
                p=long(position)
                position = vlc.Position ()
                position.origin = vlc.AbsolutePosition
                position.key = vlc.MediaTime
                position.value = p
            self.check_player ()
            self.mc.start (position)
            # Workaround for the unstable position parameter handling by start
            self.mc.set_media_position (position)
        else:
            if position is None:
                position = self.relative_position
            elif not isinstance(position, vlc.Position):
                p=long(position)
                position = vlc.Position ()
                position.origin = vlc.AbsolutePosition
                position.key = vlc.MediaTime
                position.value = p
            if status == "pause":
                self.check_player ()
                if self.status == vlc.PlayingStatus:
                    self.mc.pause (position)
                elif self.status == vlc.PauseStatus:
                    self.mc.resume (position)
            elif status == "resume":
                self.check_player()
                if self.status == vlc.PauseStatus:
                    self.mc.resume (position)
                else:
                    self.mc.start (position)
            elif status == "stop":
                self.check_player()
                if not self.status in (vlc.EndStatus, vlc.UndefinedStatus):
                    self.mc.stop (position)
            elif status == "set":
                self.check_player()
                if self.status in (vlc.EndStatus, vlc.UndefinedStatus):
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
                s = self.mc.get_stream_information (vlc.MediaTime)
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
            self.status = vlc.UndefinedStatus
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
        @type key: vlc.Key
        @param origin: the Position origin
        @type origin: vlc.Origin
        @return: a position
        @rtype: vlc.Position
        """
        if key is None:
            key=vlc.MediaTime
        if origin is None:
            origin=vlc.AbsolutePosition
        p = vlc.Position ()
        p.origin = origin
        p.key = key
        p.value=long(value)
        return p

    def check_player(self):
        return True

    def snapshot(self, position):
        # Do not update the snapshot if we are not playing
        if self.status != self.PlayingStatus:
            return None
        # FIXME: dirty hack to workaround a bug in VLC snapshot
        # functionality (unstability of the GUI when taking a snapshot
        # < 100ms)
        if (self.current_position_value <= 100 and
            (config.data.os == 'win32' or config.data.os == 'darwin')):
            print "Snapshots <=100ms dropped"
            return None
        d=self.mc.snapshot(position)
        return Snapshot(d)

    def set_visual(self, xid):
        self.mc.set_visual(xid)

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
