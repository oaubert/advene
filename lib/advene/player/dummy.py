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

    def __init__(self):
        self.playlist=[]
        pass

    def log(self, *p):
        print "Dummy player: ", *p
        
    def get_media_position(self, origin, key):
        self.log("get_media_position")
        return 0

    def set_media_position(self, position):
        self.log("set_media_position %s" % str(position))
        return
    
    def start(self, position):
        self.log("start %s" % str(position))

    def pause(self, position): 
        self.log("pause %s" % str(position))

    def resume(self, position):
        self.log("resume %s" % str(position))

    def stop(self, position): 
        self.log("stop %s" % str(position))

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
        s.streamstatus=Player.UndefinedStatus
        return s

    def sound_get_volume(self):
        return 0

    def sound_set_volume(self, v):
        self.log("sound_set_volume %s" % str(v))
