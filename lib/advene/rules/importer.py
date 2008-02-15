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
import advene.core.config as config
import time

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
        start=f[0]['timestamp']*1000
	end=start
	# bad timestamps : s instead of ms
	id_="Traces"
	title_="Traces"
        schema=self.package.get_element_by_id(id_)
	if (schema is None):
	    #schema creation
            self.package._idgenerator.add(id_)
  	    schema=self.package.createSchema(ident=id_)
            schema.author=config.data.userid
            schema.date=time.strftime("%Y-%m-%d")
            schema.title=title_
            self.package.schemas.append(schema)
        for e in f:
	    type_ = e['event_name']
	    type = self.package.get_element_by_id(type_)
	    if (type is None):
		#Annotation type creation
		self.package._idgenerator.add(type_)
                type=schema.createAnnotationType(
                    ident=type_)
                type.author=config.data.userid
                type.date=time.strftime("%Y-%m-%d")
                type.title=type_
                type.mimetype='application/x-advene-structured'
                type.setMetaData(config.data.namespace, 'color', self.package._color_palette.next())
                type.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
            	schema.annotationTypes.append(type)		
		
	    d={
	        'type': type,
                'begin': e['timestamp']*1000 - start,
                'duration': 50,
                'timestamp': e['timestamp']*1000,
                'content': '',
            }
	    if e.has_key('content'):
		d['content']=e['content']+'position='+str(e['movietime'])+'\n'
	    else:
		d['content']='position='+str(e['movietime'])+'\n'
	    if end<e['timestamp']*1000+50:
		end=e['timestamp']*1000+50
            yield d
        #fix package duration
	self.package.cached_duration=end-start
	
    def process_file(self, filename):
        if self.package is None:
            self.init_package(filename='event_history.xml', annotationtypeid='event')
        self.convert(self.iterator(filename))
        return self.package

register(EventHistoryImporter)
