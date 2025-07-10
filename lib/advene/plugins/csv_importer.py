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

# CSV importer

name="CSV importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import csv
import os

import advene.util.helper as helper
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(CSVImporter)
    return True

class CSVImporter(GenericImporter):
    """Import data from a CSV file
    """
    name = _("CSV importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in [ '.csv', '.tsv' ]:
            return 100
        return 0

    def __init__(self, *p, **kw):
        super().__init__(*p, **kw)

        # Used dialect
        self.dialect = "excel"
        self.time_column = ""
        self.end_column = ""
        self.relative = False
        self.columns = ""
        self.optionparser.add_option("-d", "--dialect",
                                     action="store", type="choice", dest="dialect", choices=csv.list_dialects(), default=self.dialect,
                                     help=_("CSV dialect"))
        self.optionparser.add_option("-t", "--time-column",
                                     action="store", type="str", dest="time_column", default=self.time_column,
                                     help=_("Name of the time column. Leave empty for first column."))
        self.optionparser.add_option("-e", "--end-column",
                                     action="store", type="str", dest="end_column", default=self.end_column,
                                     help=_("Name of the end time column. If empty, only begin time is used."))
        self.optionparser.add_option("-r", "--relative",
                                     action="store_true", dest="relative", default=self.relative,
                                     help=_("Should the timestamps be encoded relative to the first timestamp?"))
        self.optionparser.add_option("-c", "--columns",
                                     action="store", type="str", dest="columns", default=self.columns,
                                     help=_("Column names to extract, separated with ','. Empty for all columns"))

    def process_file(self, filename, dest=None):
        p, at = self.init_package(filename=dest)

        with open(filename, 'r') as f:
            rows = csv.DictReader(f, dialect=self.dialect)
            if len(rows.fieldnames) == 1:
                # Only 1 field detected, probably the dialect is wrong
                raise Exception(f"Only 1 column detected - cannot process: {rows.fieldnames[0]} - try to select the appropriate dialect {self.dialect}")
            elif len(rows.fieldnames) == 0:
                raise Exception("No column detected - cannot process")

            if not self.time_column:
                self.time_column = rows.fieldnames[0]
            if self.time_column not in rows.fieldnames:
                raise Exception(f"Begin time column {self.time_column} is not present in header:\n{', '.join(rows.fieldnames)}")

            if self.end_column and self.end_column not in rows.fieldnames:
                raise Exception(f"End time column {self.end_column} is not present in header:\n{', '.join(rows.fieldnames)}")

            if self.columns:
                columns = self.columns.split(",")
            else:
                columns = [ col
                            for col in rows.fieldnames
                            if col != self.time_column and col != self.end_column ]
            for col in columns:
                if col not in rows.fieldnames:
                    raise Exception(f"The column {col} is not present in header")
            # Create annotations for columns
            self.name2type = {}
            for col in columns:
                self.name2type[col] = self.ensure_new_type(col,
                                                           title=col,
                                                           description=_(f"{col} from {filename}"))
            self.convert(self.iterator(rows, columns))
        self.progress(1.0)
        return self.package

    def iterator(self, rows, columns):
        """Iterate through the rows
        """
        progress = 0.01
        first_timestamp = None
        previous_begin = None
        previous_row = None
        self.progress(progress, f"Starting conversion {columns}")
        for row in rows:
            progress += 0.01
            self.progress(progress)
            begin = helper.parse_time(row[self.time_column])
            if first_timestamp is None:
                first_timestamp = begin
            if self.relative:
                begin = begin - first_timestamp

            if self.end_column:
                # Simple version: we can send immediately
                end = helper.parse_time(row[self.end_column])
                if self.relative:
                    end = end - first_timestamp
                for col in columns:
                    yield {
                        'begin': begin,
                        'end': end,
                        'type': self.name2type[col],
                        'content': rows[col]
                    }
            else:
                # Complete and send previous data
                if previous_begin is not None and previous_row is not None:
                    for col in columns:
                        yield {
                            'begin': previous_begin,
                            'end': begin,
                            'type': self.name2type[col],
                            'content': previous_row[col]
                        }
                previous_begin = begin
                previous_row = row

        self.progress(1.0)
