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

import io
import json

import advene.core.config as config
from advene.util.exporter import GenericExporter, CustomJSONEncoder

def register(controller=None):
    controller.register_exporter(WebAnnotationExporter)
    return True

class WebAnnotationExporter(GenericExporter):
    """WebAnnotation exporter.
    """
    name = _("WebAnnotation exporter")
    extension = 'jsonld'

    @classmethod
    def is_valid_for(cls, expr):
        """Is the template valid for different types of sources.

        expr is either "package" or "annotation-type" or "annotation-container".
        """
        return expr in ('package', 'annotation-type', 'annotation-container')

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
                "@id": a.author,
                "@type": "Person",
            "nick": a.author
            },
            "body": {
                "@type": "Text",
                "advene:mimetype": a.content.mimetype,
                "value": a.content.data
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
        media_uri = package.getMetaData(config.data.namespace, "media_uri") or package.mediafile or "media_uri"

        data = {
            "@context": [ "http://www.w3.org/ns/anno.jsonld",
                          "http://www.w3.org/ns/ldp.jsonld",
                          {
                              "advene": "http://www.advene.org/ns/webannotation.jsonld"
                          }
            ],
            "id": self.source.uri,
            "type": "AnnotationCollection",
            "label": self.controller.get_title(self.source),
            "first": {
                "id": "/".join((self.source.uri, "page1")),
                "type": "AnnotationPage",
                "startIndex": 0,
                "items": [ self.annotation_jsonld(a, media_uri)
                           for a in self.source.annotations ] }
        }

        if filename is None:
            return data
        else:
            with (filename if isinstance(filename, io.TextIOBase) else open(filename, 'w')) as fd:
                json.dump(data, fd, skipkeys=True, ensure_ascii=False, sort_keys=True, indent=4, cls=CustomJSONEncoder)
            return ""
