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

class AdARDFExporter(GenericExporter):
    name = _("AdA RDF exporter")
    extension = 'rdf'

    # FIXME: add format option (turtle, n3, json-ld, xml...)

    @classmethod
    def is_valid_for(cls, expr):
        """Is the template valid for different types of sources.

        expr is either "package" or "annotation-type" or "annotation-container".
        """
        return expr in ('package', 'annotation-type', 'annotation-container')

    def export(self, filename):
        RDF = rdflib.RDF
        RDFS = rdflib.RDFS
        XSD = rdflib.XSD

        # FIXME: do some validity checks: presence of ontology_uri / media_uri metadata

        # Works in source is a package or a type
        package = self.source.ownerPackage

        # Get the namespace from the package metdata
        ontology = package.getMetaData(config.data.namespace, "ontology_uri")
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

            if a.content.mimetype == 'text/x-advene-keyword-list':
                g.add((body, RDF.type, AO.PredefinedValuesAnnotationType))
                g.add((body, AO.annotationType, URIRef(a.type.getMetaData(config.data.namespace, "ontology_uri"))))
                for v in a.content.parsed():
                    # FIXME: handle [TO] and [VS] values
                    g.add((body, AO.annotationValue, Literal(v)))
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
        g.serialize(destination=filename, format='turtle')
