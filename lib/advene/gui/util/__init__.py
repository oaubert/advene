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
"""GUI helper methods.
"""

from gettext import gettext as _

import gtk
import gobject
import cgi
import StringIO

import advene.core.config as config
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.query import Query

def png_to_pixbuf (png_data, width=None, height=None):
    """Load PNG data into a pixbuf
    """
    loader = gtk.gdk.PixbufLoader ('png')
    if not isinstance(png_data, str):
        png_data=str(png_data)
    try:
        loader.write (png_data, len (png_data))
        pixbuf = loader.get_pixbuf ()
        loader.close ()
    except gobject.GError:
        # The PNG data was invalid.
        pixbuf=gtk.gdk.pixbuf_new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))

    if width and not height:
        height = width * pixbuf.get_height() / pixbuf.get_width()
    if height and not width:
        width = height * pixbuf.get_width() / pixbuf.get_height()
    if width and height:
        p=pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        return p
    else:
        return pixbuf

def image_from_position(controller, position=None, width=None, height=None):
    i=gtk.Image()
    if position is None:
        position=controller.player.current_position_value
    pb=png_to_pixbuf (controller.package.imagecache[position],
                                         width=width, height=height)
    i.set_from_pixbuf(pb)
    return i

def overlay_svg(png_data, svg_data):
    """Overlay svg graphics over a png image.
    
    @return: a PNG image
    """
    try:
        loader = gtk.gdk.PixbufLoader('svg')
    except Exception, e:
        print "Unable to load the SVG pixbuf loader: ", str(e)
        loader=None
    if loader is not None:
        try:
            loader.write (svg_data)
            loader.close ()
            p = loader.get_pixbuf ()
            width = p.get_width()
            height = p.get_height()
            pixbuf=png_to_pixbuf (png_data).scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
            p.composite(pixbuf, 0, 0, width, height, 0, 0, 1.0, 1.0, gtk.gdk.INTERP_BILINEAR, 255)
        except gobject.GError, e:
            # The PNG data was invalid.
            print "Invalid image data", e
            pixbuf=gtk.gdk.pixbuf_new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))
    else:
        pixbuf=gtk.gdk.pixbuf_new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))
    
    s=StringIO.StringIO()
    def pixbuf_save_func(buf):
        s.write(buf)
        return True
    pixbuf.save_to_callback(pixbuf_save_func, "png", {"tEXt::key":"Overlayed SVG"})

    return s.getvalue()

def get_small_stock_button(sid, callback=None, *p):
    b=gtk.Button()
    b.add(gtk.image_new_from_stock(sid, gtk.ICON_SIZE_SMALL_TOOLBAR))
    if callback:
        b.connect('clicked', callback, *p)
    return b

def get_pixmap_button(pixmap, callback=None, *p):
    b=gtk.Button()
    i=gtk.Image()
    i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
    b.add(i)
    i.show()
    if callback:
        b.connect('clicked', callback, *p)
    return b

def get_pixmap_toolbutton(pixmap, callback=None, *p):
    if pixmap.startswith('gtk-'):
        # Stock-id
        b=gtk.ToolButton(pixmap)
    else:
        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
        b=gtk.ToolButton(icon_widget=i)
        i.show()
    if callback:
        b.connect('clicked', callback, *p)
    return b

color_cache={}

def name2color(color):
    """Return the gtk color for the given color name or code.
    """
    if color:
        # Found a color. Cache it.
        try:
            gtk_color=color_cache[color]
        except KeyError:
            try:
                color_cache[color]=gtk.gdk.color_parse(color)
            except (TypeError, ValueError):
                print "Unable to parse ", color
                color_cache[color]=None
            gtk_color=color_cache[color]
    else:
        gtk_color=None
    return gtk_color

arrow_up_xpm="""13 16 2 1
       c None
.      c #FF0000
      .      
     ...     
    .....    
   .......   
  .........  
 ........... 
.............
     ...     
     ...     
     ...     
     ...     
     ...     
     ...     
     ...     
     ...     
     ...     
""".splitlines()

arrow_right_xpm="""16 13 2 1
. c None
# c #ff0000
................
..........#.....
..........##....
..........###...
..........####..
###############.
################
###############.
..........####..
..........###...
..........##....
..........#.....
................""".splitlines()


def shaped_window_from_xpm(xpm):
    # Code adapted from evolution/widgets/table/e-table-header-item.c
    pixbuf = gtk.gdk.pixbuf_new_from_xpm_data(xpm)
    pixmap, bitmap = pixbuf.render_pixmap_and_mask()

    gtk.widget_push_colormap(gtk.gdk.rgb_get_colormap())
    win = gtk.Window(gtk.WINDOW_POPUP)
    pix = gtk.Image()
    pix.set_from_pixmap(pixmap, bitmap)
    win.realize()
    win.add(pix)
    win.shape_combine_mask(bitmap, 0, 0)
    gtk.widget_pop_colormap()
    return win

def encode_drop_parameters(**kw):
    """Encode the given parameters as drop parameters.
    
    @return: a string
    """
    for k in kw:
        if isinstance(kw[k], unicode):
            kw[k]=kw[k].encode('utf8')
        if not isinstance(kw[k], basestring):
            kw[k]=str(kw[k])
    return cgi.urllib.urlencode(kw).encode('utf8')

def decode_drop_parameters(data):
    """Decode the drop parameters.

    @return: a dict.
    """
    return dict( (k, unicode(v, 'utf8')) 
                 for (k, v) in cgi.parse_qsl(unicode(data, 'utf8').encode('utf8')) )

def get_target_types(el):
    """Return DND target types for element.
    """
    if isinstance(el, Annotation):
        targets= (config.data.drag_type['annotation'] 
                  + config.data.drag_type['timestamp'] 
                  + config.data.drag_type['tag'])
    elif isinstance(el, View):
        if helper.get_view_type(el) == 'adhoc':
            targets=config.data.drag_type['adhoc-view'] 
        else:
            targets=config.data.drag_type['view']
    elif isinstance(el, AnnotationType):
        targets=config.data.drag_type['annotation-type']
    elif isinstance(el, RelationType):
        targets=config.data.drag_type['annotation-type']
    elif isinstance(el, Query):
        targets=config.data.drag_type['query']
    elif isinstance(el, Schema):
        targets=config.data.drag_type['schema']
    # FIXME: Resource
    else:
        targets=[]
    targets.extend(config.data.drag_type['uri-list']
                   + config.data.drag_type['text-plain']
                   + config.data.drag_type['TEXT']
                   + config.data.drag_type['STRING'])
    return targets

def drag_data_get_cb(widget, context, selection, targetType, timestamp, controller):
    """Generic drag-data-get handler.

    Usage information:
    this method must be connected passing the controller as user data:
      widget.connect('drag-data-get', drag_data_get_cb, controller)
     
    and the context must has a _element attribute (defined in a
    'drag-begin' handler for instance).
    """
    typ=config.data.target_type
    el = context._element

    d={ typ['annotation']: Annotation,
        typ['annotation-type']: AnnotationType,
        typ['relation-type']: AnnotationType,
        typ['view']: View,
        typ['query']: Query,
        typ['schema']: Schema }
    if targetType in d:
        # Directly pass URIs for Annotation, types and views
        if not isinstance(el, d[targetType]):
            return False
        selection.set(selection.target, 8, el.uri.encode('utf8'))
        return True
    elif targetType == typ['adhoc-view']:
        if helper.get_view_type(el) != 'adhoc':
            return False
        selection.set(selection.target, 8, encode_drop_parameters(id=el.id))
        return True
    elif targetType == typ['uri-list']:
        try:
            ctx=controller.build_context(here=el)
            uri=ctx.evaluateValue('here/absolute_url')
        except:
            uri="No URI for " + unicode(el)
        selection.set(selection.target, 8, uri.encode('utf8'))
    elif targetType in (typ['text-plain'], typ['STRING']):
        selection.set(selection.target, 8, controller.get_title(el).encode('utf8'))
    else:
        print "Unknown target type for drag: %d" % targetType
    return True

