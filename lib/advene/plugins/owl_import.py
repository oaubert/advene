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
        AO = rdflib.Namespace('http://ada.filmontology.org/ontology/')
        AR = rdflib.Namespace('http://ada.filmontology.org/resource/')
        PREFIX = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
        PREFIX ar: <http://ada.filmontology.org/resource/>
        PREFIX ao: <http://ada.filmontology.org/ontology/>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        """
        def get_label(graph, subject, default=""):
            """Return a label for the object.

            Using preferably @en labels
            """
            labels = graph.preferredLabel(s, lang='en')
            if labels:
                # We have at least 1 @en label. Return it.
                return labels[0][1]
            else:
                # No defined label. Use default
                return default

        def get_comment(graph, subject, default=""):
            """Return the comment@en for the object.
            """
            results = list(graph.query(PREFIX + 'SELECT ?comment WHERE { <%s> rdfs:comment ?comment . FILTER langMatches( lang(?comment), "en" ) }' % unicode(subject)))
            if results:
                return unicode(results[0][0])
            else:
                return default

        progress=0.01
        self.progress(progress, "Starting conversion")
        RDF = rdflib.RDF
        schemas = list(graph.subjects(RDF.type, AO.AnnotationLevel))
        incr=0.98 / len(schemas)
        for s in schemas:
            progress += incr
            # Create the schema
            # FIXME: there is no label neither description at the moment.
            schema_id = s.rpartition('/')[-1]
            title = get_label(graph, s, schema_id)
            description = get_comment(graph, s)
            schema = self.create_schema(schema_id, title=title, description=description)
            if not self.progress(progress, "Creating schema %s" % schema.title):
                break
            for at in graph.objects(s, AO.term('hasAnnotationType')):
                at_id = at.rpartition('/')[-1]
                label = get_label(graph, at, at_id)
                description = get_comment(graph, at)
                self.create_annotation_type(schema, at_id, title=label, description=description)
        self.progress(1.0)
        # Hack: we have an empty iterator (no annotations here), but
        # if the yield instruction is not present in the method code,
        # it will not be considered as an iterator. So the following 2
        # lines mark the end of the iterator, and its iterator status.
        return
        yield None

if __name__ == "__main__":
    import sys
    if rdflib is None:
        print("Cannot import required rdflib module")
        sys.exit(1)
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = OWLImporter()

    i.process_options(sys.argv[1:])
    print "Converting %s to %s using %s" % (fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    print i.statistics_formatted()
