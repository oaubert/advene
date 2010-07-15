#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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

name="DCP importer"

from gettext import gettext as _

import re
import csv
import itertools

import advene.util.helper as helper
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(DCPImporter)
    return True

timestamp_re = re.compile('(\d\d):(\d\d):(\d\d):(\d\d)')

class DCPImporter(GenericImporter):
    name = _("DCP importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.tsv') or fname.endswith('.txt') or fname.endswith('.csv'):
            return 80
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        f=open(filename, 'rU')
        if self.package is None:
            self.init_package()
        self.schema=self.create_schema('DCP')
        rows=csv.reader(f, 'excel-tab')
        self.labels = rows.next()
        self.label2type = {}
        self.convert(self.iterator(rows))
        self.progress(1.0)
        return self.package

    def str2time(self, s):
        m=timestamp_re.match(s)
        if m:
            (h, m, s, f) = m.groups()
            t=( ((long(h) * 60 + long(m)) * 60) + long(s) ) * 1000 + long(f) * 40
        else:
            t=0
        return t

    def iterator(self, rows):
        progress=0.02
        cache={}
        for row in rows:
            self.progress(progress)
            progress += .01
            t=self.str2time(row[1])
            for (label, tc, value) in itertools.izip(self.labels[2::2], row[2::2], row[3::2]):
                label = unicode(label, 'mac_roman')

                if tc == 'IN':
                    # Store into cache
                    cache[label]=( t, unicode(value, 'mac_roman') )
                elif tc == 'OUT':
                    (begin, content) = cache.get(label, (0, 'FIXME'))
                    at = self.label2type.get(label)
                    if at is None:
                        at = self.label2type[label] = self.create_annotation_type(self.schema, helper.title2id(label), title=label)
                    yield {
                        'begin': begin,
                        'end': t,
                        'content': content,
                        'type': at,
                        }
        self.progress(1.0)

