"""VLC library functions."""

import advene.core.config as config
import os
import sys
import time
import Image
import StringIO
import inspect
import md5
import sre

from gettext import gettext as _

from advene.model.annotation import Annotation, Relation
import advene.model.tal.context

def fourcc2rawcode (code):
    """VideoLan to PIL code conversion.
    
    Converts the FOURCC used by VideoLan into the corresponding
    rawcode specification used by the python Image module.

    @param code: the FOURCC code from VideoLan
    @type code: string
    @return: the corresponding PIL code
    @rtype: string
    """
    conv = { 'RV32' : 'BGRX' }
    fourcc = "%c%c%c%c" % (code & 0xff,
                           code >> 8 & 0xff,
                           code >> 16 & 0xff,
                           code >> 24)
    return conv[fourcc]

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
    if image.height == 0:
        print "Error : %s" % a.data
        return ""
    
    if image.type == "PNG":
        # Image is already PNG
        return image.data

    i = Image.fromstring ("RGB", (image.width, image.height), image.data,
                          "raw", fourcc2rawcode(image.type))
    if output is not None:
        i.save (output, 'png')
        return ""
    else:
        ostream = StringIO.StringIO ()
        i.save(ostream, 'png')
        v=TypedString(ostream.getvalue())
        v.contenttype='image/png'
        return v

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

        def get_id(uri):
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
        lat= [ get_id(t) for t in rt.getHackedMemberTypes() ]
        t1=get_id(ann1.type.uri)
        t2=get_id(ann2.type.uri)
        
        #print "Testing (%s, %s) matching %s" % (t1, t2, lat)
        if t1 == lat[0] and t2 == lat[1]:
            r.append(rt)
    #print "Matching: %s" % r
    return r

def get_title(controller, element, representation=None):
    if element is None:
        return _("None")
    if isinstance(element, unicode) or isinstance(element, str):
        return element
    if (isinstance(element, Annotation) or isinstance(element, Relation)
        and controller is not None):
        if representation is not None and representation != "":
            c=controller.event_handler.build_context(event='Display', here=element)
            return c.evaluateValue(representation)
        expr=element.type.getMetaData(config.data.namespace, "representation")
        if expr is None or expr == '' or sre.match('^\s+', expr):
            return element.content.data
        elif controller is not None:
            c=controller.event_handler.build_context(event='Display', here=element)
            return c.evaluateValue(expr)
    if hasattr(element, 'title'):
        return unicode(element.title)
    if hasattr(element, 'id'):
        return unicode(element.id)
    return unicode(element)

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
    l.extend (advene.model.tal.context.AdveneContext.defaultMethods ())

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
    else:
        print "%s Not supported yet." % element.viewableClass

def unimport_element(package, element, controller):
    p=package
    if element.viewableClass == 'view':
        p.views.remove(element)
        controller.notify("ViewDelete", view=v)
    elif element.viewableClass == 'schema':
        p.schemas.remove(s)
        controller.notify("SchemaDelete", schema=s)
    else:
        print "%s Not supported yet." % element.viewableClass


element_declinations={
    'schema': (_('schema'), _('schemas')),
    'annotation': (_('annotation'), _('annotations')),
    'annotation_type': (_('annotation type'), _('annotation types')),
    'relation': (_('relation'), _('relations')),
    'relation_type': (_('relation type'), _('relation types')),
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
