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
""" HandyXml
    Make simple XML use convenient.
    Ned Batchelder, http://nedbatchelder.com
"""

import os.path, sys, types

from xml.dom import EMPTY_NAMESPACE
from xml.dom import Node
from advene.util.expat import PyExpat

__version__ = '1.1.20040127'        # History at the end of the file.
__all__ = ['path', 'xml', 'xpath']

try:
    True, False
except NameError:
    True, False = (1==1, 1==0)

# Try to use 4Suite for speed.
bDomlette = False
try:
    from Ft.Xml.Domlette import NonvalidatingReader
    bDomlette = True
except:
    pass

# Try to use the optional xml.xpath.
bXPath = False
try:
    from xml import xpath as xml_xpath
    bXPath = True
except ImportError:
    pass

#
# XML support
#

class HandyXmlWrapper:
    """This class wraps an XML element to give it convenient attribute access.

       Example::

         <element attr1='foo' attr2='bar'>
             <child attr3='baz' />
         </element>
         element.attr1 == 'foo'
         element.child.attr3 == 'baz'
    """
    def __init__(self, node):
        self.node = node

    def __getattr__(self, attr):
        if hasattr(self.node, attr):
            return getattr(self.node, attr)

        if attr[0:2] != '__':
            #print "Looking for "+attr, self.node, dir(self.node)
            if hasattr(self.node, 'hasAttribute'):
                if self.node.hasAttribute(attr):
                    return self.node.getAttribute(attr)
            elif hasattr(self.node, 'hasAttributeNS'):
                if self.node.hasAttributeNS(EMPTY_NAMESPACE, attr):
                    return self.node.getAttributeNS(EMPTY_NAMESPACE, attr)
            else:
                raise "Can't look for attributes on node?"

            els = None
            if hasattr(self.node, 'childNodes'):
                els = []
                for e in self.node.childNodes:
                    if e.nodeType == Node.ELEMENT_NODE:
                        if e.localName == attr:
                            els.append(e)
            else:
                raise "Can't look for children on node?"
            if els:
                # Save the attribute, since this could be a hasattr
                # that will be followed by getattr
                els = map(HandyXmlWrapper, els)
                if type(self.node) == types.InstanceType:
                    setattr(self.node, attr, els)
                return els

        raise AttributeError, "Couldn't find %s for node" % attr

# The path on which we look for XML files.
path = ['.']

def _findFile(filename):
    """ Find files on path.
    """
    ret = None
    searchPath = path
    # If cog is in use, then use its path as well.
    if sys.modules.has_key('cog'):
        searchPath += sys.modules['cog'].path
    # Search the directories on the path.
    for dir in searchPath:
        p = os.path.join(dir, filename)
        if os.path.exists(p):
            ret = os.path.abspath(p)
    return ret

# A dictionary from full file paths to parsed XML.
_xmlcache = {}

def xml(xmlin, forced=False):
    """ Parse some XML.
        Argument xmlin can be a string, the filename of some XML;
        or an open file, from which xml is read.
        forced to True to skip caching check
        The return value is the parsed XML as DOM nodes.
    """

    filename = None

    # A string argument is a file name.
    if isinstance(xmlin, types.StringTypes):
        filename = _findFile(xmlin)
        if not filename:
            raise "Couldn't find XML to parse: %s" % xmlin

    if filename:
        if _xmlcache.has_key(filename) and not forced:
            return _xmlcache[filename]
        xmlin = open(filename)

    xmldata = xmlin.read()

    if bDomlette:
        doc = NonvalidatingReader.parseString(xmldata, filename or ' ')
    else:
        doc = PyExpat.Reader().fromString(xmldata)

    parsedxml = HandyXmlWrapper(doc.documentElement)

    if filename:
        _xmlcache[filename] = parsedxml

    return parsedxml

if bXPath:
    def xpath(input, expr):
        """ Evaluate the xpath expression against the input XML.
        """
        if isinstance(input, types.StringTypes) or hasattr(input, 'read'):
            # If input is a filename or an open file, then parse the XML.
            input = xml(input)
        return map(HandyXmlWrapper, xml_xpath.Evaluate(expr, input))

else:
    def xpath(input, expr):
        raise "The xml.xpath module is not installed! Get it from http://pyxml.sourceforge.net/"

# History:
# 1.0.20040125  First version.
# 1.1.20040127  xml.xpath is an optional module.  Be forgiving if it is absent.
#               xml() and xpath() can now take an open file as well as a file name.
