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
"""Tag bag view
============

Note: this adhoc view is also used in element edit popups.

This view presents a number of tags to the user, so that she can apply
them to various elements by drag and drop.

Dragging a tag to an annotation with add the tag to the annotation's tag.

Dragging an annotation to the tag bag will add the annotation tags to
the presented list of tags.
"""
import logging
logger = logging.getLogger(__name__)

# Advene part
import advene.core.config as config
from advene.gui.views import AdhocView
from advene.gui.edit.properties import EditWidget
from advene.gui.util import dialog, get_small_stock_button, name2color

from gettext import gettext as _

import re
from gi.repository import Gdk
from gi.repository import Gtk

from advene.gui.widget import TagWidget

name="Tagbag view plugin"

def register(controller):
    controller.register_viewclass(TagBag)

class TagBag(AdhocView):
    view_name = _("Tag Bag")
    view_id = 'tagbag'
    tooltip = _("Bag of tags")
    def __init__(self, controller=None, parameters=None, tags=None, vertical=True):
        super(TagBag, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("New tag"), self.new_tag),
            (_("Clear"), self.clear),
            (_("Preferences"), self.edit_options),
            (_("Save default options"), self.save_default_options),
            )
        self.options={
            'display-new-tags': False
            }
        self.controller=controller
        self.vertical=vertical

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        l=[ v for (n, v) in arg if n == 'tag' ]
        if l:
            tags=l
        self.tags=tags
        if self.tags is None:
            self.tags=[]

        self.button_height=24
        self.mainbox=None
        self.widget=self.build_widget()
        self.refresh()

    def clear(self, *p):
        del self.tags[:]
        self.refresh()

    def tag_update(self, context, parameters):
        tag=context.evaluateValue('tag')
        if not tag in self.tags:
            # The tag is not present
            if self.options['display-new-tags']:
                self.tags.append(tag)
                self.append_repr(tag)
            return True

        # Is there an associated color ?
        col = self.controller.package._tag_colors(tag, None)
        if col is None:
            return True

        l=[ b for b in self.mainbox.get_children() if b.tag == tag ]
        for b in l:
            b.update_widget()
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
        d = Gtk.Dialog(title=_("New tag name"),
                       parent=self.controller.gui.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                 Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 ))
        l=Gtk.Label(label=_("Enter a new tag name and select its color."))
        d.vbox.pack_start(l, False, True, 0)

        hb=Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Name")), False, False, 0)
        tagname=Gtk.Entry()
        hb.pack_start(tagname, False, True, 0)
        d.vbox.pack_start(hb, False, True, 0)

        hb=Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Color")), False, False, 0)
        colorbutton=Gtk.ColorButton()
        colorbutton.set_color(Gdk.color_parse('red'))
        hb.pack_start(colorbutton, False, True, 0)
        d.vbox.pack_start(hb, False, True, 0)

        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        d.show_all()
        dialog.center_on_mouse(d)

        res=d.run()
        if res == Gtk.ResponseType.OK:
            try:
                tag=tagname.get_text()
            except ValueError:
                tag=None
            color=colorbutton.get_color()
        else:
            tag=None
        d.destroy()

        if tag and not tag in self.tags:
            if not re.match('^[\w\d_]+$', tag):
                dialog.message_dialog(_("The tag contains invalid characters"),
                                               icon=Gtk.MessageType.ERROR)
                return True
            self.tags.append(tag)
            self.controller.package._tag_colors[tag]="#%04x%04x%04x" % (color.red, color.green, color.blue)
            self.controller.notify('TagUpdate', tag=tag)
            self.refresh()
        return True

    def edit_options(self, *p):
        cache=dict(self.options)

        ew=EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Tag bag options"))
        ew.add_checkbox(_("Update with new tags"), "display-new-tags", _("Automatically display new defined tags"))
        res=ew.popup()

        if res:
            self.options.update(cache)
        return True

    def all_tags(self, *p):
        self.tags=sorted(self.controller.package._tag_colors.keys())
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

    def get_element_color(self, tag):
        """Return the gtk color for the given tag.
        Return None if no color is defined.
        """
        try:
            col=self.controller.package._tag_colors[tag]
        except KeyError:
            col=None
        return name2color(col)

    def append_repr(self, t):
        b=TagWidget(t, container=self)
        b.update_widget()

        def remove(widget, tag):
            if tag in self.tags:
                self.tags.remove(tag)
                self.controller.notify('TagUpdate', tag=tag)
                self.refresh()
            return True

        def set_color(widget, tag):
            d=Gtk.ColorSelectionDialog(_("Choose the color for tag %s") % tag)
            try:
                color=self.get_element_color(tag)
                if color:
                    d.get_color_selection().set_current_color(color)
            except:
                pass

            res=d.run()
            if res == Gtk.ResponseType.OK:
                col=d.get_color_selection().get_current_color()
                self.controller.package._tag_colors[tag]="#%04x%04x%04x" % (col.red, col.green, col.blue)
                self.controller.notify('TagUpdate', tag=tag)
                # The color setting of the widget is done in the callback for TagUpdate
            d.destroy()
            return True

        def popup_menu(widget, event):
            if not (event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS):
                return False

            menu=Gtk.Menu()

            for label, action in (
                (_("Set color"), set_color),
                (_("Remove"), remove)
                ):
                item = Gtk.MenuItem(label, use_underline=False)
                item.connect('activate', action, t)
                menu.append(item)
            menu.show_all()
            menu.popup_at_pointer(None)
            return True

        b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                          config.data.get_target_types('tag'),
                          Gdk.DragAction.LINK)

        b.connect('button-press-event', popup_menu)
        b.show()
        self.mainbox.pack_start(b, False, True, 0)

    def build_widget(self):

        if self.vertical:
            v=Gtk.VBox()
            mainbox=Gtk.VBox()
        else:
            v=Gtk.HBox()
            mainbox=Gtk.HBox()

        mainbox.set_homogeneous(False)
        sw=Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        sw.add_with_viewport(mainbox)
        self.mainbox=mainbox

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.annotations.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                for a in sources:
                    for tag in a.tags:
                        if not tag in self.tags:
                            self.tags.append(tag)
                self.refresh()
            elif targetType == config.data.target_type['tag']:
                tags=str(selection.get_data(), 'utf8').split(',')
                for tag in tags:
                    if not tag in self.tags:
                        self.tags.append(tag)
                self.refresh()
            else:
                logger.warn("Unknown target type for mainbox drop: %d" % targetType)
            return True

        self.mainbox.drag_dest_set(Gtk.DestDefaults.MOTION |
                                   Gtk.DestDefaults.HIGHLIGHT |
                                   Gtk.DestDefaults.ALL,
                                   config.data.get_target_types('annotation', 'tag'),
                                   Gdk.DragAction.LINK)
        self.mainbox.connect('drag-data-received', mainbox_drag_received)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['tag']:
                tag=str(selection.get_data(), 'utf8')
                if tag in self.tags:
                    self.tags.remove(tag)
                self.refresh()
            else:
                logger.warn("Unknown target type for remove drop: %d" % targetType)
            return True


        hb=Gtk.HBox()
        hb.set_homogeneous(False)

        b=get_small_stock_button(Gtk.STOCK_DELETE)

        b.set_tooltip_text(_("Drop a tag here to remove it from the list"))
        b.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('tag'),
                        Gdk.DragAction.LINK)
        b.connect('drag-data-received', remove_drag_received)
        hb.pack_start(b, False, True, 0)

        for (stock, tip, method) in (
            (Gtk.STOCK_SAVE, _("Save as adhoc view"), self.save_view),
            (Gtk.STOCK_ADD, _("Add a new tag"), self.new_tag),
            (Gtk.STOCK_INDEX, _("Display all defined tags"), self.all_tags),
            ):
            b=get_small_stock_button(stock)
            b.set_tooltip_text(tip)
            b.connect('clicked', method)
            hb.pack_start(b, False, True, 0)

        v.buttonbox=hb

        v.pack_start(hb, False, True, 0)
        v.add(sw)

        return v
