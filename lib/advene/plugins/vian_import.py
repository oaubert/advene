#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2020 Olivier Aubert <contact@olivieraubert.net>
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

# VIAN importer

name="VIAN importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import json
import os

import advene.core.config as config
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(VIANImporter)
    return True

class VIANImporter(GenericImporter):
    """Import a VIAN file.
    """
    name = _("VIAN importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in [ '.eext' ]:
            return 90
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        with open(filename, 'r') as f:
            vian = json.load(f)
        p, at = self.init_package(filename=dest)
        p.setMetaData(config.data.namespace_prefix['dc'],
                      'description',
                      _("Converted from %s") % filename)
        self.convert(self.iterator(vian))
        self.progress(1.0)
        return self.package

    def iterator(self, vian):
        """Iterate through the loaded JSON
        """
        progress=0.01
        self.progress(progress, "Starting conversion")

        self.package.setMedia(vian['movie_descriptor']['movie_path'])
        self.package.setMetaData (config.data.namespace, "duration", str(vian['movie_descriptor']['duration']))

        incr = 0.05
        ntypes = len(vian['segmentation']) + len(vian['experiments'])
        if ntypes > 0:
            incr = 1 / ntypes

        segment_cache = {}
        # Map segments to annotations and keep a dict of segments
        for segmentation in vian['segmentation']:
            progress += incr
            self.progress(progress, f"Converting segmentation {segmentation['name']}")
            new_atype = self.ensure_new_type(
                segmentation['unique_id'],
                title = segmentation['name'])
            # FIXME: should get it from first segment?
            new_atype.mimetype = 'text/plain'
            new_atype.setMetaData(config.data.namespace, "description",
                                  segmentation['notes'])

            for segment in segmentation['segments']:
                an = {
                    "type": new_atype,
                    "begin": segment['start_ms'],
                    "end": segment['end_ms'],
                    "id": segment['unique_id'],
                    # FIXME: we lose the segment['name'] here
                    "content": segment['annotation_body'][0]['content'],
                }
                segment_cache[an['id']] = an
                yield an

        # Map classification results to annotations
        for expe in vian['experiments']:
            progress += incr
            self.progress(progress, f"Converting experiment {expe['name']}")
            new_atype = self.ensure_new_type(
                expe['unique_id'],
                title = expe['name'])
            new_atype.mimetype = 'text/x-advene-keyword-list'

            for result in expe['classification_results']:
                an = segment_cache.get(result['target'])
                if an is None:
                    logger.warn("Cannot find segment for %s", result['target'])
                else:
                    yield {
                        "type": new_atype,
                        "begin": an['begin'],
                        "end": an['end'],
                        # FIXME: how to dereference keyword information?
                        "content": result['keyword'],
                    }

        self.progress(1.0)
