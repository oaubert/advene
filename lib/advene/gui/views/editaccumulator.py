# -*- coding: utf-8 -*-
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
from advene.gui.edit.elements import get_edit_popup

class EditAccumulator(AccumulatorPopup):
    """View displaying a limited number of compact editing widgets.
    """
    def __init__ (self, *p, **kw):
        kw['vertical']=True
        super(EditAccumulator, self).__init__(self, *p, **kw)
        self.view_name = _("EditAccumulator")
        self.view_id = 'editaccumulator'
        self.close_on_package_load = False
        self.edited_elements={}

    def edit(self, element):
        e=get_edit_popup(element, self.controller)
        if e.window:
            # The edit popup is already open
            return True
        w=e.compact()

        # Buttons hbox
        hbox=gtk.HBox()

        # Title
        if hasattr(element, 'type'):
            t="%s (%s)" % (self.controller.get_title(element),
                           self.controller.get_title(element.type))
        else:
            t=self.controller.get_title(element)

        # Limit label size
        if len(t) > 30:
            t=unicode(t[:29])+u'\u2026'
        l=gtk.Label(t)
        hbox.pack_start(l, expand=False)
        
        # Right align (hackish)
        b=gtk.HBox()
        hbox.pack_start(b, expand=True)

        def handle_ok(b, w):
            e.apply_cb()
            self.undisplay_cb(b, w)
            return True

        # Validate button
        b=gtk.Button('V')
        b.connect("clicked", lambda x: e.apply_cb())
        self.controller.gui.tooltips.set_tip(b, _("Validate"))
        hbox.pack_start(b, expand=False)

        # OK button
        b=gtk.Button('OK')
        b.connect("clicked", handle_ok, w)
        self.controller.gui.tooltips.set_tip(b, _("Validate and close"))
        hbox.pack_start(b, expand=False)

        # Close button
        b=gtk.Button('X')
        b.connect("clicked", self.undisplay_cb, w)
        self.controller.gui.tooltips.set_tip(b, _("Close"))
        hbox.pack_start(b, expand=False)

        self.edited_elements[element]=w
        self.display(w, title=hbox)

        def handle_destroy(*p):
            if self.controller and self.controller.gui:
                self.controller.gui.unregister_edit_popup(e)
            self.undisplay_cb(None, w)
            return True

        w.connect('destroy', handle_destroy)
        e.window=w
        if self.controller and self.controller.gui:
            self.controller.gui.register_edit_popup(e)


    def edit_element_handler(self, context, parameters):
        event=context.evaluateValue('event')
        if not event.endswith('Create'):
            return True
        el=event.replace('Create', '').lower()
        element=context.evaluateValue(el)
        self.edit(element)
        return True

    def register_callback (self, controller=None):
        """Add the handler for annotation edit.
        """
        self.callbacks = []
        for e in ('Annotation', 'View', 'Relation'):
            r=controller.event_handler.internal_rule (event="%sCreate" % e,
                                                      method=self.edit_element_handler)
            self.callbacks.append(r)

    def unregister_callback (self, controller=None):
        for c in self.callbacks:
            controller.event_handler.remove_rule(c, type_="internal")

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
