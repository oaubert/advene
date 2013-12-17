#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2012 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
"""Generic helper functions."""

import time
import StringIO
import inspect
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
import os
import sys
import re
import zipfile
import urllib
import unicodedata

import advene.core.config as config
from advene.core.imagecache import ImageCache

try:
    import Image
except ImportError:
    print "Cannot load Image module. Image conversion is disabled."

from gettext import gettext as _

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.view import View
from advene.model.query import Query
import advene.model.zippackage

from advene.model.tal.context import AdveneContext
from advene.model.exception import AdveneException

# Initialize ElementTree namespace map with our own prefixes.  This
# helps generating readable XML through ElementTree (the appropriate
# namespace prefixes will be used)
import xml.etree.ElementTree as ET
ET._namespace_map.update({
    config.data.namespace: 'advene',
    'http://www.w3.org/2000/svg': 'svg',
    'http://www.w3.org/1999/xlink': 'xlink',
    'http://purl.org/dc/elements/1.1/': 'dc',
    'http://experience.univ-lyon1.fr/advene/ns/advenetool': 'advenetool',
    'http://xml.zope.org/namespaces/tal': 'tal',
    'http://xml.zope.org/namespaces/metal': 'metal',
    })

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
    def __new__(cls, value=""):
        s=unicode.__new__(cls, value)
        s.contenttype='text/plain'
        return s

class TypedString(str):
    """String with a mimetype attribute.
    """
    def __new__(cls, value=""):
        s=str.__new__(cls, value)
        s.contenttype='text/plain'
        return s

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
        png=ImageCache.not_yet_available_image

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
    m=md5(mediafile)
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
    mediafile = p.getMetaData (config.data.namespace, "mediafile")
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
            m=normalized_re.search(unicodedata.name(c, ' '))
            if m:
                c=m.group(2)
                if m.group(1) == 'SMALL':
                    c=c.lower()
            else:
                c=' '
        res.append(c)
    return "".join(res)

def format_time_reference(val = 0):
    """Formats a value (in milliseconds) into a time string.

    Use the most complete format (HH:MM:SS.sss), for reference into
    saved files.
    """
    if val is None:
        return '--:--:--.---'
    elif val < 0:
        return '00:00:00.000'
    (s, ms) = divmod(long(val), 1000)
    # Format: HH:MM:SS.mmm
    return "%s.%03d" % (time.strftime("%H:%M:%S", time.gmtime(s)), ms)

def format_time (val = 0):
    """Formats a value (in milliseconds) into a time string, respecting user preferences.

    @param val: the value
    @type val: int
    @return: the formatted string
    @rtype: string
    """
    dummy = False
    if val is None:
        dummy = True
        val = 0
    elif val < 0:
        val = 0
    (s, ms) = divmod(long(val), 1000)
    f = config.data.preferences['timestamp-format']
    if f == '%S':
        ret = str(s)
    elif f == '%.S':
        ret = '%d.%03d' % (s, ms)
    else:
        f = f.replace('''%.S''', '''%S.''' + '%03d' % ms).replace('''%fS''', '''%Sf''' + '%02d' % long(ms * config.data.preferences['default-fps'] / 1000))
        try:
            ret = time.strftime(f, time.gmtime(s))
        except ValueError:
            ret = '--:error:--'

    if dummy:
        return ret.replace('0', '-')
    else:
        return ret

class InvalidTimestamp(Exception):
    pass

small_time_regexp=re.compile('(?P<m>\d+):(?P<s>\d+)(?P<sep>[.,f]?)(?P<ms>\d+)?$')
time_regexp=re.compile('(?P<h>\d+):(?P<m>\d+):(?P<s>\d+)(?P<sep>[.,:f]?)(?P<ms>\d+)?$')
float_regexp = re.compile('(?P<s>\d*)\.(?P<ms>\d*)')
def parse_time(s):
    """Convert a time string as long.

    This function tries to handle multiple formats:

    - plain integers are considered as milliseconds.
      Regexp: \d+
      Example: 2134 or 134 or 2000

    - float numbers are considered as seconds
      Regexp: \d*\.\d*
      Example: 2.134 or .134 or 2.

    - formatted timestamps with colons in them will be interpreted as follows.
      m:s (1 colon)
      m:s.ms (1 colon)
      m:sfNN
      h:m:s (2 colons)
      h:m:s.ms (2 colons)
      h:m:sfNN

      Legend:
      h: hours
      m: minutes
      s: seconds
      ms: milliseconds
      NN: frame number
    """
    try:
        val=long(s)
    except ValueError:
        # It was not a plain integer. Try to determine its format.
        t=None
        m = float_regexp.match(s)
        if m:
            t = m.groupdict()
        else:
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
                if t['sep'] == 'f':
                    # Frame number
                    t['ms'] = long(long(t['ms']) * (1000 / config.data.preferences['default-fps']))
                else:
                    t['ms']=(t['ms'] + ("0" * 4))[:3]
            else:
                t['ms']=0
            for k in t:
                if t[k] is None:
                    t[k] = 0
                try:
                    t[k] = long(t[k] or 0)
                except ValueError:
                    t[k] = 0
            val= t.get('ms', 0) + t.get('s', 0) * 1000 + t.get('m', 0) * 60000 + t.get('h', 0) * 3600000
        else:
            raise InvalidTimestamp("Unknown time format for %s" % s)
    return val

def matching_relationtypes(package, typ1, typ2):
    """Return a list of relationtypes that can be used to link annotations of type typ1 and typ2.

    We use the id (i.e. the fragment part from the URI) to match.
    """
    # FIXME: works only on binary relations for the moment.
    r=[]
    for rt in package.relationTypes:
        def get_id_from_fragment(uri):
            try:
                i=uri[uri.index('#')+1:]
            except ValueError:
                i=uri
            return unicode(i)

        # URI version
        # lat=[ absolute_uri(package, t) for t in rt.getHackedMemberTypes() ]
        # t1=typ1.uri
        # t2=typ2.uri

        # Id version
        lat= [ get_id_from_fragment(t) for t in rt.getHackedMemberTypes() ]
        t1=get_id_from_fragment(typ1.uri)
        t2=get_id_from_fragment(typ2.uri)

        #print "Testing (%s, %s) matching %s" % (t1, t2, lat)
        if len (lat) == 2 \
        and (lat[0] == u'' or lat[0] == t1) \
        and (lat[1] == u'' or lat[1] == t2):
            r.append(rt)
    #print "Matching: %s" % r
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
    Resources: _("Resource Folder"),
    ResourceData: _("Resource File"),
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

    pl=[e[0]
        for e in inspect.getmembers(type(el))
        if isinstance(e[1], property) and e[1].fget is not None]
    if pl:
        l.append(_('---- Attributes ----'))
        l.extend(pl)

    l.append(_('---- Methods ----'))
    # Global methods
    l.extend (AdveneContext.defaultMethods ())
    # User-defined global methods
    l.extend (config.data.global_methods)

    return l

def import_element(package, element, controller, notify=True):
    p=package
    if element.viewableClass == 'view':
        v=p.importView(element)
        p.views.append(v)
        if notify:
            controller.notify("ViewCreate", view=v)
    elif element.viewableClass == 'schema':
        s=p.importSchema(element)
        p.schemas.append(s)
        if notify:
            controller.notify("SchemaCreate", schema=s)
    elif element.viewableClass == 'annotation':
        a=p.importAnnotation(element)
        p.annotations.append(a)
        if notify:
            controller.notify("AnnotationCreate", annotation=a)
    elif element.viewableClass == 'relation':
        r=p.importRelation(element)
        p.relations.append(r)
        if notify:
            controller.notify("RelationCreate", relation=r)
    elif element.viewableClass == 'query':
        q=p.importQuery(element)
        p.queries.append(q)
        if notify:
            controller.notify("QueryCreate", query=q)
    else:
        print "Import element of class %s not supported yet." % element.viewableClass

def unimport_element(package, element, controller, notify=True):
    p=package
    if element.viewableClass == 'view':
        p.views.remove(element)
        if notify:
            controller.notify("ViewDelete", view=element)
    elif element.viewableClass == 'schema':
        p.schemas.remove(element)
        if notify:
            controller.notify("SchemaDelete", schema=element)
    elif element.viewableClass == 'annotation':
        p.annotations.remove(element)
        if notify:
            controller.notify("AnnotationDelete", annotation=element)
    elif element.viewableClass == 'relation':
        p.relations.remove(element)
        if notify:
            controller.notify("RelationDelete", relation=element)
    elif element.viewableClass == 'query':
        p.queries.remove(element)
        if notify:
            controller.notify("QueryDelete", query=element)
    else:
        print "%s Not supported yet." % element.viewableClass

def get_statistics(fname):
    """Return formatted statistics about the package.
    """
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
    h=advene.model.package.StatisticsHandler()
    data=h.parse_file(s)
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
    }

def format_element_name(name, count=None):
    """Formats an element name (from the model) according to count."""
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

def common_fieldnames(elements):
    """Extract common fieldnames from simple structured elements.
    """
    regexp=re.compile('^(\w+)=.*')
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

    @return the new content or None if the content could not be updated.
    """
    r = None
    if representation is None or empty_representation.match(representation):
        r = unicode(new_title)
    else:
        m = parsed_representation.match(representation)
        if m:
            # We have a simple representation (here/content/parsed/name)
            # so we can update the name field.
            new_title = unicode(new_title).replace('\n', '\\n')
            name=m.group(1)
            reg = re.compile('^' + name + '=(.*?)$', re.MULTILINE)
            if reg.search(original_content):
                r = reg.sub(name + '=' + new_title, original_content)
            else:
                # The key is not present, add it
                if original_content:
                    r = original_content + "\n%s=%s" % (name, new_title)
                else:
                    r = "%s=%s" % (name, new_title)
        # else: too complex representation. Return None as default value.
    return r
