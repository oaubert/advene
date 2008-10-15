"""I am the content handler for mimetype application/x-advene-type-constraint.
"""

from advene.model.exceptions import ContentHandlingError

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
    # TODO should that be "application/x-advene-boolean" or sth like that?
    return "text/plain"

def apply_to(view, obj):
    params = view.content_parsed
    r = True
    for k,v in params.iteritems():
        if k == "mimetype":
            mimetype = getattr(obj, "content_mimetype")
            if mimetype is not None and mimetype != v:
                return False
        else:
            raise ContentHandlingError(
                    "unknown type-constraint parameter: %s" % k
            )
        return True

#
