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
        GenericImporter.__init__(self, author, package, defaulttype,
                                 controller, callback)

        self.atype = annotation_type.id if annotation_type else self.controller.package.annotationTypes[0].id
        self.confidence = 0.0
        self.detected_position = True
        self.split_types = False
        self.markup = False
        self.create_relations = False
        self.url = "http://localhost:9000/"

        self.optionparser.add_option(
            "-t", "--type", action="store", type="choice", dest="atype",
            choices=[at.id for at in self.controller.package.annotationTypes],
            default=self.atype,
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
            "-m", "--markup", action="store_true",
            dest="markup", default=self.markup,
            help=_("Store results as markup in the annotation text"),
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
        src_atype = self.controller.package.get_element_by_id(self.atype)
        minconf = self.confidence

        # Make sure that we have all appropriate screenshots
        missing_screenshots = []
        for a in src_atype.annotations:
            for t in (a.fragment.begin, (a.fragment.begin + a.fragment.end) / 2, a.fragment.end):
                if not self.controller.package.imagecache.is_initialized(t):
                    self.controller.update_snapshot(t)
                    missing_screenshots.append(t)
        if len(missing_screenshots) > 0:
            self.output_message = _("Cannot run concept extraction, %d screenshots are missing. Wait for extraction to complete.") % len(missing_screenshots)
            return

        self.progress(.1, "Concept extraction")
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
        self.progress(.2, "Parsing results")

        progress = .2
        step = .8 / (len(src_atype.annotations) or 1)

        for a in src_atype.annotations:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            response = session.post(self.url, headers=headers, json={ 'annotationid': a.id,
                                                                      'begin': a.fragment.begin,
                                                                      'end': a.fragment.end,
                                                                      'minimum_confidence': minconf,
                                                                      'frames': [
                                                                          {
                                                                              'screenshot': base64.encodestring(str(self.controller.package.imagecache.get(t))),
                                                                              'timecode': t
                                                                          } for t in (a.fragment.begin, (a.fragment.begin + a.fragment.end) / 2, a.fragment.end)
                                                                      ]
            })
            output = response.json()
            for item in output['data']:
                # Should not happen, since we pass the parameter to the server
                if item["confidence"] < minconf:
                    continue
                if self.detected_position:
                    begin = item['timecode']
                else:
                    begin = a.fragment.begin
                end = a.fragment.end
                t = item.get('label')
                if t and self.split_types:
                    at = new_atypes.get(t)
                    if at is None:
                        # Not defined yet. Create a new one.
                        at = self.ensure_new_type(t, title = _("%s concept" % t))
                        at.mimetype = 'application/json'
                        at.setMetaData(config.data.namespace, "representation",
                                       'here/content/parsed/label')
                        new_atypes[t] = at
                        new_atype = at
                an = (yield {
                    'type': new_atype,
                    'begin': begin,
                    'end': end,
                    'content': json.dumps(item)
                })
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
