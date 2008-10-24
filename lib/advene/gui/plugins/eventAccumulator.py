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
"""Event Accumulator.

This widget allows to stack compact event history.
"""

import gtk
import time

from gettext import gettext as _

import advene.core.config as config
from advene.gui.views import AdhocView
from advene.gui.util import png_to_pixbuf
import advene.util.helper as helper
import urllib
import advene.model.view

def register(controller):
    controller.register_viewclass(EventAccumulator)
    

name="Trace view"

class EventAccumulator(AdhocView):
    view_name = _("Trace")
    view_id = 'trace_1'
    tooltip=("Trace of Advene Events")
    def __init__ (self, controller=None, parameters=None, package=None):
        super(EventAccumulator, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.sw = None
        self.size = 0
        self.filters = {
            'content': '',
        }
        self.times=[_('real'), _('activity')]
        self.latest = {
            'events': None,
            'operations': None,
            'actions': None,
            'eventsBox': None,
            'operationsBox': None,
            'actionsBox': None,
        }
        self.operations_names = {
            'AnnotationCreate': _('Creating an annotation'),
            'AnnotationEditEnd': _('Validating edition of an annotation'),
            'AnnotationDelete': _('Deleting an annotation'),
            'RelationCreate': _('Creating a relation'),
            'AnnotationMerge': _('Merging annotations'),
            'AnnotationMove': _('Moving an annotation'),
            'PlayerStart': _('Starting playback'),
            'PlayerStop': _('Ending playback'),
            'PlayerPause': _('Pausing playback'),
            'PlayerResume': _('Resuming playback'),
            'PlayerSet': _('Moving to a position in the movie'),
            'ViewActivation': _('Activating a view'),
            'AnnotationTypeCreate': _('Creating an annotation type'),
            'RelationTypeCreate': _('Creating a relation type'),
            'RelationTypeDelete': _('Deleting a relation type'),
            'AnnotationTypeDelete': _('Deleting a relation type'),
            'AnnotationTypeEditEnd': _('Ending edition of an annotation type'),
            'RelationTypeEditEnd': _('Ending edition of a relation type'),
            'ViewCreate': _('Creating a view'),
            'ViewEditEnd': _('Ending edition of a view'),
        }
        self.incomplete_operations_names = {
            'ElementEditBegin': _('Beginning edition'),
            'ElementEditDestroy': _('Ending edition'),
            'ElementEditCancel': _('Canceling edition'),
        }
        #self.contextual_actions = (
        #    (_("Save view"), self.save_view),
        #    (_("Save default options"), self.save_default_options),
        #    )
        self.options = {
            'max_size': 20,
            'time': _('real'), #real or activity
            'detail': 'operations', #depending on tracer.trace.levels (basically : events, operations or actions)
            }
        #opt, arg = self.load_parameters(parameters)
        #self.options.update(opt)
        self.toolTips = gtk.Tooltips()
        self.toolTips.enable()
        self.__package=package
        if package is None and controller is not None:
            self.__package=controller.package
        self.tracer = self.controller.tracers[0]
        #self.cached_trace = None
        self.accuBox = None
        self.comboD = None
        self.comboT = None
        self.sc = None
        self.btn_filter = None
        self.widget = self.build_widget()
        self.widget.connect("destroy", self.destroy)
        #registering plugin with trace builder
        #self.controller.event_handler.register_view(self)
        self.tracer.register_view(self)
        self.receive(self.tracer.trace)

    def build_widget(self):
        mainbox = gtk.VBox()
        btnbar=gtk.HBox()
     
        # choix details
        if len(self.tracer.trace.levels.keys())<=0:
            print "EventAccumulator error : no trace level"
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
            bdet.set_size_request(60, 20)
            btnbar.pack_start(gtk.Label(_(' Details : ')), expand=False)
            btnbar.pack_start(bdet, expand=False)
            bdet.connect('clicked', details_changed)
            btnbar.pack_start(gtk.VSeparator())

        # choix temps
        if len(self.times)<=0:
            print "EventAccumulator error : no times defined"
        else:
            def time_changed(w):
                v=w.get_label()
                i=self.times.index(v)+1
                if i>=len(self.times):
                    i=0
                v=self.times[i]
                w.set_label(v)
                #updating options
                self.options['time']=v
                #refreshing display
                self.receive(self.tracer.trace)
                return
            
            btimeLabel = self.options['time']
            btime = gtk.Button(btimeLabel)
            btime.set_size_request(60, 20)
            btnbar.pack_start(gtk.Label(_(' Time : ')), expand=False)
            btnbar.pack_start(btime, expand=False)
            btime.connect('clicked', time_changed)
            btnbar.pack_start(gtk.VSeparator())
        
        # choix max
        def max_changed(w):
            self.options['max_size']=int(w.get_value())
            self.receive(self.tracer.trace)
            return
        btnbar.pack_start(gtk.Label(_(' Max. : ')), expand=False)
        self.sc = gtk.HScale(gtk.Adjustment ( value=20, lower=5, upper=100, step_incr=1, page_incr=5, page_size=5))
        self.sc.set_size_request(100, 10)
        self.sc.set_digits(0)
        self.sc.set_value_pos(gtk.POS_LEFT)
        self.sc.connect('value_changed', max_changed)
        btnbar.pack_start(self.sc, expand=False)
        btnbar.pack_start(gtk.VSeparator())

        self.btn_filter = gtk.Button(_(' Filters'))
        #self.btn_filter.connect('clicked', self.open_filters)
        btnbar.pack_start(self.btn_filter, expand=False)
        
        mainbox.pack_start(btnbar, expand=False)
        mainbox.pack_start(gtk.HSeparator(), expand=False)
        self.accuBox=gtk.VBox()
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
            self.showEvents(trace.levels[self.options['detail']], event)
        if self.options['detail'] == 'operations':
            self.showOperations(trace.levels[self.options['detail']], operation)
        elif self.options['detail'] == 'actions':
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
            self.size = self.size + 1
            self.packEvent(event)
        else:
            #refreshing the whole trace
            while self.size > 0:
                self.unpackEvent()
            if len(tracelevel)==0:
                return
            trace_max = max(0, len(tracelevel))
            trace_min = max(0, trace_max-self.options['max_size'])
            for i in tracelevel[trace_min:trace_max]:
                self.size = self.size + 1
                #print "%s %s" % (self.size, i.name)
                self.packEvent(i)
        return
    
    def showOperations(self, tracelevel, operation):
        #adjust the current display to the modified trace
        if operation is not None:
            if self.size>=self.options['max_size']:
                self.unpackEvent()
            self.size = self.size + 1
            self.packOperation(operation)
        else:
            #refreshing the whole trace
            while self.size > 0:
                self.unpackEvent()
            if len(tracelevel)==0:
                return
            trace_max = max(0, len(tracelevel))
            trace_min = max(0, trace_max-self.options['max_size'])
            for i in tracelevel[trace_min:trace_max]:
                self.size = self.size + 1
                #print "%s %s" % (self.size, i.name)
                self.packOperation(i)
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
            for i in tracelevel[trace_min:trace_max]:
                if i.name == "Undefined":
                    print "Undefined action for object %s" % i
                    pass
                #print "%s %s" % (self.size, i.name)
                self.size = self.size + 1
                #print "pack %s" % i
                self.packAction(i)
            return
        #adjust the current display to the modified trace
        if action.name == "Undefined":
            print "Undefined action for object %s" % action
            return
        if action == self.latest['actions']:
            # same action as before, we just need to refresh it
            self.update_last_action_box(action)
            return
        if self.size>=self.options['max_size']:
            self.unpackEvent()
        self.size = self.size + 1
        self.packAction(action)
        return
    
    def packAction(self, obj_evt):
        self.latest['actions'] = obj_evt
        vb=gtk.VBox()
        self.latest['actionsBox'] = self.build_action_box(obj_evt)
        vb.add(self.latest['actionsBox'])
        vb.add(gtk.HSeparator())
        self.accuBox.pack_start(vb, expand=False)
        self.accuBox.show_all()

    def packOperation(self, obj_evt):
        if obj_evt is not None:
            self.latest['operations']=obj_evt
            vb=gtk.VBox()
            self.latest['operationsBox'] = self.build_operation_box(obj_evt)
            vb.add(self.latest['operationsBox'])
            vb.add(gtk.HSeparator())
            self.accuBox.pack_start(vb, expand=False)
            self.accuBox.show_all()
    
    def packEvent(self, obj_evt):
        if obj_evt is not None:
            self.latest['events']=obj_evt
            vb=gtk.VBox()
            self.latest['eventsBox'] = self.build_event_box(obj_evt)
            vb.add(self.latest['eventsBox'])
            vb.add(gtk.HSeparator())
            self.accuBox.pack_start(vb, expand=False)
            self.accuBox.show_all()
        
    def unpackEvent(self):
        self.accuBox.remove(self.accuBox.get_children()[0])
        self.size = self.size-1

    def update_last_action_box(self, obj_evt):
        tup = gtk.tooltips_data_get(self.latest['actionsBox'])
        if tup is None:
            return
        corpsstr = ""
        for op in obj_evt.operations:
            op_time = time.strftime("%H:%M:%S", time.localtime(op.time))
            if self.options['time'] == 'activity':
                op_time = helper.format_time(op.activity_time)
            if op.concerned_object['name'] is None:
                corpsstr += urllib.unquote( op_time + " : " + op.name + "\n")
            else:
                corpsstr += urllib.unquote( op_time + " : " + op.name + " ( " + op.concerned_object['name'] + " : " + op.concerned_object['id'] + " )\n")
        self.toolTips.set_tip(tup[1], corpsstr)
        self.receive(self.tracer.trace)
        # workaround to solve tooltip refresh problem

    def build_event_box(self, obj_evt):
        # build the widget to present an event :
        # tooltip with event infos
        # image containing snapshot of the event
        # label with the time of the event
        snap = obj_evt.snapshot
        pix = png_to_pixbuf(snap,height=50)
        corpsstr = ""
        if obj_evt.content is not None:
            corpsstr = urllib.unquote(obj_evt.content)
        ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time))
        if self.options['time'] == 'activity':
            ev_time = helper.format_time(obj_evt.activity_time)
        entetestr = "%s : %s" % (ev_time, obj_evt.name)
        entete = gtk.Label(entetestr.encode("UTF-8"))
        #i = gtk.image_new_from_pixbuf(pix) pygtk2.12
        i = gtk.Image()
        i.set_from_pixbuf(pix)
        hb = gtk.HBox()
        if i is not None:
            hb.pack_start(i, expand=False)
            hb.pack_start(gtk.VSeparator(), expand=False)
        hb.pack_start(entete, expand=False)
        if corpsstr != "":
            self.toolTips.set_tip(hb,corpsstr)
        return hb

    def build_operation_box(self, obj_evt):
        # build the widget to present an event :
        # tooltip with event infos
        # image containing snapshot of the event
        # label with the time of the event
        snap = obj_evt.snapshot
        pix = png_to_pixbuf(snap,height=50)
        corpsstr = ''
        if obj_evt.content is not None:
            corpsstr = urllib.unquote(obj_evt.content)
        ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time))
        if self.options['time'] == 'activity':
            ev_time = helper.format_time(obj_evt.activity_time)
        if obj_evt.name in self.operations_names.keys():
            entetestr = "%s : %s" % (ev_time, self.operations_names[obj_evt.name])
        else:
            comp = ''
            ob = self.controller.package.get_element_by_id(obj_evt.concerned_object['id'])
            #print "%s %s %s" % (self.controller.package, obj_evt.concerned_object['id'], ob)
            if isinstance(ob, advene.model.annotation.Annotation):
                comp = _('an annotation')
            elif isinstance(ob,advene.model.annotation.Relation):
                comp = _('a relation')
            else:
                comp = _('an unknown item')
            entetestr = "%s : %s of %s" % (ev_time, self.incomplete_operations_names[obj_evt.name], comp)
            
        
        entete = gtk.Label(entetestr.encode("UTF-8"))
        #i = gtk.image_new_from_pixbuf(pix) pygtk2.12
        i = gtk.Image()
        i.set_from_pixbuf(pix)
        hb = gtk.HBox()
        box = gtk.EventBox()
        if i is not None:
            hb.pack_start(i, expand=False)
            hb.pack_start(gtk.VSeparator(), expand=False)
        hb.pack_start(entete, expand=False)
        if corpsstr != "":
            self.toolTips.set_tip(box,corpsstr)
        def box_pressed(w, event, id, mtime):
            #print "%s %s" % (id, mtime)
            if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                if id is not None:
                    obj = self.controller.package.get_element_by_id(id)
                    if obj is not None:
                        #Need to edit the item
                        #print obj
                        self.controller.gui.edit_element(obj)
                    else:
                        print "item %s no longuer exists" % id
                else:
                    #print mtime
                    c=self.controller
                    pos = c.create_position (value=mtime,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
                    c.update_status (status="set", position=pos)
                    #need to check if id is None then go to movietime
            return
        box.add(hb)
        box.connect('button-press-event', box_pressed, obj_evt.concerned_object['id'], obj_evt.movietime)
        return box

    def build_action_box(self, obj_evt):
        # build the widget to present an event :
        # tooltip with event infos
        # image containing snapshot of the event
        # label with the time of the event
        snap = obj_evt.snapshot
        pix = png_to_pixbuf(snap,height=50)
        act = obj_evt.name
        act_begin = time.strftime("%H:%M:%S", time.localtime(obj_evt.time[0]))
        if self.options['time'] == 'activity':
            act_begin = helper.format_time(obj_evt.activity_time[0])
        entetestr = "%s : %s" % (act_begin, act)
        corpsstr = ""
        for op in obj_evt.operations:
            op_time = time.strftime("%H:%M:%S", time.localtime(op.time))
            if self.options['time'] == 'activity':
                op_time = helper.format_time(op.activity_time)
            if op.concerned_object['name'] is None:
                corpsstr += urllib.unquote( op_time + " : " + op.name + "\n")
            else:
                corpsstr += urllib.unquote( op_time + " : " + op.name + " ( " + op.concerned_object['name'] + " : " + op.concerned_object['id'] + " )\n")
        entete = gtk.Label(entetestr.encode("UTF-8"))
        #i = gtk.image_new_from_pixbuf(pix) pygtk2.12
        i = gtk.Image()
        i.set_from_pixbuf(pix)
        hb = gtk.HBox()
        if i is not None:
            hb.pack_start(i, expand=False)
            hb.pack_start(gtk.VSeparator(), expand=False)
        hb.pack_start(entete, expand=False)
        if corpsstr != "":
            self.toolTips.set_tip(hb,corpsstr)
        return hb         

    def destroy(self, source=None, event=None):
        self.controller.tracers[0].unregister_view(self)
        return False




#TODO   
#       des moyens d'actions depuis les events
#       filtrage pre et post visu
#       recherche dans la trace

