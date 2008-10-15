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
"""VLC library functions."""

import advene.core.config as config
import time
import StringIO
import inspect
import md5
import os
import sys
import re
import zipfile
import urllib
import unicodedata
import types

from gettext import gettext as _

from advene.model.cam.package import Package
from advene.model.cam.annotation import Annotation
from advene.model.cam.relation import Relation
from advene.model.cam.list import Schema
from advene.model.cam.tag import Tag, AnnotationType, RelationType
from advene.model.cam.resource import Resource
from advene.model.cam.view import View
from advene.model.cam.query import Query
from advene.util.defaultdict import DefaultDict
from advene.model.consts import DC_NS_PREFIX, ADVENE_NS_PREFIX
from advene.model.tales import AdveneTalesException

# Initialize ElementTree namespace map with our own prefixes
import xml.etree.ElementTree as ET
ET._namespace_map[config.data.namespace]='advene'
ET._namespace_map['http://www.w3.org/2000/svg']='svg'
ET._namespace_map['http://www.w3.org/1999/xlink']='xlink'
ET._namespace_map[DC_NS_PREFIX]='dc'
ET._namespace_map[ADVENE_NS_PREFIX]='advene2'
# FIXME: add other namespaces

def fourcc2rawcode (code):
    """VideoLan to PIL code conversion.

    Converts the FOURCC used by VideoLan into the corresponding
    rawcode specification used by the python Image module.

    @param code: the FOURCC code from VideoLan
    @type code: int or string
    @return: the corresponding PIL code
    @rtype: string
    """
    if code == 'PNG' or code == 'png':
        return 'PNG'

    if code == 'video/x-raw-rgb':
        return 'BGRX'

    conv = {
        'RV32' : 'BGRX',
        'png ' : 'PNG',
        ' gnp' : 'PNG', # On PPC-MacOS X
        }
    if isinstance(code, int) or isinstance(code, long):
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

class TypedUnicode(unicode):
    """Unicode string with a mimetype attribute.
    """
    def __init__(self, *p, **kw):
        super(TypedUnicode, self).__init__(*p, **kw)
        self.contenttype='text/plain'

class TypedString(str):
    """String with a mimetype attribute.
    """
    def __init__(self, *p, **kw):
        super(TypedString, self).__init__(*p, **kw)
        self.contenttype='text/plain'

def snapshot2png (image, output=None):
    """Convert a VLC RGBPicture to PNG.

    output is either a filename or a stream. If not given, the image
    will be returned as a buffer.

    @param image: a VLC.RGBPicture
    @param output: the output stream or filename (optional)
    @type output: filename or stream
    @return: an image buffer (optional)
    @rtype: string
    """
    if image.height == 0 or image.height is None:
        print "Error : 0 sized snapshot"
        return ""

    png=None

    code=fourcc2rawcode(image.type)
    if code == 'PNG':
        png=TypedString(image.data)
        png.contenttype='image/png'
    elif code is not None:
        try:
            i = Image.fromstring ("RGB", (image.width, image.height), image.data,
                                  "raw", code)
            ostream = StringIO.StringIO ()
            i.save(ostream, 'png')
            png=TypedString(ostream.getvalue())
            png.contenttype='image/png'
        except NameError:
            print "snapshot: conversion module not available"
    else:
        print "snapshot: unknown image type ", repr(image.type)

    if png is None:
        f=open(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ), 'rb')
        png=TypedString(f.read(10000))
        png.contenttype='image/png'
        f.close()

    if output is not None:
        f=open(output, 'wb')
        f.write(png)
        f.close()
        return ""
    else:
        return png

def mediafile2id (mediafile):
    """Returns an id (with encoded /) corresponding to the mediafile.

    @param mediafile: the name of the mediafile
    @type mediafile: string
    @return: an id
    @rtype: string
    """
    m=md5.new(mediafile)
    return m.hexdigest()

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
    mediafile = p.meta.get(config.data.namespace+"mediafile", None)
    if mediafile is not None and mediafile != "":
        return mediafile2id (mediafile)
    else:
        return "undefined"

normalized_re=re.compile(r'LATIN (SMALL|CAPITAL) LETTER (\w)')
valid_re=re.compile(r'[a-zA-Z0-9_]')
extended_valid_re=re.compile(r'[ -@a-zA-Z0-9_]')

def title2id(t):
    """Convert a unicode title to a valid id.

    It will replace spaces by underscores, accented chars by their
    accented equivalent, and other characters by -
    """
    t=unicode(t)
    (text, count)=re.subn(r'\s', '_', t)
    res=[]
    for c in text:
        if not valid_re.match(c):
            # Try to normalize
            m=normalized_re.search(unicodedata.name(c))
            if m:
                c=m.group(2)
                if m.group(1) == 'SMALL':
                    c=c.lower()
            else:
                c='_'
        res.append(c)
    return "".join(res)

def unaccent(t):
    """Remove accents from a string.
    """
    t=unicode(t)
    res=[]
    for c in t:
        if not extended_valid_re.match(c):
            # Try to normalize
            m=normalized_re.search(unicodedata.name(c))
            if m:
                c=m.group(2)
                if m.group(1) == 'SMALL':
                    c=c.lower()
            else:
                c=' '
        res.append(c)
    return "".join(res)

def format_time (val=0):
    """Formats a value (in milliseconds) into a time string.

    @param val: the value
    @type val: int
    @return: the formatted string
    @rtype: string
    """
    if val is None:
        return '--:--:--.---'
    elif val < 0:
        val = 0
    (s, ms) = divmod(long(val), 1000)
    # Format: HH:MM:SS.mmm
    return "%s.%03d" % (time.strftime("%H:%M:%S", time.gmtime(s)), ms)

small_time_regexp=re.compile('(?P<m>\d+):(?P<s>\d+)[.,]?(?P<ms>\d+)?$')
time_regexp=re.compile('(?P<h>\d+):(?P<m>\d+):(?P<s>\d+)[.,]?(?P<ms>\d+)?$')
def convert_time(s):
    """Convert a time string as long.

    If the parameter is a number, it is considered as a ms value.
    Else we try to parse a hh:mm:ss.xxx value
    """
    try:
        val=long(s)
    except ValueError:
        # It was not a number. Try to determine its format.
        t=None
        m=time_regexp.match(s)
        if m:
            t=m.groupdict()
        else:
            m=small_time_regexp.match(s)
            if m:
                t=m.groupdict()
                t['h'] = 0

        if t is not None:
            if 'ms' in t and t['ms']:
                t['ms']=(t['ms'] + ("0" * 4))[:3]
            else:
                t['ms']=0
            for k in t:
                if t[k] is None:
                    t[k]=0
                t[k] = long(t[k])
            val= t['ms'] + t['s'] * 1000 + t['m'] * 60000 + t['h'] * 3600000
        else:
            raise Exception("Unknown time format for %s" % s)
    return val

def matching_relationtypes(package, typ1, typ2):
    """Return a list of relationtypes that can be used to link annotations of type typ1 and typ2.

    We use the id (i.e. the fragment part from the URI) to match.
    """
    # FIXME: works only on binary relations for the moment.
    # FIXME: adapt to new model
    r=[]
##    for rt in package.relation_types:
##        def get_id_from_fragment(uri):
##            try:
##                i=uri[uri.index('#')+1:]
##            except ValueError:
##                i=uri
##            return unicode(i)
##
##        # URI version
##        # lat=[ absolute_uri(package, t) for t in rt.getHackedMemberTypes() ]
##        # t1=typ1.uri
##        # t2=typ2.uri
##
##        # Id version
##        lat= [ get_id_from_fragment(t) for t in rt.getHackedMemberTypes() ]
##        t1=get_id_from_fragment(typ1.uri)
##        t2=get_id_from_fragment(typ2.uri)
##
##        #print "Testing (%s, %s) matching %s" % (t1, t2, lat)
##        if len (lat) == 2 \
##        and (lat[0] == u'' or lat[0] == t1) \
##        and (lat[1] == u'' or lat[1] == t2):
##            r.append(rt)
##    #print "Matching: %s" % r
    return r

element_label = {
    Package: _("Package"),
    Annotation: _("Annotation"),
    Relation: _("Relation"),
    Schema: _("Schema"),
    AnnotationType: _("Annotation Type"),
    RelationType: _("Relation Type"),
    View: _("View"),
    Query: _("Query"),
    Tag: _("Tag"),
    Resource: _("Resource"),
    }

def get_type(el):
    try:
        t=element_label[type(el)]
    except:
        t=unicode(type(el))
    return t

def get_valid_members (el):
    """Return a list of strings, valid members for the object el in TALES.

    This method is used to generate the contextual completion menu
    in the web interface and the browser view.

    @param el: the object to examine (often an Advene object)
    @type el: any

    @return: the list of elements which are members of the object,
             in the TALES meaning.
    @rtype: list
    """
    # FIXME: try to sort items in a meaningful way

    # FIXME: return only simple items if not in expert mode
    l = []
    try:
        l.extend(el.ids())
    except AttributeError:
        try:
            l.extend(el.keys())
        except AttributeError:
            pass
    if l:
        l.insert(0, _('---- Elements ----'))

    pl=[e[0].replace('_tales_', '')
        for e in inspect.getmembers(type(el))
        if isinstance(e[1], property) and e[1].fget is not None]
    if pl:
        l.append(_('---- Attributes ----'))
        l.extend(pl)

    pl=[ name
         for (name, method) in inspect.getmembers(el)
         if name in ('first', 'rest') 
         or (isinstance(method, types.MethodType) 
         and len(inspect.getargspec(method)[0]) == 1 + len(inspect.getargspec(method)[3] or [])
         and not name.startswith('_'))
         and not name == 'close' ]
    if pl:
        l.append(_('---- Methods ----'))
        l.extend(pl)
    # Global methods
    # FIXME 
    # l.extend (AdveneContext.defaultMethods ())
    # User-defined global methods
    #FIXME
    # l.extend (config.data.global_methods)

    return l

def get_statistics(fname):
    """Return formatted statistics about the package.
    """
    # FIXME: to reimplement
    st=None
    if fname.lower().endswith('.azp'):
        # If the file is a .azp, then it may have a
        # META-INF/statistics.xml file. Use it.
        # Encoding issues on win32:
        if isinstance(fname, unicode):
            fname=fname.encode(sys.getfilesystemencoding())
        try:
            z=zipfile.ZipFile(fname, 'r')
        except Exception, e:
            raise AdveneException(_("Cannot read %(filename)s: %(error)s") % {'filename': fname,
                                                                              'error': unicode(e)})

        # Check the validity of mimetype
        try:
            typ = z.read('mimetype')
        except KeyError:
            raise AdveneException(_("File %s is not an Advene zip package.") % fname)
        if typ != advene.model.zippackage.MIMETYPE:
            raise AdveneException(_("File %s is not an Advene zip package.") % fname)

        try:
            st=z.read('META-INF/statistics.xml')
        except KeyError:
            st=None

        z.close()

    if not st:
        # If we are here, it is that we could not get the statistics.xml.
        # Generate it (it can take some time)
        try:
            p=Package(uri=fname)
        except Exception, e:
            raise(_("Error:\n%s") % unicode(e))
        st=p.generate_statistics()
        p.close()

    # We have the statistics in XML format. Render it.
    s=StringIO.StringIO(st)
    #h=advene.model.package.StatisticsHandler()
    #data=h.parse_file(s)
    s.close()

    m=_("""Package %(title)s:
%(schema)s
%(annotation)s in %(annotation_type)s
%(relation)s in %(relation_type)s
%(query)s
%(view)s

Description:
%(description)s
""") % {
        'title': data['title'],
        'schema': format_element_name('schema', data['schema']),
        'annotation': format_element_name('annotation', data['annotation']),
        'annotation_type': format_element_name('annotation_type', data['annotation_type']),
        'relation': format_element_name('relation', data['relation']),
        'relation_type': format_element_name('relation_type', data['relation_type']),
        'query': format_element_name('query', data['query']),
        'view': format_element_name('view', data['view']),
        'description': data['description']
        }
    return m

element_declinations={
    'schema': (_('schema'), _('schemas')),
    'annotation': (_('annotation'), _('annotations')),
    'annotation_type': (_('annotation type'), _('annotation types')),
    'annotation-type': (_('annotation type'), _('annotation types')),
    'relation': (_('relation'), _('relations')),
    'relation_type': (_('relation type'), _('relation types')),
    'relation-type': (_('relation type'), _('relation types')),
    'query': (_('query'), _('queries')),
    'view': (_('view'), _('views')),
    'package': (_('package'), _('packages')),
    'resource': (_('resource'), _('resources')),
    }

def format_element_name(name, count=None):
    """Formats an element name (from the model) according to count.
    
    FIXME: we should use the appropriate gettext method here.
    """
    if not name in element_declinations:
        return name

    if count is None:
        return element_declinations[name][0]

    if count == 0:
        return _("No %s") % element_declinations[name][0]
    elif count == 1:
        return _("1 %s") % element_declinations[name][0]
    else:
        return _("%(count)d %(plural)s") % {
            'count': count,
            'plural': element_declinations[name][1]}

# Valid TALES expression check

# Root elements
root_elements = ('here', 'nothing', 'default', 'options', 'repeat', 'request',
                 # Root elements available in STBVs
                 'package', 'packages', 'annotation', 'relation',
                 'activeAnnotations', 'player', 'event', 'view',
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
        u=urllib.urlopen(url)
        data=[ l for l in u.readlines() if '.addVariable' in l and 'flv' in l ]
        u.close()
        if data:
            addr=re.findall('\"(http.+?)\"', data[0])
            if addr:
                stream=urllib.unquote(addr[0])
    elif 'youtube.com' in url:
        if '/get_video' in url:
            return url
        u=urllib.urlopen(url)
        data=[ l for l in u.readlines() if 'player2.swf' in l ]
        u.close()
        if data:
            addr=re.findall('(video_id=.+?)\"', data[0])
            if addr:
                stream='http://www.youtube.com/get_video?' + addr[0].strip()
    elif 'video.google.com' in url:
        if '/videodownload' in url:
            return url
        u=urllib.urlopen(url)
        data=[ l for l in u.readlines() if '.gvp' in l ]
        u.close()
        if data:
            addr=re.findall('http://.+?.gvp\?docid=.\d+', data[0])
            if addr:
                u=urllib.urlopen(addr[0])
                data=[ l for l in u.readlines() if 'url:' in l ]
                u.close()
                if data:
                    stream=data[0][4:].strip()
    return stream

def get_view_type(v):
    """Return the type of the view.

    Return values: static, dynamic, adhoc, None
    """
    if not isinstance(v, View):
        return None
    if v.content.mimetype == 'application/x-advene-ruleset':
        return 'dynamic'
    elif (v.content.mimetype == 'application/x-advene-adhoc-view'
          or v.content.mimetype == 'application/x-advene-workspace-view'):
        return 'adhoc'
    else:
        return 'static'

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

    def next(self):
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
    # FIXME: already in ...
    parent=os.path.dirname(d)
    if not os.path.exists(parent):
        recursive_mkdir(parent)
    os.mkdir(d)

def find_in_path(name):
    """Return the fullpath of the filename name if found in $PATH

    Return None if name cannot be found.
    """
    for d in os.environ['PATH'].split(os.path.pathsep):
        fullname=os.path.join(d, name)
        if os.path.exists(fullname):
            return fullname
    return None

def overlapping_annotations(t):
    """Return a set of overlapping annotations (couples)
    """
    res=DefaultDict(default=[])
    l=t.annotations[:]
    l.sort(key=lambda a: a.begin)
    while l:
        a=l.pop()
        begin=a.begin
        end=a.end
        for b in l:
            be=b.begin
            en=b.end
            if not (end <= be or en <= begin):
                res.append( (a, b) )
    return res

def common_fieldnames(elements):
    """Extract common fieldnames from simple structured elements.
    """
    regexp=re.compile('^(\w+)=.*')
    res=set()
    for e in elements:
        if e.content.mimetype == 'application/x-advene-structured':
            res.update( (regexp.findall(l) or [ '_error' ])[0] for l in e.content.data.split('\n') )
    return res
