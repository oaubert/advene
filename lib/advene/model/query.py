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
import time

import advene.model._impl as _impl
import advene.model.modeled as modeled
import advene.model.viewable as viewable
import advene.model.content as content

from advene.model.constants import adveneNS

from advene.model.util.auto_properties import auto_properties

class Query(modeled.Importable, viewable.Viewable.withClass('query'),
            content.WithContent,
            _impl.Uried, _impl.Authored, _impl.Dated, _impl.Titled, metaclass=auto_properties):
    """Query object offering query capabilities on the model"""

    def __init__(self, parent=None, element=None, ident=None, author=None):
        _impl.Uried.__init__(self, parent=parent)
        if element is not None:
            modeled.Importable.__init__(self, element, parent,
                                        parent.getQueries.__func__)
            _impl.Uried.__init__(self, parent=self.getOwnerPackage())
        else:
            doc = parent._getDocument()
            element = doc.createElementNS(self.getNamespaceUri(),
                                          self.getLocalName())
            modeled.Importable.__init__(self, element, parent,
                                        parent.getQueries.__func__)

            if ident is None:
                # FIXME: cf thread
                # Weird use of hash() -- will this work?
                # http://mail.python.org/pipermail/python-dev/2001-January/011794.html
                ident = "q" + str(id(self)) + str(time.clock()).replace('.','')
            self.setId(ident)
            if author is not None:
                self.setAuthor(author)

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
