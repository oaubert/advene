#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
import logging
logger = logging.getLogger(__name__)

import os
import signal
import subprocess
import urllib.request, urllib.parse, urllib.error

import advene.core.config as config
import advene.util.helper as helper


if config.data.os == 'win32':
    #try to determine if gstreamer is already installed
    ppath = os.getenv('GST_PLUGIN_PATH', "")
    if not ppath or not os.path.exists(ppath):
        os.environ['GST_PLUGIN_PATH'] = os.path.join(config.data.path['advene'], 'gst', 'lib', 'gstreamer-1.0')
        gstpath = os.getenv('PATH', "")
        os.environ['PATH'] = os.pathsep.join( ( os.path.join(config.data.path['advene'], 'gst', 'bin'), gstpath) )
    else:
        #even if gstpluginpath is defined, gst still may not be in path
        gstpath = os.getenv('PATH', "")
        h,t = os.path.split(ppath)
        binpath,t = os.path.split(h)
        os.environ['PATH'] = os.pathsep.join( (os.path.join( binpath, 'bin'), gstpath) )

try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import GObject, Gst
    GObject.threads_init()
    Gst.init(None)
except ImportError:
    Gst=None

import advene.core.config as config

APLAY = helper.find_in_path('aplay')

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
            uri = 'file:' + urllib.request.pathname2url(fname)
        else:
            uri = 'file://' + os.path.abspath(fname)
        pipe = Gst.parse_launch('uridecodebin name=decode uri=%s ! audioconvert ! audiopanorama panorama=%f ! audioamplify name=amplify amplification=%f ! autoaudiosink' % (uri, float(balance), int(volume) / 100.0 ))
        bus = pipe.get_bus()
        bus.add_signal_watch()

        def eos_cb(b, m):
            if m.src == pipe:
                pipe.set_state(Gst.State_NULL)

        bus.connect('message::eos', eos_cb)
        pipe.set_state(Gst.State.PLAYING)
        # FIXME: since we do not reuse the pipeline, we maybe should clean it up on state_change -> READY
        return True

    def linux_play(self, fname, volume=100, balance=0):
        """Play the given file. Requires aplay.

        It ignore the volume and balance parameters.
        """
        subprocess.Popen( [ APLAY, '-q', fname ], preexec_fn=subprocess_setup)
        signal.signal(signal.SIGCHLD, self.handle_sigchld)
        return True

    def win32_play(self, fname, volume=100, balance=0):
        """Play the given file.

        It ignore the volume and balance parameters.
        """
        import winsound
        winsound.PlaySound(fname, winsound.SND_FILENAME)
        return True

    def macosx_play(self, fname, volume=100, balance=0):
        """Play the given file.

        Cf
        http://developer.apple.com/documentation/Cocoa/Reference/ApplicationKit/Classes/NSSound_Class/Reference/Reference.html

        It ignores the balance parameter.
        """
        import AppKit
        sound = AppKit.NSSound.alloc().initWithContentsOfFile_byReference_(fname, True)
        sound.setVolume( volume / 100.0 )
        sound.play()
        return True

    def handle_sigchld(self, sig, frame):
        os.waitpid(-1, os.WNOHANG)
        return True

    if Gst is not None:
        play = gst_play
        logger.info("Using gstreamer to play sounds")
    elif config.data.os == 'win32':
        play=win32_play
        logger.info("Using winsound to play sounds")
    elif config.data.os == 'darwin':
        logger.info("Using AppKit to play sounds")
        play=macosx_play
    else:
        if not APLAY:
            logger.error("Error: cannot find aplay. Advene will be unable to play sounds.")
        play=linux_play
