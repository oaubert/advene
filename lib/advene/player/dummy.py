"""Dummy player interface
"""

class StreamInformation:
    def __init__(self):
        self.streamstatus=None
        self.url=""
        self.position=0
        self.length=0
        
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
        self.status=Player.UndefinedStatus
        self.position_update()
        pass

    def log(self, *p):
        print "Dummy player: %s" % p
        
    def get_media_position(self, origin, key):
        self.log("get_media_position")
        return 0

    def set_media_position(self, position):
        self.log("set_media_position %s" % str(position))
        return
    
    def start(self, position):
        self.log("start %s" % str(position))
        self.status=Player.PlayingStatus

    def pause(self, position): 
        self.log("pause %s" % str(position))
        if self.status == Player.PlayingStatus:
            self.status=Player.PauseStatus
        else:
            self.status=Player.PlayingStatus

    def resume(self, position):
        self.log("resume %s" % str(position))
        if self.status == Player.PlayingStatus:
            self.status=Player.PauseStatus
        else:
            self.status=Player.PlayingStatus

    def stop(self, position): 
        self.log("stop %s" % str(position))
        self.status=Player.UndefinedStatus

    def exit(self):
        self.log("exit")
    
    def playlist_add_item(self, item):
        self.playlist.append(item)

    def playlist_clear(self):
        del self.playlist[:]
        
    def playlist_get_list(self):
        return self.playlist[:]

    def snapshot(self, position):
        self.log("snapshot %s" % str(position))
        return None

    def all_snapshots(self):
        self.log("all_snapshots %s" % str(position))
        return [ None ]
    
    def display_text (self, message, begin, end):
        self.log("display_text %s" % str(message))

    def get_stream_information(self):
        s=StreamInformation()
        s.url=''
        if self.playlist:
            s.url=self.playlist[0]
        s.length=0
        s.position=0
        s.streamstatus=self.status
        return s

    def sound_get_volume(self):
        return 0

    def sound_set_volume(self, v):
        self.log("sound_set_volume %s" % str(v))

    # Helper methods
    def create_position (self, value=0, key=None, origin=None):
        """Create a Position.
        """
        return value

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
        print "dummy update_status %s" % status
        
        if status == "start" or status == "set":
            if position is None:
                position=0
            else:
                position=long(position)
            self.position_update()
            if self.status in (self.EndStatus, self.UndefinedStatus):
                self.start(position)
            else:
                self.set_media_position(position)
        else:
            if position is None:
                position = 0
            else:
                position=long(position)

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
                print "******* Error : unknown status %s in dummy player" % status
        self.position_update ()

    def is_active(self):
        # FIXME: correctly implement this
        return True

    def check_player(self):
        # FIXME: correctly implement this
        print "check player"
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.streamstatus
        self.stream_duration = s.length
        self.current_position_value = s.position
