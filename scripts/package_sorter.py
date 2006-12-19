#! /usr/bin/python
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
"""Process an Advene XML package in order to get annotations ordered
by timestamp, and all other elements ordered by id.  
"""
import sys

import elementtree.ElementTree
from elementtree.ElementTree import parse, Element, ElementTree, QName
import string

def tag(name):
    """Return the namespaced tag.
    """
    return '{%s}%s' % (ns, name)

def cmp_id(a, b):
    """Compare id
    """
    return cmp(a.attrib['id'], b.attrib['id'])

def sort_id(source):
    """Sort the source Element elements along their id.

    Returns a new Element
    """
    dest=Element(source.tag)
    dest.attrib.update(source.attrib)
    
    res=[ e for e in source ]
    res.sort(cmp_id)
    
    for e in res:
        dest.append(e)
    return dest

def cmp_time(a, b):
    """Compare time
    """
    return cmp(a._begin, b._begin)

def sort_time(source):
    """Sort the source Element elements along their time (for annotations) and id (for relations).

    Returns a new Element
    """
    dest=Element(source.tag)
    dest.attrib.update(source.attrib)
    
    antag=tag('annotation')
    reltag=tag('relation')

    rel=[ e for e in source if e.tag == reltag ]
    rel.sort(cmp_id)

    an=[ e for e in source if e.tag == antag ]
    # Pre-parse begin times
    for a in an:
        f=a.find(tag('millisecond-fragment'))
        if f is not None:
            a._begin = long(f.attrib['begin'])
        else:
            print "Error: cannot find begin time for ", a.attrib['id']
            a._begin = 0
    an.sort(cmp_time)
    
    for e in an:
        dest.append(e)
    for e in rel:
        dest.append(e)

    return dest

# Namespace handling
ns='http://experience.univ-lyon1.fr/advene/ns'
elementtree.ElementTree._namespace_map[ns]=''
elementtree.ElementTree._namespace_map['http://purl.org/dc/elements/1.1/']='dc'
elementtree.ElementTree._namespace_map['http://experience.univ-lyon1.fr/advene/ns/advenetool']='advenetool'

# Hack into elementtree to generate a readable (namespace-prefix-wise)
# Advene package
def my_fixtag(tag, namespaces):
    # given a decorated tag (of the form {uri}tag), return prefixed
    # tag and namespace declaration, if any
    if isinstance(tag, QName):
        tag = tag.text
    namespace_uri, tag = string.split(tag[1:], "}", 1)
    prefix = namespaces.get(namespace_uri)
    if prefix is None:
        prefix = elementtree.ElementTree._namespace_map.get(namespace_uri)
        if prefix is None:
            prefix = "ns%d" % len(namespaces)
        namespaces[namespace_uri] = prefix
        if prefix == "xml":
            xmlns = None
        elif prefix == '':
            # Empty prefix from _namespace_map, assume it is the
            # default
            xmlns = ('xmlns', namespace_uri)
        else:
            xmlns = ("xmlns:%s" % prefix, namespace_uri)
    else:
        xmlns = None
    if prefix == '':
        return tag, xmlns
    else:
        return "%s:%s" % (prefix, tag), xmlns

# Hook into elementtree
elementtree.ElementTree.fixtag = my_fixtag

tree = parse(sys.argv[1])
source = tree.getroot()
dest=Element(source.tag)
dest.attrib.update(source.attrib)


for e in source:
    if e.tag == tag('meta') or e.tag == tag('imports'):
        dest.append(e)
    elif e.tag in [ tag(n) for n in ('queries', 'schemas', 'views') ]:
        # Sort along id
        dest.append(sort_id(e))
    elif e.tag == tag('annotations'):
        dest.append(sort_time(e))
    else:
        print "Unknown tag", e.tag

tree=ElementTree(dest)
tree.write(open(sys.argv[2], 'w'), encoding='utf-8')
