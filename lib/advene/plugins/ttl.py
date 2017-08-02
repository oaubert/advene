#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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

name="TurTLe (RDF) importer"

from gettext import gettext as _

import re
import time

import advene.core.config as config
import advene.util.helper as helper
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(TTLImporter)
    return True

type_re = re.compile('\s+a\s+:(\w+)')
prop_re = re.compile(':has(\w+)\s+(.+)')
num_re = re.compile('^\d+$')

default_duration = 1000
class TTLImporter(GenericImporter):
    name = _("TurTLe (RDF) importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.ttl') or fname.endswith('.n3'):
            return 80
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        f=open(filename, 'rb')
        if self.package is None:
            self.init_package(filename=filename, schemaid='traces', annotationtypeid=None)
        self.model = None
        at = self.ensure_new_type('trace')
        at.mimetype='application/x-advene-structured'
        at.title='Trace'
        at.setMetaData(config.data.namespace, "representation", "here/content/parsed/type")
        self.convert(self.iterator(f))
        self.progress(1.0)
        return self.package

    def iterator(self, fd):
        progress=0.02
        in_list = False
        start_time = -1
        propname = ''
        data = ''
        for l in fd:
            l=str(l.strip().rstrip(";").strip(), 'latin1')
            if self.model is None:
                if '/modelLDT/' in l:
                    self.model = 'ldt'
                elif '/visu/' in l:
                    self.model = 'visu'

            m=type_re.search(l)
            if m:
                item = { 'type': m.group(1) }
                continue

            if l.startswith(')'):
                # End of list
                item[propname] = data
                in_list = False
                continue

            if in_list:
                data.append(l)
                continue

            m=prop_re.search(l)
            if m:
                propname = m.group(1).lower()
                if propname == 'id':
                    propname = 'id'
                data = m.group(2)
                if data == '(':
                    in_list = True
                    data = []
                    continue

                if num_re.match(data):
                    data = int(data)
                elif data.startswith('"') and data.endswith('"'):
                    data = data.strip('"')

                item[propname] = data

                continue

            if l.startswith('.'):
                self.progress(progress)
                progress += .05

                if start_time == -1:
                    if self.model == 'visu':
                        if item['type'] == 'RecordFilename':
                            start_time = item['begin']
                    else:
                        start_time = item['begin']
                    begin = 0
                    end = default_duration
                else:
                    begin = item['begin'] - start_time
                    #end = item['end'] - start_time
                    end = begin + default_duration

                if item['type'] == 'PresenceStart':
                    self.defaulttype.setMetaData(config.data.namespace_prefix['dc'], 'description', "Trace for %s %s on %s" % (item['surname'], item['name'], time.strftime('%F %H:%M:%S', time.localtime(item['begin'] / 1000))))

                item['_begin'] = helper.format_time_reference(item['begin'])
                item['_end'] = helper.format_time_reference(item['end'])

                yield {
                    'content': "\n".join( "%s=%s" % (k, str(item[k])) for k in sorted(item.keys())).encode('utf8'),
                    'begin': begin,
                    'end' : end,
                    }

        self.progress(1.0)

