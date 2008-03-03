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

import struct

import gtk
import cairo

# Advene part
import advene.core.config as config
from advene.gui.util import png_to_pixbuf
import advene.util.helper as helper
from advene.model.annotation import Annotation

import advene.gui.popup

active_color=gtk.gdk.color_parse ('#fdfd4b')

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
        # Alpha will be used to draw features
        self.alpha=1.0
        # expose_alpha will be used when rendering the surface on the widget
        self.expose_alpha=1.0

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

        self.default_size = (40, 10)
        # Initialize the size
        self.set_size_request(*self.needed_size())

    def _drag_begin(self, widget, context):
        cm=gtk.gdk.colormap_get_system()
        w,h=self.needed_size()
        pixmap=gtk.gdk.Pixmap(None, w, h, cm.get_visual().depth)
        cr=pixmap.cairo_create()
        self.draw(cr, w, h)
        cr.paint_with_alpha(0.0)
        widget.drag_source_set_icon(cm, pixmap)
        return True

    def reset_surface_size(self, width=None, height=None):
        """Redimension the cached widget content.
        """
        if not self.window:
            return False
        s=self.window.get_size()
        if width is None:
            width=s[0]
        if height is None:
            height=s[1]
        if width < 0:
            print "Error: width ", width, " < 0 for ", self.element.id
            width=5
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
        """Callback for the realize event.
        """
        if not self.reset_surface_size(*self.needed_size()):
            return True
        self.update_widget()
        return True

    def size_request_cb(self, widget, requisition):
        """Callback for the size-request event.
        """
        self.refresh()
        return False

    def set_color(self, color=None):
        """Set a local color for the widget.

        The local color will override the color that could be returned
        by the container's get_element_color method.
        """
        self.local_color=color
        self.update_widget()
        return True

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        return self.default_size

    def draw(self, context, width, height):
        """Draw the widget.

        Method to be implemented by subclasses
        """
        context.rectangle(0, 0, width, height)
        if self.local_color is not None:
            color=self.local_color
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, self.alpha)
        else:
            rgba=(1.0, 1.0, 1.0, self.alpha)
        context.set_source_rgba(*rgba)
        context.fill()

    def update_widget(self, *p):
        """Update the widget.
        """
        if not self.window:
            return False
        if self.cached_context is None:
            return False

        # First check width
        w=self.needed_size()[0]
        if w != self.cached_surface.get_width():
            self.reset_surface_size(w, self.needed_size()[1])

        bwidth=self.cached_surface.get_width()
        bheight=self.cached_surface.get_height()

        self.draw(self.cached_context, bwidth, bheight)

        self.refresh()
        return False

    def refresh(self):
        """Refresh the widget.
        """
        if self.window and self.cached_surface:
            width = self.cached_surface.get_width()
            height = self.cached_surface.get_height()
            self.window.invalidate_rect(gtk.gdk.Rectangle(0, 0, width, height), False)

    def expose_cb(self, widget, event):
        """Handle the expose event.
        """
        if self.cached_surface is None:
            return False

        context = widget.window.cairo_create()

        # Set a clip region for the expose event
        context.rectangle(event.area.x, event.area.y,
                          event.area.width, event.area.height)
        context.clip()

        # copy the annotation_surface onto this context
        context.set_source_surface(self.cached_surface, 0, 0)
        context.paint_with_alpha(self.expose_alpha)
        #self.draw(context, *widget.window.get_size())
        return False

class AnnotationWidget(GenericColorButtonWidget):
    """ Widget representing an annotation
    """
    def __init__(self, annotation=None, container=None):
        self.annotation=annotation
        self.active=False
        GenericColorButtonWidget.__init__(self, element=annotation, container=container)
        self.connect("key_press_event", self.keypress, self.annotation)
        self.connect("enter_notify_event", lambda b, e: b.grab_focus() and True)
        self.connect("drag_data_get", self.drag_sent)
        self.connect("drag_begin", self._drag_begin)
        self.connect("drag_end", self._drag_end)
        self.connect("drag_motion", self._drag_motion)
        # The widget can generate drags
        self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                             config.data.drag_type['annotation']
                             + config.data.drag_type['uri-list']
                             + config.data.drag_type['text-plain']
                             + config.data.drag_type['TEXT']
                             + config.data.drag_type['STRING']
                             + config.data.drag_type['timestamp']
                             + config.data.drag_type['tag']
                             ,
                             gtk.gdk.ACTION_LINK)
        self.no_image_pixbuf=png_to_pixbuf(self.controller.package.imagecache.not_yet_available_image, width=50)

    def _drag_begin(self, widget, context):
        w=gtk.Window(gtk.WINDOW_POPUP)
        w.set_decorated(False)

        v=gtk.VBox()
        i=gtk.Image()
        v.pack_start(i, expand=False)
        l=gtk.Label()
        v.pack_start(l, expand=False)

        def set_cursor(wid, t):
            cache=self.controller.package.imagecache
            if not t == w._current:
                if isinstance(t, long) or isinstance(t, int):
                    if cache.is_initialized(t, epsilon=500):
                        i.set_from_pixbuf(png_to_pixbuf (cache.get(t, epsilon=500), width=50))
                    elif i.get_pixbuf() != self.no_image_pixbuf:
                        i.set_from_pixbuf(self.no_image_pixbuf)
                    l.set_text(helper.format_time(t)[:30])
                elif isinstance(t, Annotation):
                    # It can be an annotation
                    i.set_from_pixbuf(png_to_pixbuf (cache.get(t.fragment.begin), width=50))
                    l.set_text(self.controller.get_title(t)[:30])
            wid._current=t
            return True

        w.add(v)
        w.show_all()
        w._current=None
        w.set_cursor = set_cursor.__get__(w)
        w.set_cursor(self.element)
        widget._icon=w
        context._popup=w
        context.set_icon_widget(w, 0, 0)
        return True

    def _drag_end(self, widget, context):
        context._popup.destroy()
        return True

    def _drag_motion(self, widget, drag_context, x, y, timestamp):
        w=drag_context.get_source_widget()
        try:
            w._icon.set_cursor(self.element)
        except AttributeError:
            pass
        return True

    def set_active(self, b):
        self.active=b
        self.update_widget()

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        """Handle the drag-sent event.
        """
        if targetType == config.data.target_type['annotation']:
            selection.set(selection.target, 8, widget.annotation.uri.encode('utf8'))
        elif targetType == config.data.target_type['uri-list']:
            c=self.controller.build_context(here=widget.annotation)
            uri=c.evaluateValue('here/absolute_url')
            selection.set(selection.target, 8, uri.encode('utf8'))
        elif (targetType == config.data.target_type['text-plain']
              or targetType == config.data.target_type['TEXT']
              or targetType == config.data.target_type['STRING']):
            selection.set(selection.target, 8, widget.annotation.content.data.encode('utf8'))
        elif targetType == config.data.target_type['timestamp']:
            selection.set(selection.target, 8, str(widget.annotation.fragment.begin))
        else:
            return False
        return True

    def keypress(self, widget, event, annotation):
        """Handle the key-press event.
        """
        if event.keyval == gtk.keysyms.e:
            self.controller.gui.edit_element(annotation)
            return True
        elif event.keyval == gtk.keysyms.h:
            if self.active:
                event="AnnotationDeactivate"
            else:
                event="AnnotationActivate"
            self.active=not self.active
            self.controller.notify(event, annotation=self.annotation)
            return True
        elif event.keyval == gtk.keysyms.F11:
            menu=advene.gui.popup.Menu(annotation, controller=self.controller)
            menu.popup()
            return True
        elif event.keyval == gtk.keysyms.space:
            # Play the annotation
            c=self.controller
            pos = c.create_position (value=annotation.fragment.begin,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.queue_action(c.update_status, status="set", position=pos)
            c.gui.set_current_annotation(annotation)
            return True
        elif event.keyval == gtk.keysyms.Delete and event.state & gtk.gdk.SHIFT_MASK:
            # Delete annotation
            p=annotation.ownerPackage
            p.annotations.remove(annotation)
            self.controller.notify('AnnotationDelete', annotation=annotation)
            return True
        return False

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        return (self.container.unit2pixel(self.annotation.fragment.duration),
                self.container.button_height)

    def draw(self, context, width, height):
        """Draw the widget in the cache pixmap.
        """
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
        try:
            context.rectangle(0, 0, width, height)
        except MemoryError:
            print "MemoryError when rendering rectangle for annotation ", self.annotation.id
            return

        color=None
        if self.active:
            color=active_color
        elif self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotation)

        if color is not None:
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, self.alpha)
        else:
            rgba=(1.0, 1.0, 1.0, self.alpha)
        context.set_source_rgba(*rgba)
        context.fill_preserve()

        # FIXME: if we have other specific renderings for different
        # mimetypes, we will have to implement a plugin system
        if self.annotation.content.mimetype == 'application/x-advene-values':
            # Finalize the rectangle
            context.stroke()
            if width < 1:
                return
            # The annotation contains a list of space-separated values
            # that should be treated as percentage (between 0.0 and
            # 100.0) of the height (FIXME: define a scale somewhere)
            l=[ (1 - v / 100.0) for v in self.annotation.content.parsed() ]
            s=len(l)
            if width < s:
                # There are more samples than available pixels. Downsample the data
                l=l[::(s/width)+1]
                s=len(l)
            w=1.0 * width / s
            c=0
            context.set_source_rgba(0, 0, 0, .5)
            for v in l:
                context.rectangle(int(c), int(height * v), int(w), height)
                context.fill()
                c += w
            return

        # Draw the border
        context.set_source_rgba(0, 0, 0, self.alpha)
        if self.is_focus():
            context.set_line_width(4)
        else:
            context.set_line_width(1)
        context.stroke()

        # Do not draw text if the widget is too small anyway
        if width < 10:
            return

        # Draw the text
        if self.annotation.relations:
            slant=cairo.FONT_SLANT_ITALIC
        else:
            slant=cairo.FONT_SLANT_NORMAL
        context.select_font_face("Helvetica",
                                 slant, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(config.data.preferences['timeline']['font-size'])

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, self.alpha)
        title=unicode(self.controller.get_title(self.annotation))
        try:
            context.show_text(title.encode('utf8'))
        except MemoryError:
            print "MemoryError while rendering title for annotation ", self.annotation.id

class AnnotationTypeWidget(GenericColorButtonWidget):
    """ Widget representing an annotation type
    """
    def __init__(self, annotationtype=None, container=None):
        self.annotationtype=annotationtype
        self.width=None
        # Highlight mark
        self.highlight=False
        # Playing mark (playing restricted to this type)
        self.playing=False
        GenericColorButtonWidget.__init__(self, element=annotationtype, container=container)
        self.connect("key_press_event", self.keypress, self.annotationtype)
        self.connect("enter_notify_event", lambda b, e: b.grab_focus() and True)
        self.connect("drag_begin", self._drag_begin)

    def set_highlight(self, b):
        self.highlight=b
        self.update_widget()

    def set_playing(self, b):
        self.playing=b
        self.update_widget()

    def keypress(self, widget, event, annotationtype):
        """Handle the key-press event.
        """
        if event.keyval == gtk.keysyms.e:
            self.controller.gui.edit_element(annotationtype)
            return True
        return False

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        w=self.width or 60
        return (w, self.container.button_height)

    def draw(self, context, width, height):
        """Draw the widget in the cache pixmap.
        """
        context.rectangle(0, 0, width, height)
        if self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotationtype)
        if color:
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, self.alpha)
        else:
            rgba=(1.0, 1.0, 1.0, self.alpha)
        context.set_source_rgba(*rgba)
        context.fill_preserve()

        # Draw the border
        if self.is_focus():
            context.set_line_width(4)
        else:
            context.set_line_width(1)
        context.set_source_rgba(0, 0, 0, 1)
        context.stroke()

        if self.highlight:
            # Draw a highlight mark
            context.rectangle(0, height - 2, width, height)
            context.fill()
            context.rectangle(0, 0, width, 2)
            context.fill()
            context.stroke()

        if self.playing:
            # Draw a highlight mark
            context.set_source_rgba(0, 0, 0, .5)
            context.set_line_width(1)
            context.move_to(width / 2, 0)
            context.line_to(width / 2 + 10, height / 2)
            context.line_to(width / 2, height)
            context.fill()
            context.stroke()

        # Draw the text
        context.set_source_rgba(0, 0, 0, 1)
        context.select_font_face("Helvetica",
                                 cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(config.data.preferences['timeline']['font-size'])

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, 1)
        title=unicode(self.controller.get_title(self.annotationtype))
        context.show_text(title.encode('utf8'))
        if self.width is None:
            ext=context.text_extents(title)
            if ext[2] != self.width:
                self.width=long(ext[2]) + 5
                self.reset_surface_size(self.width, self.container.button_height)

class TagWidget(GenericColorButtonWidget):
    """ Widget representing a tag
    """
    def __init__(self, tag=None, container=None):
        self.tag=tag
        self.width=60
        GenericColorButtonWidget.__init__(self, element=tag, container=container)
        self.connect("drag_begin", self._drag_begin)
        self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                             config.data.drag_type['tag'],
                             gtk.gdk.ACTION_LINK)
        # The button can generate drags
        self.connect("drag_data_get", self.drag_sent)

        # Allow the entry to get drops of type application/x-color
        self.connect("drag_data_received", self.drag_received)
        self.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                 gtk.DEST_DEFAULT_HIGHLIGHT |
                                 gtk.DEST_DEFAULT_ALL,
                                 config.data.drag_type['color'], gtk.gdk.ACTION_COPY)

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        if targetType == config.data.target_type['tag']:
            selection.set(selection.target, 8, unicode(self.tag).encode('utf8'))
        else:
            self.log("Unknown target type for drag: %d" % targetType)
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop of a color.
        """
        if targetType == config.data.target_type['color']:
            # The structure consists in 4 unsigned shorts: r, g, b, opacity
            (r, g, b, opacity)=struct.unpack('HHHH', selection.data)
            if self.container is not None and hasattr(self.container, 'controller'):
                c=self.container.controller
                c.package._tag_colors[self.tag]="#%04x%04x%04x" % (r, g, b)
                c.notify('TagUpdate', tag=self.tag)
            return True
        return False

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        w=self.width or 50
        return (w, self.container.button_height)

    def draw(self, context, width, height):
        """Draw the widget in the cache pixmap.
        """
        context.rectangle(0, 0, width, height)
        color=self.container.get_element_color(self.tag)
        if color:
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, self.alpha)
        else:
            rgba=(1.0, 1.0, 1.0, self.alpha)
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
                                 cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, 1)
        context.show_text(unicode(self.tag).encode('utf8'))
        ext=context.text_extents(self.tag)
        w=long(ext[2]) + 5
        if self.width != w:
            self.reset_surface_size(self.width, self.container.button_height)
            #print "Resetting width", self.width

class TimestampMarkWidget(GenericColorButtonWidget):
    """ Widget representing an timestamp mark (for note-taking view)
    """
    def __init__(self, container=None):
        GenericColorButtonWidget.__init__(self, container=container)
        self.default_size=(8, self.container.button_height)

    def draw(self, context, width, height):
        """Draw the widget in the cache pixmap.
        """
        context.rectangle(0, 0, width, height)
        if self.local_color is not None:
            color=self.local_color
            rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, self.alpha)
        else:
            rgba=(1.0, 1.0, 1.0, self.alpha)
        context.set_source_rgba(*rgba)
        context.fill()

        # Draw a playing mark
        context.set_source_rgba(0, 0, 0, .5)
        context.set_line_width(1)
        context.move_to(2, 0)
        context.line_to(width - 2, height / 2)
        context.line_to(2, height)
        context.fill()
        context.stroke()

class AnnotationRepresentation(gtk.Button):
    """Representation for an annotation.
    """
    def __init__(self, annotation, controller):
        super(AnnotationRepresentation, self).__init__()
        self.annotation=annotation
        self.controller=controller
        self.add(self.controller.gui.get_illustrated_text(text=self.controller.get_title(annotation),
                                                          position=annotation.fragment.begin,
                                                          vertical=False,
                                                          height=20))
        self.connect("button_press_event", self.button_press_handler, annotation)
        self.connect("drag_data_get", self.drag_sent)
        # The widget can generate drags
        self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                             config.data.drag_type['annotation']
                             + config.data.drag_type['uri-list']
                             + config.data.drag_type['text-plain']
                             + config.data.drag_type['TEXT']
                             + config.data.drag_type['STRING']
                             + config.data.drag_type['timestamp']
                             + config.data.drag_type['tag']
                             ,
                             gtk.gdk.ACTION_LINK)

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        """Handle the drag-sent event.
        """
        if targetType == config.data.target_type['annotation']:
            selection.set(selection.target, 8, widget.annotation.uri.encode('utf8'))
        elif targetType == config.data.target_type['uri-list']:
            c=self.controller.build_context(here=widget.annotation)
            uri=c.evaluateValue('here/absolute_url')
            selection.set(selection.target, 8, uri.encode('utf8'))
        elif (targetType == config.data.target_type['text-plain']
              or targetType == config.data.target_type['TEXT']
              or targetType == config.data.target_type['STRING']):
            selection.set(selection.target, 8, widget.annotation.content.data.encode('utf8'))
        elif targetType == config.data.target_type['timestamp']:
            selection.set(selection.target, 8, str(widget.annotation.fragment.begin))
        else:
            return False
        return True


    def button_press_handler(self, widget, event, annotation):
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            menu=advene.gui.popup.Menu(annotation, controller=self.controller)
            menu.popup()
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.controller.gui.edit_element(annotation)
            return True
        return False

class RelationRepresentation(gtk.Button):
    """Representation for a relation.
    """
    arrow={ 'to': u'\u2192', 'from': u'\u2190' }

    def __init__(self, relation, controller, direction='to'):
        self.relation=relation
        self.controller=controller
        self.direction=direction
        super(RelationRepresentation, self).__init__(u'%s %s %s' % (self.arrow[direction], controller.get_title(relation), self.arrow[direction]))
        self.connect("button_press_event", self.button_press_handler, relation)

    def button_press_handler(self, widget, event, relation):
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            menu=advene.gui.popup.Menu(relation, controller=self.controller)
            menu.popup()
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.controller.gui.edit_element(relation)
            return True
        return False

