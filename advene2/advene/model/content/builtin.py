"""I am the content handler for mimetype application/x-advene-builtin-view.
"""

import urllib

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
    r = {}
    for l in obj.content_data.splitlines():
        if not l:
            continue
        if '=' in l:
            key, val = l.split("=", 1)
            key = key.strip()
            r[key] = urllib.unquote_plus(val)
        else:
            r['_error']=l 
            print "Syntax error in content: >%s<" % l.encode('utf8')
    return r
