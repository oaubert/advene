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
"""Trace builder.

This plugin build a Trace object from events.
It needs to register to the ECAEngine to capture events.
It transforms these events into Operation objects and Action objects.
Widgets can register with this trace builder to receive the trace.
"""

import os

from threading import Thread
import Queue
import gobject
import time
import socket
import urllib
import xml.dom
from gettext import gettext as _

import advene.core.config as config

import advene.model.view
import advene.util.ElementTree as ET

import advene.util.helper as helper
import advene.util.handyxml as handyxml

from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.package import Package

def register(controller):
    tb = TraceBuilder(controller)
    tb.start()
    controller.register_tracer(tb)
    return

name="Trace Builder plugin"

class TraceBuilder(Thread):
    def __init__ (self, controller=None, parameters=None, package=None, ntbd=False, nte=False):
        Thread.__init__(self)
        self.equeue = Queue.Queue(-1)
        self.exit_code = "###\n"
        #self.close_on_package_load = False

        self.controller=controller
        self.host = "::1" #"2a01:e35:2efc:5cd0:216:cbff:fea0:3fb9"
        self.port = 9992
        self.texp = None # thread to export trace to a network
        self.tbroad = None # thread to broadcast trace
        self.bdq = None # broadcasting queue
        self.network_broadcasting = ntbd
        self.network_exp = nte
        self.operations = []
        self.registered_views = []
        self.opened_actions = {}
        self.filtered_events = ['SnapshotUpdate', 'AnnotationBegin', 'AnnotationEnd', 'BookmarkHighlight', 'BookmarkUnhighlight']
        self.action_types = ['Annotation', 'Restructuration', 'Navigation', 'Classification', 'View building']
        self.operation_mapping = {
        'AnnotationCreate':0,
        'AnnotationEditEnd':1,
        'AnnotationDelete':1,
        'RelationCreate':1,
        'RelationEditEnd':1,
        'AnnotationMerge':1,
        'AnnotationMove':1,
        'PlayerStart':2,
        'PlayerStop':2,
        'PlayerPause':2,
        'PlayerResume':2,
        'PlayerSet':2,
        'ViewActivation':2,
        'ViewDeactivation':2,
        'AnnotationTypeCreate':3,
        'RelationTypeCreate':3,
        'RelationTypeDelete':3,
        'AnnotationTypeDelete':3,
        'AnnotationTypeEditEnd':3,
        'RelationTypeEditEnd':3,
        'SchemaCreate':3,
        'SchemaEditEnd':3,
        'SchemaDelete':3,
        'ViewCreate':4,
        'ViewEditEnd':4,
        'ViewDelete':4,
        'EditSessionStart':5,
        #'ElementEditEnd':5,
        'ElementEditDestroy':5,
        'EditSessionEnd':5,
        }
        self.editEndNames = ['ElementEditDestroy', 'ElementEditEnd', 'AnnotationEditEnd', 'RelationEditEnd', 'AnnotationTypeEditEnd', 'RelationTypeEditEnd', 'EditSessionEnd', 'ViewEditEnd', 'SchemaEditEnd']

        if package is None and controller is not None:
            package=controller.package
        self.__package=package
        if self.network_broadcasting:
            self.init_broadcasting()
        self.controller.event_handler.register_view(self)
        self.traces = []
        self.trace = Trace() # current trace
        self.trace.start = config.data.startup_time
        self.traces.append(self.trace)

    def log(self, msg, level=None):
        m=": ".join( ("Tracebuilder", msg) )
        if self.controller:
            self.controller.log(m, level)
        else:
            print m

    def run(self):
        while (1):
            #we shouldnt receive exception from the queue
            obj = self.equeue.get()
            if not isinstance(obj, dict):
                if obj == self.exit_code:
                    self.on_exit()
                    break
                else:
                    continue
            if obj['event_name'] in self.filtered_events:
                continue
            self.receive(obj)

    def on_exit(self):
        if self.network_exp:
            # wait for export thread death
            if self.texp is not None:
                if self.texp.isAlive():
                    self.log('Export thread still running, waiting for its death...')
                self.texp.join()
        # Also save trace on filesystem.
        if config.data.preferences['record-actions']:
            try:
                fn = self.export()
            except Exception, e:
                self.log("error exporting trace : %s" % unicode(e).encode('utf-8'))

        if self.network_broadcasting:
            self.end_broadcasting()

    def init_broadcasting(self):
        self.bdq = Queue.Queue(-1)
        self.tbroad = TBroadcast(self.host, self.port, self.bdq)
        self.tbroad.start()

    def export(self):
        # Check that there are events to record
        if not sum( len(l) for l in self.trace.levels.itervalues() ):
            self.log("No event to export")
            return ''

        fname=config.data.advenefile(time.strftime("trace_advene-%Y%m%d-%H%M%S"),
                                     category='settings')
        try:
            stream=open(fname, 'wb')
        except (OSError, IOError), e:
            #self.log(_("Cannot export to %(fname)s: %(e)s") % locals())
            self.log(_("Cannot export to %(fname)s: %(e)s") % locals())
            return None
        tr=ET.Element('trace', name=self.trace.name)
        for lvl in self.trace.levels.keys():
            grp = ET.Element(lvl)
            #everything can be rebuild from events.
            for (id_e, e) in enumerate(self.trace.levels[lvl]):
                #e.to_xml_string(id_e)
                grp.append(e.export(id_e))
            tr.append(grp)
            # everything except comments could be rebuild from events...

        helper.indent(tr)
        ET.ElementTree(tr).write(stream, encoding='utf-8')
        stream.close()
        if self.network_exp:
            self.network_export()
        self.log("trace exported to %s" % fname)
        return fname

    def toggle_network_export(self):
        self.network_exp = not self.network_exp
        self.log("network export %s" % self.network_exp)
        return

    def network_export(self):
        if not self.network_exp:
            return
        if self.texp is not None:
            if self.texp.isAlive():
                self.log("Export thread still running")
                return
            else:
                self.texp.join() # nettoie le zombie ou pas ...
        self.texp = TExport(self.host, self.port, self.trace)
        self.texp.start()

    def toggle_network_broadcasting(self):
        self.network_broadcasting = not self.network_broadcasting
        if self.network_broadcasting:
            self.init_broadcasting()
        else:
            self.end_broadcasting()
        self.log("broadcast %s" % self.network_broadcasting)
        return

    def end_broadcasting(self):
        if self.tbroad.isAlive(): # should always be
            self.log('Broadcasting thread still running, sending its death order !')
            self.bdq.put("###\n")
            self.tbroad.join()
        return

    def change_nework_infos(self, ip, port):
        bc=self.network_broadcasting
        if bc:
            self.toggle_network_broadcasting()
        self.host = ip
        self.port = port
        if bc:
            self.toggle_network_broadcasting()
        return

    def remove_trace(self, index):
        if index >= len(self.traces):
            return False
        self.traces.pop(index)
        self.alert_registered(None, None, None)
        return True

    def search(self, trace, words=u'', exact=False, options=None):
        if options is None:
            options=['oname', 'oid', 'ocontent']
        # exact will be to match exact terms or just find the terms in a string
        # oname : objects name
        # oid : objects id
        # ocontent : objects content
        temp=Trace()
        temp.rename('Results for \'%s\' in %s' % (words, trace.name))
        for e in trace.levels['events']:
            etemp = e.copy()
            temp.add_to_trace('events', etemp)
        for a in trace.levels['actions']:
            atemp = a.copy()
            atemp.operations=[]
            temp.add_to_trace('actions', atemp)

            for o in a.operations:
                if o.concerned_object['name'] is not None:
                    content=o.content.encode('utf-8')
                    contentb = content.find('content="')
                    if contentb > 0 :
                        contentb = contentb+9
                        contentf = content.find('"', contentb)
                        content = urllib.unquote(content[contentb:contentf])
                        content = unicode(content)
                    name = unicode(o.concerned_object['name'])
                    _id = o.concerned_object['id']
                    found = False or (not exact and 'oname' in options and name.find(words.lower())>=0) or (exact and 'oname' in options and name==words) or (not exact and 'oid' in options and _id.lower().find(words.lower())>=0) or (exact and 'oid' in options and _id==words) or (not exact and 'ocontent' in options and content.lower().find(words.lower())>=0) or (exact and 'ocontent' in options and content==words)
                    if found and not o in temp.levels['operations']:
                        otemp = o.copy()
                        temp.add_to_trace('operations', otemp)
                        atemp.operations.append(otemp)

            if len(atemp.operations)<=0:
                temp.remove_from_trace('actions', atemp)
        self.traces.append(temp)
        self.alert_registered(None, None, None)
        return temp

    def convert_old_trace(self, fname):
        #FIXME : complete the import and do not use handyxml.
        self.log('importing trace from %s' % fname)
        if not os.path.exists(fname):
            oldfname=fname
            fname = config.data.advenefile(oldfname, category='settings')
            self.log("%s not found, trying %s" % (oldfname, fname))
            if not os.path.exists(fname):
                self.log("%s not found, giving up." % fname)
                return False
        pk=handyxml.xml(fname, forced=True)
        if pk.node.nodeName != 'package':
            self.log("This does not look like a trace file.")
            return False
        self.traces.append(Trace())
        self.opened_actions = {}
        if pk.annotations:
            for an in pk.annotations[0].annotation:
                an_content = ''
                an_ac_time='0'
                an_m_time='0'
                an_movie_time='0'
                evn=None
                if an.childNodes:
                    an_ac_time=an.childNodes[1].getAttribute('begin')
                if an.content:
                    if an.content[0].childNodes:
                        evn=an.content[0].childNodes[0]
                        if evn and evn.nodeType is xml.dom.Node.TEXT_NODE:
                            an_content = evn.data.encode('utf-8')
                an_name = an.type[1:]
                if an_content.find('position='):
                    d= an_content.find('position=')
                    e = an_content.find('\n', an_content.find('position='))
                    an_m_time=an_content[d:e]
                #evt = Event(an_name, float(an_time), float(an_ac_time), an_content, an_movie, float(an_m_time), an_o_name, an_o_id)
                #evt.change_comment(ev.comment)
                #self.trace.add_to_trace('events', evt)
                self.log('%s %s %s' % (an_name, an_ac_time, an_content))
        return

    def imp_type(self, typ):
        if typ == 'advene.model.schema.Schema':
            return advene.model.schema.Schema
        elif typ == 'advene.model.schema.AnnotationType':
            return advene.model.schema.AnnotationType
        elif typ == 'advene.model.schema.RelationType':
            return advene.model.schema.RelationType
        elif typ == 'advene.model.annotation.Annotation':
            return advene.model.annotation.Annotation
        elif typ == 'advene.model.annotation.Relation':
            return advene.model.annotation.Relation
        elif typ == 'advene.model.view.View':
            return advene.model.view.View
        else:
            return None

    def import_trace(self, fname, reset=False):
        # fname : String, trace file path
        # reset : boolean, reset current trace FIXME: to be removed or modified
        # import append a trace to self.traces
        self.log('importing trace from %s' % fname)
        # reseting current trace
        if reset:
            self.trace = Trace()
            self.opened_actions = {}
            self.trace.start = config.data.startup_time
            # should be now
            self.log("Trace cleaned.")
        # checking trace path
        if not os.path.exists(fname):
            oldfname=fname
            fname = config.data.advenefile(oldfname, category='settings')
            self.log("%s not found, trying %s" % (oldfname, fname))
            if not os.path.exists(fname):
                self.log("%s not found, giving up." % fname)
                return False
        tr=handyxml.xml(fname, forced=True)
        lid=0
        if tr.node.nodeName != 'trace':
            self.log("This does not look like a trace file.")
            return False
        # creating an empty new trace
        self.traces.append(Trace())
        tmp_opened_actions = {}
        if hasattr(tr, 'name'):
            self.traces[-1].rename('%s (imported)' % tr.name)
        else:
            self.traces[-1].rename('No Name (imported)')
        events = tr
        if hasattr(tr, 'events'):
            events = tr.events[0]
        for ev in events.event:
            lid = lid+1
            ev_content = ''
            evn=None
            if ev.childNodes:
                evn=ev.childNodes[0]
            if evn and evn.nodeType is xml.dom.Node.TEXT_NODE:
                ev_content = evn.data.encode('utf-8')
            if ev.o_name=="None":
                ev.o_name=None
            if ev.o_id=="None":
                ev.o_id=None
            if not hasattr(ev, 'o_type') or ev.o_type=="None": #for compatibility with previous traces
                ev.o_type=None
            if not hasattr(ev, 'o_cid') or ev.o_cid=="None": #for compatibility with previous traces
                ev.o_cid=None
            if self.traces[-1].start == 0 or float(ev.time) < self.traces[-1].start:
                self.traces[-1].start=float(ev.time)
            evt = Event(ev.name, float(ev.time), float(ev.ac_time), ev_content, ev.movie, float(ev.m_time), ev.o_name, ev.o_id, self.imp_type(ev.o_type), ev.o_cid)
            evt.change_comment(ev.comment)
            self.traces[-1].add_to_trace('events', evt)
            if evt.name in self.operation_mapping.keys():
                op = Operation(ev.name, float(ev.time), float(ev.ac_time), ev_content, ev.movie, float(ev.m_time), ev.o_name, ev.o_id, self.imp_type(ev.o_type), ev.o_cid)
                self.traces[-1].add_to_trace('operations', op)
                if op is not None:
                    if ev.name in self.operation_mapping.keys():
                        ac_t = self.operation_mapping[ev.name]
                    else:
                        continue
                    typ = "Undefined"
                    if ac_t < len(self.action_types):
                        typ = self.action_types[ac_t]
                    if typ == "Undefined":
                        if ev.o_name=='annotation' or ev.o_name=='relation':
                            typ="Restructuration"
                        elif ev.o_name=='annotationtype' or ev.o_name=='relationtype' or ev.o_name=='schema':
                            typ="Classification"
                        elif ev.o_name=='view':
                            typ="View building"
                    if typ in tmp_opened_actions.keys():
                        # an action is already opened for this event
                        ac = tmp_opened_actions[typ]
                        if typ == "Navigation" and (op.name == "PlayerStop" or op.name == "PlayerPause"):
                            del tmp_opened_actions[typ]
                        ac.add_operation(op)
                        continue
                    for t in tmp_opened_actions.keys():
                        if t != "Navigation":
                            del tmp_opened_actions[t]
                    ac = Action(name=typ, begintime=op.time, endtime=None, acbegintime=op.activity_time, acendtime=None, content=None, movie=op.movie, movietime=op.movietime, operations=[op])
                    self.traces[-1].add_to_trace('actions', ac)
                    tmp_opened_actions[typ]=ac
        if hasattr(tr, 'actions'):
            for ac in tr.actions[0].action:
                self.traces[-1].levels['actions'][int(ac.id[1:])].change_comment(ac.comment)

        self.alert_registered(None, None, None)
        self.log("%s events imported" % lid)
        return True

    def receive(self, obj):
        # obj : received event
        ev = op = ac = None
        ev = self.packEvent(obj)
        # broadcast reseau
        if self.network_broadcasting:
            #verifying thread is still alive
            if self.tbroad.isAlive():
                self.bdq.put_nowait(ev)
            #should be handled in TBroadcast thread
            else:
                #cleaning
                self.toggle_network_broadcasting()
                #relaunching
                self.toggle_network_broadcasting()
                self.bdq.put_nowait(ev)
        if ev.name in self.operation_mapping.keys():
            op = self.packOperation(obj)
            if op is not None:
                ac = self.packAction(obj, op)
        self.alert_registered(ev, op, ac)

    def packEvent(self, obj):
        #print obj['event_name']
        if obj['event_name'] != 'SnapshotUpdate':
            self.controller.update_snapshot(self.controller.player.current_position_value)
        #ev_snapshot = self.controller.package.imagecache.get(self.controller.player.current_position_value, epsilon=100)
        ev_time = time.time()
        ev_activity_time = (time.time() - self.trace.start) * 1000
        ev_name = obj['event_name']
        ev_movie = self.controller.package.getMetaData(config.data.namespace, "mediafile")
        ev_movie_time = self.controller.player.current_position_value
        ev_content = ''
        elem = None
        elem_name = None
        elem_id = None
        elem_type = None
        elem_class_id = None
        # Logging content depending on keys
        if 'element' in obj:
            if isinstance(obj['element'], Annotation):
                obj['annotation']=obj['element']
            elif isinstance(obj['element'], Relation):
                obj['relation']=obj['element']
            elif isinstance(obj['element'], AnnotationType):
                obj['annotationtype']=obj['element']
            elif isinstance(obj['element'], RelationType):
                obj['relationtype']=obj['element']
            elif isinstance(obj['element'], Schema):
                obj['schema']=obj['element']
            elif isinstance(obj['element'], View):
                obj['view']=obj['element']
            elif isinstance(obj['element'], Package):
                obj['package']=obj['element']
        if 'uri' in obj:
            obj['content']='movie="%s"' % str(obj['uri'])
            elem_name='movie'
            elem_id=str(obj['uri'])
        elif 'annotation' in obj:
            elem=obj['annotation']
            if elem is not None:
                ev_content= "\n".join(
                    ( 'annotation=' + elem.id,
                      'type=' + elem.type.id,
                      'mimetype=' + elem.type.mimetype,
                      'begin=' + str(elem.fragment.begin),
                      'end=' + str(elem.fragment.end),
                      'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                            )
                elem_name='annotation'
                elem_id=elem.id
                elem_type = advene.model.annotation.Annotation
                elem_class_id = elem.type.id
        elif 'relation' in obj:
            elem=obj['relation']
            if elem is not None:
                ev_content= "\n".join(
                    ( 'relation=' + elem.id,
                      'type=' + elem.type.id,
                      'mimetype=' + elem.type.mimetype,
                      'source=' + elem.members[0].id,
                      'dest=' + elem.members[1].id )
                    )
                elem_name='relation'
                elem_id=elem.id
                elem_type = advene.model.annotation.Relation
                elem_class_id = elem.type.id
        elif 'annotationtype' in obj:
            elem=obj['annotationtype']
            if elem is not None:
                ev_content= "\n".join(
                    ('annotationtype='+elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name=elem.title
                elem_id=elem.id
                elem_type = advene.model.schema.AnnotationType
                elem_class_id = elem.schema.id
        elif 'relationtype' in obj:
            elem=obj['relationtype']
            if elem is not None:
                ev_content= "\n".join(
                    ('relationtype=' + elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name=elem.title
                elem_id=elem.id
                elem_type = advene.model.schema.RelationType
                elem_class_id = elem.schema.id
        elif 'schema' in obj:
            elem=obj['schema']
            if elem is not None:
                ev_content= 'schema=' + elem.id
                elem_name=elem.title
                elem_id=elem.id
                elem_type = advene.model.schema.Schema
        elif 'view' in obj:
            elem=obj['view']
            if elem is not None:
                if isinstance(elem, advene.model.view.View):
                    ev_content= "\n".join(
                        ('view=' + elem.id,
                         'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                        )
                    elem_name=elem.title
                    elem_id=elem.id
                    elem_type = advene.model.view.View
                else:
                    ev_content= 'view=' + str(elem)
                    elem_name='not a view'
                    elem_id='undefined'
        elif 'package' in obj:
            elem=obj['package']
            if elem is not None:
                ev_content= 'package=' + elem.title
                elem_name='package'
                elem_id=elem.title
                elem_type = advene.model.package.Package
        elif 'position' in obj:
            #event related to the player
            if obj['position'] is not None:
                ev_content=str(time.strftime("%H:%M:%S", time.gmtime(obj['position']/1000)))
        #TODO undo ?
        ev_undo=False
        if 'undone' in obj.keys():
            ev_undo = True
        ev = Event(ev_name, ev_time, ev_activity_time, unicode(ev_content), ev_movie, ev_movie_time, elem_name, elem_id, elem_type, elem_class_id)
        #ev = Event(ev_name, ev_time, ev_activity_time, ev_snapshot, ev_content, ev_movie, ev_movie_time, elem_name, elem_id)
        self.trace.add_to_trace('events', ev)
        return ev

    def packOperation(self, obj):
        #op_snapshot = self.controller.package.imagecache.get(self.controller.player.current_position_value, epsilon=100)
        op_time = time.time()
        op_activity_time = (time.time() - self.trace.start) * 1000
        op_name = obj['event_name']
        #op_params = obj['parameters']
        #for i in obj.keys():
        #    print "%s : %s" % (i,obj[i])
        op_movie = self.controller.package.getMetaData(config.data.namespace, "mediafile")
        op_movie_time = self.controller.player.current_position_value
        op_content = None
        elem = None
        elem_name = None
        elem_id = None
        elem_type = None
        elem_class_id = None
        # package uri annotation relation annotationtype relationtype schema
        # Logging content depending on keys
        if 'element' in obj:
            if isinstance(obj['element'], advene.model.annotation.Annotation):
                obj['annotation']=obj['element']
            elif isinstance(obj['element'], advene.model.annotation.Relation):
                obj['relation']=obj['element']
            elif isinstance(obj['element'], advene.model.schema.AnnotationType):
                obj['annotationtype']=obj['element']
            elif isinstance(obj['element'], advene.model.schema.RelationType):
                obj['relationtype']=obj['element']
            elif isinstance(obj['element'], advene.model.schema.Schema):
                obj['schema']=obj['element']
            elif isinstance(obj['element'], advene.model.view.View):
                obj['view']=obj['element']
            elif isinstance(obj['element'], advene.model.package.Package):
                obj['package']=obj['element']
        if 'uri' in obj:
            obj['content']='movie="'+str(obj['uri'])+'"'
            elem_name='movie'
            elem_id=str(obj['uri'])
        elif 'annotation' in obj:
            elem=obj['annotation']
            if elem is not None:
                op_content= "\n".join(
                    ( 'annotation=' + elem.id,
                      'type=' + elem.type.id,
                      'mimetype=' + elem.type.mimetype,
                      'begin=' + str(elem.fragment.begin),
                      'end=' + str(elem.fragment.end),
                      'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                            )
                elem_name='annotation'
                elem_id=elem.id
                elem_type = advene.model.annotation.Annotation
                elem_class_id = elem.type.id
        elif 'relation' in obj:
            elem=obj['relation']
            if elem is not None:
                op_content= "\n".join(
                    ( 'relation=' + elem.id,
                      'type=' + elem.type.id,
                      'mimetype=' + elem.type.mimetype,
                      'source=' + elem.members[0].id,
                      'dest=' + elem.members[1].id )
                    )
                elem_name='relation'
                elem_id=elem.id
                elem_type = advene.model.annotation.Relation
                elem_class_id = elem.type.id
        elif 'annotationtype' in obj:
            elem=obj['annotationtype']
            if elem is not None:
                op_content= "\n".join(
                    ('annotationtype='+elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name=elem.title
                elem_id=elem.id
                elem_type = advene.model.schema.AnnotationType
                elem_class_id = elem.schema.id
        elif 'relationtype' in obj:
            elem=obj['relationtype']
            if elem is not None:
                op_content= "\n".join(
                    ('relationtype=' + elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name=elem.title
                elem_id=elem.id
                elem_type = advene.model.schema.RelationType
                elem_class_id = elem.schema.id
        elif 'schema' in obj:
            elem=obj['schema']
            if elem is not None:
                op_content= 'schema=' + elem.id
                elem_name=elem.title
                elem_id=elem.id
                elem_type = advene.model.schema.Schema
        elif 'view' in obj:
            elem=obj['view']
            if elem is not None:
                if isinstance(elem, advene.model.view.View):
                    op_content= "\n".join(
                        ('view=' + elem.id,
                         'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                        )
                    elem_name=elem.title
                    elem_id=elem.id
                    elem_type = advene.model.view.View
                else:
                    op_content= 'view=' + str(elem)
                    elem_name='not a view'
                    elem_id='undefined'
        elif 'package' in obj:
            elem=obj['package']
            if elem is not None:
                op_content= 'package=' + elem.title
                elem_name='package'
                elem_id=elem.title
                elem.type=advene.model.package.Package
        elif 'position' in obj:
            #event related to the player
            if obj['position'] is not None:
                op_content=str(time.strftime("%H:%M:%S", time.gmtime(obj['position']/1000)))
        if self.trace.levels['operations']:
            prev = self.trace.levels['operations'][-1]
            if op_name in self.editEndNames and prev.name in self.editEndNames and prev.concerned_object['id'] == elem_id:
                return
        op = Operation(op_name, op_time, op_activity_time, unicode(op_content), op_movie, op_movie_time, elem_name, elem_id, elem_type, elem_class_id)
        self.trace.add_to_trace('operations', op)
        return op

    def packAction(self, obj, op):
        ope = op
        ac_t = None
        # verifier l'action de l'evenement
        if obj['event_name'] in self.operation_mapping.keys():
            ac_t = self.operation_mapping[obj['event_name']]
        else:
            return
        typ = "Undefined"
        if ac_t < len(self.action_types):
            typ = self.action_types[ac_t]
        if typ == "Undefined":
            typ = self.find_action_name(obj)
            # traiter les edit
        if typ in self.opened_actions.keys():
            # an action is already opened for this event
            ac = self.opened_actions[typ]
            if typ == "Navigation" and (ope.name == "PlayerStop" or ope.name == "PlayerPause"):
                del self.opened_actions[typ]
            ac.add_operation(ope)
            return ac
        for t in self.opened_actions.keys():
            if t != "Navigation":
                del self.opened_actions[t]
        # verifier que ce n'est pas la meme que la derniere
#        if len(self.trace.levels['actions'])>0:
#            if self.trace.levels['actions'][len(self.trace.levels['actions'])-1].name == type:
#                ac = self.trace.levels['actions'][len(self.trace.levels['actions'])-1]
#                ac.add_operation(ope)
                #mise a jour des temps de fin, contenu, liste operations
#                return ac
        ac = Action(name=typ, begintime=ope.time, endtime=None, acbegintime=ope.activity_time, acendtime=None, content=None, movie=ope.movie, movietime=ope.movietime, operations=[ope])
        self.trace.add_to_trace('actions', ac)
        self.opened_actions[typ]=ac
        return ac

    def alert_registered(self, event, operation, action):
        for i in self.registered_views:
            gobject.idle_add(i.receive, self.trace, event, operation, action)
        return

    def register_view(self, view):
        self.registered_views.append(view)
        return

    def unregister_view(self, view):
        self.registered_views.remove(view)
        return

    def find_action_name(self, obj_evt):
        # need to test something else in annot
        if 'annotation' in obj_evt or 'relation' in obj_evt:
            return "Restructuration"
        if 'annotationtype' in obj_evt or 'relationtype' in obj_evt or 'schema' in obj_evt:
            return "Classification"
        if 'view' in obj_evt:
            return "View building"
        return "Undefined"

    #def get_trace_level(self, level):
    #    return self.trace.get_level(level)

    #def get_trace(self):
    #    return self.trace

class Trace:
    def __init__ (self):
        self.start=0
        self.name=time.strftime("trace-%Y%m%d-%H%M%S")
        self.levels={
        'events':[],
        'operations':[],
        'actions':[],
        }

    def rename(self, name):
        # rename the trace
        self.name = name
        return

    def sort_trace_by(self, level, typ):
        # allow to sort trace level 1 or 2 by time or name
        return

    def add_to_trace(self, level, obj):
        # add an object to a level of the trace
        if obj is None or not self.levels.has_key(level):
            return None
        self.levels[level].append(obj)
        return obj

    def remove_from_trace(self, level, obj):
        # remove an object from the trace
        if obj is None or not self.levels.has_key(level) or obj not in self.levels[level]:
            return None
        self.levels[level].remove(obj)
        return obj

    def add_level(self, level):
        # create a new level in the trace
        if self.levels.has_key(level):
            return None
        self.levels[level]=[]
        return self.levels[level]

    def remove_level(self, level):
        # remove a level from the trace
        if level == 'actions' or level == 'operations' or level=='events':
            print 'You cannot delete events, operations and actions levels'
            return
        if self.levels.has_key(level):
            del self.levels[level]
        return

    def rename_level(self, level, new_name):
        # change the name of a level of the trace
        if (not self.levels.has_key(level)) or self.levels.has_key(new_name) or level == 'actions' or level == 'operations':
            print 'You cannot rename operations and actions levels'
            return None
        self.levels[new_name]=self.levels[level]
        del self.levels[level]
        return self.levels[new_name]

    def get_level(self, level):
        if self.levels.has_key(level):
            return self.levels[level]
        else:
            return None

    def list_all(self):
        for i in self.levels.keys():
            print "Trace niveau \'%s\'" % i
            for t in self.levels[i]:
                print "    %s : \'%s\'" % (t, t.name)
        return

class Event:
    def __init__(self, name, time_, actime, content, movie, movietime, obj, obj_id, obj_type, o_class_id):
        self.name = name
        self.time = time_
        self.activity_time = actime
        self.content = content or u''
        self.movie = movie
        self.movietime = movietime
        self.comment = ''
        self.concerned_object = {
            'name':obj,
            'id':obj_id,
            'type':obj_type,
            'cid':o_class_id,
        }

    def copy(self):
        e = Event(self.name, self.time, self.activity_time,
                  self.content, self.movie, self.movietime,
                  self.concerned_object['name'], self.concerned_object['id'],
                  self.concerned_object['type'], self.concerned_object['cid'])
        e.change_comment(self.comment)
        return e

    def exp_type(self, typ):
        if typ == Schema:
            return 'advene.model.schema.Schema'
        elif typ == AnnotationType:
            return 'advene.model.schema.AnnotationType'
        elif typ == RelationType:
            return 'advene.model.schema.RelationType'
        elif typ == Annotation:
            return 'advene.model.annotation.Annotation'
        elif typ == Relation:
            return 'advene.model.annotation.Relation'
        elif typ == View:
            return 'advene.model.view.View'
        else:
            return 'None'

    def export(self, n_id):
        #print "%s %s %s %s %s %s %s %s %s %s" % ('e'+str(n_id), self.name, str(self.time), str(self.activity_time), self.movie, str(self.movietime), self.comment, str(self.concerned_object['name']), str(self.concerned_object['id']), self.content)
        e = ET.Element('event', id='e'+str(n_id),
                name=self.name, time=str(self.time),
                ac_time=str(self.activity_time), movie=str(self.movie), m_time=str(self.movietime), comment=self.comment, o_name=str(self.concerned_object['name']), o_id=str(self.concerned_object['id']), o_type=self.exp_type(self.concerned_object['type']), o_cid=str(self.concerned_object['cid']))
        e.text = self.content
        return e

    def to_xml_string(self, n_id):
        return ET.tostring(self.export(n_id), encoding="utf-8")
        #return "<event id='e%s' name='%s' time='%s' ac_time='%s' movie='%s' m_time='%s' comment='%s' o_name='%s' o_id='%s' o_type='%s' o_cid='%s'/>" % (str(n_id), self.name, str(self.time), str(self.activity_time), str(self.movie), str(self.movietime), self.comment, str(self.concerned_object['name']), str(self.concerned_object['id']), str(self.concerned_object['type']), str(self.concerned_object['cid']))


    def change_comment(self, comment=''):
        self.comment = comment
        return


class Operation:
    def __init__(self, name, time_, actime, content, movie, movietime, obj, obj_id, obj_type, o_class_id):
        self.name = name
        self.time = time_
        self.activity_time = actime
        self.content = content or u''
        self.movie = movie
        self.movietime = movietime
        self.comment = ''
        self.concerned_object = {
            'name':obj,
            'id':obj_id,
            'type':obj_type,
            'cid':o_class_id,
        }

    def copy(self):
        o = Operation(self.name, self.time, self.activity_time,
                      self.content, self.movie, self.movietime,
                      self.concerned_object['name'], self.concerned_object['id'],
                      self.concerned_object['type'],self.concerned_object['cid'])
        o.change_comment(self.comment)
        return o

    def export(self, n_id):
        #print "%s %s %s %s %s %s %s %s %s %s" % ('e'+str(n_id), self.name, str(self.time), str(self.activity_time), self.movie, str(self.movietime), self.comment, str(self.concerned_object['name']), str(self.concerned_object['id']), self.content)
        e = ET.Element('operation', id='o'+str(n_id),
                name=self.name, time=str(self.time),
                ac_time=str(self.activity_time), movie=str(self.movie), m_time=str(self.movietime), comment=self.comment, o_name=str(self.concerned_object['name']), o_id=str(self.concerned_object['id']), o_type=str(self.concerned_object['type']), o_cid=str(self.concerned_object['cid']))
        e.text = self.content
        return e

    def to_xml_string(self, n_id):
        return ET.tostring(self.export(n_id), encoding="utf-8")

    def change_comment(self, comment=''):
        self.comment = comment
        return

class Action:
    def __init__(self, name, begintime, endtime, acbegintime, acendtime, content, movie, movietime, operations):
        self.operations = operations or []
        self.name = name

        if endtime is None:
            endtime = begintime + 0.5
        if acendtime is None:
            acendtime = acbegintime + 500

        self.time = [ begintime, endtime ]
        self.activity_time = [ acbegintime, acendtime ]

        self.content = content or u''

        self.movie = movie
        self.movietime = movietime

        self.comment = ''

    def copy(self):
        a = Action(self.name, self.time[0], self.time[1],
                   self.activity_time[0], self.activity_time[1],
                   self.content, self.movie, self.movietime,
                   self.operations)
        a.change_comment(self.comment)
        return a

    def change_comment(self, comment=''):
        self.comment = comment

    def add_operation(self, operation):
        self.operations.append(operation)
        self.set_time(1, operation.time)

    def set_time(self, choice, newtime):
        offset = (newtime - self.time[choice])*1000
        self.time[choice]=newtime
        self.activity_time[choice]=self.activity_time[choice] + offset

    def set_content(self, newcontent):
        self.content = newcontent

    def export(self, a_id):
        #print "%s %s %s %s %s %s %s %s %s %s" % ('e'+str(n_id), self.name, str(self.time), str(self.activity_time), self.movie, str(self.movietime), self.comment, str(self.concerned_object['name']), str(self.concerned_object['id']), self.content)
        e = ET.Element('action', id='a'+str(a_id),
                name=self.name, b_time=str(self.time[0]),
                e_time=str(self.time[1]),
                ac_b_time=str(self.activity_time[0]),
                ac_e_time=str(self.activity_time[1]),
                movie=self.movie,
                m_time=str(self.movietime),
                comment = self.comment)
        e.text = self.content
        return e

    def to_xml_string(self, n_id):
        return ET.tostring(self.export(n_id), encoding="utf-8")

class TExport(Thread):
    def __init__ (self, host, port, trace):
        Thread.__init__(self)
        self.host = host
        self.port = port
        self.trace = trace

    def run(self):
        try:
            sck = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
            addr = socket.getaddrinfo(self.host, self.port)
            sck.connect(addr[0][4])
        except (socket.error, socket.gaierror), e:
            print(_("Cannot export to %(host)s:%(port)s %(error)s") % {
                    'host': self.host,
                    'port': self.port,
                    'error': e})
            return
        nbe=0
        try:
            data="INCOMIIIIIIIIIIIIIIING !"
            sck.send(data.encode('utf-8'))
            for (id_e, e) in enumerate(self.trace.levels['events']):
                tmp=e.to_xml_string(id_e)
                sck.sendall(tmp)
                nbe+=1
        except (socket.error, socket.gaierror), e:
            print(_("Cannot send data to %(host)s:%(port)s %(error)s") % {
                    'host': self.host,
                    'port': self.port,
                    'error': e } )
            sck.close()
            return
        print '%s events exported to %s:%s' % (nbe, self.host, self.port)
        sck.close()

class TBroadcast(Thread):

    def __init__ (self, host, port, bdq):
        Thread.__init__(self)
        self.host = host
        self.port = port
        self.bdq = bdq
        self.obsel = None

    def run(self):
        # Creating socket and queue
        try:
            sck = socket.socket(socket.AF_INET6, socket.SOCK_STREAM, 0)
            addr = socket.getaddrinfo(self.host, self.port)
            sck.connect(addr[0][4])
        except (socket.error, socket.gaierror), e:
            print(_("Cannot export to %(host)s:%(port)s %(error)s") % {
                    'host': self.host,
                    'port': self.port,
                    'error': e})
            return
        nbe=0
        # Infinite loop waiting for event to send
        # Receiving from Queue and sending to host
        # Need to test some special code to stop thread
        while (1):
            #we shouldnt receive exception from the queue
            self.obsel = self.bdq.get()
            if not isinstance(self.obsel, Event):
                if self.obsel == "###\n":
                    print "Broadcasting: death received"
                    break
                else:
                    continue
            tmp = self.obsel.to_xml_string(nbe)
            try:
                sck.sendall(tmp)
                nbe+=1
            except (socket.error, socket.gaierror), e:
                print(_("Cannot send event %(nb)s to %(host)s:%(port)s %(error)s") % {
                        'nb': nbe,
                        'host': self.host,
                        'port': self.port,
                        'error': e})
                return
        print _('%(nb)s events sent to %(host)s:%(port)s during session.') % {
            'nb': nbe,
            'host': self.host,
            'port': self.port }
        sck.close()
