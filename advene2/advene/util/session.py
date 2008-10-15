"""
A module for managing session-wide global data.

This module provides the ``session`` object, storing variables on a per-thread
basis: each thread has its own values for the session variables.

A set of session variables are predefined and have a default value (use
``session._dir()`` to get a list of them). User-defined session variables can
be used butg must be prefixed with "x_".

All errors (trying to read or delete an non-existant session variable, or
trying to set an invalid one) raise AttributeError.

E.g.::
    from advene.util.session import session
    session.package = some_package
    session.user = "pchampin"
    session.x_info = "some additional info"
    # those variables are only set in the scope of the current thread
"""

import os
import sys
from threading import local
from shutil import rmtree

class _Session(object):
    def __init__(self, **kw):
        self._default = dict(kw)
        self._data = local()

    def __getattr__(self, name):
        r = getattr(self._data, name, None)
        if r is None:
            try:
                r = self._default[name]
            except KeyError, e:
                raise AttributeError(*e.args)
        return r

    def __setattr__(self, name, value):
        if name[0] == "_":
            return object.__setattr__(self, name, value)
        if name not in self._default and name[:2] != "x_":
            raise AttributeError("%s is not a session variable "
                                 "(use 'x_%s' instead)" % (name, name))
        setattr(self._data, name, value)

    def __delattr__(self, name):
        if name[0] == "_":
            return object.__delattr__(self, name)
        delattr(self._data, name)

    def _dir(self):
        r1 = frozenset(self._default.iterkeys())
        r2 = frozenset(i for i in dir(self._data) if i[0] != "_")
        r = r1.union(r2)
        return list(r)

tempdir_list = []

def cleanup():
    """Remove the temp. directories used during the session.

    No check is done to see wether it is in use or not. This
    method is intended to be used at the end of the application,
    to clean up the mess.
    """
    for d in tempdir_list:
        print "Cleaning up %s" % d
        if os.path.isdir(d.encode(sys.getfilesystemencoding())):
            rmtree(d, ignore_errors=True)

session = _Session(
    package = None,
    user = None,)
