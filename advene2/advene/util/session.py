"""
A module for managing session-wide global data.

This module provides the ``session`` object, storing variables on a per-thread
basis: each thread has its own values for the session variables.

A set of session variables are predefined and have a default value (use
``session._dir()`` to get a list of them). User-defined session variables can
be used butg must be prefixed with "x_".

All errors (trying to read or delete an non-existant session variable, or
trying to set an invalid one) raise KeyError.

A thread using session variables should call ``session._clean()`` before
terminating, in order to free memory space occupied by its session variables.

E.g.::
    from advene.util.session import session
    session.package = some_package
    session.user = "pchampin"
    session.x_info = "some additional info"
    # those variables are only set in the scope of the current thread
"""

from thread import get_ident, allocate_lock

class _Session(object):
    def __init__(self, **kw):
        self._default = dict(kw)
        self._dicts = {}
        self._lock = allocate_lock()

    def __getattribute__(self, name):
        if name[0] == "_":
            return object.__getattribute__(self, name)

        L = self._lock
        thread_id = get_ident()
        L.acquire()
        try:
            d = self._dicts.get(thread_id)
            if d is None or name not in d:
                return self._default[name]
            else:
                return d[name]
        finally:
            L.release()

    def __setattr__(self, name, value):
        if name[0] == "_":
            return object.__setattr__(self, name, value)
        if name not in self._default and name[:2] != "x_":
            raise KeyError("%s is not a session variable "
                           "(use 'x_%s' instead" % (name, name))
        L = self._lock
        thread_id = get_ident()
        _dicts = self._dicts
        L.acquire()
        try:
            d = _dicts.get(thread_id)
            if d is None: d = _dicts[thread_id] = {}
            d[name] = value
        finally:
            L.release()

    def __delattr__(self, name):
        if name[0] == "_":
            return object.__delattr__(self, name)

        L = self._lock
        thread_id = get_ident()
        _dicts = self._dicts
        L.acquire()
        try:
            d = _dicts.get(thread_id)
            if d is None: d = _dicts[thread_id] = {}
            del d[name]
        finally:
            L.release()

    def _dir(self):
        L = self._lock
        thread_id = get_ident()
        L.acquire()
        r1 = frozenset(self._default.iterkeys())
        r2 = frozenset(self._dicts.get(thread_id, {}).iterkeys())
        r = r1.union(r2)
        L.release()
        return list(r)

    def _clean(self):
        L = self._lock
        thread_id = get_ident()
        L.acquire()
        try:
            del self._dicts[thread_id]
        finally:
            L.release()


session = _Session(
    package = None,
    user = None,
)
