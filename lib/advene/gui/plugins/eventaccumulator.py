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

from advene.gui.views import AdhocView
import advene.util.helper as helper
import urllib
import advene.model.view
from advene.gui.widget import TimestampRepresentation
from advene.rules.elements import ECACatalog

def register(controller):
    controller.register_viewclass(EventAccumulator)

name="Trace view"

class EventAccumulator(AdhocView):
    view_name = _("Activity trace")
    view_id = 'trace'
    tooltip=("Trace of user activity")
    def __init__ (self, controller=None, parameters=None, package=None):
        super(EventAccumulator, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.sw = None
        self.size = 0
        self.filters = {
            'content': '',
            'objects': [],
            'events': ['AnnotationBegin','AnnotationEnd','BookmarkHighlight','BookmarkUnhighlight','PopupDisplay','SnapshotUpdate'],
            'operations': [],
            'actions': [],
        }
        self.times=['real', 'activity']
        self.latest = {
            'events': None,
            'operations': None,
            'actions': None,
            'eventsBox': None,
            'operationsBox': None,
            'actionsBox': None,
            'nav_action':None,
            'nav_actionBox':None,
        }
        # ECACatalog event_names et set(())
        self.events_names= ['DurationUpdate','AnnotationBegin','AnnotationEnd','BookmarkHighlight','BookmarkUnhighlight','PackageLoad','PopupDisplay','MediaChange','PackageActivate','PackageSave','ApplicationStart','SnapshotUpdate']
        self.operations_names = ['AnnotationCreate','AnnotationEditEnd','AnnotationDelete','RelationCreate','AnnotationMerge','AnnotationMove','PlayerStart','PlayerStop','PlayerPause','PlayerResume','PlayerSet','ViewActivation','AnnotationTypeCreate','RelationTypeCreate','RelationTypeDelete','AnnotationTypeDelete','AnnotationTypeEditEnd','RelationTypeEditEnd','ViewCreate','ViewEditEnd']
        self.incomplete_operations_names = {
            'EditSessionStart': _('Beginning edition'),
            'ElementEditBegin': _('Beginning edition'),
            'ElementEditDestroy': _('Canceling edition'),
            'ElementEditCancel': _('Canceling edition'),
            'EditSessionEnd': _('Canceling edition'),
            'ElementEditEnd': _('Ending edition'),
        }

        #self.contextual_actions = (
        #    (_("Save view"), self.save_view),
        #    (_("Save default options"), self.save_default_options),
        #    )
        self.options = {
            'max_size': 20,
            'time': 'real', #real or activity
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
        self.DetB = None
        self.accuBox = None
        self.sc = None
        self.btn_filter = None
        self.init_btn_evb = None
        self.init_btn_filter = None
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
            self.DetB = bdet
            bdet.set_size_request(60, 20)
            btnbar.pack_start(gtk.Label(_(' Trace : ')), expand=False)
            btnbar.pack_start(bdet, expand=False)
            bdet.connect('clicked', details_changed)

        self.btn_filter = gtk.Button(_(' Filters'))
        self.btn_filter.connect('clicked', self.modify_filters)
        btnbar.pack_start(self.btn_filter, expand=False)

        self.init_btn_filter = gtk.Button(_('Reset'))
        self.init_btn_filter.connect('clicked', self.init_obj_filter)
        self.init_btn_filter.set_sensitive(False)
        btnbar.pack_start(self.init_btn_filter, expand=False)
        self.filter_active(False)
        btnbar.pack_start(gtk.VSeparator())

        # choix temps
        if not self.times:
            print "EventAccumulator error : no times defined"
        else:
            def time_changed(w):
                v=w.get_label()
                i=(self.times.index(v) + 1) % len(self.times)
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
        self.sc = gtk.HScale(gtk.Adjustment ( value=20, lower=5, upper=5000, step_incr=1, page_incr=5, page_size=5))
        self.sc.set_size_request(100, 10)
        self.sc.set_digits(0)
        self.sc.set_value_pos(gtk.POS_LEFT)
        self.sc.connect('value_changed', max_changed)
        btnbar.pack_start(self.sc, expand=False)
        btnbar.pack_start(gtk.VSeparator())

        exp_b = gtk.Button(_('Export'))
        exp_b.connect('clicked', self.export)
        btnbar.pack_start(exp_b, expand=False)

        mainbox.pack_start(btnbar, expand=False)
        mainbox.pack_start(gtk.HSeparator(), expand=False)
        self.accuBox=gtk.VBox()
        self.sw = gtk.ScrolledWindow()
        self.sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.sw.add_with_viewport(self.accuBox)
        self.sw.set_vadjustment(gtk.Adjustment(value = 208, lower = 0, upper=208, step_incr=52, page_incr=208, page_size=208))
        mainbox.pack_start(self.sw)
        return mainbox

    def export(self, w):
        fname = self.tracer.export()
        d = gtk.Dialog(title=_("Exporting traces"),
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK
                                 ))
        l=gtk.Label(_("Export done to\n%s") % fname)
        l.set_selectable(True)
        l.set_line_wrap(True)
        l.show()
        d.vbox.pack_start(l, expand=False)
        d.vbox.show_all()
        d.show()
        res=d.run()
        d.destroy()
        return

    def modify_filters(self, w):
        w=gtk.Window(gtk.WINDOW_TOPLEVEL)
        def level_changed(w, options):
            v=w.get_label()
            i=self.tracer.trace.levels.keys().index(v)+1
            if i>=len(self.tracer.trace.levels.keys()):
                i=0
            v=self.tracer.trace.levels.keys()[i]
            w.set_label(v)
            self.show_options(options, v)
            options.show_all()
            return
        vb = gtk.VBox()
        levelslab = self.options['detail']
        levels = gtk.Button(levelslab)
        vb.pack_start(levels, expand=False)
        #levels.set_size_request(60, 20)
        vb.pack_start(gtk.HSeparator(), expand=False)
        options = gtk.VBox()
        self.show_options(options, levelslab)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_size_request(600, 480)
        sw.add_with_viewport(options)
        vb.pack_start(sw, expand=False)
        vb.pack_start(gtk.HSeparator(), expand=False)
        def options_quit(w, window):
            window.destroy()
            return
        hbb = gtk.HBox()
        btn_q = gtk.Button(stock=gtk.STOCK_CLOSE)
        hbb.pack_end(btn_q, expand=False)
        btn_q.connect('clicked', options_quit, w)
        vb.pack_end(hbb, expand=False)
        levels.connect('clicked', level_changed, options)
        w.set_name(_('Defining Filters'))
        w.add(vb)
        w.show_all()
        #sw.connect

    def show_options(self, options, levelslab):
        for ob in options.get_children():
            options.remove(ob)
        def option_clicked(w, name, levelslab):
            #print '%s %s %s' % (name, w.get_active(), levelslab)
            if w.get_active():
                self.filters[levelslab].remove(name)
            else:
                self.filters[levelslab].append(name)
            self.receive(self.tracer.trace)
            return
        if levelslab == 'events':
            for i in self.events_names:
                option = gtk.CheckButton( ECACatalog.event_names[i])
                options.pack_start(option, expand=False)
                if i in self.filters[levelslab]:
                    option.set_active(False)
                else:
                    option.set_active(True)
                option.connect('toggled', option_clicked, i, levelslab)
        if levelslab == 'events' or levelslab == 'operations':
            for i in self.operations_names:
                option = gtk.CheckButton( ECACatalog.event_names[i])
                options.pack_start(option, expand=False)
                if i in self.filters[levelslab]:
                    option.set_active(False)
                else:
                    option.set_active(True)
                option.connect('toggled', option_clicked, i, levelslab)
            for i in self.incomplete_operations_names.keys():
                option = gtk.CheckButton(self.incomplete_operations_names[i])
                options.pack_start(option, expand=False)
                if i in self.filters[levelslab]:
                    option.set_active(False)
                else:
                    option.set_active(True)
                option.connect('toggled', option_clicked, i, levelslab)
        if levelslab == 'actions':
            for i in self.tracer.action_types:
                option = gtk.CheckButton(i)
                options.pack_start(option, expand=False)
                if i in self.filters[levelslab]:
                    option.set_active(False)
                else:
                    option.set_active(True)
                option.connect('toggled', option_clicked, i, levelslab)
        return

    def init_filters(self, w):
        self.filters = {
            'content': '',
            'objects': [],
            'events': ['DurationUpdate','AnnotationBegin','AnnotationEnd','BookmarkHighlight','BookmarkUnhighlight','PopupDisplay','SnapshotUpdate'],
            'operations': [],
            'actions': [],
        }
        self.filter_active(False)
        self.receive(self.tracer.trace)

    def init_obj_filter(self, w):
        self.filters['objects']=[]
        self.filter_active(False)
        self.receive(self.tracer.trace)
        return

    def filter_active(self, activate):
        #i=gtk.Image()
        #if activate:
            #i.set_from_file(config.data.advenefile( ( 'pixmaps', 'filters_off.png') ))
        #else:
            #i.set_from_file(config.data.advenefile( ( 'pixmaps', 'filters_on.png') ))
        #self.init_btn_filter.set_image(i)
        self.init_btn_filter.set_sensitive(activate)



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
            if (event is not None and event.name in self.filters['events']):
                return
            self.showEvents(trace.levels[self.options['detail']], event)
        if self.options['detail'] == 'operations':
            if (operation is not None and operation.name in self.filters['operations']):
                return
            self.showOperations(trace.levels[self.options['detail']], operation)
        elif self.options['detail'] == 'actions':
            if (action is not None and action.name in self.filters['actions']):
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
            #if event.name in self.filters['events']:
            #    return
            if self.size>=self.options['max_size']:
                self.unpackEvent()
            self.packEvent(event)
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
                if tracelevel[t_temp].name in self.filters['events']:
                    #print 'Ignored %s' % tracelevel[t_temp].name
                    trace_min = trace_min-1
                t_temp = t_temp-1
            #print 'Final min %s' % trace_min
            for i in tracelevel[trace_min:trace_max]:
                if i.name not in self.filters['events']:
                    #print "%s %s" % (self.size, i.name)
                    self.packEvent(i)
        return

    def showOperations(self, tracelevel, operation):
        #adjust the current display to the modified trace
        filter_obj = (len(self.filters['objects'])>0)
        #print filter_obj
        if operation is not None:
            if filter_obj and operation not in self.filters['objects']:
                return
            if self.size>=self.options['max_size']:
                self.unpackEvent()
            self.packOperation(operation)
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
                if (filter_obj and tracelevel[t_temp] not in self.filters['objects']) or tracelevel[t_temp].name in self.filters['operations']:
                    trace_min = trace_min-1
                t_temp = t_temp -1
            for i in tracelevel[trace_min:trace_max]:
                if (not filter_obj or i in self.filters['objects']) and i.name not in self.filters['operations']:
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
            t_temp = trace_max-1
            while t_temp > trace_min and trace_min > 0:
                if tracelevel[t_temp].name == "Undefined" or tracelevel[t_temp].name in self.filters['actions']:
                    trace_min = trace_min-1
                t_temp = t_temp -1
            for i in tracelevel[trace_min:trace_max]:
                if i.name == "Undefined":
                    print "Undefined action for object %s" % i
                    pass
                if i.name not in self.filters['actions']:
                    #print "%s %s" % (self.size, i.name)
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
        elif action == self.latest['nav_action']:
            self.update_last_action_box(action, True)
            return
        if self.size>=self.options['max_size']:
            self.unpackEvent()
        self.packAction(action)
        return

    def packAction(self, obj_evt):
        vb=gtk.VBox()
        if obj_evt.name == 'Navigation':
            self.latest['nav_action'] = obj_evt
            self.latest['nav_actionBox'] = self.build_action_box(obj_evt)
        self.latest['actions'] = obj_evt
        self.latest['actionsBox'] = self.build_action_box(obj_evt)
        vb.add(self.latest['actionsBox'])
        vb.add(gtk.HSeparator())
        self.accuBox.pack_start(vb, expand=False)
        self.accuBox.show_all()
        self.size = self.size + 1

    def packOperation(self, obj_evt):
        if obj_evt is not None:
            self.latest['operations']=obj_evt
            vb=gtk.VBox()
            self.latest['operationsBox'] = self.build_operation_box(obj_evt)
            vb.add(self.latest['operationsBox'])
            vb.add(gtk.HSeparator())
            self.accuBox.pack_start(vb, expand=False)
            self.accuBox.show_all()
            self.size = self.size + 1

    def packEvent(self, obj_evt):
        if obj_evt is not None:
            self.latest['events']=obj_evt
            vb=gtk.VBox()
            self.latest['eventsBox'] = self.build_event_box(obj_evt)
            vb.add(self.latest['eventsBox'])
            vb.add(gtk.HSeparator())
            self.accuBox.pack_start(vb, expand=False)
            self.accuBox.show_all()
            self.size = self.size + 1

    def unpackEvent(self):
        if self.accuBox.get_children():
            self.accuBox.remove(self.accuBox.get_children()[0])
        else:
            print "no event to unpack ? %s" % self.size
        if self.size>0:
            self.size = self.size-1


    def update_last_action_box(self, obj_evt, nav=False):
        if nav:
            tup = gtk.tooltips_data_get(self.latest['nav_actionBox'])
        else:
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
        corpsstr = ''
        entetestr = ''
        if obj_evt.content is not None:
            corpsstr = urllib.unquote(obj_evt.content)
        ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time))
        if self.options['time'] == 'activity':
            ev_time = helper.format_time(obj_evt.activity_time)
        if obj_evt.name in self.events_names or obj_evt.name in self.operations_names:
            if ECACatalog.event_names[obj_evt.name]:
                entetestr = "%s : %s" % (ev_time, ECACatalog.event_names[obj_evt.name])
            else:
                entetestr = "%s : %s" % (ev_time, "Event not described")
            if obj_evt.concerned_object['id']:
                entetestr = entetestr + ' (%s)' % obj_evt.concerned_object['id']
        elif obj_evt.name in self.incomplete_operations_names.keys():
            comp = ''
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
        else:
            print "unlabelled event : %s" % obj_evt.name
            entetestr = "%s : %s" % (ev_time, obj_evt.name)
        entete = gtk.Label(entetestr.encode("UTF-8"))
        hb = gtk.HBox()
        tr = TimestampRepresentation(obj_evt.movietime, self.controller, 50, 0, None , False)
        if tr is not None:
            hb.pack_start(tr, expand=False)
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
        corpsstr = ''
        if obj_evt.content is not None:
            corpsstr = urllib.unquote(obj_evt.content)
        ev_time = time.strftime("%H:%M:%S", time.localtime(obj_evt.time))
        if self.options['time'] == 'activity':
            ev_time = helper.format_time(obj_evt.activity_time)
        if obj_evt.name in self.operations_names:
            if ECACatalog.event_names[obj_evt.name]:
                entetestr = "%s : %s" % (ev_time, ECACatalog.event_names[obj_evt.name])
            else:
                entetestr = "%s : %s" % (ev_time, "Operation not described")
            if obj_evt.concerned_object['id']:
                entetestr = entetestr + ' (%s)' % obj_evt.concerned_object['id']
        elif obj_evt.name in self.incomplete_operations_names.keys():
            comp = ''
            # store type of item in the trace
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
            entetestr = "%s : %s %s" % (ev_time, self.incomplete_operations_names[obj_evt.name], comp)
        else:
            print "unlabelled event : %s" % obj_evt.name
            entetestr = "%s : %s" % (ev_time, obj_evt.name)
        entete = gtk.Label(entetestr.encode("UTF-8"))
        hb = gtk.HBox()
        box = gtk.EventBox()
        tr = TimestampRepresentation(obj_evt.movietime, self.controller, 50, 0, None , False)
        if tr is not None:
            hb.pack_start(tr, expand=False)
            hb.pack_start(gtk.VSeparator(), expand=False)
        if corpsstr != "":
            self.toolTips.set_tip(box,corpsstr)
        def box_pressed(w, event, id):
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
            return
        box.add(entete)
        box.connect('button-press-event', box_pressed, obj_evt.concerned_object['id'])
        hb.pack_start(box, expand=False)
        return hb

    def build_action_box(self, obj_evt):
        # build the widget to present an event :
        # tooltip with event infos
        # image containing snapshot of the event
        # label with the time of the event
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
        hb = gtk.HBox()
        box = gtk.EventBox()
        tr = TimestampRepresentation(obj_evt.movietime, self.controller, 50, 0, None , False)
        if tr is not None:
            hb.pack_start(tr, expand=False)
            hb.pack_start(gtk.VSeparator(), expand=False)
        if corpsstr != "":
            self.toolTips.set_tip(hb,corpsstr)
        def box_pressed(w, event, ops):
            if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                #FIXME : need to change details in another way
                self.filters['objects']=[]
                self.filters['objects'].extend(ops)
                self.options['detail']='operations'
                self.DetB.set_label('operations')
                #FIXME color change of the reset button when applying a filter
                self.filter_active(True)
                self.receive(self.tracer.trace)
            return
        box.add(entete)
        box.connect('button-press-event', box_pressed, obj_evt.operations)
        hb.pack_start(box, expand=False)
        return hb

    def destroy(self, source=None, event=None):
        self.controller.tracers[0].unregister_view(self)
        return False




#TODO
#       des moyens d'actions depuis les events
#       filtrage pre et post visu
#       recherche dans la trace

