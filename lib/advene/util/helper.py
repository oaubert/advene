#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
import logging
logger = logging.getLogger(__name__)

import collections
import itertools
import time
import io
import inspect
import json
import os
import re
import zipfile

import advene.core.config as config
from advene.core.imagecache import ImageCache
# Imports for backwards compatibility
from advene.util.tools import chars, fourcc2rawcode, \
    TitledElement, TypedUnicode, TypedString, memoize, mediafile2id, \
    mediafile_checksum, package2id, title2id, unaccent, get_keyword_list, \
    median, get_timestamp, get_id, is_valid_tales, \
    get_video_stream_from_website, CircularList, indent, recursive_mkdir, \
    find_in_path, common_fieldnames, title2content, clamp, \
    path2uri, uri2path, is_uri, media_is_valid

try:
    from PIL import Image
except ImportError:
    logger.error("Cannot load Image module. Image conversion is disabled.")

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
        logger.error("Error : 0 sized snapshot")
        return ""

    png = None

    code = fourcc2rawcode(image.type)
    if code == 'PNG':
        png = TypedString(image.data)
        png.contenttype = 'image/png'
    elif code is not None:
        try:
            i = Image.fromstring ("RGB", (image.width, image.height), image.data,
                                  "raw", code)
            ostream = io.StringIO ()
            i.save(ostream, 'png')
            png = TypedString(ostream.getvalue())
            png.contenttype = 'image/png'
        except NameError:
            logger.error("snapshot: conversion module not available")
    else:
        logger.error("snapshot: unknown image type %s", repr(image.type))

    if png is None:
        png = ImageCache.not_yet_available_image

    if output is not None:
        f = open(output, 'wb')
        f.write(png)
        f.close()
        return ""
    else:
        return png

def format_time_reference(val = 0):
    """Formats a value (in milliseconds) into a time string.

    Use the most complete format (HH:MM:SS.sss), for reference into
    saved files.
    """
    if val is None:
        return '--:--:--.---'
    elif val < 0:
        return '00:00:00.000'
    (s, ms) = divmod(int(val), 1000)
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
    (s, ms) = divmod(int(val), 1000)
    f = config.data.preferences['timestamp-format']
    if f == '%S':
        ret = str(s)
    elif f == '%.S':
        ret = '%d.%03d' % (s, ms)
    else:
        f = f.replace('''%.S''', '''%S.''' + '%03d' % ms).replace('''%fS''', '''%Sf''' + '%02d' % int(ms * config.data.preferences['default-fps'] / 1000))
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

small_time_regexp = re.compile(r'(?P<m>\d+):(?P<s>\d+)(?P<sep>[.,f]?)(?P<ms>\d+)?$')
time_regexp = re.compile(r'((?P<h>\d+):)?(?P<m>\d+):(?P<s>\d+)((?P<sep>[.,:f])(?P<ms>\d+))?$')
float_regexp = re.compile(r'(?P<s>\d*)\.(?P<ms>\d*)')
def parse_time(s):
    r"""Convert a time string as long.

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
    # Remove surrounding whitespace, including zero-width space.
    # See https://bugs.python.org/issue13391
    if isinstance(s, str):
        s = s.strip().strip(u'\u200B\ufeff')
    if s is None:
        return 0
    try:
        val = int(s)
    except ValueError:
        # It was not a plain integer. Try to determine its format.
        t = None
        m = float_regexp.match(s)
        if m:
            t = m.groupdict()
            t['sep'] = ''
        else:
            m = time_regexp.match(s)
            if m:
                t = m.groupdict()
            else:
                m = small_time_regexp.match(s)
                if m:
                    t = m.groupdict()
                    t['h'] = 0

        if t is not None:
            if 'ms' in t and t['ms']:
                if t['sep'] == 'f':
                    # Frame number
                    t['ms'] = int(int(t['ms']) * (1000 / config.data.preferences['default-fps']))
                else:
                    t['ms'] = (t['ms'] + ("0" * 4))[:3]
            else:
                t['ms'] = 0
            for k in t:
                if t[k] is None:
                    t[k] = 0
                try:
                    t[k] = int(t[k] or 0)
                except ValueError:
                    t[k] = 0
            val =  t.get('ms', 0) + t.get('s', 0) * 1000 + t.get('m', 0) * 60000 + t.get('h', 0) * 3600000
        else:
            raise InvalidTimestamp("Unknown time format for %s" % s)
    return val

def matching_relationtypes(package, typ1, typ2):
    """Return a list of relationtypes that can be used to link annotations of type typ1 and typ2.

    We use the id (i.e. the fragment part from the URI) to match.
    """
    # FIXME: works only on binary relations for the moment.
    r = []
    for rt in package.relationTypes:
        def get_id_from_fragment(uri):
            try:
                i = uri[uri.index('#')+1:]
            except ValueError:
                i = uri
            return str(i)

        # URI version
        # lat = [ absolute_uri(package, t) for t in rt.getHackedMemberTypes() ]
        # t1 = typ1.uri
        # t2 = typ2.uri

        # Id version
        lat =  [ get_id_from_fragment(t) for t in rt.getHackedMemberTypes() ]
        t1 = get_id_from_fragment(typ1.uri)
        t2 = get_id_from_fragment(typ2.uri)

        logger.debug("Testing (%s, %s) matching %s", t1, t2, lat)
        if len (lat) == 2 \
        and (lat[0] == '' or lat[0] == t1) \
        and (lat[1] == '' or lat[1] == t2):
            r.append(rt)
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
        t = element_label[type(el)]
    except Exception:
        t = type(el).__name__
    return t

def get_type_predefined_completions(at, sort_key=None):
    """Return the predefined completions for the given annotation type

    If sort_key is defined, then sort values against the metadata value
    indexed by key defined in sort.
    """
    s = at.getMetaData(config.data.namespace, "completions")
    res = get_keyword_list(s)

    if sort_key is not None:
        metadata = None
        try:
            metadata = json.loads(at.getMetaData(config.data.namespace, 'value_metadata') or 'null')
        except ValueError:
            logger.warning("Cannot parse metadata %s", metadata)
        if metadata is not None:
            res.sort(key=lambda k: metadata.get(k, {}).get(sort_key, 0))
    return res

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
    items = []
    try:
        items.extend(el.ids())
    except AttributeError:
        try:
            items.extend(list(el.keys()))
        except AttributeError:
            pass
    if items:
        items.insert(0, _('---- Elements ----'))

    pl = [ e[0]
           for e in inspect.getmembers(type(el))
           if isinstance(e[1], property) and e[1].fget is not None ]
    if pl:
        items.append(_('---- Attributes ----'))
        items.extend(pl)

    items.append(_('---- Methods ----'))
    # Global methods
    items.extend (AdveneContext.defaultMethods ())
    # User-defined global methods
    items.extend (config.data.global_methods)

    return items

def import_element(package, element, controller, notify=True):
    p = package
    if element.viewableClass == 'view':
        v = p.importView(element)
        p.views.append(v)
        if notify:
            controller.notify("ViewCreate", view=v)
    elif element.viewableClass == 'schema':
        s = p.importSchema(element)
        p.schemas.append(s)
        if notify:
            controller.notify("SchemaCreate", schema=s)
    elif element.viewableClass == 'annotation':
        a = p.importAnnotation(element)
        p.annotations.append(a)
        if notify:
            controller.notify("AnnotationCreate", annotation=a)
    elif element.viewableClass == 'relation':
        r = p.importRelation(element)
        p.relations.append(r)
        if notify:
            controller.notify("RelationCreate", relation=r)
    elif element.viewableClass == 'query':
        q = p.importQuery(element)
        p.queries.append(q)
        if notify:
            controller.notify("QueryCreate", query=q)
    else:
        logger.warning("Import element of class %s not supported yet.", element.viewableClass)

def unimport_element(package, element, controller, notify=True):
    p = package
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
        logger.warning("%s Not supported yet.", element.viewableClass)

def get_statistics(fname):
    """Return formatted statistics about the package.
    """
    st = None
    if fname.lower().endswith('.azp'):
        # If the file is a .azp, then it may have a
        # META-INF/statistics.xml file. Use it.
        try:
            z = zipfile.ZipFile(fname, 'r')
        except Exception as e:
            raise AdveneException(_("Cannot read %(filename)s: %(error)s") % {'filename': fname,
                                                                              'error': str(e)})

        # Check the validity of mimetype
        try:
            typ = z.read('mimetype').decode('utf-8')
        except KeyError:
            raise AdveneException(_("File %s is not an Advene zip package - no mimetype.") % fname)
        if typ != advene.model.zippackage.MIMETYPE:
            raise AdveneException(_("File %(fname)s is not an Advene zip package - wrong mimetype %(type)s.") % {'fname': fname,
                                                                                                                 'type': typ})

        try:
            st = z.read('META-INF/statistics.xml').decode('utf-8')
        except KeyError:
            st = None

        z.close()

    if not st:
        # If we are here, it is that we could not get the statistics.xml.
        # Generate it (it can take some time)
        try:
            p = Package(uri=fname)
        except Exception:
            raise _("Error:\n%s")
        st = p.generate_statistics()
        p.close()

    # We have the statistics in XML format. Render it.
    s = io.StringIO(st)
    h = advene.model.package.StatisticsHandler()
    data = h.parse_file(s)
    s.close()

    m = _("""Package %(title)s:
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

def get_annotations_statistics(annotations, format='text'):
    """Return some statistics about the given annotations.

    The returned format can be either text or dict
    """
    if not annotations:
        if format == 'text':
            return _("No annotation")
        else:
            return {
                'min': 0,
                'max': 0,
                'mean': 0,
                'median': 0,
                'total': 0
            }
    total_duration = sum(a.fragment.duration for a in annotations)
    res = {
        'min': min(a.fragment.duration for a in annotations),
        'max': max(a.fragment.duration for a in annotations),
        'mean': total_duration / len(annotations),
        'median': median(a.fragment.duration for a in annotations),
        'total': total_duration
    }
    # Determine distinct values. We split fields against commas
    # FIXME: this should be a specific content-type (application/x-advene-keywords)
    distinct_values = collections.Counter(itertools.chain.from_iterable(re.split(r'\s*,\s*', a.content.data) for a in annotations))
    res['distinct_values_count'] = distinct_values_count = len(distinct_values)
    if distinct_values_count < 20:
        res['distinct_values'] = distinct_values
        res['distinct_values_repr'] = "\n".join("\t%s: %s" % (k.replace('\n', '\\n'), distinct_values[k]) for k in sorted(distinct_values.keys()))
    else:
        res['distinct_values'] = []
        res['distinct_values_repr'] = ""

    if format == 'text':
        for k in ('min', 'max', 'mean', 'median', 'total'):
            res[k] = format_time(res[k])
        res['count'] = format_element_name('annotation', len(annotations))
        return """Count: %(count)s
Min duration: %(min)s
Max duration: %(max)s
Mean duration: %(mean)s
Median duration: %(median)s
Total duration: %(total)s

%(distinct_values_count)d distinct values.
%(distinct_values_repr)s
""" % res
    else:
        return res

def get_schema_statistics(schema):
    """Return some stats about the schema.
    """
    return """{annotationtype_count} with {annotation_count}
    {relationtype_count} with {relation_count}
    """.format(
        annotationtype_count=format_element_name('annotation_type', len(schema.annotationTypes)),
        relationtype_count=format_element_name('relation_type', len(schema.relationTypes)),
        annotation_count=format_element_name('annotation', sum(len(at.annotations) for at in schema.annotationTypes)),
        relation_count=format_element_name('relation', sum(len(rt.relations) for rt in schema.relationTypes))
    )

element_declinations = {
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
    if name not in element_declinations:
        return f"{count} {name}(s)"

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

def is_video_file(uri):
    ext = os.path.splitext(uri)[1].lower()
    return (ext in config.data.video_extensions)
