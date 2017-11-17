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
"""Trace Preview.

This widget allows to stack compact operation history to preview the trace.
"""

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
import time

from gettext import gettext as _

from advene.gui.views import AdhocView
import urllib.request, urllib.parse, urllib.error
import advene.model.view
from advene.rules.elements import ECACatalog
import advene.core.config as config
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.package import Package
from advene.gui.util import gdk2intrgba

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
        controller.log("Cannot register TracePreview: the goocanvas python module does not seem to be available.")
    else:
        controller.register_viewclass(TracePreview)

name="Trace preview"

class TracePreview(AdhocView):
    view_name = _("Trace preview")
    view_id = 'tracepreview'
    tooltip=("Preview of collected user activity trace")
    def __init__ (self, controller=None, parameters=None, package=None):
        super(TracePreview, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.sw = None
        self.size = 0
        self.last_obs_box = None
        self.last_obs = None
        self.incomplete_operations_names = {
            'EditSessionStart': _('Beginning edition'),
            'ElementEditBegin': _('Beginning edition'),
            'ElementEditDestroy': _('Canceling edition'),
            'ElementEditCancel': _('Canceling edition'),
            'EditSessionEnd': _('Canceling edition'),
            'ElementEditEnd': _('Ending edition'),
            'PlayerSeek': _('Moving to'),
        }
        self.options = {
            'max_size': 8,
            }
        #self.DetB = None
        self.sc = None
        self.accuBox = None
        self.box_h = 30
        self.__package = package
        if package is None and controller is not None:
            self.__package=controller.package
        self.tracer = self.controller.tracers[0]
        self.widget = self.build_widget()
        self.widget.connect("destroy", self.destroy)
        self.tracer.register_view(self)
        self.receive(self.tracer.trace)

    def build_widget(self):
        mainbox = Gtk.VBox()
        btnbar=Gtk.HBox()
        btngt = Gtk.Button(_('Full trace'))
        btngt.set_tooltip_text(_('Open the trace timeline view fareast'))
        btngt.set_size_request(60, 20)
        def open_trace(widget):
            l=[ w for w in self.controller.gui.adhoc_views if w.view_id == 'tracetimeline' ]
            if not l:
                self.controller.gui.open_adhoc_view(name='tracetimeline', destination='fareast')
        btnbar.pack_start(btngt, False, True, 0)
        btngt.connect('clicked', open_trace)
        mainbox.pack_start(btnbar, False, True, 0)
        mainbox.pack_start(Gtk.HSeparator(), False, False, 0)
        self.accuBox = Gtk.VBox()
        self.sw = Gtk.ScrolledWindow()
        self.sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.sw.add_with_viewport(self.accuBox)
        self.sw.set_vadjustment(Gtk.Adjustment.new(value = 208, lower = 0, upper=208, step_incr=52, page_incr=208, page_size=208))
        mainbox.pack_start(self.sw, True, True, 0)
        return mainbox


    def scroll_win(self):
        a = self.sw.get_vadjustment()
        if a:
            a.set_value(a.get_upper())
        return

    def receive(self, trace, event=None, operation=None, action=None):
        # trace : the full trace to be managed
        # event : the new or latest modified event
        # operation : the new or latest modified operation
        # action : the new or latest modified action
        #print "received : action %s, operation %s, event %s" % (action, operation, event)
        if operation is None and not (event is None and action is None):
            return
        self.showObs(trace.levels['operations'], operation)
        self.scroll_win()

    def showObs(self, tracelevel, operation):
        #adjust the current display to the modified trace
        if operation is not None:
            if self.size>=self.options['max_size']:
                self.unpackEvent()
            self.packObs(operation, 'operations')
        else:
            #refreshing the whole trace
            while self.size > 0:
                self.unpackEvent()
            if len(tracelevel)==0:
                return
            trace_max = max(0, len(tracelevel))
            trace_min = max(0, trace_max-self.options['max_size'])
            t_temp = trace_max-1
            while t_temp > trace_min and trace_min > 0:
                t_temp = t_temp -1
            for i in tracelevel[trace_min:trace_max]:
                self.packObs(i, 'operations')
        return

    def packObs(self, obj_evt, level):
        if obj_evt is not None:
            vb=Gtk.VBox()
            self.last_obs_box = self.buildBox(obj_evt, level)
            def zoom_in_timeline(widget, event, obj_evt):
                if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                    l=[ w for w in self.controller.gui.adhoc_views if w.view_id == 'tracetimeline' ]
                    if l:
                        a=l[-1]
                    else:
                        a=self.controller.gui.open_adhoc_view(name='tracetimeline', destination='fareast')
                    g = a.find_group(obj_evt)
                    if g is not None:
                        a.zoom_on(canvas_item=g)
                        g.on_mouse_over(None, None, None)
                        a.show_inspector()
                        a.inspector.select_operation(obj_evt)
            self.last_obs_box.connect('button-press-event', zoom_in_timeline, obj_evt)
            self.last_obs = obj_evt
            vb.add(self.last_obs_box)
            vb.add(Gtk.HSeparator())
            self.accuBox.pack_start(vb, False, True, 0)
            self.accuBox.show_all()
            self.size = self.size + 1

    def buildBox(self, obj_evt, level):
        if level<0:
            print('refresh trace')
        else:
            ### FIXME : this code should be factorized with the
            ### similar one in tracetimeline (addOperation)
            ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time))
            corpsstr = ''
            entetestr = ''
            if obj_evt.name not in self.incomplete_operations_names:
                if ECACatalog.event_names[obj_evt.name]:
                    entetestr = "%s : %s" % (ev_time, ECACatalog.event_names[obj_evt.name])
                else:
                    entetestr = "%s : %s" % (ev_time, "Event not described")
                if obj_evt.concerned_object['id']:
                    entetestr = entetestr + ' (%s)' % obj_evt.concerned_object['id']
            elif obj_evt.name.find('Player')>=0:
                txt = obj_evt.content
                if txt != None:
                    # content should be of the form pos_bef \n pos
                    #but if it is an old trace, we only got pos
                    poss = txt.split('\n')
                    if len(poss)>1 and obj_evt.name.find('PlayerSeek')>=0:
                        txt=poss[1]
                    else:
                        txt=poss[0]
                else:
                    txt = time.strftime("%H:%M:%S", time.gmtime(obj_evt.movietime/1000))
                entetestr = "%s : %s %s" % (ev_time, self.incomplete_operations_names[obj_evt.name], txt)
            else:
                comp = ''
                if obj_evt.concerned_object['type'] == Annotation:
                    comp = _('of an annotation (%s)') % obj_evt.concerned_object['id']
                elif obj_evt.concerned_object['type'] == Relation:
                    comp = _('of a relation (%s)') % obj_evt.concerned_object['id']
                elif obj_evt.concerned_object['type'] == AnnotationType:
                    comp = _('of an annotation type (%s)') % obj_evt.concerned_object['id']
                elif obj_evt.concerned_object['type'] == RelationType:
                    comp = _('of a relation type (%s)') % obj_evt.concerned_object['id']
                elif obj_evt.concerned_object['type'] == Schema:
                    comp = _('of a schema (%s)') % obj_evt.concerned_object['id']
                elif obj_evt.concerned_object['type'] == View:
                    comp = _('of a view (%s)') % obj_evt.concerned_object['id']
                elif obj_evt.concerned_object['type'] == Package:
                    comp = _('of a package (%s)') % obj_evt.concerned_object['id']
                else:
                    comp = _('of an unknown item (%s)') % obj_evt.concerned_object['id']
                    #print "%s" % ob
                entetestr = "%s : %s %s" % (ev_time, self.incomplete_operations_names[obj_evt.name], comp)
            if obj_evt.content is not None:
                corpsstr = urllib.parse.unquote(obj_evt.content.encode('utf-8'))
            entete = Gtk.Label(label=ev_time.encode("UTF-8"))
            hb = Gtk.HBox()
            hb.pack_start(entete, False, True, 0)
            objcanvas = goocanvas.Canvas()
            objcanvas.set_bounds (0,0,60,20)
            hb.pack_end(objcanvas, False, True, 0)
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
            goocanvas.Image(parent=objcanvas.get_root_item(), width=20,height=20,x=0,y=0,pixbuf=pb)
            # object icon
            objg = Group(parent = objcanvas.get_root_item ())
            if obj_evt.concerned_object['id']:
                ob = self.controller.package.get_element_by_id(obj_evt.concerned_object['id'])
                temp_c = self.controller.get_element_color(ob)
                if temp_c is not None:
                    temp_c = gdk2intrgba(Gdk.color_parse(temp_c))
                else:
                    temp_c = 0xFFFFFFFF
                goocanvas.Ellipse(parent=objg,
                        center_x=40,
                        center_y=10,
                        radius_x=9,
                        radius_y=9,
                        stroke_color='black',
                        fill_color_rgba=temp_c,
                        line_width=1.0)
                if obj_evt.concerned_object['type'] == Annotation:
                    #draw a A
                    txt='A'
                elif obj_evt.concerned_object['type'] == Relation:
                    #draw a R
                    txt='R'
                elif obj_evt.concerned_object['type'] == AnnotationType:
                    #draw a AT
                    txt='AT'
                elif obj_evt.concerned_object['type'] == RelationType:
                    #draw a RT
                    txt='RT'
                elif obj_evt.concerned_object['type'] == Schema:
                    #draw a S
                    txt='S'
                elif obj_evt.concerned_object['type'] == View:
                    #draw a V
                    txt='V'
                else:
                    #draw a U
                    txt='U'
                goocanvas.Text (parent = objg,
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
                    if len(poss)>1 and obj_evt.name.find('PlayerSeek')>=0:
                        txt=poss[1]
                    else:
                        txt=poss[0]
                else:
                    txt = time.strftime("%H:%M:%S", time.gmtime(obj_evt.movietime/1000))
                goocanvas.Text (parent = objg,
                        text = txt,
                        x = 40,
                        y = 10,
                        width = -1,
                        anchor = Gtk.ANCHOR_CENTER,
                        font = "Sans 7")
            cm = objcanvas.get_colormap()
            color = cm.alloc_color('#FFFFFF')
            if obj_evt.name in self.tracer.colormodel[level]:
                color = Gdk.color_parse(self.tracer.colormodel[level])
            elif self.tracer.modelmapping[level]:
                for k in self.tracer.modelmapping[level]:
                    if obj_evt.name in self.tracer.modelmapping[level][k]:
                        x = self.tracer.modelmapping[level][k][obj_evt.name]
                        if x >=0:
                            kn = self.tracer.tracemodel[k][x]
                            if kn in self.tracer.colormodel[k]:
                                color = Gdk.color_parse(self.tracer.colormodel[k][kn])
                                break
                        else:
                            #BIG HACK, FIXME
                            #should do nothing but for incomplete operations we need to do something...
                            if obj_evt.name in self.incomplete_operations_names:
                                if obj_evt.concerned_object['id']:
                                    ob = self.controller.package.get_element_by_id(obj_evt.concerned_object['id'])
                                    if isinstance(ob, advene.model.annotation.Annotation) or isinstance(ob,advene.model.annotation.Relation):
                                        x=1
                                    elif isinstance(ob,advene.model.schema.AnnotationType) or isinstance(ob,advene.model.schema.RelationType) or isinstance(ob,advene.model.schema.Schema):
                                        x=3
                                    elif isinstance(ob,advene.model.view.View):
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
            return hb

    def unpackEvent(self):
        if self.accuBox.get_children():
            self.accuBox.remove(self.accuBox.get_children()[0])
        else:
            print("Trace Preview: no event to unpack ? %s" % self.size)
        if self.size>0:
            self.size = self.size-1

    def destroy(self, source=None, event=None):
        self.controller.tracers[0].unregister_view(self)
        return False
