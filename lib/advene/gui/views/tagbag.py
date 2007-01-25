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
"""Tag bag
"""

# Advene part
import advene.core.config as config
from advene.gui.views import AdhocView
import advene.gui.util

from gettext import gettext as _

import gtk

class TagBag(AdhocView):
    def __init__(self, controller=None, parameters=None, tags=None):
        self.view_name = _("Tag Bag")
        self.view_id = 'tagbagview'
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("New tag"), self.new_tag),
            (_("Clear"), self.clear),
            (_("Save view"), self.save_view),
            )
        self.options={}
        self.controller=controller

        if parameters:
            opt, arg = self.load_parameters()
            self.options.update(opt)
            l=[ v for (n, v) in arg if n == 'tag' ]
            if l:
                tags=l
        self.tags=tags

        self.mainbox=None
        self.widget=self.build_widget()
        self.refresh()

    def clear(self, *p):
        del self.tags[:]
        self.refresh()

    def new_tag(self, *p):
        """Enter a new tag.
        """
        tag=advene.gui.util.entry_dialog(title=_("New tag name"),
                                         text=_("Enter a new tag name"))
        if tag and not tag in self.tags:
            self.tags.append(tag)
            self.refresh()
        return True

    def get_save_arguments(self):
        arguments = [ ('tag', t) for t in self.tags ]
        return self.options, arguments
        
    def refresh(self, *p):
        self.mainbox.foreach(self.mainbox.remove)
        for p in self.tags:
            self.append_repr(p)
        self.mainbox.show_all()
        return True

    def append_repr(self, t):
        def drag_sent(widget, context, selection, targetType, eventTime):
            if targetType == config.data.target_type['tag']:
                selection.set(selection.target, 8, unicode(t))
            else:
                self.log("Unknown target type for drag: %d" % targetType)
            return True

        b=gtk.Button(t)
        #b.connect("clicked", self.activate, t)
        # The button can generate drags
        b.connect("drag_data_get", drag_sent)

        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['tag'],
                          gtk.gdk.ACTION_LINK)

        self.mainbox.pack_start(b, expand=False)

    def build_widget(self):
        v=gtk.VBox()

        mainbox=gtk.VBox()
        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(mainbox)
        self.mainbox=mainbox

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation']:
                a=self.controller.package.annotations.get(selection.data)
                for tag in a.tags:
                    if not tag in self.tags:
                        self.tags.append(tag)
                self.refresh()
            elif targetType == config.data.target_type['tag']:
                tags=selection.data.split(',')
                for tag in tags:
                    if not tag in self.tags:
                        self.tags.append(tag)
                self.refresh()
            else:
                self.log("Unknown target type for mainbox drop: %d" % targetType)
            return True

        self.mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation']
                                  + config.data.drag_type['tag']
                                   , gtk.gdk.ACTION_LINK)
        self.mainbox.connect("drag_data_received", mainbox_drag_received)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['tag']:
                tag=selection.data
                if tag in self.tags:
                    self.tags.remove(tag)
                self.refresh()
            else:
                self.log("Unknown target type for remove drop: %d" % targetType)
            return True

        v.add(sw)

        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        self.controller.gui.tooltips.set_tip(b, _("Drop a tag here to remove it from the list"))
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['tag'], gtk.gdk.ACTION_LINK)
        b.connect("drag_data_received", remove_drag_received)
        v.pack_start(b, expand=False)

        return v
