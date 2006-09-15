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
"""Edit Accumulator.

This widget allows to stack compact editing widgets.
"""

import gtk

from gettext import gettext as _

import advene.core.config as config
from advene.gui.views.accumulatorpopup import AccumulatorPopup
from advene.gui.edit.elements import EditFragmentForm, get_edit_popup

class EditAccumulator(AccumulatorPopup):
    """View displaying a limited number of compact editing widgets.
    """
    def __init__ (self, *p, **kw):
        kw['vertical']=True
        super(EditAccumulator, self).__init__(self, *p, **kw)
        self.view_name = _("EditAccumulator")
	self.view_id = 'editaccumulator'
	self.close_on_package_load = False
        
    def edit(self, element):
        e=get_edit_popup(element, self.controller)
        w=e.compact()
        self.display(w, title=self.controller.get_title(element))

    def update_position(self, pos):
        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['annotation']:
            source_uri=selection.data
            source=self.controller.package.annotations.get(source_uri)
            self.edit(source)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def build_widget(self):
        mainbox=super(EditAccumulator, self).build_widget()

        # The widget can receive drops from annotations
        mainbox.connect("drag_data_received", self.drag_received)
        mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
				  gtk.DEST_DEFAULT_HIGHLIGHT |
				  gtk.DEST_DEFAULT_ALL,
				  config.data.drag_type['annotation'], gtk.gdk.ACTION_LINK)

        return mainbox
