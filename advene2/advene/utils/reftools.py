"""I provide utility functions and class related to weak references.
"""

from weakref import WeakValueDictionary

class WeakValueDictWithCallback(WeakValueDictionary):
    """I extend WeakValueDictionary with a configurable callback function.

    The callback function must be given *before* any value is assigned,
    so WeakValueDictWithCallback does not accept a dict nor keyword arguments
    as __init__ parameters.
    The callback function will be invoked after a key is removed, with that key
    as its only argument.
    """
    def __init__(self, callback):
        WeakValueDictionary.__init__ (self)
        # The superclass WeakValueDictionary assigns self._remove as a
        # callback to all the KeyedRef it creates. So we have to override
        # self._remove.
        # Note however that self._remobe is *not* a method because, as a
        # callback, it can be invoked after the dictionary is collected.
        # So it is a plain function, stored as an *instance* attribute.
        def remove(wr, _callback=callback, _original=self._remove):
            _original(wr)
            _callback(wr.key)
        self._remove = remove
