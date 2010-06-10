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

FIXME:
- get/set_rate

Use appsink to get data out of a pipeline:
https://thomas.apestaart.org/thomas/trac/browser/tests/gst/crc/crc.py
"""

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

from advene.util.snapshotter import Snapshotter
try:
    import advene.util.svgoverlay
except ImportError:
    print "SVG overlay support not present"

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

        self.snapshotter=Snapshotter(self.snapshot_taken, width=config.data.player['snapshot-width'])
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

        self.imageoverlay=None
        if config.data.player['svg']:
            try:
                self.imageoverlay=gst.element_factory_make('svgoverlay', 'overlay')
            except:
                pass

        self.imagesink = gst.element_factory_make(sink, 'sink')

        elements=[]
        if self.captioner is not None:
            elements.append(self.captioner)
        if self.imageoverlay is not None:
            elements.append(gst.element_factory_make('queue'))
            elements.append(gst.element_factory_make('ffmpegcolorspace'))
            elements.append(self.imageoverlay)
            elements.append(gst.element_factory_make('ffmpegcolorspace'))

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
        if len(elements) >= 2:
            gst.element_link_many(*elements)

        print "gstreamer: using", sink
        print "adding ghostpad for", elements[0]

        self.video_sink.add_pad(gst.GhostPad('sink', elements[0].get_pad('video_sink') or elements[0].get_pad('sink')))

        self.player.props.video_sink=self.video_sink

        bus = self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_sync_message)

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
        if message.startswith('<svg') or (message.startswith('<?xml') and '<svg' in message):
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
        #print "gst - update_status ", status, str(position)
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
        self.position_update ()

    def is_active(self):
        return True

    def check_player(self):
        print "check player"
        return True

    def position_update(self):
        s = self.get_stream_information ()
        if s.position == 0:
            # Try again once. timestamp sometimes goes through 0 when
            # modifying the player position.
            s = self.get_stream_information()

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
        print "Reparent", hex(xid)

        gtk.gdk.display_get_default().sync()
        
        self.imagesink.set_xwindow_id(xid)
        self.imagesink.set_property('force-aspect-ratio', True)
        self.imagesink.expose()
        #gtk.gdk.threads_leave()
        
    def set_visual(self, xid):
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
            self.reparent(self.xid)

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

    def fullscreen(self, connect=None):

        def keypress(widget, event):
            if event.keyval == gtk.keysyms.Escape:
                self.unfullscreen()
                return True
            elif event.keyval == gtk.keysyms.space:
                # Since we are in fullscreen, there can be no
                # confusion with other widgets.
                self.pause()
                return True
            return False
        
        def buttonpress(widget, event):
            if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                self.unfullscreen()
                return True
            return False

        if self.fullscreen_window is None:
            self.fullscreen_window=gtk.Window()
            self.fullscreen_window.add_events(gtk.gdk.BUTTON_PRESS_MASK |
                                              gtk.gdk.BUTTON_RELEASE_MASK |
                                              gtk.gdk.KEY_PRESS_MASK |
                                              gtk.gdk.KEY_RELEASE_MASK |
                                              gtk.gdk.SCROLL_MASK)
            self.fullscreen_window.connect('key-press-event', keypress)
            self.fullscreen_window.connect('button-press-event', buttonpress)
            self.fullscreen_window.connect('destroy', self.unfullscreen)
            if connect is not None:
                connect(self.fullscreen_window)

            style=self.fullscreen_window.get_style().copy()
            black=gtk.gdk.color_parse('black')
            for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                style.bg[state]=black
                style.base[state]=black
            self.fullscreen_window.set_style(style)

        if config.data.os == 'darwin':
            self.fullscreen_window.set_size_request(gtk.gdk.screen_width(), gtk.gdk.screen_height())
            self.fullscreen_window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_SPLASHSCREEN)
            self.fullscreen_window.set_position(gtk.WIN_POS_CENTER)
            self.fullscreen_window.show()
        else:
            self.fullscreen_window.show()
            self.fullscreen_window.window.fullscreen()

        self.fullscreen_window.grab_focus()

        if config.data.os == 'win32':
            self.reparent(self.fullscreen_window.window.handle)
        else:
            self.reparent(self.fullscreen_window.window.xid)

    def unfullscreen(self, *p):
        self.reparent(self.xid)
        if self.fullscreen_window.window:
            self.fullscreen_window.hide()
        else:
            # It has been destroyed
            self.fullscreen_window = None
        return True

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

