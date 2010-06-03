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
import gtk

from gettext import gettext as _

from advene.gui.views import AdhocView
from advene.gui.edit.timeadjustment import FrameSelector

name="Shot validation view plugin"

def register(controller):
    controller.register_viewclass(ShotValidation)

class ShotValidation(AdhocView):
    view_name = _("Shot validation view")
    view_id = 'shotvalidation'
    tooltip=_("Display shot validation interface")

    def __init__(self, controller=None, parameters=None, annotationtype=None):
        super(ShotValidation, self).__init__(controller=controller)
        self.close_on_package_load = True
        self.contextual_actions = (
            )
        self.controller=controller
        self._annotationtype=None
        self.annotationtype=annotationtype
        self.options={}

        # Load options
        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)

        self.widget = self.build_widget()

    def set_annotationtype(self, at):
        self._annotationtype=at
        self.annotations = sorted(at.annotations, key=lambda a: a.fragment.begin)

    def get_annotationtype(self):
        return self._annotationtype
    annotationtype=property(get_annotationtype, set_annotationtype)

    def set_title(self, s):
        self.title_widget.set_markup(s)

    def set_index(self, i):
        self.current_index.set_value(i + 1)
    def get_index(self):
        return int(self.current_index.get_value()) - 1
    index = property(get_index, set_index)

    def goto_current(self, *p):
        """Select annotation containing current player time.
        """
        l=[ a for a in self.annotations if self.controller.player.current_position_value in a.fragment ]
        if l:
            self.set_index(self.annotations.index(l[0]))
        return True

    def merge(self, *p):
        """Merge the annotation with the previous one.
        """
        i = self.index
        if i == 0:
            return True

        annotation = self.annotations[i]
        previous = self.annotations[i - 1]
        batch=object()

        self.controller.notify('EditSessionStart', element=previous, immediate=True)
        previous.fragment.end = annotation.fragment.end
        self.controller.notify('AnnotationEditEnd', annotation=previous, batch_id=batch)
        self.controller.notify('EditSessionEnd', element=previous)
        self.annotations.remove(annotation)
        self.controller.delete_element(annotation, immediate_notify=True, batch_id=batch)
        self.set_index(i - 1)
        return True

    def validate_and_next(self, new):
        """Validate the current annotation and display the next one.
        """
        i = self.index
        annotation = self.annotations[i]
        batch=object()

        if new != annotation.fragment.begin:
            self.controller.notify('EditSessionStart', element=annotation, immediate=True)
            annotation.fragment.begin = new
            self.controller.notify('AnnotationEditEnd', annotation=annotation, batch_id=batch)
            self.controller.notify('EditSessionEnd', element=annotation)

        # Update previous annotation end.
        if i > 0:
            annotation = self.annotations[i - 1]
            if new != annotation.fragment.end:
                self.controller.notify('EditSessionStart', element=annotation, immediate=True)
                annotation.fragment.end = new
                self.controller.notify('AnnotationEditEnd', annotation=annotation, batch_id=batch)
                self.controller.notify('EditSessionEnd', element=annotation)

        self.set_index(i + 1)
        return True

    def build_widget(self):
        if not self.annotations:
            return gtk.Label((_("No annotations to adjust")))

        vbox = gtk.VBox()
                    
        self.title_widget = gtk.Label()
        vbox.pack_start(self.title_widget)

        self.selector = FrameSelector(self.controller, self.annotations[0].fragment.begin)
        self.selector.callback = self.validate_and_next

        # Current index, in a user-readable way (i.e. starting at 1)
        size=len(self.annotations)

        # We initialize the adjustment at size, so that when we set it
        # back to 1 at the end of the initialization, the
        # handle_index_change correctly updates buttons.
        self.current_index = gtk.Adjustment(size, 1, size, 1, 10)

        def handle_index_change(adj):
            i = int(adj.get_value()) - 1
            if i >= 0 and i <= len(self.annotations) - 1:
                a=self.annotations[i]
                self.selector.set_timestamp(a.fragment.begin)
                self.set_title(_("Begin of ") + self.controller.get_title(a))
                if i > 0:
                    self.prev_button.set_label(_("Previous: %s") % self.controller.get_title(self.annotations[i - 1]))
                    self.prev_button.set_sensitive(True)
                else:
                    self.prev_button.set_label(_("No previous annotation"))
                    self.prev_button.set_sensitive(True)

                if i < len(self.annotations) - 1:
                    self.next_button.set_label(_("Next: %s") % self.controller.get_title(self.annotations[i + 1]))
                    self.next_button.set_sensitive(True)
                else:
                    self.next_button.set_label(_("No next annotation"))
                    self.next_button.set_sensitive(True)
            else:
                # End: display a message ?
                pass
        self.current_index.connect('value-changed', handle_index_change)
        
        vbox.add(self.selector.widget)

        # Button bar
        hb=gtk.HBox()

        self.prev_button = gtk.Button()
        self.prev_button.connect("clicked", lambda b: self.set_index(self.index - 1))
        hb.add(self.prev_button)

        b=gtk.Button(_("Current time"))
        b.set_tooltip_text(_("Go to annotation containing current player time."))
        b.connect("clicked", self.goto_current)
        hb.add(b)

        b=gtk.Button(_("Merge with previous"))
        b.set_tooltip_text(_("Merge with previous annotation, i.e. remove this bound."))
        b.connect("clicked", self.merge)
        hb.add(b)

        l = gtk.Label("#")
        hb.pack_start(l, expand=False)

        self.next_button = gtk.Button()
        self.next_button.connect("clicked", lambda b: self.set_index(self.index + 1))

        s=gtk.SpinButton(self.current_index, 1, 0)
        s.set_increments(1, 10)
        s.set_update_policy(gtk.UPDATE_IF_VALID)
        s.set_numeric(True)
        hb.add(s)

        hb.add(self.next_button)

        vbox.pack_start(hb, expand=False)
        self.set_index(0)
        vbox.show_all()
        
        return vbox

