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
"""Gstreamer player interface.

Based on gst >= 0.10 API.

See http://pygstdocs.berlios.de/pygst-reference/index.html for API

SVG support depends on the unofficial gdkpixbufoverlay element. It can
be obtained (as a patch) from http://bugzilla.gnome.org/show_bug.cgi?id=550443

FIXME:
- fullscreen (reparent to its own gtk.Window and use gtk.Window.(un)fullscreen )
- get/set_rate
- Win32: directdrawsink implements the X Overlay interface then you
  can use it to setup your video window or to receive a signal when
  directdrawsink will create the default one.
- TODO: investigate SVG support. Maybe through gdkpixbufdec:
gst-launch videotestsrc ! videomixer name=mix ! ffmpegcolorspace ! xvimagesink filesrc location=/tmp/a.jpg ! gdkpixbufdec ! ffmpegcolorspace ! mix.

For set_rate:
> If you only want to change the rate without changing the seek
        > positions, use GST_SEEK_TYPE_NONE/GST_CLOCK_TIME_NONE for the start
        > position also.

        Actually, this will generally cause some strangeness in the seeking,
        because the fast-forward will begin from the position that the SOURCE of
        the pipeline has reached. Due to buffering after the decoders, this is
        not the position that the user is seeing on the screen, so their
        trick-mode operation will commence with a jump in the position.

        What you want to do is query the current position of the playback, and
        use that with GST_SEEK_TYPE_SET to begin the trickmode from the exact
        position you want.

Caps negotiation: http://gstreamer.freedesktop.org/data/doc/gstreamer/head/pwg/html/section-nego-upstream.html

Videomixer:

videotestsrc pattern=1 ! video/x-raw-yuv,width=100,height=100 ! videobox border-alpha=0 alpha=0.5 top=-70 bottom=-70 right=-220 ! videomixer name=mix ! ffmpegcolorspace ! xvimagesink videotestsrc ! video/x-raw-yuv,width=320, height=240 ! alpha alpha=0.7 ! mix.

This should show a 320x240 pixels video test source with some transparency showing the background checker pattern. Another video test source with just the snow pattern of 100x100 pixels is overlayed on top of the first one on the left vertically centered with a small transparency showing the first video test source behind and the checker pattern under it. 

videotestsrc ! video/x-raw-yuv,width=320, height=240 ! videomixer name=mix ! ffmpegcolorspace ! xvimagesink filesrc location=/tmp/a.svg  ! gdkpixbufdec ! videoscale ! video/x-raw-rgb,width=320,height=240 ! ffmpegcolorspace ! alpha alpha=0.5 ! mix. 

Working pipeline (but it does not correctly handle transparency):
filesrc location=/tmp/a.svg ! gdkpixbufdec ! ffmpegcolorspace ! videomixer name=mix ! ffmpegcolorspace ! xvimagesink videotestsrc ! mix.

Mosaic : 2 videos side-by-side:

videotestsrc pattern=11 !  video/x-raw-yuv,width=320,height=200 ! videobox left=-320 ! videomixer name=mix ! ffmpegcolorspace ! xvimagesink videotestsrc pattern=0 ! video/x-raw-yuv,width=320,height=200 ! mix.

puis
pads=list(mix.pads())
pads[0].props.xpos=-320
pads[1].props.xpos=320
"""

import advene.core.config as config
import tempfile

import gobject
gobject.threads_init()

try:
    import pygst
    pygst.require('0.10')
    import gst
except ImportError:
    gst=None

import gtk
import os
from threading import Condition

name="GStreamer video player"

def register(controller):
    if gst is None:
        return False
    controller.register_player(Player)
    return True

class StreamInformation:
    def __init__(self):
        self.streamstatus=None
        self.url=""
        self.position=0
        self.length=0

class Snapshot:
    def __init__(self, d=None):
        if d is not None:
            for k in ('width', 'height', 'data', 'type', 'date'):
                try:
                    setattr(self, k, d[k])
                except KeyError:
                    setattr(self, k, None)

class Position:
    def __init__(self, value=0):
        self.value=value
        # See Player attributes below...
        self.origin=0
        self.key=2

    def __str__(self):
        return "Position " + str(self.value)

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

# Placeholder
class Caption:
    pass

class Player:
    player_id='gstreamer'
    player_capabilities=[ 'seek', 'pause', 'caption', 'frame-by-frame' ]

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

    PositionKeyNotSupported=Exception("Position key not supported")
    PositionOriginNotSupported=Exception("Position origin not supported")
    InvalidPosition=Exception("Invalid position")
    PlaylistException=Exception("Playlist error")
    InternalException=Exception("Internal player error")

    def __init__(self):

        self.xid = None
        self.mute_volume=None
        # fullscreen gtk.Window
        self.fullscreen_window=None

        self.build_converter()
        self.build_pipeline()

        self.caption=Caption()
        self.caption.text=""
        self.caption.begin=-1
        self.caption.end=-1

        self.overlay=Caption()
        self.overlay.filename=''
        self.overlay.begin=-1
        self.overlay.end=-1

        self.videofile=None
        self.status=Player.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 0
        self.relative_position=self.create_position(0,
                                                    origin=self.RelativePosition)

        self.position_update()

    def build_converter(self):
        """Build the snapshot converter pipeline.
        """
        # Snapshot format conversion infrastructure.
        self.converter=gst.parse_launch('fakesrc name=src ! queue name=queue ! videoscale ! ffmpegcolorspace ! video/x-raw-rgb,width=%d,height=%d ! pngenc ! fakesink name=sink signal-handoffs=true' % config.data.player['snapshot-dimensions'])
        self.converter._lock = Condition()

        self.converter.queue=self.converter.get_by_name('queue')
        self.converter.sink=self.converter.get_by_name('sink')

        def converter_cb(element, buf, pad):
            c=self.converter
            c._lock.acquire()
            c._buffer=buf
            c._lock.notify()
            c._lock.release()
            return True

        self.converter.sink.connect('handoff', converter_cb)
        self.converter.set_state(gst.STATE_PLAYING)

    def build_pipeline(self):
        sink='xvimagesink'
        if config.data.player['vout'] == 'x11':
            sink='ximagesink'
        if config.data.os == 'win32':
            sink='directdrawsink'

        self.player = gst.element_factory_make("playbin", "player")

        self.video_sink = gst.Bin()

        # TextOverlay does not seem to be present in win32 installer. Do without it.
        try:
            self.captioner=gst.element_factory_make('textoverlay', 'captioner')
            # FIXME: move to config.data
            self.captioner.props.font_desc='Sans 24'
            #self.caption.props.text="Foobar"
        except:
            self.captioner=None

        try:
            self.imageoverlay=gst.element_factory_make('gdkpixbufoverlay', 'overlay')
        except:
            self.imageoverlay=None

        self.imagesink = gst.element_factory_make(sink, 'sink')

#
#        self.svg_renderer = gst.parse_launch('fakesrc name=svgsrc ! gdkpixbufdec ! ffmpegcolorspace ! videoscale')
#        mix=gst.element_factory_make("videomixer", "mix")
#        spad = src.get_static_pad('src')
#        dpad = mix.get_request_pad('sink_%d')
#        spad.link(dpad)
#        mix.link(conv) # conv == ffmpegcolorspace ! xvimagesink

        # Controller for the videomixer position properties
        # from video-controller.py
        #control = gst.Controller(dpad, "xpos", "ypos")
        #control.set_interpolation_mode("xpos", gst.INTERPOLATE_LINEAR)
        #control.set_interpolation_mode("ypos", gst.INTERPOLATE_LINEAR)
        #control.set("xpos", 0, 0)
        #control.set("xpos", 5 * gst.SECOND, 200)
        #control.set("ypos", 0, 0)
        #control.set("ypos", 5 * gst.SECOND, 200)



        if sink == 'ximagesink':
            print "Using ximagesink."
            filter = gst.element_factory_make("capsfilter", "filter")
            filter.set_property("caps", gst.Caps("video/x-raw-yuv, width=%d, height=%s" % config.data.player['snapshot-dimensions']))
            self.filter=filter

            csp=gst.element_factory_make('ffmpegcolorspace')
            # Do not try to hard to solve the resize problem, before
            # the gstreamer bug
            # http://bugzilla.gnome.org/show_bug.cgi?id=339201 is
            # solved...
            #self.scale=gst.element_factory_make('videoscale')
            self.video_sink.add(self.captioner, filter, csp, self.imagesink)
            gst.element_link_many(self.captioner, filter, csp, self.imagesink)
        elif self.captioner is not None:
            if self.imageoverlay is not None:
                self.video_sink.add(self.captioner, self.imageoverlay, self.imagesink)
                self.captioner.link(self.imageoverlay)
                self.imageoverlay.link(self.imagesink)
            else:
                self.video_sink.add(self.captioner, self.imagesink)
                self.captioner.link(self.imagesink)
        else:
            self.video_sink.add(self.imagesink)

        if self.captioner:
            self.video_sink.add_pad(gst.GhostPad('sink', self.captioner.get_pad('video_sink')))
        else:
            self.video_sink.add_pad(gst.GhostPad('sink', self.imagesink.get_pad('sink')))

        self.player.props.video_sink=self.video_sink

        bus = self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_sync_message)
##        bus.add_signal_watch()
##        def debug_message(bus, message):
##            if message.structure is None:
##                return
##            print "gst message", message.structure.get_name()
##            return True
##        bus.connect('message', debug_message)

    def position2value(self, p):
        """Returns a position in ms.
        """
        if isinstance(p, Position):
            v=p.value
            if p.key != self.MediaTime:
                print "gstreamer: unsupported key ", p.key
                return 0
            if p.origin != self.AbsolutePosition:
                v += self.current_position()
        else:
            v=p
        return long(v)

    def current_status(self):
        st=self.player.get_state()[1]
        if st == gst.STATE_PLAYING:
            return self.PlayingStatus
        elif st == gst.STATE_PAUSED:
            return self.PauseStatus
        else:
            return self.UndefinedStatus

    def current_position(self):
        """Returns the current position in ms.
        """
        try:
            pos, format = self.player.query_position(gst.FORMAT_TIME)
        except:
            position = 0
        else:
            position = pos * 1.0 / gst.MSECOND
        return position

    def dvd_uri(self, title=None, chapter=None):
        # FIXME: find the syntax to specify chapter
        return "dvd://%s" % str(title)

    def check_uri(self):
        if gst.uri_is_valid(self.player.get_property('uri')):
            return True
        else:
            print "Invalid URI", self.player.get_property('uri')
            return False

    def log(self, *p):
        print "gstreamer player: %s" % p

    def get_media_position(self, origin, key):
        return self.current_position()

    def set_media_position(self, position):
        if not self.check_uri():
            return
        if self.current_status() == self.UndefinedStatus:
            self.player.set_state(gst.STATE_PAUSED)
        p = long(self.position2value(position) * gst.MSECOND)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET, p,
                                   gst.SEEK_TYPE_NONE, 0)
        res = self.player.send_event(event)
        if not res:
            raise InternalException

    def start(self, position=0):
        if not self.check_uri():
            return
        if position != 0:
            self.set_media_position(position)
        self.player.set_state(gst.STATE_PLAYING)

    def pause(self, position=0):
        if not self.check_uri():
            return
        if self.status == self.PlayingStatus:
            self.player.set_state(gst.STATE_PAUSED)
        else:
            self.player.set_state(gst.STATE_PLAYING)

    def resume(self, position=0):
        self.pause(position)

    def stop(self, position=0):
        if not self.check_uri():
            return
        self.player.set_state(gst.STATE_READY)

    def exit(self):
        self.player.set_state(gst.STATE_NULL)

    def playlist_add_item(self, item):
        self.videofile=item
        if os.path.exists(item):
            item="file://" + os.path.abspath(item)
        self.player.set_property('uri', item)

    def playlist_clear(self):
        self.videofile=None
        self.player.set_property('uri', '')

    def playlist_get_list(self):
        return [ self.videofile ]

    def convert_snapshot(self, frame):
        """Synchronously convert a frame (gst.Buffer) to jpeg.
        """
        c=self.converter
        # Lock the conversion pipeline
        c._lock.acquire()
        c._buffer=None

        # Push the frame into the conversion pipeline
        c.queue.get_pad('src').push(frame)

        # Wait for the lock to be released
        while c._buffer is None:
            c._lock.wait()

        b=c._buffer.copy()
        c._lock.release()
        return b

    def snapshot(self, position):
        if not self.check_uri():
            return None

        try:
            b=self.player.props.frame.copy()
        except SystemError:
            return None

        f=self.convert_snapshot(b)
        t=f.timestamp / gst.MSECOND

        return Snapshot( { 'data': f.data,
                           'type': 'PNG',
                           'date': t,
                           # Hardcoded size values. They are not used
                           # by the application, since their are
                           # encoded in the PNG file anyway.
                           'width': 160,
                           'height': 100 } )

    def all_snapshots(self):
        self.log("all_snapshots %s")
        return [ None ]

    def display_text (self, message, begin, end):
        if not self.check_uri():
            return
        if message.startswith('<svg'):
            if self.imageoverlay is None:
                print "Cannot overlay SVG"
                return True
            self.overlay.begin=self.position2value(begin)
            self.overlay.end=self.position2value(end)
            self.overlay.filename=tempfile.mktemp('.svg', 'adv')
            open(self.overlay.filename, 'w').write(message)
            self.imageoverlay.props.image_name=self.overlay.filename
            return True
        
        if not self.captioner:
            print "Cannot caption ", message.encode('utf8')
            return
        self.caption.begin=self.position2value(begin)
        self.caption.end=self.position2value(end)
        self.caption.text=message
        self.captioner.props.text=message

    def get_stream_information(self):
        s=StreamInformation()
        if self.videofile:
            s.url=''
        else:
            s.url=self.videofile

        try:
            dur, format = self.player.query_duration(gst.FORMAT_TIME)
        except:
            duration = 0
        else:
            duration = dur * 1.0 / gst.MSECOND

        s.length=duration
        s.position=self.current_position()
        s.status=self.current_status()
        return s

    def sound_get_volume(self):
        """Get the current volume.

        The result is a long value in [0, 100]
        """
        v = self.player.get_property('volume') * 100 / 4
        return long(v)

    def sound_set_volume(self, v):
        if v > 100:
            v = 100
        elif v < 0:
            v = 0
        v = v * 4.0 / 100
        self.player.set_property('volume', v)

    # Helper methods
    def create_position (self, value=0, key=None, origin=None):
        """Create a Position.
        """
        if key is None:
            key=self.MediaTime
        if origin is None:
            origin=self.AbsolutePosition

        p=Position()
        p.value = value
        p.origin = origin
        p.key = key
        return p

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
        #print "gst - update_status ", status, str(position)
        if position is None:
            position=0
        else:
            position=self.position2value(position)

        if status == "start" or status == "set":
            self.position_update()
            if status == 'start':
                if self.status == self.PauseStatus:
                    self.resume (position)
                elif self.status != self.PlayingStatus:
                    self.start(position)
            self.set_media_position(position)
        else:
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
                print "******* Error : unknown status %s in gstreamer player" % status
        self.position_update ()

    def is_active(self):
        return True

    def check_player(self):
        print "check player"
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.status
        self.stream_duration = s.length
        self.current_position_value = long(s.position)
        if self.caption.text and (s.position < self.caption.begin
                                  or s.position > self.caption.end):
            self.display_text('', -1, -1)
        if self.overlay.filename and (s.position < self.overlay.begin
                                      or s.position > self.overlay.end):
            self.imageoverlay.props.image_name=''
            self.overlay.begin=-1
            self.overlay.end=-1
            os.unlink(self.overlay.filename)
            self.overlay.filename=''

    def set_visual(self, xid):
        self.xid = xid
        self.imagesink.set_xwindow_id(self.xid)
        self.imagesink.set_property('force-aspect-ratio', True)
        return True

    def restart_player(self):
        # FIXME: destroy the previous player
        self.player.set_state(gst.STATE_READY)
        # Rebuilt the pipeline
        self.build_pipeline()
        self.playlist_add_item(self.videofile)
        self.position_update()
        return True

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        if message.structure.get_name() == 'prepare-xwindow-id':
            self.imagesink.set_xwindow_id(self.xid)
            message.src.set_property('force-aspect-ratio', True)

    def sound_mute(self):
        if self.mute_volume is None:
            self.mute_volume=self.sound_get_volume()
            self.sound_set_volume(0)
        return

    def sound_unmute(self):
        if self.mute_volume is not None:
            self.sound_set_volume(self.mute_volume)
            self.mute_volume=None
        return

    def sound_is_muted(self):
        return (self.mute_volume is not None)

    def disp(self, e, indent="  "):
        l=[str(e)]
        if hasattr(e, 'elements'):
            i=indent+"  "
            l.extend( [ self.disp(c, i) for c in e.elements() ])
        return ("\n"+indent).join(l)

    def fullscreen(self):
        def keypress(widget, event):
            if event.keyval == gtk.keysyms.Escape:
                self.unfullscreen()
                return True
            elif event.keyval == gtk.keysyms.space:
                # Since we are in fullscreen, there can be no
                # confusion with other widgets.
                self.pause()
                return True
            else:
                try:
                    if self.fullscreen_key_handler(widget, event):
                        return True
                except AttributeError:
                    return False
            return False
        if self.fullscreen_window is None:
            self.fullscreen_window=gtk.Window()
            self.fullscreen_window.connect('key-press-event', keypress)
            style=self.fullscreen_window.get_style().copy()
            black=gtk.gdk.color_parse('black')
            for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                style.bg[state]=black
                style.base[state]=black
            self.fullscreen_window.set_style(style)
        self.fullscreen_window.show()
        self.fullscreen_window.window.fullscreen()
        self.imagesink.set_xwindow_id(self.fullscreen_window.window.xid)

    def unfullscreen(self):
        self.imagesink.set_xwindow_id(self.xid)
        self.fullscreen_window.hide()
