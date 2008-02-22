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
"""mplayer control class.

We reuse code from the pymp project :
http://jdolan.dyndns.org/jaydolan/pymp.html
"""

import os, fcntl, gobject
import re

STATUS_TIMEOUT = 50

# Dummy classes to match pymp API
class Control:
    def __init__(self):
        self.current_position_value=0

    def setProgress(self, time):
        self.current_position_value=time
        return

class Playlist(list):
    def __init__(self):
        self.continuous=True
        self.current_index=0

    def next(self, a, b):
        if self.current_index is None:
            self.current_index = 0
        else:
            self.current_index += 1

        if self.current_index > len(self)-1:
            self.current_index=0
        try:
            n=self[self.current_index]
        except IndexError:
            return None
        return n

class Pymp:
    def __init__(self):
        self.control=Control()
        self.playlist=Playlist()


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
        self.status=Player.UndefinedStatus
        self.relative_position=0
        self.pymp=Pymp()
        self.mplayer=Mplayer(self.pymp)


        self.status=self.UndefinedStatus

        self.position_update()
        pass

    def dvd_uri(self, title=None, chapter=None):
        return "dvd://%s" % str(title)

    def log(self, *p):
        print "Mplayer plugin : %s" % p

    def get_media_position(self, origin, key):
        self.log("get_media_position")
        return long(self.pymp.control.current_position_value * 1000)

    def set_media_position(self, position):
        self.log("set_media_position %s" % str(position))
        self.mplayer.cmd("seek %d 2" % (position / 1000))
        return

    def start(self, position):
        self.log("start %s" % str(position))
        if len(self.pymp.playlist) > 0:
            self.mplayer.play(self.pymp.playlist[0])
        return

    def pause(self, position):
        self.log("pause %s" % str(position))
        self.mplayer.pause()

    def resume(self, position):
        self.log("resume %s" % str(position))
        self.mplayer.pause()

    def stop(self, position):
        self.log("stop %s" % str(position))
        self.pause(position)

    def exit(self):
        self.log("exit")
        self.mplayer.close()

    def playlist_add_item(self, item):
        self.pymp.playlist.append(item)

    def playlist_clear(self):
        del self.pymp.playlist[:]

    def playlist_get_list(self):
        return self.pymp.playlist[:]

    def snapshot(self, position):
        self.log("snapshot %s" % str(position))
        self.mplayer.cmd("screenshot")
        return None

    def all_snapshots(self):
        self.log("all_snapshots %s")
        return [ None ]

    def display_text (self, message, begin, end):
        self.log("display_text %s" % str(message))
        self.mplayer.cmd("osd_show_text %s" % message)

    def get_stream_information(self):
        s=StreamInformation()
        if self.mplayer.mplayerIn:
            if self.mplayer.paused:
                self.status=self.PauseStatus
            else:
                self.status=self.PlayingStatus
            s.streamstatus=self.status
            self.mplayer.queryStatus()
            s.position=long(self.pymp.control.current_position_value * 1000)
            s.length=long(self.mplayer.totalTime * 1000)
            s.url=self.pymp.playlist[self.pymp.playlist.current_index]
        else:
            self.status=self.UndefinedStatus
            s.streamstatus=self.status
            s.position=0
            s.length=0
            s.url=''
            if self.pymp.playlist:
                s.url=self.pymp.playlist[0]
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
        print "mplayer update_status %s" % status

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
                print "******* Error : unknown status %s in mplayer" % status
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

    def set_visual(self, xid):
        self.mplayer.wid=xid
        return

# Copy/paster from pymp/mplayer.py

#
#  Provides simple piped I/O to an mplayer process.
#
class Mplayer:


        #
        #  Initializes this Mplayer with the specified Pymp.
        #
        def __init__(self, pymp):

                self.pymp = pymp
                self.re_time=re.compile("(A|V):\s*(\d+\.\d+)")
                self.re_length=re.compile("ANS_LENGTH=(\d+)")
                self.mplayerIn = None
                self.mplayerOut = None
                self.eofHandler = 0
                self.statusQuery = 0
                self.paused=False
                self.totalTime=0
                self.wid=None

        #
        #   Plays the specified target.
        #
        def play(self, target):
            args=["mplayer", "-slave"]
            if self.wid is not None:
                args.append("-wid")
                args.append(str(self.wid))

            args.append('"%s"' % target)
            args.append("2>/dev/null")

            mpc=" ".join(args)

            self.mplayerIn, self.mplayerOut = os.popen2(mpc)  #open pipe
            fcntl.fcntl(self.mplayerOut, fcntl.F_SETFL, os.O_NONBLOCK)

            self.startEofHandler()
            self.startStatusQuery()

        #
        #  Issues command to mplayer.
        #
        def cmd(self, command):

                if not self.mplayerIn:
                        return

                try:
                        self.mplayerIn.write(command + "\n")
                        self.mplayerIn.flush()  #flush pipe
                except StandardError:
                        return

        #
        #  Toggles pausing of the current mplayer job and status query.
        #
        def pause(self):

                if not self.mplayerIn:
                        return

                if self.paused:  #unpause
                        self.startStatusQuery()
                        self.paused = False

                else:  #pause
                        self.stopStatusQuery()
                        self.paused = True

                self.cmd("pause")

        #
        #  Cleanly closes any IPC resources to mplayer.
        #
        def close(self):

                if self.paused:  #untoggle pause to cleanly quit
                        self.pause()

                self.stopStatusQuery()  #cancel query
                self.stopEofHandler()  #cancel eof monitor

                self.cmd("quit")  #ask mplayer to quit

                try:
                        self.mplayerIn.close()   #close pipes
                        self.mplayerOut.close()
                except StandardError:
                        pass

                self.mplayerIn, self.mplayerOut = None, None
                self.pymp.control.setProgress(-1)  #reset bar

        #
        #  Triggered when mplayer's stdout reaches EOF.
        #
        def handleEof(self, source, condition):

                self.stopStatusQuery()  #cancel query

                self.mplayerIn, self.mplayerOut = None, None

                if self.pymp.playlist.continuous:  #play next target
                        self.pymp.playlist.next(None, None)
                else:  #reset progress bar
                        self.pymp.control.setProgress(-1)

                return False

        #
        #  Queries mplayer's playback status and upates the progress bar.
        #
        def queryStatus(self):
            curTime, line = None, None

            while True:
                try:  #attempt to fetch last line of output
                    line = self.mplayerOut.read()

                    # If totalTime is not yet known, look for it
                    if self.totalTime == 0:
                        m=self.re_length.search(line)
                        if m:
                            self.totalTime = long(m.group(1))
                            print "Got length: %d" % self.totalTime

                    m=self.re_time.match(line)
                    if m:
                        curTime = float(m.group(2))
                    else:
                        print line
                except StandardError:
                    break

                if curTime:
                    self.pymp.control.setProgress(curTime) #update progressbar
                    if self.totalTime == 0:
                        #print "Getting time length"
                        self.cmd("get_time_length") #grab the length of the file

                return True

        #
        #  Inserts the status query monitor.
        #
        def startStatusQuery(self):
                self.statusQuery = gobject.timeout_add(STATUS_TIMEOUT, self.queryStatus)

        #
        #  Removes the status query monitor.
        #
        def stopStatusQuery(self):
                gobject.source_remove(self.statusQuery)

        #
        #  Inserts the EOF monitor.
        #
        def startEofHandler(self):
                self.eofHandler = gobject.io_add_watch(self.mplayerOut, gobject.IO_HUP, self.handleEof)

        #
        #  Removes the EOF monitor.
        #
        def stopEofHandler(self):
                gobject.source_remove(self.eofHandler)


#End of file
