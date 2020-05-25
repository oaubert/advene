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

# WebAnnotation importer

name="WebAnnotation importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import json
import os

import advene.core.config as config
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(WebAnnotationImporter)
    return True

class WebAnnotationImporter(GenericImporter):
    name = _("WebAnnotation importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in [ '.jsonld', '.json' ]:
            return 90
        return 0

    def process_file(self, filename, dest=None):
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
        except ValueError:
            logger.error("Cannot parse source data")
            return self.package
        p, at = self.init_package(filename=dest)
        p.setMetaData(config.data.namespace_prefix['dc'],
                      'description',
                      _("Converted from %s") % filename)

        if data.get('type') == 'AnnotationCollection':
            items = data.get('first', {}).get('items', [])
            #label = data.get('label', 'No label')
        elif data.get('items'):
            items = data.get('items')
        else:
            items = []

        self.convert(self.iterator(items))
        self.progress(1.0)
        return self.package

    def iterator(self, items):
        """Iterate through the loaded jsonld items
        """
        def parse_mediafragment(target):
            try:
                media = target['source']
                selector = target['selector']
            except KeyError:
                logger.debug("Invalid target")
                return None
            if selector.get('@type') != "FragmentSelector":
                logger.debug("No mediafragment selector")
                return None
            # If there are advene:begin/advene:end properties, use
            # them.
            if selector.get('advene:begin') is not None and selector.get('advene:end') is not None:
                begin = selector.get('advene:begin')
                end = selector.get('advene:end')
            else:
                # Else parse the MediaFragment syntax
                val = selector.get('value', "")
                if not val.startswith('t='):
                    logger.debug("Invalid mediafragment value %s", val)
                    return None
                begin, end = val[2:].split(',')
                begin = int(float(begin) * 1000)
                end = int(float(end) * 1000)
            return media, begin, end

        progress = 0.01
        step = 1.0 / len(items)
        self.progress(progress, "Starting conversion")
        for i in items:
            if not (i.get('@type') == 'Annotation'
                    or i.get('type') == 'Annotation'):
                logger.debug("Not an annotation")
                continue
            # Check that it is a media annotation
            fragment = parse_mediafragment(i.get('target'))
            if fragment is None:
                continue
            el = { 'media': fragment[0],
                   'begin': fragment[1],
                   'end': fragment[2] }
            if i.get('advene:type'):
                # A type is defined. Use it. Else we will fallback on
                # default type.
                el['type'] = i.get('advene:type')
            if i.get('creator'):
                el['author'] = i.get('creator').get('@id')
            body = i.get('body')
            # body can be either an object or a list of objects
            if body is not None:
                if isinstance(body, list):
                    textbody = [ b for b in body if b.get('@type') in ('Text', 'TextualBody', 'oa:TextualBody') ]
                    if len(textbody) == 1:
                        # Found 1 Text body. Use it.
                        el['content'] = textbody[0].get('value', '')
                        yield el
                    else:
                        # Cannot find a single text body. Dump the JSON of the whole list
                        el['content'] = json.dumps(body)
                        yield el
                else:
                    if body.get('@type') in ('Text', 'TextualBody', 'oa:TextualBody'):
                        el['content'] = body.get('value')
                        yield el
                    else:
                        # Fallback for other body types
                        el['content'] = json.dumps(body)
                        yield el
            yield el
            progress += step
            self.progress(progress)
        self.progress(1.0)
