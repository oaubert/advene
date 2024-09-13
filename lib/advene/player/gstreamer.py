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
"""Gstreamer player interface.

Based on gst >= 1.0 API.
"""
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import advene.core.config as config
from advene.util.helper import format_time, path2uri
from advene.gui.util import get_drawable, is_wayland

import ctypes
import os
import time

try:
    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GstVideo', '1.0')
    gi.require_version('GstPbutils', '1.0')
    from gi.repository import GObject, Gst
    from gi.repository import GLib
    from gi.repository import GstVideo
    from gi.repository import GstPbutils
    if config.data.os == 'linux':
        from gi.repository import GdkX11
    elif config.data.os == 'win32':
        gi.require_version('GdkWin32', '3.0')
        from gi.repository import GdkWin32
    from gi.repository import Gdk
    from gi.repository import Gtk
    from advene.util.snapshotter import Snapshotter
    svgelement = 'rsvgoverlay'
    GObject.threads_init()
    Gst.init(None)
    if True or not hasattr(Gst.Structure, '__getitem__'):
        # Monkey patch __getitem__
        Gst.Structure.__getitem__ = Gst.Structure.get_value
except (ImportError, ValueError):
    Gst=None

name="GStreamer video player"

def register(controller):
    if Gst is None:
        return False
    controller.register_player(Player)
    return True

class StreamInformation:
    def __init__(self):
        self.status=None
        self.url=""
        self.position=0
        self.length=0

class Snapshot:
    def __init__(self, d=None):
        if d is not None:
            for k in ('width', 'height', 'data', 'type', 'date', 'media'):
                try:
                    setattr(self, k, d[k])
                except KeyError:
                    setattr(self, k, None)

# Placeholder
class Caption:
    pass

class Player:
    player_id='gstreamer'
    player_capabilities=[ 'seek', 'pause', 'caption', 'frame-by-frame', 'async-snapshot', 'set-rate', 'svg' ]

    # Status
    PlayingStatus=0
    PauseStatus=1
    InitStatus=2
    EndStatus=3
    UndefinedStatus=4

    def __init__(self):
        self.xid = None
        self.mute_volume=None
        self.rate = 1.0
        # fullscreen Gtk.Window
        self.fullscreen_window = None
        self.fullscreen_drawable = None
        self.container = None

        # Fullscreen timestamp display - cache data
        self.last_timestamp = 0
        self.last_timestamp_update = 0

        try:
            self.snapshotter = Snapshotter(self.snapshot_taken, width=config.data.player['snapshot-width'])
        except Exception as e:
            self.log("Could not initialize snapshotter:" +  str(e))
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

        self.videofile = None
        self.status = Player.UndefinedStatus
        self.current_position_value = 0
        self.stream_duration = 0
        self.position_update()

    def log (self, msg):
        """Display a message.
        """
        logger.warning(msg)

    def build_pipeline(self):
        sink='autovideosink'
        if config.data.player['vout'] == 'x11':
            sink='ximagesink'
        elif config.data.player['vout'] == 'xvideo':
            sink='xvimagesink'
        elif config.data.player['vout'] == 'gtk':
            sink='gtksink'
            if is_wayland():
                sink = 'gtkwaylandsink'
        elif config.data.player['vout'] == 'd3d':
            sink='d3dvideosink'
        elif config.data.player['vout'] == 'gl':
            sink='glimagesinkelement'
        elif config.data.player['vout'].startswith('raw:'):
            # "Raw" element definition - will be passed to Gst.parse_launch
            sink = config.data.player['vout'][4:]

        self.player = Gst.ElementFactory.make("playbin", "player")

        self.video_sink = Gst.Bin()

        # TextOverlay does not seem to be present in win32 installer. Do without it.
        try:
            self.captioner=Gst.ElementFactory.make('textoverlay', 'captioner')
            # FIXME: move to config.data
            self.captioner.props.font_desc='Sans 24'
        except Exception:
            self.captioner=None

        self.imageoverlay=None
        if config.data.player['svg'] and svgelement:
            try:
                self.imageoverlay=Gst.ElementFactory.make(svgelement, 'overlay')
                self.imageoverlay.props.fit_to_frame = True
            except Exception:
                logger.error("Gstreamer SVG overlay element is not available", exc_info=True)

        try:
            self.imagesink = Gst.parse_launch(f"{sink} name=sink")
        except GLib.GError as err:
            logger.error(f"Player: {err.message} - cannot render video")
            self.imagesink = Gst.parse_launch("fakesink name=sink")

        try:
            self.imagesink.set_property('force-aspect-ratio', True)
        except TypeError:
            logger.warning("Cannot set force-aspect-ratio on video sink")
        self.real_imagesink = self.imagesink

        elements=[]
        elements.append(Gst.ElementFactory.make('videoconvert', None))
        elements.append(Gst.ElementFactory.make('videoscale', None))
        if self.imageoverlay is not None:
            # FIXME: Issue: rsvgoverlay.fit_to_frame expects that the
            # dimensions of the input buffers match the aspect ratio
            # of the original video, which is currently not the case.
            elements.append(Gst.ElementFactory.make('queue', None))
            elements.append(self.imageoverlay)
        if self.captioner is not None:
            elements.append(self.captioner)

        # Add a queue before display
        elements.append(Gst.ElementFactory.make('queue', None))

        if sink == 'glimagesinkelement':
            upload = Gst.ElementFactory.make('glupload', None)
            csp=Gst.ElementFactory.make('glcolorconvert', None)
            elements.extend( (upload, csp, self.imagesink) )
        else:
            csp=Gst.ElementFactory.make('videoconvert', None)
            elements.extend( (csp, self.imagesink) )

        for el in elements:
            self.video_sink.add(el)
        if len(elements) >= 2:
            for src, dst in zip(elements, elements[1:]):
                src.link(dst)

        logger.debug("Using %s", sink)

        # Note: it is crucial to make ghostpad an attribute, so that
        # it is not garbage-collected at the end of the build_pipeline
        # method.
        self._video_ghostpad = Gst.GhostPad.new('sink', elements[0].get_static_pad('video_sink') or elements[0].get_static_pad('sink'))
        # Idem for elements
        self._video_elements = elements

        logger.debug("Using video sink pipeline %s", self._video_elements)
        self.video_sink.add_pad(self._video_ghostpad)

        self.player.props.video_sink=self.video_sink
        self.player.props.force_aspect_ratio = True

        self.audio_sink = Gst.parse_launch('scaletempo name=scaletempo ! audioconvert ! audioresample ! autoaudiosink')
        self.audio_sink.add_pad(Gst.GhostPad.new('sink', self.audio_sink.get_child_by_name('scaletempo').get_static_pad('sink')))
        self.player.props.audio_sink=self.audio_sink

        bus = self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_sync_message)
        bus.add_signal_watch()
        bus.connect('message::error', self.on_bus_message_error)
        bus.connect('message::warning', self.on_bus_message_warning)

    def current_status(self):
        st = self.player.get_state(100)[1]
        if st == Gst.State.PLAYING:
            return self.PlayingStatus
        elif st == Gst.State.PAUSED:
            return self.PauseStatus
        else:
            return self.UndefinedStatus

    def current_position(self):
        """Returns the current position in ms.
        """
        try:
            pos = self.player.query_position(Gst.Format.TIME)[1]
        except Exception:
            logger.error("Current position exception", exc_info=True)
            position = 0
        else:
            position = pos / Gst.MSECOND
        return position

    def dvd_uri(self, title=None, chapter=None):
        # FIXME: find a way to specify chapter/title
        # resindvd does not allow to specify it in the URI
        return "dvd://"

    def set_uri(self, item):
        self.videofile = item
        item = path2uri(item)
        self.player.set_property('uri', item)
        if self.snapshotter:
            self.snapshotter.set_uri(item)
        if self.fullres_snapshotter:
            self.fullres_snapshotter.set_uri(item)
        return self.get_video_info()

    def get_uri(self):
        return self.player.get_property('current-uri') or self.player.get_property('uri') or ""

    def get_video_info(self):
        """Return information about the current video.
        """
        uri = self.get_uri()
        default = {
            'uri': uri,
            'framerate_denom': 1,
            'framerate_num': config.data.preferences['default-fps'],
            'width': 640,
            'height': 480,
            'duration': 0,
        }
        if not uri:
            return default

        d = GstPbutils.Discoverer()
        try:
            info = d.discover_uri(uri)
        except Exception as e:
            logger.error("Cannot find video info: %s", e.message)
            info = None
        if info is None:
            # Return default data.
            logger.warning("Could not find information about video, using absurd defaults.")
            return default
        if not info.get_video_streams():
            # Could be an audio file.
            default['duration'] = info.get_duration() / Gst.MSECOND
            return default

        stream = info.get_video_streams()[0]
        return {
            'uri': uri,
            'framerate_denom': stream.get_framerate_denom(),
            'framerate_num': stream.get_framerate_num(),
            'width': stream.get_width(),
            'height': stream.get_height(),
            'duration': info.get_duration() / Gst.MSECOND,
        }

    def check_uri(self):
        uri = self.get_uri()
        if uri and Gst.uri_is_valid(uri):
            return True
        else:
            self.log("Invalid URI " + str(uri))
            return False

    def get_position(self):
        return self.current_position()

    def set_position(self, position):
        if not self.check_uri():
            return
        if self.current_status() == self.UndefinedStatus:
            self.player.set_state(Gst.State.PAUSED)
        p = int(position) * Gst.MSECOND
        event = Gst.Event.new_seek(self.rate, Gst.Format.TIME,
                                   Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                                   Gst.SeekType.SET, int(p),
                                   Gst.SeekType.NONE, 0)
        res = None
        if event:
            res = self.player.send_event(event)
        if not res or not event:
            logger.warning(_("Problem when seeking into media"))

    def start(self, position=0):
        if not self.check_uri():
            return
        if position != 0:
            self.set_position(position)
        self.player.set_state(Gst.State.PLAYING)

    def pause(self, position=0):
        if not self.check_uri():
            return
        if self.status == self.PlayingStatus:
            self.player.set_state(Gst.State.PAUSED)
        else:
            self.player.set_state(Gst.State.PLAYING)

    def resume(self, position=0):
        self.pause(position)

    def stop(self, position=0):
        if not self.check_uri():
            return
        self.player.set_state(Gst.State.READY)

    def exit(self):
        self.player.set_state(Gst.State.NULL)

    def fullres_snapshot_taken(self, data):
        if self.fullres_snapshot_callback:
            s = Snapshot(data)
            self.fullres_snapshot_callback(snapshot=s)
            self.fullres_snapshot_callback = None

    def async_fullres_snapshot(self, position, callback):
        """Take full-resolution snapshots.

        This method is not reentrant: as long as there is a call
        pending, it is not available for another position.
        """
        if self.fullres_snapshot_callback is not None:
            callback(message=_("Cannot capture full-resolution snapshot, another capture is ongoing."))
            return
        if self.fullres_snapshotter is None:
            # Initialise it.
            self.fullres_snapshotter = Snapshotter(self.fullres_snapshot_taken)
            self.fullres_snapshotter.set_uri(self.player.get_property('uri'))
        self.fullres_snapshot_callback = callback
        if not self.fullres_snapshotter.thread_running:
            self.fullres_snapshotter.start()
        self.fullres_snapshotter.enqueue(position)

    def snapshot_taken(self, data):
        s = Snapshot(data)
        logger.debug("-------------------------------- snapshot taken %d %s", s.date, self.snapshot_taken)
        if self.snapshot_notify:
            self.snapshot_notify(s)

    def async_snapshot(self, position, notify=None):
        t = int(position)
        if notify is not None and self.snapshot_notify is None:
            self.snapshot_notify = notify
        if self.snapshotter:
            if not self.snapshotter.thread_running:
                self.snapshotter.start()
            self.snapshotter.enqueue(t)
        else:
            logger.error("snapshotter not present")

    def display_text (self, message, begin, end):
        if not self.check_uri():
            return
        if message.startswith('<svg') or (message.startswith('<?xml') and '<svg' in message):
            if self.imageoverlay is None:
                self.log("Cannot overlay SVG")
                return True
            self.overlay.begin=begin
            self.overlay.end=end
            self.overlay.data=message
            self.imageoverlay.props.data=message
            return True

        if not self.captioner:
            self.log("Cannot caption " + str(message))
            return
        self.caption.begin=begin
        self.caption.end=end
        self.caption.text=message
        self.captioner.props.text=message

    def get_stream_information(self):
        s = StreamInformation()
        s.uri = self.get_uri()
        try:
            dur = self.player.query_duration(Gst.Format.TIME)[1]
        except Exception:
            duration = 0
        else:
            duration = dur / Gst.MSECOND

        s.length=duration
        s.position=self.current_position()
        s.status=self.current_status()
        return s

    def sound_get_volume(self):
        """Get the current volume.

        The result is a long value in [0, 100]
        """
        v = self.player.get_property('volume') * 100 / 4
        return int(v)

    def sound_set_volume(self, v):
        if v > 100:
            v = 100
        elif v < 0:
            v = 0
        v = v * 4.0 / 100
        self.player.set_property('volume', v)

    def update_status (self, status=None, position=None):
        """Update the player status.

        Defined status:
           - C{start}
           - C{pause}
           - C{resume}
           - C{stop}
           - C{seek}
           - C{seek_relative}

        If no status is given, it only updates the value of self.status

        If C{position} is None, it will be considered as the current
        position.

        @param status: the new status
        @type status: string
        @param position: the position
        @type position: int

        """
        logger.debug("update_status %s %s ", status, str(position))
        if position is None:
            position = 0

        if status in ("start", "seek", "seek_relative"):
            self.position_update()
            if status == "seek_relative":
                position = self.current_position() + position
            if status == "start":
                if self.status == self.PauseStatus:
                    self.resume(position)
                elif self.status != self.PlayingStatus:
                    self.start(position)
                    time.sleep(0.005)
            self.set_position(position)
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
            elif status == "" or status is None:
                pass
            else:
                self.log("******* Error : unknown status %s in gstreamer player" % status)
        self.position_update ()

    def is_playing(self):
        """Is the player in Playing or Paused status?
        """
        s = self.get_stream_information ()
        return s.status == self.PlayingStatus or s.status == self.PauseStatus

    def check_player(self):
        logger.debug("check player")
        return True

    def position_update(self):
        s = self.get_stream_information ()
        if s.position == 0:
            # Try again once. timestamp sometimes goes through 0 when
            # modifying the player position.
            s = self.get_stream_information()

        self.status = s.status
        self.stream_duration = s.length
        self.current_position_value = int(s.position)
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

    def reparent(self, xid, sink=None):
        if sink is None:
            sink = self.real_imagesink
        else:
            self.real_imagesink = sink
        logger.debug("Reparent %s", xid)
        # See https://bugzilla.gnome.org/show_bug.cgi?id=599885
        if xid:
            self.log("Reparent " + hex(xid))
            Gdk.Display().get_default().sync()
            try:
                sink.set_window_handle(xid)
                sink.set_property('force-aspect-ratio', True)
                sink.expose()
            except AttributeError:
                logger.warning("cannot set video output widget")

    def set_visual(self, xid):
        if not xid:
            return True
        self.xid = xid
        self.reparent(xid)
        return True

    def set_widget(self, widget, container):
        handle = None
        self.container = container

        if config.data.player['vout'] == 'gtk':
            # Special case: we use a gtk sink, so we get a Gtk widget
            # and not the XOverlay API
            try:
                container.pack_start(self.imagesink.props.widget, True, True, 0)
                self.imagesink.props.widget.show()
                widget.hide()
            except Exception:
                logger.exception("Embedding error")
            return

        if config.data.os == "win32":
            # From
            # http://stackoverflow.com/questions/25823541/get-the-window-handle-in-pygi
            # We check for ensure_native since win32 gtk3 DrawingArea seems to miss this method.
            if hasattr(widget, 'ensure_native') and not widget.ensure_native():
                logger.error("Cannot embed video player - it requires a native window")
                return
            ctypes.pythonapi.PyCapsule_GetPointer.restype = ctypes.c_void_p
            ctypes.pythonapi.PyCapsule_GetPointer.argtypes = [ctypes.py_object]
            drawingarea_gpointer = ctypes.pythonapi.PyCapsule_GetPointer(widget.__gpointer__, None)
            gdkdll = ctypes.CDLL("libgdk-3-0.dll")
            handle = gdkdll.gdk_win32_window_get_handle(drawingarea_gpointer)
        else:
            handle = widget.get_id()

        widget.show()
        self.set_visual(handle)

    def restart_player(self):
        # FIXME: properly destroy the previous player
        self.player.set_state(Gst.State.READY)
        # Rebuild the pipeline
        self.build_pipeline()
        if self.videofile is not None:
            self.set_uri(self.videofile)
        self.position_update()
        return True

    def on_sync_message(self, bus, message):
        s = message.get_structure()
        logger.debug("sync message %s", s)
        if s is None:
            return True
        if GstVideo.is_video_overlay_prepare_window_handle_message(message):
            imagesink = message.src
            imagesink.set_property("force-aspect-ratio", True)
            self.reparent(self.xid, imagesink)
        return True

    def on_bus_message_error(self, bus, message):
        s = message.get_structure()
        if s is None:
            return True
        title, message = message.parse_error()
        logger.error("%s: %s", title, message)
        return True

    def on_bus_message_warning(self, bus, message):
        s = message.get_structure()
        if s is None:
            return True
        title, message = message.parse_warning()
        logger.warning("%s: %s", title, message)
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
        return self.mute_volume is not None

    def set_rate(self, rate=1.0):
        if not self.check_uri():
            return
        try:
            p = self.player.query_position(Gst.Format.TIME)[1]
        except Gst.QueryError:
            self.log("Error in set_rate (query position)")
            return
        event = Gst.Event.new_seek(self.rate, Gst.Format.TIME,
                                   Gst.SeekFlags.FLUSH,
                                   Gst.SeekType.SET, int(p),
                                   Gst.SeekType.NONE, 0)
        if event:
            res = self.player.send_event(event)
            if not res:
                self.log("Could not set rate")
            else:
                self.rate = rate
        else:
            self.log("Cannot build set_rate event")

    def get_rate(self):
        return self.rate

    def is_fullscreen(self):
        return self.fullscreen_window and self.fullscreen_window.is_active()

    def fullscreen(self, connect=None):
        def keypress(widget, event):
            if event.keyval == Gdk.KEY_Escape:
                self.unfullscreen()
                return True
            return False

        def buttonpress(widget, event):
            if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                self.unfullscreen()
                return True
            return False

        if self.fullscreen_window is None:
            self.fullscreen_window = Gtk.Window()
            self.fullscreen_window.set_name("fullscreen_player")
            self.fullscreen_window.connect('key-press-event', keypress)
            self.fullscreen_window.connect('button-press-event', buttonpress)
            self.fullscreen_window.connect('destroy', self.unfullscreen)
            if config.data.player['vout'] == 'gtk':
                self.fullscreen_drawable = self.imagesink.props.widget
            else:
                self.fullscreen_drawable = get_drawable()
                self.fullscreen_window.add(self.fullscreen_drawable)
            self.fullscreen_drawable.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                                                Gdk.EventMask.BUTTON_RELEASE_MASK |
                                                Gdk.EventMask.KEY_PRESS_MASK |
                                                Gdk.EventMask.KEY_RELEASE_MASK |
                                                Gdk.EventMask.SCROLL_MASK)
            if connect is not None:
                connect(self.fullscreen_drawable)
            self.fullscreen_window.show_all()

            # Use black background
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b"#fullscreen_player { color:#fff; background-color: #000; }")
            context = Gtk.StyleContext()
            context.add_provider_for_screen(Gdk.Screen.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.fullscreen_window.show_all()
        self.fullscreen_window.get_window().fullscreen()
        self.fullscreen_window.grab_focus()

        # Do not use set_visual/set_widget so that the player does not
        # update self.xid and keep it as a reference
        if config.data.player['vout'] == 'gtk':
            # Remove from main GUI
            self.fullscreen_drawable.get_parent().remove(self.fullscreen_drawable)
            # Add to fullscreen_window
            self.fullscreen_window.add(self.fullscreen_drawable)
        else:
            self.reparent(self.fullscreen_drawable.get_id())

    def unfullscreen(self, *p):
        if config.data.player['vout'] == 'gtk':
            widget = self.imagesink.props.widget
            widget.get_parent().remove(widget)
            self.container.pack_start(widget, True, True, 0)
        else:
            self.reparent(self.xid)
        if not self.overlay.data and self.imageoverlay:
            # Reset imageoverlay data in any case
            self.imageoverlay.props.data = None
        if self.fullscreen_window.get_window():
            self.fullscreen_window.hide()
        else:
            # It has been destroyed
            self.fullscreen_window = None
            self.fullscreen_drawable = None
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

    def dump_bin(self, gbin, depth=0, recurse=-1, showcaps=True):
        return [ description
                 for element in reversed(list(gbin.iterate_elements()))
                 for description in self.dump_element(element, depth, recurse - 1) ]

    def dump_element(self, e, depth=0, recurse=-1, showcaps=True):
        """Return a list of strings describing the element.
        """
        descriptions = []
        indentstr = depth * 8 * ' '

        # print element path and factory
        path = e.get_path_string() + (isinstance(e, Gst.Bin) and '/' or '')
        factory = e.get_factory()
        if factory is not None:
            descriptions.append( '%s%s (%s)' % (indentstr, path, factory.get_name()) )
        else:
            descriptions.append( '%s%s (No factory)' % (indentstr, path) )

        # print info about each pad
        for p in e.pads:
            name = p.get_name()

            # negotiated capabilities
            caps = p.get_current_caps()
            if caps:
                capsname = caps.get_structure(0).get_name()
            elif showcaps:
                capsname = '; '.join(s.to_string() for s in set(p.get_current_caps() or []))
            else:
                capsname = None

            # flags
            flags = []
            if not p.is_active():
                flags.append('INACTIVE')
            if p.is_blocked():
                flags.append('BLOCKED')

            # direction
            direc = "=>" if p.get_direction() is Gst.PadDirection.SRC else "<="

            # peer
            peer = p.get_peer()
            if peer:
                peerpath = self.relpath(path, peer.get_path_string())
            else:
                peerpath = None

            # ghost target
            if isinstance(p, Gst.GhostPad):
                target = p.get_target()
                if target:
                    ghostpath = target.get_path_string()
                else:
                    ghostpath = None
            else:
                ghostpath = None

            line=[ indentstr, "    " ]
            if flags:
                line.append( ','.join(flags) )
            line.append(".%s" % name)
            if capsname:
                line.append( '[%s]' % capsname )
            if ghostpath:
                line.append( "ghosts %s" % self.relpath(path, ghostpath) )
            line.append( "%s %s" % (direc, peerpath) )

            #if peerpath and peerpath.find('proxy')!=-1: print peer
            descriptions.append( ''.join(line) )
        if recurse and isinstance(e, Gst.Bin):
            descriptions.extend( self.dump_bin(e, depth+1, recurse) )
        return descriptions

    def str_element(self, element):
        return "\n".join(self.dump_element(element))
