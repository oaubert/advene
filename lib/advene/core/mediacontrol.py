"""Abstraction for the MediaControl API, maintaining player state.
"""
import advene.core.config as config
import time

import ORBit, CORBA
ORBit.load_typelib (config.data.typelib)
import VLC
import advene.util.vlclib

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
        if self.mc is not None:
            self.mc.exit()
        self.launcher.stop()

    def restart_player (self):
        """Restart (cleanly) the player."""
        self.orb, self.mc = self.launcher.restart ()

    def exit (self):
        self.stop_player()

    def check_player (self):
        if self.mc is None or not self.is_active ():
            self.orb, self.mc = self.launcher.init ()
            m = self.get_default_media()
            if m is not None and m != "":
                self.mc.playlist_add_item (m)

    def get_default_media (self):
        """Return the default media path (used when starting the player).
        
        This method should be overriden by the mediacontrol parent.
        """
        return None
    
    def __init__ (self):
        """Wrapper initialization.
        """
        self.launcher = advene.util.vlclib.VLCPlayer (config.data)
        self.orb = None
        self.mc = None
        #self.orb, self.mc = self.launcher.init ()
        
        # 0 relative position
        pos = VLC.Position ()
        pos.origin = VLC.RelativePosition
        pos.key = VLC.MediaTime
        pos.value = 0
        self.relative_position = pos
        
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
                position.origin = VLC.RelativePosition
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
                self.mc.resume (position)
            elif status == "stop":
                self.check_player()
                self.mc.stop (position)
            elif status == "set":
                self.check_player()
                if self.status in (VLC.EndStatus, VLC.UndefinedStatus):
                    self.mc.start (position)
                else:
                    self.mc.set_media_position (position)
            elif status == "":
                pass
            else:
                print "******* Error : unknown status %s in mediacontrol.py" % status

        self.position_update ()
        
    def position_update (self):
        """Updates the current status information."""
        if self.mc is not None:
            s = self.mc.get_stream_information ()
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
