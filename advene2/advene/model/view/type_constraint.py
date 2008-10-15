"""I am the content handler for mimetype application/x-advene-type-constraint.
"""

from advene.model.exceptions import ContentHandlingError

from gettext import gettext as _

# general handler interface

def claims_for_handle(mimetype):
    """Is this view_handler likely to handle a view with that mimetype.

    Return an int between 00 and 99, indicating the likelyhood of this handler
    to handle correctly the given mimetype. 70 is used as a standard value when
    the hanlder is pretty sure it can handle the mimetype.
    """
    if mimetype == "application/x-advene-type-constraint":
        return 99
    else:
        return 0

def get_output_mimetype(view):
    """Return the mimetype of the content produced by that view.

    Note that the output mimetype may depend on the mimetype of the view, as
    well as the content of the view itself, but should not depend on the
    element the view is applied to.
    """
    return "application/x-advene-diagnosis"
    # note that application/x-advene-diagnosis is represented by the class
    # Diagnosis below.
    # An empty diagnosis means 'True', while a non-empty diagnosis means 'False'
    # diagnosis can be added (as well as added to an empty string).

def apply_to(view, obj):
    params = view.content_parsed
    r = Diagnosis()
    for k,v in params.iteritems():
        if k == "mimetype":
            mimetype = getattr(obj, "content_mimetype")
            if mimetype is not None and not check_mimetype(v, mimetype):
                r.append(
                  "%(uri)s: mimetype %(mimetype)s does not match %(expected)s",
                  uri = obj.uriref, expected = v,
                  mimetype = obj.content_mimetype,
                )
        else:
            raise ContentHandlingError(
                    "unknown type-constraint parameter: %s" % k
            )
    return r

def check_mimetype(expected, actual):
    e1, e2 = expected.split("/")
    a1, a2 = actual.split("/")
    return (e1 == "*" or a1 == e1) and (e2 == "*" or a2 == e2)

class Diagnosis(object):
    def __init__(self, value=None):
        assert value is None or isinstance(value, list)
        if value is None:
            value = []
        self._v = value

    def __nonzero__(self):
        return len(self._v) == 0

    def __iter__(self):
        for template, args in self._v:
            yield _(template) % args

    def __str__(self):
        return "\n".join(self)

    def __repr__(self):
        return "Diagnosis(%r)" % self._v

    def __and__(self, rho):
        if isinstance(rho, Diagnosis):
            return Diagnosis(self._v + rho._v)
        elif not rho:
            return rho
        else:
            return self

    def __rand__(self, lho):
        if isinstance(lho, Diagnosis):
            return Diagnosis(lho + self._v)
        elif lho:
            return self
        else:
            return lho

    def append(self, template, **args):
        self._v.append((template, args))

#
