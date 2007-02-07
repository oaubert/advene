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
"""Tag bag view
============

Note: this adhoc view is also used in element edit popups.

This view presents a number of tags to the user, so that she can apply
them to various elements by drag and drop.

Dragging a tag to an annotation with add the tag to the annotation's tag.

Dragging an annotation to the tag bag will add the annotation tags to
the presented list of tags.
"""

# Advene part
import advene.core.config as config
from advene.gui.views import AdhocView
import advene.gui.util

from gettext import gettext as _

import re
import gtk

class TagBag(AdhocView):
    def __init__(self, controller=None, parameters=None, tags=None, vertical=True):
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
        self.vertical=vertical

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

    def tag_update(self, context, parameters):
        tag=context.evaluateValue('tag')
        # Is there an associated color ?
        try:
            col=self.controller.package._tag_colors[tag]
        except KeyError:
            return True

        l=[ b for b in self.mainbox.get_children() if b.get_label() == tag ]
        for b in l:
            self.set_widget_color(b, col)
        return True

    def register_callback (self, controller=None):
        """Add the activate handler for annotations.
        """
        self.callback=controller.event_handler.internal_rule (event="TagUpdate",
                                                              method=self.tag_update)
        return True

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.callback, type_="internal")
        return True

    def new_tag(self, *p):
        """Enter a new tag.
        """
        tag=advene.gui.util.entry_dialog(title=_("New tag name"),
                                         text=_("Enter a new tag name"))
        if tag and not tag in self.tags:
            if not re.match('^[\w\d_]+$', tag):
                advene.gui.util.message_dialog(_("The tag contains invalid characters"),
                                               icon=gtk.MESSAGE_ERROR)
                return True            
            self.tags.append(tag)
            self.controller.notify('TagUpdate', tag=tag)
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

    def set_widget_color(self, widget, color):
        if isinstance(color, basestring):
            color=gtk.gdk.color_parse (color)
            
        for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            widget.modify_bg (style, color)
        return True

    def append_repr(self, t):
        def drag_sent(widget, context, selection, targetType, eventTime):
            if targetType == config.data.target_type['tag']:
                selection.set(selection.target, 8, unicode(t))
            else:
                self.log("Unknown target type for drag: %d" % targetType)
            return True

        b=gtk.Button(t)
        
        try:
            col=self.controller.package._tag_colors[t]
            self.set_widget_color(b, col)
        except KeyError:
            pass

        # The button can generate drags
        b.connect("drag_data_get", drag_sent)

        def remove(widget, tag):
            if tag in self.tags:
                self.tags.remove(tag)
                try:
                    del self.controller.package._tag_colors[tag]
                except KeyError:
                    pass
                self.controller.notify('TagUpdate', tag=tag)
                self.refresh()
            return True

        def set_color(widget, tag):
            d=gtk.ColorSelectionDialog(_("Choose the color for tag %s") % tag)
            try:
                col=self.controller.package._tag_colors[tag]
                d.colorsel.set_current_color(gtk.gdk.color_parse(col))
            except:
                pass

            res=d.run()
            if res == gtk.RESPONSE_OK:
                col=d.colorsel.get_current_color()
                self.controller.package._tag_colors[tag]="#%04x%04x%04x" % (col.red, col.green, col.blue)
                self.controller.notify('TagUpdate', tag=tag)
                # The color setting of the widget is done in the callback for TagUpdate
            d.destroy()
            return True

        def popup_menu(widget, event):
            if not (event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS):
                return False

            menu=gtk.Menu()

            for label, action in ( 
                (_("Set color"), set_color),
                (_("Remove"), remove)
                ):
                item = gtk.MenuItem(label)
                item.connect("activate", action, t)
                menu.append(item)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True

        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['tag'],
                          gtk.gdk.ACTION_LINK)

        b.connect("button_press_event", popup_menu)
        self.mainbox.pack_start(b, expand=False)

    def build_widget(self):
        
        if self.vertical:
            v=gtk.VBox()
            mainbox=gtk.VBox()
        else:
            v=gtk.HBox()
            mainbox=gtk.HBox()

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

        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", self.new_tag)
        v.pack_start(b, expand=False)

        return v
