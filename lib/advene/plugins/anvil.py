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

# Anvil importer.

name="Anvil importer"

import re
import sets

import advene.core.config as config
from advene.util.importer import GenericImporter
import advene.util.ElementTree as ET

def register(controller=None):
    print "Registering AnvilImporter"
    controller.register_importer(AnvilImporter)
    return True

class AnvilImporter(GenericImporter):
    name = _("Anvil importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.endswith('.anvil'):
            return 100
        elif fname.endswith('.xml'):
            return 30
        return 0
    can_handle=staticmethod(can_handle)
    
    def process_file(self, filename):
        f=open(filename, 'r')
        tree=ET.parse(f)
        root=tree.getroot()

        p, at=self.init_package(filename=filename,
                                schemaid='anvil', annotationtypeid=None)
        self.convert(self.iterator(root))
        self.progress(1.0)
        return self.package
        
    def iterator(self, root):
        schema=self.package.get_element_by_id('anvil')
        if root.tag != 'annotation':
            print "Invalid Anvil file format: ", root.tag
            return
        
        progress=0.01
        self.progress(progress)
        l=root.findall('.//track')
        type_incr=1.0/len(l)
        for track in l:
            at=self.create_annotation_type (schema, track.attrib['name'])
            self.progress(value=progress, label="Converting " + at.id)
            attribnames=sets.Set()
            elements=track.findall('.//el')
            el_incr=type_incr / len(elements)
            for el in elements:
                progress += el_incr
                self.progress(progress)
                content="\n".join( [ "%s=%s" % (a.attrib['name'], a.text)
                                     for a in el.findall('attribute') ] )
                attribnames.update([ a.attrib['name'] for a in el.findall('attribute') ])
                yield {
                    'type': at,
                    'content': content,
                    'begin': long(float(el.attrib['start']) * 1000),
                    'end': long(float(el.attrib['end']) * 1000),
                    }
                if len(attribnames) == 1:
                    n=list(attribnames)[0]
                    # Only 1 attribute name. Define an appropriate
                    # representation for the type.
                    at.setMetaData(config.data.namespace, 'representation', 'here/content/parsed/' + n)
        self.progress(1.0)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = AnvilImporter()

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    print "Converting %s to %s using %s" % (fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    print i.statistics_formatted()
