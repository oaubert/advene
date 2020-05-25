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

# OWL importer

name="AdA OWL importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import json
import os

import advene.core.config as config
from advene.util.importer import GenericImporter
try:
    import rdflib
except ImportError:
    rdflib = None

def register(controller=None):
    if rdflib is not None:
        controller.register_importer(AdAOWLImporter)
    return True

class AdAOWLImporter(GenericImporter):
    """Convert an AdA OWL schema into an Advene structure.

    Many assumptions are made here about the ontology structure:

    - the imported graph should define a single owl:Ontology, which
      defines the basic namespace AO.

    - the ontology defines elements of type AO:AnnotationLevel, which
      are converted into Advene schemas.

    - every AO:AnnotationLevel AO:hasAnnotationType: subjects which
      are converted into Advene annotation types.

    - every AO:AnnotationType AO:hasPredefinedValue which are used to
      populate the completions field for the annotation type
    """
    name = _("OWL (schema) importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in [ '.owl' ]:
            return 90
        return 0

    def process_file(self, filename, dest=None):
        graph = rdflib.Graph()
        graph.parse(filename)
        p, at = self.init_package(filename=dest)
        p.setMetaData(config.data.namespace_prefix['dc'],
                      'description',
                      _("Converted from %s") % filename)
        self.convert(self.iterator(graph))
        self.progress(1.0)
        return self.package

    def iterator(self, graph):
        """Iterate through the loaded OWL.
        """
        progress=0.01
        self.progress(progress, "Starting conversion")
        RDF = rdflib.RDF
        OWL = rdflib.OWL

        # Determine the ontology namespace (since it is versioned)
        ontology = list(graph.subjects(RDF.type, OWL.Ontology))
        if len(ontology) != 1:
            logger.error(_("Cannot find a unique ontology in the OWL file."))
            return
        ontology = ontology[0]
        AO = rdflib.Namespace(ontology)
        AR = rdflib.Namespace(ontology.replace('/ontology/', '/resource/'))
        PREFIX = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX ar: <{AR}>
        PREFIX ao: <{AO}>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        """.format(**locals())

        def get_label(graph, subject, default=""):
            """Return a label for the object.

            First try ao:prefixedLabel, then label@en
            Using preferably @en labels
            """
            labels = list(graph.objects(subject, AO.prefixedLabel))
            if labels:
                return labels[0]
            labels = graph.preferredLabel(subject, lang='en')
            if labels:
                # We have at least 1 @en label. Return it.
                return labels[0][1]
            else:
                # No defined label. Use default
                return default

        def get_comment(graph, subject, default=""):
            """Return the comment@en for the object.
            """
            results = list(graph.query(PREFIX + 'SELECT ?comment WHERE { <%s> rdfs:comment ?comment . FILTER langMatches( lang(?comment), "en" ) }' % str(subject)))
            if results:
                return str(results[0][0])
            else:
                return default

        # Dictionary holding a mapping between old ids and new ids. It
        # will be stored as package-level metadata, in order to be
        # easily removed once migration is effective.
        old_id_mapping = {}

        schemas = [ s[0] for s in graph.query(PREFIX + """SELECT ?schema WHERE { ?schema rdf:type ao:AnnotationLevel . OPTIONAL { ?schema ao:sequentialNumber ?number } . BIND ( COALESCE( ?number, 0 ) as ?number ) } ORDER BY xsd:integer(?number)""") ]
        if not schemas:
            logger.error(_("Cannot find a valid schema in the OWL file."))
            return
        incr=0.98 / len(schemas)
        for s in schemas:
            progress += incr
            # Create the schema
            schema_id = s.rpartition('/')[-1]
            title = get_label(graph, s, schema_id)
            description = get_comment(graph, s)
            schema = self.create_schema(schema_id, title=title, description=description)
            schema.setMetaData(config.data.namespace, "ontology_uri", str(s))
            if not self.progress(progress, "Creating schema %s" % schema.title):
                break
            atnodes = [ at[0] for at in graph.query(PREFIX + """SELECT ?at WHERE { <%s> ao:hasAnnotationType ?at . OPTIONAL { ?at ao:sequentialNumber ?number } . BIND ( COALESCE( ?number, 0 ) as ?number )} ORDER BY xsd:integer(?number)""" % str(s)) ]
            for atnode in atnodes:
                at_id = atnode.rpartition('/')[-1]
                label = get_label(graph, atnode, at_id)
                description = get_comment(graph, atnode)
                # Set completions
                values = [ (t[0], str(t[1]))
                           for t in graph.query(PREFIX + """SELECT ?x ?label WHERE { <%s> ao:hasPredefinedValue ?x . ?x rdfs:label ?label . FILTER ( lang(?label) = "en" ) OPTIONAL { ?x ao:sequentialNumber ?number } . BIND ( COALESCE( ?number, 0 ) as ?number ) } ORDER BY xsd:integer(?number)""" % str(atnode)) ]
                if (atnode, RDF.type, AO.PredefinedValuesAnnotationType) in graph or values:
                    mimetype = "text/x-advene-keyword-list"
                elif (atnode, RDF.type, AO.NumericValuesAnnotationType) in graph:
                    mimetype = "application/x-advene-values"
                else:
                    # Default is text/plain anyway
                    mimetype = "text/plain"
                at = self.create_annotation_type(schema, at_id, title=label, description=description, mimetype=mimetype)
                at.setMetaData(config.data.namespace, "ontology_uri", str(atnode))

                if values:
                    # Check for EvolvingAnnotationType and ContrastingAnnotationType to insert [TO] and [VS] predefined keywords
                    values_list = [ v[1] for v in values ]
                    if (atnode, RDF.type, AO.ContrastingAnnotationType) in graph:
                        values_list.insert(0, '[VS]')
                    if (atnode, RDF.type, AO.EvolvingAnnotationType) in graph:
                        values_list.insert(0, '[TO]')
                    at.setMetaData(config.data.namespace, "completions", ",".join(values_list))

                # Store old advene id
                old_ids = list(graph.objects(atnode, AO.oldAdveneIdentifier))
                for i in old_ids:
                    old_id_mapping[i] = at_id

                # Set color
                colors = list(graph.objects(atnode, AO.adveneColorCode))
                if colors:
                    if len(colors) > 1:
                        logger.warning("Multiple colors defined for %s. Using first one.", at_id)
                    color = colors[0]
                    at.setMetaData(config.data.namespace, "color", "string:%s" % color)

                # Additional value metadata
                metadata = {}
                for v in values:
                    value_metadata = {
                        'ontology_uri': str(v[0]),
                    }
                    numeric_values = list(graph.objects(v[0], AO.annotationNumericValue))
                    if numeric_values:
                        if len(numeric_values) > 1:
                            logger.warning("Multiple numeric values defined for %s. Using first one.", v[1])
                        value_metadata['numeric_value'] = numeric_values[0].value
                    metadata[v[1]] = value_metadata
                at.setMetaData(config.data.namespace, "value_metadata", json.dumps(metadata))
        self.progress(1.0)
        self.package.setMetaData(config.data.namespace, "old_id_mapping", json.dumps(old_id_mapping))
        self.package.setMetaData(config.data.namespace, "ontology_uri", str(AO))
        # Hack: we have an empty iterator (no annotations here), but
        # if the yield instruction is not present in the method code,
        # it will not be considered as an iterator. So the following 2
        # lines mark the end of the iterator, and its iterator status.
        return
        yield None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import sys
    from advene.core.controller import AdveneController
    if rdflib is None:
        logger.error("Cannot import required rdflib module")
        sys.exit(1)
    if len(sys.argv) < 4:
        logger.error("Usage: %s (base_package.azp|\"\") owl_file.owl output_package.azp")
        sys.exit(1)

    base_package = sys.argv[1]
    owl_file = sys.argv[2]
    output_package = sys.argv[3]

    c = AdveneController()
    if base_package:
        c.load_package(base_package)
        package = c.package
    else:
        package = None

    i = AdAOWLImporter(controller=c, package=package)

    i.process_options(sys.argv[3:])
    logger.info("Importing %s into %s to produce %s", owl_file, base_package, output_package)
    p = i.process_file(owl_file)
    p.save(output_package)
    logger.info(i.statistics_formatted())
