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
from advene.gui.edit.frameselector import FrameSelector

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

        self.current_index = gtk.Adjustment(10, 1, 10, 1, 10)
        self.options={}

        # Load options
        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)

        self.annotationtype=annotationtype
        self.widget = self.build_widget()

    def set_annotationtype(self, at):
        self._annotationtype=at
        self.annotations = sorted(at.annotations, key=lambda a: a.fragment.begin)
        self.current_index.set_upper(len(self.annotations))

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

    def update_annotationtype(self, annotationtype=None, event=None):
        if annotationtype == self.annotationtype and event == 'AnnotationTypeDelete':
            self.close()
        return True

    def update_annotation(self, annotation=None, event=None):
        if annotation.type == self.annotationtype and event in ('AnnotationCreate', 'AnnotationDelete'):
            # Update annotation type, which will trigger an update of self.annotations
            self.annotationtype = annotation.type
            self.current_index.emit('value-changed')
        
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
        self.controller.notify('AnnotationEditEnd', annotation=previous, batch=batch)
        self.controller.notify('EditSessionEnd', element=previous)
        self.annotations.remove(annotation)
        self.controller.delete_element(annotation, immediate_notify=True, batch=batch)
        self.message(_("Merged #%(first)d-#%(second)d into #%(first)d" % { 'first': i + 1,
                                                                           'second': i + 2 }))
        self.undo_button.set_sensitive(True)

        # We want to display the next annotation, i.e. at i. But we
        # were already at i, so the handle_index_change would not be
        # triggered. Force value-changed emission
        self.set_index(i)
        self.current_index.emit('value-changed')
        return True

    def handle_keypress(self, widget, event):
        if event.keyval == gtk.keysyms.Page_Down:
            # Next annotation
            self.set_index(self.index + 1)
            return True
        elif event.keyval == gtk.keysyms.Page_Up:
            # Previous annotation
            self.set_index(self.index - 1)
            return True
        return False

    def undo(self, *p):
        """Undo the last modification.
        """
        self.message(_("Last action undone"))
        self.controller.gui.undo()
        if self.index > 0:
            self.index = self.index - 1
        return True
            
    def validate_and_next(self, new):
        """Validate the current annotation and display the next one.
        """
        i = self.index
        annotation = self.annotations[i]
        batch=object()

        event = gtk.get_current_event()
        if event.state & gtk.gdk.CONTROL_MASK:
            # Control-key is held. Split the annotation.
            if new > annotation.fragment.begin and new < annotation.fragment.end:
                self.controller.split_annotation(annotation, new)
                self.message(_("Split annotation #%(current)d into #%(current)d and #%(next)d") % {
                        'current': i + 1,
                        'next': i + 2 
                        })
            else:
                self.message(_("Cannot split annotation #%(current)d: out of bounds.") % {
                        'current': i + 1,
                        })
            return True

        if new != annotation.fragment.begin:
            self.controller.notify('EditSessionStart', element=annotation, immediate=True)
            annotation.fragment.begin = new
            self.controller.notify('AnnotationEditEnd', annotation=annotation, batch=batch)
            self.controller.notify('EditSessionEnd', element=annotation)
            self.undo_button.set_sensitive(True)

        # Update previous annotation end.
        if i > 0:
            annotation = self.annotations[i - 1]
            if new != annotation.fragment.end:
                self.controller.notify('EditSessionStart', element=annotation, immediate=True)
                annotation.fragment.end = new
                self.controller.notify('AnnotationEditEnd', annotation=annotation, batch=batch)
                self.controller.notify('EditSessionEnd', element=annotation)
            self.message(_("Changed cut between #%(first)d and %(second)d") % { 'first': i + 1,
                                                                                  'second': i + 2 })
        else:
            self.message(_("Changed begin time for first annotation"))
        self.set_index(i + 1)
        return True

    def build_widget(self):
        if not self.annotations:
            return gtk.Label((_("No annotations to adjust")))

        vbox = gtk.VBox()
                    
        self.title_widget = gtk.Label()
        vbox.pack_start(self.title_widget)

        self.selector = FrameSelector(self.controller, self.annotations[0].fragment.begin, label=_("Click on the frame just after the cut to adjust the cut time.\nControl-click on a frame to indicate a missing cut."))
        self.selector.callback = self.validate_and_next

        def handle_index_change(adj):
            i = int(adj.get_value()) - 1
            if i >= 0 and i <= len(self.annotations) - 1:
                a=self.annotations[i]
                self.selector.set_timestamp(a.fragment.begin)
                self.set_title(_("Begin of #%(index)d (title: %(content)s)") % { 'index': i + 1,
                                                                                 'content': self.controller.get_title(a, max_size=60) })
                self.prev_button.set_sensitive(i > 0)
                self.next_button.set_sensitive(i < len(self.annotations) - 1)
            else:
                # End: display a message ?
                pass
        self.current_index.connect('value-changed', handle_index_change)
        
        vbox.add(self.selector.widget)

        # Button bar
        hb=gtk.HBox()

        self.prev_button = gtk.Button(_("< Previous cut"))
        self.prev_button.set_tooltip_text(_("Display previous cut"))
        self.prev_button.connect("clicked", lambda b: self.set_index(self.index - 1))
        hb.add(self.prev_button)

        l = gtk.Label("#")
        hb.pack_start(l, expand=False)

        self.next_button = gtk.Button(_("Next cut >"))
        self.next_button.set_tooltip_text(_("Display next cut"))
        self.next_button.connect("clicked", lambda b: self.set_index(self.index + 1))

        s=gtk.SpinButton(self.current_index, 1, 0)
        s.set_increments(1, 10)
        s.set_update_policy(gtk.UPDATE_IF_VALID)
        s.set_numeric(True)

        # For an unknown reason, the default behaviour of updating
        # SpinButton through scroll does not work. Emulate it.
        def handle_spin_scroll(widget, event):
            if event.direction == gtk.gdk.SCROLL_UP:
                offset=+1
            elif event.direction == gtk.gdk.SCROLL_DOWN:
                offset=-1
            self.set_index(self.index + offset)
            return True
        s.connect('scroll-event', handle_spin_scroll)
        hb.add(s)

        hb.add(self.next_button)

        vbox.pack_start(hb, expand=False)

        hb = gtk.HButtonBox()
        b=gtk.Button(_("Current time"))
        b.set_tooltip_text(_("Go to annotation containing current player time."))
        b.connect("clicked", self.goto_current)
        hb.add(b)

        b=gtk.Button(_("Refresh snapshots"))
        b.set_tooltip_text(_("Refresh missing snapshots"))
        b.connect("clicked", lambda b: self.selector.refresh_snapshots())
        hb.add(b)

        b=gtk.Button(_("Undo"))
        b.set_tooltip_text(_("Undo last modification"))
        b.connect("clicked", self.undo)
        hb.add(b)
        b.set_sensitive(False)
        self.undo_button = b

        b=gtk.Button(_("Merge with previous"))
        b.set_tooltip_text(_("Merge with previous annotation, i.e. remove this bound."))
        b.connect("clicked", self.merge)
        hb.add(b)

        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.set_tooltip_text(_("Close view."))
        b.connect("clicked", self.close)
        hb.add(b)

        vbox.pack_start(hb, expand=False)

        self.statusbar = gtk.Statusbar()
        vbox.pack_start(self.statusbar, expand=False)

        self.set_index(0)
        vbox.show_all()
        vbox.connect('key-press-event', self.handle_keypress)
        return vbox

