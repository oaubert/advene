"""Native implementation of VLC module."""

# Définition des constantes
class PositionOrigin (int):
    pass

AbsolutePosition = PositionOrigin (0)
RelativePosition = PositionOrigin (1)
ModuloPosition   = PositionOrigin (2)

class PositionKey (int):
    pass

ByteCount   = PositionKey (0)
SampleCount = PositionKey (1)
MediaTime   = PositionKey (2)

class Position:
    def __init__(self):
        self.origin = None
        self.key = None
        self.value = None

class PositionKeyNotSupported(Exception):
    pass

class InvalidPosition(Exception):
    pass

class PlaylistSeq(list):
    pass

class ByteSeq(str):
    pass

class RGBPicture:
    def __init__ (self):
        self.width=0
        self.height=0
        self.type=0
        self.data=ByteSeq()
        self.date=0

class RGBPictureSeq(list):
    pass

class PlayerStatus (int):
    pass

PlayingStatus    = PlayerStatus (0)
PauseStatus      = PlayerStatus (1)
ForwardStatus    = PlayerStatus (2)
BackwardStatus   = PlayerStatus (3)
RewindStatus     = PlayerStatus (4)
NotStartedStatus = PlayerStatus (5)
StartStatus      = PlayerStatus (6)
UndefinedStatus  = PlayerStatus (7)

class StreamInformation:
    def __init__(self):
        self.streamstatus = NotStartedStatus
        self.url=""
        self.position=0
        self.length=840000000

class MediaControl(object):
    def __init__ (self):
        self.playlist = []
        
    def get_media_position(self, an_origin, a_key):
        p = Position ()
        p.origin = an_origin
        p.key = a_key
        p.value = 0
        return p
    
    def set_media_position(self, a_position):
        pass
     
    def start(self, a_position):
        pass

    def pause(self, a_position):
        pass
    
    def resume(self, a_position):
        pass
    
    def stop(self, a_position):
        pass

    def exit(self):
        pass

    def playlist_add_item (self, a_file):
        self.playlist.append (a_file)

    def playlist_empty(self):
        return len(self.playlist) == 0

    def playlist_get_list (self):
        return self.playlist

    def snapshot (self, a_position):
        r = RGBPicture()
        return r

    def  all_snapshots (self):
        r = RGBPicture()
        return [ r ]

    def display_text (self, message, begin, end):
        print "OSD Text (%d, %d) : %s" % (begin.value, end.value, message)

    def get_stream_information (self):
        i = StreamInformation ()
        if self.playlist:
            i.url = self.playlist[0]
        return i

    def _non_existent(self):
        return False

