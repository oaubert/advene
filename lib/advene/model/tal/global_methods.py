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
"""
This module contains all the global methods to be automatically added to a new
AdveneContext.
Note that those method must import every module they need _inside_ their body in
order to prevent cyclic references.

If called on an invalid target, the method should return None.
"""
import logging
logger = logging.getLogger(__name__)

from json import dumps

def absolute_url(target, context):
    """Return the absolute URL of the element.
    """

    import advene.model.annotation
    import advene.model.content
    import advene.model.fragment
    import advene.model.package
    import advene.model.query
    import advene.model.schema
    import advene.model.view
    import advene.model.resources

    def _abs_url(target):
        if isinstance(target, advene.model.annotation.Annotation):
            return '/annotations/%s' % target.getId()
        elif isinstance(target, advene.model.annotation.Relation):
            return '/relations/%s' % target.getId()
        elif isinstance(target, advene.model.package.Package):
            return ''
        elif isinstance(target, advene.model.query.Query):
            return '/queries/%s' % target.getId()
        elif isinstance(target, advene.model.schema.Schema):
            return '/schemas/%s' % target.getId()
        elif isinstance(target, advene.model.schema.AnnotationType):
            return '/schemas/%s/annotationTypes/%s' % \
                                    (target.getSchema().getId(), target.getId())
        elif isinstance(target, advene.model.schema.RelationType):
            return '/schemas/%s/relationTypes/%s' % \
                                    (target.getSchema().getId(), target.getId())
        elif isinstance(target, advene.model.view.View):
            return '/views/%s' % target.getId()
        elif isinstance(target, (advene.model.resources.ResourceData,
                                 advene.model.resources.Resources) ):
            return '/resources/%s' % target.resourcepath
        else:
            return None

    path = _abs_url(target)

    if path is None:
        if context is None:
            return None
        resolved_stack = context.locals['__resolved_stack']
        if resolved_stack is None or len (resolved_stack) == 0:
            return None
        suffix = [resolved_stack[0][0]]
        for i in resolved_stack[1:]:
            name, obj = i
            path = _abs_url (obj)
            if path is not None:
                path = "%s/%s" % (path, "/".join (suffix))
                break
            else:
                suffix.insert (0, name)
        #print "Generated %s" % path

    if path is not None and context is not None:
        options = context.globals['options']
        if 'package_url' in options:
            path = '%s%s' % (options['package_url'], path)
    return path

def isa (target, context):
    """Check the type of an element.

    Return an object such that target/isa/[viewable_class],
    target/isa/[viewable_type] and target/isa/[viewable_class]/[viewble_type]
    are true for the correct values of viewable_class and viewable_type.
    Note that for annotations and relations, viewable_type must be the QName
    for of the type URI.

    Note that for contents, viewable_type can be a two part path, corresponding
    to the usual mime-type writing. The star ('*') character, however, is not
    supported. For example, if c1 has type 'text/*' and c2 has type
    'text/plain', the following will evaluate to True: c1/isa/text,
    c2/isa/text, c1/isa/text/html; the following will of course evaluate to
    False: c2/isa/text/html.
    """
    class my_dict (dict):
        def __init__ (self, values=None, default=False):
            dict.__init__(self)
            self.__default = default
            if values:
                for k, v in values.items():
                    self[k]=v

        def __contains__(self, key):
            return True

        def __getitem__ (self, key):
            if key in dict:
                return dict.__getitem__ (self, key)
            else:
                return self.__default

        def merge (self, dico):
            for k, v in dico.items():
                self[k]=v

    try:
        viewable_class = target.getViewableClass()
    except AttributeError:
        return my_dict({'unknown':True})

    r = my_dict ({viewable_class:True})
    if viewable_class == 'content':
        t1, t2 = target.getMimetype ().split ('/')
        vt1 = my_dict ({t2:True})
        mimetype_dict = my_dict ({t1:vt1})
        r[viewable_class] = mimetype_dict
        r.merge (mimetype_dict)
    elif viewable_class in ('annotation', 'relation'):
        viewable_type = target.getType ().getId ()
        d1 = my_dict ({viewable_type:True})
        r[viewable_class] = d1
        r.merge (d1)
    elif viewable_class == 'list':
        viewable_type = target.getViewableType ()
        list_dict = ({viewable_type:True})
        r[viewable_class] = list_dict
        r.merge (list_dict)

    return r

def meta(target, context):
    """Access to meta attributes.

    Function to be used as a TALES global method, in order to give access
    to meta attributes.

    This function assumes that the 'options' of the TALES context have a
    dictionnary named 'namespace_prefix', whose keys are prefices and whose
    values are corresponding namespace URIs.

    The use of this function is (assuming that here is a Metaed object):
    here/meta/dc/version
    for example (where prefix 'dc' has been mapped to the Dublin Core
    namespace URI in 'namespace_prefix'.
    """

    import advene.model._impl

    class MetaNameWrapper:
        def __init__(self, target, namespace_uri):
            self.__target = target
            self.__namespace_uri = namespace_uri

        def __contains__(self, key):
            return self[key] is not None

        def __getitem__(self, key):
            return self.__target.getMetaData(self.__namespace_uri, key)

    class MetaNSWrapper:
        def __init__(self, target, context):
            self.__target = target
            options = context.globals['options']
            self.__ns_dict = options.get('namespace_prefix', {})

        def __contains__(self, key):
            return key in self.__ns_dict

        def __getitem__(self, key):
            if key in self.__ns_dict:
                return MetaNameWrapper(self.__target, self.__ns_dict[key])
            else:
                return None

        def keys(self):
            return list(self.__ns_dict.keys())

    if isinstance (target, advene.model._impl.Metaed):
        r = MetaNSWrapper (target, context)
        return r
    else:
        return None

def view(target, context):
    """Apply a view on an element.

    """
    import advene.model.viewable
    import advene.model.exception

    class ViewWrapper:

        """
        Return a wrapper around a viewable (target), having the two following
        bevaviours:
         - it is a callable, running target.view() when invoked
         - it is a dictionnary, returning a callable running target.view(key)
           on __getitem__

        The reason why all returned objects are callable is to prevent view
        evaluation when not needed (e.g., in expressions like
        here/view/foo/absolute_url)
        """

        def __init__ (self, target, context):
            if not isinstance(target, advene.model.viewable.Viewable):
                raise advene.model.exception.AdveneException ("Trying to ViewWrap a non-Viewable object %s" % target)
            self._target = target
            self._context = context

        def __call__ (self):
            return self._target.view (context=self._context)

        def __contains__ (self, key):
            v = self._target._find_named_view (key, self._context)
            return v is not None

        def __getitem__ (self, key):
            def render ():
                return self._target.view (view_id=key, context=self._context)
            return render

        def ids (self):
            """
            Returns the ids of views from the root package which are valid for
            this object.

            Note that such IDs may not work in every context in TALES.
            """
            return self._target.getValidViews()

        def keys (self):
            """
            Returns the ids of views from the root package which are valid for
            this object.

            Note that such IDs may not work in every context in TALES.
            """
            return self._target.getValidViews()

    if not isinstance (target, advene.model.viewable.Viewable):
        if hasattr(target, '__len__'):
            target = advene.model.viewable.GenericViewableList(target, context.locals['__resolved_stack'])
        else:
            target = advene.model.viewable.GenericViewable(target, context.locals['__resolved_stack'])
    return context.wrap_nocall(ViewWrapper (target, context))

def snapshot_url (target, context):
    """Return the URL of the snapshot for the given annotation or fragment.

    It can be applied to an annotation, a fragment or a millisecond
    position (integer).
    """
    import advene.model.annotation
    import advene.model.fragment

    begin=""
    p=None
    if isinstance(target, advene.model.annotation.Annotation):
        begin = target.fragment.begin
        p=target.rootPackage
    elif isinstance(target, advene.model.fragment.MillisecondFragment):
        begin = target.begin
        p=target.rootPackage
    elif isinstance(target, int):
        begin=target
        # Use the current package
        p=context.evaluateValue('package')
    else:
        return None

    options = context.globals['options']
    return "/packages/%s/imagecache/%s" % (options['aliases'][p],
                                           str(begin))

def player_url (target, context):
    """Return the URL to play the video from the element position.

    The element can be an annotation, a fragment or a millisecond
    position (integer).
    """
    import advene.model.annotation
    import advene.model.fragment
    import urllib.request, urllib.parse, urllib.error

    begin=""
    end=None
    p=None
    if isinstance(target, advene.model.annotation.Annotation):
        begin = target.fragment.begin
        end = target.fragment.end
        p=target.rootPackage
    elif isinstance(target, advene.model.fragment.MillisecondFragment):
        begin = target.begin
        end = target.end
        p=target.rootPackage
    elif isinstance(target, int):
        begin=target
    else:
        return None

    base_url = "/media/play/%s" % str(begin)
    if end is not None:
        base_url = base_url + "/" + str(end)

    package=context.evaluateValue('package')
    if p is None or p == package:
        return base_url
    else:
        c=context.evaluateValue('options/controller')
        return base_url + "?" + urllib.parse.urlencode( {'filename': c.get_default_media(p)} )

def formatted (target, context):
    """Return a formatted timestamp as hh:mm:ss.mmmm

    This method applies to either integers (in this case, it directly
    returns the formated string), or to fragments. It returns a
    dictionary with begin, end and duration keys.
    """
    import advene.model.fragment
    from advene.util.helper import format_time

    if isinstance(target, int):
        return format_time(target)

    if not isinstance(target, advene.model.fragment.MillisecondFragment):
        return None

    res = {
        'begin': '--:--:--.---',
        'end'  : '--:--:--.---',
        'duration': '--:--:--.---'
        }
    for k in res:
        t=getattr(target, k)
        res[k] = format_time(t)
    res['begin_s'] = target.begin / 1000.
    res['end_s'] = target.end / 1000.
    return res

def first (target, context):
    """Return the first item of target.

    Return the first element of =target=, which must obviously be a list-like
    object.
    """
    if callable(target):
        t=target()
    else:
        t=target
    if t:
        return t[0]
    else:
        return None

def last (target, context):
    """Return the last item of target.

    Return the last element of =target=, which must obviously be a list-like
    object.
    """
    if callable(target):
        t=target()
    else:
        t=target
    if t:
        return t[-1]
    else:
        return None

def rest (target, context):
    """Return all but the first items of target.

    Return all elements of target but the first. =target= must obvioulsly be a
    list-like, sliceable object.
    """
    if callable(target):
        t=target()
    else:
        t=target
    return t[1:]

def query(target, context):
    """Apply a query on target.

    """
    class QueryWrapper:

        """
        Return a wrapper around an element (target), having the  following
        bevaviour:
         - it is a dictionnary, returning a callable running target.query(key)
           on __getitem__

        The reason why all returned objects are callable is to prevent view
        evaluation when not needed (e.g., in expressions like
        here/query/foo/absolute_url)
        """

        def __init__ (self, target, context):
            self._target = target
            # Note: we are in a wrapper. self._context is the context
            # of the query method target, i.e. package for instance, and not
            # of the query itself.
            self._context = context

        def _get_query_by_id(self, key):
            try:
                queries = self._target.rootPackage.queries
            except AttributeError:
                # We are querying an element that has no rootPackage
                # (a list for instance). So fallback to the context
                # package global.
                queries = self._context.globals['package'].queries
            qlist = [ q for q in queries if q.id == key ]
            if qlist:
                return qlist[0]
            else:
                return None

        def __contains__(self, key):
            return self._get_query_by_id(key)

        def __getitem__ (self, key):
            #print "getitem %s" % key
            def render ():
                # Key is the query id
                q=self._get_query_by_id(key)
                if not q:
                    raise KeyError("The query %s cannot be found" % key)
                c=context.globals['options']['controller']
                self._context.pushLocals()
                self._context.setLocal('here', self._target)
                res, qexpr=c.evaluate_query(q, context=self._context)
                self._context.popLocals()
                return res
            return render

        def ids (self):
            """
            Returns the ids of views from the root package which are valid for
            this object.

            Note that such IDs may not work in every context in TALES.
            """
            return [ q.id for q in self._target.rootPackage.queries ]

        def keys (self):
            """
            Returns the ids of views from the root package which are valid for
            this object.

            Note that such IDs may not work in every context in TALES.
            """
            return self.ids()

    return QueryWrapper(target, context)

def sorted (target, context):
    """Return a sorted list

    This method applies either to list of annotations, that will be
    sorted according to their positions, or to any list of comparable
    items.
    """
    from advene.model.annotation import Annotation
    from advene.model.fragment import AbstractNbeFragment

    if hasattr(target, 'viewableType') and target.viewableType == 'annotation-list' or (
            isinstance(target, list) and len(target) > 0 and hasattr(target[0], 'fragment')):
        items = list(target[:])
        items.sort(key=lambda e: e.fragment.begin)
    elif hasattr(target, '__getslice__') and len(target) > 0 and isinstance(target[0], (Annotation,
                                                                                        AbstractNbeFragment,
                                                                                        int,
                                                                                        float,
                                                                                        str)):
        items = list(target[:])
        items.sort()
    elif (hasattr(target, '__getslice__') and len(target) > 0 and hasattr(target[0], 'title')):
        items = list(target[:])
        items.sort(key=lambda e: e.title or e.id)
    else:
        items = target
    return items

def length(target, context):
    """Return the length of the target.
    """
    return len(target)

def randompick(target, context):
    """Return a random element from the target.
    """
    import random
    try:
        e=random.choice(target)
    except IndexError:
        # If list is empty, or target is not a list
        e=None
    return e

def old_related(target, context):
    """Return the related annotation.

    This is a shortcut for the case where there is only 1 binary
    relation.

    We search first outgoingRelations. If none exist, we check
    incomingRelations.
    """
    try:
        r=target.outgoingRelations
    except AttributeError:
        # Not an annotation
        return None
    if r:
        return r[0].members[-1]
    r=target.incomingRelations
    if r:
        return r[0].members[0]
    return None

def tag_color(target, context):
    """Return a color matching one of the tags.
    """
    c=context.globals['options']['controller']
    return c.get_tag_color_for_element(target)

def value_color(target, context):
    """Return a color matching the value metadata.
    """
    c=context.globals['options']['controller']
    return c.get_tag_color_for_element(target)

def representation(target, context):
    """Return a concise representation for the element.
    """
    #c=context.evaluateValue('options/controller')
    c=context.globals['options']['controller']
    return c.get_title(target)

def color(target, context):
    """Return the color of the element.
    """
    from advene.model.annotation import Annotation, Relation
    from advene.model.schema import AnnotationType, RelationType
    import re

    if isinstance(target, (Annotation, Relation, AnnotationType, RelationType)):
        # The proper way would be
        # c=context.evaluateValue('options/controller')
        # but the following is a mediocre optimization
        c=context.globals['options']['controller']
        col=c.get_element_color(target)
        if col is None:
            return col
        m=re.search('#(..)..(..)..(..)..', col)
        if m:
            # Approximate the color, since CSS specification only
            # allows 24-bit color definition
            return '#'+''.join(m.groups())
        else:
            return col
    else:
        return None

def transition_fix_ns(target, context):
    """Replace old namespaces into new ones.

    This method is used by the Advene1->Advene2 export filter.
    """
    if isinstance(target, str):
        return target.replace("http://experience.univ-lyon1.fr/advene/ns/advenetool",
                              "http://advene.org/ns/advene-application/2.0")
    else:
        return str

def transition_fix_date(target, context):
    """Reformat dates into iso8601 format.

    This method is used by the Advene1->Advene2 export filter.
    """
    import re
    import datetime
    m=re.search(r'(\d\d\d\d)-(\d\d?)-(\d\d)', target)
    if m:
        return datetime.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    else:
        return target

def urlquote(target, context):
    """Percent-encode the given string.
    """
    import urllib.request, urllib.parse, urllib.error
    return urllib.parse.quote(str(target).encode('utf-8'))

def json(target, context):
    """JSON-encode the parameter.
    """
    def default_repr(o):
        if callable(o):
            return o()
        if hasattr(o, '__iter__'):
            return list(o)
        return str(o)

    try:
        ret = dumps(target,
                    default=default_repr,
                    skipkeys=True,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=4)
    except Exception as e:
        return dumps({
            "_ERROR": e.message
            })
    return ret

def export(target, context):
    """Apply an export filter to the target.
    """
    from advene.util.exporter import get_exporter
    from advene.util.tools import TypedUnicode
    import io

    class ExporterWrapper:
        """Return a wrapper around an element (target)

         It is a dictionnary, returning a callable running
           get_exporter(exportername).export(target) on __getitem__

        The reason why all returned objects are callable is to prevent view
        evaluation when not needed (e.g., in expressions like
        here/view/foo/absolute_url)
        """

        def __init__ (self, target, context):
            self._target = target
            self._context = context

        def __contains__ (self, key):
            v = get_exporter(key)
            return v is not None

        def __getitem__ (self, key):
            def render ():
                ex = get_exporter(key)
                with io.StringIO() as buf:
                    self._context.globals['options']['controller'].apply_export_filter(self._target, ex, filename=buf)
                    res = TypedUnicode(buf.getvalue())
                res.contenttype = ex.mimetype
                return res

            return render

        def ids (self):
            """Returns the ids of valid exporters
            """
            return list(get_exporter().keys())

        def keys (self):
            """Returns the ids of valid exporters
            """
            return list(get_exporter().keys())

        def __str__(self):
            return "export global method. Use /keys to see what filters are available."

    return context.wrap_nocall(ExporterWrapper(target, context))
