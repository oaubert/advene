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

from advene.gui.views import AdhocView
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

class TraceTimeline(AdhocView):
    view_name = _("Traces")
    view_id = 'trace2'
    tooltip=("Traces of Advene Events in a Timeline")
    def __init__ (self, controller=None, parameters=None, package=None):
        super(TraceTimeline, self).__init__(controller=controller)
        self.close_on_package_load = False
        #self.toolTips = gtk.Tooltips()
        #self.toolTips.enable()
        self.tracer = self.controller.tracers[0]
        self.__package=package
        #self.contextual_actions = (
        #    (_("Refresh"), self.refresh),
        #    )
        if package is None and controller is not None:
            self.__package=controller.package
        self.drag_coordinates=None
        self.canvas = None
        self.head_canvas = None
        self.toolbox = None
        self.lasty=0
        self.canvasX = None
        self.canvasY = 1
        self.obj_l = 5
        self.incr = 500
        self.timefactor = 100
        self.autoscroll = True
        self.sw = None
        self.cols={}
        self.tracer.register_view(self)
        for act in self.tracer.action_types:
            self.cols[act] = (None, None)
        self.widget = self.build_widget()
        self.widget.connect("destroy", self.destroy)
        self.populate_head_canvas()
        self.widget.show_all()
        self.refresh()
        
    def build_widget(self):
        bx = gtk.HPaned()
        mainbox = gtk.VPaned()
        self.head_canvas = goocanvas.Canvas()
        c = len(self.cols)
        self.canvasX = c*100
        self.head_canvas.set_bounds (0,0,self.canvasX,35)
        mainbox.pack1(self.head_canvas, resize=False, shrink=True)
        self.canvas = goocanvas.Canvas()
        self.canvas.set_bounds (0, 0,self.canvasX, self.canvasY)
        scrolled_win = gtk.ScrolledWindow ()
        self.sw = scrolled_win
        scrolled_win.add(self.canvas)
        mainbox.pack2(scrolled_win, resize=True, shrink=True)
        mainbox.set_position(35)
        
        bx.pack1(mainbox, resize=True, shrink=True)
        self.toolbox = gtk.VBox()
        lbz = gtk.Label(_('Zoom'))
        btnp = gtk.Button('+')
        btnm = gtk.Button('-')
        btnc = gtk.Button('100%')
        lbf = gtk.Label(_('Filtres'))
        self.toolbox.pack_start(lbz, expand=False)
        self.toolbox.pack_start(gtk.HSeparator(), expand=False)
        self.toolbox.pack_start(btnp, expand=False)
        self.toolbox.pack_start(btnm, expand=False)
        self.toolbox.pack_start(btnc, expand=False)
        self.toolbox.pack_start(gtk.HSeparator(), expand=False)
        self.toolbox.pack_start(lbf, expand=False)
        self.toolbox.pack_start(gtk.HSeparator(), expand=False)
        bx.pack2(self.toolbox, resize=False, shrink=True)

        def on_background_scroll(widget, event):
            zoom=event.state & gtk.gdk.CONTROL_MASK
            a = None
            if zoom:
                if event.direction == gtk.gdk.SCROLL_DOWN:
                    zoom_out(widget)
                elif  event.direction == gtk.gdk.SCROLL_UP:
                    zoom_in(widget)
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

        def zoom_out(w):
            h = self.canvas.get_allocation().height
            if h/float(self.canvasY)>=0.8:
                zoom_100(w)
            else:
                self.canvasY = self.canvasY * 0.8
                self.timefactor *= 1.25
                self.obj_l *= 0.8
            #print "%s" % (self.timefactor)
            self.canvas.set_bounds (0,0,self.canvasX,self.canvasY)
            self.refresh()
        btnm.connect('clicked', zoom_out)
        
        def zoom_in(w):
            self.canvasY = self.canvasY * 1.25
            self.timefactor *= 0.8
            self.obj_l *= 1.25
            #print "%s" % (self.timefactor)
            self.canvas.set_bounds (0,0,self.canvasX,self.canvasY)
            self.refresh()
        btnp.connect('clicked', zoom_in)

        def zoom_100(w):
            wa = self.canvas.get_allocation()
            self.canvasY = wa.height
            if 'actions' in self.tracer.trace.levels.keys() and self.tracer.trace.levels['actions']:
                a = self.tracer.trace.levels['actions'][-1].activity_time[1]
                self.timefactor = a/(self.canvasY-1.0)
                self.obj_l = 5000/self.timefactor
            else:
                self.timefactor = 1000
                self.obj_l = 5
            #print self.timefactor
            self.canvas.set_bounds(0,0,self.canvasX, self.canvasY)
            self.refresh()
        btnc.connect('clicked', zoom_100)
        return bx

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

    def populate_head_canvas(self):
        offset = 0
        offset_x = 100
        offset_c = [0x000088AA, 0x0000FFAA, 0x008800AA, 0x00FF00AA, 0x880000AA, 0xFF0000FF, 0x008888FF, 0x880088FF, 0x888800FF, 0xFF00FFFF, 0x00FFFFFF, 0xFFFF00FF, 0x00FF88FF, 0xFF0088FF, 0x0088FFFF, 0x8800FFFF, 0x88FF00FF, 0xFF8800FF]
        # 18 col max
        for c in self.cols.keys():
            gpc = offset_c[offset]
            #print '%02x %02x' % (offset_c*(16**offset), gpc)
            etgroup = HeadGroup(self.controller, self.head_canvas, c, 5+offset_x*offset, 0, 8, gpc)
            self.cols[c]=(etgroup, None)
            offset = offset + 1
        return

    def destroy(self, source=None, event=None):
        self.controller.tracers[0].unregister_view(self)
        return False

    def refresh(self, action=None):
        root = self.canvas.get_root_item()
        while root.get_n_children()>0:
            root.remove_child (0)
        for act in self.cols.keys():
            (h,l) = self.cols[act]
            self.cols[act] = (h, None)
        if 'actions' in self.tracer.trace.levels.keys() and self.tracer.trace.levels['actions']:
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
        for i in self.tracer.trace.levels['actions']:
                self.receive(self.tracer.trace, action=i)

    def receive(self, trace, event=None, operation=None, action=None):
        # trace : the full trace to be managed
        # event : the new or latest modified event
        # operation : the new or latest modified operation
        # action : the new or latest modified action

        if (operation or event) and action is None:
            return
        #print "received : action %s, operation %s, event %s" % (action, operation, event)
        if action is None:
            #redraw screen
            self.refresh()
            if self.autoscroll:
                a = self.sw.get_vadjustment()
                a.value=a.upper-a.page_size
            return
        h,l = self.cols[action.name]
        color = h.color_c
        if l and l.event == action:
            y1=l.rect.get_bounds().y1+1
            x1=l.rect.get_bounds().x1+1
            child_num = l.find_child (l.rect)
            l.remove_child (child_num)
            length = (action.activity_time[1]-action.activity_time[0])//self.timefactor
            if y1+length > self.canvasY:
                self.refresh(action)
            #l.rect = l.newRect(x1, y1, length, l.color, l.color_c)
            #l.redrawObjs(self.obj_l)
        else:
            x = h.rect.get_bounds().x1+1
            y = action.activity_time[0]//self.timefactor
            length = (action.activity_time[1]-action.activity_time[0])//self.timefactor
            #print "%s %s %s %s" % (action, x, y, length)
            if action.activity_time[1] > self.canvasY*self.timefactor:
                #print "%s %s %s" % (action.name , action.activity_time[1], self.canvasY*self.timefactor)
                self.refresh(action)
            ev = EventGroup(self.controller, self.canvas, None, action, x, y, length, self.obj_l, 14, color)
            self.cols[action.name]=(h,ev)
            #self.lasty = ev.rect.get_bounds().y2
            #print "%s %s %s" % (y, length, self.lasty)
        if self.autoscroll:
            a = self.sw.get_vadjustment()
            a.value=a.upper-a.page_size

class HeadGroup (Group):
    def __init__(self, controller=None, canvas=None, name="N/A", x = 5, y=0, fontsize=14, color_c=0x00ffff50):
        Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.name=name
        self.rect = None
        self.text = None
        self.color_s = "black"
        self.color_c = color_c
        self.fontsize=fontsize
        self.rect = goocanvas.Rect (parent = self,
                                    x = x,
                                    y = y,
                                    width = 90,
                                    height = 30,
                                    fill_color_rgba = 0xFFFFFF00,
                                    stroke_color = 0xFFFFFF00,
                                    line_width = 0)
        self.text = goocanvas.Text (parent = self,
                                        text = self.name,
                                        x = x+45,
                                        y = y+15,
                                        width = -1,
                                        anchor = gtk.ANCHOR_CENTER,
                                        font = "Sans Bold %s" % str(self.fontsize))

        def change_name(self, name):
            return

        def change_font(self, font):
            return
        
class EventGroup (Group):
    def __init__(self, controller=None, canvas=None, type=None, event=None, x =0, y=0, l=1, ol=5, fontsize=8, color_c=0x00ffffff):
        Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.event=event
        self.type=type
        self.rect = None
        self.text = None
        self.color_c = color_c
        self.color_o = 0xADEAEAFF
        self.color = "black"
        self.fontsize=fontsize
        self.rect = self.newRect (x,y,l,self.color, self.color_c)
        self.objs={}
        self.redrawObjs(ol)
        self.lines = []

    def newRect(self, xx, yy, l, color, color_c):
        return goocanvas.Rect (parent = self,
                                    x = xx,
                                    y = yy,
                                    width = 90,
                                    height = l,
                                    fill_color_rgba = color_c,
                                    stroke_color = color,
                                    line_width = 2.0)

    def addObj(self, obj_id, factor, xx, yy, ol, color, color_c):
        #o = goocanvas.Rect (parent = self,
        #                            x = xx,
        #                            y = yy,
        #                            width = ol,
        #                            height = ol,
        #                            fill_color_rgba = color_c,
        #                            stroke_color = color,
        #                            line_width = 1.0)
        o = goocanvas.Ellipse(parent=self,
                            center_x=xx+ol/2,
                            center_y=yy+ol/2,
                            radius_x=ol/2,
                            radius_y=ol/2,
                            stroke_color=color,
                            fill_color_rgba=color_c,
                            line_width=1.0)
        
        def toggle_rels(w, target, ev, obj_id):
            #print "%s %s %s %s" % (w, target, ev.button, obj_id)
            if ev.button != 1:
                return
            r = w.get_canvas().get_root_item()
            chd = []
            i=0
            while i <r.get_n_children():
                f = r.get_child(i)
                if isinstance(f, EventGroup) and f.objs is not None:
                    chd.append(f)
                    if f.lines:
                        for l in f.lines:
                            n=f.find_child(l)
                            f.remove_child(n)
                        f.lines=[]
                i+=1
            for c in chd:
                if obj_id in c.objs.keys():
                    (r_obj, f) = c.objs[obj_id] #rect, factor
                    if r_obj != w:
                        #faire un lien
                        x2=y2=0
                        #x1 = w.get_bounds().x1 + w.props.width/2
                        #y1 = w.get_bounds().y1 + w.props.height/2
                        x1 = w.props.center_x
                        y1 = w.props.center_y
                        if r_obj is None:
                            x2 = c.rect.get_bounds().x1 + c.rect.props.width/2
                            y2 = c.rect.get_bounds().y1 + c.rect.props.height/2
                        else:
                            x2 = r_obj.props.center_x
                            y2 = r_obj.props.center_y
                            
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
        o.connect('button-press-event', toggle_rels, obj_id)
        return o

    def redrawObjs(self, ol=5):
        l = self.rect.props.height
        w = self.rect.props.width
        if ol > (w-6)/3.0:
            ol = (w-6)/3.0
        y=self.rect.get_bounds().y1+1
        x=self.rect.get_bounds().x1+1
        #FIXME : brutal way to do that. Need only to find what operation was added to update only this square
        for obj in self.objs.keys():
            (r_obj, f) = self.objs[obj]
            if r_obj is not None:
                child_num = self.find_child (r_obj)
                self.remove_child (child_num)
        self.objs= {}
        for op in self.event.operations:
            obj = op.concerned_object['id']
            if obj is None:
                pass
            if obj in self.objs.keys():
                (r_obj, pds) = self.objs[obj]
                self.objs[obj] = (None, pds+1)
            else:
                self.objs[obj] = (None, 1)
        if l <ol+2 or ol<5:
            #too small, we do not draw rects
            return
        #self.objs : item : #time modified during action
        ox = x+2
        oy = y+2
        #trier le dictionnaire par poids?
        for obj in self.objs.keys():
            # modif 90 par largeur colonne
            if ox+(ol+2)*2>= x+90:
                if oy+ol+2>= y+l:
                    # ...
                    #goocanvas.Text(parent = self,
                    #                    text = "...",
                    #                    x = ox,
                    #                    y = oy,
                    #                    width = -1,
                    #                    anchor = gtk.ANCHOR_CENTER,
                    #                    font = "Sans Bold %s" % str(self.fontsize))
                    break
                else:
                    (r_obj, pds) = self.objs[obj]
                    self.objs[obj]= (self.addObj(obj, pds, ox, oy, ol, self.color, self.color_o), pds)
                    ox = x+2
                    oy += (ol+2)
            else:
                (r_obj, pds) = self.objs[obj]
                self.objs[obj]= (self.addObj(obj, pds, ox, oy, ol, self.color, self.color_o), pds)
                ox += (ol+2)

