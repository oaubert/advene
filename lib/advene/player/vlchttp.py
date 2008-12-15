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
"""VLC http interface

Launch vlc with the following command-line:

vlc --intf http --http-src=${adveneshare}/vlc/http

It is in fact too slow for Advene's needs.
"""

import re
import httplib
import urllib
import thread

class StreamInformation:
    def __init__(self):
        self.streamstatus=None
        self.url=""
        self.position=0
        self.length=0


class VLCException(Exception):
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
    InitStatus=2
    EndStatus=3
    UndefinedStatus=4

    # # Exceptions
    PositionKeyNotSupported = VLCException
    PositionOrigin          = VLCException
    InvalidPosition         = VLCException
    PlaylistException       = VLCException
    InternalException       = VLCException
    statusmapping={
        "stop": EndStatus,
        "paused": PauseStatus,
        "playing": PlayingStatus,
        }

    def __init__(self, hostname="localhost", port=8080):
        self.http = httplib.HTTP()
        self.http.connect(host=hostname, port=port)
        print "Thread %s" % str(thread.get_ident())
        print self.sound_get_volume()
        #print self.playlist_get_list()

    def send_command(self, command):
        print "Sending %s" % command
        self.http.putrequest('GET', command)
        self.http.endheaders()
        status, reason, headers = self.http.getreply()
        print 'status =', status
        if status != 200:
            print "Error: %s" % reason
        return None

    def get_command(self, command):
        """Send a command and return the one-line result."""
        print "Sending %s" % command
        self.http.putrequest('GET', command)
        self.http.endheaders()
        status, reason, headers = self.http.getreply()
        print 'status =', status
        if status != 200:
            print "Error: %s" % reason
            return None
        l=self.http.getfile().read()
        return l.rstrip()

    def get_multiline_command(self, command):
        """Send a command and return the multiline result."""
        l=self.get_command(command)
        if l is None:
            return l
        else:
            return l.split('\n')

    def get_media_position(self, origin, key):
        l=self.get_command('/get_media_position.html')
        m=re.search('(\d+)', l)
        if m is not None:
            val=long(m.group(1))
        else:
            val=0
        return val

    def set_media_position(self, position):
        # FIXME: convert from Position to int.
        self.send_command('/?seek_value=%ds&control=seek' % (long(position) / 1000))

    def start(self, position):
        self.send_command('/?control=play&item=0')

    def pause(self, position):
        self.send_command('/?control=pause')

    def resume(self, position):
        self.send_command('/?control=pause')

    def stop(self, position):
        self.send_command('/?control=stop')

    def exit(self):
        # FIXME: todo
        #self.send_command('/?control=shutdown')
        return

    def playlist_add_item(self, item):
        # FIXME: convert from dvd://dev/dvd to dvd:/
        self.send_command('/?mrl=%s&control=add&sout=' % urllib.quote(item, safe=''))

    def playlist_clear(self):
        # FIXME: todo
        self.send_command('/?control=del')

    def playlist_get_list(self):
        l=self.get_multiline_command('/playlist.html')
        if l is None:
            return []
        pl = [ item.rstrip() for item in l if item ]
        return pl

    def snapshot(self, position):
        # FIXME: todo
        return None
        l=self.get_command('/snapshot.html')
        return None

    def all_snapshots(self):
        # FIXME: todo
        return [ ]

    def display_text (self, message, begin, end):
        # FIXME: todo
        print "Not implemented yet"
        pass

    def get_stream_information(self):
        s=StreamInformation()
        s.url=''
        s.length=0
        s.position=0
        s.streamstatus=Player.UndefinedStatus

        l=self.get_multiline_command('/get_stream_information.html')
        s.streamstatus=self.statusmapping[l[0].split("=")[1]]
        s.position=long(l[2].split("=")[1])*1000
        s.length=long(l[3].split("=")[1])*1000
        s.url=l[4].split("=")[1]
        return s

    def sound_get_volume(self):
        # FIXME: Normalize volume to be in [0..100]
        l=self.get_command("/volume.html")
        vol=0
        m=re.search('(\d+)', l)
        if m is not None:
            vol=long(m.group(1))
        return vol

    def sound_set_volume(self, v):
        # FIXME: Normalize volume to be in [0..100]
        self.send_command('/?value=%d&control=volume' % v)

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
        print "vlchttp update_status %s" % status

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
                print "******* Error : unknown status %s in vlchttp" % status
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

if __name__ == "__main__":
    player=Player("localhost", 8080)
    print "Playlist: ", player.playlist_get_list()
    print "Volume: ", player.sound_get_volume()
    player.playlist_add_item('/tmp/k.mpg')
    print "Playlist: ", player.playlist_get_list()
    player.start(0)
