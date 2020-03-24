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
"""WebAnnotation JSON-LD export filter.

This filter exports data as WebAnnotation in JSON-LD format.
"""

name="WebAnnotation JSON-LD exporter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import advene.core.config as config
from advene.util.exporter import FlatJsonExporter

def register(controller=None):
    controller.register_exporter(WebAnnotationExporter)
    return True

class WebAnnotationExporter(FlatJsonExporter):
    """WebAnnotation exporter.
    """
    name = _("WebAnnotation exporter")
    extension = 'jsonld'
    mimetype = "application/json"

    def annotation_uri(self, a, media_uri):
        return a.uri

    def annotation_jsonld(self, a, media_uri):
        return {
            "@id": self.annotation_uri(a, media_uri),
            "@type": "Annotation",
            "advene:type": a.type.id,
            "advene:type_title": self.controller.get_title(a.type),
            "advene:color": self.controller.get_element_color(a),
            "created": a.date,
            "creator": {
                "@id": "local:user/%s" % a.author,
                "@type": "Person",
                "nick": a.author
            },
            "body": {
                "@type": "Text",
                "advene:mimetype": a.content.mimetype,
                "value": a.content.data,
                "advene:representation": self.controller.get_title(a),
            },
            "target": {
                "source": media_uri,
                "selector": {
                    "@type": "FragmentSelector",
                    "conformsTo": "http://www.w3.org/TR/media-frags/",
                    "value": "t=%.03f,%.03f" % (a.fragment.begin / 1000, a.fragment.end / 1000),
                    "advene:begin": a.fragment.begin,
                    "advene:end": a.fragment.end
                }
            }
        }

    def export(self, filename=None):
        # Works if source is a package or a type
        package = self.source.ownerPackage
        media_uri = package.getMetaData(config.data.namespace, "media_uri") or self.controller.get_default_media()

        data = {
            "@context": [ "http://www.w3.org/ns/anno.jsonld",
                          "http://www.w3.org/ns/ldp.jsonld",
                          {
                              "advene": "http://www.advene.org/ns/webannotation/",
                              # Ideally, we should use a random URI
                              # here (because without more
                              # information, we cannot know the actual
                              # URI of this local symbol) but it would
                              # render the export unstable.
                              "local": "http://www.advene.org/ns/_local/"
                          }
            ],
            "id": self.source.uri,
            "type": "AnnotationCollection",
            "label": self.controller.get_title(self.source),
            "first": {
                "id": "/".join((self.source.uri, "page1")),
                "type": "AnnotationPage",
                "startIndex": 0,
                "items": [ json
                           for json in ( self.annotation_jsonld(a, media_uri) for a in self.source.annotations )
                           if json is not None ]}
        }
        data["totalItems"] = len(data['first']['items'])

        return self.output(data, filename)
