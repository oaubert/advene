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

Use appsink to get data out of a pipeline:
https://thomas.apestaart.org/thomas/trac/browser/tests/gst/crc/crc.py
"""

debug = True

import advene.core.config as config
import os
import time

import gobject
gobject.threads_init()

import gtk
import os

if config.data.os == 'win32':
    #try to determine if gstreamer is already installed
    ppath = os.getenv('GST_PLUGIN_PATH')
    if not ppath or not os.path.exists(ppath):
        os.environ['GST_PLUGIN_PATH']=config.data.path['advene']+'/gst/lib/gstreamer-0.10'
    gstpath = os.getenv('PATH')
    os.environ['PATH']=config.data.path['advene']+'/gst/bin;'+gstpath

try:
    import pygst
    pygst.require('0.10')
    import gst
except ImportError:
    gst=None

import gtk
import cairo
import rsvg

from advene.util.snapshotter import Snapshotter

name="GStreamer video player"

def register(controller):
    if gst is None:
        return False
    controller.register_player(Player)
    return True

class SVGOverlay(gst.Element):
    __gstdetails__ = ("SVG overlay", "Filter/Editor/Video", "Overlays SVG content over the video",
                      "Olivier Aubert <olivier.aubert@liris.cnrs.fr>")

    __gproperties__ = {
        'data': ( gobject.TYPE_STRING, 'data', 'SVG data to overlay', None, gobject.PARAM_WRITABLE ),
        'filename': ( gobject.TYPE_STRING, 'filename', 'SVG file to overlay', None, gobject.PARAM_WRITABLE ),
        }
    
    _sinkpadtemplate = gst.PadTemplate ("sink",
                                         gst.PAD_SINK,
                                         gst.PAD_ALWAYS,
                                         gst.caps_from_string ("video/x-raw-rgb,bpp=32,depth=32,blue_mask=-16777216,green_mask=16711680, red_mask=65280, alpha_mask=255,width=[ 1, 2147483647 ],height=[ 1, 2147483647 ],framerate=[ 0/1, 2147483647/1 ]"))
    _srcpadtemplate = gst.PadTemplate ("src",
                                         gst.PAD_SRC,
                                         gst.PAD_ALWAYS,
                                         gst.caps_from_string ("video/x-raw-rgb,bpp=32,depth=32,blue_mask=-16777216,green_mask=16711680, red_mask=65280, alpha_mask=255,width=[ 1, 2147483647 ],height=[ 1, 2147483647 ],framerate=[ 0/1, 2147483647/1 ]"))
    
    def __init__(self):
        gst.Element.__init__(self)

        self.svg = None

        self.sinkpad = gst.Pad(self._sinkpadtemplate, "sink")
        self.sinkpad.set_chain_function(self.chainfunc)
        self.sinkpad.set_event_function(self.eventfunc)
        self.sinkpad.set_getcaps_function(gst.Pad.proxy_getcaps)
        self.sinkpad.set_setcaps_function(gst.Pad.proxy_setcaps)
        self.add_pad (self.sinkpad)

        self.srcpad = gst.Pad(self._srcpadtemplate, "src")
        self.srcpad.set_event_function(self.srceventfunc)
        self.srcpad.set_query_function(self.srcqueryfunc)
        self.srcpad.set_getcaps_function(gst.Pad.proxy_getcaps)
        self.srcpad.set_setcaps_function(gst.Pad.proxy_setcaps)
        self.add_pad (self.srcpad)

    def chainfunc(self, pad, buffer):
        print "chainfunc"
        if self.svg is None:
            return self.srcpad.push(buffer)

        try:
            outbuf = buffer.copy_on_write ()
            self.draw_on(outbuf)
            return self.srcpad.push(outbuf)
        except:
            return gst.GST_FLOW_ERROR

    def eventfunc(self, pad, event):
        print "eventfunc"
        return self.srcpad.push_event (event)
        
    def srcqueryfunc (self, pad, query):
        print "srcqueryfunc"
        return self.sinkpad.query (query)
    def srceventfunc (self, pad, event):
        print "srceventfunc"
        return self.sinkpad.push_event (event)

    def do_set_property(self, key, value):
        print "do_set_property"
        if key.name == 'data':
            self.set_svg(data=value)
        elif key.name == 'filename':
            self.set_svg(filename=value)
        else:
            print "No property %s" % key.name

    def set_svg(self, filename=None, data=None):
        """Set the SVG data to render.

        Use None to reset.
        """
        print "set_svg"
        if data is not None:
            self.svg=rsvg.Handle(data=data)
        elif filename is not None:
            self.svg=rsvg.Handle(filename)
        else:
            self.svg=None

    def draw_on(self, buf):
        print "draw_on"
        if self.svg is None:
            return

        try:
            caps = buf.get_caps()
            width = caps[0]['width']
            height = caps[0]['height']
            surface = cairo.ImageSurface.create_for_data (buf, cairo.FORMAT_ARGB32, width, height, 4 * width)
            ctx = cairo.Context(surface)
        except:
            print "Failed to create cairo surface for buffer"
            import traceback
            traceback.print_exc()
            return

        sx=1.0 * width / self.svg.props.width
        sy=1.0 * height / self.svg.props.height
        scale = cairo.Matrix( sx, 0, 0, sy, 0, 0 )
        ctx.set_matrix(scale)
        self.svg.render_cairo(ctx)

gst.element_register(SVGOverlay, 'svgoverlay2')
gobject.type_register(SVGOverlay)

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
    player_capabilities=[ 'seek', 'pause', 'caption', 'frame-by-frame', 'async-snapshot' ]

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

        self.snapshotter=Snapshotter(self.snapshot_taken, width=config.data.player['snapshot-dimensions'][0])
        #self.snapshotter.start()
        
        # This method should be set by caller:
        self.snapshot_notify=None
        self.build_pipeline()

        self.caption=Caption()
        self.caption.text=""
        self.caption.begin=-1
        self.caption.end=-1

        self.overlay=Caption()
        self.overlay.data=''
        self.overlay.begin=-1
        self.overlay.end=-1

        self.videofile=None
        self.status=Player.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 0
        self.relative_position=self.create_position(0,
                                                    origin=self.RelativePosition)

        self.position_update()

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
            self.imageoverlay=gst.element_factory_make('svgoverlay2FIXME', 'overlay')
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

        elements=[]
        if self.captioner is not None:
            elements.append(self.captioner)
        if self.imageoverlay is not None:
            elements.append(gst.element_factory_make('queue'))
            elements.append(gst.element_factory_make('ffmpegcolorspace'))
            elements.append(self.imageoverlay)

        if sink == 'xvimagesink':
            # Imagesink accepts both rgb/yuv and is able to do scaling itself.
            elements.append( self.imagesink )
        else:
            csp=gst.element_factory_make('ffmpegcolorspace')
            # The scaling did not work before 2008-10-11, cf
            # http://bugzilla.gnome.org/show_bug.cgi?id=339201
            scale=gst.element_factory_make('videoscale')
            self.videoscale=scale
            elements.extend( (csp, scale, self.imagesink) )

        self.video_sink.add(*elements)
        if len(elements) > 2:
            gst.element_link_many(*elements)

        print "gstreamer: using", sink

        print "adding ghostpad for", elements[0]
        self.video_sink.add_pad(gst.GhostPad('sink', elements[0].get_pad('video_sink') or elements[0].get_pad('sink')))

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
        #if debug:
        #    print "Before get_state"
        st=self.player.get_state()[1]
        #if debug:
        #    print "After get_state"
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
        uri=self.player.get_property('uri')
        if uri and gst.uri_is_valid(uri):
            return True
        else:
            print "Invalid URI", str(uri)
            return False

    def log(self, *p):
        print "gstreamer player: %s" % p

    def get_media_position(self, origin, key):
        return self.current_position()

    def set_media_position(self, position):
        if debug:
            print "Before check_uri"
        if not self.check_uri():
            return
        if debug:
            print "Before status check"
        if self.current_status() == self.UndefinedStatus:
            if debug:
                print "Before set_state paused"
            self.player.set_state(gst.STATE_PAUSED)
            if debug:
                print "After set_state paused"
        p = long(self.position2value(position) * gst.MSECOND)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET, p,
                                   gst.SEEK_TYPE_NONE, 0)
        if debug:
            print "Before send_event"
            res = self.player.send_event(event)
        if debug:
            print "After send_event"
        if not res:
            raise InternalException

    def start(self, position=0):
        if debug:
            print "Starting"
        if not self.check_uri():
            return
        if position != 0:
            self.set_media_position(position)
        if debug:
            print "Before set_state"
        self.player.set_state(gst.STATE_PLAYING)
        if debug:
            print "After set_state"

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
            if config.data.os == 'win32':
                item="file:///" + os.path.abspath(item)
            else:
                item="file://" + os.path.abspath(item)
        self.player.set_property('uri', item)
        if self.snapshotter:
            self.snapshotter.set_uri(item)
        
    def playlist_clear(self):
        self.videofile=None
        self.player.set_property('uri', '')

    def playlist_get_list(self):
        if self.videofile:
            return [ self.videofile ]
        else:
            return [ ]

    def snapshot_taken(self, buffer):
        if self.snapshot_notify:
            s=Snapshot( { 'data': buffer.data,
                          'type': 'PNG',
                          'date': buffer.timestamp / gst.MSECOND,
                          # Hardcoded size values. They are not used
                          # by the application, since they are
                          # encoded in the PNG file anyway.
                          'width': 160,
                          'height': 100 } )
            self.snapshot_notify(s)
            
    def async_snapshot(self, position):
        t=long(self.position2value(position))
        if not self.snapshotter.thread_running:
            self.snapshotter.start()
        if self.snapshotter:
            self.snapshotter.enqueue(t)
        
    def snapshot(self, position):
        if not self.check_uri():
            return None
        # Return None in all cases.
        return None

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
            self.overlay.data=message
            self.imageoverlay.props.data=message
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
        print "gst - update_status ", status, str(position)
        #print "Current status", self.player.get_state(), self.imageoverlay.get_state()
        if position is None:
            position=0
        else:
            position=self.position2value(position)

        if status == "start" or status == "set":
            self.position_update()
            if status == "start":
                if self.status == self.PauseStatus:
                    self.resume (position)
                elif self.status != self.PlayingStatus:
                    self.start(position)
                    time.sleep(0.005)
#            print "Before s_m_p", position
            self.set_media_position(position)
#            print "After s_m_p"
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
        if debug:
            print "Before position_update"
        self.position_update ()
        if debug:
            print "After position_update - New status", self.player.get_state()

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
        if self.overlay.data and (s.position < self.overlay.begin
                                      or s.position > self.overlay.end):
            self.imageoverlay.props.data=None
            self.overlay.begin=-1
            self.overlay.end=-1
            self.overlay.data=None

    def reparent(self, xid):
        # See https://bugzilla.gnome.org/show_bug.cgi?id=599885
        #gtk.gdk.threads_enter()
        gtk.gdk.display_get_default().sync()
        
        self.imagesink.set_xwindow_id(xid)
        self.imagesink.set_property('force-aspect-ratio', True)
        
        #gtk.gdk.threads_leave()
        
    def set_visual(self, xid):
        print "set_visual", xid
        if not xid:
            return True
        self.xid = xid
        self.reparent(xid)
        return True

    def set_widget(self, widget):
        self.set_visual( widget.get_id() )
            
    def restart_player(self):
        # FIXME: destroy the previous player
        self.player.set_state(gst.STATE_READY)
        # Rebuild the pipeline
        self.build_pipeline()
        self.playlist_add_item(self.videofile)
        self.position_update()
        return True

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return
        if message.structure.get_name() == 'prepare-xwindow-id':
            self.set_visual(self.xid)

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
        if config.data.os == 'darwin':
            self.fullscreen_window.set_size_request(gtk.gdk.screen_width(), gtk.gdk.screen_height())
        else:
            self.fullscreen_window.window.fullscreen()
        if config.data.os == 'win32':
            self.reparent(self.fullscreen_window.window.handle)
        else:
            self.reparent(self.fullscreen_window.window.xid)

    def unfullscreen(self):
        self.reparent(self.xid)
        self.fullscreen_window.hide()

    # relpath, dump_bin and dump_element implementation based on Daniel Lenski <dlenski@gmail.com>
    # posted on gst-dev mailing list on 20070913
    def relpath(self, p1, p2):
        sep = os.path.sep

        # get common prefix (up to a slash)
        common = os.path.commonprefix((p1, p2))
        common = common[:common.rfind(sep)]

        # remove common prefix
        p1 = p1[len(common)+1:]
        p2 = p2[len(common)+1:]

        # number of seps in p1 is # of ..'s needed
        return "../" * p1.count(sep) + p2

    def dump_bin(self, bin, depth=0, recurse=-1, showcaps=True):
        return [ l  for e in reversed(list(bin)) for l in self.dump_element(e, depth, recurse - 1) ]

    def dump_element(self, e, depth=0, recurse=-1, showcaps=True):
        ret=[]
        indentstr = depth * 8 * ' '

        # print element path and factory
        path = e.get_path_string() + (isinstance(e, gst.Bin) and '/' or '')
        factory = e.get_factory()
        if factory is not None:
            ret.append( '%s%s (%s)' % (indentstr, path, factory.get_name()) )
        else:
            ret.append( '%s%s (No factory)' % (indentstr, path) )

        # print info about each pad
        for p in e.pads():
            name = p.get_name()

            # negotiated capabilities
            caps = p.get_negotiated_caps()
            if caps: capsname = caps[0].get_name()
            elif showcaps: capsname = '; '.join(s.to_string() for s in set(p.get_caps()))
            else: capsname = None

            # flags
            flags = []
            if not p.is_active(): flags.append('INACTIVE')
            if p.is_blocked(): flags.append('BLOCKED')

            # direction
            direc = (p.get_direction() is gst.PAD_SRC) and "=>" or "<="

            # peer
            peer = p.get_peer()
            if peer: peerpath = self.relpath(path, peer.get_path_string())
            else: peerpath = None

            # ghost target
            if isinstance(p, gst.GhostPad):
                target = p.get_target()
                if target: ghostpath = target.get_path_string()
                else: ghostpath = None
            else:
                ghostpath = None

            line=[ indentstr, "    " ]
            if flags: line.append( ','.join(flags) )
            line.append(".%s" % name)
            if capsname: line.append( '[%s]' % capsname )
            if ghostpath: line.append( "ghosts %s" % self.relpath(path, ghostpath) )
            line.append( "%s %s" % (direc, peerpath) )
            
            #if peerpath and peerpath.find('proxy')!=-1: print peer
            ret.append( ''.join(line) )
        if recurse and isinstance(e, gst.Bin):
            ret.extend( self.dump_bin(e, depth+1, recurse) )
        return ret

    def str_element(self, element):
        return "\n".join(self.dump_element(element))

