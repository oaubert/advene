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
"""Simple Shape editor widget
==========================

  This component provides a simple framework allowing to edit basic
  shapes, and generate the corresponding XML.

  This component should not have dependencies on Advene, so that it
  can be reused in other projects.

  Note: if given a background image at instanciation, ShapeDrawer will
  use its size as reference, else it will use a hardcoded dimension
  (see ShapeDrawer.__init__). When loading a SVG file, it will convert
  its dimensions into the reference size. When saving the SVG again,
  it will lose the original SVG dimensions and use instead the
  background/hardcoded dimensions.

FIXME: XML load/dump should try to preserve unhandled information (especially TAL instructions)
FIXME: find a way to pass search paths for xlink:href elements resolution
FIXME: find a way to pass the background path
"""
import logging
logger = logging.getLogger(__name__)

import os
import sys
import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
import cairo
import math
import urllib.request, urllib.parse, urllib.error
import re

from math import atan2, cos, sin

import xml.etree.ElementTree as ET

from gettext import gettext as _

COLORS = [ 'red', 'green', 'blue', 'black', 'white', 'gray', 'yellow' ]
SVGNS = 'http://www.w3.org/2000/svg'

stroke_width_re=re.compile(r'stroke-width:\s*(\d+)')
stroke_color_re=re.compile(r'stroke:\s*(\w+)')
arrow_width_re=re.compile(r'#arrow(\d+)')

defined_shape_classes=[]

class Shape:
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

    # If True, then the shape needs more than 2 control points to be
    # created. This implies a different interaction.
    MULTIPOINT = False

    def __init__(self, name=None, color="green", dimensions=None):
        self.name=name or self.SHAPENAME
        self.color=color
        self.linewidth=2
        self.opacity = 1.0
        self.filled = False
        # Pixel tolerance for control point selection
        self.tolerance = 6
        self.link=None
        self.link_label=None
        if dimensions is None:
            # It is needed since set_bounds initializes all the
            # dimension-related attributes of the object.
            dimensions = ( (0, 0), (10, 10) )
        self.set_bounds(dimensions)
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

    def render(self, context, invert=False):
        """Render the shape on the given context

        @param context: the destination context
        @type context: cairo.Context
        @param invert: should the rendering inverse the selection ?
        @type invert: boolean
        """
        return

    def render_setup(self, context, invert=False):
        """Setup context for common attributes.
        """
        context.set_line_width(self.linewidth)
        col = Gdk.RGBA()
        col.parse(self.color)
        col.alpha = self.opacity
        Gdk.cairo_set_source_rgba(context, col)

        if invert:
            context.set_operator(cairo.OPERATOR_XOR)
        else:
            context.set_operator(cairo.OPERATOR_OVER)

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

    def __unicode__(self):
        return "%s {%s}" % (self.SHAPENAME,
                            ",".join("%s: %d" % (c[0], getattr(self, c[0])) for c in self.coords))

    @classmethod
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
        s.color=element.attrib.get('stroke', None)
        s.opacity = float(element.attrib.get('opacity', 1.0))
        style=element.attrib.get('style', '')
        m=stroke_width_re.search(style)
        if m:
            s.linewidth=int(m.group(1))
        if s.color is None:
            # Try to find it in style definition
            m=stroke_color_re.search(style)
            if m:
                s.color = m.group(1)
            else:
                # Default fallback
                s.color = 'green'
        c=cls.xml2coords(cls.coords, element.attrib, context)
        for n, v in c.items():
            setattr(s, n, v)
        s.svg_attrib=dict(element.attrib)
        if hasattr(s, 'post_parse'):
            s.post_parse()
        return s

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
        if self.opacity != 1.0  or  "opacity" in attrib:
            attrib['opacity'] = str(self.opacity)
        attrib['stroke']=self.color
        attrib['style']="stroke-width:%d" % self.linewidth
        attrib['name']=self.name
        e=ET.Element(ET.QName(SVGNS, self.SVGTAG), attrib=attrib)
        if self.link:
            a=ET.Element('a', attrib={ 'xlink:href': self.link,
                                       'title': self.link_label or _("Link to %s") % self.link })
            a.append(e)
            yield a
        else:
            yield e

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

    @staticmethod
    def xml2coords(coords, attrib, context):
        """Converts coordinates in XML format to their appropriate value

        The context object must have 2 attributes:
        - dimensions: a (width, height) tuple giving the display canvas dimensions.
        - svg_dimensions: a (width, height) tuple giving the original SVG dimensions.

        @param coords: a list of (name, dimension_index) tuple
        @param attrib: an attributes dictionary
        @param context: an object holding the context information
        @return: a dictionary with values converted
        """
        res={}
        # Convert numeric attributes (possibly percentage) to float
        for n, dimindex in coords:
            v=attrib[n]
            if v.endswith('%'):
                # Convert it to absolute values
                v=float(v[:-1]) * context.dimensions[dimindex] / 100
            else:
                if context.dimensions == context.svg_dimensions:
                    v=float(v)
                else:
                    v=float(v) * context.dimensions[dimindex] / context.svg_dimensions[dimindex]
            res[n]=int(v)
        logger.debug("xml2coords %s -> %s", attrib, res)
        return res

    def coords2xml(self, relative, dimensions):
        """Converts coordinates to XML format

        Note: we do not convert back to original SVG dimensions,
        i.e. if a (640, 400) SVG was loaded over a (320, 200) canvas,
        we will generate in return a (320, 200) SVG.

        @param relative: convert to relative dimensions
        @param dimensions: a (width, height) tuple
        @return: a dictionary with values converted
        """
        res={}
        if relative:
            for n, dimindex in self.coords:
                res[n]="%.03f%%" % (getattr(self, n) * 100.0 / dimensions[dimindex])
        else:
            res = { n: str(getattr(self, n)) for n, d in self.coords }
        return res

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox=Gtk.VBox()

        def label_widget(label, widget, expand=False):
            hb=Gtk.HBox()
            hb.add(Gtk.Label(label=label))
            hb.pack_start(widget, expand, True, 0)
            return hb

        # Name
        namesel = Gtk.Entry()
        namesel.set_text(self.name)
        vbox.pack_start(label_widget(_("Name"), namesel), False, False, 0)

        # Link
        linksel = Gtk.Entry()
        linksel.set_text(self.link or '')
        vbox.pack_start(label_widget(_("Link"), linksel), False, False, 0)

        # Linklabel
        linklabelsel = Gtk.Entry()
        linklabelsel.set_text(self.link_label or '')
        vbox.pack_start(label_widget(_("Link label"), linklabelsel), False, False, 0)

        # Color
        colorsel = Gtk.ComboBoxText()
        for s in COLORS:
            colorsel.append_text(s)
        try:
            i=COLORS.index(self.color)
        except IndexError:
            i=0
        colorsel.set_active(i)
        vbox.pack_start(label_widget(_("Color"), colorsel), False, False, 0)

        # Linewidth
        linewidthsel = Gtk.HScale()
        linewidthsel.set_range(1, 15)
        linewidthsel.set_increments(1, 1)
        linewidthsel.set_value(self.linewidth)
        vbox.pack_start(label_widget(_("Linewidth"), linewidthsel, True), True, True, 0)

        # Filled
        filledsel = Gtk.ToggleButton()
        filledsel.set_active(self.filled)
        vbox.pack_start(label_widget(_("Filled"), filledsel), False, False, 0)

        # Linewidth
        opacitysel = Gtk.HScale()
        opacitysel.set_range(0, 1)
        opacitysel.set_digits(1)
        opacitysel.set_increments(.1, .2)
        opacitysel.set_value(self.opacity)
        vbox.pack_start(label_widget(_("Opacity"), opacitysel, True), True, True, 0)

        # svg_attrib
        store=Gtk.ListStore(str, str)
        for k, v in self.svg_attrib.items():
            store.append([k, v])
        treeview=Gtk.TreeView(model=store)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Attribute", renderer, text=0)
        column.set_resizable(True)
        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        renderer.set_property('editable', True)
        column = Gtk.TreeViewColumn("Value", renderer, text=1)
        column.set_resizable(True)
        treeview.append_column(column)

        treeview.show_all()
        e=Gtk.Expander.new('SVG attributes')
        e.add(treeview)
        e.set_expanded(False)
        vbox.add(e)

        vbox.widgets = {
            'name': namesel,
            'color': colorsel,
            'opacity': opacitysel,
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

        d = Gtk.Dialog(title=_("Properties of %s") % self.name,
                       parent=None,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ) )

        d.vbox.add(edit)

        def keypressed_cb(widget=None, event=None):
            if event.keyval == Gdk.KEY_Return:
                d.response(Gtk.ResponseType.OK)
                return True
            elif event.keyval == Gdk.KEY_Escape:
                d.response(Gtk.ResponseType.CANCEL)
                return True
            return False
        d.connect('key-press-event', keypressed_cb)

        edit.show_all()
        res=d.run()
        if res == Gtk.ResponseType.OK:
            # Get new values
            for n in ('name', 'link', 'link_label', 'uri', 'text'):
                if n in edit.widgets:
                    setattr(self, n, edit.widgets[n].get_text())
            self.color = COLORS[edit.widgets['color'].get_active()]
            for n in ('linewidth', 'textsize', 'arrowwidth'):
                if n in edit.widgets:
                    setattr(self, n, int(edit.widgets[n].get_value()))
            for n in ('opacity', ):
                if n in edit.widgets:
                    setattr(self, n, float(edit.widgets[n].get_value()))
            for n in ('filled', 'arrow', 'closed'):
                if n in edit.widgets:
                    setattr(self, n, edit.widgets[n].get_active())
            d.destroy()
            return True
        else:
            d.destroy()
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

    def render(self, context, invert=False):
        self.render_setup(context, invert)
        context.rectangle(self.x,
                          self.y,
                          self.width,
                          self.height)
        if self.filled:
            context.fill()
        else:
            context.stroke()
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
        return ( self.x <= x <= self.x + self.width
                 and self.y <= y <= self.y + self.height )

class Text(Rectangle):
    """Text shape.
    """
    SHAPENAME=_("Text")
    SVGTAG='text'

    coords=( ('x', 0),
             ('y', 1) )

    def __init__(self, name=SHAPENAME, color="green", dimensions=None):
        super(Text, self).__init__(name, color, dimensions)
        self.linewidth=1
        self.filled=True
        self.text='Some text'
        # FIXME: maybe we should consider a relative size (wrt. canvas size)
        self.textsize=20

    def get_bounds(self):
        return ( (self.x, self.y - self.height), (self.x + self.width, self.y) )

    def render(self, context, invert=False):
        self.render_setup(context, invert)
        context.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(self.textsize)

        extents = context.text_extents(self.text)

        # Fix width, height attributes
        self.width = extents[2]
        self.height = extents[3]
        context.move_to(self.x, self.y)
        try:
            context.show_text(self.text)
            self.width, self.height = extents[2:4]
        except MemoryError:
            logger.error("MemoryError while rendering text")
        return

    def control_point(self, point):
        return None

    @classmethod
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
        s.color=element.attrib.get('stroke', '2')
        s.text=element.text or ''
        style=element.attrib.get('style', '')
        m=stroke_width_re.search(style)
        if m:
            s.linewidth=int(m.group(1))
        c=cls.xml2coords(cls.coords, element.attrib, context)
        for n, v in c.items():
            setattr(s, n, v)
        s.svg_attrib=dict(element.attrib)
        if hasattr(s, 'post_parse'):
            s.post_parse()
        return s

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the shape.
        """
        attrib=dict(self.svg_attrib)
        attrib.update(self.coords2xml(relative, size))
        attrib['name']=self.name
        attrib['stroke']=self.color
        if self.filled:
            attrib['fill']=self.color
        else:
            attrib['fill']='none'
        attrib['style']="stroke-width:%d; font-family: sans-serif; font-size: %d" % (self.linewidth, self.textsize)
        e=ET.Element('text', attrib=attrib)
        e.text=self.text
        if self.link:
            a=ET.Element('a', attrib={ 'xlink:href': self.link,
                                       'title': self.link_label })
            a.append(e)
            yield a
        else:
            yield e

    def __contains__(self, point):
        # We cannot use the inherited method, since text is draw *above* x,y
        x, y = point
        return ( self.x <= x <= self.x + self.width
                 and self.y - self.height <= y <= self.y )

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox = super(Text, self).edit_properties_widget()

        def label_widget(label, widget):
            hb = Gtk.HBox()
            hb.add(Gtk.Label(label=label))
            hb.pack_start(widget, False, True, 0)
            return hb

        # Text
        textsel = Gtk.Entry()
        textsel.set_text(self.text)
        label = label_widget(_("Text"), textsel)
        vbox.pack_start(label, False, True, 0)
        # Put the text at the beginning
        vbox.reorder_child(label, 0)
        vbox.widgets['text'] = textsel

        # Text size
        textsizesel = Gtk.SpinButton()
        textsizesel.set_range(4, 80)
        textsizesel.set_increments(1, 4)
        textsizesel.set_value(self.textsize)
        label = label_widget(_("Textsize"), textsizesel)
        vbox.pack_start(label, False, True, 0)
        vbox.reorder_child(label, 1)
        vbox.widgets['textsize'] = textsizesel

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

    def __init__(self, name=SHAPENAME, color="green", dimensions=None, uri=''):
        super(Image, self).__init__(name, color, dimensions)
        self.uri=uri

    def render(self, context, invert=False):
        # FIXME
        return

    @classmethod
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
        c=cls.xml2coords(cls.coords, element.attrib, context)
        for n, v in c.items():
            setattr(s, n, v)
        s.svg_attrib=dict(element.attrib)
        if hasattr(s, 'post_parse'):
            s.post_parse()
        return s

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the shape.

        @param relative: should dimensions be relative to the container size or absolute?
        @type relative: boolean
        @param size: the container size in pixels
        @type size: a couple of int
        @return: the SVG representation
        @rtype: elementtree.Element
        """
        self.x=0
        self.y=0
        self.width=size[0]
        self.height=size[1]
        attrib=dict(self.svg_attrib)
        attrib.update(self.coords2xml(relative, size))
        attrib['name']=self.name
        attrib['xlink:href']=self.uri
        e=ET.Element(ET.QName(SVGNS, self.SVGTAG), attrib=attrib)
        if self.link:
            a=ET.Element('a', attrib={ 'xlink:href': self.link,
                                       'title': self.link_label or _("Link to %s") % self.link })
            a.append(e)
            yield a
        else:
            yield e

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox=super(Image, self).edit_properties_widget()

        def label_widget(label, widget):
            hb=Gtk.HBox()
            hb.add(Gtk.Label(label=label))
            hb.pack_start(widget, False, True, 0)
            return hb

        # URI
        urisel = Gtk.Entry()
        urisel.set_text(self.uri)
        vbox.pack_start(label_widget(_("Href"), urisel), False, False, 0)
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

    def __init__(self, name=SHAPENAME, color="green", dimensions=None, arrow=False):
        super(Line, self).__init__(name, color, dimensions)
        self.arrow=arrow
        self.arrowwidth=10

    def set_bounds(self, bounds):
        self.x1, self.y1 = bounds[0]
        self.x2, self.y2 = bounds[1]
        self.width = int(self.x2 - self.x1)
        self.height = int(self.y2 - self.y1)

    def get_bounds(self):
        return ( (self.x1, self.y1), (self.x2, self.y2 ) )

    def render(self, context, invert=False):
        self.render_setup(context, invert)
        context.move_to(self.x1, self.y1)
        context.line_to(self.x2, self.y2)
        if self.arrow:
            theta=atan2( self.width, self.height )
            ox=int(self.arrowwidth / 2) + 1
            oy=self.arrowwidth
            context.stroke()
            context.new_path()
            context.move_to(self.x2, self.y2)
            context.line_to(int(self.x2 - ox * cos(theta) - oy * sin(theta)),
                            int(self.y2 + ox * sin(theta) - oy * cos(theta)))
            context.line_to(int(self.x2 + ox * cos(theta) - oy * sin(theta)),
                            int(self.y2 - ox * sin(theta) - oy * cos(theta)))
            context.close_path()
        if self.filled:
            context.fill()
        else:
            context.stroke()
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
        """
        x, y = point[0], point[1]
        retval = None
        if (abs(x - self.x1) <= self.tolerance
            and abs(y - self.y1) <= self.tolerance):
            retval = [ [self.x2, self.y2], [self.x1, self.y1] ]
        elif (abs(x - self.x2) <= self.tolerance
              and abs(y - self.y2) <= self.tolerance):
            retval = [ [self.x1, self.y1], [self.x2, self.y2] ]
        return retval

    def __contains__(self, point):
        x, y = point
        if (self.x2 - self.x1) == 0:
            return (min(self.y1, self.y2) < y < max(self.y1, self.y2)
                    and abs(x - self.x1) < self.tolerance )
        a=1.0 * (self.y2 - self.y1) / (self.x2 - self.x1)
        b=self.y1 - a * self.x1
        return ( min(self.x1, self.x2) < x < max(self.x1, self.x2)
                 and min(self.y1, self.y2) < y < max(self.y1, self.y2)
                 and abs(y - (a * x + b)) < self.tolerance )

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox=super(Line, self).edit_properties_widget()

        def label_widget(label, widget):
            hb=Gtk.HBox()
            hb.add(Gtk.Label(label=label))
            hb.pack_start(widget, False, True, 0)
            return hb

        draw_arrow = Gtk.CheckButton(_("Draw an arrow"))
        draw_arrow.set_active(self.arrow)
        vbox.pack_start(draw_arrow, True, True, 0)
        vbox.reorder_child(draw_arrow, 0)
        vbox.widgets['arrow']=draw_arrow

        # Arrow size
        arrowsize = Gtk.SpinButton()
        arrowsize.set_range(1, 40)
        arrowsize.set_increments(1, 4)
        arrowsize.set_value(self.arrowwidth)
        label = label_widget(_("Arrow size"), arrowsize)
        vbox.pack_start(label, False, True, 0)
        vbox.reorder_child(label, 1)
        vbox.widgets['arrowwidth']=arrowsize
        return vbox

    def post_parse(self):
        """Handle arrow markers.
        """
        if 'marker-end' in self.svg_attrib:
            self.arrow=True
            self.arrowwidth=int(arrow_width_re.findall(self.svg_attrib['marker-end'])[0])

    def get_svg(self, relative=False, size=None):
        """
        <defs><marker id="myMarker" viewBox="0 0 10 10" refX="1" refY="5"
        markerUnits="strokeWidth" orient="auto"
        markerWidth="4" markerHeight="3">
        <polyline points="0,0 10,5 0,10 1,5" fill="darkblue" />
        </marker></defs>
        """
        e=next(super(Line, self).get_svg(relative, size))
        if self.arrow:
            if e.tag == 'a' or e.tag == ET.QName(SVGNS, 'a'):
                # It is a link. Use the child.
                el=e[0]
            else:
                el=e
            defs=ET.Element('defs')
            marker=ET.Element('marker', {
                'id': "arrow%d" % self.arrowwidth,
                'viewBox': "0 0 10 10",
                'refX': '5',
                'refY': '5',
                'orient': 'auto',
                'markerWidth': str(int(self.arrowwidth / 2) + 1),
                'markerHeight': str(self.arrowwidth) })
            defs.append(marker)
            marker.append(ET.Element('polyline', {
                'points': "0,0 10,5 0,10 1,5",
                'fill': self.color }))
            el.attrib['marker-end']='url(#arrow%d)' % self.arrowwidth
            yield defs
            yield e
        else:
            yield e

class Path(Shape):
    """A path.

    It is composed of multiple Lines.
    """
    SHAPENAME=_("Path")
    SVGTAG='path'

    MULTIPOINT = True
    coords = []

    def __init__(self, name=SHAPENAME, color="green", dimensions=None):
        # List of tuples (x, y) composing the path in absolute form
        self.path = []
        super(Path, self).__init__(name, color, dimensions)
        self.controlled_point_index = -1
        self.closed = False

    def clone(self, style=None):
        c = Path(self.name, self.color)
        c.path = [ list(p) for p in self.path ]
        return c

    @property
    def pathlines(self):
        """Returns the coordinates of the lines composing the path
        """
        if self.closed:
            return list(zip(self.path, self.path[1:] + self.path[:1]))
        else:
            return list(zip(self.path, self.path[1:]))

    def set_controlled_point(self, index=None, point=None):
        """Specify the index of the controlled point.

        If index is not given, then we will try to infer it from the
        point information.

        @param index: index of the point in self.path
        @type index: integer (default -1)
        @param point: coordinates of the controlled point
        @type point: tuple (x, y)
        """
        if index is None:
            # Default will be last point in any case
            index = -1

            # Try to infer index from given point
            for i, p in enumerate(self.path):
                if p[0] == point[0] and p[1] == point[1]:
                    index = i
                    break
        self.controlled_point_index = index

    def add_point(self, point):
        if self.path:
            self.path.append( list(point) )
        else:
            self.path = [ list(point), list(point) ]

    def remove_controlled_point(self):
        del self.path[self.controlled_point_index]
        self.controlled_point_index = -1

    def set_bounds(self, bounds):
        # Modify the controlled point
        if self.path:
            self.path[self.controlled_point_index] = list(bounds[1])
        else:
            self.path = [ list(bounds[0]),
                          list(bounds[1]) ]

    def get_bounds(self):
        return ( (min(x for x, y in self.path),
                  min(y for x, y in self.path)),
                 (max(x for x, y in self.path),
                  max(y for x, y in self.path)) )

    def render(self, context, invert=False, partial=False):
        self.render_setup(context, invert)
        if partial:
            # Only redraw last line
            for (x1, y1), (x2, y2) in self.pathlines[-1:]:
                context.move_to(x1, y1)
                context.line_to(x2, y2)
        else:
            for (x1, y1), (x2, y2) in self.pathlines:
                context.move_to(x1, y1)
                context.line_to(x2, y2)
        if self.filled:
            context.close_path()
            context.fill()
        else:
            context.stroke()
        return

    def translate(self, vector):
        dx = int(vector[0])
        dy = int(vector[1])
        self.path = [ (x + dx, y + dy) for (x, y) in self.path ]

    def copy_from(self, shape, style=False):
        shape.path = list(self.path)
        shape.set_bounds( self.get_bounds() )
        if style:
            shape.color = self.color
            shape.linewidth = self.linewidth

    def validate(self):
        """Validation method

        It is called upon shape finalization. It checks that the last
        point is not present twice (since we can validate through
        double-click). If so, it cleans the path.
        """
        if self.path:
            while len(self.path) >= 2:
                last = self.path[-1]
                prev = self.path[-2]
                if (abs(last[0] - prev[0]) <= self.tolerance
                    and abs(last[1] - prev[1]) <= self.tolerance):
                    # Two close points: remove the last one
                    self.path = self.path[:-1]
                else:
                    break

    def control_point(self, point):
        """If on a control point, return its coordinates (x, y) and those of the other bound, else None
        """
        x, y = point[0], point[1]
        retval = None
        for i, (x1, y1) in enumerate(self.path):
            if (abs(x - x1) <= self.tolerance
                and abs(y - y1) <= self.tolerance):
                # We simply fetch the previous point as alternate
                # point.
                x2, y2 = self.path[i - 1]
                retval = [ [x2, y2], [x1, y1] ]
                break
        # Reset controlled_point_index: it quite possibly does not
        # mean anything now
        self.controlled_point_index = -1
        return retval

    def __contains__(self, point):
        x, y = point
        for (x1, y1), (x2, y2) in self.pathlines:
            if (x2 - x1) == 0:
                if (min(y1, y2) < y < max(y1, y2)
                    and abs(x - x1) < self.tolerance ):
                    return True
            else:
                a = 1.0 * (y2 - y1) / (x2 - x1)
                b = y1 - a * x1
                if ( min(x1, x2) < x < max(x1, x2)
                     and min(y1, y2) < y < max(y1, y2)
                     and abs(y - (a * x + b)) < self.tolerance ):
                    return True
        return False

    def edit_properties_widget(self):
        """Build a widget to edit the shape properties.
        """
        vbox=super(Path, self).edit_properties_widget()

        closed_path = Gtk.CheckButton(_("Close path"))
        closed_path.set_active(self.closed)
        vbox.pack_start(closed_path, True, True, 0)
        vbox.reorder_child(closed_path, 0)
        vbox.widgets['closed']=closed_path

        return vbox

    def post_parse(self):
        """Populate path
        """
        self.path = []
        data = self.svg_attrib.get('d', "").split()
        # We reverse the list so that we can .pop() data out of it
        # (instead of .pop(0))
        data.reverse()

        if not data or data.pop() != 'M':
            # We need at least a starting point and a first line
            logger.error("SVG Path parsing error - wrong initial path element")
            return

        try:
            self.path.append( (int(data.pop()), int(data.pop())) )
            while data:
                command = data.pop()
                if command in ('l', 'h', 'v'):
                    # Relative coordinates
                    last = self.path[-1]
                else:
                    last = (0, 0)
                if command.lower() == 'l':
                    # Line: next 2 items are coordinates
                    self.path.append( (last[0] + int(data.pop()), last[1] + int(data.pop())) )
                elif command.lower() == 'h':
                    self.path.append( (last[0] + int(data.pop()), last[1]) )
                elif command.lower() == 'v':
                    self.path.append( (last[0], last[1] + int(data.pop())) )
                elif command.lower() == 'z':
                    # Closed path
                    self.closed = True
                else:
                    logger.error("SVG Path parsing error - unknown command: %s", command)
        except (IndexError, ValueError):
            logger.error("SVG Path parsing error - invalid conversion", exc_info=True)

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the path

        <path d="M 10 10 L 90 90 L 90 110 L 12 120 Z" fill="transparent" stroke="black"/>

        Z is optional (used for closed paths).
        """
        e = next(super(Path, self).get_svg(relative, size))
        if e.tag == 'a' or e.tag == ET.QName(SVGNS, 'a'):
            # It is a link. Use the child.
            el=e[0]
        else:
            el=e
        if relative:
            #res[n]="%.03f%%" % (getattr(self, n) * 100.0 / dimensions[dimindex])
            # FIXME: path coords are always unitless, hence we cannot
            # use % values here.  A solution could be to use a group
            # with appropriate translation/scaling, but it will
            # complicate the parsing code.
            el.attrib['d'] = "M "  + " L ".join( "%d %d" %  (x, y) for x, y in self.path ) + (" Z" if self.closed else "")
        else:
            el.attrib['d'] = "M "  + " L ".join( "%d %d" %  (x, y) for x, y in self.path ) + (" Z" if self.closed else "")
        yield e

class Circle(Rectangle):
    """A Circle shape.

    @ivar cx, cy: the coordinates of the center in pixel
    @type centerx, cy: int
    @ivar r: the circle radius in pixel
    @type r: int
    """
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
        self.r = int(self.width / 2)

    def render(self, context, invert=False):
        self.render_setup(context, invert)
        context.arc(self.x, self.y, self.width, 0, 2 * math.pi)
        if self.filled:
            context.fill()
        else:
            context.stroke()
        return

    def __contains__(self, point):
        x, y = point
        d = (x - self.cx) ** 2 + (y - self.cy) ** 2
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

class Ellipse(Rectangle):
    """An Ellipse shape.

    @ivar cx, cy: the coordinates of the center in pixel
    @type cx, cy: int
    @ivar rx, ry: horizontal and vertical radius in pixel
    @type rx, ry: int
    """
    SHAPENAME=_("Ellipse")
    SVGTAG='ellipse'

    coords=( ('cx', 0),
             ('cy', 1),
             ('rx', 0),
             ('ry', 1) )

    def set_bounds(self, bounds):
        self.x = int(min(bounds[0][0], bounds[1][0]))
        self.y = int(min(bounds[0][1], bounds[1][1]))
        self.width = int(abs(bounds[0][0] - bounds[1][0]))
        self.height = int(abs(bounds[0][1] - bounds[1][1]))

        self.cx = int( (bounds[0][0] + bounds[1][0]) / 2)
        self.cy = int( (bounds[0][1] + bounds[1][1]) / 2)
        self.rx = int(self.width / 2)
        self.ry = int(self.height / 2)

    def render(self, context, invert=False):
        self.render_setup(context, invert)
        context.save()
        context.translate(self.x + self.width / 2.,
                          self.y + self.height / 2.)
        if self.width and self.height:
            context.scale(self.width / 2., self.height / 2.)
        context.arc(0., 0., 1., 0., 2 * math.pi)
        context.restore()
        if self.filled:
            context.fill()
        else:
            context.stroke()
        return

    def __contains__(self, point):
        x, y = point
        if self.rx == 0 or self.ry == 0:
            return False
        d =  ( 1.0 * (x - self.cx) / self.rx ) ** 2 + ( 1.0 * (y - self.cy) / self.ry )  ** 2
        return d < 1

    def translate(self, vector):
        self.cx += int(vector[0])
        self.cy += int(vector[1])
        self.x=self.cx - self.rx
        self.y=self.cy - self.ry

    def post_parse(self):
        """Method called after parsing of a SVG representation.
        """
        # Compute x, y, width, height values
        self.x=self.cx - self.rx
        self.y=self.cy - self.ry
        self.width=2 * self.rx
        self.height=2 * self.ry

class Link(Shape):
    """Link pseudo-shape.

    Handles link attributes. Its parse_svg method will return the
    enclosed concrete shape, with link and link_label fields
    initialized with the appropriate values.
    """
    SHAPENAME=_("Link")
    SVGTAG='a'

    @classmethod
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
            logger.error("Invalid <a> content in SVG")
            return None
        o.link=element.attrib.get('xlink:href', element.attrib.get('{http://www.w3.org/1999/xlink}href', ''))
        o.link_label=element.attrib.get('title', 'Link to ' + o.link)
        #o.svg_attrib=dict(element.attrib)
        return o

    def get_svg(self, relative=False, size=None):
        """Return a SVG representation of the shape.

        @param relative: should dimensions be relative to the container size or absolute?
        @type relative: boolean
        @param size: the container size in pixels
        @type size: a couple of int
        @return: the SVG representation
        @rtype: elementtree.Element
        """
        logger.error("Should not happen (abstract method)...")
        yield None

class ShapeDrawer:
    """Widget allowing to draw and edit shapes.

    Note: the specified background image is not saved in the generated
    SVG. If it should be present in the output, it must be added
    (through add_object) as an Image object with the name 'background'.

    @ivar callback: method called when a shape is created
    @type callback: method taking an object (shape) as parameter

    @ivar background: the canvas background
    @type background: Gtk.Image
    @ivar objects: the list of defined objects
    @type objects: Gtk.ListStore
    @ivar selection: the rectangular selection coordinates
    @type selection: a list of 2 lists
    @ivar feedback_shape: the currently edited shape, displayed as feedback
    @type feedback_shape: Shape
    @ivar shape_class: the default shape class to be created
    @ivar default_color: the default color for created shapes
    @type default_color: string

    @ivar mode: the current editing mode ("", "create", "resize" or "translate")
    @type mode: string

    @ivar surface: the cached surface
    @type surface: cairo.Surface

    @ivar canvaswidth, canvasheight: the canvas dimensions
    @type canvaswidth, canvasheight: int

    @ivar widget: the gtk Widget for the component
    @type widget: Gtk.Widget

    """
    def __init__(self, callback=None, background=None, default_size=None):
        """
        @param callback: the callback method
        @param background: an optional background image
        @type background: GdkPixbuf.Pixbuf
        @param default_size: default size if it cannot be determined from background
        @type default_size: (w, h) tuple
        """
        self.callback = callback or self.default_callback

        # Couples object - name
        self.objects = Gtk.ListStore( object, str )
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
        self.shape_class = Path
        self.default_color = 'green'

        self.resize_cursor = Gdk.Cursor.new(Gdk.CursorType.HAND2)
        self.inside_cursor = Gdk.Cursor.new(Gdk.CursorType.FLEUR)

        self._svg_dimensions = None

        # mode: "create", "resize" or "translate"
        self.mode = ""

        self.surface = None

        self.widget = Gtk.DrawingArea()
        self.widget.connect('configure-event', self.configure_cb)
        self.widget.connect('draw', self.draw_cb)
        self.widget.connect('button-press-event', self.button_press_event)
        self.widget.connect('button-release-event', self.button_release_event)
        self.widget.connect('motion-notify-event', self.motion_notify_event)
        self.widget.set_events(Gdk.EventMask.EXPOSURE_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK | Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK
                               | Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.POINTER_MOTION_HINT_MASK | Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK )

        self.background=None
        if background:
            self.canvaswidth = background.get_width()
            self.canvasheight = background.get_height()
            if self.canvaswidth < 200 or self.canvasheight < 200:
                self.canvaswidth = 2 * self.canvaswidth
                self.canvasheight = 2 * self.canvasheight
            self.set_background(background)
        else:
            if default_size is not None:
                self.canvaswidth = default_size[0]
                self.canvasheight = default_size[1]
            else:
                # Use hardcoded values as last fallback
                self.canvaswidth = 320
                self.canvasheight = 200
        logger.debug("ShapeDrawer.set_size_request (%d, %d)", self.canvaswidth, self.canvasheight)
        self.widget.set_size_request(self.canvaswidth, self.canvasheight)

    def default_callback(self, shape):
        """Default callback.
        """
        logger.warning("Created shape %s", str(shape))

    def set_background(self, pixbuf, reset_dimensions=False):
        """Set a new background pixbuf.
        """
        w = pixbuf.get_width()
        h = pixbuf.get_height()
        logger.debug("set_background (%d, %d) Canvas: (%d, %d)", w, h, self.canvaswidth, self.canvasheight)
        if w != self.canvaswidth or h != self.canvasheight:
            # Mismatching dimensions. Do something.
            if reset_dimensions:
                # FIXME: if we have objects, we should scale them...
                if self.objects:
                    logger.warning("Resizing SVG editor with existing objects... Strange things will happen")
                self.canvaswidth = w
                self.canvasheight = h
                self.widget.set_size_request(self.canvaswidth, self.canvasheight)
            else:
                # Resize background pixbuf
                pixbuf = pixbuf.scale_simple(self.canvaswidth, self.canvasheight, GdkPixbuf.InterpType.BILINEAR)
        self.background = pixbuf
        self.plot()

    def add_object(self, o):
        """Add an object (shape) to the object list.
        """
        self.objects.append( (o, o.name) )
        self.callback(o)
        self.plot()

    def find_object(self, o):
        """Return the iterator for the given object.

        @param o: the searched object
        @return: the iterator
        @rtype: Gtk.Iterator
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

    def get_dimensions(self):
        """Return the canvas dimensions.

        @return: the dimensions in pixel
        @rtype: a couple (width, height)
        """
        return (self.canvaswidth, self.canvasheight)
    dimensions = property(get_dimensions)

    def get_svg_dimensions(self):
        """Return the SVG dimensions.

        In the case where a SVG has been loaded, its dimensions (width/height attributes) may be different from the canvas dimensions.

        @return: the dimensions in pixel @rtype: a couple (width,
        height)
        """
        if self._svg_dimensions:
            return self._svg_dimensions
        else:
            return self.dimensions
    def set_svg_dimensions(self, t):
        self._svg_dimensions = t
    svg_dimensions = property(get_svg_dimensions, set_svg_dimensions)

    def configure_cb(self, drawingarea, event=None):
        allocation = drawingarea.get_allocation()
        logger.debug("ShapeDrawer.configure_cb (%d,%d)", allocation.width, allocation.height)
        if self.surface is None and allocation.width != 1:
            self.surface = drawingarea.get_window().create_similar_surface(cairo.CONTENT_COLOR,
                                                                           allocation.width,
                                                                           allocation.height)
            self.plot()
            return True
        else:
            return False

    def draw_cb(self, drawingarea, context):
        context.set_source_surface(self.surface, 0, 0)
        context.paint()
        if self.feedback_shape is not None:
            self.feedback_shape.render(context)
        return True

    # Redraw the cached surface
    def draw_objects(self, context):
        if self.background:
            Gdk.cairo_set_source_pixbuf(context, self.background, 0, 0)
            context.paint()
        for o in self.objects:
            # o[0] may be None, if plot() is called from the callback
            # of a ListStore signal
            if o[0] is not None:
                o[0].render(context)
        return

    def clicked_shape(self, point):
        """Check if point is on a shape.
        """
        for o in self.objects:
            if point in o[0]:
                return o[0]
        return None

    def controlled_shape(self, point):
        """Check if point is on a shape control point.

        @return The shape and the control point information
        """
        for o in self.objects:
            c = o[0].control_point(point)
            if c:
                return o[0], c
        return None, None

    def is_editing(self):
        return self.feedback_shape is not None

    def cancel_editing(self):
        self.feedback_shape = None
        self.mode = ""
        self.plot()

    def add_menuitem(self, menu=None, item=None, action=None, *param, **kw):
        if item is None or item == "":
            i = Gtk.SeparatorMenuItem()
        else:
            i = Gtk.MenuItem(item)
        if action is not None:
            i.connect('activate', action, *param, **kw)
        menu.append(i)

    def popup_menu(self, shape):
        menu = Gtk.Menu()

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
                    self.objects.set_value(i, 1, o.name or o.SHAPENAME)

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
        menu.popup_at_pointer(None)

        return True

    # Start marking selection
    def button_press_event(self, widget, event):
        point = (int(event.x), int(event.y))
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            if self.feedback_shape and self.feedback_shape.MULTIPOINT and self.mode == 'create':
                # Validate the shape
                self.feedback_shape.validate()
                self.add_object(self.feedback_shape)
                self.feedback_shape = None
                self.plot()
            else:
                # Double-click. Open properties for the shape.
                sel = self.clicked_shape( point )
                if sel is not None and sel.edit_properties():
                    self.plot()
                    # Update liststore
                    i = self.find_object(sel)
                    if i is not None:
                        self.objects.set_value(i, 1, sel.name or self.SHAPENAME)
                self.feedback_shape = None
            return True
        elif event.button == 1:
            self.selection[0][0], self.selection[0][1] = point
            self.selection[1][0], self.selection[1][1] = None, None

            if self.feedback_shape and self.feedback_shape.MULTIPOINT and self.mode == 'create':
                # Multipoint shape editing: add a  new point
                self.feedback_shape.add_point( point )
                self.plot()
                return

            sel, c = self.controlled_shape( point )
            if sel is not None:
                # Existing shape controlled
                self.feedback_shape = sel
                self.selection = c
                if self.feedback_shape.MULTIPOINT:
                    self.feedback_shape.set_controlled_point(point=c[1])
                self.mode = "resize"
            else:
                sel = self.clicked_shape( point )
                if sel is not None:
                    self.feedback_shape = sel
                    self.mode = "translate"
                else:
                    self.feedback_shape = self.shape_class(color=self.default_color,
                                                           dimensions=(point, point))
                    self.mode = "create"
        elif event.button == 3:
            if self.feedback_shape and self.mode == 'create' and self.feedback_shape.MULTIPOINT:
                self.feedback_shape.remove_controlled_point()
                self.plot()
            else:
                if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                    sel, c = self.controlled_shape( point )
                    if sel is not None:
                        # Right click on a control point - remove it
                        sel.set_controlled_point(point=c)
                        sel.remove_controlled_point()
                        self.plot()
                else:
                    # Popup menu
                    sel = self.clicked_shape( point )
                    if sel is not None:
                        self.popup_menu(sel)
        return True

    # End of selection
    def button_release_event(self, widget, event):
        if self.mode in ('resize', 'translate'):
            self.mode = ''

        if event.button == 1:
            if self.feedback_shape is not None:
                if self.feedback_shape.MULTIPOINT and self.mode == 'create':
                    # Multipoint shape: we do not reset it now, we
                    # simply will validate the point upon next press
                    return

                if self.mode == "create":
                    # Create the shape and add it to the stack
                    r = self.feedback_shape
                    self.add_object(r)

                self.feedback_shape = None
                self.plot()

            self.selection[1][0] = None
            self.selection[0][0] = None


    # Draw rectangle during mouse movement
    def motion_notify_event(self, widget, event):
        if event.is_hint:
            pointer = event.get_window().get_pointer()
            x = pointer[1]
            y = pointer[2]
        else:
            x = event.x
            y = event.y

        if self.feedback_shape is not None:
            self.selection[1][0], self.selection[1][1] = int(x), int(y)

            oldbounds = self.feedback_shape.get_bounds()

            if self.mode == "translate":
                self.feedback_shape.translate( (x - self.selection[0][0],
                                                y - self.selection[0][1] ) )
                self.selection[0][0] = x
                self.selection[0][1] = y
            elif self.mode == "resize" or self.mode == "create":
                self.feedback_shape.set_bounds( self.selection )

            bounds = self.feedback_shape.get_bounds()
            minx = sys.maxsize
            miny = sys.maxsize
            maxx = 0
            maxy = 0
            for limits in (oldbounds, bounds):
                minx = min( (limits[0][0], limits[1][0], minx) )
                miny = min( (limits[0][1], limits[1][1], miny) )
                maxx = max( (limits[0][0], limits[1][0], maxx) )
                maxy = max( (limits[0][1], limits[1][1], maxx) )
            widget.queue_draw_area(minx - 1, miny - 1, maxx - minx + 2, maxy - miny + 2)
        else:
            # Check for control points
            cursor = None
            point = (x, y)
            for o in self.objects:
                if o[0].control_point( point ):
                    cursor = self.resize_cursor
                    break
                if point in o[0]:
                    cursor = self.inside_cursor
                    break
            self.widget.get_window().set_cursor(cursor)

    def plot(self):
        """Draw in the cached surface
        """
        if self.surface:
            context = cairo.Context(self.surface)
            self.draw_objects(context)
        self.widget.queue_draw()
        return

    def get_svg(self, relative=False):
        """Return a SVG representation.
        """
        size=self.dimensions
        ET._namespace_map['http://www.w3.org/1999/xlink']='xlink'
        ET._namespace_map['http://www.w3.org/2000/svg']='svg'
        root=ET.Element(ET.QName(SVGNS, 'svg'), {
            'version': '1',
            'preserveAspectRatio': "xMinYMin meet" ,
            'viewBox': '0 0 %d %d' % size,
            'width': "%d" % size[0],
            'height': "%d" % size[1],
            'xmlns:xlink': "http://www.w3.org/1999/xlink",
            # The following xmlns declaration is needed for a
            # correct rendering in firefox
            'xmlns': "http://www.w3.org/2000/svg",
        })
        bg=[ o[0] for o in self.objects if isinstance(o, Image) and o.name == 'background' ]
        if bg:
            # There is a background. Put it first.
            bg=bg[0]
            # Force the background image dimension
            bg.x=0
            bg.y=0
            # The background image has presumably been rendered. Get
            # its dimensions.
            if hasattr(bg, '_pixbuf'):
                bg.width=bg._pixbuf.get_width()
                bg.height=bg._pixbuf.get_height()
            for e in bg.get_svg(relative=relative, size=size):
                root.append(e)
        else:
            bg=None
        for o in self.objects:
            if o == bg:
                # The background already has been added
                continue
            for e in o[0].get_svg(relative=relative, size=size):
                root.append(e)
        ET_indent(root)
        return root

    def convert_unit(self, s, dimindex=0):
        """Convert a unit.

        dimindex is the index of the unit in the .dimensions tuple: 0
        for width, 1 for height.
        """
        m=re.match(r'(\d+)(\w*)', s)
        if m:
            val=int(m.group(1))
            unit=m.group(2)
            if unit in ('px', 'pt', ''):
                return val
            elif unit == '%':
                return int(val * 100.0 / self.dimensions[dimindex])
            else:
                logger.warning('SVG: Unknown unit for %s', s)
                return val
        logger.warning('Unhandled SVG dimension format for %s', s)
        return 0

    def parse_svg(self, et, current_path=''):
        """Parse a SVG representation

        et is an ET.Element with tag == 'svg'

        path is the file path of the parsed element (so that relative
        hrefs can be resolved)
        """
        if et.tag != 'svg' and et.tag != ET.QName(SVGNS, 'svg'):
            logger.error("Not a svg file (root tag: %s)", et.tag)
            return False
        w=et.attrib.get('width')
        h=et.attrib.get('height')
        if w is not None and h is not None:
            self.svg_dimensions = (self.convert_unit(w, 0),
                                   self.convert_unit(h, 0))
        for c in et:
            for clazz in defined_shape_classes:
                o=clazz.parse_svg(c, self)
                if o is not None:
                    if isinstance(o, Image) and o.name == 'background':
                        # We have a background image.
                        if o.uri.startswith('http:'):
                            # http url, download the file
                            (fname, header)=urllib.request.urlretrieve(o.uri)
                            i=Gtk.Image()
                            logger.warning("Loaded background from %s copy in %s", o.uri, fname)
                            i.set_from_file(fname)
                        else:
                            # Consider it as local.
                            if current_path and not os.path.exists(o.uri):
                                # The file does not exist. Try to
                                # prepend the context path.
                                uri=os.path.join( current_path, o.uri)
                            else:
                                uri=o.uri
                            i=Gtk.Image()
                            i.set_from_file(uri)
                            if i.get_storage_type() != Gtk.ImageType.PIXBUF:
                                p=GdkPixbuf.Pixbuf(GdkPixbuf.Colorspace.RGB,
                                                   True, 8, o.width, o.height)
                                p.fill(0xdeadbeaf)
                                i.set_from_pixbuf(p)
                            logger.warning("Loaded background from %s", uri)
                        p=i.get_pixbuf()
                        # We insert the background at the beginning of
                        # the object stack, so that other shapes are
                        # drawn over it.
                        self.set_background(p, reset_dimensions=True)
                        self.objects.insert(0, (o, o.name))
                        # Update the size of the shape and the widget
                        o._pixbuf=self.background
                        o.x=0
                        o.y=0
                        o.width=self.background.get_width()
                        o.height=self.background.get_height()
                    else:
                        self.objects.append( (o, o.name) )
                    break
        self.plot()
        return True

class ShapeEditor:
    """Shape Editor component.

    This component provides an example of using ShapeWidget.
    """
    def __init__(self, background=None, icon_dir=None, default_size=None):
        if isinstance(background, Gtk.Image):
            background = background.get_pixbuf()
        self.drawer = ShapeDrawer(background=background, default_size=default_size)
        self.shapes = [ Rectangle, Ellipse, Line, Text, Path ]

        self.colors = COLORS
        self.drawer.default_color = self.colors[0]

        self.key_mapping={
            Gdk.KEY_l: Line,
            Gdk.KEY_r: Rectangle,
            Gdk.KEY_t: Text,
            Gdk.KEY_c: Ellipse,
            Gdk.KEY_p: Path,
            #Gdk.KEY_i: Image,
            }

        self.icon_name={
            Rectangle: 'shape_rectangle.png',
            Line: 'shape_arrow.png',
            Text: 'shape_text.png',
            Ellipse: 'shape_ellipse.png',
            Image: 'shape_image.png',
            Path: 'shape_path.png',
            }
        self.widget=self.build_widget(icon_dir)
        self.widget.connect('key-press-event', self.key_press_event)

    def key_press_event(self, widget, event):
        cl = self.key_mapping.get(event.keyval, None)
        if event.keyval == Gdk.KEY_Escape and self.drawer.is_editing():
            self.drawer.cancel_editing()
            return True
        elif isinstance(cl, type) and issubclass(cl, Shape):
            # Select the appropriate shape
            self.shape_icon.set_shape(cl)
            self.drawer.shape_class = cl
            return True
        elif callable(cl):
            cl(widget, event)
            return True
        elif event.keyval == Gdk.KEY_Delete:
            s = self.get_selected_node(self.treeview)
            if s is not None:
                self.drawer.remove_object(s)
            return True
        return False

    def remove_item(self, treeview, path, column):
        m=treeview.get_model()
        o=treeview.get_model()[m.get_iter(path)][0]
        self.drawer.remove_object(o)
        return True

    def build_selector(self, items, callback):
        sel = Gtk.ComboBoxText()
        for s in items:
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
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            node = self.get_selected_node (widget)
            if node is not None:
                if node.edit_properties():
                    self.drawer.plot()
                    # Update liststore
                    i = self.drawer.find_object(node)
                    if i is not None:
                        self.drawer.objects.set_value(i, 1, node.name or node.SHAPENAME)
                retval=True
            else:
                retval=False
        elif button == 3:
            if event.get_window() is widget.get_bin_window():
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

    def set_background(self, image):
        """Set the background image.
        """
        if isinstance(image, Gtk.Image):
            self.drawer.set_background(image.get_pixbuf())
        elif isinstance(image, GdkPixbuf.Pixbuf):
            self.drawer.set_background(image)
        else:
            raise Exception("set_background requires a Gtk.Image or a GdkPixbuf.Pixbuf")

    def build_widget(self, icon_dir):
        vbox=Gtk.VBox()

        tb = self.toolbar = Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        vbox.pack_start(tb, False, True, 0)

        hbox=Gtk.HBox()

        vbox.add(hbox)

        hbox.pack_start(self.drawer.widget, False, False, 16)
        self.drawer.widget.connect('key-press-event', self.key_press_event)

        self.treeview = Gtk.TreeView(self.drawer.objects)
        self.treeview.set_reorderable(True)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Name', renderer,
                                    text=1)
        self.treeview.append_column(column)
        self.treeview.connect('button-press-event', self.tree_view_button_cb)

        def set_shape(tb, shape):
            """Update the toolbutton with the appropriate shape information.
            """
            if icon_dir is not None and self.icon_name.get(shape, None):
                i=Gtk.Image()
                i.set_from_file( os.path.join( icon_dir, self.icon_name.get(shape, None)) )
                i.show()
                tb.set_icon_widget(i)
            else:
                tb.set_label(shape.SHAPENAME)
            tb.set_tooltip_text(shape.SHAPENAME)
            tb._shape=shape
            return True

        def select_shape(button, shape):
            self.shape_icon.set_shape(shape)
            self.drawer.shape_class=shape
            button.get_toplevel().destroy()
            return True

        def display_shape_menu(tb):
            bar=Gtk.Toolbar()
            bar.set_orientation(Gtk.Orientation.VERTICAL)
            bar.set_style(Gtk.ToolbarStyle.ICONS)

            for shape in self.shapes:
                i=Gtk.ToolButton()
                i.set_visible_horizontal(True)
                i.set_visible_vertical(True)
                set_shape(i, shape)
                i.connect('clicked', select_shape, shape)
                bar.insert(i, -1)

            w=Gtk.Window(type=Gtk.WindowType.POPUP)
            w.add(bar)
            w.set_transient_for(tb.get_toplevel())
            w.set_type_hint(Gdk.WindowTypeHint.TOOLBAR)
            w.set_modal(True)
            w.move(*tb.translate_coordinates(tb.get_toplevel(), 0, 0))
            w.show_all()
            def button_press_event(wid, event):
                wid.destroy()
                return False
            w.connect('button-press-event', button_press_event)

            return True

        self.shape_icon=Gtk.ToolButton()
        self.shape_icon.set_shape=set_shape.__get__(self.shape_icon)
        self.shape_icon.set_shape(self.drawer.shape_class)
        self.shape_icon.connect('clicked', display_shape_menu)
        tb.insert(self.shape_icon, -1)


        def set_color(tb, color):
            """Update the toolbutton with the appropriate color information.
            """
            tb.get_icon_widget().set_markup('<span background="%s">    </span>' % color)
            tb.set_tooltip_text(color)
            tb._color=color
            return True

        def select_color(button, color):
            self.color_icon.set_color(color)
            self.drawer.default_color=color
            button.get_toplevel().destroy()
            return True

        def display_color_menu(tb):
            bar=Gtk.Toolbar()
            bar.set_orientation(Gtk.Orientation.VERTICAL)
            bar.set_style(Gtk.ToolbarStyle.ICONS)

            for color in self.colors:
                i=Gtk.ToolButton(icon_widget=Gtk.Label())
                i.set_visible_horizontal(True)
                i.set_visible_vertical(True)
                set_color(i, color)
                i.connect('clicked', select_color, color)
                bar.insert(i, -1)

            w=Gtk.Window(type=Gtk.WindowType.POPUP)
            w.add(bar)
            w.set_transient_for(tb.get_toplevel())
            w.set_type_hint(Gdk.WindowTypeHint.TOOLBAR)
            w.set_modal(True)
            bar.show_all()
            w.move(*tb.translate_coordinates(tb.get_toplevel(), 0, 0))
            w.show_all()
            def button_press_event(wid, event):
                wid.destroy()
                return False
            w.connect('button-press-event', button_press_event)

            return True

        self.color_icon=Gtk.ToolButton(icon_widget=Gtk.Label())
        self.color_icon.set_color=set_color.__get__(self.color_icon)
        self.color_icon.set_color('red')
        self.color_icon.connect('clicked', display_color_menu)
        tb.insert(self.color_icon, -1)

        def load_svg(b):
            fs=Gtk.FileChooserDialog(title='Select a svg file',
                                     buttons=(Gtk.STOCK_OK, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
            res=fs.run()
            if res == Gtk.ResponseType.OK:
                name=fs.get_filename()
                root=ET.parse(name).getroot()
                self.drawer.parse_svg(root)
            fs.destroy()
            return True

        def save_svg(b):
            fs=Gtk.FileChooserDialog(title='Select a svg file to write to',
                                     action=Gtk.FileChooserAction.SAVE,
                                     buttons=(Gtk.STOCK_OK, Gtk.ResponseType.OK, Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL))
            res=fs.run()
            if res == Gtk.ResponseType.OK:
                name = fs.get_filename()
                tree = ET.ElementTree(self.drawer.get_svg(relative=False))
                f = open(name, 'w', encoding='utf-8')
                tree.write(f, encoding='unicode')
                f.close()
            fs.destroy()
            return True

        tb.insert(Gtk.SeparatorToolItem(), -1)

        b=Gtk.ToolButton(Gtk.STOCK_OPEN)
        b.set_tooltip_text(_("Load SVG"))
        b.connect('clicked', load_svg)
        tb.insert(b, -1)

        if True:
            b=Gtk.ToolButton(Gtk.STOCK_SAVE)
            b.set_tooltip_text(_("Save SVG"))
            b.connect('clicked', save_svg)
            tb.insert(b, -1)

        control = Gtk.VBox()
        control.pack_start(self.treeview, False, True, 0)
        hbox.pack_start(control, False, True, 0)

        vbox.show_all()

        return vbox

def main():
    if len(sys.argv) > 1:
        bg = sys.argv[1]
    else:
        bg = 'atelier.jpg'

    win = Gtk.Window(Gtk.WindowType.TOPLEVEL)
    win.set_title("Shape Editor test")
    #win.set_default_size(800, 600)
    win.connect('delete-event', lambda w, e: Gtk.main_quit())

    if bg.endswith('.svg'):
        ed=ShapeEditor()
        root=ET.parse(bg).getroot()
        ed.drawer.parse_svg(root)
    else:
        i=Gtk.Image()
        i.set_from_file(bg)
        ed=ShapeEditor(background=i)
        ed.drawer.add_object(Image(name='background', uri=os.path.basename(bg)))
    win.add(ed.widget)

    ed.key_mapping[Gdk.KEY_q]=lambda w, e: Gtk.main_quit()
    ed.key_mapping[Gdk.KEY_d]=lambda w, e: ET.dump(ed.drawer.get_svg())
    try:
        from evaluator import Evaluator
        ed.key_mapping[Gdk.KEY_e]=lambda w, e: Evaluator(locals_={'ed': ed}).popup()
    except ImportError:
        pass

    win.show_all()

    Gtk.main()

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
    logging.basicConfig(level=logging.DEBUG)
    main()
