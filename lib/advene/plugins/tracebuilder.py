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

import time

import advene.core.config as config
import urllib
import advene.model.view
import advene.util.ElementTree as ET
import os
import advene.util.helper as helper
import advene.util.handyxml as handyxml
import xml.dom


def register(controller):
    controller.register_tracer(TraceBuilder(controller))
    return
name="Trace Builder plugin"

class TraceBuilder:
    def __init__ (self, controller=None, parameters=None, package=None):
        #self.close_on_package_load = False
        self.controller=controller
        self.operations = []
        self.registered_views = []
        self.opened_actions = {}
        self.filtered_events = ['AnnotationBegin','AnnotationEnd','BookmarkHighlight','BookmarkUnhighlight']
        self.action_types = ['Annotation', 'Restructuration', 'Navigation', 'Classification', 'View building']
        self.operation_mapping = {
        'AnnotationCreate':0,
        'AnnotationEditEnd':1,
        'AnnotationDelete':1,
        'RelationCreate':1,
        'AnnotationMerge':1,
        'AnnotationMove':1,
        'PlayerStart':2,
        'PlayerStop':2,
        'PlayerPause':2,
        'PlayerResume':2,
        'PlayerSet':2,
        'ViewActivation':2,
        'AnnotationTypeCreate':3,
        'RelationTypeCreate':3,
        'RelationTypeDelete':3,
        'AnnotationTypeDelete':3,
        'AnnotationTypeEditEnd':3,
        'RelationTypeEditEnd':3,
        'ViewCreate':4,
        'ViewEditEnd':4,
        'EditSessionStart':5,
        #'ElementEditEnd':5,
        'ElementEditDestroy':5,
        'EditSessionEnd':5,
        }

        if package is None and controller is not None:
            package=controller.package
        self.__package=package
        self.controller.event_handler.register_view(self)
        self.trace = Trace()

    def export(self):
        fname=config.data.advenefile(time.strftime("trace_advene-%Y%m%d-%H%M%S"), 
                                     category='settings')
        try:
            stream=open(fname, 'wb')
        except (OSError, IOError), e:
            self.log(_("Cannot export to %(fname)s: %(e)s") % locals())
            return None
        tr=ET.Element('trace')
        #everything can be rebuild from events.
        for (id_e, e) in enumerate(self.trace.levels['events']):
            tr.append(e.export(id_e))
        helper.indent(tr)
        ET.ElementTree(tr).write(stream, encoding='utf-8')
        stream.close()
        #print "Data exported to %s" % fname
        return fname

    def convert_old_trace(self, fname):
        #FIXME : complete the import and do not use handyxml.
        print 'importing trace from %s' % fname
        if not os.path.exists(fname):
            oldfname=fname
            fname = os.path.join(config.data.path['settings'],oldfname)
            print "%s not found, trying %s" % (oldfname,fname)
            if not os.path.exists(fname):
                print "%s not found, giving up." % fname
                return False
        pk=handyxml.xml(fname, forced=True)
        lid=0
        if pk.node.nodeName != 'package':
            print "This does not look like a trace file."
            return False
        self.trace = Trace()
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
                an_time=an_ac_time
                if an_content.find('position='):
                    d= an_content.find('position=')
                    e = an_content.find('\n',an_content.find('position='))
                    an_m_time=an_content[d:e]
                #evt = Event(an_name, float(an_time), float(an_ac_time), an_content, an_movie, float(an_m_time), an_o_name, an_o_id)
                #evt.change_comment(ev.comment)
                #self.trace.add_to_trace('events', evt)
                print '%s %s %s' % (an_name, an_ac_time, an_content)

                
        return

    def import_trace(self, fname):
        print 'importing trace from %s' % fname
        if not os.path.exists(fname):
            oldfname=fname
            fname = os.path.join(config.data.path['settings'],oldfname)
            print "%s not found, trying %s" % (oldfname,fname)
            if not os.path.exists(fname):
                print "%s not found, giving up." % fname
                return False
        tr=handyxml.xml(fname, forced=True)
        lid=0
        if tr.node.nodeName != 'trace':
            print "This does not look like a trace file."
            return False
        self.trace = Trace()
        self.opened_actions = {}
        for ev in tr.event:
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
            evt = Event(ev.name, float(ev.time), float(ev.ac_time), ev_content, ev.movie, float(ev.m_time), ev.o_name, ev.o_id)
            evt.change_comment(ev.comment)
            self.trace.add_to_trace('events', evt)
            if evt.name in self.operation_mapping.keys():
                op = Operation(ev.name, float(ev.time), float(ev.ac_time), ev_content, ev.movie, float(ev.m_time), ev.o_name, ev.o_id)
                self.trace.add_to_trace('operations', op)
                if op is not None:
                    if ev.name in self.operation_mapping.keys():
                        ac_t = self.operation_mapping[ev.name]
                    else:
                        continue
                    type = "Undefined"
                    if ac_t < len(self.action_types):
                        type = self.action_types[ac_t]
                    if type == "Undefined":
                        if ev.o_name=='annotation' or ev.o_name=='relation':
                            type="Restructuration"
                        elif ev.o_name=='annotationtype' or ev.o_name=='relationtype' or ev.o_name=='schema':
                            type="Classification"
                        elif ev.o_name=='view':
                            type="View building"
                    if type in self.opened_actions.keys():
                        # an action is already opened for this event
                        ac = self.opened_actions[type]
                        if type == "Navigation" and (op.name == "PlayerStop" or op.name == "PlayerPause"):
                            del self.opened_actions[type]
                        ac.add_operation(op)
                        continue
                    for t in self.opened_actions.keys():
                        if t != "Navigation":
                            del self.opened_actions[t]
                    ac = Action(name=type, begintime=op.time, endtime=None, acbegintime=op.activity_time, acendtime=None, content=None, movie=op.movie, movietime=op.movietime, operations=[op])
                    self.trace.add_to_trace('actions', ac)
                    self.opened_actions[type]=ac
        self.alert_registered(None, None, None)
        print "%s events imported" % lid
        return True

    def receive(self, obj):
        # obj : received event
        ev = op = ac = None
        ev = self.packEvent(obj)
        if ev.name in self.operation_mapping.keys():
            op = self.packOperation(obj)
            if op is not None:
                ac = self.packAction(obj, op)
        #else:
        #    print "Not an operation : %s" % ev.name
        self.alert_registered(ev, op, ac)
        # this need to be replaced by a loop on packfunction depending on levels, with an array of modified objects depending on their level :
        # modif = []
        # for i in packfunctions:
        #     modif.append(i(obj))
        # self.alert_registered(modif)
        # wich could then be used in a more general way by the receiver

    def packEvent(self, obj):
        self.controller.update_snapshot(self.controller.player.current_position_value)
        #ev_snapshot = self.controller.package.imagecache.get(self.controller.player.current_position_value, epsilon=100)
        ev_time = time.time()
        ev_activity_time = (time.time() - config.data.startup_time) * 1000
        ev_name = obj['event_name']
        ev_movie = self.controller.package.getMetaData(config.data.namespace, "mediafile")
        ev_movie_time = self.controller.player.current_position_value
        ev_content = ''
        elem=None
        elem_name = None
        elem_id = None
        # Logging content depending on keys
        if 'element' in obj:
            if isinstance(obj['element'],advene.model.annotation.Annotation):
                obj['annotation']=obj['element']
            elif isinstance(obj['element'],advene.model.annotation.Relation):
                obj['relation']=obj['element']
            elif isinstance(obj['element'],advene.model.schema.AnnotationType):
                obj['annotationtype']=obj['element']
            elif isinstance(obj['element'],advene.model.schema.RelationType):
                obj['relationtype']=obj['element']
            elif isinstance(obj['element'],advene.model.schema.Schema):
                obj['schema']=obj['element']
            elif isinstance(obj['element'],advene.model.view.View):
                obj['view']=obj['element']
            elif isinstance(obj['element'],advene.model.package.Package):
                obj['package']=obj['element']
        if 'uri' in obj:
            obj['content']='movie="'+str(obj['uri'])+'"'
            elem_name='movie'
            elem_id=str(obj['uri'])
        elif 'annotation' in obj:
            elem=obj['annotation']
            if elem is not None:
                ev_content= "\n".join(
                    ( 'annotation=' + elem.id,
                      'type=' + elem.type.id,
                      'mimetype=' + elem.type.mimetype,
                      'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                            )
                elem_name='annotation'
                elem_id=elem.id
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
        elif 'annotationtype' in obj:
            elem=obj['annotationtype']
            if elem is not None:
                ev_content= "\n".join(
                    ('annotationtype='+elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name='annotationtype'
                elem_id=elem.id
        elif 'relationtype' in obj:
            elem=obj['relationtype']
            if elem is not None:
                ev_content= "\n".join(
                    ('relationtype=' + elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name='relationtype'
                elem_id=elem.id
        elif 'schema' in obj:
            elem=obj['schema']
            if elem is not None:
                ev_content= 'schema=' + elem.id
                elem_name='schema'
                elem_id=elem.id
        elif 'view' in obj:
            elem=obj['view']
            if elem is not None:
                if isinstance(elem, advene.model.view.View):
                    ev_content= "\n".join(
                        ('view=' + elem.id,
                         'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                        )
                    elem_name='view'
                    elem_id=elem.id
                else:
                    ev_content= 'view=' + str(elem)
                    elem_name='view'
                    elem_id='undefined'
        elif 'package' in obj:
            elem=obj['package']
            if elem is not None:
                ev_content= 'package=' + elem.title
                elem_name='package'
                elem_id=elem.title
        ev = Event(ev_name, ev_time, ev_activity_time, ev_content, ev_movie, ev_movie_time, elem_name, elem_id)
        #ev = Event(ev_name, ev_time, ev_activity_time, ev_snapshot, ev_content, ev_movie, ev_movie_time, elem_name, elem_id)
        self.trace.add_to_trace('events', ev)
        return ev

    def packOperation(self, obj):
        #op_snapshot = self.controller.package.imagecache.get(self.controller.player.current_position_value, epsilon=100)
        op_time = time.time()
        op_activity_time = (time.time() - config.data.startup_time) * 1000
        op_name = obj['event_name']
        #op_params = obj['parameters']
        op_movie = self.controller.package.getMetaData(config.data.namespace, "mediafile")
        op_movie_time = self.controller.player.current_position_value
        op_content = None
        elem=None
        elem_name = None
        elem_id = None
        # package uri annotation relation annotationtype relationtype schema
        # Logging content depending on keys
        if 'element' in obj:
            if isinstance(obj['element'],advene.model.annotation.Annotation):
                obj['annotation']=obj['element']
            elif isinstance(obj['element'],advene.model.annotation.Relation):
                obj['relation']=obj['element']
            elif isinstance(obj['element'],advene.model.schema.AnnotationType):
                obj['annotationtype']=obj['element']
            elif isinstance(obj['element'],advene.model.schema.RelationType):
                obj['relationtype']=obj['element']
            elif isinstance(obj['element'],advene.model.schema.Schema):
                obj['schema']=obj['element']
            elif isinstance(obj['element'],advene.model.view.View):
                obj['view']=obj['element']
            elif isinstance(obj['element'],advene.model.package.Package):
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
                      'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                            )
                elem_name='annotation'
                elem_id=elem.id
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
        elif 'annotationtype' in obj:
            elem=obj['annotationtype']
            if elem is not None:
                op_content= "\n".join(
                    ('annotationtype='+elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name='annotationtype'
                elem_id=elem.id
        elif 'relationtype' in obj:
            elem=obj['relationtype']
            if elem is not None:
                op_content= "\n".join(
                    ('relationtype=' + elem.id,
                     'schema=' + elem.schema.id,
                     'mimetype=' + elem.mimetype)
                    )
                elem_name='relationtype'
                elem_id=elem.id
        elif 'schema' in obj:
            elem=obj['schema']
            if elem is not None:
                op_content= 'schema=' + elem.id
                elem_name='schema'
                elem_id=elem.id
        elif 'view' in obj:
            elem=obj['view']
            if elem is not None:
                if isinstance(elem, advene.model.view.View):
                    op_content= "\n".join(
                        ('view=' + elem.id,
                         'content="'+ urllib.quote(elem.content.data.encode('utf-8'))+'"')
                        )
                    elem_name='view'
                    elem_id=elem.id
                else:
                    op_content= 'view=' + str(elem)
                    elem_name='view'
                    elem_id='undefined'
        elif 'package' in obj:
            elem=obj['package']
            if elem is not None:
                op_content= 'package=' + elem.title
                elem_name='package'
                elem_id=elem.title
        if self.trace.levels['operations']:
            prev = self.trace.levels['operations'][-1]
            #print '%s %s , %s %s' % (op_name, prev.name, prev.concerned_object['id'], elem_id)
            if op_name == 'ElementEditDestroy' and (prev.name == 'ElementEditDestroy' or prev.name == 'ElementEditEnd' or prev.name == 'AnnotationEditEnd' or prev.name == 'AnnotationTypeEditEnd' or prev.name == 'RelationTypeEditEnd') and prev.concerned_object['id'] == elem_id:
                return
        op = Operation(op_name, op_time, op_activity_time, op_content, op_movie, op_movie_time, elem_name, elem_id)
        #op = Operation(op_name, op_time, op_activity_time, op_content, op_snapshot, op_movie, op_movie_time, elem_name, elem_id)
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
        type = "Undefined"
        if ac_t < len(self.action_types):
            type = self.action_types[ac_t]
        if type == "Undefined":
            type = self.find_action_name(obj)
            # traiter les edit
        if type in self.opened_actions.keys():
            # an action is already opened for this event
            ac = self.opened_actions[type]
            if type == "Navigation" and (ope.name == "PlayerStop" or ope.name == "PlayerPause"):
                del self.opened_actions[type]
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
        ac = Action(name=type, begintime=ope.time, endtime=None, acbegintime=ope.activity_time, acendtime=None, content=None, movie=ope.movie, movietime=ope.movietime, operations=[ope])
        self.trace.add_to_trace('actions', ac)
        self.opened_actions[type]=ac
        return ac

    def alert_registered(self, event, operation, action):
        for i in self.registered_views:
            i.receive(self.trace, event, operation, action)
        return

    def register_view(self, view):
        self.registered_views.append(view)
        return

    def unregister_view(self, view):
        self.registered_views.remove(view)
        return

    def find_action_name(self, obj_evt):
        evid = obj_evt['event_name']
        # need to test something else in annot
        if 'annotation' in obj_evt or 'relation' in obj_evt:
            return "Restructuration"
        if 'annotationtype' in obj_evt or 'relationtype' in obj_evt or 'schema' in obj_evt:
            return "Classification"
        if 'view' in obj_evt:
            return "View_building"
        return "Undefined"

    #def get_trace_level(self, level):
    #    return self.trace.get_level(level)

    #def get_trace(self):
    #    return self.trace

class Trace:
    def __init__ (self):
        self.levels={
        'events':[],
        'operations':[],
        'actions':[],
        }

    def sort_trace_by(self, level, type):
        # allow to sort trace level 1 or 2 by time or name
        return

    def add_to_trace(self, level, obj):
        # add an object to a level of the trace
        if obj is None or not self.levels.has_key(level):
            return None
        self.levels[level].append(obj)
        return

    def remove_from_trace(self, level, obj):
        # remove an object from the trace
        # should not be used as a trace is what it is ...
        return

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
                print "    %s : \'%s\'" % (t,t.name)
        return

class Event:
    def __init__(self, name, time, actime, content, movie, movietime, obj, obj_id):
        self.name = name
        self.time = time
        self.activity_time = actime
        self.content = content
        self.movie = movie
        self.movietime = movietime
        self.comment = ''
        self.concerned_object = {
            'name':obj,
            'id':obj_id,
        }

    def export(self, n_id):
        #print "%s %s %s %s %s %s %s %s %s %s" % ('e'+str(n_id), self.name, str(self.time), str(self.activity_time), self.movie, str(self.movietime), self.comment, str(self.concerned_object['name']), str(self.concerned_object['id']), self.content)
        e = ET.Element('event', id='e'+str(n_id), 
                name=self.name, time=str(self.time),
                ac_time=str(self.activity_time), movie=str(self.movie), m_time=str(self.movietime), comment=self.comment, o_name=str(self.concerned_object['name']), o_id=str(self.concerned_object['id']))
        e.text = self.content
        return e

    def change_comment(self, comment=''):
        self.comment = comment
        return


class Operation:
    def __init__(self, name, time, actime, content, movie, movietime, obj, obj_id):
        self.name = name
        self.time = time
        self.activity_time = actime
        self.content = ''
        if content is not None:
            self.content = content
        self.movie = movie
        self.movietime = movietime
        self.comment = ''
        self.concerned_object = {
            'name':obj,
            'id':obj_id,
        }

    def export(self, n_id):
        e = ET.Element('operation', id='o'+str(n_id), name=self.name, time=str(self.time),
                ac_time=str(self.activity_time), movie=self.movie, m_time=str(self.movietime), comment=self.comment, o_name=self.concerned_object['name'], o_id=self.concerned_object['id'])
        e.text = self.content
        return e

    def change_comment(self, comment=''):
        self.comment = comment
        return

class Action:
    def __init__(self, name, begintime, endtime, acbegintime, acendtime, content, movie, movietime, operations):
        self.operations=[]
        self.time = [0,0]
        self.activity_time=[0,0]
        self.name = name
        self.time[0] = begintime
        self.comment = ''
        if endtime is not None:
            self.time[1] = endtime
        else:
            self.time[1] = begintime + 50
        self.activity_time[0] = acbegintime
        if acendtime is not None:
            self.activity_time[1] = acendtime
        else:
            self.activity_time[1] = acbegintime + 50000
        self.content = ''
        if content is not None:
            self.content = content
        self.movie = movie
        self.movietime = movietime
        if operations is not None:
            self.operations = operations

    def change_comment(self, comment=''):
        self.comment = comment
        return

    def add_operation(self, operation):
        self.operations.append(operation)
        self.set_time(1,operation.time)

    def set_time(self, choice, newtime):
        offset = newtime - self.time[choice]
        self.time[choice]=newtime
        self.activity_time[choice]=self.activity_time[choice] + offset

    def set_content(self, newcontent):
        self.content = newcontent


