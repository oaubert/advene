#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2017 Olivier Aubert <contact@olivieraubert.net>
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

name="HPI plugin"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import base64
import json
import requests

import advene.core.config as config
import advene.util.helper as helper
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(HPIImporter)
    return True

class HPIImporter(GenericImporter):
    name = _("HPI concept extraction")
    annotation_filter = True

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        return 80
    can_handle=staticmethod(can_handle)

    def __init__(self, author=None, package=None, defaulttype=None,
                 controller=None, callback=None, annotation_type=None):
        GenericImporter.__init__(self,
                                 author=author,
                                 package=package,
                                 defaulttype=defaulttype,
                                 controller=controller,
                                 callback=callback,
                                 annotation_type=annotation_type)
        if self.source_annotation_type is None:
            self.source_annotation_type = self.controller.package.annotationTypes[0]
        self.source_type_id = self.source_annotation_type.id
        self.model = "standard"
        self.confidence = 0.0
        self.detected_position = True
        self.split_types = False
        self.create_relations = False
        self.url = "http://localhost:9000/"

        self.optionparser.add_option(
            "-t", "--type", action="store", type="choice", dest="source_type_id",
            choices=[at.id for at in self.controller.package.annotationTypes],
            default=self.source_type_id,
            help=_("Type of annotation to analyze"),
            )
        self.optionparser.add_option(
            "-u", "--url", action="store", type="string",
            dest="url", default=self.url,
            help=_("URL of the webservice"),
            )
        self.optionparser.add_option(
            "-c", "--min-confidence", action="store", type="float",
            dest="confidence", default=0.0,
            help=_("Minimum confidence level (between 0.0 and 1.0)"),
            )
        self.optionparser.add_option(
            "-p", "--position", action="store_true",
            dest="detected_position", default=self.detected_position,
            help=_("Use detected position for created annotations"),
            )
        self.optionparser.add_option(
            "-x", "--split-types", action="store_true",
            dest="split_types", default=self.split_types,
            help=_("Split by entity type"),
            )
        self.optionparser.add_option(
            "-m", "--model", action="store", type="string",
            dest="model", default=self.model,
            help=_("Model to be used for detection"),
            )
        self.optionparser.add_option(
            "-r", "--relations", action="store_true",
            dest="create_relations", default=self.create_relations,
            help=_("Create relations between the original annotations and the new ones"),
            )

    @staticmethod
    def can_handle(fname):
        """
        """
        if 'http' in fname:
            return 100
        else:
            return 0

    def process_file(self, _filename):
        self.convert(self.iterator())

    def iterator(self):
        """I iterate over the created annotations.
        """
        self.source_annotation_type = self.controller.package.get_element_by_id(self.source_type_id)
        minconf = self.confidence

        # Make sure that we have all appropriate screenshots
        missing_screenshots = []
        for a in self.source_annotation_type.annotations:
            for t in (a.fragment.begin,
                      int((a.fragment.begin + a.fragment.end) / 2),
                      a.fragment.end):
                if not self.controller.package.imagecache.is_initialized(t):
                    self.controller.update_snapshot(t)
                    missing_screenshots.append(t)
        if len(missing_screenshots) > 0:
            self.output_message = _("Cannot run concept extraction, %d screenshots are missing. Wait for extraction to complete.") % len(missing_screenshots)
            return

        self.progress(.1, "Sending request to server")
        if self.split_types:
            # Dict indexed by entity type name
            new_atypes = {}
        else:
            new_atype = self.ensure_new_type(
                "concept_%s" % self.atype,
                title = _("Concepts for %s" % (self.atype)))
            new_atype.mimetype = 'application/json'
            new_atype.setMetaData(config.data.namespace, "representation",
                                  'here/content/parsed/label')
        if self.create_relations:
            schema = self.create_schema('s_concept')
            rtype_id = 'concept_relation'
            rtype = self.package.get_element_by_id(rtype_id)
            if not rtype:
                # Create a relation type if it does not exist.
                rtype = schema.createRelationType(ident=rtype_id)
                rtype.author = config.data.get_userid()
                rtype.date = self.timestamp
                rtype.title = "Related concept"
                rtype.mimetype='text/plain'
                rtype.setHackedMemberTypes( ('*', '*') )
                schema.relationTypes.append(rtype)
                self.update_statistics('relation-type')
            if not hasattr(rtype, 'getHackedMemberTypes'):
                logger.error("%s is not a valid relation type" % rtype_id)
        # Use a requests.session to use a KeepAlive connection to the server
        session = requests.session()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        response = session.post(self.url, headers=headers, json={
            "model": self.model,
            'media_uri': self.package.uri,
            'media_filename': self.controller.get_default_media(),
            'minimum_confidence': minconf,
            'annotations': [
                { 'annotationid': a.id,
                  'begin': a.fragment.begin,
                  'end': a.fragment.end,
                  'frames': [
                      {
                          'screenshot': base64.encodebytes(bytes(self.controller.package.imagecache.get(t))).decode('ascii'),
                          'timecode': t
                      } for t in (a.fragment.begin,
                                  int((a.fragment.begin + a.fragment.end) / 2),
                                  a.fragment.end)
                  ]
                }
                for a in self.source_annotation_type.annotations
            ]
        })

        output = response.json()
        if output.get('status') != 200:
            # Not OK result. Display error message.
            msg = _("Server error: %s") % output.get('message', _("Server transmission error."))
            logger.error(msg)
            self.output_message = msg
            return
        # FIXME: maybe check consistency with media_filename/media_uri?
        concepts = output.get('data', {}).get('concepts', [])
        progress = .2
        step = .8 / (len(concepts) or 1)
        self.progress(.2, _("Parsing %d results") % len(concepts))
        for item in concepts:
            # Should not happen, since we pass the parameter to the server
            if item["confidence"] < minconf:
                continue
            a = self.package.get_element_by_id(item['annotationid'])
            if self.detected_position:
                begin = item['timecode']
            else:
                begin = a.fragment.begin
            end = a.fragment.end
            label = item.get('label')
            label_id = helper.title2id(label)
            if label and self.split_types:
                new_atype = new_atypes.get(label_id)
                if new_atype is None:
                   # Not defined yet. Create a new one.
                   new_atype = self.ensure_new_type(label_id, title = _("%s concept" % label))
                   new_atype.mimetype = 'application/json'
                   new_atype.setMetaData(config.data.namespace, "representation",
                                         'here/content/parsed/label')
                   new_atypes[label_id] = new_atype
            an = yield {
                'type': new_atype,
                'begin': begin,
                'end': end,
                'content': json.dumps(item),
                'send': True
            }
            if an is not None and self.create_relations:
                r = self.package.createRelation(
                    ident='_'.join( ('r', a.id, an.id) ),
                    type=rtype,
                    author=config.data.get_userid(),
                    date=self.timestamp,
                    members=(a, an))
                r.title = "Relation between %s and %s" % (a.id, an.id)
                self.package.relations.append(r)
                self.update_statistics('relation')
            self.progress(progress)
            progress += step
