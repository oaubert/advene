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

# AdA RDF Exporter

name="AdA RDF exporter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from functools import lru_cache
import rdflib
from rdflib import URIRef, BNode, Literal
from rdflib.collection import Collection

import advene.core.config as config
import advene.util.helper as helper
from advene.util.exporter import GenericExporter

def register(controller=None):
    controller.register_exporter(AdARDFExporter)
    return True

# Evolving/ContrastingAnnotationType markers
TO_KW = '[TO]'
VS_KW = '[VS]'

class AdARDFExporter(GenericExporter):
    name = _("AdA RDF exporter")
    extension = 'rdf'

    # FIXME: add format option (turtle, n3, json-ld, xml...)
    def __init__(self, controller=None, source=None):
        super().__init__(controller=controller, source=source)
        self.format = "n3"
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
        RDF = rdflib.RDF
        RDFS = rdflib.RDFS
        XSD = rdflib.XSD

        # Works in source is a package or a type
        package = self.source.ownerPackage

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

        collection = BNode()
        page = URIRef("page1")
        g.add((collection, RDF.type, OA.AnnotationCollection))
        g.add((collection, RDFS.label, Literal(self.controller.get_title(self.source))))
        g.add((collection, AS.totalItems, Literal(len(self.source.annotations), datatype=XSD.nonNegativeInteger)))
        g.add((collection, AS.first, page))

        @lru_cache(maxsize=None)
        def get_user_node(username):
            unode = URIRef(username)
            g.add((unode, RDF.type, OA.Person))
            g.add((unode, OA.nick, Literal(username)))
            return unode

        pageItems = BNode()
        g.add((page, AS.items, pageItems))

        itemcollection = Collection(g, pageItems)

        for a in self.source.annotations:
            anode = URIRef(a.uri)
            itemcollection.append(anode)
            g.add((anode, RDF.type, OA.Annotation))
            g.add((anode, OA.created, Literal(a.date, datatype=XSD.dateTime)))
            g.add((anode, OA.creator, get_user_node(a.author)))

            body = BNode()
            g.add((anode, OA.body, body))

            type_uri = a.type.getMetaData(config.data.namespace, "ontology_uri")
            if not type_uri:
                logger.warn(_("Cannot determine ontology URI for type %s"), self.controller.get_title(a.type))
                type_uri = a.type.id
            g.add((body, AO.annotationType, URIRef(type_uri)))

            # Build body according to content type
            if a.content.mimetype == 'text/x-advene-keyword-list':
                g.add((body, RDF.type, AO.PredefinedValuesAnnotationType))
                keywords = a.content.parsed()
                keywords_list = list(keywords)

                def add_keyword_to_graph(kw, type_=AO.annotationValue):
                    uri = keywords.get(kw, 'ontology_uri')
                    val = URIRef(uri) if uri else Literal(kw)
                    g.add( (body, type_, val) )

                prev = None
                while keywords_list:
                    current = keywords_list.pop(0)
                    if current in (TO_KW, VS_KW):
                        if prev is None:
                            logger.error("Syntax error: %s keyword should have a value before." % current)
                            prev = None
                        elif not keywords_list:
                            logger.error("Syntax error: %s keyword should have a value after." % current)
                            prev = None
                        else:
                            if current == TO_KW:
                                add_keyword_to_graph(prev, AO.fromAnnotationValue)
                                current = keywords_list.pop(0)
                                add_keyword_to_graph(current, AO.toAnnotationValue)
                                prev = current # or None?
                            elif current == VS_KW:
                                # FIXME: how to properly encode contrasting values? Copying TO code for the moment
                                add_keyword_to_graph(prev, AO.fromAnnotationValue)
                                current = keywords_list.pop(0)
                                add_keyword_to_graph(current, AO.toAnnotationValue)
                                prev = current # or None?
                            else:
                                logger.error("This should never happen.")
                    else:
                        if prev is not None:
                            add_keyword_to_graph(prev)
                        prev = current
                # Last item
                if prev is not None:
                    add_keyword_to_graph(prev)
            else:
                g.add((body, RDF.type, OA.Text))
                g.add((body, OA.value, Literal(a.content.data)))

            target = BNode()
            g.add((anode, OA.target, target))

            g.add((target, OA.source, URIRef(package.getMetaData(config.data.namespace, "media_uri") or package.mediafile)))

            selector = BNode()
            g.add((target, OA.selector, selector))

            g.add((selector, RDF.type, OA.FragmentSelector))
            g.add((selector, OA.conformsTo, URIRef("http://www.w3.org/TR/media-frags/")))
            g.add((selector, OA.value, Literal("t={},{}".format(helper.format_time_reference(a.fragment.begin),
                                                                  helper.format_time_reference(a.fragment.end)))))

        g.add((page, RDF.type, AS.OrderedCollectionPage))
        g.add((page, AS.items, pageItems))
        g.add((page, AS.startIndex, Literal(0, datatype=XSD.nonNegativeInteger)))
        g.serialize(destination=filename, format=self.format)
        logger.info(_("Wrote %d triples to %s"), len(g), filename)
        return ""

