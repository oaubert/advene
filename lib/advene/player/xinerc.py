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
"""Xine interface
"""

import socket
import re
import os
import time

import advene.util.spawn as spawn
import Image

class StreamInformation:
    def __init__(self):
        self.streamstatus=None
        self.url=""
        self.position=0
        self.length=0

class RGBPicture:
    def __init__ (self):
        self.width=0
        self.height=0
        self.type=0
        self.data=""
        self.date=0

class XineException(Exception):
    pass

class PlayerLauncher:
    """Launcher class.
    """
    def __init__ (self):
        """Initialize the player."""
        self.launcher = spawn.ProcessLauncher (name='xine',
                                               args=['-n'])

    def is_active (self):
        """Check if a Xine player is active.

        @return: True if the player if active.
        """
        if self.launcher and not self.launcher.is_running():
            return False
        return True

    def _start (self):
        """Run the Xine player
        """
        if not self.launcher.start ():
            raise Exception(_("Cannot start the player"))
        return

    def init (self):
        """Initialize the player.
        """
        self._start ()

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
    InitStatus=2
    EndStatus=3
    UndefinedStatus=4

    # # Exceptions
    PositionKeyNotSupported = XineException
    PositionOrigin          = XineException
    InvalidPosition         = XineException
    PlaylistException       = XineException
    InternalException       = XineException

    statusmapping={}

    def __init__(self):
        map={ 'STOP': self.EndStatus,
              'PLAY': self.PlayingStatus,
              'QUIT': self.EndStatus,
              'IDLE': self.UndefinedStatus }
        for k,v in map.iteritems():
            self.statusmapping['Current status: XINE_STATUS_'+k]=v

        self.relative_position=self.create_position(value=0,
                                                    origin=self.RelativePosition)
        self.socket=socket.socket()
        try:
            self.socket.connect(('localhost', 6789))
        except socket.error, e:
            if e[0] == 111:
                # Connection refused. Try to launch the player.
                launcher=PlayerLauncher()
                launcher.init()
                time.sleep(1)
                self.socket.connect(('localhost', 6789))
        self.fsocket=self.socket.makefile()
        l=self.fsocket.readline()
        if not "Nice to meet" in l:
            raise Exception("Error in connection to xine: %s" % l)
        print "connected: %s" % l
        l=self.get_command('identify vlc:vlc')
        print "authenticated"
        if not "has been authentified" in l:
            raise Exception("Authentication failed: %s" % l)

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
        print "xine update_status %s" % status

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
                print "******* Error : unknown status %s in xine.py" % status
        self.position_update ()

    def is_active(self):
        # FIXME: correctly implement this
        return True

    def check_player(self):
        # FIXME: correctly implement this
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.streamstatus
        self.stream_duration = s.length
        self.current_position_value = s.position

    def send_command(self, command):
        #print "sending command %s" % command
        self.socket.send(command+"\n")
        return None

    def get_command(self, command):
        """Send a command and return the one-line result."""
        self.send_command(command)
        r=self.fsocket.readline()
        return r

    def get_multiline_command(self, command):
        """Send a command and return the multiline result as a list."""
        self.send_command(command)
        res=[]
        l=self.fsocket.readline()
        while l.rstrip() != "":
            res.append(l)
            l=self.fsocket.readline()
        return res

    def get_media_position(self, origin, key):
        l=self.send_command('get position')
        m=re.search('(\d+)', l)
        if m is not None:
            val=long(m.group(1))
        else:
            val=0
        return val

    def set_media_position(self, position):
        # FIXME: convert from Position to int.
        self.send_command('seek %d' % (long(position) / 1000))

    def start(self, position):
        self.send_command('play')

    def pause(self, position):
        self.send_command('pause')

    def resume(self, position):
        self.send_command('pause')

    def stop(self, position):
        self.send_command('stop')

    def exit(self):
        self.send_command('halt')
        return

    def playlist_add_item(self, item):
        # FIXME: convert from dvd://dev/dvd to dvd:/
        i=item.replace(' ', '%20')
        self.send_command('mrl add %s' % i)

    def playlist_clear(self):
        self.send_command('playlist delete all')

    def playlist_get_list(self):
        l=self.get_multiline_command('playlist show')
        reg=re.compile('\s+\d+\s+(.+)$')
        pl=[]
        for i in l:
            m=reg.search(i)
            if m is not None:
                pl.append(m.group(1))
        return pl

    def snapshot(self, position):
        l=self.get_command('snapshot')
        m=re.search("File '(.+?)' written.", l)
        if m is not None:
            sfile=m.group(1)
            print "Snapshot is in file %s" % sfile
            p=RGBPicture()
            # Dummy values, are not used except to test
            # that their are non-zero
            p.width=42
            p.heigh=42
            p.type="PNG"
            p.date=self.current_position_value
            f=open(sfile,'r')
            p.data=f.read()
            f.close()
            os.unlink(sfile)
            return p
        return None

    def all_snapshots(self):
        return [ self.snapshot(None) ]

    def display_text (self, message, begin, end):
        print "Should caption %s" % message
        pass

    def get_stream_information(self):
        s=StreamInformation()
        s.url=''
        s.length=0
        s.position=0
        s.streamstatus=Player.UndefinedStatus

        l=self.get_multiline_command('playlist show')
        re=re.compile('\*>\s+\d+\s+(.+)$')
        v=[ re.search(i).group(1)
            for i in l
            if re.search(i) ]
        if len(v) == 1:
            s.url=v[0]

        l=self.get_command('get length')
        number=re.compile('(\d+)')
        m=number.search(l)
        if m:
            s.length=long(m.group(1))
        else:
            s.length=0

        p=self.get_command('get position')
        m=number.search(p)
        if m:
            s.position=long(m.group(1))
        else:
            s.position=0

        # get status is broken in xine v.0.99.1 and always returns
        # XINE_STATUS_STOP
        #s.streamstatus=self.statusmapping[self.get_command('get status').strip()]
        s.streamstatus=self.PlayingStatus

        return s

    def sound_get_volume(self):
        # FIXME: Normalize volume to be in [0..100]
        l=self.get_command('get audio volume')
        vol=0
        m=re.search('(\d+)', l)
        if m is not None:
            vol=long(m.group(1))
        return vol

    def sound_set_volume(self, v):
        # FIXME: Normalize volume to be in [0..100]
        self.send_command('set audio volume ' + str(v))
