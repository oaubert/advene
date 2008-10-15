"""
Backend implementation
======================

Backends are the part of the Advene implementation that is specific to a given storage-and-indexing layer. Everything that is independant of that layer must be implemented in the ``core`` package instead.

A consequence of the dependance-requirement is that consistency checking is normally not expected from the backend. However, a given backend may chose to implement some checkings for its internal requirements (indexing, for example). Note that some consistency checking may also be implemented as ``assert`` to make debugging easier, but implementations should not rely on those assertions, since they are not active in optimized code.

TODO: more documentation.

See the reference implementation ``sqlite_backend``_.
"""

# backend register functions

def iter_backends():
    global _backends
    return iter (_backends)

def register_backend (b):
    global _backends
    _backends.insert (0, b)

def unregister_backend (b):
    global _backends
    _backends.remove (b)

# backend related exceptions

class NoBackendClaiming (Exception):
    pass

class PackageInUse (Exception):
    pass

class InternalError (Exception):
    def __init__ (self, msg, original_exception=None, *args):
        self.args = (msg, original_exception) + args
    def __str__ (self):
        return "%s\nOriginal message:\n%s" % self.args[:2]

# implementation

_backends = []

import advene.model.backends.sqlite_backend

register_backend (sqlite_backend)
