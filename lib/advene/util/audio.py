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
import subprocess
import signal
import os
from threading import Thread

import advene.core.config as config

class SoundPlayer:
    def linux_play(self, fname):
        """Play the given file. Requires aplay.
        """
        pid=subprocess.Popen( [ '/usr/bin/aplay', '-q', fname ] )
        signal.signal(signal.SIGCHLD, self.handle_sigchld)
        return True

    def win32_play(self, fname):
        #from winsound import PlaySound, SND_FILENAME, SND_ASYNC
        #PlaySound(fname, SND_FILENAME|SND_ASYNC)
        #spt = SpThread(fname)
        #spt.setDaemon(True)
        #spt.start()
        pathsp = os.path.sep.join((config.data.path['advene'],'pySoundPlayer.exe'))
        if not os.path.exists(pathsp):
            pathsp = os.path.sep.join((config.data.path['advene'],'Win32SoundPlayer','pySoundPlayer.exe'))
        if os.path.exists(pathsp):
            pid=subprocess.Popen( [ pathsp, fname ] )
            #no SIGCHLD handler for win32
        return True

    def macosx_play(self, fname):
        """Play the given file.

        Cf
        http://developer.apple.com/documentation/Cocoa/Reference/ApplicationKit/Classes/NSSound_Class/Reference/Reference.html
        """
        import objc
        import AppKit
        sound = AppKit.NSSound.alloc().initWithContentsOfFile_byReference_(fname, True)
        sound.play()
        return True

    def handle_sigchld(self, sig, frame):
        os.waitpid(-1, os.WNOHANG)
        return True

    if config.data.os == 'win32':
        play=win32_play
    elif config.data.os == 'darwin':
        play=macosx_play
    else:
        if not os.path.exists('/usr/bin/aplay'):
            print "Error: aplay is not installed. Advene will be unable to play sounds."
        play=linux_play

class SpThread(Thread):
    def __init__(self,name):
        Thread.__init__(self)
        self.fname = name
    def run(self):
        import pymedia.muxer as muxer, pymedia.audio.acodec as acodec, pymedia.audio.sound as sound
        import time
        dm= muxer.Demuxer( str.split( self.fname, '.' )[ -1 ].lower() )
        snds= sound.getODevices()
        f= open( self.fname, 'rb' )
        snd= dec= None
        s= f.read( 32000 )
        card=0
        rate=1
        t= 0
        while len( s ):
            frames= dm.parse( s )
            if frames:
                for fr in frames:
                    if dec== None:
                        print dm.getHeaderInfo(), dm.streams
                        dec= acodec.Decoder( dm.streams[ fr[ 0 ] ] )
                    r= dec.decode( fr[ 1 ] )
                    if r and r.data:
                        if snd== None:
                            print 'Opening sound %s with %d channels -> %s' % ( self.fname, r.channels, snds[ card ][ 'name' ] )
                            snd= sound.Output( int( r.sample_rate* rate ), r.channels, sound.AFMT_S16_LE, card )
                        data= r.data
                        snd.play( data )
            s= f.read( 512 )
        while snd.isPlaying():
            time.sleep( .05 )
