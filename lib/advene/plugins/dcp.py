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
import urllib

import advene.core.config as config
import advene.util.helper as helper
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(DCPImporter)
    return True

timestamp_re = re.compile('(\d\d):(\d\d):(\d\d):(\d\d)')

# Column -> (type, attr) mapping.
#
type_mapping = {
    u'Inquadratura'                      : (u'Inquadratura', 'num'),
    u'Descrizione inquadratura'          : (u'Inquadratura', 'descrizione'),
    u'Piani/Immagini'                    : (u'Inquadratura', 'piani_immagini'),
    u'Ampiezza temporale inquadratura'   : (u'Inquadratura', 'ampiezza_temporale'),

    u'Ampiezza temporale raccordo'       : (u'Raccordo'    , 'ampiezza_temporale'),
    u'Raccordi di contenuto'             : (u'Raccordo'    , 'contenuto'),
    u'Raccordi spaziali'                 : (u'Raccordo'    , 'spaziali'),
    u'Raccordi tecnici'                  : (u'Raccordo'    , 'tecnici'),
    u'Raccordi temporali'                : (u'Raccordo'    , 'temporali'),

    u'Grande unit\xe0'                   : (u'Grande_unita', 'num'),
    u'Ampiezza temporale grande unit\xe0': (u'Grande_unita', 'ampiezza_temporale'),
    u'Descrizione grande unit\xe0'       : (u'Grande_unita', 'descrizione'),
    u'Transizioni fra grandi unit\xe0'   : (u'Grande_unita', 'transizioni_fra'),

    u'Sequenza'                          : (u'Sequenza'    , 'num'),
    u'Ampiezza temporale sequenza'       : (u'Sequenza'    , 'ampiezza_temporale'),
    u'Descrizione sequenza'              : (u'Sequenza'    , 'descrizione'),
    u'Transizioni fra sequenze'          : (u'Sequenza'    , 'transizioni_fra'),
    }

class DCPImporter(GenericImporter):
    name = _("DCP importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if 'dcp' in fname or 'colonne' in fname:
            return 80
        elif fname.endswith('.tsv') or fname.endswith('.txt') or fname.endswith('.csv'):
            return 70
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        if self.package is None:
            self.init_package()
        self.schema=self.create_schema('DCP')

        # Get row count
        f=open(filename, 'rU')
        rows=csv.reader(f, 'excel-tab')
        self.row_count = sum(1 for row in rows)
        f.close()
        del rows

        print "Converting ", self.row_count, " records"
        # Conversion
        f=open(filename, 'rU')
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
            t=( ((long(h) * 60 + long(m)) * 60) + long(s) ) * 1000 + long(f) * (1000 / config.data.preferences['default-fps'])
        else:
            t=0
        return t

    def iterator(self, rows):
        progress=0.02
        incr = 1.0 / self.row_count
        # Column cache: store (in_time, content) for each column
        column_cache = {}
        # Row cache: for coalesced types, store
        # (in_time, content) indexed by DCP type
        row_cache = {}
        for row in rows:
            row_cache.clear()
            self.progress(progress, _("Converting #%(num)d / %(count)d") % { 'num': rows.line_num,
                                                                             'count': self.row_count})
            progress += incr
            t = self.str2time(row[1])
            for (label, tc, value) in itertools.izip(self.labels[2::2], row[2::2], row[3::2]):
                label = unicode(label, 'mac_roman')

                if tc == 'IN':
                    # Store into column_cache
                    column_cache[label]=( t, unicode(value, 'mac_roman') )
                elif tc == 'OUT':
                    (begin, content) = column_cache.get(label, (0, 'OUT without IN'))
                    if label in type_mapping:
                        # Coalesced type
                        row_cache[label] = (begin, content)
                        continue
                    at = self.label2type.get(label)
                    if at is None:
                        at = self.label2type[label] = self.create_annotation_type(self.schema, helper.title2id(label), title=label)
                    yield {
                        'begin': begin,
                        'end': t,
                        'content': content,
                        'type': at,
                        }
            # Process row_cache
            output = {}
            for dcp_type, data in row_cache.iteritems():
                label, attr = type_mapping[dcp_type]
                begin, content = data
                at = self.label2type.get(label)
                if at is None:
                    at = self.label2type[label] = self.create_annotation_type(self.schema, helper.title2id(label), title=label, mimetype='application/x-advene-structured')
                    at.setMetaData(config.data.namespace, 'representation', 'here/content/parsed/num')
                info = output.setdefault(at, { 'begin': begin, 'content': [] })
                #if info[begin] != begin:
                #    # FIXME: consistency check on begin time. What to do here???
                info['content'].append('%s=%s' % (attr, content.replace('\n', ' -- ')))
            for at, info in output.iteritems():
                yield {
                    'begin': info['begin'],
                    'end': t,
                    'content': "\n".join(info['content']),
                    'type': at,
                    }
        self.progress(1.0)

