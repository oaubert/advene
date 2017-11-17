# -*- coding: utf-8 -*-
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
"""Trace timeline.

This widget allows to present event history in a timeline view.
"""

import time
import urllib.request, urllib.parse, urllib.error

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Gtk

from gettext import gettext as _

from advene.model.fragment import MillisecondFragment
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.gui.views import AdhocView
import advene.util.helper as helper
from advene.rules.elements import ECACatalog
import advene.core.config as config
from advene.gui.util import dialog, get_small_stock_button, gdk2intrgba
from advene.model.util.defaultdict import DefaultDict

try:
    import gi
    gi.require_version('GooCanvas', '2.0')
    from gi.repository import GooCanvas
    from gi.repository.GooCanvas import CanvasGroup
except ImportError:
    # Goocanvas is not available. Define some globals in order not to
    # fail the module loading, and use them as a guard in register()
    GooCanvas=None
    CanvasGroup=object

def register(controller):
    if GooCanvas is None:
        controller.log("Cannot register TraceTimeline: the goocanvas python module does not seem to be available.")
    else:
        controller.register_viewclass(TraceTimeline)

name="Trace Timeline view"
INCOMPLETE_OPERATIONS_NAMES = {
            'EditSessionStart': _('Beginning edition'),
            'ElementEditBegin': _('Beginning edition'),
            'ElementEditDestroy': _('Canceling edition'),
            'ElementEditCancel': _('Canceling edition'),
            'EditSessionEnd': _('Canceling edition'),
            'ElementEditEnd': _('Ending edition'),
            'PlayerSeek': _('Moving to'),
        }

TYPE_ABREVIATION=DefaultDict(default='U')
TYPE_ABREVIATION.update({
        Annotation: 'A',
        Relation: 'R',
        AnnotationType: 'AT',
        RelationType: 'RT',
        Schema: 'S',
        View: 'V',
        })

class TraceTimeline(AdhocView):
    """ Class to define a timeline view of traces.
    """
    view_name = _("Traces")
    view_id = 'tracetimeline'
    tooltip=("Traces of Advene Events in a Timeline")
    def __init__ (self, controller=None, parameters=None, package=None):
        super(TraceTimeline, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.tracer = self.controller.tracers[0]
        self.__package=package
        if self.tracer.trace.start:
            self.start_time=self.tracer.trace.start
        elif self.tracer.trace.levels['events']:
            self.start_time = self.tracer.trace.levels['events'][0].time
        else:
            self.start_time = config.data.startup_time
        #self.contextual_actions = (
        #    (_("Refresh"), self.refresh),
        #    )
        if package is None and controller is not None:
            self.__package=controller.package
        self.drag_coordinates=None

        self.active_trace = None
        self.timemarks = []
        # Header canvas
        self.head_canvas = None
        # Main timeline canvas
        self.canvas = None
        # Contextualizing document canvas
        self.doc_canvas = None
        # time context canvas
        self.context_canvas = None
        self.display_values = {} # name : (canvasY, timefactor, obj_l, center value)
        self.selection=[ 0, 0, 0, 0 ]
        self.sel_frame=None
        self.inspector = None
        self.btnl = None
        self.btnlm = None
        self.link_mode = 0
        self.lasty=0
        self.canvasX = 0
        self.context_canvasX = 0
        self.context_canvasY = 850
        self.context_col_width = 1
        self.context_colspacing = 1
        self.context_frame = None
        self.doc_canvas_X = 100
        self.canvasY = 824
        self.head_canvasY = 25
        self.doc_canvas_Y = 45
        self.docgroup = None
        self.obj_l = 5
        self.incr = 500
        self.timefactor = 10.0/824
        self.autoscroll = True
        self.auto_refresh = False # de/activate autorefresh
        self.auto_refresh_keep_100 = False # autorefresh keep 100% ratio
        self.auto_refresh_delay = 1000 # time between 2 refresh in ms
        self.ar_tag = None # autorefresh id value
        self.links_locked = False
        self.now_line=None
        self.sw = None
        self.cols={} # head_group / last event_group
        self.context_cols={} # action_type, color, last_line
        self.context_t_max = time.time()
        for i, act in enumerate(self.tracer.tracemodel['actions']):
            self.cols[act] = (None, None)
            c=gdk2intrgba(Gdk.color_parse(self.tracer.colormodel['actions'][act]))
            self.context_cols[act]=(i, c, None)
        self.col_width = 80
        self.colspacing = 5
        self.active_trace = self.tracer.trace
        self.widget = self.build_widget()
        self.widget.connect("destroy", self.destroy)
        self.populate_head_canvas()
        self.realize_id = self.widget.connect_after('realize', self.widget_realized)
        self.widget.show_all()


    def widget_realized(self, w):
        w.disconnect(self.realize_id)
        #self.receive(self.active_trace)
        self.tracer.register_view(self)
        self.refresh()

    def select_trace(self, trace):
        """Change the selected trace, reinitializing the current display.

        Specific display values are stored in self.display_values for each opened trace.

        @type trace: advene.plugins.tracebuilder.Trace
        @param trace: the trace to display

        """
        if isinstance(trace, int):
            # Interpret it as an index into the self.tracers.traces
            # list
            trace=self.tracer.traces[trace]
        # unlock inspector
        if self.links_locked:
            self.toggle_lock()
            self.inspector.clean()
        # save zoom values
        h = self.canvas.get_allocation().height
        va=self.sw.get_vadjustment()
        vc = (va.get_value() + h/2.0) * self.timefactor
        self.display_values[self.active_trace.name] = (self.canvasY, self.timefactor, self.obj_l, vc)
        self.active_trace = trace
        self.start_time=self.active_trace.start
        # redraw docgroup
        self.docgroup.redraw(self.active_trace)
        # restore zoom values if any
        if self.active_trace.name in self.display_values:
            (self.canvasY, self.timefactor, self.obj_l, vc) = self.display_values[self.active_trace.name]
            self.extend_canvas()
            self.refresh(center = vc)
        else:
            self.refresh()

    def build_widget(self):
        mainbox = Gtk.VBox()
        # trace selector
        def trace_changed(w):
            self.select_trace(w.get_active())
            return True
        self.selector_box = Gtk.HBox()
        self.trace_selector = dialog.list_selector_widget(
            members= [( n, _("%(name)s (%(index)d)") % {
                        'name': t.name,
                        'index': n
                        }) for (n, t) in enumerate(self.tracer.traces)],
            preselect=0,
            callback=trace_changed)
        #self.trace_selector.set_size_request(70,-1)
        self.selector_box.pack_start(self.trace_selector, True, True, 0)
        self.remove_trace_button = get_small_stock_button(Gtk.STOCK_CANCEL)
        def remove_trace(button, event):
            """Remove a trace from the selector list
            """
            tr = self.trace_selector.get_active()
            if tr > 0:
                self.tracer.remove_trace(tr)
                mod= self.trace_selector.get_model()
                if len(self.tracer.traces)<len(mod):
                    mod.remove(mod.get_iter(tr))
                    self.trace_selector.set_active(tr-1)
                #self.select_trace(tr-1)

        self.remove_trace_button.connect('button-press-event', remove_trace)
        self.selector_box.pack_start(self.remove_trace_button, False, True, 0)
        mainbox.pack_start(self.selector_box, False, True, 0)

        quicksearch_options = [False, ['oname','oid','ocontent']] # exact search, where to search
        self.quicksearch_button=get_small_stock_button(Gtk.STOCK_FIND)
        self.quicksearch_entry=Gtk.Entry()
        self.quicksearch_entry.set_text(_('Search'))
        def do_search(button, options):
            """Execute a search query in the active trace.

            Result is added to the selector as a new trace.

            @type options: list
            @param options: a list containing the different options for the search query (see tracebuilder for more infos)
            """
            tr=self.tracer.search(self.active_trace, self.quicksearch_entry.get_text(), options[0], options[1])
            mod= self.trace_selector.get_model()
            if len(self.tracer.traces)>len(mod):
                n = len(self.tracer.traces)-1
                mod.append((_("%(name)s (%(index)s)") % {
                        'name': self.tracer.traces[n].name,
                        'index': n},
                           n, None ))
                self.trace_selector.set_active(n)
            #self.select_trace(tr)
        self.quicksearch_button.connect('clicked', do_search, quicksearch_options)
        self.quicksearch_button.connect('activate', do_search, quicksearch_options)
        def is_focus(w, event):
            """Auto select search text if focused
            """
            if w.is_focus():
                return False
            w.select_region(0, len(w.get_text()))
            w.grab_focus()
            return True
        def is_typing(w, event):
            """Execute search query if <Enter> is pressed in search entry
            """
            #if return is hit, activate quicksearch_button
            if event.keyval == Gdk.KEY_Return:
                self.quicksearch_button.activate()
        self.quicksearch_entry.connect('button-press-event', is_focus)
        self.quicksearch_entry.connect('key-press-event', is_typing)
        self.search_box = Gtk.HBox()
        self.search_box.pack_start(self.quicksearch_entry, False, True, 0)
        self.search_box.pack_start(self.quicksearch_button, False, True, 0)
        #mainbox.pack_start(self.search_box, False, True, 0)

        toolbox = Gtk.Toolbar()
        toolbox.set_orientation(Gtk.Orientation.HORIZONTAL)
        toolbox.set_style(Gtk.ToolbarStyle.ICONS)
        #toolbox.set_icon_size(Gtk.IconSize.MENU)
        #mainbox.pack_start(toolbox, False, True, 0)


        htb = Gtk.HBox()
        htb.pack_start(toolbox, True, True, 0)
        htb.pack_start(self.search_box, False, True, 0)

        mainbox.pack_start(htb, False, True, 0)

        c = len(self.cols)
        self.context_canvasX = c*(self.context_col_width+self.context_colspacing) + 5 # 1+4 for select square

        bx = Gtk.HPaned()
        hbt = Gtk.HBox()
        self.context_canvas = GooCanvas.Canvas()
        self.context_canvas.set_bounds (0, 0, self.context_canvasX, self.context_canvasY)
        self.context_canvas.set_size_request(self.context_canvasX, -1)

        def context_resize(w, alloc):
            """Adapt context canvas on resize (it should always cover the entire allocated space)
            """
            h = w.get_allocation().height
            if h != self.context_canvasY+1.0:
                self.context_canvasY = (h-1.0)
                self.context_canvas.set_bounds(0,0,self.context_canvasX, self.context_canvasY)
                self.context_update_time()
        self.context_canvas.connect('size-allocate', context_resize)

        hbt.pack_start(self.context_canvas, False, True, 0)
        hbt.pack_start(Gtk.VSeparator(), False, False, 0)
        hbt.pack_start(bx, True, True, 0)
        mainbox.pack_start(hbt, True, True, 0)

        timeline_box=Gtk.VBox()
        bx.pack1(timeline_box, resize=False, shrink=False)

        scrolled_win = Gtk.ScrolledWindow ()
        self.sw = scrolled_win
        self.sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.ALWAYS)
        def sw_scrolled(a):
            """Move context selection frame when scrolling the timeline
            """
            self.context_update_sel_frame()
        self.sw.get_vadjustment().connect('value-changed', sw_scrolled)
        self.head_canvas = GooCanvas.Canvas()

        self.canvasX = c*(self.col_width+self.colspacing)
        self.head_canvas.set_bounds (0,0,self.canvasX,self.head_canvasY)
        self.head_canvas.set_size_request(-1, self.head_canvasY)
        timeline_box.pack_start(self.head_canvas, False, False, 0)

        self.canvas = GooCanvas.Canvas()
        self.canvas.set_bounds (0, 0,self.canvasX, self.canvasY)
        self.canvas.set_size_request(200, 25) # important to force a minimum size (else we could have problem with radius of objects < 0)

        self.doc_canvas = GooCanvas.Canvas()
        self.doc_canvas.set_bounds(0,0, self.doc_canvas_X, self.doc_canvas_Y)
        self.doc_canvas.set_size_request(-1, self.doc_canvas_Y)
        self.docgroup = DocGroup(controller=self.controller, canvas=self.doc_canvas, name="Nom du film", x = 15, y=10, w=self.doc_canvas_X-30, h=self.doc_canvas_Y-25, fontsize=8, color_c=0x00000050)
        self.canvas.connect('button-press-event', self.canvas_clicked)
        self.canvas.connect('button-release-event', self.canvas_release)

        def canvas_resize(w, alloc):
            """Adapt the main canvas, head canvas and the drawing (Evengroups, marks, lines) according to the new allocated space.
            """
            if abs(self.canvasX-(alloc.width-20)) < 5:
                # resize every 5 pixels
                return
            ratio = (alloc.width - 20.0) / self.canvasX
            self.canvasX = alloc.width-20.0
            self.col_width = float(self.canvasX)/len(self.cols)-self.colspacing
            #redraw head_canvas
            self.head_canvas.set_bounds (0, 0, self.canvasX, self.head_canvasY)
            self.redraw_head_canvas()
            self.extend_canvas()
            root = self.canvas.get_root_item()
            i=root.get_n_children()-1
            while i>=0:
                c = root.get_child(i)
                if isinstance(c, EventGroup):
                    c.rect.props.x *= ratio
                    c.rect.props.width *= ratio
                    c.w *= ratio
                    c.ol *= ratio
                    c.x *= ratio
                    c.fontsize = c.ol/3
                    c.update_objs(ratiox=ratio, blocked=self.links_locked)
                i -= 1
            for tm in self.timemarks:
                for i in range(0,tm.get_n_children()):
                    tm.get_child(i).props.x *= ratio
                    tm.get_child(i).props.width *= ratio
            self.update_lines()
            if self.now_line:
                self.now_line.props.x *= ratio
                self.now_line.props.width *= ratio

        self.head_canvas.connect('size-allocate', canvas_resize)

        def doc_canvas_resize(w, alloc):
            """Adapt the doc canvas to the new allocated space and redraw the doc group
            """
            # FIXME : maybe we should not delete and recreate it
            # as we can just move it as everything else :D
            #redraw doc_canvas
            self.doc_canvas_X = alloc.width
            self.doc_canvas_Y = alloc.height
            self.doc_canvas.set_bounds(0,0, self.doc_canvas_X, self.doc_canvas_Y)
            self.docgroup.rect.remove()
            self.docgroup.w = self.doc_canvas_X-30
            self.docgroup.h = self.doc_canvas_Y-25
            self.docgroup.rect = self.docgroup.newRect()
            self.docgroup.redraw(self.active_trace)
        self.doc_canvas.connect('size-allocate', doc_canvas_resize)
        scrolled_win.add(self.canvas)

        def show_tooltip(w, x, y, km, tooltip):
            """Show a tooltip according to the item under the cursor
            """
            under_cursor = self.canvas.get_items_at(x, y+w.get_vadjustment().get_value(), False)
            if not under_cursor:
                return False
            for item in under_cursor:
                if item.props.tooltip is not None:
                    tooltip.set_text(item.props.tooltip)
                    return True
            return False
        scrolled_win.set_has_tooltip(True)
        scrolled_win.connect("query-tooltip", show_tooltip)


        timeline_box.pack_start(Gtk.HSeparator(), False, False, 0)
        timeline_box.add(scrolled_win)

        mainbox.pack_start(Gtk.HSeparator(), False, False, 0)

        mainbox.pack_start(self.doc_canvas, False, True, 0)

        btnm = Gtk.ToolButton(stock_id=Gtk.STOCK_ZOOM_OUT)
        btnm.set_tooltip_text(_('Zoom out'))
        btnm.set_label('')
        toolbox.insert(btnm, -1)

        btnp = Gtk.ToolButton(stock_id=Gtk.STOCK_ZOOM_IN)
        btnp.set_tooltip_text(_('Zoom in'))
        btnp.set_label('')
        toolbox.insert(btnp, -1)

        btnc = Gtk.ToolButton(stock_id=Gtk.STOCK_ZOOM_100)
        btnc.set_tooltip_text(_('Zoom 100%'))
        btnc.set_label('')
        toolbox.insert(btnc, -1)
        self.btnl = Gtk.ToolButton()
        self.btnl.set_tooltip_text(_('Toggle links lock'))
        img = Gtk.Image()
        img.set_from_file(config.data.advenefile( ( 'pixmaps', 'unlocked.png') ))
        self.btnl.set_icon_widget(img)
        toolbox.insert(self.btnl, -1)
        self.btnl.connect('clicked', self.toggle_lock)
        #btn to change link mode
        b = Gtk.ToolButton(label='L')
        b.set_tooltip_text(_('Toggle link mode'))
        toolbox.insert(b, -1)
        b.connect('clicked', self.toggle_link_mode)

        def open_trace(b):
            """Open a trace file, add it to the trace selector and make it active
            """
            fname=dialog.get_filename(title=_("Open a trace file"),
                                   action=Gtk.FileChooserAction.OPEN,
                                   button=Gtk.STOCK_OPEN,
                                   default_dir=config.data.path['settings'],
                                   filter='any')
            if not fname:
                return True
            # FIXME: import_trace should return the trace reference,
            self.tracer.import_trace(fname)
            # Refresh combo box
            self.receive(self.tracer.traces[-1])
            self.trace_selector.set_active(len(self.tracer.traces) - 1)
            return True

        btnar = Gtk.ToggleToolButton(stock_id=Gtk.STOCK_REFRESH)
        btnar.set_tooltip_text(_('Toggle auto refresh'))
        btnar.set_label('')
        btnar.connect('clicked', self.toggle_auto_refresh)
        toolbox.insert(btnar, -1)


        s=Gtk.SeparatorToolItem()
        s.set_draw(True)
        toolbox.insert(s, -1)

        b=Gtk.ToolButton(stock_id=Gtk.STOCK_OPEN)
        b.set_tooltip_text(_('Open an existing trace'))
        toolbox.insert(b, -1)
        b.connect('clicked', open_trace)

        # Export trace
        btne = Gtk.ToolButton(stock_id=Gtk.STOCK_SAVE)
        btne.set_tooltip_text(_('Save trace'))
        toolbox.insert(btne, -1)
        btne.connect('clicked', self.export)

        btnopt = Gtk.ToolButton(stock_id=Gtk.STOCK_PREFERENCES)
        btnopt.set_tooltip_text(_('Configuration'))
        btnopt.set_label('')
        #btnopt.connect('clicked', open_options)
        toolbox.insert(btnopt, -1)



        self.inspector = Inspector(self.controller)
        bx.pack2(self.inspector)


        def on_background_scroll(widget, event):
            """Manage scrolling event on timeline.

            Zoom if <ctrl> is pressed.
            Horizontal scrolling if <shift> is pressed.
            Vertical scrolling if nothing special.
            """
            zoom=event.get_state() & Gdk.ModifierType.CONTROL_MASK
            a = None
            if zoom:
                center = event.y * self.timefactor
                if event.direction == Gdk.ScrollDirection.DOWN:
                    zoom_out(widget, center)
                elif  event.direction == Gdk.ScrollDirection.UP:
                    self.zoom_at_ratio(widget, 1.25, center)
                return
            elif event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                # Horizontal scroll
                a = scrolled_win.get_hadjustment()
                incr = a.get_step_increment()
            else:
                # Vertical scroll
                a = scrolled_win.get_vadjustment()
                incr = a.get_step_increment()

            if event.direction == Gdk.ScrollDirection.DOWN:
                a.set_value(helper.clamp(a.get_value() + incr,
                            a.get_lower(),
                            a.get_upper() - a.get_page_size()))
            elif event.direction == Gdk.ScrollDirection.UP:
                a.set_value(helper.clamp(a.get_value() - incr,
                            a.get_lower(),
                            a.get_upper() - a.get_page_size()))
            return True
        self.canvas.connect('scroll-event', on_background_scroll)

        def on_background_motion(widget, event):
            """Manage background motion when left button is clicked.

            if <shift> is pressed, draw a selection frame
            if nothing is pressed, drag the canvas
            """
            if not event.get_state() & Gdk.ModifierType.BUTTON1_MASK:
                return False
            if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                # redraw selection frame
                #self.widget.get_parent_window().set_cursor(Gdk.Cursor.new(Gdk.PLUS))
                if self.selection[0]==0 and self.selection[1]==0:
                    self.selection[0]=event.x
                    self.selection[1]=event.y
                p = GooCanvas.Points([(self.selection[0],self.selection[1]),(self.selection[0],event.y),(event.x,event.y),(event.x,self.selection[1])])
                if self.sel_frame is not None:
                    self.sel_frame.props.points = p
                else:
                    self.sel_frame=GooCanvas.Polyline (parent = self.canvas.get_root_item(),
                                        close_path = True,
                                        points = p,
                                        stroke_color = 0xFFFFFFFF,
                                        line_width = 1.0,
                                        start_arrow = False,
                                        end_arrow = False,
                                        )
                return
            if self.sel_frame:
                self.sel_frame.remove()
                self.sel_frame=None

            if not self.drag_coordinates:
                self.drag_coordinates=(event.x_root, event.y_root)
                self.widget.get_parent_window().set_cursor(Gdk.Cursor.new(Gdk.DIAMOND_CROSS))
                #curseur grab
                return False
            x, y = self.drag_coordinates
            wa=widget.get_allocation()
            a=scrolled_win.get_hadjustment()
            a.set_value(helper.clamp(a.get_value() + x - event.x_root,
                                     a.get_lower(),
                                     a.get_upper() - wa.get_width()))
            a=scrolled_win.get_vadjustment()
            a.set_value(helper.clamp(a.get_value() + y - event.y_root,
                        a.get_lower(),
                                     a.get_upper() - wa.get_width()))

            self.drag_coordinates= (event.x_root, event.y_root)
            return False
        self.canvas.connect('motion-notify-event', on_background_motion)

        def zoom_out(w, center_v=None):
            """Manage zoom when zooming out.

            Verify that we won't too much dezoom.
            @type center_v: number
            @param center_v: the time value on which we need to center
            """
            h = self.canvas.get_allocation().height
            if h/float(self.canvasY)>=0.8:
                self.zoom_100(w)
            else:
                self.zoom_at_ratio(w, 0.8, center_v)

        btnm.connect('clicked', zoom_out)

        btnp.connect('clicked', self.zoom_at_ratio, 1.25, None)

        btnc.connect('clicked', self.zoom_100)

        bx.set_position(self.canvasX+15)
        return mainbox

    def zoom_100(self, w=None):
        """Zoom the timeline to 100% of the canvas space.
        """
        h = self.canvas.get_allocation().height
        ratio = (h-1.0)/self.canvasY
        self.zoom_at_ratio(w, ratio, None)


    def refresh_time(self):
        """Do a refresh of the timeline, extending the canvas to the current time.

        Called every x seconds to refresh continuously.
        Keep 100% aspect ratio if self.auto_refresh_keep_100
        """
        # should return false to stop cycle
        if self.active_trace != self.tracer.trace:
            # we are not currently visualizing the true trace
            # do not disable autorefresh but skip it
            return True
        self.canvasY = (time.time()-self.active_trace.start)/self.timefactor
        self.extend_canvas()
        self.draw_marks()
        if self.autoscroll:
            a = self.sw.get_vadjustment()
            a.set_value(a.get_upper() - a.get_page_size())
        if self.auto_refresh_keep_100:
            self.zoom_100()
        self.context_update_time()
        return self.auto_refresh

    def toggle_auto_refresh(self, w=None):
        """Activate or deactivate autorefresh
        """
        #function to launch / stop autorefresh
        self.auto_refresh = not self.auto_refresh
        if self.auto_refresh:
            self.ar_tag = GObject.timeout_add(self.auto_refresh_delay, self.refresh_time)
            #should change an icon button
            print("auto_refresh started")
        else:
            #should change an icon button
            GObject.source_remove(self.ar_tag)
            print("auto_refresh stopped")

    def show_inspector(self):
        """Expand inspector zone to show it
        """
        self.widget.get_children()[2].get_children()[2].set_position(201) # same as size request for canvas

    def export(self, w):
        """Export current trace to a predefined location
        """
        fname = self.tracer.export()
        d = Gtk.Dialog(title=_("Exporting traces"),
                       parent=self.controller.gui.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK
                                 ))
        l=Gtk.Label(label=_("Export done to\n%s") % fname)
        l.set_selectable(True)
        l.set_line_wrap(True)
        l.show()
        d.vbox.pack_start(l, False, True, 0)
        d.vbox.show_all()
        d.show()
        res=d.run()
        d.destroy()
        return

    def toggle_link_mode(self, w):
        """Change the link mode and propagate it to eventgroups and objgroups
        """
        if self.link_mode == 0:
            self.link_mode = 1
            w.set_label('H')
        else:
            self.link_mode = 0
            w.set_label('L')
        i=0
        root = self.canvas.get_root_item()
        while i < root.get_n_children():
            go = root.get_child(i)
            if isinstance(go, ObjGroup) or isinstance(go, EventGroup):
                go.link_mode=self.link_mode
            i+=1
        self.update_lines()
        return

    def zoom_at_ratio(self, w=None, ratio=1, center_v=None):
        """Recalculate the canvas bounds and each element of the drawing according to the y zoom ratio

        If a center value is given, keep centering the canvas on this value
        """
        h = self.canvas.get_allocation().height
        #print float(h*self.timefactor)/ratio<1, h, self.timefactor
        if float(h*self.timefactor)/ratio<1:
            print("TraceTimeline: minimal zoom is 1s")
            return
        va=self.sw.get_vadjustment()

        if center_v is None:
            vc = (va.get_value() + h/2.0) * self.timefactor
        else:
            vc = center_v
        self.canvasY *= ratio
        self.timefactor *= 1.0/ratio
        self.obj_l *= ratio
        self.extend_canvas()

        root = self.canvas.get_root_item()
        n=root.get_n_children()-1
        while n>=0:
            c = root.get_child(n)
            if isinstance(c, EventGroup):
                c.rect.props.height *= ratio
                c.rect.props.y *= ratio
                c.ol *= ratio
                c.y *= ratio
                c.l *= ratio
                c.fontsize = c.ol/3
                c.update_objs(ratioy=ratio, blocked=self.links_locked)
            n -= 1
        for tm in self.timemarks:
            for i in range(0,tm.get_n_children()):
                tm.get_child(i).props.y *= ratio
        if len(self.timemarks)>2:
            #on a au moins 2 lignes temporelles
            if ratio > 1 and self.timemarks[1].get_child(0).props.y - self.timemarks[0].get_child(0).props.y > h/4.0 or self.timemarks[1].get_child(0).props.y - self.timemarks[0].get_child(0).props.y < h/6.0:
                #elles sont trop espacées, on recalcule.
                for t in self.timemarks:
                    t.remove()
                self.timemarks=[]
                self.draw_marks()
        self.update_lines()
        va.set_value(helper.clamp(vc/self.timefactor-va.get_page_size()/2.0,
                                  va.get_lower(),
                                  va.get_upper() - va.get_page_size()))

    def zoom_on(self, w=None, canvas_item=None):
        """Zoom on an item (ObjGroup or EventGroup) in the canvas
        """
        min_y = -1
        max_y = -1
        if hasattr(canvas_item, 'rect'):
            # eventgroup
            min_y = canvas_item.rect.get_bounds().y1
            max_y = canvas_item.rect.get_bounds().y2
        elif hasattr(canvas_item, 'rep'):
            # objgroup
            obj_id = canvas_item.cobj['id']
            if obj_id is None:
                return
            i=0
            # listing all eventgroup containing this item
            root = self.canvas.get_root_item()
            egl=[]
            while i < root.get_n_children():
                eg = root.get_child(i)
                if isinstance(eg, EventGroup):
                    for op in eg.event.operations:
                        #check if an operation concerns this item
                        if op.concerned_object['id'] == obj_id:
                            egl.append(eg)
                i+=1
            for c in egl:
                #we take max / min Y from eventgroups only because when resizing objgroupsmight also disappear...

                y_mi = c.rect.get_bounds().y1
                y_ma = c.rect.get_bounds().y2 #y1 + c.rect.props.height why that ???
                if min_y == -1:
                    min_y = y_mi
                min_y = min(min_y, y_mi)
                max_y = max(max_y, y_ma)

        h = self.canvas.get_allocation().height
        # if h < 10, the widget is not fully drawn yet, we must use an arbitrary value
        if h < 10:
            h=200
        # 20.0 to keep a little space between border and object
        va=self.sw.get_vadjustment()
        rapp = h / (20.0 + max_y - min_y)
        vc = self.timefactor * ((min_y + max_y) / 2.0) * (va.get_upper() / self.canvasY)
        self.zoom_at_ratio(None, rapp, vc)


    #FIXME : types / schema / views
    def recreate_item(self, w=None, obj_group=None):
        """Allows to recreate a deleted Advene object from the trace.

        Currently only works for annotations and relations
        """
        c = obj_group.operation.content
        if obj_group.cobj['type'] == Annotation:
            # t : content a parse
            # b : content a parse
            # d : content a parse
            t=None
            b=d=0
            t = self.controller.package.get_element_by_id(obj_group.cobj['cid'])
            if t is None or not isinstance(t, AnnotationType):
                print("No corresponding type, creation aborted")
                return
            a = int(c.find("begin=")+6)
            aa = int(c.find("\n", a))
            b = int(c[a:aa])
            a = int(c.find("end=")+4)
            aa = int(c.find("\n", a))
            e = int(c[a:aa])
            d = e-b
            a = int(c.find("content=")+9)
            aa = len(c)-1
            cont = c[a:aa]
            an = self.controller.package.createAnnotation(
                ident=obj_group.cobj['id'],
                type=t,
                author=config.data.userid,
                date=self.controller.get_timestamp(),
                fragment=MillisecondFragment(begin=b,
                                             duration=d))
            an.content.data = urllib.parse.unquote(cont.encode('utf-8'))
            self.controller.package.annotations.append(an)
            self.controller.notify("AnnotationCreate", annotation=an, comment="Recreated from Trace")
        elif obj_group.cobj['type'] == Relation:
            t=None
            t = self.controller.package.get_element_by_id(obj_group.cobj['cid'])
            if t is None or not isinstance(t, RelationType):
                print("No corresponding type, creation aborted")
                return
            a = int(c.find("source=")+7)
            aa = int(c.find("\n", a))
            s = c[a:aa]
            source = self.controller.package.get_element_by_id(s)
            a = int(c.find("dest=")+5)
            aa = int(c.find("\n", a))
            d = c[a:aa]
            dest = self.controller.package.get_element_by_id(d)
            a = int(c.find("content=")+9)
            aa = len(c)-1
            cont = c[a:aa]
            if source is None or dest is None or not isinstance(source, Annotation) or not isinstance(dest, Annotation):
                print("Source or Destination missing, creation aborted")
                return
            r = self.controller.package.createRelation(ident=obj_group.cobj['id'],
                                 members=(source, dest),
                                 type=t)
            r.content.data = urllib.parse.unquote(cont.encode('utf-8'))
            self.controller.package.relations.append(r)
            self.controller.notify("RelationCreate", relation=r)
        else:
            print('TODO')

        return

    def edit_item(self, w=None, obj=None):
        """Open advene edit window to edit the selected element
        """
        if obj is not None:
            self.controller.gui.edit_element(obj)

    def goto(self, w=None, time=None):
        """Navigate in the movie to the time

        @type time: number
        @param time: the timestamp we want to reach
        """
        self.controller.update_status("seek", time)

    def canvas_release(self, w, ev):
        """Manage the release of mouse buttons on the canvas

        Remove the selection frame, and zoom if <shift> pressed
        """
        if self.sel_frame:
            self.sel_frame.remove()
            self.sel_frame=None
        if ev.state & Gdk.ModifierType.SHIFT_MASK:
            if self.selection[0]==0 and self.selection[1]==0:
                #not a simple click + maj + release
                return
            self.selection[2]=ev.x
            self.selection[3]=ev.y
            self.widget.get_parent_window().set_cursor(None)
            min_y=min(self.selection[1], self.selection[3])
            max_y=max(self.selection[1], self.selection[3])
            h = self.canvas.get_allocation().height
            va=self.sw.get_vadjustment()
            if (max_y-min_y)* self.timefactor<1:
                #must be a misclick, zoom < 1s
                self.selection = [ 0, 0, 0, 0]
                return
            rapp = h / float(max_y - min_y)
            vc = self.timefactor * ((min_y + max_y) / 2.0) * (va.get_upper() / self.canvasY)
            self.zoom_at_ratio(None, rapp, vc)
            self.selection = [ 0, 0, 0, 0]
            return
        if ev.button == 1:
            self.drag_coordinates=None
            self.widget.get_parent_window().set_cursor(None)

    def canvas_clicked(self, w, ev):
        """Manage mouse buttons on the canvas

        Draw a selection frame if <shift> pressed and left click
        Display contextual menu according to under the cursor items if right click
        """
        if ev.state & Gdk.ModifierType.SHIFT_MASK:
            self.selection = [ ev.x, ev.y, 0, 0]
            if self.sel_frame:
                self.sel_frame.remove()
                self.sel_frame=None
            self.widget.get_parent_window().set_cursor(Gdk.Cursor.new(Gdk.PLUS))
            return
        obj_gp = None
        evt_gp = None
        l = self.canvas.get_items_at(ev.x, ev.y, False)
        if l is not None:
            for o in l:
                go = o.get_parent()
                if isinstance(go, ObjGroup):
                    obj_gp = go
                if isinstance(go, EventGroup):
                    evt_gp = go
        if obj_gp is None and evt_gp is None:
            return
        if ev.button == 3:
            #clic droit sur un item
            menu=Gtk.Menu()
            if obj_gp is not None:
                if obj_gp.rep is not None:
                    i=Gtk.MenuItem(_("Zoom and center on linked items"))
                    i.connect("activate", self.zoom_on, obj_gp)
                    menu.append(i)
                obj = objt = None
                if obj_gp.cobj['id'] is not None:
                    obj = self.controller.package.get_element_by_id(obj_gp.cobj['id'])
                if obj_gp.cobj['cid'] is not None:
                    objt = self.controller.package.get_element_by_id(obj_gp.cobj['cid'])
                if obj is not None:
                    i=Gtk.MenuItem(_("Edit item"))
                    i.connect("activate", self.edit_item, obj)
                    menu.append(i)
                elif objt is not None:
                    i=Gtk.MenuItem(_("Recreate item"))
                    i.connect("activate", self.recreate_item, obj_gp)
                    menu.append(i)
                m = Gtk.Menu()
                mt= []

                if obj_gp.operation.movietime not in mt:
                    n=''
                    if obj_gp.operation.name in INCOMPLETE_OPERATIONS_NAMES:
                        n = INCOMPLETE_OPERATIONS_NAMES[obj_gp.operation.name]
                    else:
                        n = ECACatalog.event_names[obj_gp.operation.name]
                    mt.append(obj_gp.operation.movietime)
                    i = Gtk.MenuItem("%s (%s)" % (time.strftime("%H:%M:%S", time.gmtime(obj_gp.operation.movietime/1000)), n))
                    i.connect("activate", self.goto, obj_gp.operation.movietime)
                    m.append(i)
                i=Gtk.MenuItem(_("Go to..."))
                i.set_submenu(m)
                menu.append(i)
            if evt_gp is not None:
                i=Gtk.MenuItem(_("Zoom on action"))
                i.connect("activate", self.zoom_on, evt_gp)
                menu.append(i)
                if obj_gp is None:
                    m = Gtk.Menu()
                    mt= []
                    for op in evt_gp.event.operations:
                        if op.movietime not in mt:
                            n=''
                            if op.name in INCOMPLETE_OPERATIONS_NAMES:
                                n = INCOMPLETE_OPERATIONS_NAMES[op.name]
                            else:
                                n = ECACatalog.event_names[op.name]
                            mt.append(op.movietime)
                            i = Gtk.MenuItem("%s (%s)" % (time.strftime("%H:%M:%S", time.gmtime(op.movietime/1000)), n))
                            i.connect("activate", self.goto, op.movietime)
                            m.append(i)
                    i=Gtk.MenuItem(_("Go to..."))
                    i.set_submenu(m)
                    menu.append(i)
            menu.show_all()
            menu.popup_at_pointer(None)
        elif ev.button == 1:
            if obj_gp is not None:
                self.toggle_lock(w=obj_gp)
            else:
                self.toggle_lock(w=evt_gp)

    def toggle_lock(self, w=None):
        """Draw or remove links between items

        Blocked object handlers accordingly
        """
        self.links_locked = not self.links_locked
        if self.links_locked:
            #self.btnl.set_label(_('Locked'))
            img = self.btnl.get_icon_widget()
            img.set_from_file(config.data.advenefile( ( 'pixmaps', 'locked.png') ))
            img.show()
            self.btnl.set_icon_widget(img)
        else:
            #self.btnl.set_label(_('Unlocked'))
            img = self.btnl.get_icon_widget()
            img.set_from_file(config.data.advenefile( ( 'pixmaps', 'unlocked.png') ))
            img.show()
            self.btnl.set_icon_widget(img)
        i=0
        root = self.canvas.get_root_item()
        while i < root.get_n_children():
            go = root.get_child(i)
            if isinstance(go, ObjGroup) or isinstance(go, EventGroup):
                if self.links_locked:
                    #print "lock %s" % go
                    go.handler_block(go.handler_ids['enter-notify-event'])
                    go.handler_block(go.handler_ids['leave-notify-event'])
                else:
                    #print "unlock %s" % go
                    go.handler_unblock(go.handler_ids['enter-notify-event'])
                    go.handler_unblock(go.handler_ids['leave-notify-event'])
                    # if selected group, force leave
                    if hasattr(go, 'center_sel') and go.center_sel:
                        go.on_mouse_leave(None, None, None)
                    if go == w:
                        go.on_mouse_over(None, None, None)
            i+=1

    def draw_marks(self):
        """Draw the time marks on the main canvas
        """
        # verifying start time (changed if an import occured)
        self.start_time = self.active_trace.start
        #Calculating where to start from and the increment between marks
        tinc = 60
        if not self.timemarks:
            wa = self.canvas.get_parent().get_allocation().height

            if wa > 100:
                tinc = wa/5.0 # 5 marks in the widget
            else: # when closing and reopening the view
                tinc = 2 / self.timefactor
            t=tinc
        else:
            if len(self.timemarks)>=2:
               tinc=self.timemarks[1].get_child(0).get_bounds().y1-self.timemarks[0].get_child(0).get_bounds().y1
            else:
               tinc=self.timemarks[0].get_child(0).get_bounds().y1
            t=self.timemarks[-1].get_child(0).get_bounds().y1+tinc
        ld = GooCanvas.LineDash([5.0, 20.0])
        while t < self.canvasY:
            #print self.start_time, t, t*self.timefactor
            txt = time.strftime("%H:%M:%S",time.localtime(self.start_time+t*self.timefactor))
            mgroup = GooCanvas.Group(parent=self.canvas.get_root_item())
            a=GooCanvas.polyline_new_line(mgroup,
                                        0,
                                        t,
                                        self.canvasX,
                                        t,
                                        line_dash=ld,
                                        line_width = 0.2)
            a.props.tooltip=txt
            a=GooCanvas.Text(parent = mgroup,
                        text = txt,
                        x = 0,
                        y = t-5,
                        width = -1,
                        anchor = Gtk.ANCHOR_W,
                        fill_color_rgba=0x121212FF,
                        font = "Sans 7")
            a.props.tooltip=txt
            a=GooCanvas.Text(parent = mgroup,
                        text = txt,
                        x = self.canvasX-4,
                        y = t-5,
                        width = -1,
                        fill_color_rgba=0x121212FF,
                        anchor = Gtk.ANCHOR_E,
                        font = "Sans 7")
            a.props.tooltip=txt
            self.timemarks.append(mgroup)
            mgroup.lower(None)
            t+=tinc
        return

    def redraw_head_canvas(self):
        """Clean and redraw the head canvas
        """
        root = self.head_canvas.get_root_item()
        while root.get_n_children()>0:
            root.remove_child (0)
        self.populate_head_canvas()
        return

    def populate_head_canvas(self):
        """Create head canvas groups according to the trace model
        """
        offset = 0
        for c in self.tracer.tracemodel['actions']:
            etgroup = HeadGroup(self.controller, self.head_canvas, c, (self.colspacing+self.col_width)*offset, 0, self.col_width, 8, gdk2intrgba(Gdk.color_parse(self.tracer.colormodel['actions'][c])))
            (og, oa) = self.cols[c]
            self.cols[c]=(etgroup, oa)
            offset += 1
        return

    def destroy(self, source=None, event=None):
        """Intercept the destroy event to unregister the view and suspend the autorefresh
        """
        if self.auto_refresh:
            self.toggle_auto_refresh()
        self.tracer.unregister_view(self)
        return False

    def extend_canvas(self):
        """Extend the main canvas to display time until now
        """
        self.canvas.set_bounds (0, 0, self.canvasX, self.canvasY)
        if self.now_line:
            self.now_line.props.y=self.canvasY-1


    def refresh(self, center = None):
        """Refresh the drawing of the main canvas

        Remove everything on the main canvas and redraw them
        Should only be used when opening the view / changing selected trace

        @type center: number
        @param center: the time value on which we need to center
        """
        # method to refresh the canvas display
        # 1/ clean the canvas, memorizing selected item
        # 2/ recalculate the canvas area according to timefactor and last action
        # 3/ redraw time separators
        # 4/ redraw each action
        # 5/ recenter the canvas according to previous centering
        # 6/ reselect selected item
        # 7/ re-deactivate locked_links
        # center : the timestamp on which the display needs to be centered
        #print "----------------REFRESH START-----------------"
        if self.links_locked:
            self.toggle_lock()
            self.inspector.clean()
        self.widget.get_parent_window().set_cursor(Gdk.Cursor.new(Gdk.CursorType.WATCH))
        root=self.canvas.get_root_item()
        while root.get_n_children()>0:
            c = root.get_child(0)
            c.remove()
        self.timemarks=[]
        self.context_clean()
        for c in self.cols:
            h,l = self.cols[c]
            self.cols[c]=(h,None)
        self.now_line = GooCanvas.polyline_new_line(root,
                                        0,
                                        self.canvasY-1,
                                        self.canvasX,
                                        self.canvasY-1,
                                        line_width = 3,
                                        stroke_color_rgba=0xFF0000FF)
        for lvl in self.active_trace.levels:
            if lvl == 'event':
                for i in self.active_trace.levels[lvl]:
                    self.receive_int(self.active_trace, event=i, operation=None, action=None)
            elif lvl == 'actions':
                for i in self.active_trace.levels[lvl]:
                    self.receive_int(self.active_trace, event=None, operation=None, action=i)
                    # operations are processed within the action
        self.draw_marks()
        if center:
            va=self.sw.get_vadjustment()
            va.value = center/self.timefactor-va.get_page_size()/2.0
            if va.value<va.lower:
                va.value=va.lower
            elif va.value>va.get_upper()-va.get_page_size():
                va.value=va.get_upper()-va.get_page_size()
        self.context_update_time()
        self.widget.get_parent_window().set_cursor(None)
        #print "----------------REFRESH END-----------------"
        return


    def receive(self, trace, event=None, operation=None, action=None):
        """This function is called by the tracer to update the gui. It is registered in the trace when creating the class.

        It should always return False to avoid 100% cpu consumption.

        @type trace: advene.plugins.tracebuilder.Trace
        @param trace: the full trace to be managed
        @type event: advene.plugins.tracebuilder.Event
        @param event: the new or latest modified event
        @type operation: advene.plugins.tracebuilder.Operation
        @param operation: the new or latest modified operation
        @type action: advene.plugins.tracebuilder.Action
        @param action: the new or latest modified action
        """
        if self.active_trace == trace:
            self.receive_int(trace, event, operation, action)
        if not (event or operation or action):
            tm = self.trace_selector.get_model()
            n=len(tm)
            if n < len(self.tracer.traces):
                tm.append((_("%(name)s (%(index)s)") % {
                        'name': self.tracer.traces[n].name,
                        'index': n},
                           n, None ))
        return False

    def receive_int(self, trace, event=None, operation=None, action=None):
        """Manage each new event in the trace.

        @type trace: advene.plugins.tracebuilder.Trace
        @param trace: the full trace to be managed
        @type event: advene.plugins.tracebuilder.Event
        @param event: the new or latest modified event
        @type operation: advene.plugins.tracebuilder.Operation
        @param operation: the new or latest modified operation
        @type action: advene.plugins.tracebuilder.Action
        @param action: the new or latest modified action

        @rtype: EventGroup
        @return: the newly created or updated EventGroup
        """
        #print "Debug: received : action %s, operation %s, event %s" % (action, operation, event)
        ev = None
        if event and (event.name=='DurationUpdate' or event.name=='MediaChange'):
            #new film, update duration
            self.docgroup.changeMovielength(trace)
        if (operation or event) and action is None:
            # no action changed, return
            return ev
        if operation:
            # new operation, add it on docgroup
            self.docgroup.addLine(operation.movietime)
        if action is None:
            # no event, operation or action, this is a refresh query, redraw screen
            return ev
        h,l = self.cols[action.name]
        #print "INIT %s" % l
        if (l and not l.get_canvas()):
            print("Tracetimeline : Synchronization between tracer and view lost - droping event")
            #to avoid crashing when tracebuilder is calling receive of a tracetimeline being closed
            return
        color = h.color_c
        if l and l.event == action:
            # action corresponding to the last action of this type, update the drawing
            #calculating old length
            b=l.rect.get_bounds()
            oldlength = b.y2-b.y1
            #calculating new length
            newlength = float(action.time[1]-action.time[0])/self.timefactor
            if b.y1+newlength >= self.canvasY-1:
                #need to expand canvas
                self.canvasY = b.y1+newlength+1
                self.extend_canvas()
                self.draw_marks()
            #transofrm item
            l.rect.props.height=newlength
            #update already existing / not existing items before adding the new one
            l.update_objs(blocked=self.links_locked)
            ev=l
            #print "UPD %s" % ev
        else:
            #totally new action
            # getting x bound from header
            x = h.rect.get_bounds().x1+1
            #calculating y0 and length
            y = float(action.time[0]-self.start_time)/self.timefactor
            length = float(action.time[1]-action.time[0])/self.timefactor
            if y+length >= self.canvasY-1:
                #need to expand canvas
                self.canvasY = y+length+1
                self.extend_canvas()
                self.draw_marks()
            ev = EventGroup(self.link_mode, self.controller, self.inspector, self.canvas, self.docgroup, None, action, x, y, length, self.col_width, self.obj_l, 14, color, self.links_locked)
            self.cols[action.name]=(h,ev)
            #print "NEW %s" % ev
        self.update_lines()
        self.canvas.show()
        if self.autoscroll:
            a = self.sw.get_vadjustment()
            a.set_value(a.get_upper()-a.get_page_size())
        if l and l.event == action:
            self.context_update_line(action)
        else:
            self.context_add_line(action)
        return ev

    def update_lines(self):
        """Search for the Objgroup containing lines and update them
        """
        if not self.inspector.item:
            #No selected item
            if self.links_locked and not self.inspector.action:
                #No item, no action, but links_locked
                self.toggle_lock()
            return
        else:
            self.inspector.item.update_lines()


    def find_group(self, observed):
        """Find an avent Group according to an action or operation

        @type observed: advene.plugins.tracebuilder.Operation or advene.plugins.tracebuilder.Action
        @param observed: an action or operation to find

        @rtype: EventGroup
        @return: an event group containing the operation or corresponding to the action
        """
        g=None
        root = self.canvas.get_root_item()
        i=0
        while i < root.get_n_children():
            g = root.get_child(i)
            i+=1
            if isinstance(g, EventGroup):
                if observed == g.event:
                    return g
                if observed in g.event.operations:
                    return g
        return None


    """Context related functions
    """

    def context_clean(self):
        """Clean the context canvas
        """
        root=self.context_canvas.get_root_item()
        while root.get_n_children()>0:
            c = root.get_child(0)
            c.remove()
        self.context_frame = None
        self.context_t_max = self.canvasY*self.timefactor + self.active_trace.start
        for act in self.context_cols:
            (i, c, toto) = self.context_cols[act]
            self.context_cols[act]=(i, c, None)


    def context_update_time(self):
        """Update the context canvas according to current time
        """
        ratio = float((self.context_t_max-self.active_trace.start))/(self.canvasY*self.timefactor)
        self.context_t_max = self.canvasY*self.timefactor + self.active_trace.start
        if ratio>0:
            #else there should be nothing drawn
            root = self.context_canvas.get_root_item()
            n = 0
            while n < root.get_n_children():
                l=root.get_child(n)
                n+=1
                if isinstance(l,GooCanvas.Polyline):
                    l.props.y *= ratio
                    l.props.height *= ratio
        self.context_update_sel_frame()

    def context_add_line(self, action):
        """Add a line corresponding to the action in the context canvas.

        @type action: advene.plugins.tracebuilder.Action
        @param action: the action to add to the context
        """
        self.context_update_time()
        y1 = float(action.time[0]-self.active_trace.start)*self.context_canvasY/(self.context_t_max-self.active_trace.start)
        y2 = float(action.time[1]-self.active_trace.start)*self.context_canvasY/(self.context_t_max-self.active_trace.start)
        (i,color,line)=self.context_cols[action.name]
        x = 3+2*i
        l = GooCanvas.polyline_new_line(self.context_canvas.get_root_item(),
                                        x,
                                        y1,
                                        x,
                                        y2,
                                        stroke_color_rgba = color,
                                        line_width = 1.0)
        self.context_cols[action.name]=(i,color,l)
        return

    def context_update_line(self, action=None):
        """ Update a line corresponding to the action in the context canvas.

        @type action: advene.plugins.tracebuilder.Action
        @param action: the action to update in the context
        """
        self.context_update_time()
        (i,color,line)=self.context_cols[action.name]
        y1 = float(action.time[0]-self.active_trace.start)*self.context_canvasY/(self.context_t_max-self.active_trace.start)
        y2 = float(action.time[1]-self.active_trace.start)*self.context_canvasY/(self.context_t_max-self.active_trace.start)
        line.props.height = y2-y1
        return

    def context_draw_sel_frame(self):
        """Draw the selection frame on context canvas, corresponding to what is displayed in the trace timeline
        """
        #refresh canvas bounds
        self.context_frame = GooCanvas.Rect (parent = self.context_canvas.get_root_item(),
                                    x = 0,
                                    y = 0,
                                    width = self.context_canvasX,
                                    height = self.context_canvasY,
                                    fill_color_rgba = 0xFFFFFF00,
                                    stroke_color = 0xFFFFFFFF,
                                    line_width = 1.0)
        return

    def context_update_sel_frame(self):
        """Update the context canvas selection frame.
        """
        if not self.context_frame:
            self.context_draw_sel_frame()
        h = self.canvas.get_allocation().height
        va=self.sw.get_vadjustment()
        tmin = va.value * self.timefactor
        tmax = (va.value + h) * self.timefactor
        r1 = tmin / (self.context_t_max-self.active_trace.start)
        r2=min(1,tmax / (self.context_t_max-self.active_trace.start))
        y1 = self.context_canvasY*r1
        y2 = self.context_canvasY*r2
        self.context_frame.props.y=y1
        self.context_frame.props.height = max(0, y2-y1)
        return


class HeadGroup (CanvasGroup):
    """Group containing a rectangle and a name used to display headers.
    """
    def __init__(self, controller=None, canvas=None, name="N/A", x = 5, y=0, w=90, fontsize=14, color_c=0x00ffff50):
        CanvasGroup.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        #self.name=name[0:2]
        self.name=name[0:5]
        self.w = 90
        self.color_s = "black"
        self.color_c = color_c
        self.fontsize=fontsize
        self.rect = GooCanvas.Rect (parent = self,
                                    x = x,
                                    y = y,
                                    width = self.w,
                                    height = 20,
                                    fill_color_rgba = 0xFFFFFF00,
                                    stroke_color = 0xFFFFFF00,
                                    line_width = 0)
        self.text = GooCanvas.Text (parent = self,
                                        text = self.name,
                                        x = x+w/2,
                                        y = y+15,
                                        width = -1,
                                        anchor = Gtk.ANCHOR_CENTER,
                                        font = "Sans Bold %s" % str(self.fontsize))

        def change_name(self, name):
            """Change the name of the head group.

            @type name: string
            @param name: new name, 5 max chars
            """
            self.name=name[0:5]
            self.text.props.text=self.name
            return

        def change_font(self, font):
            """Change the font of the head group.

            @type font: string
            @param font: new font, whithout size
            """
            self.text.props.font="%s %s" % (font, str(self.fontsize))
            return

class EventGroup (CanvasGroup):
    """Group containing a rectangle, commentmarks and ObjGroups used to display an action
    """
    def __init__(self, link_mode=0, controller=None, inspector=None, canvas=None, dg=None, type=None, event=None, x =0, y=0, l=1, w=90, ol=5, fontsize=6, color_c=0x00ffffff, blocked=False):
        CanvasGroup.__init__(self, parent = canvas.get_root_item ())
        self.canvas = canvas
        self.controller=controller
        self.inspector = inspector
        self.event=event
        self.type=type
        self.link_mode=link_mode
        self.commentMark = None
        self.dg = dg
        self.rect = None
        self.color_sel = 0xD9D919FF
        self.color_c = color_c
        self.color_o = 0xADEAEAFF
        self.color_m = 0x00ffbfff
        self.color = "black"
        self.fontsize=fontsize
        self.x = x
        self.y = y
        self.l = l
        self.ol = ol # object length #TODO verif pourquoi on le transmet d'avant
        self.w = w
        self.rect = self.newRect (self.color, self.color_c)
        self.objs=[]
        #self.lines = []
        self.update_objs(blocked=blocked)
        self.handler_ids = {
        'enter-notify-event':None,
        'leave-notify-event':None,
        }
        #self.connect('button-press-event', self.on_click)
        self.handler_ids['enter-notify-event'] = self.connect('enter-notify-event', self.on_mouse_over)
        self.handler_ids['leave-notify-event'] = self.connect('leave-notify-event', self.on_mouse_leave)
        if blocked:
            self.handler_block(self.handler_ids['enter-notify-event'])
            self.handler_block(self.handler_ids['leave-notify-event'])
        if self.event.comment!='':
            self.addCommentMark()

    def newRect(self, color, color_c):
        """Create a new rectangle for the group

        @type color: number
        @param color: stroke color rgb
        @type color_c: number
        @param color_c: fill color rgba

        @rtype: GooCanvas.Rect
        @return: the new rect
        """
        return GooCanvas.Rect (parent = self,
                                    x = self.x,
                                    y = self.y,
                                    width = self.w,
                                    height = self.l,
                                    fill_color_rgba = color_c,
                                    stroke_color = color,
                                    line_width = 2.0)

    def addObj(self, op, blocked):
        """Add objgroups to the group, if they can be displayed.

        @type op: advene.plugins.tracebuilder.Operation
        @param op: the operation to add as obj
        @type blocked: bool
        @param blocked: True if handlers should be blocked at creation
        """
        x=self.rect.get_bounds().x1+3
        ratio = float((self.event.time[1]-self.event.time[0]))/self.rect.props.height
        y = (op.time-self.event.time[0]) / ratio + self.rect.get_bounds().y1

        l = self.rect.props.height
        w = self.rect.props.width
        ol = min(l-3, float(w)/2 - 3)
        if ol < 6:
            #not enough space to display 1 item, return
            return
        true_y=y
        if self.event.time[1] == op.time:
            #last operation, need to change y to display it
            y = y - ol -5
        #FIXME fontsize according to object length with a min of 6 and a max of ??,
        self.fontsize = ol/3
        self.ol = ol
        if y + ol >= self.rect.get_bounds().y2-2 or y < self.rect.get_bounds().y1-1:
            # not in the rectangle
            return
        self.objs.append( ObjGroup(self.link_mode, self.controller, self.inspector, self.canvas, self.dg, x, y, ol/2, self.fontsize, op, blocked))
        if true_y != y:
            #need to store true y value
            self.objs[-1].true_y = true_y

        return

    def update_objs(self, ratiox=1,ratioy=1, blocked=False):
        """Update Objgroups belonging to the group

        @type ratiox: number
        @param ratiox: the x zoom ratio
        @type ratioy: number
        @param ratioy: the y zoom ratio
        @type blocked: bool
        @param blocked: True if handlers should be blocked at creation
        """
        w = self.rect.props.width
        l = self.rect.props.height
        if l < 10:
            #not enough space
            for c in self.objs:
                c.remove()
            self.objs=[]
            if self.commentMark:
                self.removeCommentMark()

        else:
            if not self.objs:
                self.drawObjs(blocked)
            else:
                ol = min(l-3, float(w)/2 - 3)
                self.ol=ol
                already_existing_op=[]
                to_be_removed = []
                for c in self.objs:
                    already_existing_op.append(c.operation)
                    if c.true_y != c.y: # was the last operation, restore the true value
                        c.y=c.true_y
                    c.x *= ratiox
                    c.y *= ratioy
                    c.true_y = c.y # we need to remember this value for the next update
                    c.r = ol/2
                    c.fontsize = 2*c.r/3
                    if self.event.time[1] == c.operation.time:
                        #last operation, need to change y to display it
                        c.y = self.rect.get_bounds().y2 - ol -3
                    if c.y + ol >= self.rect.get_bounds().y2-2:
                        # not in the rectangle
                        to_be_removed.append(c)
                        continue
                    if c.y < self.rect.get_bounds().y1-1:
                        #FIXME it may introduce some gap between true pos and this pos, but theorically, it should never be <, so ...
                        c.y = self.rect.get_bounds().y1-1
                    if not c in to_be_removed:
                        c.move_group()
                for c in to_be_removed:
                    self.objs.remove(c)
                    c.remove()
                for op in self.event.operations:
                    #obj may not already exist for this op
                    if op not in already_existing_op:
                        self.addObj(op, blocked)
            if self.commentMark:
                self.commentMark.props.x *= ratiox
                self.commentMark.props.y *= ratioy
            elif self.event.comment!='':
                self.addCommentMark()

    def drawObjs(self, blocked):
        """Add objgroup for each operation of the action of the group.

        @type blocked: bool
        @param blocked: True if handlers should be blocked at creation
        """
        for op in self.event.operations:
            self.addObj(op, blocked)


    def on_mouse_over(self, w, target, event):
        """Change marks and inspector informations according to the group.
        """
        self.fill_inspector()
        self.dg.changeMarks(action=self.event)
        return

    def on_mouse_leave(self, w, target, event):
        """Empty marks and inspector informations
        """
        self.clean_inspector()
        self.dg.changeMarks()
        return

    def clean_inspector(self):
        """Empty inspector
        """
        self.inspector.clean()

    def fill_inspector(self):
        """Fill inspector with informations concerning this group
        """
        self.inspector.fillWithAction(self)

    def removeCommentMark(self):
        """Remove comment mark from this group
        """
        if self.commentMark:
            self.commentMark.remove()
            self.commentMark = None

    def addCommentMark(self):
        """Add comment mark to this group if it has a comment
        """
        if not self.commentMark:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                        ( ('pixmaps', 'traces', 'msg.png')), 16, 16)
            self.commentMark = GooCanvas.Image(parent=self,
                                                width=16,
                                                height=16,
                                                x=self.x,
                                                y=self.y,
                                                pixbuf=pb)
        self.commentMark.props.tooltip=self.event.comment


class ObjGroup (CanvasGroup):
    """Group used to display informations on an operation
    """
    def __init__(self, link_mode=0, controller=None, inspector=None, canvas=None, dg=None, x=0, y=0, r=4, fontsize=5, op=None, blocked=False):
        CanvasGroup.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.rep = None
        self.text = None
        self.canvas = canvas
        self.dg=dg
        self.link_mode=link_mode
        self.inspector = inspector
        self.color_sel = 0xD9D919FF
        self.stroke_color_sel = "red"
        self.color_f = 0xFFFFFFFF
        self.color_s = "black"
        self.fontsize = fontsize
        self.operation = op
        self.cobj = op.concerned_object
        self.x = x
        self.y = y
        self.r = r
        self.true_y = y # needed to display last operation correctly
        self.rep = None
        self.text = None
        # trying to get the item color in advene
        if self.cobj['id']:
            temp_it = self.controller.package.get_element_by_id(self.cobj['id'])
            temp_c = self.controller.get_element_color(temp_it)
            if temp_c is not None:
                self.color_f = gdk2intrgba(Gdk.color_parse(temp_c))
            self.rep = self.newRep()
            self.text = self.newText()
        self.oprep = self.newOpRep()
        self.lines = []
        self.sel = False
        self.center_sel = False
        self.handler_ids = {
        'enter-notify-event':None,
        'leave-notify-event':None,
        }
        self.handler_ids['enter-notify-event'] = self.connect('enter-notify-event', self.on_mouse_over)
        self.handler_ids['leave-notify-event'] = self.connect('leave-notify-event', self.on_mouse_leave)
        if blocked:
            self.handler_block(self.handler_ids['enter-notify-event'])
            self.handler_block(self.handler_ids['leave-notify-event'])

    def move_group(self):
        """Update the display of each element of the group except lines
        """
        #move rep
        if self.rep:
            self.rep.props.center_y = self.y + self.r + 3
            self.rep.props.center_x = self.x +3* self.r + 3
            self.rep.props.radius_x = self.r
            self.rep.props.radius_y = self.r
        #move icon, cannot modify directly GooCanvas.Image pixbuf property ... stretching ?
        if self.oprep:
            #~ self.oprep.props.y = self.y +3
            #~ self.oprep.props.x = self.x
            #~ self.oprep.props.height = 2*self.r
            #~ self.oprep.props.width = 2*self.r
            self.oprep.remove()
            self.oprep=self.newOpRep()
        #move text
        if self.text:
            self.text.props.y = self.y + self.r + 3
            self.text.props.x = self.x +3 * self.r + 3
            self.text.props.font = "Sans %s" % str(self.fontsize)


    def update_lines(self):
        """Update lines if the group is the selected item
        """
        if self.center_sel:
            self.remove_rels()
            self.add_rels()


    def on_mouse_over(self, w, target, event):
        """Change marks and inspector informations according to the group, and display lines
        """
        self.toggle_rels(True)
        self.fill_inspector()
        self.dg.changeMarks(obj=self)
        return

    def on_mouse_leave(self, w, target, event):
        """Change marks and inspector informations and remove lines
        """
        self.toggle_rels(False)
        self.clean_inspector()
        self.dg.changeMarks()
        return

    def clean_inspector(self):
        """Empty inspector
        """
        self.inspector.clean()

    def fill_inspector(self):
        """Fill inspector with informations concerning this group
        """
        self.inspector.fillWithItem(self)

    def remove_rels(self):
        """Remove relations lines from this group
        """
        r = self.canvas.get_root_item()
        i=0
        while i<r.get_n_children():
            og = r.get_child(i)
            if isinstance(og, ObjGroup):
                #we remove lines
                for l in og.lines:
                    l.remove()
                og.lines=[]
                if og.sel:
                    og.deselect()
            i+=1
        return

    def add_rels(self):
        """Add relations lines to this group, according to the link mode and raises group to top.
        """
        r = self.canvas.get_root_item()
        lg=[]
        i=0
        while i<r.get_n_children():
            eg = r.get_child(i)
            if isinstance(eg, EventGroup):
                lop = {}
                # if it is an eventgroup, we list its operations which do have an objgroup
                for objg in eg.objs:
                    if objg.rep:
                        #navigation actions do not have rep
                        lop[objg.operation]=objg
                # we then test each operation from event group
                for op in eg.event.operations:
                    if op.concerned_object == self.cobj:
                        # if it concerns our advene object, and it has an associated objgroup we add it
                        if op in lop:
                            lg.append(lop[op])
                        elif eg not in lg:
                            # else we had the eventgroup
                            lg.append(eg)
            i+=1
        self.center_sel = True
        self.select()
        if self.link_mode == 0:
            x0=self.rep.props.center_x
            y0=self.rep.props.center_y
            for g in lg:
                if g == self:
                    continue
                if hasattr(g, 'rep'):
                    #this is an objgroup
                    x1=g.rep.props.center_x
                    y1=g.rep.props.center_y
                else:
                    #this is an eventgroup
                    x1=g.rect.props.x+g.rect.props.width/2.0
                    y1=g.rect.props.y+g.rect.props.height
                p = GooCanvas.Points ([(x0, y0), (x1,y1)])
                self.lines.append(GooCanvas.Polyline (parent = self,
                                  close_path = False,
                                  points = p,
                                  stroke_color = 0xFFFFFFFF,
                                  line_width = 1.0,
                                  start_arrow = False,
                                  end_arrow = False,
                                  ))
        else:
            dic={}
            for g in lg:
                if isinstance(g, EventGroup):
                    x=g.rect.props.x+g.rect.props.width/2.0
                    y=g.rect.props.y+g.rect.props.height
                    # we test each op from this group
                    for op in g.event.operations:
                        if op.concerned_object == self.cobj:
                            # if it concerns our advene object, and it is not already in (obj maybe)
                            if op.time not in dic:
                                dic[op.time]=(x,y)
                else:
                    dic[g.operation.time]=(g.rep.props.center_x, g.rep.props.center_y)
            ks = list(dic.keys())
            ks.sort()
            p=GooCanvas.Points([dic[k] for k in ks])
            self.lines.append(GooCanvas.Polyline (parent = self,
                                close_path = False,
                                points = p,
                                stroke_color = 0xFFFFFFFF,
                                line_width = 1.0,
                                start_arrow = False,
                                end_arrow = False,
                                ))
        self.raise_(None)


    def toggle_rels(self, on):
        """Toggle relations display

        @type on: bool
        @param on: True to display rels
        """
        if not self.rep:
            # there is no line to trace for navigation operations
            return
        if not on:
            self.remove_rels()
        else:
            self.add_rels()
        return


    def select(self):
        """Highlight selection.
        """
        self.rep.props.fill_color_rgba=self.color_sel
        self.rep.props.stroke_color = self.stroke_color_sel
        self.sel = True

    def deselect(self):
        """Draw selection back to normal.
        """
        self.rep.props.fill_color_rgba=self.color_f
        self.rep.props.stroke_color = self.color_s
        self.sel = False
        self.center_sel = False

    def newOpRep(self):
        """Change icon representing operation.

        @rtype: GooCanvas.Image
        @return: the newly created image
        """
        #BIG HACK to display icon
        te = self.operation.name
        if te.find('Edit')>=0:
            if te.find('Start')>=0:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    (( 'pixmaps', 'traces', 'edition.png')), int(2*self.r), int(2*self.r))
            elif te.find('End')>=0 or te.find('Destroy')>=0:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    (( 'pixmaps', 'traces', 'finedition.png')), int(2*self.r), int(2*self.r))
        elif te.find('Creat')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    (( 'pixmaps', 'traces', 'plus.png')), int(2*self.r), int(2*self.r))
        elif te.find('Delet')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    (( 'pixmaps', 'traces', 'moins.png')), int(2*self.r), int(2*self.r))
        elif te.find('Set')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'allera.png')), int(2*self.r), int(2*self.r))
        elif te.find('Start')>=0 or te.find('Resume')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'lecture.png')), int(2*self.r), int(2*self.r))
        elif te.find('Pause')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'pause.png')), int(2*self.r), int(2*self.r))
        elif te.find('Stop')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'stop.png')), int(2*self.r), int(2*self.r))
        elif te.find('Activation')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'web.png')), int(2*self.r), int(2*self.r))
        else:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'error.png')), int(2*self.r), int(2*self.r))
            print('No icon for %s' % te)
        return GooCanvas.Image(parent=self, width=int(2*self.r),height=int(2*self.r),x=self.x,y=self.y+3,pixbuf=pb)


    def newRep(self):
        """Create an advene object representation (ellipse).

        @rtype: GooCanvas.Ellipse
        @return: the newly created ellipse
        """
        return GooCanvas.Ellipse(parent=self,
                        center_x=self.x + 3*self.r + 3,
                        center_y=self.y+self.r + 3,
                        radius_x=self.r,
                        radius_y=self.r,
                        stroke_color=self.color_s,
                        fill_color_rgba=self.color_f,
                        line_width=1.0)

    def newText(self):
        """ Create a new text representation of the advene object

        @rtype: GooCanvas.Text
        @return: the newly created text
        """
        txt = 'U'
        if self.cobj['type'] is None:
            # need to test if we can find the type in an other way, use of type() is not a good thing
            o = self.controller.package.get_element_by_id(self.cobj['id'])
            self.cobj['type']=type(o)
            #print self.type
        txt = TYPE_ABREVIATION[self.cobj['type']]
        return GooCanvas.Text (parent = self,
                        text = txt,
                        x = self.x + 3 * self.r + 3,
                        y = self.y + self.r + 3,
                        width = -1,
                        anchor = Gtk.ANCHOR_CENTER,
                        font = "Sans %s" % str(self.fontsize))


class Inspector (Gtk.VBox):
    """Inspector component to display informations concerning items and actions in the timeline
    """
    def __init__ (self, controller=None):
        GObject.GObject.__init__(self)
        self.action=None
        self.item=None
        self.controller=controller
        self.tracer = self.controller.tracers[0]
        self.pack_start(Gtk.Label(_('Inspector')), False, False, 0)
        self.pack_start(Gtk.HSeparator(), False, False, 0)
        self.inspector_id = Gtk.Label(label='')
        self.pack_start(self.inspector_id, False, True, 0)
        self.inspector_id.set_alignment(0, 0.5)
        self.inspector_id.set_tooltip_text(_('Item Id'))
        self.inspector_type = Gtk.Label(label='')
        self.pack_start(self.inspector_type, False, True, 0)
        self.inspector_type.set_tooltip_text(_('Item name or class'))
        self.inspector_type.set_alignment(0, 0.5)
        self.inspector_name = Gtk.Label(label='')
        self.pack_start(self.inspector_name, False, True, 0)
        self.inspector_name.set_tooltip_text(_('Type or schema'))
        self.inspector_name.set_alignment(0, 0.5)
        self.pack_start(Gtk.HSeparator(), False, False, 0)
        self.pack_start(Gtk.Label(_('Operations')), False, False, 0)
        self.pack_start(Gtk.HSeparator(), False, False, 0)
        opscwin = Gtk.ScrolledWindow ()
        opscwin.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        opscwin.set_border_width(0)
        self.inspector_opes= Gtk.VBox()
        opscwin.add_with_viewport(self.inspector_opes)
        self.pack_start(opscwin, True, True, 0)
        self.commentBox = Gtk.VBox()
        self.comment=Gtk.Entry()
        save_btn=Gtk.Button()
        img = Gtk.Image()
        img.set_from_file(config.data.advenefile( ( 'pixmaps', 'traces', 'msg_add.png') ))
        save_btn.add(img)
        def save_clicked(w):
            """Save comment in the trace
            """
            if self.action:
                comment = self.comment.get_text()
                self.action.event.change_comment(comment)
                if comment != '':
                    self.action.addCommentMark()
                else:
                    self.action.removeCommentMark()

        save_btn.connect('clicked', save_clicked)
        clear_btn=Gtk.Button()
        img = Gtk.Image()
        img.set_from_file(config.data.advenefile( ( 'pixmaps', 'traces', 'msg_del.png') ))
        clear_btn.add(img)
        def clear_clicked(w):
            """Clear the comment
            """
            self.comment.set_text('')
            save_clicked(w)

        clear_btn.connect('clicked', clear_clicked)
        btns = Gtk.HBox()
        btns.pack_start(save_btn, False, True, 0)
        btns.pack_start(clear_btn, False, True, 0)
        self.commentBox.pack_end(btns, False, True, 0)
        self.commentBox.pack_end(self.comment, False, True, 0)
        self.commentBox.pack_end(Gtk.HSeparator(), False, False, 0)
        self.commentBox.pack_end(Gtk.Label(_('Comment')), False, False, 0)
        self.commentBox.pack_end(Gtk.HSeparator(), False, False, 0)
        self.pack_end(self.commentBox, False, True, 0)
        self.clean()

    def fillWithItem(self, item):
        """Fill the inspector with informations concerning an object

        @type item: ObjGroup
        @param item: the advene object to display informations about
        """
        self.action=None
        self.item=item
        if item.cobj['id'] is not None:
            self.inspector_id.set_text(item.cobj['id'])
        if item.cobj['cid'] is not None:
            self.inspector_name.set_text(item.cobj['cid'])
        if item.cobj['name'] is not None:
            self.inspector_type.set_text(item.cobj['name'])
        self.addOperations([item.operation]) # could be a list of ope if we decide to pack op
        self.show_all()

    def fillWithAction(self, action=None, op=None):
        """Fill the inspector with informations concerning an action

        @type action: EventGroup
        @param action: the action to display informations about
        @type op: advene.plugins.tracebuilder.Operation
        @param op: the operation to select in the list
        """
        self.action=action
        self.item=None
        self.inspector_id.set_text(_('Action'))
        self.inspector_name.set_text('')
        self.inspector_type.set_text(action.event.name)
        self.pack_end(self.commentBox, False, True, 0)
        self.comment.set_text(action.event.comment)
        self.addOperations(action.event.operations, op)
        self.show_all()

    def select_operation(self, op):
        """Fill the inspector with an operation informations.

        @type op: advene.plugins.tracebuilder.Operation
        @param op: the operation to display informations about
        """
        self.fillWithAction(self.action, op)


    def addOperations(self, op_list=[], op_sel=None):
        """Used to pack operation boxes in the inspector

        @type op_list: list
        @param op_list: list of operations to display
        @type op_sel: advene.plugins.tracebuilder.Operation
        @param op_sel: the operation to highlight
        """
        for c in self.inspector_opes.get_children():
            self.inspector_opes.remove(c)
        for o in op_list:
            l = self.addOperation(o, o==op_sel)
            l.set_size_request(-1, 20)
            self.inspector_opes.pack_start(l, False, True, 0)

    def addOperation(self, obj_evt=None, sel=False):
        """Build a box to display an operation

        @type obj_evt: advene.plugins.tracebuilder.Operation
        @param obj_evt : operation to build a box for
        @type sel: bool
        @param sel: True if the box should be highlighted
        """
        corpsstr = ''
        if obj_evt.content is not None and obj_evt.content != 'None':
            corpsstr = urllib.parse.unquote(obj_evt.content.encode("UTF-8"))
        elif obj_evt.name.startswith('Player'):
            #we should display the movietime instead of the content.
            corpsstr = time.strftime("%H:%M:%S", time.gmtime(obj_evt.movietime/1000))
        ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time))

        if obj_evt.name in INCOMPLETE_OPERATIONS_NAMES:
            n = INCOMPLETE_OPERATIONS_NAMES[obj_evt.name]
        else:
            n = ECACatalog.event_names[obj_evt.name]
        entetestr = "%s : %s" % (ev_time, n)
        if obj_evt.concerned_object['id']:
            entetestr = entetestr + ' (%s)' % obj_evt.concerned_object['id']
        elif obj_evt.name=='PlayerSeek':
            # destination time to add
            poss = obj_evt.content.split('\n')
            if len(poss)>1:
                entetestr = entetestr + ' %s' % poss[1]
            else:
                entetestr = entetestr + ' %s' % poss[0]
        entete = Gtk.Label(label=ev_time.encode("UTF-8"))
        hb = Gtk.HBox()

        #hb.pack_start(entete, False, True, 0)
        objcanvas = GooCanvas.Canvas()
        objcanvas.set_bounds (0,0,60,20)
        #BIG HACK to display icon
        te = obj_evt.name
        if te.find('Edit')>=0:
            if te.find('Start')>=0:
                pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    (( 'pixmaps', 'traces', 'edition.png')))
            elif te.find('End')>=0 or te.find('Destroy')>=0:
                pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    (( 'pixmaps', 'traces', 'finedition.png')))
        elif te.find('Creat')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    (( 'pixmaps', 'traces', 'plus.png')))
        elif te.find('Delet')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    (( 'pixmaps', 'traces', 'moins.png')))
        elif te.find('Set')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    ( ('pixmaps', 'traces', 'allera.png')))
        elif te.find('Start')>=0 or te.find('Resume')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    ( ('pixmaps', 'traces', 'lecture.png')))
        elif te.find('Pause')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    ( ('pixmaps', 'traces', 'pause.png')))
        elif te.find('Stop')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile
                    ( ('pixmaps', 'traces', 'stop.png')))
        elif te.find('Activation')>=0:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'web.png')), 20,20)
        else:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(config.data.advenefile
                    ( ('pixmaps', 'traces', 'error.png')), 20,20)
            print('No icon for %s' % te)
        GooCanvas.Image(parent=objcanvas.get_root_item(), width=20,height=20,x=0,y=0,pixbuf=pb)
        # object icon
        objg = CanvasGroup(parent = objcanvas.get_root_item ())
        if sel:
            GooCanvas.Rect(parent=objg,
                            x=0,
                            y=0,
                            width=60,
                            height=20,
                            stroke_color='red',
                            line_width=2.0
                            )
        if obj_evt.concerned_object['id']:
            ob = self.controller.package.get_element_by_id(obj_evt.concerned_object['id'])
            temp_c = self.controller.get_element_color(ob)
            if temp_c is not None:
                temp_c = gdk2intrgba(Gdk.color_parse(temp_c))
            else:
                temp_c = 0xFFFFFFFF
            GooCanvas.Ellipse(parent=objg,
                    center_x=40,
                    center_y=10,
                    radius_x=9,
                    radius_y=9,
                    stroke_color='black',
                    fill_color_rgba=temp_c,
                    line_width=1.0)
            txt = TYPE_ABREVIATION[obj_evt.concerned_object['type']]
            GooCanvas.Text (parent = objg,
                    text = txt,
                    x = 40,
                    y = 10,
                    width = -1,
                    anchor = Gtk.ANCHOR_CENTER,
                    font = "Sans 5")
        else:
            # no concerned object, we are in an action of navigation
            txt = obj_evt.content
            if txt != None:
                # content should be of the form pos_bef \n pos
                #but if it is an old trace, we only got pos
                poss = txt.split('\n')
                if len(poss)>1 and te.find('PlayerSeek')>=0:
                    txt=poss[1]
                else:
                    txt=poss[0]
            else:
                txt = time.strftime("%H:%M:%S", time.gmtime(obj_evt.movietime/1000))
            GooCanvas.Text (parent = objg,
                    text = txt,
                    x = 40,
                    y = 10,
                    width = -1,
                    anchor = Gtk.ANCHOR_CENTER,
                    font = "Sans 7")
        cm = objcanvas.get_colormap()
        color = cm.alloc_color('#FFFFFF')
        if obj_evt.name in self.tracer.colormodel['operations']:
            color = Gdk.color_parse(self.tracer.colormodel['operations'][obj_evt.name])
        elif self.tracer.modelmapping['operations']:
            for k in self.tracer.modelmapping['operations']:
                if obj_evt.name in self.tracer.modelmapping['operations'][k]:
                    x = self.tracer.modelmapping['operations'][k][obj_evt.name]
                    if x >=0:
                        kn = self.tracer.tracemodel[k][x]
                        if kn in self.tracer.colormodel[k]:
                            color = Gdk.color_parse(self.tracer.colormodel[k][kn])
                            break
                    else:
                        #BIG HACK, FIXME
                        #should do nothing but for incomplete operations we need to do something...
                        if obj_evt.name in INCOMPLETE_OPERATIONS_NAMES:
                            if obj_evt.concerned_object['id']:
                                ob = self.controller.package.get_element_by_id(obj_evt.concerned_object['id'])
                                if obj_evt.concerned_object['type'] == Annotation or obj_evt.concerned_object['type'] == Relation or isinstance(ob, Annotation) or isinstance(ob, Relation):
                                    x=1
                                elif obj_evt.concerned_object['type'] == RelationType or obj_evt.concerned_object['type'] == AnnotationType or obj_evt.concerned_object['type'] == Schema or isinstance(ob, AnnotationType) or isinstance(ob, RelationType) or isinstance(ob, Schema) :
                                    x=3
                                elif obj_evt.concerned_object['type'] == View or isinstance(ob, View):
                                    x=4
                                else:
                                    x=-1
                                if x >=0:
                                    kn = self.tracer.tracemodel[k][x]
                                    if kn in self.tracer.colormodel[k]:
                                        color = Gdk.color_parse(self.tracer.colormodel[k][kn])
                                        break
        objcanvas.modify_base (Gtk.StateType.NORMAL, color)
        objcanvas.set_size_request(60,20)
        if corpsstr != "":
            objcanvas.set_tooltip_text(corpsstr)
        if entetestr != "":
            entete.set_tooltip_text(entetestr)

        box = Gtk.EventBox()
        def box_pressed(w, event, id):
            """Edit the element if double clicked

            @type id: advene id
            @param id: the id of the package element to edit
            """
            if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                if id is not None:
                    obj = self.controller.package.get_element_by_id(id)
                    if obj is not None:
                        self.controller.gui.edit_element(obj)
                    else:
                        print("item %s no longuer exists" % id)
            return
        box.add(entete)
        box.connect('button-press-event', box_pressed, obj_evt.concerned_object['id'])
        objcanvas.connect('button-press-event', box_pressed, obj_evt.concerned_object['id'])
        hb.pack_start(box, False, True, 0)
        hb.pack_end(objcanvas, False, True, 0)
        return hb

    def clean(self):
        """Used to clean the inspector when selecting no item
        """
        self.action=None
        self.item=None
        self.inspector_id.set_text('')
        self.inspector_name.set_text('')
        self.inspector_type.set_text('')
        self.remove(self.commentBox)
        for c in self.inspector_opes.get_children():
            self.inspector_opes.remove(c)
        self.comment.set_text('')
        self.show_all()

class DocGroup (CanvasGroup):
    """Group used to display a representation of the movie
    """
    def __init__(self, controller=None, canvas=None, name="N/A", x =10, y=10, w=80, h=20, fontsize=14, color_c=0x00000050):
        CanvasGroup.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.canvas=canvas
        self.name=name
        self.rect = None
        self.w = w
        self.h = h
        self.x= x
        self.y = y
        self.movielength = 1
        if self.controller.package.cached_duration>0:
            self.movielength = self.controller.package.cached_duration
        self.tracer = self.controller.tracers[0]
        self.color_c = color_c
        self.color_f = 0xFFFFFF00
        self.lw = 1.0
        self.fontsize=fontsize
        self.lines=[]
        self.marks=[]
        self.rect = self.newRect()
        self.timemarks=[]
        self.connect('button-press-event', self.docgroup_clicked)

    def newRect(self):
        """Create a new rectangle to represent the movie.

        @rtype: GooCanvas.Rect
        @return: a new rectangle
        """
        return GooCanvas.Rect (parent = self,
                                    x = self.x,
                                    y = self.y,
                                    width = self.w,
                                    height = self.h,
                                    fill_color_rgba = self.color_f,
                                    stroke_color_rgba = self.color_c,
                                    line_width = self.lw)

    def drawtimemarks(self):
        """Add begin and end time marks and 1-3 other
        """
        nbmax = int(self.w / 10)
        if nbmax > 3:
            nbmax = 3
        #timestamp 0
        self.timemarks.append(GooCanvas.Text (parent = self,
                                text = time.strftime("%H:%M:%S", time.gmtime(0)),
                                x = self.x,
                                y = self.y+self.h+7,
                                fill_color = self.color_c,
                                width = -1,
                                anchor = Gtk.ANCHOR_CENTER,
                                font = "Sans 6"))
        p = GooCanvas.Points ([(self.x, self.y+self.h), (self.x, self.y+self.h+2)])
        self.timemarks.append(GooCanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color_rgba = self.color_c,
                                        line_width = 1.0,
                                        start_arrow = False,
                                        end_arrow = False
                                        ))
        #timestamp fin
        self.timemarks.append(GooCanvas.Text (parent = self,
                                text = time.strftime("%H:%M:%S", time.gmtime(self.movielength/1000)),
                                x = self.x+self.w,
                                y = self.y+self.h+7,
                                fill_color = self.color_c,
                                width = -1,
                                anchor = Gtk.ANCHOR_CENTER,
                                font = "Sans 6"))
        p = GooCanvas.Points ([(self.x+self.w, self.y+self.h), (self.x+self.w, self.y+self.h+2)])
        self.timemarks.append(GooCanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color_rgba = self.color_c,
                                        line_width = 1.0,
                                        start_arrow = False,
                                        end_arrow = False
                                        ))
        if nbmax <=0:
            return
        sec = int(self.movielength / 1000)
        if sec < nbmax:
            return
        #1-3 timestamps intermediaires
        for i in range(0, nbmax+1):
            rap = 1.0 * i / (nbmax+1)
            self.timemarks.append(GooCanvas.Text (parent = self,
                                text = time.strftime("%H:%M:%S", time.gmtime(sec * rap)),
                                x = self.x + self.w * rap,
                                y = self.y+self.h+7,
                                fill_color = self.color_c,
                                width = -1,
                                anchor = Gtk.ANCHOR_CENTER,
                                font = "Sans 6"))
            p = GooCanvas.Points ([(self.x + self.w * rap, self.y+self.h), (self.x + self.w * rap, self.y+self.h+2)])
            self.timemarks.append(GooCanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color_rgba = self.color_c,
                                        line_width = 1.0,
                                        start_arrow = False,
                                        end_arrow = False
                                        ))

    #FIXME
    def redraw(self, trace=None, action=None, obj=None):
        """Remove everything on the doc canvas and redraw everything.

        @type trace: advene.plugins.tracebuilder.Trace
        @param trace: the trace to redraw
        @type action: advene.plugins.tracebuilder.Action
        @param action: the action for which to draw marks
        @type obj: ObjGroup
        @param obj: the objgroup for which to draw marks
        """
        for l in self.lines:
            l.remove()
        self.lines=[]
        for m in self.marks:
            m.remove()
        self.marks=[]
        for t in self.timemarks:
            t.remove()
        self.timemarks=[]
        self.drawtimemarks()
        if 'actions' not in trace.levels:
            return
        for a in trace.levels['actions']:
            for o in a.operations:
                self.addLine(o.movietime)
        self.changeMarks(action, obj)

    def changeMarks(self, action=None, obj=None):
        """Change "v" signs to show selected items

        @type action: advene.plugins.tracebuilder.Action
        @param action: the action for which to draw marks
        @type obj: ObjGroup
        @param obj: the objgroup for which to draw marks
        """
        for m in self.marks:
            m.remove()
        self.marks=[]
        if action is not None:
            #print "%s %s %s" % (action.name, ACTIONS.index(action.name), color)
            for op in action.operations:
                self.addMark(op.movietime,
                             gdk2intrgba(Gdk.color_parse(self.tracer.colormodel['actions'][action.name])))
        elif obj is not None:
            self.addMark(obj.operation.movietime, 0xD9D919FF)

    def addMark(self, time=0, color=0x444444ff):
        """Add "v" signs to show selected items

        @type time: number
        @param time: the time at which to draw mark
        @type color: number
        @param color: the rgba color of the mark
        """
        offset = 3
        x=self.rect.get_bounds().x1 + int(self.w * time / self.movielength)
        x1 = x-offset
        x2 = x+offset
        y2=self.rect.get_bounds().y1
        y1=y2-offset
        p = GooCanvas.Points ([(x1, y1), (x, y2), (x2, y1)])
        l = GooCanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color_rgba = color,
                                        line_width = 2.0,
                                        start_arrow = False,
                                        end_arrow = False
                                        )
        self.marks.append(l)

    def changeMovielength(self, trace=None, time=None):
        """Change the duration of the movie

        @type trace: advene.plugins.tracebuilder.Trace
        @param trace: the trace to redraw after changing the duration
        @type time: number
        @param time: the new duration of the movie
        """
        if time is not None:
            self.movielength=time
        elif self.controller.package.cached_duration>0:
            self.movielength=self.controller.package.cached_duration
        self.redraw(trace)


    def addLine(self, time=0, color=0x00000050, offset=0):
        """Add a line to represent a movie access time.

        @type time: number
        @param time: the time at which to draw line
        @type color: number
        @param color: the rgba color of the line
        @type offset: number
        @param offset: an offset to expand y bounds
        """
        x=self.rect.get_bounds().x1 + int(self.w * time / self.movielength)
        y1=self.rect.get_bounds().y1 - offset
        y2=self.rect.get_bounds().y2 + offset
        p = GooCanvas.Points ([(x, y1), (x, y2)])
        #ld = GooCanvas.LineDash([3.0, 3.0])
        l = GooCanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color_rgba = color,
                                        line_width = 1.0,
                                        #line_dash=ld,
                                        start_arrow = False,
                                        end_arrow = False
                                        )
        self.lines.append(l)

    def docgroup_clicked(self, w, t, ev):
        """Move in the movie if docgroup clicked
        """
        if ev.button == 1:
            self.controller.update_status ("seek", self.movielength * (ev.x-self.x)/self.w)

