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

# AdA rdflib Exporter

name="AdA rdflib exporter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from collections import namedtuple

try:
    import rdflib
    from rdflib import URIRef, BNode, Literal
    from rdflib.collection import Collection
    from rdflib.namespace import RDF, RDFS, XSD, DC, DCTERMS
except ImportError:
    rdflib = None

import advene.core.config as config
import advene.util.helper as helper
from advene.util.exporter import GenericExporter

def register(controller=None):
    if rdflib is None:
        logger.warning("rdflib module is not available. AdARDFExporter plugin is disabled.")
    else:
        controller.register_exporter(AdArdflibExporter)
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
                logger.error("Syntax error: expecting a value, not %s keyword.", current)
                prev = None
                need_value = False
            if prev is None:
                logger.error("Syntax error: %s keyword should have a value before.", current)
                prev = None
                need_value = False
            elif not keywords:
                logger.error("Syntax error: %s keyword should have a value after.", current)
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
                        logger.error("Syntax error: mixed contrasting/evolving values in %s", current)
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
                        logger.error("Syntax error: mixed contrasting/evolving values in %s", current)
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

class AdArdflibExporter(GenericExporter):
    name = _("AdA rdflib exporter")
    extension = 'rdf'

    def __init__(self, controller=None, source=None):
        super().__init__(controller=controller, source=source)
        self.format = "json-ld"
        self.optionparser.add_option("-f", "--format",
                                     action="store", type="choice", dest="format",
                                     choices=("n3", "json-ld", "ttl", "xml"),
                                     default=self.format,
                                     help=_("File format for output"))

    @classmethod
    def is_valid_for(cls, expr):
        """Is the template valid for different types of sources.

        expr is either "package" or "annotation-type" or "annotation-container".
        """
        return expr in ('package', 'annotation-type', 'annotation-container')

    def get_filename(self, basename=None, source=None):
        """Return a filename with the appropriate extension.
        """
        self.extension = self.format
        return super().get_filename(basename, source)

    def export(self, filename):
        # Works in source is a package or a type
        package = self.source.ownerPackage

        media_uri = package.getMetaData(config.data.namespace, "media_uri") or self.controller.get_default_media()

        # Get the namespace from the package metdata
        ontology = package.getMetaData(config.data.namespace, "ontology_uri")
        if not ontology:
            return _("Cannot find the ontology URI. It should be defined as package metadata.")
        AO = rdflib.Namespace(ontology)
        #AR = rdflib.Namespace(ontology.replace('/ontology/', '/resource/'))
        AS = rdflib.Namespace("http://www.w3.org/ns/activitystreams#")
        OA = rdflib.Namespace("http://www.w3.org/ns/oa#")

        g = rdflib.Graph()
        g.bind('ao', AO)
        g.bind('oa', OA)
        g.bind('activitystreams', AS)
        g.bind('dc', DC)
        g.bind('dcterms', DCTERMS)

        collection = BNode()
        page = URIRef("page1")
        g.add((collection, RDF.type, OA.AnnotationCollection))
        g.add((collection, RDFS.label, Literal(self.controller.get_title(self.source))))
        g.add((collection, AS.totalItems, Literal(len(self.source.annotations), datatype=XSD.nonNegativeInteger)))
        g.add((collection, AS.first, page))

        pageItems = BNode()
        g.add((page, AS.items, pageItems))

        itemcollection = Collection(g, pageItems)

        def get_annotation_uri(a):
            return "%s/%s" % (media_uri, a.id)

        not_part_of_ontology = set()
        for a in self.source.annotations:
            # First check if it is part of the ontology schema
            type_uri = a.type.getMetaData(config.data.namespace, "ontology_uri")
            if not type_uri:
                # Report only once by type
                if a.type not in not_part_of_ontology:
                    logger.warning(_("Cannot determine ontology URI for type %s"), self.controller.get_title(a.type))
                    not_part_of_ontology.add(a.type)
                # Just ignore this annotation
                continue
            anode = URIRef(get_annotation_uri(a))
            itemcollection.append(anode)
            g.add((anode, RDF.type, OA.Annotation))
            g.add((anode, DCTERMS.created, Literal(a.date, datatype=XSD.dateTime)))
            # We use DC instead of DCTERMS so that we can simply put the string value as a literal
            g.add((anode, DC.creator, Literal(a.author)))

            def new_body(btype=None):
                """Create a new body node
                """
                body = BNode()
                g.add((anode, OA.hasBody, body))

                g.add((body, AO.annotationType, URIRef(type_uri)))
                if btype is not None:
                    g.add((body, RDF.type, btype))
                return body

            value_type_mapping = {
                "evolving": AO.EvolvingValuesAnnotationType,
                "contrasting": AO.ContrastingValuesAnnotationType,
                "predefined": AO.PredefinedValuesAnnotationType
            }
            # Build body according to content type
            if a.type.mimetype == 'text/x-advene-keyword-list':
                keywords = a.content.parsed()

                def get_keyword_uri(kw):
                    uri = keywords.get(kw, 'ontology_uri')
                    val = URIRef(uri) if uri else Literal(kw)
                    return val

                for typedvalues in keywords_to_struct(list(keywords)):
                    if typedvalues is None:
                        logger.warning("Empty typedvalues for %s", keywords)
                        continue
                    body = new_body(value_type_mapping[typedvalues.type])

                    if typedvalues.type == "predefined":
                        for kw in typedvalues.values:
                            g.add( (body, AO.annotationValue, get_keyword_uri(kw)) )
                    else:
                        # Generate a sequence for contrasting/evolving values.
                        seq = BNode()
                        Collection(g, seq, [ get_keyword_uri(kw) for kw in typedvalues.values ])
                        g.add( (body, AO.annotationValueSequence, seq) )

                # Attach comment to the last body
                if keywords.get_comment():
                    g.add( (body, RDFS.comment, Literal(keywords.get_comment())) )

            else:
                body = new_body()
                g.add((body, RDF.type, OA.TextualBody))
                g.add((body, RDF.value, Literal(a.content.data)))

            target = BNode()
            g.add((anode, OA.hasTarget, target))

            g.add((target, OA.hasSource, URIRef(media_uri)))

            selector = BNode()
            g.add((target, OA.hasSelector, selector))

            g.add((selector, RDF.type, OA.FragmentSelector))
            g.add((selector, DCTERMS.conformsTo, URIRef("http://www.w3.org/TR/media-frags/")))
            g.add((selector, RDF.value, Literal("t={},{}".format(helper.format_time_reference(a.fragment.begin),
                                                                 helper.format_time_reference(a.fragment.end)))))

        g.add((page, RDF.type, AS.OrderedCollectionPage))
        g.add((page, AS.items, pageItems))
        g.add((page, AS.startIndex, Literal(0, datatype=XSD.nonNegativeInteger)))
        if filename is None:
            return g
        else:
            g.serialize(destination=filename, format=self.format)
            logger.info(_("Wrote %(count)d triples to %(filename)s"), { "count": len(g),
                                                                        "filename": filename })
            return ""

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
