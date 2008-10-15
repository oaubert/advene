"""I am the content handler for mimetype application/x-advene-builtin-view.
"""

from inspect import getargspec

from advene.model.consts import _RAISE
from advene.model.core.element import \
    MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.exceptions import ContentHandlingError

# general handler interface

def claims_for_handle(mimetype):
    """Is this view_handler likely to handle a view with that mimetype.

    Return an int between 00 and 99, indicating the likelyhood of this handler
    to handle correctly the given mimetype. 70 is used as a standard value when
    the hanlder is pretty sure it can handle the mimetype.
    """
    if mimetype == "application/x-advene-builtin-view":
        return 99
    else:
        return 0

def get_output_mimetype(view):
    """Return the mimetype of the content produced by that view.

    Note that the output mimetype may depend on the mimetype of the view, as
    well as the content of the view itself, but should not depend on the
    element the view is applied to.
    """
    global _methods
    params = view.content_parsed
    return _methods[params["method"]].info["output_mimetype"]

def apply_to(view, obj):
    global _methods
    params = view.content_parsed
    method = params.pop("method")
    m = _methods.get(method, None)
    if m is None:
        raise ContentHandlingError("unknown builtin view method: %s" % method)
    try:
        return _methods[method](obj, **params)
    except TypeError, e:
        raise ContentHandlingError(*e.args)
    

# specific to this handler

def iter_methods():
    global _methods
    return _methods.iterkeys()

def get_method_info(method, default=_RAISE):
    global _methods
    r = _methods.get(method, _RAISE)
    if r is None:
        if default is _RAISE:
            raise KeyError(method)
        else:
            r = default
    else:
        r = r.info.copy()
    return r

# private implementation

def _wrap_method(**info):
    def wrapper(f, info=info):
        global _methods
        _methods[f.__name__] = f
        f.info = info
        info["params"] = getargspec(f)[0][1:]
        return f
    return wrapper

_methods = {}


@_wrap_method(
    output_mimetype = "text/plain",
)
def hello_world(obj):
    return "hello world!"



@_wrap_method(
    output_mimetype = "text/plain",
    type = "one of the following values:\n" \
           " * ANNOTATION\n * IMPORT\n * LIST\n * MEDIA\n * PACKAGE\n * QUERY\n" \
           " * RELATION\n * RESOURCE\n * TAG\n * VIEW\n"""
)
def has_type(obj, type):
    d = { "ANNOTATION": ANNOTATION,
          "IMPORT": IMPORT,
          "LIST": LIST,
          "MEDIA": MEDIA,
          "PACKAGE": "Package",
          "QUERY": QUERY,
          "RELATION": RELATION,
          "RESOURCE": RESOURCE,
          "TAG": TAG,
          "VIEW": VIEW,
        }
    type = d[type]
    ref = getattr(obj, "ADVENE_TYPE", None)
    if ref is None:
        if obj.__class__.__name__ == "Package":
            ref = "Package"
        # TODO are the following heuristics really the good solution?
        elif isinstance(basestring):
            ref = RESOURCE
        else:
            try:
                iter(obj)
            except TypeError:
                ref = None
            else:
                ref = LIST
    if type == ref:
        return "true"
    else:
        return ""


@_wrap_method(
    output_mimetype = "text/plain",
    mimetype = "a mimetype that the element's content mimetype, if any, must "\
               "match"
)
def basic_element_constraint(obj, mimetype=None):
    if mimetype is not None:
        m = getattr(obj, "content_mimetype", None)
        if m is not None:
            if m != mimetype:
                # TODO manage generic mimetypes (with '*')
                return ""
    return "true"

#
