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
import cairo

# Advene part
import advene.core.config as config

import advene.util.helper as helper
import advene.gui.popup

class GenericColorButtonWidget(gtk.DrawingArea):
    """ Widget emulating a color button widget
    """
    def __init__(self, element=None, container=None):
        gtk.DrawingArea.__init__(self)
        self.set_flags(self.flags() | gtk.CAN_FOCUS)
        self.element=element

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

        #self.connect('event', self.debug_cb, "Event")
        #self.connect_after('event', self.debug_cb, "After")

        self.cached_surface = None
        self.cached_context = None

        # Initialize the size
        self.set_size_request(*self.needed_size())

    def reset_surface_size(self, width=None, height=None):
        if not self.window:
            return False
        s=self.window.get_size()
        if width is None:
            width=s[0]
        if height is None:
            height=s[1]
        if (self.cached_surface
            and self.cached_surface.get_width() == width
            and self.cached_surface.get_height() == height):
            return True
        self.cached_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
        self.cached_context = cairo.Context(self.cached_surface)
        self.set_size_request(width, height)
        self.window.lower()
        return True

    def realize_cb(self, widget):
        if not self.reset_surface_size(*self.needed_size()):
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

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        return (40, 10)

    def draw(self, context, width, height):
        """Draw the widget.

        Method to be implemented by subclasses
        """
        context.rectangle(0, 0, width, height)
        if self.local_color is not None:
            color=self.local_color
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, 1)
        else:
            rgba=(1.0, 1.0, 1.0, 1)
        context.set_source_rgba(*rgba)
        context.fill()

    def update_widget(self, *p):
        if not self.window:
            return False
        if self.cached_context is None:
            return False

        # First check width
        w=self.needed_size()[0]
        if w != self.cached_surface.get_width():
            self.reset_surface_size(w, self.container.button_height)

        bwidth=self.cached_surface.get_width()
        bheight=self.cached_surface.get_height()

        self.draw(self.cached_context, bwidth, bheight)

        self.refresh()
        return True

    def refresh(self):
        if self.window:
            width = self.cached_surface.get_width()
            height = self.cached_surface.get_height()
            self.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, width, height), False)

    def expose_cb(self, widget, event):
        if self.cached_surface is None:
            return False

        context = widget.window.cairo_create()

        # Set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y,
                          event.area.width, event.area.height)
        context.clip()

        # copy the annotation_surface onto this context
        context.set_source_surface(self.cached_surface, 0, 0)
        context.paint()
        return False

class AnnotationWidget(GenericColorButtonWidget):
    """ Widget representing an annotation
    """
    def __init__(self, annotation=None, container=None):
        self.annotation=annotation
        GenericColorButtonWidget.__init__(self, element=annotation, container=container)
        self.connect("key_press_event", self.keypress, self.annotation)
        self.connect("enter_notify_event", lambda b, e: b.grab_focus() and True)
        self.connect("drag_data_get", self.drag_sent)
        # The widget can generate drags
        self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                             config.data.drag_type['annotation']
                             + config.data.drag_type['uri-list']
                             + config.data.drag_type['text-plain']
                             + config.data.drag_type['TEXT']
                             + config.data.drag_type['STRING']
                             + config.data.drag_type['timestamp']
                             ,
                             gtk.gdk.ACTION_LINK)

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        if targetType == config.data.target_type['annotation']:
            selection.set(selection.target, 8, widget.annotation.uri)
        elif targetType == config.data.target_type['uri-list']:
            c=self.controller.build_context(here=widget.annotation)
            uri=c.evaluateValue('here/absolute_url')
            selection.set(selection.target, 8, uri)
        elif (targetType == config.data.target_type['text-plain']
              or targetType == config.data.target_type['TEXT']
              or targetType == config.data.target_type['STRING']):
            selection.set(selection.target, 8, widget.annotation.content.data)
        elif targetType == config.data.target_type['timestamp']:
            selection.set(selection.target, 8, str(widget.annotation.fragment.begin))
        else:
            return False
        return True

    def keypress(self, widget, event, annotation):
        if event.keyval == gtk.keysyms.e:
            self.controller.gui.edit_element(annotation)
            return True
        elif event.keyval == gtk.keysyms.space:
            # Play the annotation
            c=self.controller
            pos = c.create_position (value=annotation.fragment.begin,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            c.gui.set_current_annotation(annotation)
            return True
        return False

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        return (self.container.unit2pixel(self.annotation.fragment.duration),
                self.container.button_height)

    def draw(self, context, width, height):
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
        context.rectangle(0, 0, width, height)
        if self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotation)
        if color:
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, 1)
        else:
            rgba=(1.0, 1.0, 1.0, 1)
        context.set_source_rgba(*rgba)
        context.fill_preserve()

        # Draw the border
        if self.is_focus():
            context.set_line_width(4)
        else:
            context.set_line_width(1)
        context.set_source_rgba(0, 0, 0, 1)
        context.stroke()

        # Draw the text
        if self.annotation.relations:
            weight=cairo.FONT_WEIGHT_BOLD
        else:
            weight=cairo.FONT_WEIGHT_NORMAL
        context.select_font_face("Helvetica",
                                 cairo.FONT_SLANT_NORMAL, weight)
        context.set_font_size(config.data.preferences['timeline']['font-size'])

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, 1)
        title=self.controller.get_title(self.annotation)
        context.show_text(title)

class AnnotationTypeWidget(GenericColorButtonWidget):
    """ Widget representing an annotation type
    """
    def __init__(self, annotationtype=None, container=None):
        self.annotationtype=annotationtype
        self.width=None
        GenericColorButtonWidget.__init__(self, element=annotationtype, container=container)
        self.connect("key_press_event", self.keypress, self.annotationtype)
        self.connect("button_press_event", self.buttonpress)
        self.connect("enter_notify_event", lambda b, e: b.grab_focus() and True)

    def keypress(self, widget, event, annotationtype):
        if event.keyval == gtk.keysyms.e:
            self.controller.gui.edit_element(annotationtype)
            return True
        return False

    def buttonpress(self, widget, event):
        """Display the popup menu when right-clicking on annotation type.
        """
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            menu=advene.gui.popup.Menu(widget.annotationtype,
                                       controller=self.controller)
            menu.popup()
            return True
        return False

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        w=self.width or 60
        return (w, self.container.button_height)

    def draw(self, context, width, height):
        context.rectangle(0, 0, width, height)
        if self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotationtype)
        if color:
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, 1)
        else:
            rgba=(1.0, 1.0, 1.0, 1)
        context.set_source_rgba(*rgba)
        context.fill_preserve()

        # Draw the border
        if self.is_focus():
            context.set_line_width(4)
        else:
            context.set_line_width(1)
        context.set_source_rgba(0, 0, 0, 1)
        context.stroke()

        # Draw the text
        context.select_font_face("Helvetica",
                                 cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(config.data.preferences['timeline']['font-size'])

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, 1)
        title=self.controller.get_title(self.annotationtype)
        context.show_text(title)
        if self.width is None:
            ext=context.text_extents(title)
            if ext[2] != self.width:
                self.width=long(ext[2]) + 5
                self.reset_surface_size(self.width, self.container.button_height)
