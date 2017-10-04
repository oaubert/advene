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
"""Dynamic montage module

FIXME: visual feedback when playing
FIXME: loop option
FIXME: replace button dropzone by EventBox 1pixel wide, with visual feedback
"""

import logging
logger = logging.getLogger(__name__)

# Advene part
import advene.core.config as config
import advene.util.helper as helper
from advene.gui.util import get_small_stock_button, name2color
import advene.gui.util.dialog as dialog
from advene.gui.views import AdhocView
from advene.gui.widget import AnnotationWidget
from advene.gui.views.annotationdisplay import AnnotationDisplay
import advene.gui.popup

from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import Gtk
import re

name="Montage view plugin"

def register(controller):
    controller.register_viewclass(Montage)

class Montage(AdhocView):
    view_name = _("Montage")
    view_id = 'montage'
    tooltip = _("Dynamic montage of annotations")
    def __init__(self, controller=None, elements=None, parameters=None):
        super(Montage, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Save view"), self.save_view),
            (_("Clear"), self.clear),
            (_("Play"), self.play),
            (_("Render"), self.render),
            )
        self.options={
            }
        self.controller=controller

        def scale_event(*p):
            self.refresh()
            return True

        # How many units (ms) does a pixel represent ?
        # How many units does a pixel represent ?
        # self.scale.get_value() = unit by pixel
        # Unit = ms
        self.scale = Gtk.Adjustment.new(int((self.controller.package.cached_duration or 60*60*1000) / Gdk.get_default_root_window().get_width()),
                                        5,
                                        36000,
                                        5,
                                        1000,
                                        100)
        self.scale.connect('value-changed', scale_event)

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        if elements is None:
            elements=[]
            # Get args
            for n, v in arg:
                if n == 'id':
                    try:
                        a=self.controller.package.get_element_by_id(v)
                    except KeyError:
                        # FIXME: should we silently pass, or display missing ids ?
                        pass
                    elements.append(a)

        # Needed by AnnotationWidget
        self.button_height = 20
        self.active_color=name2color('#fdfd4b')

        self.master_view=None

        # In self.contents, we store the AnnotationWidgets We do not
        # store directly the annotations, since there may be multiple
        # occurrences of the same annotations, and we need to
        # differenciate them.
        self.contents=[]
        self.duration=0

        self.mainbox=None
        self.widget=self.build_widget()

        # Annotation widget currently played
        self.current_widget = None

        if elements is not None:
            # Fill with default values
            for a in elements:
                self.insert(a)
        self.refresh()

    def set_master_view(self, master):
        def master_value_changed(sc):
            self.scale.set_value(sc.get_value())
            return False
        def master_changed(sc):
            self.scale.set_all(self.scale.get_value(),
                               sc.get_lower(), sc.get_upper(),
                               sc.get_step_increment(), sc.get_page_increment(),
                               sc.get_page_size())
            return False

        self.safe_connect(master.scale, 'value-changed', master_value_changed)
        self.safe_connect(master.scale, 'changed', master_changed)
        master.register_slave_view(self)
        self.master_view=master
        return

    def set_annotation(self, a=None):
        for v in self._slave_views:
            try:
                v.set_annotation(a)
            except AttributeError:
                pass

    def close(self, *p):
        super(Montage, self).close(*p)
        if self.master_view:
            self.master_view.unregister_slave_view(self)
        return True

    def get_save_arguments(self):
        return self.options, [ ('id', w.annotation.id) for w in self.contents ]

    def insert(self, annotation=None, position=None):
        def drag_sent(widget, context, selection, targetType, eventTime):
            # Override the standard AnnotationWidget drag_sent behaviour.
            if targetType == config.data.target_type['uri-list']:
                uri="advene:/adhoc/%d/%d" % (hash(self),
                                                  hash(widget))
                selection.set(selection.get_target(), 8, uri.encode('utf8'))
                return True
            return False

        def remove_cb(menuitem, widget):
            self.contents.remove(widget)
            self.refresh()
            return True

        def button_press(widget, event):
            """Handle button presses on annotation widgets.
            """
            if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
                # Display the popup menu when clicking on annotation.
                menu=advene.gui.popup.Menu(widget.annotation, controller=self.controller)
                menu.add_menuitem(menu.menu, _("Remove from montage"), remove_cb, widget)
                menu.menu.show_all()
                menu.popup()
                return True
            return False

        w=AnnotationWidget(annotation=annotation, container=self)
        w.connect('drag-data-get', drag_sent)
        w.connect('button-press-event', button_press)
        w.connect('focus-in-event', lambda b, e: self.set_annotation(annotation))

        if position is not None:
            self.contents.insert(position, w)
        else:
            self.contents.append(w)
        self.refresh()
        return True

    def unit2pixel(self, u):
        return int(u / self.scale.get_value())

    def pixel2unit(self, p):
        return int(p * self.scale.get_value())

    def refresh(self, *p):
        self.mainbox.foreach(self.mainbox.remove)
        self.append_dropzone(0)
        duration=0
        for i, a in enumerate(self.contents):
            self.append_repr(a)
            self.append_dropzone(i+1)
            duration += a.annotation.fragment.duration
        self.mainbox.show_all()

        self.duration=duration
        self.duration_label.set_text(helper.format_time(duration))
        return True

    def update_position(self, pos):
        w=self.current_widget
        if w is None:
            return
        f=w.annotation.fragment
        if not pos in f:
            w.fraction_marker=None
            return
        w.fraction_marker = 1.0 * (pos - f.begin) / f.duration

    def clear(self, *p):
        self.contents=[]
        self.refresh()
        return True

    def get_element_color(self, element):
        """Return the gtk color for the given element.
        Return None if no color is defined.
        """
        color=self.controller.get_element_color(element)
        return name2color(color)

    def set_widget_active(self, w, active):
        color=None
        if active:
            color=self.active_color
        w.active = active
        w.set_color(color)
        w.update_widget()

    def set_annotation_active(self, annotation, active):
        for w in self.contents:
            if w.annotation == annotation:
                self.set_widget_active(w, active)

    def update_annotation (self, annotation=None, event=None):
        """Update an annotation's representation."""
        if event == 'AnnotationActivate':
            self.set_annotation_active(annotation, True)
        elif event == 'AnnotationDeactivate':
            self.set_annotation_active(annotation, False)
        elif event == 'AnnotationEditEnd':
            # Update its representations
            l=[ w.update_widget() for w in self.contents if w.annotation == annotation ]
        elif event == 'AnnotationDelete':
            l=[ w for w in self.contents if w.annotation == annotation ]
            if l:
                for w in l:
                    self.contents.remove(w)
                self.refresh()
        return True

    def append_dropzone(self, i):
        """Append a dropzone for a given index.
        """
        def drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.annotations.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                for ann in sources:
                    self.insert(ann, i)
                    # If the origin is from the same montage, then
                    # consider it is a move and remove the origin
                    # annotation
                    w=Gtk.drag_get_source_widget(context)
                    if w in self.contents:
                        self.contents.remove(w)
                self.refresh()
                return True
            else:
                logger.warn("Unknown target type for drag: %d" % targetType)
            return False

        b = Gtk.Button()
        b.set_size_request(4, self.button_height)
        b.index=i
        b.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('annotation'),
                        Gdk.DragAction.COPY | Gdk.DragAction.LINK)
        b.connect('drag-data-received', drag_received)

        self.mainbox.pack_start(b, False, False, 0)
        return b

    def append_repr(self, w):
        self.mainbox.pack_start(w, False, False, 0)
        w.update_widget()
        return w

    def render(self, *p):
        """Render the current montage.
        """
        self.controller.gui.render_montage_dialog([ w.annotation for w in self.contents ],
                                                  basename = helper.title2id(self.view_name) + ".ogv",
                                                  title = _("Extracting %s") % self.view_name,
                                                  label = _("Exporting montage %(title)s\nto %%(filename)s") % { 'title': self.view_name })
        return True

    def play(self, *p):
        """Play the current montage.
        """
        annotation_queue=iter(self.contents)

        def one_step(controller, position):
            """Go to the beginning of the annotation, and program the next jump.
            """
            try:
                w=next(annotation_queue)
                if self.current_widget is not None:
                    self.current_widget.fraction_marker=None
                self.current_widget=w
                a=w.annotation
            except StopIteration:
                self.controller.update_status('pause')
                for w in self.contents:
                    self.set_widget_active(w, False)
                if self.current_widget is not None:
                    self.current_widget.fraction_marker=None
                self.current_widget=None
                return False
            # Go to the annotation
            # Change position only if we are not already at the right place
            if abs(position - a.fragment.begin) > 100:
                self.controller.queue_action(self.controller.update_status, 'seek', a.fragment.begin, notify=False)
            self.controller.queue_action(self.set_widget_active, w, True)
            self.controller.position_update()
            # And program its end.

            # This is a bit convoluted, but it is needed to make sure
            # that the videotime_action does not get removed before
            # even being taken into account (when going backwards),
            # because the controller videotime_action handling removes
            # actions that are before the current time.
            self.controller.register_usertime_delayed_action(0,
                                                             lambda c, b: self.controller.register_videotime_action(a.fragment.end, one_step))
            return True

        self.controller.update_status('start', notify=False)
        self.controller.register_usertime_delayed_action(0, one_step)

        return True

    def build_widget(self):
        self.zoom_adjustment=Gtk.Adjustment.new(value=1.0,
                                                lower=0.01,
                                                upper=2.0,
                                                step_increment=.01,
                                                page_increment=.1,
                                                page_size=.1)

        def zoom_adj_change(adj):
            # Update the value of self.scale accordingly
            # Get the window size
            if not self.mainbox.get_window():
                # The widget is not yet realized
                return True
            display_size=self.mainbox.get_parent().get_window().get_width()
            # Dropzones are approximately 10 pixels wide, and should
            # be taken into account, but it enforces handling the corner cases
            self.scale.set_value(1.0 * self.duration / (display_size / adj.get_value() ))

            # Update the zoom combobox value
            self.zoom_combobox.get_child().set_text('%d%%' % int(100 * adj.get_value()))
            return True

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['uri-list']:
                m=re.match('advene:/adhoc/%d/(.+)' % hash(self),
                           selection.get_data().decode('utf-8'))
                if m:
                    h=int(m.group(1))
                    l=[ w for w in self.contents if hash(w) == h ]
                    if l:
                        # Found the element. Remove it.
                        self.contents.remove(l[0])
                        self.refresh()
                return True
            else:
                logger.warn("Unknown target type for drop: %d" % targetType)
            return False

        self.zoom_adjustment.connect('value-changed', zoom_adj_change)

        v=Gtk.VBox()

        # Toolbar
        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        b=get_small_stock_button(Gtk.STOCK_DELETE)
        b.set_tooltip_text(_("Drop an annotation here to remove it from the list"))
        b.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('uri-list'),
                        Gdk.DragAction.COPY | Gdk.DragAction.LINK)
        b.connect('drag-data-received', remove_drag_received)
        ti=Gtk.ToolItem()
        ti.add(b)
        tb.insert(ti, -1)

        b=Gtk.ToolButton(Gtk.STOCK_MEDIA_PLAY)
        b.set_tooltip_text(_("Play the montage"))
        b.connect('clicked', self.play)
        tb.insert(b, -1)

        b = Gtk.ToolButton(Gtk.STOCK_SAVE)
        b.set_tooltip_text(_("Save the view in the package"))
        b.connect('clicked', self.save_view)
        tb.insert(b, -1)

        def zoom_entry(entry):
            f=entry.get_text()

            i=re.findall(r'\d+', f)
            if i:
                f=int(i[0])/100.0
            else:
                return True
            self.zoom_adjustment.set_value(f)
            return True

        def zoom_change(combo):
            v=combo.get_current_element()
            if isinstance(v, float):
                self.zoom_adjustment.set_value(v)
            return True

        def zoom(i, factor):
            self.zoom_adjustment.set_value(self.zoom_adjustment.get_value() * factor)
            return True

        b=Gtk.ToolButton(Gtk.STOCK_ZOOM_OUT)
        b.connect('clicked', zoom, 1.3)
        b.set_tooltip_text(_("Zoom out"))
        tb.insert(b, -1)

        b=Gtk.ToolButton(Gtk.STOCK_ZOOM_IN)
        b.connect('clicked', zoom, .7)
        b.set_tooltip_text(_("Zoom in"))
        tb.insert(b, -1)

        self.zoom_combobox=dialog.list_selector_widget(members=[
                ( f, "%d%%" % int(100*f) )
                for f in [
                    (1.0 / pow(1.5, n)) for n in range(0, 10)
                    ]
                ],
                                                       entry=True,
                                                       callback=zoom_change)
        self.zoom_combobox.get_child().connect('activate', zoom_entry)
        self.zoom_combobox.get_child().set_width_chars(4)

        ti=Gtk.ToolItem()
        ti.add(self.zoom_combobox)
        ti.set_tooltip_text(_("Set zoom level"))
        tb.insert(ti, -1)

        b=Gtk.ToolButton(Gtk.STOCK_ZOOM_100)
        b.connect('clicked', lambda i: self.zoom_adjustment.set_value(1.0))
        b.set_tooltip_text(_("Set 100% zoom"))
        tb.insert(b, -1)

        def toggle_highlight(b):
            if b.highlight:
                event="AnnotationActivate"
                label= _("Unhighlight annotations")
                b.highlight=False
            else:
                event="AnnotationDeactivate"
                label=_("Highlight annotations")
                b.highlight=True
            b.set_tooltip_text(label)
            for a in set( [ w.annotation for w in self.contents ] ):
                self.controller.notify(event, annotation=a)
            return True
        i=Gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'highlight.png') ))
        b=Gtk.ToggleToolButton()
        b.set_tooltip_text(_("Highlight annotations"))
        b.set_icon_widget(i)
        b.highlight=True
        b.connect('clicked', toggle_highlight)
        tb.insert(b, -1)

        v.pack_start(tb, False, True, 0)

        self.mainbox=Gtk.HBox()

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.annotations.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                for ann in sources:
                    if ann is None:
                        self.log("Problem when getting annotation from DND")
                        pass
                    self.insert(ann)
                    # If the origin is from the same montage, then
                    # consider it is a move and remove the origin
                    # annotation
                    w=Gtk.drag_get_source_widget(context)
                    if w in self.contents:
                        self.contents.remove(w)
                self.refresh()
                return True
            elif targetType == config.data.target_type['annotation-type']:
                at=self.controller.package.annotationTypes.get(str(selection.get_data(), 'utf8'))
                for a in at.annotations:
                    self.insert(a)
                self.refresh()
                return True
            else:
                logger.warn("Unknown target type for drag: %d" % targetType)
            return False
        v.drag_dest_set(Gtk.DestDefaults.MOTION |
                                   Gtk.DestDefaults.HIGHLIGHT |
                                   Gtk.DestDefaults.ALL,
                                   config.data.get_target_types('annotation', 'annotation-type'),
                                   Gdk.DragAction.COPY | Gdk.DragAction.LINK | Gdk.DragAction.MOVE)
        v.connect('drag-data-received', mainbox_drag_received)

        sw=Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sw.add_with_viewport(self.mainbox)
        self.scrollwindow=sw

        v.pack_start(sw, False, True, 0)

        a=AnnotationDisplay(controller=self.controller)
        f=Gtk.Frame.new(_("Inspector"))
        f.add(a.widget)
        v.add(f)
        self.controller.gui.register_view (a)
        a.set_master_view(self)
        a.widget.show_all()

        v.pack_start(Gtk.VBox(), True, True, 0)

        hb=Gtk.HBox()
        l=Gtk.Label(label=_("Total duration:"))
        hb.pack_start(l, False, True, 0)
        self.duration_label=Gtk.Label(label='??')
        hb.pack_start(self.duration_label, False, True, 0)
        v.pack_start(hb, False, True, 0)

        return v
