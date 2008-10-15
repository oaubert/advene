"""
Backend implementation
======================

Backends are the part of the Advene implementation that is specific to a given
storage-and-indexing layer. Everything that is independant of that layer is 
implemented in the `advene.model.core` package instead.

A consequence of the dependance-requirement is that consistency checking is
normally not expected from the backend. However, a given backend may chose to
implement some checkings for its internal requirements (indexing, for example).
Note that some consistency checking may also be implemented as ``assert`` to
make debugging easier, but implementations should not rely on those assertions,
since they are not active in optimized code.

TODO: more documentation, including the fact that only one backend instance
should exist for a given "database" (or the like, depending on
implementations).

See the reference implementation `advene.model.backend.sqlite`.
"""

from exceptions import BaseException

# backend register functions

def iter_backends():
    global _backends
    return iter(_backends)

def register_backend(b):
    global _backends
    _backends.insert(0, b)

def unregister_backend(b):
    global _backends
    _backends.remove(b)

# utility class

class ClaimFailure(object):
    """Failure code of a claims_for_* method.

    A ClaimFailure always has a False truth value. Furthermore, it has an
    ``exception`` attribute containing, if not None, an exception explaining
    the failure.
    """

    def __init__(self, exception=None):
        self.exception = exception

    def __nonzero__(self):
        return False

    def __repr__(self):
        return "ClaimFailure(%r)" % self.exception

# backend related exceptions

class NoBackendClaiming(Exception):
    pass

class WrongFormat(Exception):
    """
    I am raised whenever a backend is badly formatted.
    """
    pass

class NoSuchPackage(Exception):
    """
    I am raised whenever a backend is required for an inexisting package.
    """
    pass

class PackageInUse(Exception):
    """
    I am raised whenever an attempt is made to bind a Package instance to a
    backend already bound, or to create an existing (bound or not) Package.
    The message can either be the other Package instance, if available, or the
    package backend url.
    """
    def __str__ (self):
        if isinstance(self.message, basestring):
            return self.message
        else:
            return self.message._id # a package instance
    pass

class InternalError(Exception):
    def __init__(self, msg, original_exception=None, *args):
        self.args = (msg, original_exception) + args
    def __str__(self):
        return "%s\nOriginal message:\n%s" % self.args[:2]

# implementation

_backends = []

# default registration
# NB: do not import sooner, because the sqlite backend relies on the
#     definitions above
import advene.model.backends.sqlite

register_backend(sqlite)
