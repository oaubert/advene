"""I am the content handler for mimetype application/x-advene-builtin-view.
"""

from inspect import getargspec

from advene.model.consts import _RAISE
from advene.model.core.element import \
    MEDIA, ANNOTATION, RELATION, TAG, LIST, IMPORT, QUERY, VIEW, RESOURCE
from advene.model.exceptions import ContentHandlingError

# general handler interface

def claims_for_handle(mimetype):
    """Is this content likely to handle a content with that mimetype.

    Return an int between 00 and 99, indicating the likelyhood of this handler
    to handle correctly the given mimetype. 70 is used as a standard value when
    the hanlder is pretty sure it can handle the mimetype.
    """
    if mimetype == "application/x-advene-builtin-view":
        return 99
    else:
        return 0

def parse_content(obj):
    """
    Parse the content of the given package element, and return the produced
    object.
    """
    s = obj.content_data
    r = {}
    for line in s.split("\n"):
        line = line.strip()
        if line == "": continue
        key, val = line.split("=")
        key = key.strip()
        val = val.strip()
        r[key] = val
    return r
