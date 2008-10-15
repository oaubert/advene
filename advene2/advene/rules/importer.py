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

from advene.util.importer import GenericImporter, register
import urllib
import advene.core.config as config
import time
import os.path

from gettext import gettext as _

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
        end=start
        id_="Traces"
        schema=self.package.get(id_)
        for e in f:
            type_ = e['event_name']
            type = self.package.get(type_)
            if (type is None):
                #Annotation type creation
                self.package._idgenerator.add(type_)
                at=schema.create_annotation_type(id=type_)
                at.title=type_
                at.mimetype='application/x-advene-structured'
                at.color=self.package._color_palette.next()
                at.element_color='here/tag_color'

            d={
                'type': at,
                'begin': e['timestamp'] - start,
                'duration': 50,
                'timestamp': e['timestamp'],
                'content': '',
            }
            if e.has_key('content'):
                d['content']=e['content']+'\nposition='+str(e['movietime'])+'\n'
            else:
                d['content']='position='+str(e['movietime'])+'\n'
            if end<e['timestamp']+50:
                end=e['timestamp']+50
            yield d
        #fix package duration
        self.package.cached_duration=end-start

    def process_file(self, filename):
        if self.package is None:
            self.init_package(filename='event_history.xml', annotationtypeid='event')
        id_="Traces"
        title_="Traces"
        schema=self.package.get(id_)
        if schema is None:
            self.package._idgenerator.add(id_)
            schema=self.package.create_schema(id=id_)
            schema.title=title_
        self.convert(self.iterator(filename))
        return self.package
register(EventHistoryImporter)
