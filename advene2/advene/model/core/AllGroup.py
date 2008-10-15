"""
I define class AllGroup.
"""

from itertools import chain
from advene.utils.itertools import interclass

class AllGroup (object):

    def __init__ (self, owner):
        self._owner = owner

    def __contains__ (self, element):
        if element in self._owner._own: return True
        for imp in self._owner._imports_dict.itervalues():
            if element in imp._all: return True
        return True

    @property
    def streams (self):
        return chain ( self._owner._own.streams,
                       *[ imp._all.streams
                          for imp in self._owner._imports_dict.itervalues() ] )

    @property
    def annotations (self):
        return interclass ( self._owner._own.annotations,
                            *[ imp._all.annotations
                               for imp in self._owner._imports_dict.itervalues() ] )

    @property
    def relations (self):
        return chain ( self._owner._own.relations,
                       *[ imp._all.relations
                          for imp in self._owner._imports_dict.itervalues() ] )

    @property
    def bags (self):
        return chain ( self._owner._own.bags,
                       *[ imp._all.bags
                          for imp in self._owner._imports_dict.itervalues() ] )

    @property
    def imports (self):
        return chain ( self._owner._own.imports,
                       *[ imp._all.imports
                          for imp in self._owner._imports_dict.itervalues() ] )

    @property
    def queries (self):
        return chain ( self._owner._own.queries,
                       *[ imp._all.queries
                          for imp in self._owner._imports_dict.itervalues() ] )

    @property
    def views (self):
        return chain ( self._owner._own.views,
                       *[ imp._all.views
                          for imp in self._owner._imports_dict.itervalues() ] )

    @property
    def resources (self):
        return chain ( self._owner._own.resources,
                       *[ imp._all.resources
                          for imp in self._owner._imports_dict.itervalues() ] )
 
