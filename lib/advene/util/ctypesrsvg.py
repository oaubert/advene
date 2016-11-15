#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2016 Olivier Aubert <contact@olivieraubert.net>
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

"""ctypes-based wrapper mimicking native py-rsvg API
"""

# Code adapted from http://cairographics.org/cairo_rsvg_and_python_in_windows/
import sys
import os
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
    try:
        # First try numbered versions.
        l=ctypes.CDLL('librsvg-2.so.2')
        g=ctypes.CDLL('libgobject-2.0.so.0')
    except OSError:
        l=ctypes.CDLL('librsvg-2.so')
        g=ctypes.CDLL('libgobject-2.0.so')

if g is not None:
    g.g_type_init()

class RsvgDimensionData(ctypes.Structure):
    _fields_ = [("width", ctypes.c_int),
                ("height", ctypes.c_int),
                ("em", ctypes.c_double),
                ("ex", ctypes.c_double)]

class PycairoContext(ctypes.Structure):
    _fields_ = [("PyObject_HEAD", ctypes.c_byte * object.__basicsize__),
                ("ctx", ctypes.c_void_p),
                ("base", ctypes.c_void_p)]

class GError(ctypes.Structure):
    _fields_ = [("quark", ctypes.c_uint32),
                ("code", ctypes.c_int),
                ("message", ctypes.c_char_p)]

class Handle(object):
    def __init__(self, filename=None, data=None):
        error = ctypes.POINTER(GError)() # A GError
        self.handle = None
        if filename is not None:
            self.handle = l.rsvg_handle_new_from_file(unicode(filename).encode('utf8'), ctypes.byref(error))
        elif data is not None:
            if isinstance(data, unicode):
                data = data.encode('utf8')
            self.handle = l.rsvg_handle_new_from_data(data, len(data), ctypes.byref(error))
        if error:
            print "SVG rendering error:", error.contents.message
            g.g_clear_error(ctypes.byref(error))

    def __del__(self):
        if self.handle and l:
            l.rsvg_handle_free(self.handle)
            self.handle = None

    def get_dimension_data(self):
        if self.handle:
            svgDim = RsvgDimensionData()
            l.rsvg_handle_get_dimensions(self.handle, ctypes.byref(svgDim))
            return (svgDim.width, svgDim.height, svgDim.em, svgDim.ex)
        else:
            return (320, 200, 1.0, 1.0)

    def render_cairo(self, ctx):
        if self.handle:
            ctx.save()
            z = PycairoContext.from_address(id(ctx))
            l.rsvg_handle_render_cairo(self.handle, z.ctx)
            ctx.restore()

