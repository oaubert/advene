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
"""VLC player control through CORBA.

Note: as the rest of the application is CORBA-agnostic, we should not
expose anything CORBA-specific to the application. That is why the
constants are redefined as class attributes, and the create_position
method is provided to build the adequate Position instances.

"""

import time
import sys

import advene.core.config as config

from gettext import gettext as _

import ORBit, CORBA
ORBit.load_typelib (config.data.typelib)
import VLC

import advene.util.spawn as spawn

class PlayerLauncher:
    """Launcher class.

    @ivar orb: the CORBA ORB
    @ivar mc: the VLC.MediaControl object
    @ivar launcher: the launcher object
    @type launcher: spawn.ProcessLauncher
    @ivar ior: the MediaControl's IOR
    @type ior: string
    """
    def __init__ (self, config=None):
        """Initialize the player."""
        if config is None:
            raise Exception ("PlayerLauncher needs a Config object")
        self.config=config
        # FIXME: to remove once the port to win32 is done
        if config.os == 'win32':
            self.launcher=None
        else:
            args=[ '--intf', 'corba' ]
            args.extend(config.player_args)
            self.launcher = spawn.ProcessLauncher (name=config.player['name'],
                                                   args=args,
                                                   path=config.path['vlc'])
        self.orb=None
        self.mc=None
        self.ior=None

    def is_active (self):
        """Check if a VLC player is active.

        @return: True if the player if active."""
        if self.mc is None:
            return False

        if self.launcher and not self.launcher.is_running():
            return False

        try:
            if self.mc._non_existent ():
                return False
        except:
            pass

        # The process is active, but the CORBA plugin may not be
        # active.
        if os.access (self.config.iorfile, os.R_OK):
            return True
        return False

    def _start (self):
        """Run the VLC player and wait for the iorfile creation.

        @raise Exception: exception raised if the IOR file cannot be read
                          after config.data.orb_max_tries tries
        @return: the IOR of the VLC player
        @rtype: string
        """
        if not self.launcher:
            return "Dummy IOR (for the moment)"
        args=[ '--intf', 'corba' ]
        args.extend(config.data.player_args)
        if not self.launcher.start (args):
            raise Exception(_("Cannot start the player"))
        ior=""
        iorfile=self.config.iorfile
        tries=0
        while tries < self.config.orb_max_tries:
            try:
                ior = open(iorfile).readline()
                break
            except:
                tries=tries+1
                time.sleep(1)
        if ior == "":
            raise Exception (_("Cannot read the IOR file %s") % iorfile)
        return ior

    def init (self):
        """Initialize the ORB and the VLC.MediaControl.

        Return a tuple (orb, mc) once the player is initialized. We
        try multiple times to access the iorfile before quitting.

        @raise Exception: exception raised if we could not get a valid
                          VLC.MediaControl
        @return: (orb, mc)
        @rtype: tuple
        """

        iorfile=self.config.iorfile

        if self.orb is None:
            self.orb = CORBA.ORB_init()

        # First try: the player may already be active
        ior=""
        try:
            ior = open(iorfile).readline()
        except:
            pass

        if ior == "":
            # No IOR file was present. We try to launch the player
            ior = self._start ()

        mc = self.orb.string_to_object(ior)

        if mc._non_existent ():
            # The remote object is not available.
            # We remove the obsolete iorfile and try again
            try:
                os.unlink (iorfile)
            except:
                pass
            
            ior=self._start ()

            mc = self.orb.string_to_object(ior)
            if mc._non_existent ():
                raise Exception (_("Unable to get a MediaControl object."))

        self.mc=mc
        self.ior=ior
        return (self.orb, self.mc)

    def stop(self):
        """Cleanly stop the player."""
        if self.mc is not None:
            try:
                self.mc.exit ()
            except Exception, e:
                print _("Got exception %s when stopping launcher.") % str(e)
                import code
                e, v, tb = sys.exc_info()
                code.traceback.print_exception (e, v, tb)
        self.mc=None
        self.ior=None

    def restart (self):
        """Cleanly restart the player."""
        self.stop ()
        time.sleep (1)
        return self.init ()

class Player(object):
    """Wrapper class for a VLC.MediaControl object.

    It provides some helper methods, and forwards other requests to
    the VLC.MediaControl object.

    @ivar launcher: the process launcher
    @type launcher: spawn.ProcessLauncher
    @ivar orb: the ORB used to communicate with the player
    @type orb: CORBA ORB
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
        except AttributeError:
            self.check_player()
            return self.mc.__getattribute__ (name)

    def is_active (self):
        """Checks whether the player is active.

        @return: True if the player process is active.
        @rtype: boolean
        """
        return self.launcher.is_active()

    def stop_player(self):
        """Stop the player."""
        self.launcher.stop()

    def restart_player (self):
        """Restart (cleanly) the player."""
        self.orb, self.mc = self.launcher.restart ()

    def exit (self):
        self.stop_player()

    def check_player (self):
        if self.mc is None or not self.is_active ():
            self.orb, self.mc = self.launcher.init ()
            mediafile = self.get_default_media()
            if mediafile is not None and mediafile != "":
                if isinstance(mediafile, unicode):
                    mediafile=mediafile.encode('utf8')
                self.mc.playlist_add_item (mediafile)

    def get_default_media (self):
        """Return the default media path (used when starting the player).

        This method should be overriden by the mediacontrol parent.
        """
        return None

    def __init__ (self):
        """Wrapper initialization.
        """
        self.launcher = PlayerLauncher (config.data)
        self.orb = None
        self.mc = None
        #self.orb, self.mc = self.launcher.init ()

        # 0 relative position
        pos = self.create_position(value=0,
                                   key=VLC.MediaTime,
                                   origin=VLC.RelativePosition)
        self.relative_position = pos

        self.status = VLC.UndefinedStatus
        # Current position value (updated by self.position_update ())
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
        if status == "start" or status == "set":
            if position is None:
                position=self.create_position(value=0,
                                              origin=VLC.AbsolutePosition,
                                              key=VLC.MediaTime)
            elif not isinstance(position, VLC.Position):
                p=long(position)
                position=self.create_position(value=p,
                                              origin=VLC.AbsolutePosition,
                                              key=VLC.MediaTime)
            self.check_player ()
            self.position_update()
            if self.status in (VLC.EndStatus, VLC.UndefinedStatus):
                self.mc.start (position)
            else:
                self.mc.set_media_position (position)
        else:
            if position is None:
                position = self.relative_position
            elif not isinstance(position, VLC.Position):
                p=long(position)
                position=self.create_position(value=p,
                                              origin=VLC.RelativePosition,
                                              key=VLC.MediaTime)
            if status == "pause":
                self.check_player ()
                self.position_update()
                if self.status == VLC.PlayingStatus:
                    self.mc.pause (position)
                elif self.status == VLC.PauseStatus:
                    self.mc.resume (position)
            elif status == "resume":
                self.check_player()
                self.mc.resume (position)
            elif status == "stop":
                self.check_player()
                self.mc.stop (position)
            elif status == "" or status == None:
                pass
            else:
                print "******* Error : unknown status %s in mediacontrol.py" % status

        self.position_update ()

    def position_update (self):
        """Updates the current status information."""
        if self.mc is not None:
            try:
                s = self.mc.get_stream_information ()
            except CORBA.COMM_FAILURE, e:
                raise self.InternalException(e)
            self.status = s.streamstatus
            self.stream_duration = s.length
            self.current_position_value = s.position
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

    def dvd_uri(self, title, chapter):
        return "dvdsimple:///dev/dvd@%s:%s" % (str(title), str(chapter))
    
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
        p.value = value
        return p
