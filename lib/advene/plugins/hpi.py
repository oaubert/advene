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
from collections import OrderedDict
from io import BytesIO
import json
from PIL import Image
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
                 controller=None, callback=None, source_type=None):
        GenericImporter.__init__(self,
                                 author=author,
                                 package=package,
                                 defaulttype=defaulttype,
                                 controller=controller,
                                 callback=callback,
                                 source_type=source_type)
        if self.source_type is None:
            self.source_type = self.controller.package.annotationTypes[0]
        self.source_type_id = self.source_type.id

        if source_type is not None:
            # A source_type was specified at instanciation. Update the
            # preferences now since we will use this info to update
            # the filter options.
            self.get_preferences().update({'source_type_id': self.source_type_id})

        self.model = "standard"
        self.confidence = 0.0
        self.detected_position = True
        self.split_types = False
        self.create_relations = False
        self.url = self.get_preferences().get('url', 'http://localhost:9000/')

        self.server_options = {}
        # Populate available models options from server
        try:
            r = requests.get(self.url)
            if r.status_code == 200:
                # OK. We should have some server options available as json
                data = r.json()
                caps = data.get('data', {}).get('capabilities', {})
                for n in ('minimum_batch_size', 'maximum_batch_size', 'available_models'):
                    self.server_options[n] = caps.get(n, None)
                logger.warn("Got capabilities from VCD server - batch size in (%d, %d) - %d models: %s",
                            self.server_options['minimum_batch_size'],
                            self.server_options['maximum_batch_size'],
                            len(self.server_options['available_models']),
                            ", ".join(item['id'] for item in self.server_options['available_models']))
        except requests.exceptions.RequestException:
            pass
        if 'available_models' in self.server_options:
            self.available_models = OrderedDict((item['id'], item) for item in self.server_options['available_models'])
        else:
            self.available_models = OrderedDict()
            self.available_models["standard"] = { 'id': "standard",
                                                  'label': "Standard",
                                                  'image_size': 224 }

        self.optionparser.add_option(
            "-t", "--source-type-id", action="store", type="choice", dest="source_type_id",
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
            "-m", "--model", action="store", type="choice",
            dest="model", default=self.model, choices=list(self.available_models.keys()),
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

    def check_requirements(self):
        """Check if external requirements for the importers are met.

        It returns a list of strings describing the unmet
        requirements. If the list is empty, then all requirements are
        met.
        """
        unmet_requirements = []

        # Check server connectivity
        try:
            requests.get(self.url)
        except requests.exceptions.RequestException:
            unmet_requirements.append(_("Cannot connect to VCD server. Check that it is running and accessible."))

        # Make sure that we have all appropriate screenshots
        missing_screenshots = set()
        for a in self.source_type.annotations:
            for t in (a.fragment.begin,
                      int((a.fragment.begin + a.fragment.end) / 2),
                      a.fragment.end):
                if self.controller.get_snapshot(annotation=a, position=t).is_default:
                    missing_screenshots.add(t)
        if len(missing_screenshots) > 0:
            unmet_requirements.append(_("%d / %d screenshots are missing. Wait for extraction to complete.") % (len(missing_screenshots),
                                                                                                                3 * len(self.source_type.annotations)))
        return unmet_requirements

    def iterator(self):
        """I iterate over the created annotations.
        """
        logger.warn("Importing using %s model", self.model)
        self.source_type = self.controller.package.get_element_by_id(self.source_type_id)
        minconf = self.confidence

        self.progress(.1, "Sending request to server")
        if self.split_types:
            # Dict indexed by entity type name
            new_atypes = {}
        else:
            new_atype = self.ensure_new_type(
                "concept_%s" % self.source_type_id,
                title = _("Concepts for %s" % (self.source_type_id)))
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

        image_scale = self.available_models.get(self.model, {}).get('image_size')
        if image_scale:
            logger.warn("Scaling images to (%d, %d) as requested by %s", image_scale, image_scale, self.model)

        def get_scaled_image(t):
            """Return the image at the appropriate scale for the selected model.
            """
            original = bytes(self.controller.package.imagecache.get(t))
            if image_scale:
                im = Image.open(BytesIO(original))
                im = im.resize((image_scale, image_scale))
                buf = BytesIO()
                im.save(buf, 'PNG')
                scaled = buf.getvalue()
                buf.close()
            else:
                scaled = original
            return scaled

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
                          'screenshot': base64.encodebytes(get_scaled_image(t)).decode('ascii'),
                          'timecode': t
                      } for t in (a.fragment.begin,
                                  int((a.fragment.begin + a.fragment.end) / 2),
                                  a.fragment.end)
                  ]
                }
                for a in self.source_type.annotations
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
        logger.warn(_("Parsing %d results (level %f)") % (len(concepts), self.confidence))
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
