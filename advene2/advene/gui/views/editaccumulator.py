# -*- coding: utf-8 -*-
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
"""Edit Accumulator.

This widget allows to stack compact editing widgets.
"""

import gtk

from gettext import gettext as _

import advene.core.config as config
from advene.gui.views.accumulatorpopup import AccumulatorPopup
from advene.gui.edit.elements import get_edit_popup
from advene.gui.util import get_small_stock_button, get_pixmap_button

name="Edit accumulator view plugin"

def register(controller):
    controller.register_viewclass(EditAccumulator)

class EditAccumulator(AccumulatorPopup):
    """View displaying a limited number of compact editing widgets.
    """
    view_name = _("EditAccumulator")
    view_id = 'editaccumulator'

    def __init__ (self, *p, **kw):
        kw['vertical']=True
        super(EditAccumulator, self).__init__(*p, **kw)
        self.close_on_package_load = False
        self.edited_elements={}
        self.size = 0

    def edit(self, element):
        e=get_edit_popup(element, self.controller)
        if e._widget:
            # The edit popup is already open
            return True
        w=e.compact()

        # Buttons hbox
        hbox=gtk.HBox()

        def handle_ok(b, w):
            e.apply_cb()
            self.undisplay_cb(b, w)
            return True

        # OK button
        b=get_pixmap_button('small_ok.png', handle_ok, w)
        b.set_relief(gtk.RELIEF_NONE)
        self.controller.gui.tooltips.set_tip(b, _("Validate and close"))
        hbox.pack_start(b, expand=False)

        # Close button
        b=get_pixmap_button('small_close.png', self.undisplay_cb, w)
        b.set_relief(gtk.RELIEF_NONE)
        self.controller.gui.tooltips.set_tip(b, _("Close"))
        hbox.pack_start(b, expand=False)

        t=self.get_short_title(element)
        l=gtk.Label()
        l.set_markup('<b>%s</b>' % t)
        hbox.pack_start(l, expand=True)

        self.edited_elements[element]=w
        w._title_label=l
        self.display(w, title=hbox)

        def handle_destroy(*p):
            if self.controller and self.controller.gui:
                self.controller.gui.unregister_edit_popup(e)
            self.undisplay_cb(None, w)
            return True

        w.connect('destroy', handle_destroy)

        if self.controller and self.controller.gui:
            self.controller.gui.register_edit_popup(e)

    def get_short_title(self, element):
        # Title
        if hasattr(element, 'type'):
            t="%s (%s)" % (self.controller.get_title(element),
                           self.controller.get_title(element.type))
        else:
            t=self.controller.get_title(element)

        # Limit label size
        # Ellipsize does not work well here, the label is always
        # allocated too small a space
        #l.set_ellipsize(pango.ELLIPSIZE_END)
        if len(t) > 80:
            t=unicode(t[:79])+u'\u2026'
        return t

    def edit_element_handler(self, context, parameters):
        event=context.evaluate('event')
        if not event.endswith('Create'):
            return True
        el=event.replace('Create', '').lower()
        element=context.evaluate(el)
        if hasattr(element, 'complete') and not element.complete:
            self.edit(element)
        return True

    def update_element(self, element, event):
        if not event.endswith('EditEnd') or not element in self.edited_elements:
            return False
        w=self.edited_elements[element]
        l=w._title_label
        l.set_markup('<b>%s</b>' % self.get_short_title(element))
        return True
            
    def update_annotation(self, annotation, event):
        self.update_element(annotation, event)
        return True

    def update_relation(self, relation, event):
        self.update_element(relation, event)
        return True

    def update_view(self, view, event):
        self.update_element(view, event)
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
            sources=[ self.controller.package.annotations.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
            for source in sources:
                self.edit(source)
        else:
            print "Unknown target type for drop: %d" % targetType
        return True

    def build_widget(self):
        mainbox=super(EditAccumulator, self).build_widget()

        # The widget can receive drops from annotations
        mainbox.connect('drag-data-received', self.drag_received)
        mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['annotation'], gtk.gdk.ACTION_LINK)

        return mainbox
