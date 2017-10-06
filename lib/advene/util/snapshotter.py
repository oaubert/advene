#! /usr/bin/python
#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2009-2017 Olivier Aubert <contact@olivieraubert.net>
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

"""Snapshotter class/utility.

This module offers the possiblity to extract png-encoded snapshots of
specific timestamps in a movie file. It can be used from any
application, or as a standalone application.

Command-line usage:
snapshotter.py file://uri/to/movie/file.avi 1200 2400 4600

This will capture snapshots for the given timestamps (in ms) and save them into /tmp.
"""
import sys

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import GObject, GLib, GstBase, Gst
GObject.threads_init()
Gst.init(None)

from threading import Event, Thread
import queue
import heapq
from urllib.parse import unquote

import logging
logger = logging.getLogger(__name__)

try:
    from evaluator import Evaluator
except ImportError:
    Evaluator=None

def debug(f):
    def wrap(*args):
        logger.warn("%s %s", f.__name__, args)
        return f(*args)
    return wrap

class NotifySink(GstBase.BaseSink):

    __gstmetadata__ = ("Notify sink", "Sink", "Notifying sink",
                       "Olivier Aubert <contact@olivieraubert.net>")

    __gsttemplates__ = (
        Gst.PadTemplate.new("sink",
                            Gst.PadDirection.SINK,
                            Gst.PadPresence.ALWAYS,
                            Gst.Caps.new_any()),
        )

    __gproperties__ = {
        'notify': ( GObject.TYPE_PYOBJECT, 'notify', 'The notify method', GObject.ParamFlags.READWRITE ),
        }

    def __init__(self):
        GstBase.BaseSink.__init__(self)
        self.set_sync(False)
        self._notify=None

    def do_preroll(self, buffer):
        logger.debug("do_preroll %s", self._notify)
        if self._notify is not None:
            self._notify(self.buffer_as_struct(buffer))
        return Gst.FlowReturn.OK

    def do_set_property(self, key, value):
        if key.name == 'notify':
            self._notify=value
        else:
            logger.info("No property %s" % key.name)

    def do_get_property(self, key):
        if key.name == 'notify':
            return self._notify
        else:
            logger.info("No property %s" % key.name)

    def buffer_as_struct(self, buffer):
        (res, mapinfo) = buffer.map(Gst.MapFlags.READ)
        if not res:
            logger.warn("Error in converting buffer")
            res = None
        else:
            pos = self.query_position(Gst.Format.TIME)[1]
            res = {
                'data': bytes(mapinfo.data),
                'type': 'PNG',
                'date': pos / Gst.MSECOND,
                'pts': buffer.pts / Gst.MSECOND,
                # Hardcoded size values. They are not used
                # by the application, since they are
                # encoded in the PNG file anyway.
                'width': 160,
                'height': 100 }
        buffer.unmap(mapinfo)
        return res

__gstelementfactory__ = ("notifysink", Gst.Rank.NONE, NotifySink)
def plugin_init(plugin, userarg):
    NotifySinkType = GObject.type_register(NotifySink)
    Gst.Element.register(plugin, 'notifysink', 0, NotifySinkType)
    return True

version = Gst.version()
reg = Gst.Plugin.register_static_full(version[0], version[1],
                                      'notify_plugin', 'Notify plugin',
                                      plugin_init, '1.0', 'Proprietary', 'abc', 'def', 'ghi', None)

class UniquePriorityQueue(queue.PriorityQueue):
    """PriorityQueue with unique elements.

    Adapted from http://stackoverflow.com/questions/5997189/how-can-i-make-a-unique-value-priority-queue-in-python
    Thanks to Eli Bendersky.
    """
    def _init(self, maxsize):
        super()._init(maxsize)
        self.values = set()

    def _put(self, item):
        if item[1] not in self.values:
            self.values.add(item[1])
            super()._put(item)

    def _get(self, heappop=heapq.heappop):
        item = super()._get()
        self.values.remove(item[1])
        return item

class Snapshotter(object):
    """Snapshotter class.

    Basic idea: define a "notify" method, which will get a dict as
    parameter. The dict contains the PNG-encoded snapshot ['data']
    and its timestamp ['date'].

    When you need to have a snapshot at a specific timestamp, call
    s.enqueue class with the timestamp. Your notify method will be
    called with the result.

    Setup note: the Snapshotter class runs a daemon thread
    continuously waiting for timestamps to process. Thus you should:
    * call GObject.threads_init() at the beginning of you application
    * invoke the "start" method to start the thread.

    """
    def __init__(self, notify=None, width=None):
        self.active = False
        self.notify=notify
        # Snapshot queue handling
        self.timestamp_queue=UniquePriorityQueue()

        self.snapshot_ready=Event()
        self.thread_running=False
        self.should_clear = False

        # Pipeline building
        self.videobin = Gst.Bin()
        self.videobin.set_name('videosink')

        self.player = Gst.ElementFactory.make("playbin")

        csp = Gst.ElementFactory.make('videoconvert')
        pngenc = Gst.ElementFactory.make('pngenc')
        queue = Gst.ElementFactory.make('queue')
        sink = NotifySink()

        fakesink = Gst.ElementFactory.make('fakesink', 'audiosink')
        self.player.set_property('audio-sink', fakesink)

        if width is not None:
            caps = Gst.Caps.from_string("video/x-raw,width=%d,pixel-aspect-ratio=(fraction)1/1" % width)
            filter_ = Gst.ElementFactory.make("capsfilter", "filter")
            filter_.set_property("caps", caps)
            scale=Gst.ElementFactory.make('videoscale')
            l=(csp, scale, filter_, pngenc, queue, sink)
        else:
            l=(csp, pngenc, queue, sink)

        for el in l:
            self.videobin.add(el)
        for src, dst in zip(l, l[1:]):
            src.link(dst)
        # Keep a reference on all pipeline elements, so that they are not garbage-collected
        self._elements = l

        self._ghostpad = Gst.GhostPad.new('sink', csp.get_static_pad('sink'))
        self._ghostpad.set_active(True)
        self.videobin.add_pad(self._ghostpad)

        self.player.set_property('video-sink', self.videobin)

        bus=self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_bus_message)
        bus.add_signal_watch()
        bus.connect('message::error', self.on_bus_message_error)
        bus.connect('message::warning', self.on_bus_message_warning)

        sink.props.notify=self.queue_notify

    def get_uri(self):
        return self.player.get_property('current-uri')

    def set_uri(self, uri):
        logger.debug("set_uri %s", uri)
        if uri:
            self.player.set_state(Gst.State.NULL)
            self.player.set_property('uri', uri)
            uri = self.player.get_property('uri')
            if uri and Gst.uri_is_valid(uri):
                self.active = True
            else:
                self.active = False
            self.player.set_state(Gst.State.PAUSED)
            self.enqueue(0)
        else:
            self.active = False
            self.player.set_state(Gst.State.NULL)

    def on_bus_message(self, bus, message):
        s = message.get_structure()
        if s is None:
            return
        logger.debug("Bus message::", s.get_name())

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
        logger.warn("%s: %s", title, message)
        return True

    def simple_notify(self, struct):
        """Basic single-snapshot method.

        Used for debugging.
        """
        if struct is None:
            logger.warn("Snapshotter: invalid struct")
            return True
        logger.info("Timecode %010d - pts %010d" % (struct['date'],
                                                    struct['pts']))
        t = struct['date']
        fname='/tmp/%010d.png' % t
        f=open(fname, 'wb')
        f.write(struct['data'])
        f.close()
        logger.info("Snapshot written to" + fname)
        return True

    def snapshot(self, t):
        """Set movie time to a specific time.
        """
        p = int(t * Gst.MSECOND)
        logger.debug("Seeking to %d", t)
        self.player.set_state(Gst.State.PAUSED)
        res = self.player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE, p)
        if not res:
            logger.debug("Snapshotter error when sending event for %d %s. ", t, res)
            # Enqueue again
            self.enqueue(t)
        return True

    def enqueue(self, *l):
        """Enqueue timestamps to capture.
        """
        if not self.active:
            return
        for t in l:
            self.timestamp_queue.put_nowait( (t, t) )
        logger.debug("----- enqueued elements %s (%d total)", l, self.timestamp_queue.qsize())
        self.snapshot_ready.set()

    def process_queue(self):
        """Process the timestamp queue.

        This method is meant to run continuously in its own thread.
        """
        self.thread_running=True
        while True:
            self.snapshot_ready.wait()
            if self.should_clear:
                # Clear the queue
                self.should_clear = False
                while True:
                    try:
                        # FIXME: this could potentially deadlock, if
                        # there is a producer thread that continuously
                        # adds new elements.
                        self.timestamp_queue.get_nowait()
                    except queue.Empty:
                        break
            (t, dummy) = self.timestamp_queue.get()
            self.snapshot_ready.clear()
            self.snapshot(t)
        return True

    def clear(self):
        """Clear the queue.
        """
        if not self.timestamp_queue.empty():
            self.should_clear = True
        return True

    def queue_notify(self, struct):
        """Notification method.

        It processes the captured buffer and unlocks the
        snapshot_event to process further timestamps.
        """
        if self.notify is not None:
            # Add media info to the structure
            struct['media'] = unquote(self.get_uri().replace('file://', ''))
            self.notify(struct)
        # We are ready to process the next snapshot
        self.snapshot_ready.set()
        return True

    def start(self):
        """Start the snapshotter thread.
        """
        t=Thread(target=self.process_queue)
        t.setDaemon(True)
        t.start()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    try:
        uri=sys.argv[1]
        if uri.startswith('/'):
            uri='file://'+uri
    except IndexError:
        uri='file:///data/video/Bataille.avi'

    s=Snapshotter(width=160)
    s.set_uri(uri)
    s.notify=s.simple_notify
    s.start()

    if sys.argv[2:]:
        # Timestamps have been specified. Non-interactive version.
        s.enqueue( *(int(t) for t in sys.argv[2:]) )

        loop=GObject.MainLoop()
        def wait_for_completion():
            if s.timestamp_queue.empty():
                # Quit application
                s.snapshot_ready.wait()
                loop.quit()
            return True
        GLib.idle_add(wait_for_completion)
        loop.run()
    else:
        if Evaluator is None:
            logger.warn("Missing evaluator module.\nFetch it from the repository")
            sys.exit(0)

        # Adding the following lines breaks the code, with a warning:
        #    sys:1: Warning: cannot register existing type `GstSelectorPad'
        #    sys:1: Warning: g_object_new: assertion `G_TYPE_IS_OBJECT (object_type)' failed
        #pipe=Gst.parse_launch('playbin uri=file:///media/video/Bataille.avi')
        #pipe.set_state(Gst.State.PLAYING)

        ev=Evaluator(globals_=globals(), locals_=locals())
        ev.set_expression('s.enqueue(12000, 24000, 36000)')
        ev.run()
