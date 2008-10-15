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
"""Dynamic montage module

FIXME: visual feedback when playing
FIXME: loop option
FIXME: replace button dropzone by EventBox 1pixel wide, with visual feedback
"""

# Advene part
import advene.core.config as config
import advene.util.helper as helper
from advene.gui.util import get_small_stock_button, name2color, get_pixmap_button
import advene.gui.util.dialog as dialog
from advene.gui.views import AdhocView
from advene.gui.widget import AnnotationWidget
from advene.gui.views.annotationdisplay import AnnotationDisplay
import advene.gui.popup

from gettext import gettext as _

import gtk
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
            )
        self.options={
            }
        self.controller=controller

        def scale_event(*p):
            self.refresh()
            return True

        # How many units (ms) does a pixel represent ?
        # How many units does a pixel represent ?
        # self.scale.value = unit by pixel
        # Unit = ms
        self.scale = gtk.Adjustment (value=(self.controller.package.cached_duration or 60*60*1000) / gtk.gdk.get_default_root_window().get_size()[0],
                                     lower=5,
                                     upper=36000,
                                     step_incr=5,
                                     page_incr=1000)
        self.scale.connect('value-changed', scale_event)

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        if elements is None:
            elements=[]
            # Get args
            for n, v in arg:
                if n == 'id':
                    try:
                        a=self.controller.package.get(v)
                    except KeyError:
                        # FIXME: should we silently pass, or display missing ids ?
                        pass
                    elements.append(a)

        # Needed by AnnotationWidget
        self.button_height = 20
        self.active_color=gtk.gdk.color_parse ('#fdfd4b')

        self.master_view=None

        # In self.contents, we store the AnnotationWidgets We do not
        # store directly the annotations, since there may be multiple
        # occurrences of the same annotations, and we need to
        # differenciate them.
        self.contents=[]
        self.duration=0

        self.mainbox=None
        self.widget=self.build_widget()

        if elements is not None:
            # Fill with default values
            for a in elements:
                self.insert(a)
        self.refresh()

    def set_master_view(self, master):
        def master_value_changed(sc):
            self.scale.value=sc.value
            return False
        def master_changed(sc):
            self.scale.set_all(self.scale.value,
                               sc.lower, sc.upper,
                               sc.step_increment, sc.page_increment,
                               sc.page_size)
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
                selection.set(selection.target, 8, uri.encode('utf8'))
                return True
            return False

        def remove_cb(menuitem, widget):
            self.contents.remove(widget)
            self.refresh()
            return True

        def button_press(widget, event):
            """Handle button presses on annotation widgets.
            """
            if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
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
        return long(u / self.scale.value)

    def pixel2unit(self, p):
        return long(p * self.scale.value)

    def refresh(self, *p):
        self.mainbox.foreach(self.mainbox.remove)
        self.append_dropzone(0)
        duration=0
        for i, a in enumerate(self.contents):
            self.append_repr(a)
            self.append_dropzone(i+1)
            duration += a.annotation.duration
        self.mainbox.show_all()

        self.duration=duration
        self.duration_label.set_text(helper.format_time(duration))
        return True

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
                sources=[ self.controller.package.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
                for ann in sources:
                    self.insert(ann, i)
                    # If the origin is from the same montage, then
                    # consider it is a move and remove the origin
                    # annotation.
                    # FIXME: should honour context.action parameter (control/shift)
                    w=context.get_source_widget()
                    if w in self.contents:
                        self.contents.remove(w)
                self.refresh()
                return True
            else:
                print "Unknown target type for drag: %d" % targetType
            return False

        b = gtk.Button()
        b.set_size_request(4, self.button_height)
        b.index=i
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['annotation'], gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK)
        b.connect('drag-data-received', drag_received)

        self.mainbox.pack_start(b, expand=False, fill=False)
        return b

    def append_repr(self, w):
        self.mainbox.pack_start(w, expand=False, fill=False)
        w.update_widget()
        return w

    def play(self, *p):
        """Play the current montage.
        """
        annotation_queue=iter(self.contents)

        def one_step(controller, position):
            """Go to the beginning of the annotation, and program the next jump.
            """
            try:
                w=annotation_queue.next()
                a=w.annotation
                #print "Playing ", a.id
            except StopIteration:
                #print "StopIteration"
                self.controller.update_status('pause')
                for w in self.contents:
                    self.set_widget_active(w, False)
                return False
            # Go to the annotation
            # Change position only if we are not already at the right place
            if abs(position - a.fragment.begin) > 100:
                self.controller.queue_action(self.controller.update_status, 'set', a.begin, notify=False)
            self.controller.queue_action(self.set_widget_active, w, True)
            self.controller.position_update()
            # And program its end.

            # This is a bit convoluted, but it is needed to make sure
            # that the videotime_action does not get removed before
            # even being taken into account (when going backwards),
            # because the controller videotime_action handling removes
            # actions that are before the current time.
            self.controller.register_usertime_delayed_action(0,
                                                             lambda c, b: self.controller.register_videotime_action(a.end, one_step))
            return True

        self.controller.update_status('start', notify=False)
        self.controller.register_usertime_delayed_action(0, one_step)

        return True

    def build_widget(self):
        self.zoom_adjustment=gtk.Adjustment(value=1.0, lower=0.01, upper=2.0)

        def zoom_adj_change(adj):
            # Update the value of self.scale accordingly
            # Get the window size
            if not self.mainbox.window:
                # The widget is not yet realized
                return True
            display_size=self.mainbox.parent.window.get_size()[0]
            # Dropzones are approximately 10 pixels wide, and should
            # be taken into account, but it enforces handling the corner cases
            self.scale.value = 1.0 * self.duration / (display_size / adj.value )

            # Update the zoom combobox value
            self.zoom_combobox.child.set_text('%d%%' % long(100 * adj.value))
            return True

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['uri-list']:
                m=re.match('advene:/adhoc/%d/(.+)' % hash(self),
                           selection.data)
                if m:
                    h=long(m.group(1))
                    l=[ w for w in self.contents if hash(w) == h ]
                    if l:
                        # Found the element. Remove it.
                        self.contents.remove(l[0])
                        self.refresh()
                return True
            else:
                print "Unknown target type for drop: %d" % targetType
            return False

        self.zoom_adjustment.connect('value-changed', zoom_adj_change)

        v=gtk.VBox()

        # Toolbar
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        b=get_small_stock_button(gtk.STOCK_DELETE)
        self.controller.gui.tooltips.set_tip(b, _("Drop an annotation here to remove it from the list"))
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['uri-list'], gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK)
        b.connect('drag-data-received', remove_drag_received)
        ti=gtk.ToolItem()
        ti.add(b)
        tb.insert(ti, -1)

        b=gtk.ToolButton(stock_id=gtk.STOCK_MEDIA_PLAY)
        b.set_tooltip(self.controller.gui.tooltips, _("Play the montage"))
        b.connect('clicked', self.play)
        tb.insert(b, -1)

        def zoom_entry(entry):
            f=entry.get_text()

            i=re.findall(r'\d+', f)
            if i:
                f=int(i[0])/100.0
            else:
                return True
            self.zoom_adjustment.value=f
            return True

        def zoom_change(combo):
            v=combo.get_current_element()
            if isinstance(v, float):
                self.zoom_adjustment.value=v
            return True

        def zoom(i, factor):
            self.zoom_adjustment.value=self.zoom_adjustment.value * factor
            return True

        b=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_OUT)
        b.connect('clicked', zoom, 1.3)
        tb.insert(b, -1)

        b=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_IN)
        b.connect('clicked', zoom, .7)
        tb.insert(b, -1)

        self.zoom_combobox=dialog.list_selector_widget(members=[
                ( f, "%d%%" % long(100*f) )
                for f in [
                    (1.0 / pow(1.5, n)) for n in range(0, 10)
                    ]
                ],
                                                       entry=True,
                                                       callback=zoom_change)
        self.zoom_combobox.child.connect('activate', zoom_entry)
        self.zoom_combobox.child.set_width_chars(4)

        ti=gtk.ToolItem()
        ti.add(self.zoom_combobox)
        tb.insert(ti, -1)

        b=gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_100)
        b.connect('clicked', lambda i: self.zoom_adjustment.set_value(1.0))
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
            self.controller.gui.tooltips.set_tip(b, label)
            for a in set( [ w.annotation for w in self.contents ] ):
                self.controller.notify(event, annotation=a)
            return True
        b=gtk.ToggleToolButton()
        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'highlight.png') ))
        b.set_icon_widget(i)
        b.highlight=True
        b.connect('clicked', toggle_highlight)
        tb.insert(b, -1)

        v.pack_start(tb, expand=False)

        self.mainbox=gtk.HBox()

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
                for ann in sources:
                    if ann is None:
                        self.log("Problem when getting annotation from DND")
                        pass
                    self.insert(ann)
                    # If the origin is from the same montage, then
                    # consider it is a move and remove the origin
                    # annotation
                    w=context.get_source_widget()
                    if w in self.contents:
                        self.contents.remove(w)
                self.refresh()
                return True
            elif targetType == config.data.target_type['annotation-type']:
                at=self.controller.package.get(unicode(selection.data, 'utf8'))
                for a in at.annotations:
                    self.insert(a)
                self.refresh()
                return True
            else:
                print "Unknown target type for drag: %d" % targetType
            return False
        v.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                   gtk.DEST_DEFAULT_HIGHLIGHT |
                                   gtk.DEST_DEFAULT_ALL,
                                   config.data.drag_type['annotation']
                                   + config.data.drag_type['annotation-type'],
                                   gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_MOVE)
        v.connect('drag-data-received', mainbox_drag_received)

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
        sw.add_with_viewport(self.mainbox)
        self.scrollwindow=sw

        v.pack_start(sw, expand=False)

        a=AnnotationDisplay(controller=self.controller)
        f=gtk.Frame(_("Inspector"))
        f.add(a.widget)
        v.add(f)
        self.controller.gui.register_view (a)
        a.set_master_view(self)
        a.widget.show_all()

        v.pack_start(gtk.VBox(), expand=True)

        hb=gtk.HBox()
        l=gtk.Label(_("Total duration:"))
        hb.pack_start(l, expand=False)
        self.duration_label=gtk.Label('??')
        hb.pack_start(self.duration_label, expand=False)
        v.pack_start(hb, expand=False)

        return v
