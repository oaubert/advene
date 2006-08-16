#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

from advene.util.importer import GenericImporter, register
import urllib

class EventHistoryImporter(GenericImporter):
    """Event History importer.
    """
    name=_("Event history importer")

    def __init__(self, **kw):
        super(EventHistoryImporter, self).__init__(**kw)

    def can_handle(fname):
        return fname == 'event_history'
    can_handle=staticmethod(can_handle)

    def iterator(self, f):
        start=f[0]['timestamp']
        for e in f:
            d={
                'begin': e['timestamp'] - start,
                'duration': 10,
                'timestamp': e['timestamp'],
                'content': urllib.urlencode(e),
                }
            yield d

    def process_file(self, filename):
        if self.package is None:
            self.init_package(filename='event_history.xml', annotationtypeid='event')
        self.convert(self.iterator(filename))
        return self.package

register(EventHistoryImporter)
