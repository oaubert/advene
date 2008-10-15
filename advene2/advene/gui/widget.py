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
"""Reusable widgets.

Note that, contrary to a common pattern found in the Advene sources
(where the real widget is stored as the self.widget attribute), each
of the widgets defined in this module is a gtk.Widget.

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
import pango
import gobject

# Advene part
import advene.core.config as config
from advene.core.imagecache import ImageCache

from advene.gui.util import png_to_pixbuf
from advene.gui.util import encode_drop_parameters
import advene.util.helper as helper
from advene.model.cam.annotation import Annotation

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

        self.connect('expose-event', self.expose_cb)
        self.connect('realize', self.realize_cb)
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
        widget._icon=pixmap
        def set_cursor(wid, t=None):
            try:
                self.container.set_annotation(t)
            except AttributeError:
                # The container does not implement the set_annotation method.
                return False
            return True
        pixmap.set_cursor = set_cursor.__get__(w)
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
gobject.type_register(GenericColorButtonWidget)

class AnnotationWidget(GenericColorButtonWidget):
    """ Widget representing an annotation
    """
    def __init__(self, annotation=None, container=None):
        self.annotation=annotation
        self.active=False
        GenericColorButtonWidget.__init__(self, element=annotation, container=container)
        self.connect('key-press-event', self.keypress, self.annotation)
        self.connect('enter-notify-event', lambda b, e: b.grab_focus() and True)
        self.connect('drag-data-get', self.drag_sent)
        self.connect('drag-begin', self._drag_begin)
        self.connect('drag-end', self._drag_end)
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
                             gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE )
        self.no_image_pixbuf=None

    def _drag_begin(self, widget, context):
        try:
            widgets=self.container.get_selected_annotation_widgets()
            if not widget in widgets:
                widgets=[]
        except AttributeError:
            widgets=[]

        w=gtk.Window(gtk.WINDOW_POPUP)
        w.set_decorated(False)

        style=w.get_style().copy()
        black=gtk.gdk.color_parse('black')
        white=gtk.gdk.color_parse('white')

        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            style.bg[state]=black
            style.fg[state]=white
            style.text[state]=white
            #style.base[state]=white
        w.set_style(style)

        v=gtk.VBox()
        v.set_style(style)
        h=gtk.HBox()
        h.set_style(style)
        begin=gtk.Image()
        h.pack_start(begin, expand=False)
        padding=gtk.HBox()
        # Padding
        h.pack_start(padding, expand=True)
        end=gtk.Image()
        h.pack_start(end, expand=False)
        v.pack_start(h, expand=False)
        l=gtk.Label()
        l.set_ellipsize(pango.ELLIPSIZE_END)
        l.set_style(style)
        v.pack_start(l, expand=False)

        def set_cursor(wid, t=None):
            if t is None:
                t=self.annotation
            cache=self.controller.package.imagecache
            if self.no_image_pixbuf is None:
                self.no_image_pixbuf=png_to_pixbuf(ImageCache.not_yet_available_image, width=config.data.preferences['drag-snapshot-width'])
            if not t == w._current:
                if isinstance(t, long) or isinstance(t, int):
                    if cache.is_initialized(t, epsilon=config.data.preferences['bookmark-snapshot-precision']):
                        begin.set_from_pixbuf(png_to_pixbuf (cache.get(t, epsilon=config.data.preferences['bookmark-snapshot-precision']), width=config.data.preferences['drag-snapshot-width']))
                    elif begin.get_pixbuf() != self.no_image_pixbuf:
                        begin.set_from_pixbuf(self.no_image_pixbuf)
                    end.hide()
                    padding.hide()
                    l.set_text(helper.format_time(t))
                elif isinstance(t, Annotation):
                    # It can be an annotation
                    begin.set_from_pixbuf(png_to_pixbuf (cache.get(t.begin), width=config.data.preferences['drag-snapshot-width']))
                    end.set_from_pixbuf(png_to_pixbuf (cache.get(t.end), width=config.data.preferences['drag-snapshot-width']))
                    end.show()
                    padding.show()
                    if widgets:
                        l.set_text(_("Set of %s annotations") % len(widgets))
                    else:
                        l.set_text(self.controller.get_title(t))
            wid._current=t
            return True

        w.add(v)
        w.show_all()
        w._current=None
        w.set_cursor = set_cursor.__get__(w)
        w.set_cursor()
        w.set_size_request(long(2.5 * config.data.preferences['drag-snapshot-width']), -1)
        widget._icon=w
        context.set_icon_widget(w, 0, 0)
        return True

    def _drag_end(self, widget, context):
        widget._icon.destroy()
        widget._icon=None
        return True

    def set_active(self, b):
        self.active=b
        self.update_widget()

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        """Handle the drag-sent event.
        """
        try:
            widgets=self.container.get_selected_annotation_widgets()
            if not widget in widgets:
                widgets=None
        except AttributeError:
            widgets=None
        if not widgets:
            widgets=[ widget ]

        if targetType == config.data.target_type['annotation']:
            selection.set(selection.target, 8, "\n".join( w.annotation.uriref for w in widgets ).encode('utf8'))
        elif targetType == config.data.target_type['uri-list']:
            l=(self.controller.build_context(here=w.annotation).evaluate('here/absolute_url')
               for w in widgets)
            selection.set(selection.target, 8, "\n".join(l).encode('utf8'))
        elif (targetType == config.data.target_type['text-plain']
              or targetType == config.data.target_type['TEXT']
              or targetType == config.data.target_type['STRING']):
            selection.set(selection.target, 8, "\n".join(w.annotation.content.data.encode('utf8') for w in widgets))
        elif targetType == config.data.target_type['timestamp']:
            l=(encode_drop_parameters(timestamp=w.annotation.fragment.begin,
                                      comment=self.controller.get_title(w.annotation)) for w in widgets)
            selection.set(selection.target, 8, "\n".join(l))
        else:
            return False
        return True

    def keypress(self, widget, event, annotation):
        """Handle the key-press event.
        """
        if event.keyval == gtk.keysyms.e:
            try:
                widgets=self.container.get_selected_annotation_widgets()
                if not widget in widgets:
                    widgets=None
            except AttributeError:
                widgets=None
            if not widgets:
                self.controller.gui.edit_element(annotation)
            else:
                for w in widgets:
                    self.controller.gui.edit_element(w.annotation)
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
            pos = c.create_position (value=annotation.begin,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.queue_action(c.update_status, status="set", position=pos)
            c.gui.set_current_annotation(annotation)
            return True
        elif event.keyval == gtk.keysyms.Delete and event.state & gtk.gdk.SHIFT_MASK:
            # Delete annotation or selection
            try:
                widgets=self.container.get_selected_annotation_widgets()
                if not widget in widgets:
                    widgets=None
            except AttributeError:
                widgets=None
            if not widgets:
                self.controller.delete_element(annotation)
            else:
                batch_id=object()
                for w in widgets:
                    self.controller.delete_element(w.annotation, batch_id=batch_id)
            return True
        return False

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        return (self.container.unit2pixel(self.annotation.duration),
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
            #l=[ (1 - v / 100.0) for v in self.annotation.content.parsed ]
            l=[ (1 - int(v) / 100.0) for v in self.annotation.content.data.split() ]
            s=len(l)
            if width < s:
                # There are more samples than available pixels. Downsample the data
                l=l[::(s/width)+1]
                s=len(l)
            w=1.0 * width / s
            c=w
            context.set_source_rgba(0, 0, 0, .5)
            context.move_to(0, height)
            context.line_to(0, int(height * v))
            for v in l:
                context.line_to(int(c), int(height * v))
                c += w
            context.line_to(int(c), height)
            context.fill()
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
        # FIXME
        #if self.annotation.relations:
        #    slant=cairo.FONT_SLANT_ITALIC
        #else:
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
gobject.type_register(AnnotationWidget)

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
        self.connect('key-press-event', self.keypress, self.annotationtype)
        self.connect('enter-notify-event', lambda b, e: b.grab_focus() and True)
        self.connect('drag-begin', self._drag_begin)

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
gobject.type_register(AnnotationTypeWidget)

class TagWidget(GenericColorButtonWidget):
    """ Widget representing a tag
    """
    def __init__(self, tag=None, container=None):
        self.tag=tag
        self.width=60
        GenericColorButtonWidget.__init__(self, element=tag, container=container)
        self.connect('drag-begin', self._drag_begin)
        self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                             config.data.drag_type['tag'],
                             gtk.gdk.ACTION_LINK)
        # The button can generate drags
        self.connect('drag-data-get', self.drag_sent)

        # Allow the entry to get drops of type application/x-color
        self.connect('drag-data-received', self.drag_received)
        self.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                 gtk.DEST_DEFAULT_HIGHLIGHT |
                                 gtk.DEST_DEFAULT_ALL,
                                 config.data.drag_type['color'], gtk.gdk.ACTION_COPY)

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        if targetType == config.data.target_type['tag']:
            # FIXME: tag.uriref ?
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
                self.tag.color="string:#%04x%04x%04x" % (r, g, b)
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
        title=unicode(self.tag.title).encode('utf8')
        context.show_text(title)
        ext=context.text_extents(title)
        w=long(ext[2]) + 5
        if self.width != w:
            self.reset_surface_size(self.width, self.container.button_height)
            #print "Resetting width", self.width
gobject.type_register(TagWidget)

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
gobject.type_register(TimestampMarkWidget)

class AnnotationRepresentation(gtk.Button):
    """Representation for an annotation.
    """
    def __init__(self, annotation, controller):
        super(AnnotationRepresentation, self).__init__()
        self.annotation=annotation
        self.controller=controller
        self.add(self.controller.gui.get_illustrated_text(text=self.controller.get_title(annotation),
                                                          position=annotation.begin,
                                                          vertical=False,
                                                          height=20))
        self.connect('button-press-event', self.button_press_handler, annotation)
        self.connect('drag-data-get', self.drag_sent)
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
            selection.set(selection.target, 8, widget.annotation.uriref.encode('utf8'))
        elif targetType == config.data.target_type['uri-list']:
            selection.set(selection.target, 8, self.controller.build_context(here=widget.annotation).evaluate('here/absolute_url').encode('utf8'))
        elif (targetType == config.data.target_type['text-plain']
              or targetType == config.data.target_type['TEXT']
              or targetType == config.data.target_type['STRING']):
            selection.set(selection.target, 8, widget.annotation.content.data.encode('utf8'))
        elif targetType == config.data.target_type['timestamp']:
            selection.set(selection.target, 
                          8, 
                          encode_drop_parameters(timestamp=widget.annotation.fragment.begin,
                                                 comment=self.controller.get_title(widget.annotation)))
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
gobject.type_register(AnnotationRepresentation)

class RelationRepresentation(gtk.Button):
    """Representation for a relation.
    """
    if config.data.os == 'win32':
        arrow={ 'to': u'->', 'from': u'<-' }
    else:
        arrow={ 'to': u'\u2192', 'from': u'\u2190' }

    def __init__(self, relation, controller, direction='to'):
        self.relation=relation
        self.controller=controller
        self.direction=direction
        super(RelationRepresentation, self).__init__(u'%s %s %s' % (self.arrow[direction], controller.get_title(relation), self.arrow[direction]))
        self.connect('button-press-event', self.button_press_handler, relation)

    def button_press_handler(self, widget, event, relation):
        if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
            menu=advene.gui.popup.Menu(relation, controller=self.controller)
            menu.popup()
            return True
        elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.controller.gui.edit_element(relation)
            return True
        return False
gobject.type_register(RelationRepresentation)

class TimestampRepresentation(gtk.Button):
    """Representation of a timestamp.

    It is a button with a representative image and the timestamp displayed under it.

    @ivar image: the image widget
    @type image: gtk.Image
    @ivar label: the label (timestamp) widget
    @type label: gtk.Label
    """
    def __init__(self, value, controller, width=None, epsilon=None, comment_getter=None, visible_label=True):
        """Instanciate a new TimestampRepresentation.
        
        @param value: the timestamp value
        @type value: int
        @param controller: the controller
        @type controller: advene.core.Controller
        @param width: the snapshot width
        @type width: int
        @param epsilon: the precision (for snapshot display)
        @type epsilon: int (ms)
        @param comment_getter: method returning the associated comment
        @type comment_getter: method
        @param visible_label: should the timestamp label be displayed?
        @type visible_label: boolean
        """
        super(TimestampRepresentation, self).__init__()
        self._value=value
        self.controller=controller
        self.width=width or config.data.preferences['bookmark-snapshot-width']
        if epsilon is None:
            epsilon=config.data.preferences['bookmark-snapshot-precision']
        self.epsilon=epsilon
        self.visible_label=visible_label
        # comment_getter is a method which returns the comment
        # associated to this timestamp
        self.comment_getter=comment_getter
        # extend_popup_menu is a method which takes the menu and the
        # element as parameter, and adds appropriate menu items.
        self.extend_popup_menu=None
        self.highlight=False

        style=self.get_style().copy()
        black=gtk.gdk.color_parse('black')
        white=gtk.gdk.color_parse('white')

        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            style.bg[state]=black
            style.base[state]=black
            style.fg[state]=white
            style.text[state]=white
            #style.base[state]=white
        self.set_style(style)

        box=gtk.VBox()
        box.set_style(style)
        self.image=gtk.Image()
        self.image.set_style(style)
        self.label=gtk.Label()
        self.label.set_style(style)
        box.pack_start(self.image, expand=False)
        box.pack_start(self.label, expand=False)
        if not self.visible_label:
            self.label.set_no_show_all(True)
            self.label.hide()
        self.add(box)
        self.box=box

        self.refresh()

        self.connect('button-press-event', self._button_press_handler)
        self.connect('drag-data-get', self._drag_sent)
        # The widget can generate drags
        self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                             config.data.drag_type['timestamp']
                             + config.data.drag_type['text-plain']
                             + config.data.drag_type['TEXT']
                             + config.data.drag_type['STRING']
                             ,
                             gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)

        # Define drag cursor
        def _drag_begin(widget, context):
            w=gtk.Window(gtk.WINDOW_POPUP)
            w.set_decorated(False)
            w.set_style(style)

            v=gtk.VBox()
            v.set_style(style)
            i=gtk.Image()
            v.pack_start(i, expand=False)
            l=gtk.Label()
            l.set_style(style)
            l.set_ellipsize(pango.ELLIPSIZE_END)
            v.pack_start(l, expand=False)

            if self.value is None:
                val=-1
            else:
                val=self.value
            i.set_from_pixbuf(png_to_pixbuf (self.controller.package.imagecache.get(val, epsilon=self.epsilon), width=config.data.preferences['drag-snapshot-width']))
            l.set_markup('<small>%s</small>' % helper.format_time(self.value))

            w.add(v)
            w.show_all()
            w.set_default_size(3 * config.data.preferences['drag-snapshot-width'], -1)
            widget._icon=w
            context.set_icon_widget(w, 0, 0)
            return True

        def _drag_end(widget, context):
            widget._icon.destroy()
            widget._icon=None
            return True
        self.connect('drag-begin', _drag_begin)
        self.connect('drag-end', _drag_end)

        def enter_bookmark(widget, event):
            self.controller.notify('BookmarkHighlight', timestamp=self.value, immediate=True)
            self.highlight=True
            return False
        def leave_bookmark(widget, event):
            self.controller.notify('BookmarkUnhighlight', timestamp=self.value, immediate=True)
            self.highlight=False
            return False
        self.connect('enter-notify-event', enter_bookmark)
        self.connect('leave-notify-event', leave_bookmark)

    def get_value(self):
        return self._value
    def set_value(self, v):
        if self.highlight:
            self.controller.notify('BookmarkUnhighlight', timestamp=self._value, immediate=True)
            self.highlight=False
        self._value=v
        self.refresh()
    value=property(get_value, set_value, doc="Timestamp value")

    def _drag_sent(self, widget, context, selection, targetType, eventTime):
        """Handle the drag-sent event.
        """
        if (targetType == config.data.target_type['text-plain']
              or targetType == config.data.target_type['TEXT']
              or targetType == config.data.target_type['STRING']):
            selection.set(selection.target, 8, helper.format_time(self._value).encode('utf-8'))
        elif targetType == config.data.target_type['timestamp']:
            if self.comment_getter is not None:
                    selection.set(selection.target, 8, encode_drop_parameters(timestamp=self._value,
                                                                              comment=self.comment_getter()))
            else:
                    selection.set(selection.target, 8, encode_drop_parameters(timestamp=self._value))
        else:
            return False
        return True

    def goto_and_refresh(self, *p):
        """Goto the timestamp, and refresh the image if necessary and possible.
        """
        if self._value is None:
            return True
        cache=self.controller.package.imagecache
        # We have to check for is_initialized before doing the
        # update_status, since the snapshot may be updated by the update_status
        do_refresh=not cache.is_initialized(self._value, epsilon=self.epsilon)
        self.controller.update_status("start", self._value)
        if do_refresh:
            # The image was invalidated (or not initialized). Use
            # a timer to update it after some time.
            def refresh_timeout():
                if cache.is_initialized(self._value, epsilon=self.epsilon):
                    # The image was updated. Refresh the display.
                    self.refresh()
                return False
            gobject.timeout_add (100, refresh_timeout)
        return True

    def _button_press_handler(self, widget, event):
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS and self._value is not None:
            self.goto_and_refresh()
            return True
        elif event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS and self.popup_menu is not None:
            self.popup_menu()
            return True
        return False

    def refresh(self):
        """Update the display of the widget according to self._value and self.width
        """
        if self._value is None:
            v=-1
        else:
            v=self._value
        if self.width < 9:
            self.image.hide()
            self.set_size_request(6, 12)
        else:
            ic=self.controller.gui.imagecache
            if ic is None:
                png=ImageCache.not_yet_available_image
            else:
                png=ic.get(v, epsilon=self.epsilon)
            self.image.set_from_pixbuf(png_to_pixbuf(png, width=self.width))
            self.set_size_request(-1, -1)
            self.image.show()
        ts=helper.format_time(self._value)
        self.label.set_markup('<small>%s</small>' % ts)
        if self.visible_label and self.label.get_child_requisition()[0] <= 1.2 * self.image.get_child_requisition()[0]:
            self.label.show()
        else:
            self.label.hide()
        self.controller.gui.tooltips.set_tip(self, ts)
        return True

    def as_html(self, with_timestamp=True):
        """Return a HTML representation of the widget.
        """
        data={ 'image_url': 'http:/media/snapshot/advene/%d' % self._value,
               'player_url': 'http:/media/play/%d' % self._value,
               'timestamp': helper.format_time(self._value) 
               }
        ret="""<a href="%(player_url)s"><img width="120" border="0" src="%(image_url)s" alt="" /></a>""" % data
        if with_timestamp:
            ret = ''.join( (ret, """<br /><em><a href="%(player_url)s">%(timestamp)s</a></em>""" % data) )
        return ret
                          
    def set_width(self, w):
        """Set the width of the snapshot and refresh the display.
        """
        self.width=w
        self.refresh()

    def invalidate_snapshot(self, *p):
        """Invalidate the snapshot image.
        """
        self.controller.package.imagecache.invalidate(self.value, self.epsilon)
        self.refresh()
        return True

    def popup_menu(self, popup=True):
        """Display the popup menu.

        If self.extend_popup_menu is defined, it must be a method
        which will be called with the menu and the element as
        parameters, in order to extend the popup menu with contextual
        items.

        @param popup: should the menu be immediately displayed as a popup menu
        @type popup: boolean
        """
        p=self.controller.player

        menu = gtk.Menu()
        item = gtk.MenuItem(_("Invalidate snapshot"))
        item.connect('activate', self.invalidate_snapshot)
        menu.append(item)

        item = gtk.MenuItem(_("Use the current player position"))
        item.connect('activate', lambda i: self.set_value(p.current_position_value))
        if p.status != p.PauseStatus and p.status != p.PlayingStatus:
            item.set_sensitive(False)
        menu.append(item)

        if self.extend_popup_menu is not None:
            self.extend_popup_menu(menu, self)
        menu.show_all()
        
        if popup:
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return menu
    
    def set_color(self, color):
        # FIXME: does not work ATM
        self.modify_bg(gtk.STATE_NORMAL, color)
        self.modify_base(gtk.STATE_NORMAL, color)

gobject.type_register(TimestampRepresentation)
