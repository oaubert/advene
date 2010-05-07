#! /usr/bin/python

"""Gstreamer SVGOverlay element

Copyright 2009 Olivier Aubert <olivier.aubert@liris.cnrs.fr>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import sys
import os

import gobject
gobject.threads_init()

import pygst
pygst.require('0.10')
import gst

import cairo

try:
    import rsvg
    print "Native RSVG support"
except ImportError:
    # Define a ctypes-based wrapper. 
    # Code adapted from http://cairographics.org/cairo_rsvg_and_python_in_windows/
    import ctypes
    print "ctypes RSVG support"

    if sys.platform == 'win32':
        l=ctypes.CDLL('librsvg-2-2.dll')
        g=ctypes.CDLL('libgobject-2.0-0.dll')
    elif sys.platform == 'darwin':
        try:
            l=ctypes.CDLL('librsvg-2.dylib')
            g=ctypes.CDLL('libgobject-2.0.dylib')
        except OSError:
            # Try to determine the .dylib location
            if os.path.exists('/opt/local/lib/librsvg-2.dylib'):
                # macports install.
                l=ctypes.CDLL('/opt/local/lib/librsvg-2.dylib')
                g=ctypes.CDLL('/opt/local/lib/libgobject-2.0.dylib')
            else:
                # .app bundle resource.
                d = os.path.dirname(os.path.abspath(sys.argv[0]))
                if os.path.basename(d) == 'Resources':
                    base=os.path.dirname(d)
                    l=ctypes.CDLL('%s/Frameworks/librsvg-2.2.dylib' % base)
                    g=ctypes.CDLL('%s/Frameworks/libgobject-2.0.0.dylib' % base)
                else:
                    # Cannot find librsvg
                    print "Cannot find librsvg"
                    l=None
                    g=None
    else:
        l=ctypes.CDLL('librsvg-2.so')
        g=ctypes.CDLL('libgobject-2.0.so')
    if g is not None:
        g.g_type_init()

    class rsvgHandle():
        class RsvgDimensionData(ctypes.Structure):
            _fields_ = [("width", ctypes.c_int),
                        ("height", ctypes.c_int),
                        ("em", ctypes.c_double),
                        ("ex", ctypes.c_double)]

        class PycairoContext(ctypes.Structure):
            _fields_ = [("PyObject_HEAD", ctypes.c_byte * object.__basicsize__),
                        ("ctx", ctypes.c_void_p),
                        ("base", ctypes.c_void_p)]

        def __init__(self, filename=None, data=None):
            error = ''
            if filename is not None:
                self.handle = l.rsvg_handle_new_from_file(filename, error)
            elif data is not None:
                self.handle = l.rsvg_handle_new_from_data(data, len(data), error)
            else:
                self.handle=None

        def get_dimension_data(self):
            svgDim = self.RsvgDimensionData()
            l.rsvg_handle_get_dimensions(self.handle, ctypes.byref(svgDim))
            return (svgDim.width, svgDim.height, svgDim.em, svgDim.ex)

        def render_cairo(self, ctx):
            ctx.save()
            z = self.PycairoContext.from_address(id(ctx))
            l.rsvg_handle_render_cairo(self.handle, z.ctx)
            ctx.restore()


    class rsvgClass():
        def Handle(self, filename=None, data=None):
            return rsvgHandle(filename=filename, data=data)

    rsvg = rsvgClass()

class SVGOverlay(gst.Element):
    __gtype_name__ = 'SVGOverlay'
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
        if self.svg is None:
            return self.srcpad.push(buffer)

        try:
            outbuf = buffer.copy_on_write ()
            self.draw_on(outbuf)
            return self.srcpad.push(outbuf)
        except:
            return gst.GST_FLOW_ERROR

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
        if data is not None:
            self.svg=rsvg.Handle(data=data)
        elif filename is not None:
            self.svg=rsvg.Handle(filename)
        else:
            self.svg=None

    def draw_on(self, buf):
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

        dim = self.svg.get_dimension_data()
        scale = cairo.Matrix( 1.0 * width / dim[0], 0, 0, 1.0 * height / dim[1], 0, 0 )
        ctx.set_matrix(scale)
        self.svg.render_cairo(ctx)

gst.element_register(SVGOverlay, 'svgoverlay')

if __name__ == '__main__':
    mainloop = gobject.MainLoop()

    if sys.argv[1:]:
        player=gst.element_factory_make('playbin')
        player.props.uri = 'file://' + sys.argv[1]
    
        bin=gst.Bin()
        elements = [
            gst.element_factory_make('textoverlay'),
            gst.element_factory_make('queue'),
            gst.element_factory_make('ffmpegcolorspace'),
            gst.element_factory_make('videoscale'),
            gst.element_factory_make('svgoverlay', 'overlay'),
            gst.element_factory_make('ffmpegcolorspace'),
            gst.element_factory_make('xvimagesink'),
            ]
        bin.add(*elements)
        gst.element_link_many(*elements)
        bin.add_pad(gst.GhostPad('sink', elements[0].get_pad('video_sink') or elements[0].get_pad('sink')))
        
        player.props.video_sink=bin
    else:
        player = gst.parse_launch('videotestsrc ! ffmpegcolorspace ! videoscale ! svgoverlay name=overlay ! ffmpegcolorspace ! autovideosink')
        bin = player
    
    pipe=player
    overlay=bin.get_by_name('overlay')

    def on_eos (bus, msg):
        mainloop.quit()
    bus = pipe.get_bus()
    bus.add_signal_watch()
    bus.connect('message::eos', on_eos)

    pipe.set_state (gst.STATE_PLAYING)

    import time
    def display():
        t=time.localtime()
        overlay.props.data='''<svg:svg height="160pt" preserveAspectRatio="xMinYMin meet" version="1" viewBox="0 0 200 160" width="200pt" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:svg="http://www.w3.org/2000/svg" xmlns:tal="foobar">
  <a title="nom=armee anglaise" xlink:href="http://localhost:1234/packages/Bataille/annotations/a9">
    <svg:circle cx="99" cy="73" fill="none" name="Circle([61, 44], [116, 99])" r="%d" stroke="red" style="stroke-width:2" />
  </a><svg:ellipse cx="72" cy="108" fill="none" name="" rx="55" ry="19" stroke="green" style="stroke-width:2" />
  <svg:ellipse tal:test="foo" cx="158" cy="109" fill="none" name="Ellipse([62, 81], [117, 121])" rx="27" ry="20" stroke="red" style="stroke-width:2" />
  <rect x='3' y='10' width="50" height="12" fill="black" stroke="white" />
  <text x='5' y='20' fill="white" font-size="10" stroke="white" font-family="sans">
%s
  </text>

</svg:svg>''' % (t[5], time.strftime("%H:%M:%S", t))
##        overlay.props.data='''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
##<svg height="800" version="1.0" width="600" x="0" xmlns="http://www.w3.org/2000/svg" xmlns:svg="http://www.w3.org/2000/svg" y="0">
##  <rect x='50' y='290' width='230' height='60' fill='black' stroke='black' /> 
##  <text x='55' y='335' fill="white" font-size="48" stroke="white" font-family="sans-serif">
##%s
##  </text>
##</svg>
##''' % time.strftime("%H:%M:%S", time.localtime())
        return True
    
    gobject.timeout_add(1000, display)
    try:
        mainloop.run()
    except:
        pass

    pipe.set_state (gst.STATE_NULL)
    pipe.get_state (gst.CLOCK_TIME_NONE)
