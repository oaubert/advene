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
from urllib.parse import quote

from gi.repository import Gtk

import advene.core.config as config
import advene.util.helper as helper
from advene.plugins.webannotation_export import WebAnnotationExporter
from advene.gui.views.table import COLUMN_TYPE
from advene.gui.views.checker import FeatureChecker, register_checker, AnnotationTable

def register(controller=None):
    controller.register_exporter(AdARDFExporter)
    # We also register a checker component that checks the keyword
    # syntax, in GUI mode

    # FIXME: we depend on gui.views.checker which is loaded as a
    # plugin, so it may not be available at plugin load time
    return True

# Evolving/ContrastingAnnotationType markers
TO_KW = '[TO]'
VS_KW = '[VS]'

def keywords_to_struct(keywords, on_error=None):
    """Generator that outputs typed values from keyword lists.

    on_error allows to get error messages as callbacks
    type is either predefined, contrasting or evolving.
    """
    def report_error(msg):
        logger.error(msg)
        if on_error is not None:
            on_error(msg)

    if not keywords:
        return
    TypedValues = namedtuple('TypedValue', ['type', 'values'])
    prev = None
    need_value = False
    while keywords:
        current = keywords.pop(0)
        if current in (TO_KW, VS_KW):
            if need_value:
                report_error("Syntax error: expecting a value, not %s keyword." % current)
                prev = None
                need_value = False
            if prev is None:
                report_error("Syntax error: %s keyword should have a value before." % current)
                prev = None
                need_value = False
            elif not keywords:
                report_error("Syntax error: %s keyword should have a value after." % current)
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
                        report_error("Syntax error: mixed contrasting/evolving values in %s" % current)
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
                        report_error("Syntax error: mixed contrasting/evolving values in %s" % current)
                        prev = None
                        need_value = False
                else:
                    report_error("This should never happen.")
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
                logger.warning(_("Cannot determine ontology URI for type %s"), self.controller.get_title(a.type))
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
            if (a.content.mimetype != a.type.mimetype
                and a.content.mimetype == 'text/plain'):
                a.content.mimetype = a.type.mimetype
            keywords = a.content.parsed()

            def get_keyword_uri(kw):
                uri = keywords.get(kw, 'ontology_uri')
                if uri is None:
                    # Generate a dummy URI
                    return f"http://www.advene.org/ns/_local/keyword/{quote(kw.replace(' ', '_'))}"
                return uri

            keyword_struct = list(keywords_to_struct(list(keywords)))
            bodies = []
            for typedvalues in keyword_struct:
                if typedvalues is not None:
                    body = new_body(value_type_mapping[typedvalues.type])
                    if typedvalues.type == "predefined":
                        if len(typedvalues.values) == 1:
                            # Single value. Let's try to get its numeric value
                            kw = typedvalues.values[0]
                            body['ao:annotationValue'] = get_keyword_uri(kw)
                            num_value = keywords.get(kw, 'numeric_value')
                            if num_value is not None:
                                body['ao:annotationNumericValue'] = num_value
                        else:
                            # Multiple values
                            body['ao:annotationValue'] = [ get_keyword_uri(kw) for kw in typedvalues.values ]
                    else:
                        # Generate a sequence for contrasting/evolving values.
                        body['ao:annotationValueSequence'] = { "@list": [
                            get_keyword_uri(kw) for kw in typedvalues.values
                        ] }
                        body['ao:annotationNumericValueSequence'] = { "@list": [
                            keywords.get(kw, 'numeric_value', -1) for kw in typedvalues.values
                        ] }

                    bodies.append(body)

            error = None
            if not bodies:
                # Could not parse correctly.
                error = "Could not parse keywords %s for annotation %s" % (keywords, a.uri)
                logger.warning(error)
                bodies = [ ]

            # Attach comment to the last body
            if keywords.get_comment() and bodies:
                bodies[-1]['rdfs:comment'] = keywords.get_comment()

            # Add textual body
            body = new_body(btype="oa:TextualBody")
            body['value'] = self.controller.get_title(a)
            if error:
                body['advene:ERROR'] = error
            bodies.append(body)

        else:
            body = new_body(btype="oa:TextualBody")
            # Default: use raw content data
            body['value'] = a.content.data

            # Special cases
            if a.type.id == 'ShotDuration':
                # Hardcoded case: duration in ms
                body['value'] = a.fragment.duration
            else:
                # If a representation is specified, then use it.
                rep = a.type.getMetaData(config.data.namespace, "representation")
                if rep:
                    body['value'] = self.controller.get_title(a)

            bodies = [ body ]

        if len(bodies) == 1:
            data['body'] = bodies[0]
        else:
            data['body'] = bodies

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

@register_checker
class AdAChecker(FeatureChecker):
    name = "AdA syntax"
    description = _("For every annotation type that has predefined keywords, this table displays the annotations that contain unspecified keywords or invalid syntax. Update is not real-time, you need to manually update the view with the button below.")
    def build_widget(self):
        self.table = AnnotationTable(controller=self.controller, custom_data=lambda a: (str, ))
        column = self.table.columns['custom0']
        column.props.title = _("Error")
        self.widget = Gtk.VBox()
        b = Gtk.Button("Update")
        b.connect('clicked', lambda i: self.update_view())
        self.widget.pack_start(b, False, False, 0)
        self.widget.pack_start(self.table.widget, True, True, 0)
        return self.widget

    def update_model(self, package=None):
        # Do not update information live, it is too costly.
        pass

    def update_view(self):
        # Dict of errors indexed by annotation
        errors = {}
        def custom_data(a):
            if a is None:
                return (str, )
            else:
                return ("\n".join(errors.get(a, [])), )

        for at in self.controller.package.annotationTypes:
            completions = set(helper.get_type_predefined_completions(at))
            if completions:
                # There are completions. Check for every annotation if
                # they use a keyword not predefined.
                for a in at.annotations:
                    def add_error(msg):
                        errors.setdefault(a, []).append(msg)

                    keywords = a.content.parsed()
                    if len(keywords) == 0 and keywords.get_comment() == "" and len(a.content.data) > 0:
                        # There seems to be a content, but we could find no keyword and no comment.
                        add_error("Unparsable content")
                        continue
                    # Parse keywords to detect syntax errors
                    for s in keywords_to_struct(list(keywords), add_error):
                        pass

        self.table.set_elements(list(errors.keys()), custom_data)
        self.table.model.set_sort_column_id(COLUMN_TYPE, Gtk.SortType.ASCENDING)

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
