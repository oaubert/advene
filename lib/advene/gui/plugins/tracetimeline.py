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
"""Trace timeline.

This widget allows to present event history in a timeline view.
"""

import gtk
import time
from gettext import gettext as _
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from math import floor
from advene.gui.views import AdhocView
#import advene.util.helper as helper
from advene.rules.elements import ECACatalog
import advene.core.config as config

try:
    import goocanvas
    from goocanvas import Group
except ImportError:
    # Goocanvas is not available. Define some globals in order not to
    # fail the module loading, and use them as a guard in register()
    goocanvas=None
    Group=object

def register(controller):
    if goocanvas is None:
        controller.log("Cannot register TraceTimeline: the goocanvas python module does not seem to be available.")
    else:
        controller.register_viewclass(TraceTimeline)

name="Trace Timeline view"
ACTION_COLORS=[0x000088AA, 0x008800AA, 0x880000AA, 0x008888FF, 0x880088FF, 0x0000FFAA, 0x00FF00AA, 0xFF0000FF, 0x888800FF, 0xFF00FFFF, 0x00FFFFFF, 0xFFFF00FF, 0x00FF88FF, 0xFF0088FF, 0x0088FFFF, 0x8800FFFF, 0x88FF00FF, 0xFF8800FF]
ACTIONS=[]

class TraceTimeline(AdhocView):
    view_name = _("Traces")
    view_id = 'trace2'
    tooltip=("Traces of Advene Events in a Timeline")
    def __init__ (self, controller=None, parameters=None, package=None):
        super(TraceTimeline, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.tracer = self.controller.tracers[0]
        self.__package=package
        #self.contextual_actions = (
        #    (_("Refresh"), self.refresh),
        #    )
        if package is None and controller is not None:
            self.__package=controller.package
        self.drag_coordinates=None

        # Header canvas
        self.head_canvas = None
        # Main timeline canvas
        self.canvas = None
        # Contextualizing document canvas
        self.doc_canvas = None

        self.tooltips = gtk.Tooltips()
        self.tooltips.enable()
        self.inspector = None
        self.btnl = None
        self.lasty=0
        self.canvasX = None
        self.canvasY = 1
        self.head_canvasY = 25
        self.doc_canvas_Y = 30
        self.docgroup = None
        self.obj_l = 5
        self.incr = 500
        self.timefactor = 100
        self.autoscroll = True
        self.links_locked = False
        self.sw = None
        self.cols={}
        self.tracer.register_view(self)
        for act in self.tracer.action_types:
            self.cols[act] = (None, None)
            ACTIONS.append(act)
        self.col_width = 80
        self.colspacing = 5
        self.widget = self.build_widget()
        self.widget.connect("destroy", self.destroy)
        self.populate_head_canvas()
        self.widget.show_all()
        self.receive(self.tracer.trace)

    def build_widget(self):
        mainbox = gtk.VBox()

        toolbox = gtk.Toolbar()
        toolbox.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        mainbox.pack_start(toolbox, expand=False)

        bx = gtk.HPaned()
        mainbox.pack_start(bx, expand=True)

        timeline_box=gtk.VBox()
        bx.pack1(timeline_box)
        
        scrolled_win = gtk.ScrolledWindow ()
        self.sw = scrolled_win
        self.sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_ALWAYS)

        self.head_canvas = goocanvas.Canvas()
        c = len(self.cols)
        self.canvasX = c*(self.col_width+self.colspacing)
        self.head_canvas.set_bounds (0,0,self.canvasX,self.head_canvasY)
        self.head_canvas.set_size_request(-1, self.head_canvasY)
        timeline_box.pack_start(self.head_canvas, expand=False, fill=False)

        self.canvas = goocanvas.Canvas()
        self.canvas.set_bounds (0, 0,self.canvasX, self.canvasY)
        self.canvas.set_size_request(100, 25) # important to force a minimum size (else we could have problem with radius of objects < 0)

        self.doc_canvas = goocanvas.Canvas()
        self.doc_canvas.set_bounds(0,0, self.canvasX, self.doc_canvas_Y)
        self.doc_canvas.set_size_request(-1, self.doc_canvas_Y)
        self.docgroup = DocGroup(controller=self.controller, canvas=self.doc_canvas, name="Nom du film", x = 5, y=5, w=self.canvasX-10, fontsize=8, color_c=0x00000050)
        self.canvas.get_root_item().connect('button-press-event', self.canvas_clicked)
        def canvas_resize(w, alloc):
            self.canvasX = alloc.width-20.0
            self.col_width = (self.canvasX)//len(self.cols)-self.colspacing
            #redraw head_canvas
            self.head_canvas.set_bounds (0, 0, self.canvasX, self.head_canvasY)
            self.redraw_head_canvas()
            #redraw canvas
            self.canvas.set_bounds (0, 0, self.canvasX, self.canvasY)
            h = self.canvas.get_allocation().height
            va=scrolled_win.get_vadjustment()
            vc = (va.value + h/2.0) * self.timefactor
            self.refresh(action=None, center=vc)
            #redraw doc_canvas
            self.doc_canvas.set_bounds(0,0, self.canvasX, self.doc_canvas_Y)
            self.redraw_doc_canvas()
            #print alloc.width
        self.head_canvas.connect('size-allocate', canvas_resize)
        scrolled_win.add(self.canvas)

        timeline_box.add(scrolled_win)

        mainbox.pack_start(self.doc_canvas, expand=False, fill=True)

        btnm = gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_OUT)
        btnm.set_tooltip(self.tooltips, _('Zoom out'))
        btnm.set_label('')
        toolbox.insert(btnm, -1)

        btnp = gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_IN)
        btnp.set_tooltip(self.tooltips, _('Zoom in'))
        btnp.set_label('')
        toolbox.insert(btnp, -1)

        btnc = gtk.ToolButton(stock_id=gtk.STOCK_ZOOM_100)
        btnc.set_tooltip(self.tooltips, _('Zoom 100%'))
        btnc.set_label('')
        toolbox.insert(btnc, -1)
        self.btnl = gtk.ToolButton()
        self.btnl.set_tooltip(self.tooltips, _('Toggle links lock'))
        #self.btnl.set_label(_('Unlocked'))
        img = gtk.Image()
        img.set_from_file(config.data.advenefile( ( 'pixmaps', 'unlocked.png') ))
        self.btnl.set_icon_widget(img)
        toolbox.insert(self.btnl, -1)
        self.btnl.connect('clicked', self.toggle_lock)

        self.inspector = Inspector(self.controller)
        bx.pack2(self.inspector)
        
        def on_background_scroll(widget, event):
            zoom=event.state & gtk.gdk.CONTROL_MASK
            a = None
            if zoom:
                center = event.y * self.timefactor
                if event.direction == gtk.gdk.SCROLL_DOWN:
                    zoom_out(widget, center)
                elif  event.direction == gtk.gdk.SCROLL_UP:
                    zoom_in(widget, center)
                return
            elif event.state & gtk.gdk.SHIFT_MASK:
                # Horizontal scroll
                a = scrolled_win.get_hadjustment()
                incr = a.step_increment
            else:
                # Vertical scroll
                a = scrolled_win.get_vadjustment()
                incr = a.step_increment

            if event.direction == gtk.gdk.SCROLL_DOWN:
                val = a.value + incr
                if val > a.upper - a.page_size:
                    val = a.upper - a.page_size
                elif val < a.lower:
                    val = a.lower
                if val != a.value:
                    a.value = val
            elif event.direction == gtk.gdk.SCROLL_UP:
                val = a.value - incr
                if val < a.lower:
                    val = a.lower
                elif val > a.upper - a.page_size:
                    val = a.upper - a.page_size
                if val != a.value:
                    a.value = val
            return True
        self.canvas.connect('scroll-event', on_background_scroll)

        def on_background_motion(widget, event):
            if not event.state & gtk.gdk.BUTTON1_MASK:
                return False
            #if self.dragging:
            #    return False
            if not self.drag_coordinates:
                self.drag_coordinates=(event.x_root, event.y_root)
                self.widget.get_parent_window().set_cursor(gtk.gdk.Cursor(gtk.gdk.DIAMOND_CROSS))
                #curseur grab
                return False
            x, y = self.drag_coordinates
            wa=widget.get_allocation()
            a=scrolled_win.get_hadjustment()
            v=a.value + x - event.x_root
            if v > a.lower and v+wa.width < a.upper:
                a.value=v
            a=scrolled_win.get_vadjustment()
            v=a.value + y - event.y_root
            if v > a.lower and v+wa.height < a.upper:
                a.value=v

            self.drag_coordinates= (event.x_root, event.y_root)
            return False
        self.canvas.connect('motion-notify-event', on_background_motion)

        def on_background_button_release(widget, event):
            if event.button == 1:
                self.drag_coordinates=None
                self.widget.get_parent_window().set_cursor(None)
                #curseur normal
            return False
        self.canvas.connect('button-release-event', on_background_button_release)

        def zoom_out(w, center_v=None):
            h = self.canvas.get_allocation().height
            if h/float(self.canvasY)>=0.8:
                zoom_100(w)
            else:
                va=scrolled_win.get_vadjustment()
                vc=0
                if center_v is None: 
                    vc = (va.value + h/2.0) * self.timefactor
                else:
                    vc = center_v
                self.canvasY *= 0.8
                self.timefactor *= 1.25
                self.obj_l *= 0.8
                #print "%s" % (self.timefactor)
                self.canvas.set_bounds (0,0,self.canvasX,self.canvasY)
                self.refresh(center = vc)
        btnm.connect('clicked', zoom_out)

        def zoom_in(w, center_v=None):
            h = self.canvas.get_allocation().height
            va=scrolled_win.get_vadjustment()
            if center_v is None: 
                vc = (va.value + h/2.0) * self.timefactor
            else:
                vc = center_v
            self.canvasY *= 1.25
            self.timefactor *= 0.8
            self.obj_l *= 1.25
            #print "%s" % (self.timefactor)
            self.canvas.set_bounds (0,0,self.canvasX,self.canvasY)
            self.refresh(center = vc)
        btnp.connect('clicked', zoom_in)

        def zoom_100(w):
            wa = self.canvas.get_allocation()
            self.canvasY = wa.height-10.0 # -10 pour des raisons obscures ...
            if 'actions' in self.tracer.trace.levels.keys() and self.tracer.trace.levels['actions']:
                a = self.tracer.trace.levels['actions'][-1].activity_time[1]
                self.timefactor = a/(self.canvasY)
                self.obj_l = 5000.0/self.timefactor
            else:
                self.timefactor = 1000
                self.obj_l = 5
            #print self.timefactor
            self.canvas.set_bounds(0,0,self.canvasX, self.canvasY)
            self.refresh()
        btnc.connect('clicked', zoom_100)
        
        bx.set_position(self.canvasX+15)
        return mainbox

    def zoom_on(self, w=None, canvas_item=None):
        min_y = -1
        max_y = -1
        if hasattr(canvas_item, 'rect'):
            # action
            min_y = canvas_item.rect.get_bounds().y1
            max_y = canvas_item.rect.get_bounds().y2
        elif hasattr(canvas_item, 'rep'):
            obj_id = canvas_item.id
            i=0
            root = self.canvas.get_root_item()
            while i < root.get_n_children():
                go = root.get_child(i)
                if isinstance(go, ObjGroup) and obj_id == go.id:
                    # obj
                    obj_min_y = go.rep.props.center_y - go.rep.props.radius_y
                    obj_max_y = go.rep.props.center_y + go.rep.props.radius_y
                    if min_y == -1:
                        min_y = obj_min_y
                    min_y = min(min_y, obj_min_y)
                    max_y = max(max_y, obj_max_y)
                i+=1
        #print 'y1 %s y2 %s' % (min_y, max_y)
        h = self.canvas.get_allocation().height
        # 20.0 to keep a little space between border and object
        va=self.sw.get_vadjustment()
        rapp = (20.0 + max_y - min_y) / h
        vc = self.timefactor * ((min_y + max_y) / 2.0) * (va.upper / self.canvasY)
        self.timefactor = rapp * self.timefactor
        self.canvasY = rapp * self.canvasY
        self.obj_l = rapp * self.obj_l
        self.canvas.set_bounds (0,0,self.canvasX,self.canvasY)
        self.refresh(center = vc)        
        
    def redraw_doc_canvas(self):
        return
        
    def canvas_clicked(self, w, t, ev):
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
            menu=gtk.Menu()
            if obj_gp is not None:
                i=gtk.MenuItem(_("Zoom and center on linked items"))
                i.connect("activate", self.zoom_on, obj_gp)
                menu.append(i)
            if evt_gp is not None:
                i=gtk.MenuItem(_("Zoom on action"))
                i.connect("activate", self.zoom_on, evt_gp)
                menu.append(i)
            menu.show_all()
            menu.popup(None, None, None, ev.button, ev.time)
        elif ev.button == 1:
            #clic gauche sur un item : lock
            #if obj_gp is None:
            #    return
            self.toggle_lock()
        #if obj_gp is not None:
            #self.inspector_id.set_text(obj_gp.id)
            #self.inspector_name.set_text(obj_gp.name)
            #if obj_gp.type is not None:
            #    self.inspector_type.set_text(obj_gp.type.getLocalName())
            #else:
            #    self.inspector_type.set_text('None')
            #vider les fils de self.inspector_opes
            #for c in self.inspector_opes.get_children():
            #    self.inspector_opes.remove(c)
            #for o in obj_gp.opes:
            #    self.inspector_opes.pack_start(gtk.Label("%s:\n   %s\n   (%s)" % (o.time, o.name, o.content)))
            #self.inspector.show_all()
        #temp_str = "%s (%s) : %s\n" % (self.name, self.id, self.type)
        #for o in self.opes:
        #    temp_str += "%s: %s (%s)\n" % (o.time, o.name, o.content)
        #print temp_str


    def toggle_lock(self, w=None):
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
            i+=1
                    
    def draw_marks(self):
        # adding time lines
        wa = self.canvas.get_parent().get_allocation().height
        tinc = 60
        if wa > 100:
            tinc = wa/4.0 # 4 marks in the widget
        else:
            tinc = 60000 / self.timefactor
        t=tinc
        #print t, wa
        ld = goocanvas.LineDash([5.0, 20.0])
        while t < self.canvasY:
            #print t
            goocanvas.polyline_new_line(self.canvas.get_root_item(),
                                        0,
                                        t,
                                        self.canvasX,
                                        t,
                                        line_dash=ld,
                                        line_width = 0.2)
            goocanvas.Text(parent = self.canvas.get_root_item(),
                        text = time.strftime("%H:%M:%S",time.gmtime(t*self.timefactor/1000)),
                        x = 0,
                        y = t-5,
                        width = -1,
                        anchor = gtk.ANCHOR_W,
                        fill_color_rgba=0x121212FF, #0x23456788
                        font = "Sans 7")
            goocanvas.Text(parent = self.canvas.get_root_item(),
                        text = time.strftime("%H:%M:%S",time.gmtime(t*self.timefactor/1000)),
                        x = self.canvasX-4,
                        y = t-5,
                        width = -1,
                        fill_color_rgba=0x121212FF,
                        anchor = gtk.ANCHOR_E,
                        font = "Sans 7")
            #goocanvas.Text(parent = self.canvas.get_root_item(),
            #           text = time.strftime("%H:%M:%S",time.gmtime(t*self.timefactor)/1000),
            #           x = self.canvasX/2,
            #           y = t-5,
            #           width = -1,
            #           fill_color_rgba=0x23456788,
            #           anchor = gtk.ANCHOR_CENTER,
            #           font = "Sans 8")
            t += tinc
        return

    def redraw_head_canvas(self):
        root = self.head_canvas.get_root_item()
        while root.get_n_children()>0:
            root.remove_child (0)
        self.populate_head_canvas()
        return

    def populate_head_canvas(self):
        offset = 0
        #colors = [0x000088AA, 0x0000FFAA, 0x008800AA, 0x00FF00AA, 0x880000AA, 0xFF0000FF, 0x008888FF, 0x880088FF, 0x888800FF, 0xFF00FFFF, 0x00FFFFFF, 0xFFFF00FF, 0x00FF88FF, 0xFF0088FF, 0x0088FFFF, 0x8800FFFF, 0x88FF00FF, 0xFF8800FF]
        # 18 col max
        for c in ACTIONS:
            etgroup = HeadGroup(self.controller, self.head_canvas, c, (self.colspacing+self.col_width)*offset, 0, self.col_width, 8, ACTION_COLORS[offset])
            self.cols[c]=(etgroup, None)
            offset += 1
        return

    def destroy(self, source=None, event=None):
        self.controller.tracers[0].unregister_view(self)
        return False

    def refresh(self, action=None, center = None):
        # method to refresh the canvas display
        # 1/ clean the canvas, memorizing selected item
        # 2/ recalculate the canvas area according to timefactor and last action
        # 3/ redraw time separators
        # 4/ redraw each action
        # 5/ recenter the canvas according to previous centering
        # 6/ reselect selected item
        # 7/ re-deactive locked_links
        # action : the new action forcing a refresh (if action couldnt be displayed in the current canvas area)
        # center : the timestamp on which the display needs to be centered
        root = self.canvas.get_root_item()
        selected_item = None
        while root.get_n_children()>0:
            #print "refresh removing %s" % root.get_child (0)
            c = root.get_child(0)
            if isinstance(c, EventGroup):
                for k in c.objs.keys():
                    if c.objs[k][0] is not None:
                        if c.objs[k][0].center_sel:
                            selected_item = (c.event, k)
            root.remove_child (0)
        for act in self.cols.keys():
            (h,l) = self.cols[act]
            self.cols[act] = (h, None)
        if not ('actions' in self.tracer.trace.levels.keys() and self.tracer.trace.levels['actions']):
            return
        a = None
        if action is None:
            a = self.tracer.trace.levels['actions'][-1].activity_time[1]
        else:
            a = action.activity_time[1]
            #print "t1 %s Ytf %s" % (a, self.canvasY*self.timefactor)
        if a<(self.canvasY-self.incr)*self.timefactor or a>self.canvasY*self.timefactor:
            self.canvasY = int(1.0*a/self.timefactor + 1)
        self.canvas.set_bounds (0, 0, self.canvasX, self.canvasY)
        #print "%s %s" % (self.timefactor, self.canvasY)
        self.canvas.show()
        self.draw_marks()
        sel_eg = None
        for i in self.tracer.trace.levels['actions']:
            ev = self.receive(self.tracer.trace, action=i)
            if selected_item is not None and i == selected_item[0]:
                sel_eg = ev
        if center:
            va=self.sw.get_vadjustment()
            va.value = center/self.timefactor-va.page_size/2.0
            if va.value<va.lower:
                va.value=va.lower
            elif va.value>va.upper-va.page_size:
                va.value=va.upper-va.page_size
        if selected_item is not None:
            #print "sel item : %s %s" % selected_item
            if sel_eg is not None:
                if sel_eg.get_canvas() is None:
                    #print "group deprecated"
                    # group deprecated, need to find the new one (happens when refreshing during a receive
                    n=0
                    while n<root.get_n_children():
                        #print "refresh removing %s" % root.get_child (0)
                        c = root.get_child(n)
                        if isinstance(c, EventGroup):
                            if c.event == selected_item[0]:
                                # that's the good action
                                sel_eg = c
                        n += 1
                if sel_eg.objs is not None:
                    if sel_eg.objs[selected_item[1]] is not None:
                        if sel_eg.objs[selected_item[1]][0] is not None:
                            sel_eg.objs[selected_item[1]][0].toggle_rels()
        if self.links_locked:
            i=0
            root = self.canvas.get_root_item()
            while i < root.get_n_children():
                go = root.get_child(i)
                if isinstance(go, ObjGroup):
                    go.handler_block(go.handler_ids['enter-notify-event'])
                    go.handler_block(go.handler_ids['leave-notify-event'])
                i+=1
            

    def receive(self, trace, event=None, operation=None, action=None):
        # trace : the full trace to be managed
        # event : the new or latest modified event
        # operation : the new or latest modified operation
        # action : the new or latest modified action
        # return the created group
        #print "received : action %s, operation %s, event %s" % (action, operation, event)
        if event and (event.name=='DurationUpdate' or event.name=='MediaChange'):
            self.docgroup.changeMovielength(trace)
        if operation:
            self.docgroup.addLine(operation.movietime)
        if (operation or event) and action is None:
            return
        if action is None:
            #redraw screen
            self.refresh()
            self.docgroup.redraw(trace)
            if self.autoscroll:
                a = self.sw.get_vadjustment()
                a.value=a.upper-a.page_size
            return
        h,l = self.cols[action.name]
        color = h.color_c
        ev = None
        if l and l.event == action:
            ev = l
            y1=l.rect.get_bounds().y1+1
            x1=l.rect.get_bounds().x1+1
            #print "receive removing %s" % l.rect
            child_num = l.find_child (l.rect)
            if child_num>=0:
                l.remove_child (child_num)
            length = (action.activity_time[1]-action.activity_time[0])//self.timefactor
            if y1+length > self.canvasY:
                self.refresh(action)
            else:
                l.x = x1
                l.y = y1
                l.l = length
                l.rect = l.newRect(l.color, l.color_c)
                l.redrawObjs(self.obj_l)
        else:
            x = h.rect.get_bounds().x1+1
            y = action.activity_time[0]//self.timefactor
            length = (action.activity_time[1]-action.activity_time[0])//self.timefactor
            #print "%s %s %s %s" % (action, x, y, length)
            if action.activity_time[1] > self.canvasY*self.timefactor:
                #print "%s %s %s" % (action.name , action.activity_time[1], self.canvasY*self.timefactor)
                self.refresh(action)
            ev = EventGroup(self.controller, self.inspector, self.canvas, self.docgroup, None, action, x, y, length, self.col_width, self.obj_l, 14, color)
            self.cols[action.name]=(h,ev)
            #self.lasty = ev.rect.get_bounds().y2
            #print "%s %s %s" % (y, length, self.lasty)
        if self.autoscroll:
            a = self.sw.get_vadjustment()
            a.value=a.upper-a.page_size
        #redraw canvasdoc
        #self.docgroup.redraw(trace)
        #if 'actions' in self.tracer.trace.levels.keys() and self.tracer.trace.levels['actions']:
        return ev

class HeadGroup (Group):
    def __init__(self, controller=None, canvas=None, name="N/A", x = 5, y=0, w=90, fontsize=14, color_c=0x00ffff50):
        Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.name=name[0:2]
        self.rect = None
        self.text = None
        self.w = 90
        self.color_s = "black"
        self.color_c = color_c
        self.fontsize=fontsize
        self.rect = goocanvas.Rect (parent = self,
                                    x = x,
                                    y = y,
                                    width = self.w,
                                    height = 20,
                                    fill_color_rgba = 0xFFFFFF00,
                                    stroke_color = 0xFFFFFF00,
                                    line_width = 0)
        self.text = goocanvas.Text (parent = self,
                                        text = self.name,
                                        x = x+w/2,
                                        y = y+15,
                                        width = -1,
                                        anchor = gtk.ANCHOR_CENTER,
                                        font = "Sans Bold %s" % str(self.fontsize))

        def change_name(self, name):
            return

        def change_font(self, font):
            return

class EventGroup (Group):
    def __init__(self, controller=None, inspector=None, canvas=None, dg=None, type=None, event=None, x =0, y=0, l=1, w=90, ol=5, fontsize=6, color_c=0x00ffffff):
        Group.__init__(self, parent = canvas.get_root_item ())
        self.canvas = canvas
        self.controller=controller
        self.inspector = inspector
        self.event=event
        self.type=type
        self.dg = dg
        self.rect = None
        self.color_sel = 0xD9D919FF
        self.color_c = color_c
        self.color_o = 0xADEAEAFF
        self.color = "black"
        self.fontsize=fontsize
        self.x = x
        self.y= y
        self.l = l
        self.ol = ol
        self.w = w
        self.rect = self.newRect (self.color, self.color_c)
        self.objs={}
        #self.lines = []
        self.redrawObjs(ol)
        self.handler_ids = {
        'enter-notify-event':None,
        'leave-notify-event':None,
        }
        #self.connect('button-press-event', self.on_click)
        self.handler_ids['enter-notify-event'] = self.connect('enter-notify-event', self.on_mouse_over)
        self.handler_ids['leave-notify-event'] = self.connect('leave-notify-event', self.on_mouse_leave)
        
    def newRect(self, color, color_c):
        return goocanvas.Rect (parent = self,
                                    x = self.x,
                                    y = self.y,
                                    width = self.w,
                                    height = self.l,
                                    fill_color_rgba = color_c,
                                    stroke_color = color,
                                    line_width = 2.0)

    def addObj(self, obj_id, xx, yy, ol, color, color_o):
        (pds, obj_name, obj_type, obj_opes) = self.objs[obj_id][1:5]
        o = ObjGroup(self.controller, self.inspector, self.canvas, self.dg, xx, yy, ol, self.fontsize, pds, obj_id, obj_name, obj_type, obj_opes)
        return o

    def redrawObjs(self, ol=5):
        #FIXME : brutal way to do that. Need only to find what operation was added to update only this square
        for obj in self.objs.keys():
            obg = self.objs[obj][0]
            if obg is not None:
                #print "redrawObjs removing %s" % r_obj 
                child_num = self.find_child (obg)
                if child_num>=0:
                    self.remove_child (child_num)
        self.objs = {}
        for op in self.event.operations:
            obj_opes = []
            obj = op.concerned_object['id']
            if obj is None:
                continue
            if obj in self.objs.keys():
                (pds, obj_name, obj_type, obj_opes) = self.objs[obj][1:5]
                obj_opes.append(op)
                self.objs[obj] = (None, pds+1, obj_name, obj_type, obj_opes)
            else:
                obj_name = op.concerned_object['name']
                obj_type = op.concerned_object['type']
                obj_opes.append(op)
                self.objs[obj] = (None, 1, obj_name, obj_type, obj_opes)
            #print "obj %s opes %s" % (obj, obj_opes)
        #self.objs : item : #time modified during action
        y=self.rect.get_bounds().y1+1
        x=self.rect.get_bounds().x1+1
        ox = x+2
        oy = y+2
        l = self.rect.props.height
        w = self.rect.props.width
        nb = len(self.objs.keys())
        ol = w/3 - 4
        while (floor(((w-3)/(ol+2)))*floor(((l-3)/(ol+2)))< nb and ol>3):
            ol-=1
        #print "w:%s l:%s nb:%s nbw:%s nbl:%s ol:%s" % (w-2, l-2, nb, floor(((w-2)/(ol+2))), floor(((l-2)/(ol+2))), ol)
        if ol > l-4:
            if l>7:
                ol=l-4
            else:
                return
        if ol > 20:
            ol=20
        # need to fix fontsize according to object length with a min of 6 and a max of ??, 
        self.fontsize = ol-1
        for obj in self.objs.keys():
            #print "ox %s oy %s ol %s w %s l %s" % (ox, oy, ol, w+x, l+y)
            if ox+(ol+2)>= x+w:
                if oy+(ol+2)*2>= y+l:
                    ox = x+2
                    oy += (ol+1)
                    #FIXME
                    goocanvas.Text(parent = self,
                                        text = "...",
                                        x = ox,
                                        y = oy,
                                        width = -1,
                                        anchor = gtk.ANCHOR_NORTH_WEST,
                                        font = "Sans Bold %s" % self.fontsize)
                    break
                else:
                    ox = x+2
                    oy += (ol+2)
                    (pds, obj_name, obj_type, obj_opes) = self.objs[obj][1:5]
                    self.objs[obj]= (self.addObj(obj, ox+ol/2.0, oy+ol/2.0, ol/2.0, self.color, self.color_o), pds, obj_name, obj_type, obj_opes)
                    ox += (ol+2)
            else:
                (pds, obj_name, obj_type, obj_opes) = self.objs[obj][1:5]
                self.objs[obj]= (self.addObj(obj, ox+ol/2.0, oy+ol/2.0, ol/2.0, self.color, self.color_o), pds, obj_name, obj_type, obj_opes)
                ox += (ol+2)
            #print "ox %s oy %s ol %s w %s l %s" % (ox, oy, ol, w+x, l+y)

    def on_mouse_over(self, w, target, event):
        #print '1 %s %s %s %s' % self.canvas.get_bounds()
        self.fill_inspector()
        self.dg.changeMarks(action=self.event)
        #print '2 %s %s %s %s' % self.canvas.get_bounds()
        return

    def on_mouse_leave(self, w, target, event):
        self.clean_inspector()
        self.dg.changeMarks()
        return
        
    #def on_click(self, w, target, ev):
        #print "%s %s %s" % (w, target, ev.button)
    #    if ev.button == 1:
    #        return
    #    if ev.button == 3:
            #recenter on links
    #        pass
    #    return
    
    def clean_inspector(self):
        self.inspector.clean()
    
    def fill_inspector(self):
        self.inspector.fillWithAction(self)


class ObjGroup (Group):
    def __init__(self, controller=None, inspector=None, canvas=None, dg=None, x=0, y=0, r=4, fontsize=6, pds=1, obj_id=None, obj_name=None, obj_type=None, obj_opes=[]):
        Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.rep = None
        self.text = None
        self.canvas = canvas
        self.dg=dg
        self.inspector = inspector
        self.color_sel = 0xD9D919FF
        self.color_f = 0xADEAEAFF
        self.color_s = "black"
        #self.fontsize = fontsize
        self.fontsize = 5
        self.poids = pds
        self.id = obj_id
        self.name = obj_name # name is the name of the type ...
        self.type = obj_type #the type object
        self.opes = obj_opes
        self.x = x
        self.y = y
        self.r = r
        self.rep = self.newRep()
        self.text = self.newText()
        self.lines = []
        self.sel = False
        self.center_sel = False
        self.handler_ids = {
        'enter-notify-event':None,
        'leave-notify-event':None,
        }
        #self.connect('button-press-event', self.on_click)
        self.handler_ids['enter-notify-event'] = self.connect('enter-notify-event', self.on_mouse_over)
        self.handler_ids['leave-notify-event'] = self.connect('leave-notify-event', self.on_mouse_leave)

    def on_mouse_over(self, w, target, event):
        #print '1 %s %s %s %s' % self.canvas.get_bounds()
        self.toggle_rels()
        self.fill_inspector()
        self.dg.changeMarks(obj=self)
        #print '2 %s %s %s %s' % self.canvas.get_bounds()
        return

    def on_mouse_leave(self, w, target, event):
        self.toggle_rels()
        self.clean_inspector()
        self.dg.changeMarks()
        return
        
    #def on_click(self, w, target, ev):
        #print "%s %s %s" % (w, target, ev.button)
    #    if ev.button == 1:
    #        return
    #    if ev.button == 3:
            #recenter on links
    #        pass
    #    return
    
    def clean_inspector(self):
        self.inspector.clean()
    
    def fill_inspector(self):
        self.inspector.fillWithItem(self)
    
    def toggle_rels(self):
        #temp_str = "%s (%s) : %s\n" % (self.name, self.id, self.type)
        #for o in self.opes:
        #    temp_str += "%s: %s (%s)\n" % (o.time, o.name, o.content)
        #print temp_str
        r = self.canvas.get_root_item()
        chd = []
        i=0
        desel = False
        while i <r.get_n_children():
            f = r.get_child(i)
            if isinstance(f, EventGroup) and f.objs is not None:
                chd.append(f)
                for obj_id in f.objs.keys():
                    obg = f.objs[obj_id][0]
                    if obg is None:
                        continue
                    for l in obg.lines:
                        #print "toggle removing line %s" % l
                        n=obg.find_child(l)
                        if n>=0:
                            obg.remove_child(n)
                    obg.lines=[]
                    if obg.sel:
                        if obg.center_sel and obg == self:
                            desel = True
                        obg.deselect()
            i+=1
        if desel:
            return
        self.select()
        self.center_sel = True
        for c in chd:
            if self.id in c.objs.keys():
                obj_gr = c.objs[self.id][0]
                if obj_gr != self:
                    x2=y2=0
                    x1 = self.x
                    y1 = self.y
                    if obj_gr is None:
                        x2 = c.rect.get_bounds().x1 + c.rect.props.width/2
                        y2 = c.rect.get_bounds().y1 + c.rect.props.height/2
                    else:
                        x2 = obj_gr.x
                        y2 = obj_gr.y
                        obj_gr.select()
                    p = goocanvas.Points ([(x1, y1), (x2,y2)])
                    self.lines.append(goocanvas.Polyline (parent = self,
                                    close_path = False,
                                    points = p,
                                    stroke_color = 0xFFFFFFFF,
                                    line_width = 1.0,
                                    start_arrow = False,
                                    end_arrow = False,
                                    ))
        return

    def select(self):
        self.rep.props.fill_color_rgba=self.color_sel
        self.sel = True

    def deselect(self):
        self.rep.props.fill_color_rgba=self.color_f
        self.sel = False
        self.center_sel = False
        
    def newRep(self):
        return goocanvas.Ellipse(parent=self,
                        center_x=self.x,
                        center_y=self.y,
                        radius_x=self.r,
                        radius_y=self.r,
                        stroke_color=self.color_s,
                        fill_color_rgba=self.color_f,
                        line_width=1.0)

    def newText(self):
        txt = 'U'
        if self.type is None:
            # need to test if we can find the type in an other way, use of type() is not a good thing
            o = self.controller.package.get_element_by_id(self.id)
            self.type=type(o)
            #print self.type
        if self.type == Schema:
            txt = 'S'
        elif self.type == AnnotationType:
            txt = 'AT'
        elif self.type == RelationType:
            txt = 'RT'
        elif self.type == Annotation:
            txt = 'A'
        elif self.type == Relation:
            txt = 'R'
        elif self.type == View:
            txt = 'V'

        return goocanvas.Text (parent = self,
                        text = txt,
                        x = self.x,
                        y = self.y,
                        width = -1,
                        anchor = gtk.ANCHOR_CENTER,
                        font = "Sans %s" % str(self.fontsize))


class Inspector (gtk.VBox):
    def __init__ (self, controller=None):
        gtk.VBox.__init__(self)
        self.controller=controller
        self.tooltips = gtk.Tooltips()
        self.tooltips.enable()
        self.incomplete_operations_names = {
            'EditSessionStart': _('Beginning edition'),
            'ElementEditBegin': _('Beginning edition'),
            'ElementEditDestroy': _('Canceling edition'),
            'ElementEditCancel': _('Canceling edition'),
            'EditSessionEnd': _('Canceling edition'),
            'ElementEditEnd': _('Ending edition'),
        }
        #FIXME : create a class inspector with id, name type opes
        self.pack_start(gtk.Label('Inspector'), expand=False)
        self.pack_start(gtk.HSeparator(), expand=False)
        self.inspector_id = gtk.Label('Id')
        self.pack_start(self.inspector_id, expand=False)
        self.inspector_id.set_alignment(0, 0.5)
        self.tooltips.set_tip(self.inspector_id, _('Id'))
        #name is the same as type ...
        #self.inspector_name = gtk.Label('Name') 
        #self.pack_start(self.inspector_name, expand=False)
        #self.tooltips.set_tip(self.inspector_name, _('Name'))
        #self.inspector_name.set_alignment(0, 0.5)
        self.inspector_type = gtk.Label('Type')
        self.pack_start(self.inspector_type, expand=False)
        self.tooltips.set_tip(self.inspector_type, _('Type'))
        self.inspector_type.set_alignment(0, 0.5)
        self.pack_start(gtk.HSeparator(), expand=False)
        self.pack_start(gtk.Label('Operations'), expand=False)
        self.inspector_opes=gtk.VBox()
        self.pack_start(self.inspector_opes, expand=False)
        self.clean()
        
    def fillWithItem(self, item):
        self.inspector_id.set_text(item.id)
        #self.inspector_name.set_text(item.name)
        self.inspector_type.set_text(item.name)
        #if item.type is not None:
        #    self.inspector_type.set_text(item.type.getLocalName())
        #else:
        #    self.inspector_type.set_text('None')
        
        for c in self.inspector_opes.get_children():
            self.inspector_opes.remove(c)
        nb=0
        for o in item.opes:
            nb+=1
            n=''
            if o.name in self.incomplete_operations_names:
                n = self.incomplete_operations_names[o.name]
            else:
                n = ECACatalog.event_names[o.name]
            l = gtk.Label("%s:\n%s" % (time.strftime("%H:%M:%S", time.localtime(o.time)), n))
            self.inspector_opes.pack_start(l)
            l.set_alignment(0, 0.5)
            self.tooltips.set_tip(l, o.content)
            #FIXME : need to check available space
            if nb == 8:
                print "display limited to 8 operations. Please Fixme."
                break
        self.show_all()
        
    def fillWithAction(self, action):
        self.inspector_id.set_text(_('Action'))
        self.inspector_type.set_text(action.event.name)
        for c in self.inspector_opes.get_children():
            self.inspector_opes.remove(c)
        nb=0
        for o in action.event.operations:
            nb+=1
            n=''
            if o.name in self.incomplete_operations_names:
                n = self.incomplete_operations_names[o.name]
            else:
                n = ECACatalog.event_names[o.name]
            l = gtk.Label("%s:\n%s" % (time.strftime("%H:%M:%S", time.localtime(o.time)), n))
            self.inspector_opes.pack_start(l)
            l.set_alignment(0, 0.5)
            self.tooltips.set_tip(l, o.content)
            #FIXME : need to check available space
            if nb == 8:
                print "display limited to 8 operations. Please Fixme."
                break
        self.show_all()
    
    def clean(self):
        self.inspector_id.set_text('Id')
        #self.inspector_name.set_text('Name')
        self.inspector_type.set_text('Type')
        for c in self.inspector_opes.get_children():
            self.inspector_opes.remove(c)
        self.show_all()

class DocGroup (Group):
    def __init__(self, controller=None, canvas=None, name="N/A", x = 5, y=0, w=90, fontsize=14, color_c=0x00000050):
        Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.canvas=canvas
        self.name=name
        self.rect = None
        self.w = w
        self.h = 20
        self.movielength = 1
        if self.controller.package.cached_duration>0:
            self.movielength = self.controller.package.cached_duration
        self.color_c = color_c
        self.fontsize=fontsize
        self.lines=[]
        self.marks=[]
        self.rect = goocanvas.Rect (parent = self,
                                    x = x,
                                    y = y,
                                    width = self.w,
                                    height = self.h,
                                    fill_color_rgba = 0xFFFFFF00,
                                    stroke_color_rgba = self.color_c,
                                    line_width = 1)
    
    def redraw(self, trace=None, action=None, obj=None):
        for l in self.lines:
            l.remove()
        self.lines=[]
        for m in self.marks:
            m.remove()
        self.marks=[]
        if 'actions' not in trace.levels.keys():
            return
        for a in trace.levels['actions']:
            for o in a.operations:
                self.addLine(o.movietime)
        self.changeMarks(action, obj)
    
    def changeMarks(self, action=None, obj=None):
        for m in self.marks:
            m.remove()
        self.marks=[]
        if action is not None:
            color = ACTION_COLORS[ACTIONS.index(action.name)]
            #print "%s %s %s" % (action.name, ACTIONS.index(action.name), color)
            for op in action.operations:
                self.addMark(op.movietime, color)
        elif obj is not None:
            for op in obj.opes:
                self.addMark(op.movietime, 0xD9D919FF)
        
    def addMark(self, time=0, color='gray'):
        offset = 3
        x=self.rect.get_bounds().x1 + self.w * time / self.movielength
        x1 = x-offset
        x2 = x+offset
        y2=self.rect.get_bounds().y1
        y1=y2-offset
        p = goocanvas.Points ([(x1, y1), (x, y2), (x2, y1)])
        l = goocanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color_rgba = color,
                                        line_width = 2.0,
                                        start_arrow = False,
                                        end_arrow = False
                                        )
        self.marks.append(l)
        
    def changeMovielength(self, trace=None, time=None):
        if time is not None:
            self.movielength=time
        elif self.controller.package.cached_duration>0:
            self.movielength=self.controller.package.cached_duration
        self.redraw(trace)
        
    def addLine(self, time=0, color=0x00000050, offset=0):
        # to be removed
        #~ if self.controller.package.cached_duration > self.movielength:
            #~ self.movielength=self.controller.package.cached_duration
        # assuming there is no more movielength problem
        x=self.rect.get_bounds().x1 + self.w * time / self.movielength
        y1=self.rect.get_bounds().y1 - offset
        y2=self.rect.get_bounds().y2 + offset
        p = goocanvas.Points ([(x, y1), (x, y2)])
        l = goocanvas.Polyline (parent = self,
                                        close_path = False,
                                        points = p,
                                        stroke_color_rgba = color,
                                        line_width = 1.0,
                                        start_arrow = False,
                                        end_arrow = False
                                        )
        self.lines.append(l)
