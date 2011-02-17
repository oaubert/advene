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
import advene.core.config as config

import subprocess
import signal
import os
import sys
import urllib

if config.data.os == 'win32':
    #try to determine if gstreamer is already installed
    fsenc = sys.getfilesystemencoding()
    ppath = unicode(os.getenv('GST_PLUGIN_PATH', ""), fsenc)
    if not ppath or not os.path.exists(ppath):
        os.environ['GST_PLUGIN_PATH'] = os.path.join(config.data.path['advene'], 'gst', 'lib', 'gstreamer-0.10').encode(fsenc)
        gstpath = unicode(os.getenv('PATH', ""), fsenc)
        os.environ['PATH'] = os.pathsep.join( ( os.path.join(config.data.path['advene'], 'gst', 'bin'), gstpath) ).encode(fsenc)

try:
    import pygst
    pygst.require('0.10')
    import gst
except ImportError:
    gst=None

import advene.core.config as config

def subprocess_setup():
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

class SoundPlayer:
    def gst_play(self, fname, volume=100, balance=0):
        """Play the given file through gstreamer.
        """
        if fname.startswith('file:') or fname.startswith('http:'):
            uri = fname
        elif config.data.os == 'win32':
            uri = 'file:' + urllib.pathname2url(fname)
        else:
            uri = 'file://' + os.path.abspath(fname)
        pipe = gst.parse_launch('uridecodebin name=decode uri=%s ! audiopanorama panorama=%f ! audioamplify name=amplify amplification=%f ! autoaudiosink' % (uri, float(balance), int(volume) / 100.0 ))
        bus = pipe.get_bus()
        bus.add_signal_watch()

        def eos_cb(b, m):
            if m.src == pipe:
                pipe.set_state(gst.STATE_NULL)
                
        bus.connect('message::eos', eos_cb)
        pipe.set_state(gst.STATE_PLAYING)
        # FIXME: since we do not reuse the pipeline, we maybe clean it up on state_change -> READY
        return True

    def linux_play(self, fname, volume=100, balance=0):
        """Play the given file. Requires aplay.

        It ignore the volume and balance parameters.
        """
        pid=subprocess.Popen( [ '/usr/bin/aplay', '-q', fname ], preexec_fn=subprocess_setup)
        signal.signal(signal.SIGCHLD, self.handle_sigchld)
        return True
            
    def win32_play(self, fname, volume=100, balance=0):
        """Play the given file. Requires pySoundPlayer.exe.

        It ignore the volume and balance parameters.
        """
        pathsp = os.path.sep.join((config.data.path['advene'],'pySoundPlayer.exe'))
        if not os.path.exists(pathsp):
            pathsp = os.path.sep.join((config.data.path['advene'],'Win32SoundPlayer','pySoundPlayer.exe'))
        if os.path.exists(pathsp):
            pid=subprocess.Popen( [ pathsp, fname ] )
            #no SIGCHLD handler for win32
        return True

    def macosx_play(self, fname, volume=100, balance=0):
        """Play the given file.

        Cf
        http://developer.apple.com/documentation/Cocoa/Reference/ApplicationKit/Classes/NSSound_Class/Reference/Reference.html

        It ignores the balance parameter.
        """
        import objc
        import AppKit
        sound = AppKit.NSSound.alloc().initWithContentsOfFile_byReference_(fname, True)
        sound.setVolume( volume / 100.0 )
        sound.play()
        return True

    def handle_sigchld(self, sig, frame):
        os.waitpid(-1, os.WNOHANG)
        return True

    if gst is not None:
        play = gst_play
    elif config.data.os == 'win32':
        play=win32_play
    elif config.data.os == 'darwin':
        play=macosx_play
    else:
        if not os.path.exists('/usr/bin/aplay'):
            print "Error: aplay is not installed. Advene will be unable to play sounds."
        play=linux_play
    
