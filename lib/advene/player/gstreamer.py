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

Use appsink to get data out of a pipeline:
https://thomas.apestaart.org/thomas/trac/browser/tests/gst/crc/crc.py
"""

from gettext import gettext as _

import advene.core.config as config
from advene.util.helper import format_time
import os
import time

import gobject
gobject.threads_init()

import gtk
import sys

if config.data.os == 'win32':
    #try to determine if gstreamer is already installed
    fsenc = sys.getfilesystemencoding()
    ppath = unicode(os.getenv('GST_PLUGIN_PATH', ""), fsenc)
    if not ppath or not os.path.exists(ppath):
        os.environ['GST_PLUGIN_PATH'] = os.path.join(config.data.path['advene'], 'gst', 'lib', 'gstreamer-0.10').encode(fsenc)
        gstpath = unicode(os.getenv('PATH', ""), fsenc)
        os.environ['PATH'] = os.pathsep.join( ( os.path.join(config.data.path['advene'], 'gst', 'bin'), gstpath) ).encode(fsenc)
    else:
        #even if gstpluginpath is defined, gst still may not be in path
        gstpath = unicode(os.getenv('PATH', ""), fsenc)
        h,t = os.path.split(ppath)
        binpath,t = os.path.split(h)
        os.environ['PATH'] = os.pathsep.join( (os.path.join( binpath, 'bin'), gstpath) ).encode(fsenc)

try:
    import pygst
    pygst.require('0.10')
    import gst
    from advene.util.snapshotter import Snapshotter
    svgelement = None
    # First try rsvgoverlay
    if gst.element_factory_find('rsvgoverlay'):
        svgelement = 'rsvgoverlay'
    else:
        # Not compiled. Try to fallback on the python version.
        try:
            import advene.util.svgoverlay
            svgelement = 'pysvgoverlay'
        except ImportError:
            print "SVG overlay support not present"
    print "SVG: Using %s element" % (svgelement or "None")
except ImportError:
    gst=None

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
    player_capabilities=[ 'seek', 'pause', 'caption', 'frame-by-frame', 'async-snapshot', 'set-rate' ]

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
        self.rate = 1.0
        # fullscreen gtk.Window
        self.fullscreen_window=None

        # Fullscreen timestamp display - cache data
        self.last_timestamp = 0
        self.last_timestamp_update = 0

        try:
            self.snapshotter = Snapshotter(self.snapshot_taken, width=config.data.player['snapshot-width'])
        except Exception, e:
            self.log(u"Could not initialize snapshotter:" +  unicode(e))
            self.snapshotter = None

        self.fullres_snapshotter = None
        # This method has the following signature:
        # self.fullres_snapshot_callback(snapshot=None, message=None)
        # If snapshot is None, then there should be an explanation (string) in msg.
        self.fullres_snapshot_callback = None

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

    def log (self, msg):
        """Display a message.
        """
        print "gstreamer:", unicode(msg).encode('utf-8')

    def build_pipeline(self):
        sink='xvimagesink'
        if config.data.player['vout'] == 'x11':
            sink='ximagesink'
        elif config.data.player['vout'] == 'gl':
            sink='glimagesink'
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
        if config.data.player['svg'] and svgelement:
            try:
                self.imageoverlay=gst.element_factory_make(svgelement, 'overlay')
                self.imageoverlay.props.fit_to_frame = True
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
            # Note: do not remove the (seemingly superfluous)
            # ffmpegcolorspace here, else it blocks the pipeline for
            # some unknown reason.
            elements.append(gst.element_factory_make('ffmpegcolorspace'))

        if sink == 'xvimagesink':
            # Imagesink accepts both rgb/yuv and is able to do scaling itself.
            elements.append( self.imagesink )
        else:
            csp=gst.element_factory_make('ffmpegcolorspace')
            elements.extend( (csp, self.imagesink) )

        self.video_sink.add(*elements)
        if len(elements) >= 2:
            gst.element_link_many(*elements)

        self.log("gstreamer: using " + sink)

        # Note: it is crucial to make ghostpad an attribute, so that
        # it is not garbage-collected at the end of the build_pipeline
        # method.
        self._video_ghostpad = gst.GhostPad('sink', elements[0].get_pad('video_sink') or elements[0].get_pad('sink'))
        # Idem for elements
        self._video_elements = elements

        self.video_sink.add_pad(self._video_ghostpad)

        self.player.props.video_sink=self.video_sink

        if gst.element_factory_find('scaletempo'):
            # The scaletempo element is present. Use it.
            self.audio_sink = gst.Bin()
            elements = [
                gst.element_factory_make('scaletempo'),
                gst.element_factory_make('autoaudiosink'),
                ]
            self.audio_sink.add(*elements)
            if len(elements) >= 2:
                gst.element_link_many(*elements)
            self.player.props.audio_sink = self.audio_sink
            # Keep a ref. on elements
            self._audio_elements = elements
            self._audio_ghostpad = gst.GhostPad('sink', elements[0].get_pad('audio_sink') or elements[0].get_pad('sink'))
            self.audio_sink.add_pad(self._audio_ghostpad)


        bus = self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_sync_message)

    def position2value(self, p):
        """Returns a position in ms.
        """
        if isinstance(p, Position):
            v=p.value
            if p.key != self.MediaTime:
                self.log("unsupported key " + p.key)
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
            self.log(u"Invalid URI" + unicode(uri))
            return False

    def get_media_position(self, origin, key):
        return self.current_position()

    def set_media_position(self, position):
        if not self.check_uri():
            return
        if self.current_status() == self.UndefinedStatus:
            self.player.set_state(gst.STATE_PAUSED)
        p = long(self.position2value(position) * gst.MSECOND)
        event = gst.event_new_seek(self.rate, gst.FORMAT_TIME,
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
        if config.data.os == 'win32':
            #item is a str, os.path needs to work with unicode obj to accept unicode path
            item = os.path.abspath(unicode(item))
            if os.path.exists(item):
                item="file:///" + item
        elif os.path.exists(item):
            item="file://" + os.path.abspath(item)
        self.player.set_property('uri', item)
        if self.snapshotter:
            self.snapshotter.set_uri(item)
        if self.fullres_snapshotter:
            self.fullres_snapshotter.set_uri(item)

    def playlist_clear(self):
        self.videofile=None
        self.player.set_property('uri', '')

    def playlist_get_list(self):
        if self.videofile:
            return [ self.videofile ]
        else:
            return [ ]

    def fullres_snapshot_taken(self, buffer):
        if self.fullres_snapshot_callback:
            s=Snapshot( { 'data': buffer.data,
                          'type': 'PNG',
                          'date': buffer.timestamp / gst.MSECOND,
                          # Hardcoded size values. They are not used
                          # by the application, since they are
                          # encoded in the PNG file anyway.
                          'width': 160,
                          'height': 100 } )
            self.fullres_snapshot_callback(snapshot=s)
            self.fullres_snapshot_callback = None

    def async_fullres_snapshot(self, position, callback):
        """Take full-resolution snapshots.

        This method is not reentrant: as long as there is a call
        pending, it is not available for another position.
        """
        if self.fullres_snapshot_callback is not None:
            callback(message=_("Cannot capture fullscreen snapshot, another capture is ongoing."))
            return
        if self.fullres_snapshotter is None:
            # Initialise it.
            self.fullres_snapshotter = Snapshotter(self.fullres_snapshot_taken)
            self.fullres_snapshotter.set_uri(self.player.get_property('uri'))
        self.fullres_snapshot_callback = callback
        if not self.fullres_snapshotter.thread_running:
                self.fullres_snapshotter.start()
        self.fullres_snapshotter.enqueue(position)

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
        t = long(self.position2value(position))
        if self.snapshotter:
            if not self.snapshotter.thread_running:
                self.snapshotter.start()
            # We enqueue 3 timestamps: the original timestamp, its
            # value minus 20ms (the async snapshotter goes to the
            # specified position then takes the video buffer which may then
            # be later) and its value aligned to a frame boundary
            # (considering a 25f/s framerate).
            for pos in sorted((t - 20, t / 25 * 25, t)):
                self.snapshotter.enqueue(pos)

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
                self.log("Cannot overlay SVG")
                return True
            self.overlay.begin=self.position2value(begin)
            self.overlay.end=self.position2value(end)
            self.overlay.data=message
            self.imageoverlay.props.data=message
            return True

        if not self.captioner:
            self.log(u"Cannot caption " + unicode(message))
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
                self.log("******* Error : unknown status %s in gstreamer player" % status)
        self.position_update ()

    def is_active(self):
        return True

    def check_player(self):
        self.log("check player")
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
        elif not self.overlay.data and self.imageoverlay is not None and self.is_fullscreen() and config.data.player.get('fullscreen-timestamp', False):
            t = time.time()
            # Update timestamp every half second
            if t - self.last_timestamp_update > .5 and abs(s.position - self.last_timestamp) > 10:
                self.imageoverlay.props.data = '''<svg:svg width="640pt" height="480pt" preserveAspectRatio="xMinYMin meet" version="1" viewBox="0 0 640 480" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="http://www.w3.org/2000/svg">
  <text fill="white" stroke="white" style="stroke-width:1; font-family: sans-serif; font-size: 22" x="5" y="475">%s</text>
</svg:svg>''' % format_time(s.position)
                self.last_timestamp = s.position
                self.last_timestamp_update = t

    def reparent(self, xid):
        # See https://bugzilla.gnome.org/show_bug.cgi?id=599885
        #gtk.gdk.threads_enter()
        if xid:
            self.log("Reparent " + hex(xid))

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
        #self.set_visual( None )

    def restart_player(self):
        # FIXME: destroy the previous player
        self.player.set_state(gst.STATE_READY)
        # Rebuild the pipeline
        self.build_pipeline()
        if self.videofile is not None:
            self.playlist_add_item(self.videofile)
        self.position_update()
        return True

    def on_sync_message(self, bus, message):
        if message.structure is None:
            return True
        if message.structure.get_name() == 'prepare-xwindow-id':
            self.reparent(self.xid)
        return True

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

    def set_rate(self, rate=1.0):
        if not self.check_uri():
            return
        self.rate = rate
        try:
            p = self.player.query_position(gst.FORMAT_TIME)[0]
        except gst.QueryError:
            self.log("Error in set_rate (query position)")
            return
        event = gst.event_new_seek(self.rate, gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH,
                                   gst.SEEK_TYPE_SET, long(p),
                                   gst.SEEK_TYPE_NONE, 0)
        if event:
            res = self.player.send_event(event)
            if not res:
                self.log("Could not set rate")
        else:
            self.log("Cannot build set_rate event")

    def get_rate(self):
        return self.rate

    def disp(self, e, indent="  "):
        l=[str(e)]
        if hasattr(e, 'elements'):
            i=indent+"  "
            l.extend( [ self.disp(c, i) for c in e.elements() ])
        return ("\n"+indent).join(l)

    def is_fullscreen(self):
        return self.fullscreen_window and self.fullscreen_window.is_active()

    def fullscreen(self, connect=None):

        def keypress(widget, event):
            if event.keyval == gtk.keysyms.Escape:
                self.unfullscreen()
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
            # Get geometry of the first monitor
            r = gtk.gdk.screen_get_default().get_monitor_geometry(0)
            self.fullscreen_window.set_decorated(False)
            self.fullscreen_window.set_size_request(r.width, r.height)
            #self.fullscreen_window.move(r.x, r.y)
            self.fullscreen_window.move(0, 0)
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
        if not self.overlay.data and self.imageoverlay:
            # Reset imageoverlay data in any case
            self.imageoverlay.props.data = None
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

