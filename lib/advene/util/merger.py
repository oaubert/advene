#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""
Merge packages
==============
"""

import sys
import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.fragment import MillisecondFragment
import advene.util.helper as helper

class Differ:
    """Returns a structure diff of two packages.
    """
    def __init__(self, source=None, destination=None, controller=None):
        self.source=source
        self.destination=destination
        self.controller=controller
        self.source_ids = {}

    def diff(self):
        """Iterator returning a changelist.
        
        Structure of returned elements:
        (action_name, source_element, dest_element, action)
        """
        for m in (self.diff_schemas,
                  self.diff_annotation_types, 
                  self.diff_relation_types,
                  self.diff_annotations,
                  self.diff_relations,
                  self.diff_views,
                  self.diff_queries,
                  self.diff_resources):
            for d in m():
                yield d

    def check_meta(self, s, d, namespaceid, name):
        ns=config.data.namespace_prefix[namespaceid]
        if s.getMetaData(ns, name) != d.getMetaData(ns, name):
            return ('update_meta_%s' % name,
                    s, d, 
                    lambda s, d: self.update_meta(s, d, namespaceid, name) )
        else:
            return None
        
    def update_meta(self, s, d, namespaceid, name):
        """Update the meta attribute name from the given namespace.
        """
        ns=config.data.namespace_prefix[namespaceid]
        d.setMetaData(ns, name,
                      s.getMetaData(ns, name))

    def diff_schemas(self):
        ids = dict([ (s.id, s) for s in self.destination.schemas ])
        self.source_ids['schemas']=ids
        for s in self.source.schemas:
            if s.id in ids:
                d=ids[s.id]
                # Present. Check if it was modified
                if s.title != d.title:
                    yield ('update_title', s, d, lambda s, d: d.setTitle(s.title) )
                c=self.check_meta(s, d, 'dc', 'description')
                if c:
                    yield c
            else:
                yield ('new', s, None, lambda s, d: self.copy_schema(s) )

    def diff_annotation_types(self):
        ids = dict([ (s.id, s) for s in self.destination.annotationTypes ])
        self.source_ids['annotation-types']=ids
        for s in self.source.annotationTypes:
            if s.id in ids:
                d=ids[s.id]
                # Present. Check if it was modified
                if s.title != d.title:
                    yield ('update_title', s, d, lambda s, d: d.setTitle(s.title) )
                if s.mimetype != d.mimetype:
                    yield ('update_mimetype', s, d, lambda s, d: d.setMimetype(s.mimetype) )
                c=self.check_meta(s, d, 'dc', 'description')
                if c:
                    yield c
                c=self.check_meta(s, d, 'advenetool', 'representation')
                if c:
                    yield c
                c=self.check_meta(s, d, 'advenetool', 'color')
                if c:
                    yield c
            else:
                yield ('new', s, None, lambda s, d: self.copy_annotation_type(s) )

    def diff_relation_types(self):
        ids = dict([ (s.id, s) for s in self.destination.relationTypes ])
        self.source_ids['relation-types']=ids
        for s in self.source.relationTypes:
            if s.id in ids:
                d=ids[s.id]
                # Present. Check if it was modified
                if s.title != d.title:
                    yield ('update_title', s, d, lambda s, d: d.setTitle(s.title) )
                if s.mimetype != d.mimetype:
                    yield ('update_mimetype', s, d, lambda s, d: d.setMimetype(s.mimetype) )
                c=self.check_meta(s, d, 'dc', 'description')
                if c:
                    yield c
                # FIXME: check members
            else:
                yield ('new', s, None, lambda s, d: self.copy_relation_type(s) )


    def diff_annotations(self):
        ids = dict([ (s.id, s) for s in self.destination.annotations ])
        self.source_ids['annotations']=ids
        for s in self.source.annotations:
            if s.id in ids:
                d=ids[s.id]
                # Present. Check if it was modified
                if s.fragment.begin != d.fragment.begin:
                    yield ('update_begin', s, d, lambda s, d: d.fragment.setBegin(s.fragment.begin))
                if s.fragment.end != d.fragment.end:
                    yield ('update_end', s, d, lambda s, d: d.fragment.setEnd(s.fragment.end))
                if s.content.data != d.content.data:
                    yield ('update_content', s, d, lambda s, d: d.content.setData(s.content.data))
                # FIXME: check tags
            else:
                yield ('new', s, None, lambda s, d: self.copy_annotation(s) )


    def diff_relations(self):
        ids = dict([ (s.id, s) for s in self.destination.relations ])
        self.source_ids['relations']=ids
        for s in self.source.relations:
            if s.id in ids:
                d=ids[s.id]
                # Present. Check if it was modified
                if s.content.data != d.content.data:
                    yield ('update_content', s, d, lambda s, d: d.content.setData(s.content.data))
                # FIXME: check members
                # FIXME: check tags
            else:
                yield ('new', s, None, lambda s, d: self.copy_relation(s) )

    def diff_views(self):
        ids = dict([ (s.id, s) for s in self.destination.views ])
        self.source_ids['views']=ids
        for s in self.source.views:
            if s.id in ids:
                # Present. Check if it was modified
                d=ids[s.id]
                if s.title != d.title:
                    yield ('update_title', s, d, lambda s, d: d.setTitle(s.title) )
                if (s.matchFilter['class'] != d.matchFilter['class']
                    or s.matchFilter.get('type', None) != d.matchFilter.get('type', None)):
                    yield ('update_matchfilter', s, d, lambda s, d: d.matchFilter.update(s.matchFilter) )
                if s.content.mimetype != d.content.mimetype:
                    yield ('update_mimetype', s, d, lambda s, d: d.content.setMimetype(s.content.mimetype) )
                if s.content.data != d.content.data:
                    yield ('update_content', s, d, lambda s, d: d.content.setData(s.content.data))
            else:
                yield ('new', s, None, lambda s, d: self.copy_view(s) )

    def diff_queries(self):
        ids = dict([ (s.id, s) for s in self.destination.queries ])
        self.source_ids['queries']=ids
        for s in self.source.queries:
            if s.id in ids:
                # Present. Check if it was modified
                d=ids[s.id]
                if s.title != d.title:
                    yield ('update_title', s, d, lambda s, d: d.setTitle(s.title) )
                if s.content.mimetype != d.content.mimetype:
                    yield ('update_mimetype', s, d, lambda s, d: d.setMimetype(s.mimetype) )
                if s.content.data != d.content.data:
                    yield ('update_content', s, d, lambda s, d: d.content.setData(s.content.data))
            else:
                yield ('new', s, None, lambda s, d: self.copy_query(s) )

    def diff_resources(self):
        ids=[]
        self.source_ids['resources']=ids
        # FIXME: todo
        if False:
            yield None
        return

    def copy_schema(self, s):
        el=self.destination.createSchema(ident=s.id)
        el.author=s.author
        el.date=s.date
        el.title=s.title
        self.destination.schemas.append(el)
        return el

    def copy_annotation_type(self, s):
        # Find parent, and create it if necessary
        sch=helper.get_id(self.destination.schemas, s.schema.id)
        if not sch:
            # Create it
            sch=helper.get_id(self.source.schemas, s.schema.id)
            sch=self.copy_schema(sch)
        el=self.sch.createAnnotationType(ident=s.id)
        el.author=s.author
        el.date=s.date
        el.title=s.title
        el.mimetype=s.mimetype
        sch.annotationTypes.append(el)
        return el

    def copy_relation_type(self, s):
        # Find parent, and create it if necessary
        sch=helper.get_id(self.destination.schemas, s.schema.id)
        if not sch:
            # Create it
            sch=helper.get_id(self.source.schemas, s.schema.id)
            sch=self.copy_schema(sch)
        el=self.sch.createRelationType(ident=s.id)
        el.author=s.author
        el.date=s.date
        el.title=s.title
        el.mimetype=s.mimetype
        sch.relationTypes.append(el)
        # Handle membertypes, ensure that annotation types are defined
        for m in s.hackedMemberTypes:
            if not s.startswith('#'):
                print "Cannot handle non-fragment membertypes"
            at=helper.get_id(self.destination.annotationTypes, m[1:])
            if not at:
                # The annotation type does not exist. Create it.
                at=helper.get_id(self.source.annotationTypes, m[1:])
                at=self.copy_annotation_type(at)
        # Now we can set member types
        el.setHackedMemberTypes(s.getHackedMemberTypes())
        return el

    def copy_annotation(self, s):
        at=helper.get_id(self.destination.annotationTypes, s.type.id)
        if not at:
            # The annotation type does not exist. Create it.
            at=self.copy_annotation_type(helper.get_id(self.source.annotationTypes, 
                                                       s.type.id))
        el=self.destination.createAnnotation(
            ident=s.id,
            type=at,
            author=s.author,
            date=s.date,
            fragment=s.fragment.clone())
        el.content.data=s.content.data
        self.destination.annotations.append(el)
        return el

    def copy_relation(self, s):
        rt=helper.get_id(self.destination.relationTypes, s.type.id)
        if not rt:
            # The annotation type does not exist. Create it.
            rt=self.copy_relation_type(helper.get_id(self.source.relationTypes, 
                                                     s.type.id))
        # Ensure that annotations exist
        members=[]
        for sa in s.members:
            a=helper.get_id(self.destination.annotations, sa.id)
            if not a:
                a=self.copy_annotation(sa)
            members.append(a)
        el=self.destination.createRelation(
            ident=s.id,
            type=rt,
            author=s.author,
            date=s.date,
            members=members)
        el.title=s.title
        el.content.data=s.content.data
        self.destination.relations.append(el)
        return el

    def copy_query(self, s):
        el=self.destination.createQuery(
            ident=s.id,
            author=s.author,
            date=s.date)
        el.title=s.title
        el.content.data=s.content.data
        el.content.mimetype=s.content.mimetype
        self.destination.queries.append(el)
        return el

    def copy_view(self, s):
        el=self.destination.createView(
            ident=s.id,
            clazz=s.viewableClass,
            author=s.author,
            date=s.date)
        el.title=s.title
        el.content.data=s.content.data
        el.content.mimetype=s.content.mimetype
        self.destination.views.append(el)
        return el

    def copy_resource(self, s):
        print "Not implemented yet: copy resource", str(s)
        pass

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print "Should provide 2 package names"
        sys.exit(1)

    sourcename=sys.argv[1]
    destname=sys.argv[2]

    print sourcename, destname
    source=Package(uri=sourcename)
    dest=Package(uri=destname)

    differ=Differ(source, dest)
    diff=differ.diff()
    for name, s, d, action in diff:
        print name, unicode(s).encode('utf-8'), unicode(d).encode('utf-8')
        #action(s, d)
    #dest.save('foo.xml')


