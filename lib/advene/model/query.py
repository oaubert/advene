#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
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

    def __init__(self, parent=None, element=None, ident=None):
        _impl.Uried.__init__(self, parent=parent)
        if element is not None:
            modeled.Importable.__init__(self, element, parent,
                                        parent.getQueries.im_func)
            _impl.Uried.__init__(self, parent=self.getOwnerPackage())
        else:
            doc = parent._getDocument()
            element = doc.createElementNS(self.getNamespaceUri(),
                                          self.getLocalName())
            modeled.Importable.__init__(self, element, parent,
                                        parent.getQueries.im_func)

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

    def __str__(self):
        """Return a nice string representation of the element"""
        return "Query <%s>" % self.getUri()

# simple way to do it,
# QueryFactory = modeled.Factory.of (Query)

# more verbose way to do it, but with docstring and more
# reverse-engineering-friendly ;)

class QueryFactory (modeled.Factory.of (Query)):
    """
    FIXME
    """
    pass
