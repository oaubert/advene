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
from xml.dom.ext.reader import BASIC_RESOLVER


def push(uri, id):
    return "%s#%s" % (uri,id)

def pop(uri):
    sharp = uri.rfind('#')
    slash = uri.rfind('/')
    cut = max(sharp,slash)
    return uri[:cut],uri[(cut+1):]

def fragment(uri):
    sharp = uri.rfind('#')
    if sharp>0: return uri[(sharp+1):]
    else: return ''

def no_fragment(uri):
    sharp = uri.rfind('#')
    if sharp>0: return uri[:sharp]
    else: return uri

def open(uri):
    return BASIC_RESOLVER.resolve(uri, base='')
