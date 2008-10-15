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
"""Simple Shape editor widget
==========================

  This component provides a simple framework allowing to edit basic
  shapes, and generate the corresponding XML.

  This component should not have dependencies on Advene, so that it
  can be reused in other projects.

FIXME: when parsing SVG, allow a relative option to scale absolute values wrt. SVG-specified canvas size/current canvas size
FIXME: XML load/dump should try to preserve unhandled information (especially TAL instructions)
FIXME: find a way to pass search paths for xlink:href elements resolution
FIXME: find a way to pass the background path
"""

import os
import gtk
import cairo
import urllib

try:
    import advene.util.ElementTree as ET
except ImportError:
    try:
        import elementtree.ElementTree as ET
    except ImportError:
        import xml.etree.ElementTree as ET # python 2.5

from gettext import gettext as _

COLORS = [ 'red', 'green', 'blue', 'black', 'white', 'gray', 'yellow' ]
SVGNS = 'http://www.w3.org/2000/svg'

defined_shape_classes=[]

class Shape(object):
    """The generic Shape class.

    @ivar name: the shape instance name
    @type name: string
    @ivar color: the shape color
    @type color: string
    @ivar linewidth: the line width
    @type linewidth: int
    @ivar filled: should the shape be filled ?
    @type filled: boolean
    @ivar tolerance: pixel tolerance for control point selection
    @type tolerance: int
    @ivar link: URL associated to the shape
    @type link: string or None
    @ivar link_label: label for the URL associated to the shape
    @type link_label: string or None
    @cvar SHAPENAME: the name of the shape class
    @type SHAPENAME: translated string
    """

    SHAPENAME=_("Generic shape")
    # Tag used for the generation/parsing of SVG representation
    SVGTAG=''

    def __init__(self, name=SHAPENAME, color="green"):
        self.name=name
        self.color=color
        self.linewidth=2
        self.filled = False
        # Pixel tolerance for control point selection
        self.tolerance = 6
        self.link=None
        self.link_label=None
        self.set_bounds( ( (0, 0), (10, 10) ) )
        # Extra SVG attributes to preserve (esp. tal: instructions)
        self.svg_attrib={}

    def set_bounds(self, bounds):
        """Set the bounds of the shape.

        The bounds are the coordinates of the rectangular selection
        used to define the shape.

        @param bounds: a tuple of 2 int couples
        @type bounds: tuple
        """
        pass

    def get_bounds(self):
        """Return the bounds of the shape.

        @return: a tuple of 2 int couples
        @rtype: tuple
        """
        return ( (0, 0), (10, 10) )

    def render(self, pixmap, invert=False):
        """Render the shape on the given pixmap.

        @param pixmap: the destination pixmap
        @type pixmap: gtk.gdk.Pixmap
        @param invert: should the rendering inverse the selection ?
        @type invert: boolean
        """
        return

    def translate(self, vector):
        """Translate the shape.

        @param vector: the translation vector
        @type vector: a couple of int
        """
        pass

    def control_point(self, point):
        """Test if the given point is a control point.

        If on a control point, return its coordinates (x, y) and those of the
        other bound, else None

        @param point: the tested point
        @type point: a couple of int
        @return: None, or a couple of coordinates
        @rtype: tuple
        """
        return None

    def __contains__(self, point):
        """Test if the given point is inside the shape.

        @param point: the tested point
        @type point: a couple of int
        @rtype: boolean
        """
        return False

    def parse_svg(cls, element, context):
        """Parse a SVG representation.

        The context object must implement a 'dimensions' method that
        will return a (width, height) tuple corresponding to the
        canvas size.

        @param element: etree.Element to parse
        @param context: the svg context
        @return: an appropriate shape, or None if the class could not parse the element
        """
        if element.tag != cls.SVGTAG and element.tag != ET.QName(SVGNS, cls.SVGTAG):
            return None
        s=cls(name=element.attrib.get('name', cls.SHAPENAME))
        s.filled=( element.attrib.get('fill', 'none') != 'none' )
        s.color=element.attrib['stroke']
        style=element.attrib['style']
        if style.startswith('stroke-width:'):
            s.linewidth=int(style.replace('stroke-width:', ''))
        c=cls.xml2coords(cls.coords, element.attrib, context.dimensions())
        for n, v in c.iteritems():
            setattr(s, n, v)
        s.svg_attrib=dict(element.attrib)
        if hasattr(s, 'post_parse'):
            s.post_parse()
        return s
    parse_svg=classmethod(parse_svg)

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the shape.

        @param relative: should dimensions be relative to the container size or absolute?
        @type relative: boolean
        @param size: the container size in pixels
        @type size: a couple of int
        @return: the SVG representation
        @rtype: elementtree.Element
        """
        attrib=dict(self.svg_attrib)
        attrib.update(self.coords2xml(relative, size))
        if self.filled:
            attrib['fill']=self.color
        else:
            attrib['fill']='none'
        attrib['stroke']=self.color
        attrib['style']="stroke-width:%d" % self.linewidth
        attrib['name']=self.name
        e=ET.Element(ET.QName(SVGNS, self.SVGTAG), attrib=attrib)
        if self.link:
            a=ET.Element('a', attrib={ 'xlink:href': self.link,
                                       'title': self.link_label or _("Link to %s") % self.link })
            a.append(e)
            return a
        else:
            return e

    def copy_from(self, shape, style=False):
        """Copy data from another shape.

        @param shape: the original shape
        @param style: should the style be copied also?
        @type style: boolean
        """
        return

    def clone(self, style=False):
        """Clone the shape.

        @param style: should the style be copied also?
        @type style: boolean
        @return: a new shape
        """
        s=self.__class__()
        s.copy_from(self, style)
        return s

    def xml2coords(coords, attrib, dimensions):
        """Converts coordinates in XML format to their appropriate value

        @param coords: a list of (name, dimension_index) tuple
        @param attrib: an attributes dictionary
        @param dimensions: a (width, height) tuple
        @return: a dictionary with values converted
        """
        res={}
        # Convert numeric attributes (possibly percentage) to float
        for n, dimindex in coords:
            v=attrib[n]
            if v.endswith('%'):
                # Convert it to absolute values
                v=float(v[:-1]) / 100 * dimensions[dimindex]
            else:
                v=float(v)
            res[n]=int(v)
        return res
    xml2coords=staticmethod(xml2coords)

    def coords2xml(self, relative, dimensions):
        """Converts coordinates to XML format

        @param relative: convert to relative dimensions
        @param dimensions: a (width, height) tuple
        @return: a dictionary with values converted
        """
        res={}
        if relative:
            for n, dimindex in self.coords:
                res[n]="%.03f%%" % (getattr(self, n) * 100.0 / dimensions[dimindex])
        else:
            res=dict( [ ( n, str(getattr(self, n)) ) for n, d in self.coords ] )
        return res

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox=gtk.VBox()

        def label_widget(label, widget):
            hb=gtk.HBox()
            hb.add(gtk.Label(label))
            hb.pack_start(widget, expand=False)
            return hb

        # Name
        namesel = gtk.Entry()
        namesel.set_text(self.name)
        vbox.pack_start(label_widget(_("Name"), namesel), expand=False)

        # Link
        linksel = gtk.Entry()
        linksel.set_text(self.link or '')
        vbox.pack_start(label_widget(_("Link"), linksel), expand=False)

        # Linklabel
        linklabelsel = gtk.Entry()
        linklabelsel.set_text(self.link_label or '')
        vbox.pack_start(label_widget(_("Link label"), linklabelsel), expand=False)

        # Color
        colorsel = gtk.combo_box_new_text()
        for s in COLORS:
            colorsel.append_text(s)
        try:
            i=COLORS.index(self.color)
        except IndexError:
            i=0
        colorsel.set_active(i)
        vbox.pack_start(label_widget(_("Color"), colorsel), expand=False)

        # Linewidth
        linewidthsel = gtk.SpinButton()
        linewidthsel.set_range(1, 15)
        linewidthsel.set_increments(1, 1)
        linewidthsel.set_value(self.linewidth)
        vbox.pack_start(label_widget(_("Linewidth"), linewidthsel), expand=False)

        # Filled
        filledsel = gtk.ToggleButton()
        filledsel.set_active(self.filled)
        vbox.pack_start(label_widget(_("Filled"), filledsel), expand=False)

        # svg_attrib
        store=gtk.ListStore(str, str)
        for k, v in self.svg_attrib.iteritems():
            store.append([k, v])
        treeview=gtk.TreeView(model=store)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn("Attribute", renderer, text=0)
        column.set_resizable(True)
        treeview.append_column(column)

        renderer = gtk.CellRendererText()
        renderer.set_property('editable', True)
        column = gtk.TreeViewColumn("Value", renderer, text=1)
        column.set_resizable(True)
        treeview.append_column(column)

        treeview.show_all()
        e=gtk.Expander('SVG attributes')
        e.add(treeview)
        e.set_expanded(False)
        vbox.add(e)

        vbox.widgets = {
            'name': namesel,
            'color': colorsel,
            'linewidth': linewidthsel,
            'filled': filledsel,
            'link': linksel,
            'link_label': linklabelsel,
            'attrib': treeview,
            }
        return vbox

    def edit_properties(self):
        """Display a widget to edit the shape properties.
        """
        edit=self.edit_properties_widget()

        d = gtk.Dialog(title=_("Properties of %s") % self.name,
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ) )

        d.vbox.add(edit)

        def keypressed_cb(widget=None, event=None):
            if event.keyval == gtk.keysyms.Return:
                d.response(gtk.RESPONSE_OK)
                return True
            elif event.keyval == gtk.keysyms.Escape:
                d.response(gtk.RESPONSE_CANCEL)
                return True
            return False
        d.connect('key-press-event', keypressed_cb)

        edit.show_all()
        res=d.run()
        d.destroy()

        if res == gtk.RESPONSE_OK:
            # Get new values
            for n in ('name', 'link', 'link_label', 'uri', 'text'):
                if n in edit.widgets:
                    setattr(self, n, edit.widgets[n].get_text())
            self.color = COLORS[edit.widgets['color'].get_active()]
            for n in ('linewidth', 'textsize'):
                if n in edit.widgets:
                    setattr(self, n, int(edit.widgets[n].get_value()))
            self.filled = edit.widgets['filled'].get_active()
            return True

        return False

class Rectangle(Shape):
    """Rectangle shape.

    It can be used as a baseclass for other shapes with corresponding
    behaviour.
    """
    SHAPENAME=_("Rectangle")
    SVGTAG='rect'

    # List of attributes holding the shape coordinates. The second
    # element of the tuple is the index in the dimension tuple (width,
    # height) used to compute relative sizes
    coords=( ('x', 0),
             ('y', 1),
             ('width', 0),
             ('height', 1) )

    def set_bounds(self, bounds):
        self.x = int(min(bounds[0][0], bounds[1][0]))
        self.y = int(min(bounds[0][1], bounds[1][1]))
        self.width = int(abs(bounds[0][0] - bounds[1][0]))
        self.height = int(abs(bounds[0][1] - bounds[1][1]))

    def get_bounds(self):
        return ( (self.x, self.y), (self.x + self.width, self.y + self.height) )

    def render(self, pixmap, invert=False):
        col=pixmap.get_colormap().alloc_color(self.color)
        gc=pixmap.new_gc(foreground=col, line_width=self.linewidth)
        if invert:
            gc.set_function(gtk.gdk.INVERT)
        pixmap.draw_rectangle(gc,
                  self.filled,
                  self.x,
                  self.y,
                  self.width,
                  self.height)
        return

    def translate(self, vector):
        self.x += int(vector[0])
        self.y += int(vector[1])

    def copy_from(self, shape, style=False):
        shape.x = self.x
        shape.y = self.y
        shape.width = self.width
        shape.height = self.height
        if style:
            shape.color = self.color
            shape.linewidth = self.linewidth

    def control_point(self, point):
        """If on a control point, return its coordinates (x, y) and those of the other bound, else None

        This version is fitted for rectangular areas
        """
        x, y = point[0], point[1]
        retval = [[None, None], [None, None]]
        if abs(x - self.x) <= self.tolerance:
            retval[0][0] = self.x + self.width
            retval[1][0] = self.x
        elif abs(x - self.x - self.width) <= self.tolerance:
            retval[0][0] = self.x
            retval[1][0] = self.x + self.width
        else:
            return None
        if abs(y - self.y) <= self.tolerance:
            retval[0][1] = self.y + self.height
            retval[1][1] = self.y
        elif abs(y - self.y - self.height) <= self.tolerance:
            retval[0][1] = self.y
            retval[1][1] = self.y + self.height
        else:
            return None
        return retval

    def __contains__(self, point):
        x, y = point
        return ( x >= self.x
                 and x <= self.x + self.width
                 and y >= self.y
                 and y <= self.y + self.height )

class Text(Rectangle):
    """Experimental Text shape. Non-working for the moment.
    """
    SHAPENAME=_("Text")
    SVGTAG='text'

    coords=( ('x', 0),
             ('y', 1) )

    def __init__(self, name=SHAPENAME, color="green"):
        super(Text, self).__init__(name, color)
        self.text='Some text'
        self.textsize=20

    def render(self, pixmap, invert=False):
        width, height=pixmap.get_size()
        context=pixmap.cairo_create()
        context.move_to(self.x, self.y)
        context.select_font_face("Helvetica", cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(self.textsize)

        # FIXME: does not work correctly...
        if invert:
            context.set_operator(cairo.OPERATOR_XOR)
        color=gtk.gdk.color_parse(self.color)
        rgba=(color.red / 65536.0, color.green / 65536.0, color.blue / 65536.0, 1.0)
        context.set_source_rgba(*rgba)

        try:
            context.show_text(self.text)
            self.width, self.height = context.text_extents(self.text)[2:4]
        except MemoryError:
            print "MemoryError while rendering text"
        return

    def parse_svg(cls, element, context):
        """Parse a SVG representation.

        The context object must implement a 'dimensions' method that
        will return a (width, height) tuple corresponding to the
        canvas size.

        @param element: etree.Element to parse
        @param context: the svg context
        @return: an appropriate shape, or None if the class could not parse the element
        """
        if element.tag != cls.SVGTAG and element.tag != ET.QName(SVGNS, cls.SVGTAG):
            return None
        s=cls(name=element.attrib.get('name', cls.SHAPENAME))
        s.filled=( element.attrib.get('fill', 'none') != 'none' )
        s.color=element.attrib['stroke']
        s.text=element.text
        style=element.attrib['style']
        if style.startswith('stroke-width:'):
            s.linewidth=int(style.replace('stroke-width:', ''))
        c=cls.xml2coords(cls.coords, element.attrib, context.dimensions())
        for n, v in c.iteritems():
            setattr(s, n, v)
        s.svg_attrib=dict(element.attrib)
        if hasattr(s, 'post_parse'):
            s.post_parse()
        return s
    parse_svg=classmethod(parse_svg)

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the shape.
        """
        attrib=dict(self.svg_attrib)
        attrib.update(self.coords2xml(relative, size))
        attrib['name']=self.name
        attrib['stroke']=self.color
        attrib['style']="stroke-width:%d" % self.linewidth
        e=ET.Element('text', attrib=attrib)
        e.text=self.text
        if self.link:
            a=ET.Element('a', attrib={ 'xlink:href': self.link,
                                       'title': self.link_label })
            a.append(e)
            return a
        else:
            return e

    def __contains__(self, point):
        # We cannot use the inherited method, since text is draw *above* x,y
        x, y = point
        return ( x >= self.x
                 and x <= self.x + self.width
                 and y >= self.y - self.height
                 and y <= self.y )

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox=super(Text, self).edit_properties_widget()

        def label_widget(label, widget):
            hb=gtk.HBox()
            hb.add(gtk.Label(label))
            hb.pack_start(widget, expand=False)
            return hb

        # URI
        textsel = gtk.Entry()
        textsel.set_text(self.text)
        vbox.pack_start(label_widget(_("Text"), textsel), expand=False)
        vbox.widgets['text']=textsel

        # Text size
        textsizesel = gtk.SpinButton()
        textsizesel.set_range(4, 80)
        textsizesel.set_increments(1, 4)
        textsizesel.set_value(self.textsize)
        vbox.pack_start(label_widget(_("Textsize"), textsizesel), expand=False)
        vbox.widgets['textsize']=textsizesel

        return vbox

class Image(Rectangle):
    """Experimental Image shape.

    It serves as a placeholder for the background image for the
    moment, which is handled in the ShapeDrawer class. So the render
    method is not implemented.
    """
    SHAPENAME=_("Image")
    SVGTAG='image'

    # List of attributes holding the shape coordinates. The second
    # element of the tuple is the index in the dimension tuple (width,
    # height) used to compute relative sizes
    coords=( ('x', 0),
             ('y', 1),
             ('width', 0),
             ('height', 1) )

    def __init__(self, name=SHAPENAME, color="green"):
        super(Image, self).__init__(name, color)
        self.uri=''

    def render(self, pixmap, invert=False):
        # FIXME
        return

    def parse_svg(cls, element, context):
        """Parse a SVG representation.

        The context object must implement a 'dimensions' method that
        will return a (width, height) tuple corresponding to the
        canvas size.

        @param element: etree.Element to parse
        @param context: the svg context
        @return: an appropriate shape, or None if the class could not parse the element
        """
        if element.tag != cls.SVGTAG and element.tag != ET.QName(SVGNS, cls.SVGTAG):
            return None
        s=cls(name=element.attrib.get('name', cls.SHAPENAME))
        s.uri=element.attrib.get('xlink:href', element.attrib.get('{http://www.w3.org/1999/xlink}href', ''))
        c=cls.xml2coords(cls.coords, element.attrib, context.dimensions())
        for n, v in c.iteritems():
            setattr(s, n, v)
        s.svg_attrib=dict(element.attrib)
        if hasattr(s, 'post_parse'):
            s.post_parse()
        return s
    parse_svg=classmethod(parse_svg)

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the shape.

        @param relative: should dimensions be relative to the container size or absolute?
        @type relative: boolean
        @param size: the container size in pixels
        @type size: a couple of int
        @return: the SVG representation
        @rtype: elementtree.Element
        """
        attrib=dict(self.svg_attrib)
        attrib.update(self.coords2xml(relative, size))
        attrib['name']=self.name
        attrib['xlink:href']=self.uri
        e=ET.Element(ET.QName(SVGNS, self.SVGTAG), attrib=attrib)
        if self.link:
            a=ET.Element('a', attrib={ 'xlink:href': self.link,
                                       'title': self.link_label or _("Link to %s") % self.link })
            a.append(e)
            return a
        else:
            return e

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox=super(Image, self).edit_properties_widget()

        def label_widget(label, widget):
            hb=gtk.HBox()
            hb.add(gtk.Label(label))
            hb.pack_start(widget, expand=False)
            return hb

        # URI
        urisel = gtk.Entry()
        urisel.set_text(self.uri)
        vbox.pack_start(label_widget(_("Href"), urisel), expand=False)
        vbox.widgets['uri']=urisel
        return vbox

    def __contains__(self, point):
        return False

class Line(Rectangle):
    """A simple Line.
    """
    SHAPENAME=_("Line")
    SVGTAG='line'

    coords=( ('x1', 0),
             ('y1', 1),
             ('x2', 0),
             ('y2', 1) )

    def set_bounds(self, bounds):
        self.x1, self.y1 = bounds[0]
        self.x2, self.y2 = bounds[1]

        self.width = int(self.x2 - self.x1)
        self.height = int(self.y2 - self.y1)

    def get_bounds(self):
        return ( (self.x1, self.y1), (self.x2, self.y2 ) )

    def render(self, pixmap, invert=False):
        col=pixmap.get_colormap().alloc_color(self.color)
        gc=pixmap.new_gc(foreground=col, line_width=self.linewidth)
        if invert:
            gc.set_function(gtk.gdk.INVERT)
        pixmap.draw_line(gc,
                  self.x1,
                  self.y1,
                  self.x2,
                  self.y2)
        return

    def translate(self, vector):
        self.x1 += int(vector[0])
        self.x2 += int(vector[0])
        self.y1 += int(vector[1])
        self.y2 += int(vector[1])
        # Recompute other attributes
        self.set_bounds( self.get_bounds() )

    def copy_from(self, shape, style=False):
        shape.set_bounds( self.get_bounds() )
        if style:
            shape.color = self.color
            shape.linewidth = self.linewidth

    def control_point(self, point):
        """If on a control point, return its coordinates (x, y) and those of the other bound, else None

        This version is fitted for rectangular areas
        """
        x, y = point[0], point[1]
        retval = [[None, None], [None, None]]
        if abs(x - self.x1) <= self.tolerance:
            retval[0][0] = self.x2
            retval[1][0] = self.x1
        elif abs(x - self.x2) <= self.tolerance:
            retval[0][0] = self.x1
            retval[1][0] = self.x2
        else:
            return None
        if abs(y - self.y1) <= self.tolerance:
            retval[0][1] = self.y2
            retval[1][1] = self.y1
        elif abs(y - self.y2) <= self.tolerance:
            retval[0][1] = self.y1
            retval[1][1] = self.y2
        else:
            return None
        return retval

    def __contains__(self, point):
        x, y = point
        if (self.x2 - self.x1) == 0:
            return (y > min(self.y1, self.y2)
                 and y < max(self.y1, self.y2)
                 and abs(x - self.x1) < self.tolerance )
        a=1.0 * (self.y2 - self.y1) / (self.x2 - self.x1)
        b=self.y1 - a * self.x1
        return ( x > min(self.x1, self.x2)
                 and x < max(self.x1, self.x2)
                 and y > min(self.y1, self.y2)
                 and y < max(self.y1, self.y2)
                 and abs(y - (a * x + b)) < self.tolerance )

class Circle(Rectangle):
    """A Circle shape.

    @ivar cx, cy: the coordinates of the center in pixel
    @type centerx, cy: int
    @ivar r: the circle radius in pixel
    @type r: int
    """
    # FIXME: should indeed be Ellipse, since it may happen that rx != ry
    SHAPENAME=_("Circle")
    SVGTAG='circle'

    coords=( ('cx', 0),
             ('cy', 1),
             ('r', 0) )

    def set_bounds(self, bounds):
        self.x = int(min(bounds[0][0], bounds[1][0]))
        self.y = int(min(bounds[0][1], bounds[1][1]))
        self.width = int(abs(bounds[0][0] - bounds[1][0]))
        self.height = int(abs(bounds[0][1] - bounds[1][1]))

        self.cx = int( (bounds[0][0] + bounds[1][0]) / 2)
        self.cy = int( (bounds[0][1] + bounds[1][1]) / 2)
        #self.r = int(sqrt( (self.width / 2) ** 2 + (self.height / 2) ** 2))
        self.r = self.width / 2

    def render(self, pixmap, invert=False):
        col=pixmap.get_colormap().alloc_color(self.color)
        gc=pixmap.new_gc(foreground=col, line_width=self.linewidth)
        if invert:
            gc.set_function(gtk.gdk.INVERT)
        pixmap.draw_arc(gc,
                  self.filled,
                  self.x, self.y,
                  self.width, self.height,
                  0, 360 * 64)
        return

    def __contains__(self, point):
        x, y = point
        d = (point[0] - self.cx) ** 2 + (point[1] - self.cy) ** 2
        return d < ( self.r ** 2 )

    def translate(self, vector):
        self.cx += int(vector[0])
        self.cy += int(vector[1])
        self.x=self.cx - self.r
        self.y=self.cy - self.r

    def post_parse(self):
        """Method called after parsing of a SVG representation.
        """
        # Compute x, y, width, height values
        self.x=self.cx - self.r
        self.y=self.cy - self.r
        self.width=2 * self.r
        self.height=2 * self.r

class Link(Shape):
    """Link pseudo-shape.

    Handles link attributes. Its parse_svg method will return the
    enclosed concrete shape, with link and link_label fields
    initialized with the appropriate values.
    """
    SHAPENAME=_("Link")
    SVGTAG='a'

    def parse_svg(cls, element, context):
        """Parse a SVG representation.

        The context object must implement a 'dimensions' method that
        will return a (width, height) tuple corresponding to the
        canvas size.

        @param element: etree.Element to parse
        @param context: the svg context
        @return: an appropriate shape, or None if the class could not parse the element
        """
        if element.tag != cls.SVGTAG and element.tag != ET.QName(SVGNS, cls.SVGTAG):
            return None
        # Parse the element children.
        # FIXME: we only handle the first one ATM. Should use a generator here.
        o=None
        for c in element:
            for clazz in defined_shape_classes:
                o=clazz.parse_svg(c, context)
                if o is not None:
                    break
        if o is None:
            print "Invalid <a> content in SVG"
            return None
        o.link=element.attrib.get('xlink:href', element.attrib.get('{http://www.w3.org/1999/xlink}href', ''))
        o.link_label=element.attrib.get('title', 'Link to ' + o.link)
        #o.svg_attrib=dict(element.attrib)
        return o
    parse_svg=classmethod(parse_svg)

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the shape.

        @param relative: should dimensions be relative to the container size or absolute?
        @type relative: boolean
        @param size: the container size in pixels
        @type size: a couple of int
        @return: the SVG representation
        @rtype: elementtree.Element
        """
        print "Should not happen..."
        return None

class ShapeDrawer:
    """Widget allowing to draw and edit shapes.

    @ivar callback: method called when the button is released.
    @type callback: method taking a rectangle as parameter

    @ivar background: the canvas background
    @type background: gtk.Image
    @ivar objects: the list of defined objects
    @type objects: gtk.ListStore
    @ivar selection: the rectangular selection coordinates
    @type selection: a list of 2 lists
    @ivar feedback_shape: the currently edited shape, displayed as feedback
    @type feedback_shape: Shape
    @ivar shape_class: the default shape class to be created

    @ivar mode: the current editing mode ("create", "resize" or "translate")
    @type mode: string

    @ivar pixmap: the edited pixmap
    @type pixmap: gtk.gdk.Pixmap
    @ivar canvaswidth, canvasheight: the canvas dimensions
    @type canvaswidth, canvasheight: int

    @ivar widget: the gtk Widget for the component
    @type widget: gtk.Widget

    """
    def __init__(self, callback=None, background=None):
        """
        @param callback: the callback method
        @param background: an optional background image
        @type background: gtk.Image
        """
        self.callback = callback or self.default_callback

        # background is a gtk.Image()
        self.background = background

        # Couples object - name
        self.objects = gtk.ListStore( object, str )
        def handle_reorder(*p):
            self.plot()
            return True
        self.objects.connect('rows-reordered', handle_reorder)
        self.objects.connect('row-inserted', handle_reorder)
        self.objects.connect('row-changed', handle_reorder)
        self.objects.connect('row-deleted', handle_reorder)

        # Marked area point[0, 1][x, y]
        self.selection = [[None, None], [None, None]]
        self.feedback_shape = None
        self.shape_class = Rectangle

        # mode: "create", "resize" or "translate"
        self.mode = "resize"

        self.pixmap = None

        self.widget = gtk.DrawingArea()
        self.widget.connect('expose-event', self.expose_event)
        self.widget.connect('configure-event', self.configure_event)
        self.widget.connect('button-press-event', self.button_press_event)
        self.widget.connect('button-release-event', self.button_release_event)
        self.widget.connect('motion-notify-event', self.motion_notify_event)
        self.widget.set_events(gtk.gdk.EXPOSURE_MASK | gtk.gdk.LEAVE_NOTIFY_MASK | gtk.gdk.BUTTON_PRESS_MASK | gtk.gdk.BUTTON_RELEASE_MASK | gtk.gdk.POINTER_MOTION_MASK |gtk.gdk.POINTER_MOTION_HINT_MASK)

        if self.background:
            p=self.background.get_pixbuf()
            w=p.get_width()
            h=p.get_height()
            self.canvaswidth=w
            self.canvasheight=h
        else:
            self.canvaswidth=320
            self.canvasheight=200
        self.widget.set_size_request(self.canvaswidth, self.canvasheight)

    def default_callback(self, rectangle):
        """Default callback.
        """
        print "Got selection ", str(rectangle)

    def add_object(self, o):
        """Add an object (shape) to the object list.
        """
        self.objects.append( (o, o.name) )
        self.plot()

    def find_object(self, o):
        """Return the iterator for the given object.

        @param o: the searched object
        @return: the iterator
        @rtype: gtk.Iterator
        """
        i = self.objects.get_iter_first()
        while i is not None:
            if self.objects.get_value(i, 0) == o:
                return i
            i = self.objects.iter_next(i)
        return None

    def remove_object(self, o):
        """Remove the given object from the list.
        """
        i = self.find_object(o)
        if i is not None:
            self.objects.remove( i )
        self.plot()

    def clear_objects(self):
        """Remove all objects from the list.
        """
        self.objects.clear()
        self.plot()
        return True

    def dimensions(self):
        """Return the canvas dimensions.

        @return: the dimensions in pixel
        @rtype: a couple (width, height)
        """
        return (self.canvaswidth, self.canvasheight)

    def configure_event(self, widget, event):
        if self.background:
            p=self.background.get_pixbuf()
            w=p.get_width()
            h=p.get_height()
        else:
            x, y, w, h = widget.get_allocation()

        self.pixmap = gtk.gdk.Pixmap(widget.window, w, h)
        self.canvaswidth = w
        self.canvasheight = h
        self.plot()
        return True

    # Redraw the screen from the backing pixmap
    def expose_event(self, widget, event):
        x, y, w, h = event.area
        widget.window.draw_drawable(widget.get_style().fg_gc[gtk.STATE_NORMAL], self.pixmap, x, y, x, y, w, h)
        return False

    def clicked_shape(self, point):
        """Check if point is on a shape.
        """
        for o in self.objects:
            if point in o[0]:
                return o[0]
        return None

    def add_menuitem(self, menu=None, item=None, action=None, *param, **kw):
        if item is None or item == "":
            i = gtk.SeparatorMenuItem()
        else:
            i = gtk.MenuItem(item)
        if action is not None:
            i.connect('activate', action, *param, **kw)
        menu.append(i)

    def popup_menu(self, shape):
        menu = gtk.Menu()

        def add_item(*p, **kw):
            self.add_menuitem(menu, *p, **kw)

        def remove(i, o):
            self.remove_object(o)

        def properties(i, o):
            if o.edit_properties():
                self.plot()
                # Update liststore
                i = self.find_object(o)
                if i is not None:
                    self.objects.set_value(i, 1, o.name)

        def dump_svg(i, o):
            s=o.get_svg()
            ET.dump(s)
            return True

        add_item(shape.name)
        add_item("")
        add_item(_("Delete"), remove, shape)
        add_item(_("Properties"), properties, shape)
        add_item(_("SVG"), dump_svg, shape)

        menu.show_all()
        menu.popup(None, None, None, 0, gtk.get_current_event_time())

        return True

    # Start marking selection
    def button_press_event(self, widget, event):
        x = int(event.x)
        y = int(event.y)
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            # Double-click. Open properties for the shape.
            sel=self.clicked_shape( ( x, y ) )
            if sel is not None and sel.edit_properties():
                self.plot()
                # Update liststore
                i = self.find_object(sel)
                if i is not None:
                    self.objects.set_value(i, 1, sel.name)
            return True
        elif event.button == 1:
            self.selection[0][0], self.selection[0][1] = x, y
            self.selection[1][0], self.selection[1][1] = None, None
            sel=self.clicked_shape( ( x, y ) )
            if sel is not None:
                # Existing shape selected
                self.feedback_shape = sel
                c=sel.control_point( (x, y) )
                if c is not None:
                    self.selection = c
                    self.mode = "resize"
                else:
                    self.mode = "translate"
            else:
                self.feedback_shape = self.shape_class()
                self.feedback_shape.set_bounds( ( self.selection[0], self.selection[0]) )
                self.mode = "create"
        elif event.button == 3:
            # Popup menu
            sel=self.clicked_shape( ( x, y ) )
            if sel is not None:
                self.popup_menu(sel)
        return True

    # End of selection
    def button_release_event(self, widget, event):
        x = int(event.x)
        y = int(event.y)

        retval = ( self.selection[0][:], self.selection[1][:])
        if event.button == 1:
            if self.feedback_shape is not None:
                self.feedback_shape = None
                self.plot()

            self.selection[1][0] = None
            self.selection[0][0] = None

            if self.mode == "create":
                self.callback( retval )

    # Draw rectangle during mouse movement
    def motion_notify_event(self, widget, event):
        if event.is_hint:
            x, y, State = event.window.get_pointer()
        else:
            x = event.x
            y = event.y
            State = event.state

        if State & gtk.gdk.BUTTON1_MASK and self.feedback_shape is not None:
            if self.selection[1][0] is not None:
                self.feedback_shape.render(self.pixmap, invert=True)
            self.selection[1][0], self.selection[1][1] = int(x), int(y)

            if self.mode == "translate":
                self.feedback_shape.translate( (x - self.selection[0][0],
                                                y - self.selection[0][1] ) )
                self.selection[0][0] = x
                self.selection[0][1] = y
            elif self.mode == "resize" or self.mode == "create":
                self.feedback_shape.set_bounds( self.selection )

            self.feedback_shape.render(self.pixmap, invert=True)
            self.draw_drawable()

    def draw_drawable(self):
        """Render the pixmap in the drawingarea."""
        if self.widget.window is None:
            # The widget may not be realized, in which case simply return
            return
        x, y, w, h = self.widget.get_allocation()
        self.widget.window.draw_drawable(self.widget.get_style().fg_gc[gtk.STATE_NORMAL], self.pixmap, 0, 0, 0, 0, w, h)

    def plot(self):
        """Draw in the pixmap.
        """
        if self.pixmap is None:
            return
        self.pixmap.draw_rectangle(self.widget.get_style().white_gc, True, 0, 0, self.canvaswidth, self.canvasheight)

        if self.background:
            pixbuf=self.background.get_pixbuf()
            self.pixmap.draw_pixbuf(self.widget.get_style().white_gc,
                                    pixbuf,
                                    0, 0,
                                    0, 0)

        for o in self.objects:
            # o[0] may be None, if plot() is called from the callback
            # of a ListStore signal
            if o[0] is not None:
                o[0].render(self.pixmap)

        if self.feedback_shape is not None:
            self.feedback_shape.render(self.pixmap, invert=True)

        self.draw_drawable()

    def get_svg(self, relative=False):
        """Return a SVG representation.
        """
        size=self.dimensions()
        root=ET.Element(ET.QName(SVGNS, 'svg'), {
                'version': '1',
                'preserveAspectRatio': "xMinYMin meet" ,
                'viewBox': '0 0 %d %d' % size,
                'width': "%dpt" % size[0],
                'height': "%dpt" % size[1],
                'xmlns:xlink': "http://www.w3.org/1999/xlink",
                # The following xmlns declaration is needed for a
                # correct rendering in firefox
                'xmlns': "http://www.w3.org/2000/svg",
                })
        bg=[ o[0] for o in self.objects if isinstance(o, Image) and o.name == 'background' ]
        if bg:
            # There is background. Put it first.
            bg=bg[0]
            # Force the background image dimension
            bg.x=0
            bg.y=0
            # The background image has presumably been rendered. Get
            # its dimensions.
            if hasattr(bg, '_pixbuf'):
                bg.width=bg._pixbuf.get_width()
                bg.height=bg._pixbuf.get_height()
            root.append(bg.get_svg(relative=relative, size=size))
        else:
            bg=None
        for o in self.objects:
            if o == bg:
                # The background already has been added
                continue
            root.append(o[0].get_svg(relative=relative, size=size))
        ET_indent(root)
        return root

    def parse_svg(self, et, current_path=''):
        """Parse a SVG representation

        et is an ET.Element with tag == 'svg'

        path is the file path of the parsed element (so that relative
        hrefs can be resolved)
        """
        if et.tag != 'svg' and et.tag != ET.QName(SVGNS, 'svg'):
            print "Not a svg file"
        for c in et:
            for clazz in defined_shape_classes:
                o=clazz.parse_svg(c, self)
                if o is not None:
                    if isinstance(o, Image) and o.name == 'background':
                        # We have a background image.
                        if o.uri.startswith('http:'):
                            # http url, download the file
                            (fname, header)=urllib.urlretrieve(o.uri)
                            i=gtk.Image()
                            print "Loaded background from ", o.uri, " copy in", fname
                            i.set_from_file(fname)
                        else:
                            # Consider it as local.
                            if current_path and not os.path.exists(o.uri):
                                # The file does not exist. Try to
                                # prepend the context path.
                                uri=os.path.join( current_path, o.uri)
                            else:
                                uri=o.uri
                            i=gtk.Image()
                            i.set_from_file(uri)
                            if i.get_storage_type() != gtk.IMAGE_PIXBUF:
                                p=gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,
                                                 True, 8, o.width, o.height)
                                p.fill(0xdeadbeaf)
                                i.set_from_pixbuf(p)
                            print "Loaded background from ", uri
                            self.background=i
                        # We insert the background at the beginning of
                        # the object stack, so that other shapes are
                        # drawn over it.
                        self.objects.insert(0, (o, o.name))
                        # Update the size of the shape and the widget
                        p=self.background.get_pixbuf()
                        o._pixbuf=p
                        o.x=0
                        o.y=0
                        o.width=self.canvaswidth=p.get_width()
                        o.height=self.canvasheight=p.get_height()
                    else:
                        self.objects.append( (o, o.name) )
                    break
        self.plot()
        return True

class ShapeEditor:
    """Shape Editor component.

    This component provides an example of using ShapeWidget.
    """
    def __init__(self, background=None):
        self.background=None
        self.drawer=ShapeDrawer(callback=self.callback,
                                background=background)
        self.shapes = [ Rectangle, Circle, Line, Text, Image ]

        self.colors = COLORS
        self.defaultcolor = self.colors[0]
        self.widget=self.build_widget()

    def callback(self, l):
        if l[0][0] is None or l[1][0] is None:
            return
        r = self.drawer.shape_class()
        r.name = r.SHAPENAME + str(l)
        r.color = self.defaultcolor
        r.set_bounds(l)
        self.drawer.add_object(r)
        return

    def remove_item(self, treeview, path, column):
        m=treeview.get_model()
        o=treeview.get_model()[m.get_iter(path)][0]
        self.drawer.remove_object(o)
        return True

    def build_selector(self, l, callback):
        sel = gtk.combo_box_new_text()
        for s in l:
            sel.append_text(s)
        sel.connect('changed', callback)
        sel.set_active(0)
        return sel

    def get_selected_node (self, tree_view):
        """Return the currently selected node.

        None if no node is selected.
        """
        selection = tree_view.get_selection ()
        if not selection:
            return None
        store, it = selection.get_selected()
        node = None
        if it is not None:
            node = tree_view.get_model().get_value (it, 0)
        return node

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)

        # On double-click, edit element
        if event.type == gtk.gdk._2BUTTON_PRESS:
            node = self.get_selected_node (widget)
            if node is not None:
                if node.edit_properties():
                    self.drawer.plot()
                    # Update liststore
                    i = self.drawer.find_object(node)
                    if i is not None:
                        self.drawer.objects.set_value(i, 1, node.name)
                retval=True
            else:
                retval=False
        elif button == 3:
            if event.window is widget.get_bin_window():
                model = widget.get_model()
                t = widget.get_path_at_pos(x, y)
                if t is not None:
                    path, col, cx, cy = t
                    it = model.get_iter(path)
                    node = model.get_value(it, 0)
                    widget.get_selection().select_path (path)
                    self.drawer.popup_menu(node)
                    retval = True
        return retval

    def build_widget(self):
        vbox=gtk.VBox()


        hbox=gtk.HBox()
        vbox.add(hbox)


        hbox.pack_start(self.drawer.widget, True, True, 0)

        self.treeview = gtk.TreeView(self.drawer.objects)
        self.treeview.set_reorderable(True)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn('Name', renderer,
                                    text=1)
        self.treeview.append_column(column)
        self.treeview.connect('row-activated', self.remove_item)
        self.treeview.connect('button-press-event', self.tree_view_button_cb)

        control = gtk.VBox()

        # FIXME: toolbar at the top
        def changeshape(combobox):
            self.drawer.shape_class = self.shapes[combobox.get_active()]
            return True

        shapeselector = self.build_selector( [ s.SHAPENAME for s in self.shapes ],
                                            changeshape )
        control.pack_start(shapeselector, expand=False)

        def changecolor(combobox):
            self.defaultcolor = self.colors[combobox.get_active()]
            return True

        colorselector = self.build_selector( self.colors,
                                             changecolor )
        control.pack_start(colorselector, expand=False)

        control.pack_start(self.treeview, expand=False)

        def dump_svg(b):
            s=self.drawer.get_svg(relative=False)
            ET.dump(s)

        def load_svg(b):
            fs=gtk.FileChooserDialog(title='Select a svg file',
                                     buttons=(gtk.STOCK_OK, gtk.RESPONSE_OK, gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
            res=fs.run()
            if res == gtk.RESPONSE_OK:
                name=fs.get_filename()
                root=ET.parse(name).getroot()
                self.drawer.parse_svg(root)
            fs.destroy()
            return True

        b=gtk.Button(_("Dump SVG"))
        b.connect('clicked', dump_svg)
        control.pack_start(b, expand=False)

        b=gtk.Button(_("Load SVG"))
        b.connect('clicked', load_svg)
        control.pack_start(b, expand=False)

        hbox.pack_start(control, expand=False)
        vbox.show_all()
        return vbox

def main():
    import sys

    if len(sys.argv) > 1:
        bg = sys.argv[1]
    else:
        bg = 'atelier.jpg'

    win = gtk.Window(gtk.WINDOW_TOPLEVEL)
    win.set_title("Shape Editor test")
    #win.set_default_size(800, 600)
    win.connect('delete-event', lambda w, e: gtk.main_quit())

    if bg.endswith('.svg'):
        ed=ShapeEditor()
        root=ET.parse(bg).getroot()
        ed.drawer.parse_svg(root)
    else:
        i=gtk.Image()
        i.set_from_file(bg)

        ed=ShapeEditor(background=i)
    win.add(ed.widget)

    win.show_all()

    gtk.main()

# Element-tree indent function.
# in-place prettyprint formatter
def ET_indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            ET_indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

defined_shape_classes=[ c for c in locals().values() if hasattr(c, 'SHAPENAME') ]

# Start it all
if __name__ == '__main__':
    main()
