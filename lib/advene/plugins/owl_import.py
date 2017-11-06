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

name="OWL importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import os

import advene.core.config as config
from advene.util.importer import GenericImporter
try:
    import rdflib
except ImportError:
    rdflib = None

def register(controller=None):
    if rdflib is not None:
        controller.register_importer(OWLImporter)
    return True

class OWLImporter(GenericImporter):
    """Convert an OWL schema into an Advene structure.

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

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in [ '.owl' ]:
            return 90
        return 0
    can_handle=staticmethod(can_handle)

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

            Using preferably @en labels
            """
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

        schemas = list(graph.subjects(RDF.type, AO.AnnotationLevel))
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
            schema.setMetaData(config.data.namespace, "source_uri", str(s))
            if not self.progress(progress, "Creating schema %s" % schema.title):
                break
            for atnode in graph.objects(s, AO.term('hasAnnotationType')):
                at_id = atnode.rpartition('/')[-1]
                label = get_label(graph, atnode, at_id)
                description = get_comment(graph, atnode)
                at = self.create_annotation_type(schema, at_id, title=label, description=description)
                at.setMetaData(config.data.namespace, "source_uri", str(atnode))
                values = [ str(t[0])
                           for t in graph.query(PREFIX + """SELECT ?label WHERE { <%s> ao:hasPredefinedValue ?x . ?x rdfs:label ?label . FILTER ( lang(?label) = "en" )}""" % str(atnode)) ]
                if values:
                    at.setMetaData(config.data.namespace, "completions", ",".join(values))
        self.progress(1.0)
        # Hack: we have an empty iterator (no annotations here), but
        # if the yield instruction is not present in the method code,
        # it will not be considered as an iterator. So the following 2
        # lines mark the end of the iterator, and its iterator status.
        return
        yield None

if __name__ == "__main__":
    import sys
    from advene.core.controller import AdveneController
    if rdflib is None:
        logger.error("Cannot import required rdflib module")
        sys.exit(1)
    if len(sys.argv) < 3:
        logger.error("Should provide a file name and a package name")
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    c = AdveneController()
    i = OWLImporter(controller=c)

    i.process_options(sys.argv[1:])
    logger.info("Converting %s to %s using %s", fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    logger.info(i.statistics_formatted())
