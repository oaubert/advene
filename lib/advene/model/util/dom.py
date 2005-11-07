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
import xml.dom.ext

TEXT_NODE = xml.dom.Node.TEXT_NODE
ELEMENT_NODE = xml.dom.Node.ELEMENT_NODE

def printElementSource(element, stream):
#    doc = element._get_ownerDocument()
#    df = doc.createDocumentFragment()
#    for e in element._get_childNodes():
#        df.appendChild(e.cloneNode(True))
#    xml.dom.ext.Print(df, stream)
    for e in element._get_childNodes():
        xml.dom.ext.Print(e, stream)

def printElementText(element, stream):
    if element._get_nodeType() is TEXT_NODE:
        # Note: element._get_data() returns a unicode object
        # that happens to be in the default encoding (iso-8859-1
        # currently on my system). We encode it to utf-8 to
        # be sure to deal only with this encoding afterwards.
        stream.write(element._get_data().encode('utf-8'))
    elif element._get_nodeType() is ELEMENT_NODE:
        for e in element._get_childNodes():
            printElementText(e, stream)
