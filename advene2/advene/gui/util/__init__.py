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

import advene.core.config as config
from advene.core.imagecache import ImageCache

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
    ic=controller.gui.imagecache
    if ic is None:
        png=ImageCache.not_yet_available_image
    else:
        png=ic[position]
    i.set_from_pixbuf(png_to_pixbuf(png, width=width, height=height))
    return i

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
