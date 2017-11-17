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
"""Reusable widgets.

Note that, contrary to a common pattern found in the Advene sources
(where the real widget is stored as the self.widget attribute), each
of the widgets defined in this module is a Gtk.Widget.

Updated tutorial for gtk3:
http://zetcode.com/gfx/pycairo/basicdrawing/
"""
import logging
logger = logging.getLogger(__name__)

import struct
import os

from gettext import gettext as _

import gi
import cairo
from gi.repository import GObject
from gi.repository import GdkPixbuf
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

try:
    gi.require_version('Rsvg', '2.0')
    from gi.repository import Rsvg
except ImportError:
    import advene.util.ctypesrsvg as Rsvg

# Advene part
import advene.core.config as config

from advene.gui.util import png_to_pixbuf, enable_drag_source, name2color
import advene.util.helper as helper
from advene.model.annotation import Annotation
import advene.gui.popup

active_color=name2color('#fdfd4b')

class GenericColorButtonWidget(Gtk.DrawingArea):
    """ Widget emulating a color button widget
    """
    def __init__(self, element=None, container=None):
        GObject.GObject.__init__(self)
        self.set_can_focus(True)
        self.element=element

        # If not None, it should contain a Gdk.Color
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
        self.set_events(Gdk.EventMask.POINTER_MOTION_MASK |
                        Gdk.EventMask.POINTER_MOTION_HINT_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK |
                        Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.BUTTON1_MOTION_MASK |
                        Gdk.EventMask.KEY_PRESS_MASK |
                        Gdk.EventMask.KEY_RELEASE_MASK |
                        Gdk.EventMask.FOCUS_CHANGE_MASK |
                        Gdk.EventMask.ENTER_NOTIFY_MASK |
                        Gdk.EventMask.LEAVE_NOTIFY_MASK |
                        Gdk.EventMask.SCROLL_MASK)

        self.connect('draw', self.draw_cb)
        self.connect('realize', self.realize_cb)
        self.connect_after('size-allocate', self.size_request_cb)
        self.connect('focus-in-event', self.update_widget)
        self.connect('focus-out-event', self.update_widget)

        #self.connect('event', self.debug_cb, "Event")
        #self.connect_after('event', self.debug_cb, "After")

        self.default_size = (40, 10)
        # Initialize the size
        self.set_size_request(*self.needed_size())

    def _drag_begin(self, widget, context):
        # see https://developer.gnome.org/gtk3/stable/ch26s02.html
        w,h = self.needed_size()
        pixbuf = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, w, h)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, pixbuf.get_width(),
                                     pixbuf.get_height())
        cr = cairo.Context(surface)
        self.draw(cr, w, h)
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()
        # FIXME3: use drag_source_set_icon_pixbuf
        widget.drag_source_set_icon_pixbuf(pixbuf)
        def set_cursor(wid, t=None, precision=None):
            try:
                self.container.set_annotation(t)
            except AttributeError:
                # The container does not implement the set_annotation method.
                return False
            return True
        pixbuf.set_cursor = set_cursor.__get__(w)
        return True

    def reset_surface_size(self, width=None, height=None):
        """Redimension the widget content.
        """
        w = self.get_window()
        if not w:
            return False
        if width is None:
            width = w.get_width()
        if height is None:
            height = w.get_height()
        if width <= 0:
            logger.warn("Error: width %d <= 0 for %s", width, self.element.id)
            width=5
        self.set_size_request(width, height)
        #self.get_window().lower()
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
        if not self.get_window():
            return False
        self.refresh()
        return False

    def refresh(self):
        """Refresh the widget.
        """
        self.reset_surface_size(*self.needed_size())
        self.queue_draw()

    def draw_cb(self, widget, context):
        """Handle the draw event.
        """
        context.paint_with_alpha(self.expose_alpha)
        self.draw(context, widget.get_window().get_width(), widget.get_window().get_height())
        return False
GObject.type_register(GenericColorButtonWidget)

class AnnotationWidget(GenericColorButtonWidget):
    """ Widget representing an annotation
    """
    def __init__(self, annotation=None, container=None):
        self.annotation=annotation
        self.active=False
        self._fraction_marker=None
        GenericColorButtonWidget.__init__(self, element=annotation, container=container)
        self.connect('key-press-event', self.keypress, self.annotation)
        self.connect('enter-notify-event', lambda b, e: b.grab_focus() and True)
        # The widget can generate drags
        enable_drag_source(self, annotation, container.controller)
        self.no_image_pixbuf=None

    def set_fraction_marker(self, f):
        self._fraction_marker = f
        self.update_widget()
    def get_fraction_marker(self):
        return self._fraction_marker
    fraction_marker = property(get_fraction_marker, set_fraction_marker)

    def _drag_begin(self, widget, context):
        # set_icon_widget is broken ATM in recent gtk on win32.
        if config.data.os == 'win32':
            return GenericColorButtonWidget._drag_begin(self, widget, context)

        try:
            widgets=self.container.get_selected_annotation_widgets()
            if not widget in widgets:
                widgets=[]
        except (AttributeError, RuntimeError):
            widgets=[]

        w=Gtk.Window(Gtk.WindowType.POPUP)
        w.set_decorated(False)
        # Set white on black background
        w.get_style_context().add_class('advene_drag_icon')

        v=Gtk.VBox()
        v.get_style_context().add_class('advene_drag_icon')
        h=Gtk.HBox()
        h.get_style_context().add_class('advene_drag_icon')
        begin=Gtk.Image()
        h.pack_start(begin, False, True, 0)
        padding=Gtk.HBox()
        # Padding
        h.pack_start(padding, True, True, 0)
        end=Gtk.Image()
        h.pack_start(end, False, True, 0)
        v.pack_start(h, False, True, 0)
        l=Gtk.Label()
        l.set_ellipsize(Pango.EllipsizeMode.END)
        l.get_style_context().add_class('advene_drag_icon')
        v.pack_start(l, False, True, 0)

        def set_cursor(wid, t=None, precision=None):
            if t is None:
                t = self.annotation
            if precision is None:
                precision = config.data.preferences['bookmark-snapshot-precision']
            if self.no_image_pixbuf is None:
                self.no_image_pixbuf = png_to_pixbuf(self.controller.get_snapshot(position=-1), width=config.data.preferences['drag-snapshot-width'])
            if not t == w._current:
                if isinstance(t, int):
                    snap = self.controller.get_snapshot(position=t, annotation=self.annotation, precision=precision)
                    if snap.is_default:
                        pixbuf = self.no_image_pixbuf
                    else:
                        pixbuf = png_to_pixbuf(snap, width=config.data.preferences['drag-snapshot-width'])
                    begin.set_from_pixbuf(pixbuf)
                    end.hide()
                    padding.hide()
                    l.set_text(helper.format_time(t))
                elif isinstance(t, Annotation):
                    # It can be an annotation
                    begin.set_from_pixbuf(png_to_pixbuf(self.controller.get_snapshot(annotation=t),
                                                        width=config.data.preferences['drag-snapshot-width']))
                    end.set_from_pixbuf(png_to_pixbuf(self.controller.get_snapshot(annotation=t, position=t.fragment.end),
                                                      width=config.data.preferences['drag-snapshot-width']))
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
        w.set_size_request(int(2.5 * config.data.preferences['drag-snapshot-width']), -1)
        widget._icon=w
        Gtk.drag_set_icon_widget(context, w, 0, 0)
        return True

    def set_active(self, b):
        self.active=b
        self.update_widget()

    def keypress(self, widget, event, annotation):
        """Handle the key-press event.
        """
        if event.keyval == Gdk.KEY_e:
            try:
                widgets=self.container.get_selected_annotation_widgets()
                if not widget in widgets:
                    widgets=None
            except (AttributeError, RuntimeError):
                widgets=None
            if not widgets:
                self.controller.gui.edit_element(annotation)
            else:
                for w in widgets:
                    self.controller.gui.edit_element(w.annotation)
            return True
        elif event.keyval == Gdk.KEY_h:
            if self.active:
                event="AnnotationDeactivate"
            else:
                event="AnnotationActivate"
            self.active=not self.active
            self.controller.notify(event, annotation=self.annotation)
            return True
        elif event.keyval == Gdk.KEY_F11:
            menu=advene.gui.popup.Menu(annotation, controller=self.controller)
            menu.popup()
            return True
        elif event.keyval == Gdk.KEY_space:
            # Play the annotation
            c=self.controller
            c.queue_action(c.update_status, status="seek", position=annotation.fragment.begin)
            c.gui.set_current_annotation(annotation)
            return True
        elif event.keyval == Gdk.KEY_Delete or event.keyval == Gdk.KEY_BackSpace:
            # Delete annotation or selection
            try:
                widgets=self.container.get_selected_annotation_widgets()
                if not widget in widgets:
                    widgets=None
            except (AttributeError, RuntimeError):
                widgets=None
            if not widgets:
                self.controller.delete_element(annotation)
            else:
                batch_id=object()
                for w in widgets:
                    self.controller.delete_element(w.annotation, batch=batch_id)
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
        try:
            context.rectangle(0, 0, width, height)
        except MemoryError:
            logger.error("MemoryError when rendering rectangle for annotation %s", self.annotation.id)
            return

        color=None
        if self.active:
            color=active_color
        elif self.local_color is not None:
            color=self.local_color
        else:
            color=self.container.get_element_color(self.annotation)

        # color should be a Gdk.Color
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
            if not s:
                return
            if width < s:
                # There are more samples than available pixels. Downsample the data
                l=l[::int(s/width)+1]
                s=len(l)
            w=1.0 * width / s
            c = 0
            context.set_source_rgba(0, 0, 0, .5)
            context.move_to(0, height)
            for v in l:
                context.line_to(int(c), int(height * v))
                c += w
                context.line_to(int(c), int(height * v))
            context.line_to(int(c), height)
            context.fill()
            return
        elif self.annotation.content.mimetype == 'image/svg+xml' and Rsvg is not None:
            if width < 6:
                return
            if self.annotation.content.data:
                try:
                    s = Rsvg.Handle.new_from_data(self.annotation.content.data.encode('utf-8'))
                    # Resize to fit widget height
                    scale = 1.0 * height / s.get_dimensions().height
                    context.transform(cairo.Matrix(scale, 0, 0, scale, 0, 0))
                    s.render_cairo(context)
                except Exception:
                    logger.error("Error when rendering SVG timeline component for %s", self.annotation.id, exc_info=True)
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
        context.select_font_face("sans-serif",
                                 slant, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(config.data.preferences['timeline']['font-size'])

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, self.alpha)
        title=str(self.controller.get_title(self.annotation))
        try:
            context.show_text(title)
        except MemoryError:
            logger.error("MemoryError while rendering title for annotation %s", self.annotation.id, exc_info=True)

        if self._fraction_marker is not None:
            x=int(self._fraction_marker * width)
            context.set_source_rgba(0.9, 0, 0, 0.9)
            context.set_line_width(2)
            context.move_to(x, 0)
            context.line_to(x, height)
            context.stroke()

GObject.type_register(AnnotationWidget)

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

    def set_highlight(self, b):
        self.highlight=b
        self.update_widget()

    def set_playing(self, b):
        self.playing=b
        self.update_widget()

    def keypress(self, widget, event, annotationtype):
        """Handle the key-press event.
        """
        if event.keyval == Gdk.KEY_e:
            self.controller.gui.edit_element(annotationtype)
            return True
        return False

    def needed_size(self):
        """Return the needed size of the widget.

        Method to be implemented by subclasses
        """
        w=self.width or 120
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
            context.move_to(int(width / 2), 0)
            context.line_to(int(width / 2) + 10, int(height / 2))
            context.line_to(int(width / 2), height)
            context.fill()
            context.stroke()

        # Draw the text
        context.set_source_rgba(0, 0, 0, 1)
        context.select_font_face("sans-serif",
                                 cairo.FONT_SLANT_ITALIC, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(config.data.preferences['timeline']['font-size'])

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, 1)
        title=str(self.controller.get_title(self.annotationtype))
        context.show_text(title)
        if self.width is None:
            ext=context.text_extents(title)
            if ext[2] != self.width:
                self.width=int(ext[2]) + 5
                self.reset_surface_size(self.width, self.container.button_height)
GObject.type_register(AnnotationTypeWidget)

class TagWidget(GenericColorButtonWidget):
    """ Widget representing a tag
    """
    def __init__(self, tag=None, container=None):
        self.tag=tag
        self.width=60
        GenericColorButtonWidget.__init__(self, element=tag, container=container)
        self.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                             config.data.get_target_types('tag'),
                             Gdk.DragAction.LINK)
        # The button can generate drags
        self.connect('drag-data-get', self.drag_sent)

        # Allow the entry to get drops of type application/x-color
        self.connect('drag-data-received', self.drag_received)
        self.drag_dest_set(Gtk.DestDefaults.MOTION |
                           Gtk.DestDefaults.HIGHLIGHT |
                           Gtk.DestDefaults.ALL,
                           config.data.get_target_types('color'),
                           Gdk.DragAction.COPY)

    def drag_sent(self, widget, context, selection, targetType, eventTime):
        if targetType == config.data.target_type['tag']:
            selection.set(selection.get_target(), 8, self.tag.encode('utf-8'))
        else:
            logger.warn("Unknown target type for drag: %d" % targetType)
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop of a color.
        """
        if targetType == config.data.target_type['color']:
            # The structure consists in 4 unsigned shorts: r, g, b, opacity
            (r, g, b, opacity)=struct.unpack('HHHH', selection.get_data())
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
        context.select_font_face("sans-serif",
                                 cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)

        context.move_to(2, int(height * 0.7))

        context.set_source_rgba(0, 0, 0, 1)
        context.show_text(str(self.tag))
        ext=context.text_extents(self.tag)
        w=int(ext[2]) + 5
        if self.width != w:
            self.reset_surface_size(self.width, self.container.button_height)
            logger.debug("Resetting width %d", self.width)
GObject.type_register(TagWidget)

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
        context.line_to(width - 2, int(height / 2))
        context.line_to(2, height)
        context.fill()
        context.stroke()
GObject.type_register(TimestampMarkWidget)

class AnnotationRepresentation(Gtk.Button):
    """Representation for an annotation.
    """
    def __init__(self, annotation, controller):
        super(AnnotationRepresentation, self).__init__()
        self.annotation=annotation
        self.controller=controller
        self.add(self.controller.gui.get_illustrated_text(text=self.controller.get_title(annotation),
                                                          position=annotation.fragment.begin,
                                                          vertical=False,
                                                          height=20,
                                                          color=controller.get_element_color(annotation)))
        self.connect('button-press-event', self.button_press_handler, annotation)
        enable_drag_source(self, self.annotation, self.controller)

    def button_press_handler(self, widget, event, annotation):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            menu=advene.gui.popup.Menu(annotation, controller=self.controller)
            menu.popup()
            return True
        elif event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.controller.gui.edit_element(annotation)
            return True
        return False
GObject.type_register(AnnotationRepresentation)

class RelationRepresentation(Gtk.Button):
    """Representation for a relation.
    """
    if config.data.os == 'linux':
        arrow={ 'to': helper.chars.arrow_to, 'from': helper.chars.arrow_from }
    else:
        arrow={ 'to': '->', 'from': '<-' }

    def __init__(self, relation, controller, direction='to'):
        self.relation=relation
        self.controller=controller
        self.direction=direction
        super(RelationRepresentation, self).__init__()
        l=Gtk.Label()
        self.add(l)
        l.show()
        self.refresh()
        self.connect('button-press-event', self.button_press_handler, relation)
        enable_drag_source(self, self.relation, self.controller)

    def refresh(self):
        l=self.get_children()[0]
        t='%s %s %s' % (self.arrow[self.direction],
                         self.controller.get_title(self.relation),
                         self.arrow[self.direction])
        color=self.controller.get_element_color(self.relation)
        if color:
            l.set_markup('<span background="%s">%s</span>' % (color, t.replace('<', '&lt;')))
        else:
            l.set_text(t)

    def button_press_handler(self, widget, event, relation):
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            menu=advene.gui.popup.Menu(relation, controller=self.controller)
            menu.popup()
            return True
        elif event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.controller.gui.edit_element(relation)
            return True
        return False
GObject.type_register(RelationRepresentation)

class TimestampRepresentation(Gtk.Button):
    """Representation of a timestamp.

    It is a button with a representative image and the timestamp displayed under it.

    @ivar image: the image widget
    @type image: Gtk.Image
    @ivar label: the label (timestamp) widget
    @type label: Gtk.Label
    """
    def __init__(self, value, media, controller, width=None, precision=None, comment_getter=None, visible_label=True, callback=None):
        """Instanciate a new TimestampRepresentation.

        @param value: the timestamp value
        @type value: int
        @param controller: the controller
        @type controller: advene.core.Controller
        @param width: the snapshot width
        @type width: int
        @param precision: the precision (for snapshot display)
        @type precision: int (ms)
        @param comment_getter: method returning the associated comment
        @type comment_getter: method
        @param visible_label: should the timestamp label be displayed?
        @type visible_label: boolean
        @value callback: a callback that will be called before value modification
        @type callback: method. If it returns False, then the modification will be cancelled
        """
        super(TimestampRepresentation, self).__init__()
        self._value = value
        self._rounded_value = controller.round_timestamp(value)
        if media is None:
            media = controller.package.media
        self._media = media
        self.controller=controller
        self._width=width or config.data.preferences['bookmark-snapshot-width']
        if precision is None:
            precision=config.data.preferences['bookmark-snapshot-precision']
        self.precision=precision
        self.visible_label=visible_label
        # comment_getter is a method which returns the comment
        # associated to this timestamp
        self.comment_getter=comment_getter
        # extend_popup_menu is a method which takes the menu and the
        # element as parameter, and adds appropriate menu items.
        self.extend_popup_menu=None
        self.highlight=False
        # Displayed text.
        self._text = '%(timestamp)s'
        self.callback = callback

        box=Gtk.VBox()
        self.image=Gtk.Image()
        self.valid_screenshot = False
        self.label=Gtk.Label()
        box.pack_start(self.image, False, True, 0)
        box.pack_start(self.label, False, True, 0)
        if not self.visible_label:
            self.label.set_no_show_all(True)
            self.label.hide()
        self.add(box)
        self.box=box

        self.refresh()

        self.connect('button-press-event', self._button_press_handler)

        enable_drag_source(self, self.get_value, self.controller)

        def enter_bookmark(widget, event):
            self.controller.notify('BookmarkHighlight', timestamp=self.value, media=self._media, immediate=True)
            self.highlight=True
            return False
        def leave_bookmark(widget, event):
            self.controller.notify('BookmarkUnhighlight', timestamp=self.value, media=self._media, immediate=True)
            self.highlight=False
            return False
        self.connect('enter-notify-event', enter_bookmark)
        self.connect('leave-notify-event', leave_bookmark)

        self._rules=[]
        # React to SnapshotUpdate events
        self._rules.append(self.controller.event_handler.internal_rule (event='SnapshotUpdate',
                                                                        method=self.snapshot_update_cb))
        self.connect('destroy', self.remove_rules)

    def add_class(self, cl):
        for w in (self, self.box, self.image):
            w.get_style_context().add_class(cl)

    def remove_class(self, cl):
        for w in (self, self.box, self.image):
            w.get_style_context().remove_class(cl)

    def set_width(self, w):
        self._width = w
        self.refresh()
    def get_width(self):
        return self._width
    width = property(get_width, set_width)

    def set_text(self, s):
        self._text = s
        self.refresh()
    def get_text(self):
        return self._text
    text = property(get_text, set_text)

    def snapshot_update_cb(self, context, target):
        if (context.globals['media'] == self._media
            and abs(context.globals['position'] - self._rounded_value) <= self.precision):
            # Update the representation
            self.refresh()
        return True
    def remove_rules(self, *p):
        for r in self._rules:
            self.controller.event_handler.remove_rule(r, 'internal')
        return False

    def get_value(self):
        return self._value
    def set_value(self, v):
        if v == self._value:
            return
        if self.callback is not None and v != self._value:
            if self.callback(v) is False:
                # If self.callback explicitly returns False (not
                # None), then cancel the value setting.
                return False
        if self.highlight:
            self.controller.notify('BookmarkUnhighlight', timestamp=self._value, media=self._media, immediate=True)
            self.highlight=False
        self._value = v
        self._rounded_value = self.controller.round_timestamp(v)
        self.refresh()
    value=property(get_value, set_value, doc="Timestamp value")

    def goto_and_refresh(self, *p):
        """Goto the timestamp, and refresh the image if necessary and possible.
        """
        if self._value is None:
            return True
        self.controller.update_status("seek", self._value)
        if not self.valid_screenshot:
            # The image is not (yet) available. Use a timer to update
            # it after some time.
            def refresh_timeout():
                # The image was maybe updated. Refresh the display.
                self.refresh()
                return False
            GObject.timeout_add (300, refresh_timeout)
        return True

    def _button_press_handler(self, widget, event):
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS and self._value is not None:
            self.goto_and_refresh()
            return True
        elif event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS and self.popup_menu is not None:
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
            png = self.controller.get_snapshot(v, media=self._media, precision=self.precision)
            self.valid_screenshot = not png.is_default
            self.image.set_from_pixbuf(png_to_pixbuf(bytes(png), width=self.width))
            self.set_size_request(-1, -1)
            self.image.show()
        ts=helper.format_time(self._value)
        self.label.set_markup(self._text % { 'timestamp': ts })
        self.label.get_style_context().add_class("timestamp_label")
        if self.visible_label and self.label.get_child_requisition().width <= 1.2 * self.image.get_child_requisition().width:
            self.label.show()
        else:
            self.label.hide()
        self.set_tooltip_text(ts)
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

    def refresh_snapshot(self, *p):
        """Refresh the snapshot image.
        """
        # Ask for refresh
        self.controller.update_snapshot(self.value, media=self._media, force=True)
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

        menu = Gtk.Menu()

        def goto(it, t):
            c=self.controller
            c.update_status(status="seek", position=t)
            return True

        def save_as(it):
            self.controller.gui.save_snapshot_as(self.value)
            return True

        item = Gtk.MenuItem(_("Play"))
        item.connect('activate', goto, self.value)
        menu.append(item)

        item = Gtk.MenuItem(_("Refresh snapshot"))
        item.connect('activate', self.refresh_snapshot)
        menu.append(item)

        item = Gtk.MenuItem(_("Save as..."))
        item.connect('activate', save_as)
        menu.append(item)

        if self.callback is not None:
            item = Gtk.MenuItem(_("Use current player position"))
            item.connect('activate', lambda i: self.set_value(p.current_position_value))
            if p.is_playing():
                item.set_sensitive(False)
            menu.append(item)

            item = Gtk.MenuItem(_("Adjust timestamp"))
            item.connect('activate', lambda i: self.set_value(self.controller.gui.adjust_timestamp(self.get_value())))
            menu.append(item)

        if self.extend_popup_menu is not None:
            self.extend_popup_menu(menu, self)

        menu.show_all()

        if popup:
            menu.popup_at_pointer(None)
        return menu

    def set_color(self, color):
        self.bgcolor = color

GObject.type_register(TimestampRepresentation)
