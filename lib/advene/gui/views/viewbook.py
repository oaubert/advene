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
from advene.gui.views import AdhocView

class ViewBook(AdhocView):
    """Notebook containing multiple views
    """
    def __init__ (self, controller=None, views=None):
        self.view_name = _("ViewBook")
	self.view_id = 'viewbook'

	self.controller=controller
	if views is None:
	    views = []
	self.views=[]

	# List of widgets that cannot be removed
	self.permanent_widgets = []

        self.widget=self.build_widget()
	for v in views:
	    self.add_view(v, v.view_name)

    def remove_view(self, view):
	if view in self.permanent_widgets:
	    self.controller.log(_("Cannot remove this widget, it is essential."))
	    return False
	view.close()
	return True
	    
    def add_view(self, v, name=None, permanent=False):
	"""Add a new view to the notebook.

	Each view is an Advene view, and must have a .widget attribute
	"""
	if name is None:
	    try:
		name=v.view_name
	    except AttributeError:
		name="FIXME"
	self.controller.gui.register_view (v)
	self.views.append(v)
	if permanent:
	    self.permanent_widgets.append(v)

	def close_view(item, view):
	    self.remove_view(view)
	    return True

	def popup_menu(button, event, view):
	    if event.button == 3:
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Close"))
		item.connect("activate", close_view, view)
		menu.append(item)

                try:
                    for label, action in view.contextual_actions:
                        item = gtk.MenuItem(label)
                        item.connect("activate", action, view)
                        menu.append(item)
                except AttributeError:
                    pass

		menu.show_all()
		menu.popup(None, None, None, 0, gtk.get_current_event_time())
		return True
	    return False

	e=gtk.EventBox()
        l=gtk.Label(name)
	e.add(l)
	e.connect("button_press_event", popup_menu, v)
	e.show_all()
        self.widget.append_page(v.widget, e)
	v.widget.show_all()

	num=self.widget.page_num(v.widget)
	self.widget.set_current_page(num)

	return True
	
    def drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['adhoc-view']:
            name=selection.data
	    if self.controller.gui:
		view=self.controller.gui.open_adhoc_view(name, popup=False)
		if view is not None:
		    self.add_view(view)
		else:
		    print "Cannot open", name
	    return True
        return True

    def build_widget(self):
        notebook=gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_BOTTOM)
        notebook.popup_enable()
        notebook.set_scrollable(True)

        notebook.connect("drag_data_received", self.drag_received)
        notebook.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                               gtk.DEST_DEFAULT_HIGHLIGHT |
			       gtk.DEST_DEFAULT_DROP |
                               gtk.DEST_DEFAULT_ALL,
                               config.data.drag_type['adhoc-view'],
                               gtk.gdk.ACTION_COPY)

        return notebook
