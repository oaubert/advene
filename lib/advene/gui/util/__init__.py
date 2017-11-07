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
"""GUI helper methods.
"""
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from gi.repository import GObject

import urllib.parse
import urllib.request, urllib.parse, urllib.error
import io

import advene.core.config as config
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.query import Query
import advene.util.helper as helper

# Predefined MIMEtype for annotation contents
predefined_content_mimetypes=[
    ('text/plain', _("Plain text content")),
    ('text/html', _("HTML content")),
    ('application/x-advene-structured', _("Simple-structured content")),
    ('application/x-advene-values', _("List of numeric values")),
    ('image/svg+xml', _("SVG graphics content")),
    ]

if not hasattr(Gtk.Menu, 'popup_at_pointer'):
    # Monkey patch Gtk.Menu (popup_at_pointer is available only in Gtk >= 3.22)
    def popup_at_pointer(widget, event):
        widget.popup(None, None, None, None, 0, Gtk.get_current_event_time())
    Gtk.Menu.popup_at_pointer = popup_at_pointer

def image_new_from_pixbuf(pb, width=None):
    i=Gtk.Image()
    if width:
        height = int(width * pb.get_height() / pb.get_width())
        p=pb.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    else:
        p=pb
    i.set_from_pixbuf(p)
    return i

def png_to_pixbuf (png_data, width=None, height=None):
    """Load PNG data into a pixbuf
    """
    loader = GdkPixbuf.PixbufLoader.new_with_type('png')
    if not isinstance(png_data, bytes):
        png_data=bytes(png_data)
    try:
        loader.write(png_data)
        pixbuf = loader.get_pixbuf ()
        loader.close ()
    except GObject.GError:
        # The PNG data was invalid.
        pixbuf=GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))

    if width and not height:
        height = int(width * pixbuf.get_height() / pixbuf.get_width())
    if height and not width:
        width = int(height * pixbuf.get_width() / pixbuf.get_height())
    if width and height:
        p=pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        return p
    else:
        return pixbuf

def image_from_position(controller, position=None, media=None, width=None, height=None, precision=None):
    i=Gtk.Image()
    if position is None:
        position = controller.player.current_position_value
    pb = png_to_pixbuf(controller.get_snapshot(position=position, media=media, precision=precision), width=width, height=height)
    i.set_from_pixbuf(pb)
    return i

def overlay_svg_as_pixbuf(png_data, svg_data, width=None, height=None):

    """Overlay svg graphics over a png image.

    @return: a PNG image
    """
    if not '<svg' in svg_data:
        # Generate pseudo-svg with data
        svg_data="""<svg:svg xmlns:svg="http://www.w3.org/2000/svg" width="320pt" height="200pt" version='1' preserveAspectRatio="xMinYMin meet" viewBox='0 0 320 200'>
  <svg:text x='10' y='190' fill="white" font-size="24" stroke="black" font-family="sans-serif">%s</svg:text>
</svg:svg>
""" % svg_data

    try:
        loader = GdkPixbuf.PixbufLoader.new_with_type('svg')
    except:
        logger.error("Unable to load the SVG pixbuf loader", exc_info=True)
        loader=None
    if loader is not None:
        try:
            loader.write(svg_data.encode('utf-8'))
            loader.close ()
            p = loader.get_pixbuf ()
            w = p.get_width()
            h = p.get_height()
            pixbuf=png_to_pixbuf (png_data).scale_simple(w, h, GdkPixbuf.InterpType.BILINEAR)
            p.composite(pixbuf, 0, 0, w, h, 0, 0, 1.0, 1.0, GdkPixbuf.InterpType.BILINEAR, 255)
        except GObject.GError:
            # The PNG data was invalid.
            logger.error("Invalid image data", exc_info=True)
            pixbuf=GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))
    else:
        pixbuf=GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))

    if width and not height:
        height = 1.0 * width * pixbuf.get_height() / pixbuf.get_width()
    if height and not width:
        width = 1.0 * height * pixbuf.get_width() / pixbuf.get_height()
    if width and height:
        p=pixbuf.scale_simple(int(width), int(height), GdkPixbuf.InterpType.BILINEAR)
        return p
    return pixbuf

def overlay_svg_as_png(png_data, svg_data):
    pixbuf=overlay_svg_as_pixbuf(png_data, svg_data)
    s=io.StringIO()
    def pixbuf_save_func(buf):
        s.write(buf)
        return True
    pixbuf.save_to_callback(pixbuf_save_func, "png", {"tEXt::key":"Overlayed SVG"})
    return s.getvalue()

def get_small_stock_button(sid, callback=None, *p):
    b=Gtk.Button()
    b.add(Gtk.Image.new_from_stock(sid, Gtk.IconSize.SMALL_TOOLBAR))
    if callback:
        b.connect('clicked', callback, *p)
    return b

def get_pixmap_button(pixmap, callback=None, *p):
    b=Gtk.Button()
    i=Gtk.Image()
    i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
    b.add(i)
    i.show()
    if callback:
        b.connect('clicked', callback, *p)
    return b

def get_pixmap_toolbutton(pixmap, callback=None, *p):
    if pixmap.startswith('gtk-'):
        # Stock-id
        b=Gtk.ToolButton(pixmap)
    else:
        i=Gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
        b=Gtk.ToolButton(icon_widget=i)
        i.show()
    if callback:
        b.connect('clicked', callback, *p)
    return b

color_cache={}

def name2color(color):
    """Return the gtk color for the given color name or code.
    """
    if isinstance(color, Gdk.Color):
        gtk_color = color
    elif color:
        # Found a color. Cache it.
        try:
            gtk_color=color_cache[color]
        except KeyError:
            try:
                color_cache[color]=Gdk.color_parse(color)
            except (TypeError, ValueError):
                logger.error("Unable to parse color %s", color)
                color_cache[color]=None
            gtk_color=color_cache[color]
    else:
        gtk_color=None
    return gtk_color

def encode_drop_parameters(**kw):
    """Encode the given parameters as drop parameters.

    @return: a string
    """
    for k in kw:
        if not isinstance(kw[k], str):
            kw[k]=str(kw[k])
    return urllib.parse.urlencode(kw).encode('utf8')

def decode_drop_parameters(data):
    """Decode the drop parameters.

    @return: a dict.
    """
    if isinstance(data, bytes):
        data = data.decode('utf-8')
    return dict( (k, v)
                 for (k, v) in urllib.parse.parse_qsl(data) )

def get_target_types(el):
    """Return DND target types for element.
    """
    targets = []
    if isinstance(el, Annotation):
        targets.extend(config.data.get_target_types('annotation', 'timestamp', 'tag'))
    elif isinstance(el, Relation):
        targets.extend(config.data.get_target_types('relation'))
    elif isinstance(el, View):
        if helper.get_view_type(el) == 'adhoc':
            targets.extend(config.data.get_target_types('adhoc-view'))
        else:
            targets.extend(config.data.get_target_types('view'))
    elif isinstance(el, AnnotationType):
        targets.extend(config.data.get_target_types('annotation-type'))
    elif isinstance(el, RelationType):
        targets.extend(config.data.get_target_types('relation-type'))
    elif isinstance(el, Query):
        targets.extend(config.data.get_target_types('query'))
    elif isinstance(el, Schema):
        targets.extend(config.data.get_target_types('schema'))
    elif isinstance(el, int):
        targets.extend(config.data.get_target_types('timestamp'))
    # FIXME: Resource

    targets.extend(config.data.get_target_types('uri-list',
                                                'text-plain',
                                                'TEXT',
                                                'STRING'))
    return targets

def drag_data_get_cb(widget, context, selection, targetType, timestamp, controller):
    """Generic drag-data-get handler.

    It is used by the origin widget of a drag action, when the
    destination widget queries for the DND data.

    Usage information:
    this method must be connected passing the controller as user data:
      widget.connect('drag-data-get', drag_data_get_cb, controller)

    and the context must have a _element attribute (defined in a
    'drag-begin' handler for instance).
    """
    typ=config.data.target_type
    el = context._element
    # FIXME: think about the generalisation of the notion of container
    # selection (for timestamp lists for instance)
    widgets = None
    try:
        c = widget.container
    except  (AttributeError, RuntimeError):
        # No container. Note that getattr(widget, 'container', None)
        # would anyway raise a RuntimeError (container is some kind of
        # reserved in gtk).
        c = None
    if c:
        try:
            widgets = c.get_selected_annotation_widgets()
            if not widget in widgets:
                widgets = None
        except AttributeError:
            logger.error("Cannot get_selected_annotation_widgets", exc_info=True)

    d={ typ['annotation']: Annotation,
        typ['annotation-type']: AnnotationType,
        typ['relation']: Relation,
        typ['relation-type']: RelationType,
        typ['view']: View,
        typ['query']: Query,
        typ['schema']: Schema }
    if targetType in d:
        # Directly pass URIs for Annotation, types and views
        if not isinstance(el, d[targetType]):
            return False
        if widgets:
            selection.set(selection.get_target(), 8, "\n".join( w.annotation.uri for w in widgets ).encode('utf8'))
        else:
            selection.set(selection.get_target(), 8, el.uri.encode('utf8'))
        return True
    elif targetType == typ['adhoc-view']:
        if helper.get_view_type(el) != 'adhoc':
            return False
        selection.set(selection.get_target(), 8, encode_drop_parameters(id=el.id))
        return True
    elif targetType == typ['uri-list']:

        if widgets:
            selection.set(selection.get_target(), 8, "\n".join( controller.build_context(here=w.annotation).evaluateValue('here/absolute_url') for w in widgets ).encode('utf8'))
        else:
            try:
                uri=controller.build_context(here=el).evaluateValue('here/absolute_url')
            except:
                uri="No URI for " + str(el)
            selection.set(selection.get_target(), 8, uri.encode('utf8'))
    elif targetType == typ['timestamp']:
        if isinstance(el, int):
            selection.set(selection.get_target(), 8, encode_drop_parameters(timestamp=el))
        elif isinstance(el, Annotation):
            selection.set(selection.get_target(), 8, encode_drop_parameters(timestamp=el.fragment.begin,
                                                                      comment=controller.get_title(el)))
        else:
            logger.error("Inconsistent DND target %s", targetType)
        return True
    elif targetType in (typ['text-plain'], typ['STRING']):
        selection.set(selection.get_target(), 8, controller.get_title(el).encode('utf8'))
    else:
        logger.warn("Unknown target type for drag: %d" % targetType)
    return True

def contextual_drag_begin(widget, context, element, controller):
    if callable(element):
        element=element()
    context._element=element

    if hasattr(widget, '_drag_begin'):
        if widget._drag_begin(widget, context):
            return False

    w=Gtk.Window(Gtk.WindowType.POPUP)
    w.set_decorated(False)
    w.get_style_context().add_class('advene_drag_icon')

    v=Gtk.VBox()
    v.get_style_context().add_class('advene_drag_icon')

    def get_coloured_label(t, color=None):
        l=Gtk.Label()
        #l.set_ellipsize(Pango.EllipsizeMode.END)
        if color is None:
            color='white'
        l.set_markup("""<span background="%s" foreground="black">%s</span>""" % (color, t.replace('<', '&lt;')))
        return l

    if isinstance(element, int):
        begin = image_new_from_pixbuf(png_to_pixbuf(controller.get_snapshot(position=element, precision=config.data.preferences['bookmark-snapshot-precision']), width=config.data.preferences['drag-snapshot-width']))
        begin.get_style_context().add_class('advene_drag_icon')

        l=Gtk.Label()
        l.set_text(helper.format_time(element))
        l.get_style_context().add_class('advene_drag_icon')

        v.pack_start(begin, False, True, 0)
        v.pack_start(l, False, True, 0)
        w.set_size_request(int(1.5 * config.data.preferences['drag-snapshot-width']), -1)
    elif isinstance(element, Annotation):
        # Pictures HBox
        h=Gtk.HBox()
        h.get_style_context().add_class('advene_drag_icon')
        begin = image_new_from_pixbuf(png_to_pixbuf(controller.get_snapshot(annotation=element), width=config.data.preferences['drag-snapshot-width']))
        begin.get_style_context().add_class('advene_drag_icon')
        h.pack_start(begin, False, True, 0)
        # Padding
        h.pack_start(Gtk.HBox(), True, True, 0)
        end = image_new_from_pixbuf(png_to_pixbuf(controller.get_snapshot(annotation=element, position=element.fragment.end), width=config.data.preferences['drag-snapshot-width']))
        end.get_style_context().add_class('advene_drag_icon')
        h.pack_start(end, False, True, 0)
        v.pack_start(h, False, True, 0)

        l=get_coloured_label(controller.get_title(element), controller.get_element_color(element))
        l.get_style_context().add_class('advene_drag_icon')
        v.pack_start(l, False, True, 0)
        w.get_style_context().add_class('advene_drag_icon')
        w.set_size_request(int(2.5 * config.data.preferences['drag-snapshot-width']), -1)
    elif isinstance(element, AnnotationType):
        l=get_coloured_label(_("Annotation Type %(title)s:\n%(count)s") % {
                'title': controller.get_title(element),
                'count': helper.format_element_name('annotation', len(element.annotations)),
                }, controller.get_element_color(element))
        v.pack_start(l, False, True, 0)
    elif isinstance(element, RelationType):
        l=get_coloured_label(_("Relation Type %(title)s:\n%(count)s") % {
                'title': controller.get_title(element),
                'count': helper.format_element_name('relation', len(element.relations)),
                }, controller.get_element_color(element))
        v.pack_start(l, False, True, 0)
    else:
        l=get_coloured_label("%s %s" % (helper.get_type(element),
                                        controller.get_title(element)),
                             controller.get_element_color(element))
        v.pack_start(l, False, True, 0)

    w.add(v)
    w.show_all()
    widget._icon=w
    Gtk.drag_set_icon_widget(context, w, 0, 0)
    return True

def contextual_drag_end(widget, context):
    if hasattr(widget, '_icon') and widget._icon:
        widget._icon.destroy()
        widget._icon=None
    return True

def enable_drag_source(widget, element, controller):
    """Initialize support for DND from widget.

    element can be either an Advene object instance, or a method which
    returns such an instance. This allows to use this generic method
    with dynamic widgets (which can hold reference to multiple
    elements), such as treeviews or reusable components.
    """
    if callable(element):
        el=element()
    else:
        el=element
    # Generic support
    widget.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                           get_target_types(el),
                           Gdk.DragAction.LINK | Gdk.DragAction.COPY | Gdk.DragAction.MOVE )
    widget.connect('drag-begin', contextual_drag_begin, element, controller)
    widget.connect('drag-end', contextual_drag_end)
    widget.connect('drag-data-get', drag_data_get_cb, controller)

def gdk2intrgba(color, alpha=0xff):
    """Convert a Gdk.Color to int RGBA.
    """
    return ( (color.red >> 8) << 24) \
         | ( (color.green >> 8) << 16) \
         | ( (color.blue >> 8) <<  8) \
         | alpha

def gdk2intrgb(color):
    """Convert a Gdk.Color to int RGB.
    """
    return ( (color.red >> 8) << 16) \
         | ( (color.green >> 8) << 8) \
         | (color.blue >> 8)

def get_clipboard():
    return Gtk.Clipboard.get(Gdk.Atom.intern("CLIPBOARD", True))
