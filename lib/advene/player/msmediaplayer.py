"""Windows MediaPlayer interface
"""

import win32com

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
    
    # # Exceptions
    # PositionKeyNotSupported=VLC.PositionKeyNotSupported
    # PositionOriginNotSupported=VLC.PositionOriginNotSupported
    # InvalidPosition=VLC.InvalidPosition
    # PlaylistException=VLC.PlaylistException
    # InternalException=VLC.InternalException

    def __init__(self):
        self.control=win32com.client.Dispatch("MediaPlayer.MediaPlayer.1")

        # FIXME: maybe try to get the .controls attribute of the object to
        # really control it.
        
        self.control.AutoSize=1
        self.control.ShowControls=0
        self.control.autostart=0

        # MediaPlayer9: 6BF52A52-394A-11d3-B153-00C04F79FAA6
        # MediaPlayer Core:
        #w=win32com.client.Dispatch('{09428D37-E0B9-11D2-B147-00C04F79FAA6}')
        #w.launchURL('c:\\windows\\a3dspls.wav')

    def get_media_position(self, origin, key):
        # FIXME
        return 0

    def set_media_position(self, position):
        # FIXME
        return
    
    def start(self, position):
        self.control.controls.Play()

    def pause(self, position):
        self.control.controls.Pause()

    def resume(self, position):
        self.control.controls.Play()

    def stop(self, position):
        self.control.controls.Stop()

    def exit(self):
        # FIXME
        return
    
    def playlist_add_item(self, item):
        # FIXME: we maybe can use .URL
        self.control.FileName=item
        return

    def playlist_clear(self):
        self.control.FileName=""
        return
        
    def playlist_get_list(self):
        return [ self.control.FileName ]

    def snapshot(self, position):
        # FIXME
        return None
    
    def get_stream_information(self):
        s=StreamInformation()
        s.url=self.control.FileName
        s.length=self.control.duration
        s.position=self.control.????
        s.streamstatus=statusmapping(self.control.status) ???
        # FIXME
        pass
        
    def sound_get_volume(self):
        # FIXME: Normalize volume to be in [0..255]
        return self.control.volume

    def sound_set_volume(self, v):
        # FIXME: Normalize volume to be in [0..255]
        self.control.volume=v

        
        
