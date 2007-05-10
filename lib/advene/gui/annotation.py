#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Annotation widget.

Documentation:
http://www.tortall.net/mu/wiki/CairoTutorial

http://www.pygtk.org/pygtk2reference/class-pangocairocairocontext.html
http://www.nabble.com/Image-Manipulation-under-pyGTK-t3484319.html
http://lists.freedesktop.org/archives/cairo/2007-February/009810.html
http://www.tortall.net/mu/wiki/CairoTutorial#understanding-text
http://nzlinux.virtuozzo.co.nz/blogs/2005/08/18/using-pangocairo/
http://laszlok2.blogspot.com/2006/05/prince-of-cairo_28.html
"""

import gtk
import gobject
import cairo
import pangocairo

from gettext import gettext as _

# Advene part
import advene.core.config as config

import advene.util.helper as helper

class AnnotationWidget(gtk.DrawingArea):
    """ Widget representing an annotation
    """
    def __init__(self, annotation=None, container=None):
        gtk.DrawingArea.__init__(self)
        self.set_flags(self.flags() | gtk.CAN_FOCUS)
        self.annotation=annotation
        
        # If not None, it should contain a gtk.gdk.Color
        # which will override the normal color
        self.local_color=None

        # container is the Advene view instance that manages this instance
        self.container=container
        if container:
            self.controller=container.controller
        else:
            self.controller=None
        self.set_events(gtk.gdk.POINTER_MOTION_MASK |
                        gtk.gdk.BUTTON_PRESS_MASK |
                        gtk.gdk.BUTTON_RELEASE_MASK |
                        gtk.gdk.BUTTON1_MOTION_MASK |
                        gtk.gdk.BUTTON3_MOTION_MASK |
                        gtk.gdk.KEY_PRESS_MASK |
                        gtk.gdk.KEY_RELEASE_MASK |
                        gtk.gdk.FOCUS_CHANGE_MASK |
                        gtk.gdk.ENTER_NOTIFY_MASK |
                        gtk.gdk.LEAVE_NOTIFY_MASK |
                        gtk.gdk.SCROLL_MASK)

        self.connect("expose-event", self.expose_cb)
        self.connect("realize", self.realize_cb)
        self.connect_after('size-request', self.size_request_cb)
        self.connect('focus-in-event', self.update_widget)
        self.connect('focus-out-event', self.update_widget)

        self.annotation_surface = None
        self.annotation_context = None

        w=self.container.unit2pixel(self.annotation.fragment.duration)
        self.set_size_request(w, self.container.button_height)

    def reset_surface_size(self, width=None, height=None): 
        if not self.window:
            return False
        s=self.window.get_size()
        if width is None:
            width=s[0]
        if height is None: 
            height=s[1]
        if (self.annotation_surface 
            and self.annotation_surface.get_width() == width
            and self.annotation_surface.get_height() == height):
            return True
        self.annotation_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self.annotation_context = cairo.Context(self.annotation_surface)
        self.set_size_request(width, height)
        self.window.lower()
        return True

    def realize_cb(self, widget):
        if not self.reset_surface_size(self.container.unit2pixel(self.annotation.fragment.duration),
                                       self.container.button_height):
            return True
        self.update_widget()
        return True

    def size_request_cb(self, widget, requisition):
        self.refresh()
        return False

    def set_color(self, color=None):
        self.local_color=color
        self.update_widget()
        return True

    def update_widget(self, *p):
        if not self.window:
            return False
        if self.annotation_context is None:
            return False

        # First check width
        w=self.container.unit2pixel(self.annotation.fragment.duration)
        if w != self.annotation_surface.get_width():
            self.reset_surface_size(w, self.container.button_height)

        bwidth=self.annotation_surface.get_width()
        bheight=self.annotation_surface.get_height()

        c=self.annotation_context
        
        # c.move_to(0, 0)
        # c.rel_line_to(0, bheight)
        # c.rel_line_to(bwidth, 0)
        # c.rel_line_to(0, -bheight)
        # if bwidth > 12:
        #     c.rel_line_to(-4, 0)
        #     c.rel_line_to(0, 4)
        #     c.rel_line_to(-(bwidth-8), 0)
        #     c.rel_line_to(0, -4)
        #     c.close_path()
        self.annotation_context.rectangle(0, 0, bwidth, bheight)
        if self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotation)
        if color:
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, .7)
        else:
            rgba=(1.0, 1.0, 1.0, .7)
        self.annotation_context.set_source_rgba(*rgba)
        self.annotation_context.fill_preserve()
        
        # Draw the border
        if self.is_focus():
            self.annotation_context.set_line_width(4)
        else:
            self.annotation_context.set_line_width(1)
        self.annotation_context.set_source_rgba(0, 0, 0, .9)
        self.annotation_context.stroke()
        
        # Draw the text
        if self.annotation.relations:
            weight=cairo.FONT_WEIGHT_BOLD
        else:
            weight=cairo.FONT_WEIGHT_NORMAL
        self.annotation_context.select_font_face("Helvetica",
                                                 cairo.FONT_SLANT_NORMAL, weight)
        self.annotation_context.set_font_size(12)
        
        self.annotation_context.move_to(2, int(bheight * 0.7))
        
        self.annotation_context.set_source_rgba(0, 0, 0, .9)
        title=self.controller.get_title(self.annotation)
        self.annotation_context.show_text(title)
        self.annotation_context.stroke()
        self.refresh()
        return True

    def refresh(self):
        if self.window:
            width = self.annotation_surface.get_width()
            height = self.annotation_surface.get_height()
            self.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, width, height), False)

    def expose_cb(self, widget, event):
        if self.annotation_surface is None:
            return False

        context = widget.window.cairo_create()

        # Set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y,
                          event.area.width, event.area.height)
        context.clip()

        # copy the annotation_surface onto this context
        context.set_source_surface(self.annotation_surface, 0, 0)
        #context.paint_with_alpha(.9)
        context.paint()
        return False
