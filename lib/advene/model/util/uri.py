#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2016 Olivier Aubert <contact@olivieraubert.net>
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

import os
import re
import sys
import urllib.request, urllib.parse, urllib.error
from urllib.request import urlopen
import urllib.parse

_fs_encoding = sys.getfilesystemencoding()
# In some cases, sys.getfilesystemencoding returns None. And if the
# system is misconfigured, it will return ANSI_X3.4-1968
# (apparently). In these cases, fallback to a sensible default value
if _fs_encoding in ('ascii', 'ANSI_X3.4-1968', None):
    _fs_encoding='utf-8'

urljoin = urllib.parse.urljoin

def push(uri, id_):
    return "%s#%s" % (uri, id_)

def pop(uri):
    sharp = uri.rfind('#')
    slash = uri.rfind('/')
    cut = max(sharp, slash)
    return uri[:cut], uri[(cut+1):]

def fragment(uri):
    sharp = uri.rfind('#')
    if sharp>0: return uri[(sharp+1):]
    else: return ''

def no_fragment(uri):
    sharp = uri.rfind('#')
    if sharp>0: return uri[:sharp]
    else: return uri

def open(uri):
    return urlopen(uri)

def normalize_filename(name):
    """Normalize filename for interaction with the filesystem.

    This means :

    - in win32, massage windows drive notation in a more URI-compatible syntax

    - on systems where os.path.supports_unicode_filename (win32),
    native fs API want to get unicode strings. On other ones, encode
    pathnames with an apppropriate encoding (utf-8 usually).
    """
    if name.startswith('file:///'):
        name = name[7:]

    if re.match('|/', name) or re.match('[a-zA-Z]:', name):
        # Windows drive: notation. Convert it from
        # a more URI-compatible syntax
        name=urllib.request.url2pathname(name)

    if not isinstance(name, str):
        # We should only have utf8 encoded strings internally
        name = name.decode('utf-8')

    return name
