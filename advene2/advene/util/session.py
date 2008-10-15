"""
A module for managing session-wide global data.

This module provides the ``session`` object, storing variables on a per-thread
basis: each thread has its own values for the session variables.

A set of session variables are predefined and have a default value (the dict
``get_session_defaults`` returns them in a dict). User-defined session
variables can be used but must be prefixed with "x_". Note that deleting a
predefined session variable does not actually deletes it but restores it to its 
default value.

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

_session_defaults = {"package": None, "user": os.getlogin()}

def get_session_defaults():
    return _session_defaults.copy()

class _Session(local):
    def __init__(self):
        for k,v in _session_defaults.iteritems():
            self.__dict__[k] = v

    def __setattr__(self, name, value):
        if not hasattr(self, name) and name[:2] != "x_":
            raise AttributeError("%s is not a session variable "
                                 "(use 'x_%s' instead)" % (name, name))
        self.__dict__[name] = value

    def __delattr__(self, name):
        if hasattr(self, name) and name[:2] != "x_":
            setattr(self, name, _session_defaults[name])
        else:
            del self.__dict__[name]

    def _dir(self):
        return [ n for n in dir(self) if n[0] != "_" ]

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

session = _Session()
