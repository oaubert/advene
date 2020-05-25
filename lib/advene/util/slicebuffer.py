#! /usr/bin/python

"""Gstreamer SliceBuffer element

Copyright 2011-2017 Olivier Aubert <contact@olivieraubert.net>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 2.1 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
import logging
logger = logging.getLogger(__name__)

#FIXME: code not yet converted to gst1.x
import sys

import gobject
gobject.threads_init()

import pygst
pygst.require('0.10')
import gst

import cairo

class SliceBuffer(gst.Element):
    __gtype_name__ = 'SliceBuffer'
    __gstdetails__ = ("Slice buffer", "Filter/Editor/Video", "Buffers slices of data",
                      "Olivier Aubert <contact@olivieraubert.net>")

    __gproperties__ = {
        'slicewidth':  ( gobject.TYPE_INT, 'slicewidth', 'Width of slices', 0, 65536, 0, gobject.PARAM_WRITABLE ),
        'offset': (gobject.TYPE_INT, 'offset', 'Offset of samples in the source video. If < 0, use the original offset.', -65536, 65536, 0, gobject.PARAM_WRITABLE),
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

        self.slicewidth = 1
        self.offset = 128
        self._index = 0
        self._buffer  = None
        self._surface = None

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

    def chainfunc(self, pad, buf):
        caps = buf.get_caps()
        width = caps[0]['width']
        height = caps[0]['height']
        if self._surface is None:
            # Need to initialize
            self._buffer = buf.copy_on_write ()
            self._surface = cairo.ImageSurface.create_for_data (self._buffer, cairo.FORMAT_ARGB32, width, height, 4 * width)
            self._ctx = cairo.Context(self._surface)
            self._ctx.set_source_rgb(0, 0, 0)
            self._ctx.rectangle(0, 0, width, height)
            self._ctx.fill()
            self._index = 0

        # Get rectangle
        if self.offset < 0:
            # get the rectangle at the position it will be in the destination buffer
            source_x = (self._index * self.slicewidth) % width
        else:
            # Get the rectangle at the position specified by offset
            source_x = self.offset
        dest_x = (self._index * self.slicewidth) % (width - self.slicewidth)
        self._index += 1

        # Copy slice into buffer
        surf = cairo.ImageSurface.create_for_data(buf.copy_on_write(), cairo.FORMAT_ARGB32, width, height, 4 * width)
        self._ctx.set_operator(cairo.OPERATOR_SOURCE)
        self._ctx.set_source_surface(surf, dest_x - source_x, 0)
        self._ctx.rectangle(dest_x, 0, self.slicewidth, height)
        self._ctx.fill()

        # Restamp result buffer using incoming buffer information
        self._buffer.stamp(buf)
        return self.srcpad.push(self._buffer)

    def eventfunc(self, pad, event):
        return self.srcpad.push_event (event)

    def srcqueryfunc (self, pad, query):
        return self.sinkpad.query (query)

    def srceventfunc (self, pad, event):
        return self.sinkpad.push_event (event)

    def do_change_state(self, transition):
        #if transition in [gst.STATE_CHANGE_READY_TO_PAUSED, gst.STATE_CHANGE_PAUSED_TO_READY]:
        #    self._reset()
        return gst.Element.do_change_state(self, transition)

    def do_set_property(self, key, value):
        if key.name == 'slicewidth':
            self.slicewidth = value
        elif key.name == 'offset':
            self.offset = value
        else:
            logger.error("No property %s" % key.name)

gst.element_register(SliceBuffer, 'slicebuffer')

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    mainloop = gobject.MainLoop()

    files = [ a for a in sys.argv[1:] if not '=' in a ]
    params = {}
    for p in [ a for a in sys.argv[1:] if '=' in a ]:
        name, value = p.split('=')
        params[name] = value

    # Possible parameters:
    # width=pixel_width
    # slicewidth=NNN
    # offset=column_number
    if files:
        player=gst.element_factory_make('playbin')
        player.props.uri = 'file://' + files[0]

        bin=gst.Bin()
        elements = [
            gst.element_factory_make('ffmpegcolorspace'),
            gst.element_factory_make('videoscale'),
            gst.element_factory_make('slicebuffer', 'slicer'),
            gst.element_factory_make('capsfilter', 'capsfilter'),
            gst.element_factory_make('ffmpegcolorspace'),
            gst.element_factory_make('xvimagesink', 'videosink'),
            ]
        bin.add(*elements)
        gst.element_link_many(*elements)
        bin.add_pad(gst.GhostPad('sink', elements[0].get_pad('video_sink') or elements[0].get_pad('sink')))

        slicer = bin.get_by_name('slicer')
        capsfilter = bin.get_by_name('capsfilter')
        for name, value in params.iteritems():
            if name == 'width':
                caps = gst.caps_from_string('video/x-raw-rgb,%s' % p)
                capsfilter.set_property('caps', caps)
            else:
                if name in ('slicewidth', 'offset'):
                    slicer.set_property(name, int(value))
        videosink = bin.get_by_name('videosink')
        videosink.set_property('sync', False)
        player.props.video_sink=bin
    else:
        player = gst.parse_launch('autovideosrc ! ffmpegcolorspace ! videoscale ! slicebuffer %s ! ffmpegcolorspace ! xvimagesink' % " ".join(params))
        bin = player

    pipe=player
    overlay=bin.get_by_name('overlay')


    def on_msg(bus, msg):
        s = msg.structure
        if s is None:
            return True
        if s.has_field('gerror'):
            logger.error("MSG %s", msg.structure['debug'])

    def on_eos (bus, msg):
        mainloop.quit()
    bus = pipe.get_bus()
    bus.add_signal_watch()
    bus.connect('message::eos', on_eos)
    bus.connect('message', on_msg)

    logger.info("PLAYING")
    pipe.set_state (gst.STATE_PLAYING)

    # Increase playing rate
    if params['rate']:
        event = gst.event_new_seek(int(params['rate']), gst.FORMAT_TIME,
                                   gst.SEEK_FLAG_FLUSH | gst.SEEK_FLAG_ACCURATE,
                                   gst.SEEK_TYPE_SET, 0,
                                   gst.SEEK_TYPE_NONE, 0)
        res = pipe.send_event(event)

    try:
        mainloop.run()
    except:
        pass

    pipe.set_state (gst.STATE_NULL)
    pipe.get_state (gst.CLOCK_TIME_NONE)
