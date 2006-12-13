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
"""VLC library functions."""

import advene.core.config as config
import time
import StringIO
import inspect
import md5
import sre
import zipfile

try:
    import Image
except ImportError:
    print "Cannot load Image module. Image conversion is disabled."

from gettext import gettext as _

from advene.model.package import Package
from advene.model.fragment import MillisecondFragment
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.view import View
from advene.model.query import Query
import advene.model.zippackage

from advene.model.tal.context import AdveneContext, AdveneTalesException
from advene.model.exception import AdveneException

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

    conv = { 'RV32' : 'BGRX',
             'png ' : 'PNG' }
    fourcc = "%c%c%c%c" % (code & 0xff,
                           code >> 8 & 0xff,
                           code >> 16 & 0xff,
                           code >> 24)
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
    mediafile = p.getMetaData (config.data.namespace, "mediafile")
    if mediafile is not None and mediafile != "":
        return mediafile2id (mediafile)
    else:
        return "undefined"

def format_time (val=0):
    """Formats a value (in milliseconds) into a time string.

    @param val: the value
    @type val: int
    @return: the formatted string
    @rtype: string
    """
    if val < 0:
        val = 0
    (s, ms) = divmod(long(val), 1000)
    # Format: HH:MM:SS.mmm
    return "%s.%03d" % (time.strftime("%H:%M:%S", time.gmtime(s)), ms)

small_time_regexp=sre.compile('(?P<m>\d+):(?P<s>\d+)[.,]?(?P<ms>\d+)?$')
time_regexp=sre.compile('(?P<h>\d+):(?P<m>\d+):(?P<s>\d+)[.,]?(?P<ms>\d+)?$')
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

def matching_relationtypes(package, ann1, ann2):
    """Return a list of relationtypes that can be used
    to link ann1 and ann2. We use the id (i.e. the fragment part from the URI)
    to match"""
    # FIXME: works only on binary relations for the moment.
    r=[]
    for rt in package.relationTypes:
        # Absolutize URIs
        # FIXME: horrible hack. Does not even work on
        # imported packages
        def absolute_uri(package, uri):
            if uri.startswith('#'):
                return package.uri + uri
            else:
                return uri

        def get_id_from_fragment(uri):
            try:
                i=uri[uri.index('#')+1:]
            except ValueError:
                i=uri
            return unicode(i)

        # URI version
        # lat=[ absolute_uri(package, t) for t in rt.getHackedMemberTypes() ]
        # t1=ann1.type.uri
        # t2=ann2.type.uri

        # Id version
        lat= [ get_id_from_fragment(t) for t in rt.getHackedMemberTypes() ]
        t1=get_id_from_fragment(ann1.type.uri)
        t2=get_id_from_fragment(ann2.type.uri)

        #print "Testing (%s, %s) matching %s" % (t1, t2, lat)
        if len (lat) == 2 \
        and (lat[0] == u'' or lat[0] == t1) \
        and (lat[1] == u'' or lat[1] == t2):
            r.append(rt)
    #print "Matching: %s" % r
    return r

def get_title(controller, element, representation=None):
    if element is None:
        r=_("None")
    if isinstance(element, unicode) or isinstance(element, str):
        return element
    if (isinstance(element, Annotation) or isinstance(element, Relation)
        and controller is not None):

        if representation is not None and representation != "":
            c=controller.event_handler.build_context(event='Display', here=element)
            try:
                r=c.evaluateValue(representation)
            except AdveneTalesException:
                r=element.content.data
            if not r:
                r=element.id
            return r

        expr=element.type.getMetaData(config.data.namespace, "representation")
        if expr is None or expr == '' or sre.match('^\s+', expr):
            r=element.content.data
            if not r:
                r=element.id
            return r

        elif controller is not None:
            c=controller.event_handler.build_context(event='Display', here=element)
            try:
                r=c.evaluateValue(expr)
            except AdveneTalesException:
                r=element.content.data
            if not r:
                r=element.id
            return r
    if hasattr(element, 'title') and element.title:
        return unicode(element.title)
    if hasattr(element, 'id') and element.id:
        return unicode(element.id)
    return unicode(element)

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

def import_element(package, element, controller):
    p=package
    if element.viewableClass == 'view':
        v=p.importView(element)
        p.views.append(v)
        controller.notify("ViewCreate", view=v)
    elif element.viewableClass == 'schema':
        s=p.importSchema(element)
        p.schemas.append(s)
        controller.notify("SchemaCreate", schema=s)
    elif element.viewableClass == 'annotation':
        a=p.importAnnotation(element)
        p.annotations.append(a)
        controller.notify("AnnotationCreate", annotation=a)
    elif element.viewableClass == 'relation':
        r=p.importRelation(element)
        p.relations.append(r)
        controller.notify("RelationCreate", relation=r)
    elif element.viewableClass == 'query':
        q=p.importQuery(element)
        p.queries.append(q)
        controller.notify("QueryCreate", query=q)
    else:
        print "Import element of class %s not supported yet." % element.viewableClass

def get_statistics(fname):
    """Return formatted statistics about the package.
    """
    st=None
    if fname.lower().endswith('.azp'):
        # If the file is a .azp, then it may have a
        # META-INF/statistics.xml file. Use it.
        try:
            z=zipfile.ZipFile(fname, 'r')
        except Exception, e:
            raise AdveneException(_("Cannot read %s: %s") % (fname, unicode(e)))

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

        try:
            z.close()
        except:
            pass

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

    m=_("""Package %s:
%s
%s in %s
%s in %s
%s
%s

Description:
%s
""") % (data['title'],
        format_element_name('schema', data['schema']),
        format_element_name('annotation', data['annotation']),
        format_element_name('annotation_type', data['annotation_type']),
        format_element_name('relation', data['relation']),
        format_element_name('relation_type', data['relation_type']),
        format_element_name('query', data['query']),
        format_element_name('view', data['view']),
        data['description'])
    return m


def unimport_element(package, element, controller):
    p=package
    if element.viewableClass == 'view':
        p.views.remove(element)
        controller.notify("ViewDelete", view=element)
    elif element.viewableClass == 'schema':
        p.schemas.remove(element)
        controller.notify("SchemaDelete", schema=element)
    elif element.viewableClass == 'annotation':
        p.annotations.remove(element)
        controller.notify("AnnotationDelete", annotation=element)
    elif element.viewableClass == 'relation':
        p.relations.remove(element)
        controller.notify("RelationDelete", relation=element)
    elif element.viewableClass == 'query':
        p.queries.remove(element)
        controller.notify("QueryDelete", query=element)
    else:
        print "%s Not supported yet." % element.viewableClass


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
        return _("%d %s") % (count, element_declinations[name][1])

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
		 'activeAnnotations', 'player', 'event',
                 # Root elements available in queries
                 'element',
                 )

# Path elements followed by any syntax
path_any_re = sre.compile('^(string|python):')

# Path elements followed by a TALES expression
path_tales_re = sre.compile('^(exists|not|nocall):(.+)')

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
