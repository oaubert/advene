import advene.model.util.uri

import advene.model._impl as _impl
import advene.model.modeled as modeled
import advene.model.viewable as viewable
import advene.model.content as content

from advene.model.constants import *

from advene.model.util.auto_properties import auto_properties

class Query(modeled.Importable, viewable.Viewable.withClass('query'),
            content.WithContent,
            _impl.Uried, _impl.Authored, _impl.Dated, _impl.Titled):
    """Query object offering query capabilities on the model"""
    __metaclass__ = auto_properties

    def __init__(self, parent=None, ident=None, element=None):
        _impl.Uried.__init__(self, parent=parent)
        doc = parent._getDocument()
        element = doc.createElementNS(self.getNamespaceUri(),
                                      self.getLocalName())
        modeled.Importable.__init__(self, element, parent,
                                    parent.getViews.im_func)

        if ident is None:
            # FIXME: cf thread
            # Weird use of hash() -- will this work?
            # http://mail.python.org/pipermail/python-dev/2001-January/011794.html
            ident = u"q" + unicode(id(self)) + unicode(time.clock()).replace('.','')
        self.setId(ident)
        

    # dom dependant methods

    def getNamespaceUri(): return adveneNS
    getNamespaceUri = staticmethod(getNamespaceUri)

    def getLocalName(): return "query"
    getLocalName = staticmethod(getLocalName)

# simple way to do it,
# QueryFactory = modeled.Factory.of (Query)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class QueryFactory (modeled.Factory.of (Query)):
    """
    FIXME
    """
    pass



