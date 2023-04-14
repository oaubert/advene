#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2023 Olivier Aubert <contact@olivieraubert.net>
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
"""OTranscribe export filter.

This filter exports data as a Otranscribe file.
"""

name="OTranscribe exporter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import os

import advene.core.config as config
from advene.util.exporter import FlatJsonExporter
import advene.util.helper as helper

def register(controller=None):
    controller.register_exporter(OTRExporter)
    return True

class OTRExporter(FlatJsonExporter):
    """OTR exporter.
    """
    name = _("OTR exporter")
    extension = 'otr'
    mimetype = "application/json"

    def export(self, filename=None):
        # Works if source is a package or a type
        package = self.source.ownerPackage
        media_uri = package.getMetaData(config.data.namespace, "media_uri") or self.controller.get_default_media()

        data = {
            "text": "\n".join(f"""<p><span class="timestamp" data-timestamp="{a.fragment.begin / 1000}">{helper.format_time_reference(a.fragment.begin)}</span>{ a.content.data }</p>""" for a in sorted(self.source.annotations)),
            "media": os.path.basename(media_uri),
            "media-time": self.controller.cached_duration / 1000
        }
        return self.output(data, filename)
