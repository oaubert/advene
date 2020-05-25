#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2018 Olivier Aubert <contact@olivieraubert.net>
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
"""Generic helper functions without dependencies on advene modules.
"""

import logging
logger = logging.getLogger(__name__)

import datetime
import functools
import json
from pathlib import Path
try:
    from hashlib import md5, sha256
except ImportError:
    from md5 import md5
import os
import re
import sys
import urllib.request
from urllib.parse import urlparse, unquote
from urllib.request import urlopen
import urllib.error
import unicodedata

from gettext import gettext as _

class chars:
    ellipsis=b'\\u2026'.decode('unicode_escape')
    arrow_from=b'\\u2190'.decode('unicode_escape')
    arrow_to=b'\\u2192'.decode('unicode_escape')

def fourcc2rawcode (code):
    """VideoLan to PIL code conversion.

    Converts the FOURCC used by VideoLan into the corresponding
    rawcode specification used by the python Image module.

    @param code: the FOURCC code from VideoLan
    @type code: int or string
    @return: the corresponding PIL code
    @rtype: string
    """
    if code in('PNG', 'png'):
        return 'PNG'

    if code == 'video/x-raw-rgb':
        return 'BGRX'

    conv = {
        'RV32' : 'BGRX',
        'png ' : 'PNG',
        ' gnp' : 'PNG', # On PPC-MacOS X
        }
    if isinstance(code, int):
        fourcc = "%c%c%c%c" % (code & 0xff,
                               code >> 8 & 0xff,
                               code >> 16 & 0xff,
                               code >> 24)
    else:
        fourcc=code
    try:
        ret=conv[fourcc]
    except KeyError:
        ret=None
    return ret

class TitledElement:
    """Dummy element, to accomodate the get_title method.
    """
    def __init__(self, value=None, title=""):
        self.value=value
        self.title=title

class TypedUnicode(str):
    """Unicode string with a mimetype attribute.
    """
    def __new__(cls, value=""):
        s=str.__new__(cls, value)
        s.contenttype='text/plain'
        return s

class TypedString(bytes):
    """Bytes with a mimetype attribute.
    """
    def __new__(cls, value=""):
        s=bytes.__new__(cls, value)
        s.contenttype='text/plain'
        return s

def memoize(obj):
    cache = obj.cache = {}

    @functools.wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]
    return memoizer

def mediafile2id (mediafile):
    """Returns an id (with encoded /) corresponding to the mediafile.

    @param mediafile: the name of the mediafile
    @type mediafile: string
    @return: an id
    @rtype: string
    """
    m=md5(mediafile.encode('utf-8'))
    return m.hexdigest()

def mediafile_checksum(mediafile, callback=None):
    """Return the SHA256 checksum of the given mediafile.

    @param mediafile: the name of the mediafile
    @type mediafile: string
    @return: the checksum
    @rtype: string
    """
    try:
        size = os.path.getsize(mediafile)
    except FileNotFoundError:
        logger.error("Cannot get size of file %s", mediafile)
        return None

    if callback:
        callback(0, _("Computing checksum for %s") % mediafile)
    h = sha256()
    with open(mediafile, 'rb', buffering=0) as f:
        for b in iter(lambda : f.read(128*1024), b''):
            h.update(b)
            if callback and callback(progress=f.tell() / size) is False:
                return None
    return h.hexdigest()

def package2id (p):
    """Return the id of the package's mediafile.

    Return the id (with encoded /) corresponding to the mediafile
    defined in the package. Returns "undefined" if no mediafile is
    defined.

    @param p: the package
    @type p: advene.Package

    @return: the corresponding id
    @rtype: string
    """
    mediafile = p.media
    if mediafile is not None and mediafile != "":
        return mediafile2id (mediafile)
    else:
        return "undefined"

normalized_re=re.compile(r'LATIN (SMALL|CAPITAL) LETTER (\w)')
valid_re=re.compile(r'[a-zA-Z0-9_]')
extended_valid_re=re.compile(r'[ -@a-zA-Z0-9_]')

def unaccent(t):
    """Remove accents from a string.
    """
    t = str(t)
    res = []
    for c in t:
        if not extended_valid_re.match(c):
            # Try to normalize
            m = normalized_re.search(unicodedata.name(c, ' '))
            if m:
                c = m.group(2)
                if m.group(1) == 'SMALL':
                    c = c.lower()
            else:
                c = ' '
        res.append(c)
    return "".join(res)

def title2id(t):
    """Convert a unicode title to a valid id.

    It will replace spaces by underscores, accented chars by their
    unaccented equivalent, and other characters by -
    """
    (text, count) = re.subn(r'\s', '_', unaccent(t))
    (text, count) = re.subn(r'[^\w]', '-', text)
    return text

def unescape_string(s):
    """Unescape special characters.

    \n or %n for newline
    \t or %t for tab
    """
    return s.replace('\\n', '\n').replace('%n', '\n').replace('\\t', '\t').replace('%t', '\t')

SPACE_REGEXP = re.compile(r'[^\w\d_]+', re.UNICODE)
COMMA_REGEXP = re.compile(r'\s*,\s*', re.UNICODE)
COMPLETION_SIZE_LIMIT = 1
def get_keyword_list(s):
    """Return the keywords defined in the given string.
    """
    if not s:
        return []
    regexp = SPACE_REGEXP
    if ',' in s:
        regexp = COMMA_REGEXP
    return [ w for w in regexp.split(s) if len(w) >= COMPLETION_SIZE_LIMIT ]

def median(values):
    """Return the median value of a list of values.
    """
    if not values:
        return None
    values = sorted(values)
    n = len(values)
    if n % 2:
        return values[int((n + 1) / 2) - 1]
    else:
        return sum(values[int(n / 2) - 1:int(n / 2) + 1]) / 2.0

def get_timestamp():
    """Return a formatted timestamp for the current date.
    """
    return datetime.datetime.now().replace(microsecond=0).isoformat()

def get_id(source, id_):
    """Return the element whose id is id_ in source.
    """
    l=[ e for e in source if e.id == id_ ]
    if len(l) != 1:
        return None
    else:
        return l[0]

# Valid TALES expression check

# Root elements
root_elements = ('here', 'nothing', 'default', 'options', 'repeat', 'request',
                 # Root elements available in STBVs
                 'package', 'packages', 'annotation', 'relation',
                 'player', 'event', 'view',
                 # For UserEvent:
                 'identifier',
                 # Root elements available in queries
                 'element',
                 )

# Path elements followed by any syntax
path_any_re = re.compile('^(string|python):')

# Path elements followed by a TALES expression
path_tales_re = re.compile('^(exists|not|nocall):(.+)')

def is_valid_tales(expr):
    """Return True if the expression looks like a valid TALES expression

    @param expr: the expression to check.
    @type expr: string
    """
    # Empty expressions are considered valid
    if expr == "":
        return True
    if path_any_re.match(expr):
        return True
    m=path_tales_re.match(expr)
    if m:
        return is_valid_tales(expr=m.group(2))
    # Check that the first element is a valid TALES root element
    root=expr.split('/', 1)[0]
    return root in root_elements

def get_video_stream_from_website(url):
    """Return the videostream embedded in the given website.

    Return None if no stream can be found.

    Supports: dailymotion, youtube, googlevideo
    """
    stream=None
    if  'dailymotion' in url:
        if '/get/' in url:
            return url
        u=urlopen(url)
        data=[ l for l in u.readlines() if '.addVariable' in l and 'flv' in l ]
        u.close()
        if data:
            addr=re.findall('\"(http.+?)\"', data[0])
            if addr:
                stream=unquote(addr[0])
    elif 'youtube.com' in url:
        if '/get_video' in url:
            return url
        u=urlopen(url)
        data=[ l for l in u.readlines() if 'player2.swf' in l ]
        u.close()
        if data:
            addr=re.findall('(video_id=.+?)\"', data[0])
            if addr:
                stream='http://www.youtube.com/get_video?' + addr[0].strip()
    elif 'video.google.com' in url:
        if '/videodownload' in url:
            return url
        u=urlopen(url)
        data=[ l for l in u.readlines() if '.gvp' in l ]
        u.close()
        if data:
            addr=re.findall(r'http://.+?.gvp\?docid=.\d+', data[0])
            if addr:
                u=urlopen(addr[0])
                data=[ l for l in u.readlines() if 'url:' in l ]
                u.close()
                if data:
                    stream=data[0][4:].strip()
    return stream

class CircularList(list):
    """Circular list maintaing a current index.
    """
    def __init__(self, *p):
        super(CircularList, self).__init__(*p)
        self._index=0

    def current(self):
        if self:
            return self[self._index]
        else:
            return None

    def __next__(self):
        self._index = (self._index + 1) % len(self)
        return self.current()

    def prev(self):
        self._index = (self._index - 1) % len(self)
        return self.current()

# Element-tree indent function.
# in-place prettyprint formatter
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def recursive_mkdir(d):
    d = Path(d)
    d.mkdir(parents=True)

def find_in_path(name):
    """Return the fullpath of the filename name if found in $PATH

    Return None if name cannot be found.
    """
    for d in os.environ['PATH'].split(os.path.pathsep):
        fullname=os.path.join(d, name)
        if os.path.exists(fullname):
            return fullname
    return None

def common_fieldnames(elements):
    """Extract common fieldnames from simple structured elements.
    """
    regexp=re.compile(r'^(\w+)=.*')
    res=set()
    for e in elements:
        if e.content.mimetype == 'application/x-advene-structured':
            res.update( (regexp.findall(l) or [ '_error' ])[0] for l in e.content.data.split('\n') )
    return res

parsed_representation = re.compile(r'^here/content/parsed/([\w\d_\.]+)$')
empty_representation = re.compile(r'^\s*$')

def title2content(new_title, original_content, representation):
    """Converts a title (short representation) to the appropriate content.

    It takes the 'representation' parameter into account. If it is
    present, and in a common form (typically extraction of a field),
    then we can convert the short representation back to the
    appropriate content.

    new_title is expected to be unicode.

    @return the new content or None if the content could not be updated.
    """
    assert isinstance(new_title, str)
    r = None
    if representation is None or empty_representation.match(representation):
        r = new_title
    else:
        m = parsed_representation.match(representation)
        if m:
            # We have a simple representation (here/content/parsed/name)
            # so we can update the name field.
            new_title = new_title.replace('\n', '\\n')
            name=m.group(1)

            if original_content.mimetype == 'application/x-advene-structured':
                reg = re.compile('^' + name + '=(.*?)$', re.MULTILINE)
                if reg.search(original_content.data):
                    r = reg.sub(name + '=' + new_title, original_content.data)
                else:
                    # The key is not present, add it
                    if original_content.data:
                        r = original_content.data + "\n%s=%s" % (name, new_title)
                    else:
                        r = "%s=%s" % (name, new_title)
            elif original_content.mimetype == 'application/json':
                data = json.loads(original_content.data)
                data[name] = new_title
                r = json.dumps(data)
        # else: too complex representation. Return None as default value.
    return r

def clamp(x, minimum, maximum):
    """Clamp given value between minimum and maximum.
    """
    return max(minimum, min(x, maximum))

def path2uri(p):
    if p == "" or p is None:
        return p
    u = urlparse(p)
    if len(u.scheme) > 2:
        # We already have a URI
        ret = p
    else:
        ret = Path(p).absolute().as_uri()
    return ret

def uri2path(uri):
    if uri == "":
        return uri
    if sys.platform == 'win32':
        uri = uri.replace('\\', '/')
        if re.search('^[A-Za-z]:', uri):
            uri = 'file:///' + uri
    u = urlparse(uri)
    if (u.scheme == 'file' and u.netloc == ""
        or u.scheme == ''):
        if re.search('^/[A-Za-z]:', u.path):
            return unquote(u.path[1:])
        else:
            return unquote(u.path)
    elif len(u.scheme) == "1" and sys.platform == "win32":
        # We probably have a windows path
        return uri
    else:
        logger.warning("No local path for %s", uri)
        return ""

def is_uri(uri):
    u = urlparse(uri)
    return len(u.scheme) > 1 and u.scheme != 'file'

@memoize
def media_is_valid(uri):
    """Checks that the uri is valid
    """
    try:
        request = urllib.request.Request(uri)
    except ValueError:
        # It may be a local path. Check that it exists.
        return Path(uri).exists()
    request.get_method = lambda: 'HEAD'
    try:
        urllib.request.urlopen(request)
        return True
    except urllib.request.HTTPError:
        return False
    except urllib.error.URLError:
        return False
