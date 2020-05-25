#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2020 Olivier Aubert <contact@olivieraubert.net>
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

# ELAN importer

name="ELAN importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import re
import xml.dom

import advene.core.config as config
import advene.util.handyxml as handyxml
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(ElanImporter)
    return True

class ElanImporter(GenericImporter):
    """Elan importer.
    """
    name=_("ELAN importer")

    def __init__(self, **kw):
        super(ElanImporter, self).__init__(**kw)
        self.anchors={}
        self.atypes={}
        self.schema=None
        self.relations=[]
        self.forward_references = []

    @staticmethod
    def can_handle(fname):
        if fname.endswith('.eaf'):
            return 100
        elif fname.endswith('.elan'):
            return 100
        elif fname.endswith('.xml'):
            return 50
        else:
            return 0

    def xml_to_text(self, element):
        l=[]
        if isinstance(element, handyxml.HandyXmlWrapper):
            element=element.node
        if element.nodeType is xml.dom.Node.TEXT_NODE:
            l.append(element.data)
        elif element.nodeType is xml.dom.Node.ELEMENT_NODE:
            for e in element.childNodes:
                l.append(self.xml_to_text(e))
        return "".join(l)

    def iterator(self, elan):
        valid_id_re = re.compile('[^a-zA-Z_0-9]')
        # List of tuples (annotation-id, related-annotation-uri) of
        # forward referenced annotations
        progress=0.1
        incr=0.02
        for tier in elan.TIER:
            if not hasattr(tier, 'ANNOTATION'):
                # Empty tier
                continue
            tid = tier.LINGUISTIC_TYPE_REF.replace(' ','_') + '__' + tier.TIER_ID.replace(' ', '_')

            tid=valid_id_re.sub('', tid)

            if tid not in self.atypes:
                self.atypes[tid]=self.create_annotation_type(self.schema, tid)

            if not self.progress(progress, _("Converting tier %s") % tid):
                break
            progress += incr
            for an in tier.ANNOTATION:
                d={}

                d['type']=self.atypes[tid]
                if hasattr(an, 'ALIGNABLE_ANNOTATION'):
                    # Annotation on a timeline
                    al=an.ALIGNABLE_ANNOTATION[0]
                    d['begin']=self.anchors[al.TIME_SLOT_REF1]
                    d['end']=self.anchors[al.TIME_SLOT_REF2]
                    d['id']=al.ANNOTATION_ID
                    d['content']=self.xml_to_text(al.ANNOTATION_VALUE[0].node)
                    yield d
                elif hasattr(an, 'REF_ANNOTATION'):
                    # Reference to another annotation. We will reuse the
                    # related annotation's fragment and put it in relation
                    ref=an.REF_ANNOTATION[0]
                    d['id']=ref.ANNOTATION_ID
                    d['content']=self.xml_to_text(ref.ANNOTATION_VALUE[0].node)
                    # Related annotation:
                    rel_id = ref.ANNOTATION_REF
                    rel_uri = '#'.join( (self.package.uri, rel_id) )

                    if rel_uri in self.package.annotations:
                        rel_an=self.package.annotations[rel_uri]
                        # We reuse the related annotation fragment
                        d['begin'] = rel_an.fragment.begin
                        d['end'] = rel_an.fragment.end
                    else:
                        self.forward_references.append( (d['id'], rel_uri) )
                        d['begin'] = 0
                        d['end'] = 0
                    self.relations.append( (rel_id, d['id']) )
                    yield d
                else:
                    raise Exception('Unknown annotation type')

    def create_relations(self):
        """Postprocess the package to create relations."""
        for (source_id, dest_id) in self.relations:
            source=self.package.annotations['#'.join( (self.package.uri,
                                                       source_id) ) ]
            dest=self.package.annotations['#'.join( (self.package.uri,
                                                     dest_id) ) ]

            rtypeid='_'.join( ('rt', source.type.id, dest.type.id) )
            try:
                rtype=self.package.relationTypes['#'.join( (self.package.uri,
                                                            rtypeid) ) ]
            except KeyError:
                rtype=self.schema.createRelationType(ident=rtypeid)
                #rt.author=schema.author
                rtype.date=self.schema.date
                rtype.title="Relation between %s and %s" % (source.type.id,
                                                            dest.type.id)
                rtype.mimetype='text/plain'
                # FIXME: Update membertypes (missing API)
                rtype.setHackedMemberTypes( ('#'+source.type.id,
                                             '#'+dest.type.id) )
                self.schema.relationTypes.append(rtype)
                self.update_statistics('relation-type')

            r=self.package.createRelation(
                ident='_'.join( ('r', source_id, dest_id) ),
                type=rtype,
                author=source.author,
                date=source.date,
                members=(source, dest))
            r.title="Relation between %s and %s" % (source_id, dest_id)
            self.package.relations.append(r)
            self.update_statistics('relation')

    def fix_forward_references(self):
        for (an_id, rel_uri) in self.forward_references:
            an_uri = '#'.join( (self.package.uri, an_id) )
            an=self.package.annotations[an_uri]
            rel_an=self.package.annotations[rel_uri]
            # We reuse the related annotation fragment
            an.fragment.begin = rel_an.fragment.begin
            an.fragment.end   = rel_an.fragment.end

    def process_file(self, filename):
        elan=handyxml.xml(filename)

        self.init_package(filename)
        self.schema=self.create_schema(id_='elan', title="ELAN converted schema")
        try:
            self.schema.date=elan.DATE
        except AttributeError:
            self.schema.date = self.timestamp

        # self.anchors init
        if elan.HEADER[0].TIME_UNITS != 'milliseconds':
            raise Exception('Cannot process non-millisecond fragments')

        self.progress(0.1, _("Processing time slots"))
        duration = 0
        for a in elan.TIME_ORDER[0].TIME_SLOT:
            try:
                d = self.anchors[a.TIME_SLOT_ID] = int(a.TIME_VALUE)
                duration = max(duration, d)
            except AttributeError:
                # FIXME: should not silently ignore error
                self.anchors[a.TIME_SLOT_ID] = 0

        # If duration is not yet set in Advene (starting from a
        # template), use max timestamp
        if self.controller.get_cached_duration() == 0:
            self.controller.package.setMetaData(config.data.namespace, "duration", str(duration))
            self.controller.notify('DurationUpdate', duration=duration)

        # Process types
        #for lt in elan.LINGUISTIC_TYPE:
        #    i=lt.LINGUISTIC_TYPE_ID
        #    i=i.replace(' ', '_')
        #    self.create_annotation_type(schema, i)

        self.convert(self.iterator(elan))
        self.progress(0.8, _("Fixing forward references"))
        self.fix_forward_references()
        self.progress(0.9, _("Creating relations"))
        self.create_relations()
        self.progress(1.0)
        return self.package
