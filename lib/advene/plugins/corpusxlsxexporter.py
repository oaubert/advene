#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2024 Olivier Aubert <contact@olivieraubert.net>
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
"""Corpus XLSX export export filter.

This filter exports corpus data (cross-package) as XLSX files.
"""

name = "Corpus Xlsx exporter"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import os

import advene.core.config as config
from advene.util.exporter import GenericExporter

import advene.util.helper as helper

try:
    import openpyxl
    from openpyxl.utils.cell import get_column_letter
except ImportError:
    openpyxl = None

def register(controller=None):
    if openpyxl:
        controller.register_exporter(CorpusXlsxExporter)
    return True

class CorpusXlsxExporter(GenericExporter):
    """Corpus Xlsx Exporter
    """
    name = _("Corpus Xlsx exporter")
    extension = 'xlsx'
    mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def __init__(self, controller=None, source=None, callback=None):
        super().__init__(controller, source, callback)
        self.title = False
        package_count = len(controller.global_package.package_list)
        self.all = controller.global_package
        self.optionparser.description = _(f"Export {package_count} packages as Xlsx file.")
        self.optionparser.add_option("-t", "--title",
                                     action="store_true", dest="title", default=self.title,
                                     help=_("Use annotation type titles instead of ids"))

    @classmethod
    def is_valid_for(cls, expr):
        return expr == 'package'

    def export(self, filename=None):
        # Export a corpus as a Xlsx file
        # One sheet per package, then one annotation per line
        # One sheet per annotation type, one annotation per line

        book = openpyxl.Workbook()

        # Remove default worksheet
        book.remove(book.worksheets[0])

        # Check if titles are different
        titles = [ p.title for p in self.all.package_list ]
        use_package_titles = True

        if len(set(titles)) != len(titles):
            logger.warning(_("Some package titles are identical, use package filename as sheet name"))
            use_package_titles = False

        # Add summary worksheet
        sheet = book.create_sheet('Summary')
        sheet.append([ "alias", "title", "media", "annotation count", "annotation type count", "relation type count" ])
        for alias, p in self.controller.packages.items():
            media_uri = os.path.basename(p.getMetaData(config.data.namespace, "media_uri") or "unknown")
            sheet.append([ alias,
                           p.title,
                           media_uri,
                           len(p.annotations),
                           len(p.annotationTypes),
                           len(p.relationTypes) ])

        def save_annotations(ws, annotations):
            header = [ "id", "text", "begin", "begin_ms", "end", "end_ms", "type_id", "type_title" ]
            ws.append(header)
            for a in annotations:
                ws.append([
                    a.id,
                    self.controller.get_title(a),
                    helper.format_time_reference(a.fragment.begin),
                    a.fragment.begin,
                    helper.format_time_reference(a.fragment.end),
                    a.fragment.end,
                    a.type.id,
                    self.controller.get_title(a.type)
                ])
            # Set dimensions
            for i in range(len(header)):
                 column_letter = get_column_letter(i + 1)
                 ws.column_dimensions[column_letter].width = 10

        # Add global sheet
        sheet = book.create_sheet('Global')
        save_annotations(sheet, sorted(self.controller.global_package.annotations))

        # Create 1 sheet per package
        for alias, p in self.controller.packages.items():
            if alias == 'advene':
                continue
            sheet = book.create_sheet(alias)

            media_uri = p.getMetaData(config.data.namespace, "media_uri") or "unknown"

            save_annotations(sheet, p.annotations)

        book.save(filename)
        return filename
