#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2025 Olivier Aubert <contact@olivieraubert.net>
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
"""ELAN export filter.

This filter exports Advene data as ELAN EAG
"""

name="ELAN exporter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import xml.etree.ElementTree as ET

import advene.core.config as config
from advene.util.exporter import GenericExporter

def register(controller=None):
    controller.register_exporter(ELANExporter)
    return True

class ELANExporter(GenericExporter):
    """ELAN Exporter
    """
    name = _("ELAN exporter")
    extension = 'eaf'
    mimetype = "application/xml"

    def __init__(self, controller=None, source=None, callback=None):
        super().__init__(controller, source, callback)

    def export(self, filename=None):
        package = self.source.ownerPackage
        media_uri = package.getMetaData(config.data.namespace, "media_uri") or self.controller.get_default_media()

        def h(tagname: str, attribs: dict[str, str] = None, children: list = None) -> ET.Element:
            """Create an XML element with the given tag name, attributes, and child elements or text.

            Parameters:
            - tagname: The name of the XML tag.
            - attribs: A dictionary of attributes.
            - children: A list of strings or ET.Element objects to be added as children.

            Returns:
            - An ElementTree Element.
            """
            if attribs is None:
                attribs = dict()
            if children is None:
                children = []
            element = ET.Element(tagname, attrib=attribs)

            for child in children:
                if isinstance(child, ET.Element):
                    element.append(child)
                elif isinstance(child, str):
                    if element.text is None:
                        element.text = child
                    else:
                        # Append string to last child's tail if available
                        if len(element):
                            if element[-1].tail is None:
                                element[-1].tail = child
                            else:
                                element[-1].tail += child
                        else:
                            element.text += child
                else:
                    raise TypeError(f"Child must be ET.Element or str, got {type(child)}")

            return element

        # Time slots are defined with their timestamp
        begins = ( a.fragment.begin for a in package.annotations )
        ends = ( a.fragment.end for a in package.annotations )
        timestamps = list(sorted([ *begins, *ends ]))

        tiers = [
            h('TIER', {
                'LINGUISTIC_TYPE_REF': "speech",
                'TIER_ID': at.id
            }, [
                h('ANNOTATION', {}, [
                    h('ALIGNABLE_ANNOTATION', {
                        'ANNOTATION_ID': a.id,
                        'TIME_SLOT_REF1': f"ts{a.fragment.begin}",
                        'TIME_SLOT_REF2': f"ts{a.fragment.end}"
                    },
                      [ h('ANNOTATION_VALUE',
                          {},
                          [ a.content.data ])
                       ])
                    ]
                  )
                for a in sorted(at.annotations)
            ])
            for at in package.annotationTypes
        ]

        root = h('ANNOTATION_DOCUMENT', {
            'AUTHOR': package.author,
            'DATE': package.date,
            'FORMAT': '3.0',
            'VERSION': '3.0',
            'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
            'xsi:noNamespaceSchemaLocation': "http://www.mpi.nl/tools/elan/EAFv3.0.xsd"
        }, [
            h('HEADER', {
                'MEDIA_FILE': "",
                'TIME_UNITS': 'milliseconds'
            }, [
                h('MEDIA_DESCRIPTOR', { 'MEDIA_URL': media_uri,
                                        'MIME_TYPE': "video/mp4"
                                       })
            ]),
            h('TIME_ORDER', {}, [
                h('TIME_SLOT', {
                    'TIME_SLOT_ID': f"ts{timestamp}",
                    'TIME_VALUE': str(timestamp)
                })
                for timestamp in timestamps
            ]),
            *tiers,
            h('LINGUISTIC_TYPE', {
                'GRAPHIC_REFERENCES': "false",
                'LINGUISTIC_TYPE_ID': "speech",
                'TIME_ALIGNABLE': "true"
            })
        ])
        ET.indent(root)
        tree = ET.ElementTree(root)
        tree.write(filename, encoding='utf-8', xml_declaration=True)
