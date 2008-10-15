"""
I provi to de mechanisms similar to the ``synchronized`` keyword in Java.

The idea is to associate a reentrant lock to each object, with the possibility
for a section of code to claim that lock. Functions `enter_cs` and `exit_cs`
can be used for synchronizing any section of code on any object, while the
`synchronized` decorator can be used to synchronize a whole method on its
``self`` parameter.
"""

from threading import Lock, RLock

# the following global lock is used to prevent several locks being created
# for the same object
_sync_lock = Lock()

def enter_cs(obj):
    """
    Enter a critical section on `obj`.
    """
    _sync_lock.acquire()
    try:
        L = obj.__rlock
    except AttributeError:
        L = obj.__rlock = RLock()
    finally:
        _sync_lock.release()
    L.acquire()

def exit_cs(obj):
    """
    Exit a critical section on `obj`.
    """
    obj.__rlock.release()

def synchronized(f):
    """
    A decorator for synchronized methods (alla Java).
    """
    def synchronized_f(self, *a, **kw):
        enter_cs(self)
        try:
            return f(self, *a, **kw)
        finally:
            exit_cs(self)
    synchronized_f.__name__ = f.__name__
    synchronized_f.__doc__ = f.__doc__
    return synchronized_f
