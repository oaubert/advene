#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2009 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
"""VLC access using the python ctypes-based module.
"""

import advene.core.config as config
import os

try:
    import advene.player.vlc as vlc
except ImportError:
    vlc=None

name="VLC-ctypes video player"

def register(controller=None):
    if vlc is None:
        return False
    controller.register_player(Player)
    return True

if vlc is not None:
    # Shortcut used for get_stream_information
    MediaTime=vlc.PositionKey.MediaTime

    # We store Status information as int, so that it is hashable
    PlayingStatus=vlc.PlayerStatus.PlayingStatus.value
    PauseStatus=vlc.PlayerStatus.PauseStatus.value
    InitStatus=vlc.PlayerStatus.InitStatus.value
    EndStatus=vlc.PlayerStatus.EndStatus.value
    UndefinedStatus=vlc.PlayerStatus.UndefinedStatus.value

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
        AbsolutePosition=vlc.PositionOrigin.AbsolutePosition
        RelativePosition=vlc.PositionOrigin.RelativePosition
        ModuloPosition=vlc.PositionOrigin.ModuloPosition

        ByteCount=vlc.PositionKey.ByteCount
        SampleCount=vlc.PositionKey.SampleCount
        MediaTime=vlc.PositionKey.MediaTime

        # Status
        PlayingStatus=vlc.PlayerStatus.PlayingStatus.value
        PauseStatus=vlc.PlayerStatus.PauseStatus.value
        InitStatus=vlc.PlayerStatus.InitStatus.value
        EndStatus=vlc.PlayerStatus.EndStatus.value
        UndefinedStatus=vlc.PlayerStatus.UndefinedStatus.value

        # Exceptions
        PositionKeyNotSupported=vlc.MediaControlException
        PositionOriginNotSupported=vlc.MediaControlException
        InvalidPosition=vlc.MediaControlException
        class PlaylistException(Exception):
            pass
        class InternalException(Exception):
            pass
        
    def __getattribute__ (self, name):
        """
        Use the defined method if necessary. Else, forward the request
        to the mc object
        """
        #print "********************** Getattr", name
        try:
            return object.__getattribute__ (self, name)
        except AttributeError, e:
            return self.mc.__getattribute__ (name)
            raise self.InternalException(e)

    def fullscreen(self, connect=None):
        self.mc.set_fullscreen(True)
        return True

    def playlist_add_item(self, name):
        self.mc.set_mrl(name)

    def playlist_clear(self):
        self.mc.set_mrl('')

    def playlist_get_list(self):
        return [ self.mc.get_mrl() ]

    def is_active (self):
        """Checks whether the player is active.

        @return: True if the player process is active.
        @rtype: boolean
        """
        return True

    def stop_player(self):
        """Stop the player."""
        return

    def get_player_args (self):
        """Build the VLC player argument list.

        @return: the list of arguments
        """
        args=[]
        filters=[]

        args.append( '--intf=dummy' )

        if os.path.isdir(config.data.path['plugins']):
            args.append( '--plugin-path=%s' % config.data.path['plugins'] )
        if config.data.player['verbose'] is not None:
            args.append ('--verbose')
            args.append (config.data.player['verbose'])
        if config.data.player['vout'] != 'default':
            args.append( '--vout=%s' % config.data.player['vout'] )
        if config.data.player['svg']:
            args.append( '--text-renderer=svg' )
        if config.data.player['bundled']:
            args.append( '--no-plugins-cache' )
        if filters != []:
            # Some filters have been defined
            args.append ('--vout-filter=%s' %":".join(filters))
        #print "player args", args
        return [ str(i) for i in args ]
    
    def restart_player (self):
        """Restart (cleanly) the player."""
        del self.mc

        self.args=self.get_player_args()

        print "Before MC instanciation"
        self.mc = vlc.MediaControl( self.args )
        print "After MC instanciation"

        # 0 relative position
        pos = vlc.MediaControlPosition ()
        pos.origin = self.RelativePosition
        pos.key = self.MediaTime
        pos.value = 0
        self.relative_position = pos

        self.dvd_device = config.data.player['dvd-device']

        # Attributes updated by self.position_update
        self.status = UndefinedStatus
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
        print "update_status", status

        if status == "start":
            if position is None:
                position=self.create_position(0, self.MediaTime, self.AbsolutePosition)
            elif not isinstance(position, vlc.MediaControlPosition):
                p=long(position)
                position=self.create_position(p, self.MediaTime, self.AbsolutePosition)
            self.check_player ()
            self.mc.start(position)
            # Workaround for the unstable position parameter handling by start
            self.mc.set_media_position(position)
        else:
            if position is None:
                position = self.relative_position
            elif not isinstance(position, vlc.MediaControlPosition):
                p=long(position)
                position=self.create_position(p, self.MediaTime, self.AbsolutePosition)
            if status == "pause":
                self.check_player ()
                if self.status == PlayingStatus:
                    self.mc.pause ()
                elif self.status == PauseStatus:
                    self.mc.resume ()
            elif status == "resume":
                self.check_player()
                if self.status == PauseStatus:
                    self.mc.resume ()
                else:
                    self.mc.start (position)
            elif status == "stop":
                self.check_player()
                if not self.status in (EndStatus, UndefinedStatus):
                    self.mc.stop ()
            elif status == "set":
                self.check_player()
                if self.status in (EndStatus, UndefinedStatus):
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
        mc=getattr(self, 'mc', None)
        if mc is not None:
            try:
                s = mc.get_stream_information(MediaTime)
            except Exception, e:
                print "Exception", str(e)
                raise self.InternalException(str(e))
            # Make sure we store the (python) value of the status
            self.status = s.status.value
            self.stream_duration = s.length
            self.current_position_value = s.position
            self.url=s.url
            # FIXME: the returned values are wrong just after a player start
            # (pressing Play button)
            # Workaround for now:
            # If the duration is larger than 24h, then set it to 0
            if self.stream_duration > 86400000:
                self.stream_duration = 0
                self.current_position_value = 0
        else:
            self.status = UndefinedStatus
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
            key=self.MediaTime
        if origin is None:
            origin=self.AbsolutePosition
        p = vlc.MediaControlPosition ()
        p.origin = origin
        p.key = key
        p.value=long(value)
        return p

    def check_player(self):
        return True

    def snapshot(self, position):
        # Do not update the snapshot if we are not playing
        if self.status != PlayingStatus:
            return None
        # FIXME: dirty hack to workaround a bug in VLC snapshot
        # functionality (unstability of the GUI when taking a snapshot
        # < 100ms)
        if (self.current_position_value <= 100 and
            (config.data.os == 'win32' or config.data.os == 'darwin')):
            print "Snapshots <=100ms dropped"
            return None
        s=self.mc.snapshot(position)
        return s

    def set_visual(self, xid):
        if xid:
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
