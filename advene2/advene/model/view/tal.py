"""I am the content handler for any mimetype of the form X/Y+tal.

Note that X/Y must be either text/html or an XML based mimetype.
"""

from advene.model.tales import AdveneContext

from cStringIO import StringIO
from simpletal import simpleTAL

# general handler interface

def claims_for_handle(mimetype):
    """Is this view_handler likely to handle a view with that mimetype.

    Return an int between 00 and 99, indicating the likelyhood of this handler
    to handle correctly the given mimetype. 70 is used as a standard value when
    the hanlder is pretty sure it can handle the mimetype.
    """
    if mimetype.endswith("+tal"):
        return 70
    else:
        return 0

def get_output_mimetype(view):
    """Return the mimetype of the content produced by that view.

    Note that the output mimetype may depend on the mimetype of the view, as
    well as the content of the view itself, but should not depend on the
    element the view is applied to.
    """
    return view.content_mimetype[:-4]

def apply_to(view, obj, refpkg=None):
    f = view.get_content_as_file()
    html = view.content_mimetype.startswith("text/html")
    if html:
        t = simpleTAL.compileHTMLTemplate(f, "utf-8")
        kw = {}
    else:
        t = simpleTAL.compileXMLTemplate(f)
        kw = { "suppressXMLDeclaration": 1 }
        # It is a bit ugly to suppress XML declaration, but necessary when XML
        # views are used inside other XML views.
        # Furthermore, this does not seem to serious a ugliness, since we use
        # UTF-8 # encoding, which appears to be the default (at least for
        # simpleTAL generator), and since the XML spec allows well-formed
        # documents to have no XML declaration.
    f.close()

    # should we cache the compiled template for future uses,
    # and recompile it only when the content is changed?
    # the problem is that external contents may be changed without notification
    # (or rely on f.headers['date'], but that would require to hack content.py
    #  to make that field *always* present - might be a good idea...)

    c = AdveneContext(here=obj)
    c.addGlobal("view", view)
    if refpkg is None:
        if hasattr(obj, "ADVENE_TYPE"):
            refpkg = obj.owner
        else:
            refpkg = obj
    c.addGlobal("refpkg", refpkg)
    out = StringIO()
    t.expand(c, out, outputEncoding="utf-8", **kw)
    return out.getvalue()

# specific to this handler

