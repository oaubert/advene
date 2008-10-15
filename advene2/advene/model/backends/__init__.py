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
