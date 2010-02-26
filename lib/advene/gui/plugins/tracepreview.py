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
"""Trace Preview.

This widget allows to stack compact event history to preview the trace.
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

def register(controller):
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
            'PlayerSet': _('Moving to'),
        }
        self.options = {
            'max_size': 5,
            'detail': 'operations', #depending on tracer.trace.levels (basically : events, operations or actions)
            }
        self.DetB = None
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
        mainbox = gtk.VBox()
        btnbar=gtk.HBox()

        # choix details
        if len(self.tracer.trace.levels.keys())<=0:
            print "Trace Preview error : no trace level"
        else:
            def details_changed(w):
                v=w.get_label()
                i=self.tracer.trace.levels.keys().index(v)+1
                if i>=len(self.tracer.trace.levels.keys()):
                    i=0
                v=self.tracer.trace.levels.keys()[i]
                w.set_label(v)
                #updating options
                self.options['detail']=v
                #refreshing display
                self.receive(self.tracer.trace)
                return
            bdetLabel = self.options['detail']
            bdet = gtk.Button(bdetLabel)
            self.DetB = bdet
            bdet.set_size_request(60, 20)
            btnbar.pack_start(gtk.Label(_(' Trace : ')), expand=False)
            btnbar.pack_start(bdet, expand=False)
            bdet.connect('clicked', details_changed)
        btnbar.pack_start(gtk.VSeparator())
        btngt = gtk.Button(_('Full trace'))
        btngt.set_tooltip_text(_('Open the trace timeline view fareast'))
        btngt.set_size_request(60, 20)
        def open_trace(w):
            self.controller.gui.open_adhoc_view(name='trace2', destination='fareast')
        btnbar.pack_start(btngt, expand=False)
        btngt.connect('clicked', open_trace)
            
        mainbox.pack_start(btnbar, expand=False)
        mainbox.pack_start(gtk.HSeparator(), expand=False)
        self.accuBox = gtk.VBox()
        self.sw = gtk.ScrolledWindow()
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.sw.add_with_viewport(self.accuBox)
        self.sw.set_vadjustment(gtk.Adjustment(value = 208, lower = 0, upper=208, step_incr=52, page_incr=208, page_size=208))
        mainbox.pack_start(self.sw)
        return mainbox


    def scroll_win(self):
        a = self.sw.get_vadjustment()
        a.value=a.upper
        return

    def receive(self, trace, event=None, operation=None, action=None):
        # trace : the full trace to be managed
        # event : the new or latest modified event
        # operation : the new or latest modified operation
        # action : the new or latest modified action
        #print "received : action %s, operation %s, event %s" % (action, operation, event)
        if self.options['detail'] == 'events':
            if event is None and not (operation is None and action is None):
                return
            self.showEvents(trace.levels[self.options['detail']], event)
        elif self.options['detail'] == 'operations':
            if operation is None and not (event is None and action is None):
                return
            self.showOperations(trace.levels[self.options['detail']], operation)
        elif self.options['detail'] == 'actions':
            if action is None and not (event is None and operation is None):
                return
            self.showActions(trace.levels[self.options['detail']], action)
        else:
            self.showTrace(trace.levels[self.options['detail']])
        self.scroll_win()

    def showTrace(self, level):
        # generic trace display
        return

    def showEvents(self, tracelevel, event):
        #adjust the current display to the modified trace
        if event is not None:
            if self.size>=self.options['max_size']:
                self.unpackEvent()
            self.packObs(event, 'events')
        else:
            #refreshing the whole trace
            while self.size > 0:
                self.unpackEvent()
            if len(tracelevel)==0:
                return
            trace_max = max(0, len(tracelevel))
            trace_min = max(0, trace_max-self.options['max_size'])
            t_temp = trace_max-1
            #print 'First min %s' % trace_min
            while t_temp > trace_min and trace_min>0:
                t_temp = t_temp-1
            #print 'Final min %s' % trace_min
            for i in tracelevel[trace_min:trace_max]:
                self.packObs(i, 'events')
        return

    def showOperations(self, tracelevel, operation):
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

    def showActions(self, tracelevel, action):
        #print "action recue : %s , trace : %s" % (action, len(tracelevel))
        if action is None:
            #refreshing the whole trace
            while self.size > 0:
                self.unpackEvent()
            if len(tracelevel)==0:
                return
            trace_max = max(0, len(tracelevel))
            trace_min = max(0, trace_max-self.options['max_size'])
            #print "min %s, max %s" % (trace_min, trace_max)
            t_temp = trace_max-1
            while t_temp > trace_min and trace_min > 0:
                if tracelevel[t_temp].name == "Undefined":
                    trace_min = trace_min-1
                t_temp = t_temp -1
            for i in tracelevel[trace_min:trace_max]:
                if i.name == "Undefined":
                    print "Trace Preview: Undefined action for object %s" % i
                    pass
                self.packObs(i, 'actions')
            return
        #adjust the current display to the modified trace
        if action.name == "Undefined":
            print "Trace Preview: Undefined action for object %s" % action
            return
        if action == self.last_obs:
            # same action as before, we just need to refresh it
            self.update_last_action_box(action)
            return
        if self.size>=self.options['max_size']:
            self.unpackEvent()
        self.packObs(action, 'actions')
        return

    def packObs(self, obj_evt, level):
        if obj_evt is not None:
            vb=gtk.VBox()
            self.last_obs_box = self.buildBox(obj_evt, level)
            self.last_obs = obj_evt
            vb.add(self.last_obs_box)
            vb.add(gtk.HSeparator())
            self.accuBox.pack_start(vb, expand=False)
            self.accuBox.show_all()
            self.size = self.size + 1

    def buildBox(self, obj_evt, level):
        if level<0:
            print 'refresh trace'
        else:
            corpsstr = ''
            entetestr = ''
            if obj_evt.content is not None:
                corpsstr = urllib.unquote(obj_evt.content.encode('utf-8'))
            if isinstance(obj_evt.time, float):
                ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time))
            else: 
                # intervalle
                ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time[0]))
            if hasattr(obj_evt, 'operations'):
                entetestr = "%s : %s" % (ev_time, obj_evt.name)
                for op in obj_evt.operations:
                    op_time = time.strftime("%H:%M:%S", time.localtime(op.time))
                    if op.concerned_object['name'] is None:
                        corpsstr += urllib.unquote( op_time + " : " + op.name + "\n")
                    else:
                        corpsstr += urllib.unquote( op_time + " : " + op.name + " ( " + op.concerned_object['name'] + " : " + op.concerned_object['id'] + " )\n")
            else:
                if obj_evt.name in self.incomplete_operations_names.keys():
                    comp = ''
                    if obj_evt.concerned_object['id']:
                        ob = self.controller.package.get_element_by_id(obj_evt.concerned_object['id'])
                        #print "%s %s %s" % (self.controller.package, obj_evt.concerned_object['id'], ob)
                        if isinstance(ob, advene.model.annotation.Annotation):
                            comp = _('of an annotation (%s)') % obj_evt.concerned_object['id']
                        elif isinstance(ob,advene.model.annotation.Relation):
                            comp = _('of a relation (%s)') % obj_evt.concerned_object['id']
                        elif isinstance(ob,advene.model.schema.AnnotationType):
                            comp = _('of an annotation type (%s)') % obj_evt.concerned_object['id']
                        elif isinstance(ob,advene.model.schema.RelationType):
                            comp = _('of a relation type (%s)') % obj_evt.concerned_object['id']
                        elif isinstance(ob,advene.model.schema.Schema):
                            comp = _('of a schema (%s)') % obj_evt.concerned_object['id']
                        elif isinstance(ob,advene.model.view.View):
                            comp = _('of a view (%s)') % obj_evt.concerned_object['id']
                        elif isinstance(ob,advene.model.package.Package):
                            comp = _('of a package (%s)') % obj_evt.concerned_object['id']
                        else:
                            comp = _('of an unknown item (%s)') % obj_evt.concerned_object['id']
                            #print "%s" % ob
                    entetestr = "%s : %s %s" % (ev_time, self.incomplete_operations_names[obj_evt.name], comp)
                elif obj_evt.name in ECACatalog.event_names:
                    if ECACatalog.event_names[obj_evt.name]:
                        entetestr = "%s : %s" % (ev_time, ECACatalog.event_names[obj_evt.name])
                    else:
                        entetestr = "%s : %s" % (ev_time, "Observed item not described")
                    if obj_evt.concerned_object['id']:
                        entetestr = entetestr + ' (%s)' % obj_evt.concerned_object['id']
                else:
                    print "Trace Preview: unlabelled observed item : %s" % obj_evt.name
                    entetestr = "%s : %s" % (ev_time, obj_evt.name)
            entete = gtk.Label(entetestr.encode("UTF-8"))
            hb = gtk.HBox()
            tr = TimestampRepresentation(obj_evt.movietime, self.controller, self.box_h, 0, None , False)
            if tr is not None:
                hb.pack_start(tr, expand=False)
                hb.pack_start(gtk.VSeparator(), expand=False)
            pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 20, self.box_h)
            color = 0xdddd00FF
            if obj_evt.name in self.tracer.colormodel[level].keys():
                color = self.tracer.colormodel[level][obj_evt.name]
            pb.fill(color)
            im = gtk.image_new_from_pixbuf(pb)
            hb.pack_start(im, expand=False)
            hb.pack_start(entete, expand=False)
            if corpsstr != "":
                hb.set_tooltip_text(corpsstr)
            return hb

    def unpackEvent(self):
        if self.accuBox.get_children():
            self.accuBox.remove(self.accuBox.get_children()[0])
        else:
            print "Trace Preview: no event to unpack ? %s" % self.size
        if self.size>0:
            self.size = self.size-1

    def update_last_action_box(self, obj_evt):
        corpsstr = ""
        for op in obj_evt.operations:
            op_time = time.strftime("%H:%M:%S", time.localtime(op.time))
            if op.concerned_object['name'] is None:
                corpsstr += urllib.unquote( op_time + " : " + op.name + "\n")
            else:
                corpsstr += urllib.unquote( op_time + " : " + op.name + " ( " + op.concerned_object['name'] + " : " + op.concerned_object['id'] + " )\n")
        self.last_obs_box.set_tooltip_text(corpsstr)
        self.receive(self.tracer.trace)

    def destroy(self, source=None, event=None):
        self.controller.tracers[0].unregister_view(self)
        return False
