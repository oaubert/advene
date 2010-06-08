#! /usr/bin/python
#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2009 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
import os

import gobject
import gst
import gtk
gtk.gdk.threads_init ()

from threading import Event, Thread
import Queue
try:
    from evaluator import Evaluator
except ImportError:
    Evaluator=None

class NotifySink(gst.BaseSink):
    __gsttemplates__ = (
        gst.PadTemplate("sink",
                        gst.PAD_SINK,
                        gst.PAD_ALWAYS,
                        gst.caps_new_any()),
        )

    __gstdetails__ = ("Notify sink", "Sink", "Notifying sink",
                      "Olivier Aubert <olivier.aubert@liris.cnrs.fr>")

    __gproperties__ = {
        'notify': ( gobject.TYPE_PYOBJECT, 'notify', 'The notify method', gobject.PARAM_READWRITE ),
        }

    def __init__(self):
        gst.BaseSink.__init__(self)
        self.set_sync(False)
        self._notify=None

    #def do_render(self, buffer):
    #    return gst.FLOW_OK

    def do_preroll(self, buffer):
        if self._notify is not None:
            self._notify(buffer)
        return gst.FLOW_OK

    def do_set_property(self, key, value):
        if key.name == 'notify':
            self._notify=value
        else:
            print "No property %s" % key.name

    def do_get_property(self, key):
        if key.name == 'notify':
            return self._notify
        else:
            print "No property %s" % key.name
gst.element_register(NotifySink, 'notifysink')
gobject.type_register(NotifySink)

class Snapshotter(object):
    """Snapshotter class.

    Basic idea: define a "notify" method, which will get a gst.Buffer
    as parameter. The buffer contains the PNG-encoded snapshot (and
    its timestamp in buffer.timestamp).

    When you need to have a snapshot at a specific timestamp, call
    s.enqueue class with the timestamp. You notify method will be
    called with the result.

    Setup note: the Snapshotter class runs a daemon thread
    continuously waiting for timestamps to process. Thus you should:
    * call gtk.gdk.threads_init() at the beginning of you application
    * invoke the "start" method to start the thread.
    """
    def __init__(self, notify=None, width=None):
        self.notify=notify
        # Snapshot queue handling
        self.timestamp_queue=Queue.Queue()
        self.snapshot_ready=Event()
        self.thread_running=False

        # Pipeline building
        videobin=gst.Bin()

        self.player=gst.element_factory_make("playbin")

        csp=gst.element_factory_make('ffmpegcolorspace')
        pngenc=gst.element_factory_make('pngenc')
        queue=gst.element_factory_make('queue')
        sink=gst.element_factory_make('notifysink')

        if width is not None:
            filter=gst.element_factory_make("capsfilter")
            filter.set_property("caps", gst.Caps("video/x-raw-rgb,width=%d,pixel-aspect-ratio=(fraction)1/1" % width))
            scale=gst.element_factory_make('videoscale')            
            l=(csp, scale, filter, pngenc, queue, sink)
        else:
            l=(csp, pngenc, queue, sink)

        videobin.add(*l)
        gst.element_link_many(*l)

        videobin.add_pad(gst.GhostPad('sink', csp.get_pad('sink')))

        self.player.props.video_sink=videobin

        bus=self.player.get_bus()
        bus.enable_sync_message_emission()
        bus.connect('sync-message::element', self.on_bus_message)

        sink.props.notify=self.queue_notify

    def set_uri(self, uri):
        self.player.set_state(gst.STATE_NULL)
        self.player.props.uri=uri
        self.player.set_state(gst.STATE_PAUSED)

    def on_bus_message(self, bus, message):
        if message.structure is None:
            return
        print "Bus message::", message.structure.get_name()

    def simple_notify(self, buffer):
        """Basic single-snapshot method.

        Used for debugging.
        """
        t=(buffer.timestamp / gst.MSECOND)
        fname='/tmp/%010d.png' % t
        f=open(fname, 'w')
        f.write(buffer.data)
        f.close()
        print "Snapshot written to", fname
        os.system('qiv %s &' % fname)
        return True

    def snapshot(self, t):
        """Set movie time to a specific time.
        """
        p = long(t * gst.MSECOND)
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET, p,
                                   gst.SEEK_TYPE_NONE, 0)
        self.player.set_state(gst.STATE_PAUSED)
        res=self.player.send_event(event)
        if not res:
            print "Error when sending event"
        return True

    def enqueue(self, *l):
        """Enqueue timestamps to capture.
        """
        for t in l:
            self.timestamp_queue.put_nowait(t)
        self.snapshot_ready.set()

    def process_queue(self):
        """Process the timestamp queue.
        
        This method is meant to run continuously in its own thread.
        """
        self.thread_running=True
        while True:
            #print "Waiting for event"
            self.snapshot_ready.wait()
            #print "Getting timestamp"
            t=self.timestamp_queue.get()
            #print "Clearing event"
            self.snapshot_ready.clear()
            #print "Snapshot", t
            self.snapshot(t)
        return True

    def queue_notify(self, buffer):
        """Notification method.

        It processes the captured buffer and unlocks the
        snapshot_event to process further timestamps.
        """
        if self.notify is not None:
            self.notify(buffer)
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
    try:
        uri=sys.argv[1]
        if uri.startswith('/'):
            uri='file://'+uri
    except IndexError:
        uri='file:///media/video/Bataille.avi'

    s=Snapshotter(width=160)
    s.set_uri(uri)
    s.notify=s.simple_notify
    s.start()

    if sys.argv[2:]:
        # Timestamps have been specified. Non-interactive version.
        s.enqueue( *(long(t) for t in sys.argv[2:]) )

        loop=gobject.MainLoop()
        def wait_for_completion():
            if s.timestamp_queue.empty():
                # Quit application
                s.snapshot_ready.wait()
                loop.quit()
            return True
        gobject.idle_add(wait_for_completion)
        loop.run()
    else:
        if Evaluator is None:
            print "Missing evaluator module.\nFetch it from http://svn.gna.org/viewcvs/advene/trunk/lib/advene/gui/evaluator.py."
            sys.exit(0)

        # Adding the following lines breaks the code, with a warning:
        #    sys:1: Warning: cannot register existing type `GstSelectorPad'
        #    sys:1: Warning: g_object_new: assertion `G_TYPE_IS_OBJECT (object_type)' failed
        #pipe=gst.parse_launch('playbin uri=file:///media/video/Bataille.avi')
        #pipe.set_state(gst.STATE_PLAYING)

        ev=Evaluator(globals_=globals(), locals_=locals())
        ev.locals_['self']=ev
        window=ev.popup(embedded=False)
        ev.set_expression('s.enqueue(12000, 24000, 36000)')
        window.connect ("destroy", lambda e: gtk.main_quit())

        gtk.main()
