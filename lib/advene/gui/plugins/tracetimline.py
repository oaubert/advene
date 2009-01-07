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
import advene.util.helper as helper
import urllib
import advene.model.view
from advene.gui.widget import TimestampRepresentation
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
        self.canvasY = 1000
        self.incr = 500
        self.timefactor = 1000
        self.cols={}
        self.tracer.register_view(self)
        for act in self.tracer.action_types:
            self.cols[act] = (None, None)
        self.widget = self.build_widget()
        self.widget.connect("destroy", self.destroy)
        self.populate_head_canvas()
        self.receive(self.tracer.trace)

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
        scrolled_win.add(self.canvas)
        mainbox.pack2(scrolled_win, resize=True, shrink=True)
        mainbox.set_position(35)
        # adding time lines
        #t=0
        #while t<self.canvasY:
            
        
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
            if zoom:
                # Control+scroll: zoom in/out
                print 'zoom'
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
                return False            
            x, y = self.drag_coordinates
            
            a=scrolled_win.get_hadjustment()
            v=a.value + x - event.x_root
            if v > a.lower and v < a.upper:
                a.value=v
            a=scrolled_win.get_vadjustment()
            v=a.value + y - event.y_root
            if v > a.lower and v < a.upper:
                a.value=v
            
            self.drag_coordinates= (event.x_root, event.y_root)
            return False
        self.canvas.connect('motion-notify-event', on_background_motion)

        return bx

    def populate_head_canvas(self):
        offset = 0
        offset_x = 100
        offset_c = 0x00008800
        for c in self.cols.keys():
            gpc = 0x00000050 + offset_c*(16**offset)
            print '%02x %02x' % (offset_c*(16**offset), gpc)
            etgroup = HeadGroup(self.controller, self.head_canvas, c, 5+offset_x*offset, 0, 8, gpc)
            self.cols[c]=(etgroup, None)
            offset = offset + 1
        return

    def destroy(self, source=None, event=None):
        self.controller.tracers[0].unregister_view(self)
        return False

    def refresh(self):
        root = self.canvas.get_root_item()
        while root.get_n_children()>0:
            root.remove_child (0)
        if 'actions' in self.tracer.trace.levels.keys() and self.tracer.trace.levels['actions']:
            a = self.tracer.trace.levels['actions'][-1].activity_time[1]
            while a>self.canvasY*self.timefactor:
                self.timefactor = (self.canvasY+self.incr)*self.timefactor//self.canvasY
                self.canvasY = self.canvasY + self.incr
                print "Y : %s tf : %s" % (self.canvasY, self.timefactor)
            self.canvas.set_bounds (0, 0, self.canvasX, self.canvasY)
            self.canvas.show()
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
                self.refresh()
                #self.widget.show_all()
            
            l.rect = l.newRect(x1, y1, length, l.color, l.color_c)
            
            # modify bounds to match new length
            #self.lasty = l.rect.get_bounds().y2
            

        else:
            #y=self.lasty
            x = h.rect.get_bounds().x1+1
            y = action.activity_time[0]//self.timefactor
            length = (action.activity_time[1]-action.activity_time[0])//self.timefactor
            if y+length > self.canvasY:
                self.refresh()
            ev = EventGroup(self.controller, self.canvas, None, action, x, y, length, 14, color)
            self.cols[action.name]=(h,ev)
            #self.lasty = ev.rect.get_bounds().y2
            #print "%s %s %s" % (y, length, self.lasty)

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
                                    fill_color_rgba = self.color_c,
                                    stroke_color = self.color_s,
                                    line_width = 2.0)
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
    def __init__(self, controller=None, canvas=None, type=None, event=None, x =0, y=0, l=10, fontsize=22, color_c=0x00ffff50):
        Group.__init__(self, parent = canvas.get_root_item ())
        self.controller=controller
        self.event=event
        self.type=type
        self.rect = None
        self.text = None
        self.color_c = color_c
        self.color = "black"
        self.fontsize=fontsize
        self.rect = self.newRect (x,y,l,self.color, self.color_c)
        #self.text = self.newText (self.formattedName(),x+5,y+30)

        
    def newRect(self, xx, yy, l, color, color_c):
        return goocanvas.Rect (parent = self,
                                    x = xx,
                                    y = yy,
                                    width = 90,
                                    height = l,
                                    fill_color_rgba = color_c,
                                    stroke_color = color,
                                    line_width = 2.0)


### TODO
# 
# fixer une taille max par defaut (1 min ? 10 min ? 1h ?, possibilité de passer sur 100%, mais pas en live sinon ça va ramer)
# affichage event : 
# 
# calculer la taille par regle de trois
# a chaque nouvel event, si update d'action, redessiner le dernier rectangle
