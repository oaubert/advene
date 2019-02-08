#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2018 Olivier Aubert <contact@olivieraubert.net>
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

# AdA RDF Exporter, based on WebAnnotation exporter

name="AdA RDF exporter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from collections import namedtuple

import advene.core.config as config
from advene.plugins.webannotation_export import WebAnnotationExporter

def register(controller=None):
    controller.register_exporter(AdARDFExporter)
    return True

# Evolving/ContrastingAnnotationType markers
TO_KW = '[TO]'
VS_KW = '[VS]'

def keywords_to_struct(keywords):
    """Generator that outputs typed values from keyword lists.

    type is either predefined, contrasting or evolving.
    """
    if not keywords:
        return
    TypedValues = namedtuple('TypedValue', ['type', 'values'])
    prev = None
    need_value = False
    while keywords:
        current = keywords.pop(0)
        if current in (TO_KW, VS_KW):
            if need_value:
                logger.error("Syntax error: expecting a value, not %s keyword." % current)
                prev = None
                need_value = False
            if prev is None:
                logger.error("Syntax error: %s keyword should have a value before." % current)
                prev = None
                need_value = False
            elif not keywords:
                logger.error("Syntax error: %s keyword should have a value after." % current)
                prev = None
                need_value = False
            else:
                need_value = True
                if current == TO_KW:
                    if prev.type == "predefined":
                        # We may have accumulated predefined
                        # values. Keep the last one, but yield the
                        # other.
                        if len(prev.values) > 1:
                            yield TypedValues(type="predefined", values=prev.values[:-1])
                        prev = TypedValues(type="evolving", values=prev.values[-1:])
                    elif prev.type != "evolving":
                        logger.error("Syntax error: mixed contrasting/evolving values in %s" % current)
                        prev = None
                        need_value = False
                elif current == VS_KW:
                    if prev.type == "predefined":
                        # We may have accumulated predefined
                        # values. Keep the last one, but yield the
                        # other.
                        if len(prev.values) > 1:
                            yield TypedValues(type="predefined", values=prev.values[:-1])
                        prev = TypedValues(type="contrasting", values=prev.values[-1:])
                    elif prev.type != "contrasting":
                        logger.error("Syntax error: mixed contrasting/evolving values in %s" % current)
                        prev = None
                        need_value = False
                else:
                    logger.error("This should never happen.")
        else:
            if prev:
                if need_value or prev.type == "predefined":
                    prev = TypedValues(type=prev.type, values=prev.values + [current])
                else:
                    # Change of sequence type.
                    yield prev
                    prev = TypedValues(type="predefined", values=[ current ])
            else:
                prev = TypedValues(type="predefined", values=[ current ])
            need_value = False
    yield prev

class AdARDFExporter(WebAnnotationExporter):
    name = _("AdA RDF exporter")
    extension = 'ada.jsonld'

    def __init__(self, controller=None, source=None):
        super().__init__(controller=controller, source=source)
        self.not_part_of_ontology = set()

    def annotation_uri(self, a, media_uri):
        return "%s/%s" % (media_uri, a.id)

    def annotation_jsonld(self, a, media_uri):
        # First check if it is part of the ontology schema
        type_uri = a.type.getMetaData(config.data.namespace, "ontology_uri")
        if not type_uri:
            # Report only once by type
            if a.type not in self.not_part_of_ontology:
                logger.warn(_("Cannot determine ontology URI for type %s"), self.controller.get_title(a.type))
                self.not_part_of_ontology.add(a.type)
            # Just ignore this annotation
            return None

        # Get standard WebAnnotation jsonld serialization
        data = super().annotation_jsonld(a, media_uri)

        # Enrich with AdA-specific properties
        value_type_mapping = {
            "evolving": "ao:EvolvingValuesAnnotationType",
            "contrasting": "ao:ContrastingValuesAnnotationType",
            "predefined": "ao:PredefinedValuesAnnotationType"
        }
        # Build body according to content type
        def new_body(btype=None):
            """Create a new body node
            """
            body = {
                "ao:annotationType": type_uri
            }
            if btype is not None:
                body['@type'] = btype
            return body

        if a.type.mimetype == 'text/x-advene-keyword-list':
            keywords = a.content.parsed()

            def get_keyword_uri(kw):
                uri = keywords.get(kw, 'ontology_uri')
                return uri

            keyword_struct = list(keywords_to_struct(list(keywords)))
            body = None
            if len(keyword_struct) == 1:
                # Found 1 mapping
                typedvalues = keyword_struct[0]
                if typedvalues is not None:
                    body = new_body(value_type_mapping[typedvalues.type])
                    if typedvalues.type == "predefined":
                        # FIXME: how to generate multiple annotationValues here?
                        # Let's fallback to a sequence for the moment
                        body['ao:annotationValue'] = [ get_keyword_uri(kw) for kw in typedvalues.values ]
                    else:
                        # Generate a sequence for contrasting/evolving values.
                        body['ao:annotationValueSequence'] = { "@list": [ get_keyword_uri(kw) for kw in typedvalues.values ] }

            if body is None:
                # Could not parse correctly.
                msg = "Could not parse keywords %s for annotation %s" % (keywords, a.uri)
                logger.warn(msg)
                body = new_body(btype="oa:TextualBody")
                body['value'] = a.content.data
                body['advene:ERROR'] = msg

            # Attach comment to the last body
            if keywords.get_comment():
                body['rdf:comment'] = keywords.get_comment()

        else:
            body = new_body(btype="oa:TextualBody")
            body['value'] = a.content.data

        data['body'] = body

        return data

    def export(self, filename=None):
        # Works in source is a package or a type
        package = self.source.ownerPackage
        data = super().export(None)

        # Get the namespace from the package metdata
        ontology = package.getMetaData(config.data.namespace, "ontology_uri")
        if not ontology:
            return _("Cannot find the ontology URI. It should be defined as package metadata.")
        data['@context'].append({
            "ao": ontology,
            "ao:annotationType": { "@type": "@id" },
            "ao:annotationValue": { "@type": "@id" },
            "ao:annotationValueSequence": { "@type": "@id" }
        })

        return self.output(data, filename)

if __name__ == "__main__":
    # Let's do some tests. This will be moved to unit tests later on.
    samples = {
        "a1": 1,
        "a1,a2": 1,
        "a1,[TO],a2": 1,
        "a1,[VS],a2": 1,
        "a1,[TO],a2,[TO],a3": 1,
        "a1,[TO],a2,[TO],a3,a4": 2,
        "a1,[TO],a2,[VS],a3": 1, # Expecting syntax error
        "a1,a2,[TO],a3,a4,[VS],a5": 3
    }
    for s in samples.keys():
        print(s, "\n", list(keywords_to_struct(s.split(","))), "\n\n")

