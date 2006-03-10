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
"""Notebook containing multiple views
"""

import advene.core.config as config

import gtk
import gobject
import pango

from gettext import gettext as _

class ViewBook:
    """Notebook containing multiple views
    """
    def __init__ (self, controller=None, views=None):
        self.view_name = _("ViewBook")
	if views is None:
	    views = []
	self.views=[]
        self.widget=self.build_widget()
	for v in views:
	    self.add_view(v, v.view_name)

    def add_view(self, v, name=None):
	"""Add a new view to the notebook.

	Each view is an Advene view, and must have a .widget attribute
	"""
	if name is None:
	    try:
		name=v.view_name
	    except AttributeError:
		name="FIXME"
	self.views.append(v)
        l=gtk.Label(name)
        self.widget.append_page(v.widget, l)
	v.widget.show_all()
	return True
	
    def build_widget(self):
        notebook=gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_BOTTOM)
        notebook.popup_enable()
        notebook.set_scrollable(True)
        return notebook

    def popup(self):
	w = gtk.Window(gtk.WINDOW_TOPLEVEL)
	w.set_title (_("View Book"))

	v=gtk.VBox()
	
	v.add(self.widget)
	b=gtk.Button(stock=gtk.STOCK_CLOSE)
	b.connect("clicked", lambda b: w.destroy())
	v.pack_start(b, expand=False)
	
	w.add(v)
        w.show_all()

        return w
