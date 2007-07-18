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

from gettext import gettext as _

import gtk

from advene.gui.edit.elements import ContentHandler
from advene.gui.edit.shapewidget import ShapeDrawer, Rectangle
from advene.gui.util import image_from_position, dialog
from advene.gui.edit.rules import EditRuleSet, EditQuery
from advene.rules.elements import RuleSet, Query

name="Default content handlers"

def register(controller=None):
    for c in ZoneContentHandler, RuleSetContentHandler, SimpleQueryContentHandler:
        controller.register_content_handler(c)

class ZoneContentHandler (ContentHandler):
    """Create a zone edit form for the given element."""
    def can_handle(mimetype):
        res=0
        if mimetype == 'application/x-advene-zone':
            res=80
        return res
    can_handle=staticmethod(can_handle)

    def __init__ (self, element, controller=None, parent=None, **kw):
        self.element = element
        self.controller=controller
        self.parent=parent
        self.editable = True
        self.fname=None
        self.view = None
        self.shape = None
        self.tooltips=gtk.Tooltips()

    def set_editable (self, boolean):
        self.editable = boolean

    def callback(self, l):
        if l[0][0] is None or l[1][0] is None:
            self.shape = None
            self.view.plot()
            return

        if self.shape is None:
            r = Rectangle()
            r.name = "Selection"
            r.color = "green"
            r.set_bounds(l)
            self.view.add_object(r)
            self.shape=r
        else:
            self.shape.set_bounds(l)
            self.view.plot()
        return

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False
        if self.shape is None:
            return True

        if not self.shape:
            return True

        shape=self.shape
        shape.name=self.nameentry.get_text()
        text="""shape=rect\nname=%s\nx=%02f\ny=%02f\nwidth=%02f\nheight=%02f""" % (
            shape.name,
            shape.x * 100.0 / self.view.canvaswidth,
            shape.y * 100.0 / self.view.canvasheight,
            shape.width * 100.0 / self.view.canvaswidth,
            shape.height * 100.0 / self.view.canvasheight)

        self.element.data = text
        return True

    def get_view (self, compact=False):
        """Generate a view widget for editing zone attributes."""
        vbox=gtk.VBox()

        if self.parent is not None and hasattr(self.parent, 'fragment'):
            i=image_from_position(self.controller, self.parent.fragment.begin, height=160)
            self.view = ShapeDrawer(callback=self.callback, background=i)
        else:
            self.view = ShapeDrawer(callback=self.callback)

        if self.element.data:
            d=self.element.parsed()
            if isinstance(d, dict):
                try:
                    x = int(float(d['x']) * self.view.canvaswidth / 100)
                    y = int(float(d['y']) * self.view.canvasheight / 100)
                    width = int(float(d['width']) * self.view.canvaswidth / 100)
                    height = int(float(d['height']) * self.view.canvasheight / 100)
                    self.callback( ( (x, y),
                                     (x+width, y+height) ) )
                    self.shape.name = d['name']
                except KeyError:
                    self.callback( ( (0.0, 0.0),
                                     (10.0, 10.0) ) )
                    self.shape.name = self.element.data

        # Name edition
        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Label")), expand=False)
        self.nameentry=gtk.Entry()
        if self.shape is not None:
            self.nameentry.set_text(self.shape.name)
        hb.pack_start(self.nameentry)

        vbox.pack_start(hb, expand=False)

        vbox.add(self.view.widget)

        return vbox


class RuleSetContentHandler (ContentHandler):
    """Create a RuleSet edit form for the given element (a view, presumably).
    """
    def can_handle(mimetype):
        res=0
        if mimetype == 'application/x-advene-ruleset':
            res=80
        return res
    can_handle=staticmethod(can_handle)

    def __init__ (self, element, controller=None, parent=None, **kw):
        self.element = element
        self.controller=controller
        self.parent=parent
        self.editable = True
        self.view = None

    def set_editable (self, boolean):
        self.editable = boolean

    def check_validity(self):
        iv=self.edit.invalid_items()
        if iv:
            dialog.message_dialog(
                _("The following items seem to be\ninvalid TALES expressions:\n\n%s") %
                "\n".join(iv),
                icon=gtk.MESSAGE_ERROR)
            return False
        else:
            return True


    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False
        if not self.edit.update_value():
            return False
        self.element.data = self.edit.model.xml_repr()
        return True

    def get_view (self, compact=False):
        """Generate a view widget to edit the ruleset."""
        rs=RuleSet()
        rs.from_dom(catalog=self.controller.event_handler.catalog,
                    domelement=self.element.model)

        self.edit=EditRuleSet(rs,
                              catalog=self.controller.event_handler.catalog,
                              editable=self.editable,
                              controller=self.controller)
        self.view = self.edit.get_packed_widget()

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_win.add_with_viewport(self.view)

        return scroll_win

class SimpleQueryContentHandler (ContentHandler):
    """Create a Query edit form for the given element (a view, presumably).
    """
    def can_handle(mimetype):
        res=0
        if mimetype == 'application/x-advene-simplequery':
            res=80
        return res
    can_handle=staticmethod(can_handle)

    def __init__ (self, element, controller=None, parent=None, editable=True, **kw):
        self.element = element
        self.controller=controller
        self.parent=parent
        self.editable = editable
        self.view = None

    def check_validity(self):
        iv=self.edit.invalid_items()
        if iv:
            dialog.message_dialog(
                _("The following items seem to be\ninvalid TALES expressions:\n\n%s") %
                "\n".join(iv),
                icon=gtk.MESSAGE_ERROR)
            return False
        else:
            return True

    def set_editable (self, boo):
        self.editable = boo

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False
        if not self.edit.update_value():
            return False
        self.element.data = self.edit.model.xml_repr()
        # Just to be sure:
        self.element.mimetype = 'application/x-advene-simplequery'
        return True

    def get_view (self, compact=False):
        """Generate a view widget to edit the ruleset."""
        q=Query()
        q.from_dom(domelement=self.element.model)

        self.edit=EditQuery(q,
                            controller=self.controller,
                            editable=self.editable)
        self.view = self.edit.get_widget()

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_win.add_with_viewport(self.view)

        return scroll_win
