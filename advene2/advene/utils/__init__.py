from inspect import stack

def make_property (name):
    """
    This function must be called in the body of a class.
    It looks for _get_X, _set_X and _del_X to create the X property.
    """
    loc = stack()[1][0].f_locals
    getter = loc.get("_get_%s" % name) # None if undefined
    setter = loc.get("_set_%s" % name) # None if undefined
    deller = loc.get("_del_%s" % name) # None if undefined
    doc    = getter.__doc__
    loc[name] = property (getter, setter, deller, doc)

def make_tuple_methods (*names):
    """
    This function must be called in the body of a subclass of tuple.
    It creates methods __new__, __repr__, and as many methods as the names
    provided, returning the corresponding element of the tuple.

    e.g.

        class MyPair (tuple):
            "a lisp-like pair"
            make_tuple_methods ("car", "cdr")
    """
    loc = stack()[1][0].f_locals

    def __new__ (cls, *values):
        if len (values) != len (names):
            raise TypeError, "%s() takes exactly %s argument(s) (%s given)" \
                             % (cls.__name__, len (names), len (values))
        return tuple.__new__ (cls, values)
    loc["__new__"] = __new__

    def __repr__ (self):
        return "%s%s" % (self.__class__.__name__, tuple.__repr__ (self))
    loc["__repr__"] = __repr__

    for i,n in enumerate (names):
        loc[n] = property (lambda self, _i=i: self[_i])

class dict_view (object):
    """
    This callable accepts a dict and return a read only view of that dict.
    """

    def __init__ (self, d):
        self.__d = d

    def __getitem__ (self, key):
        return self.__d[key]

    def __in__ (self, key):
        return key in self.__d

    def __iter__ (self, key):
        return iter (self.__d)

    def __len__ (self):
        return len (self.__d)

    def __repr__ (self):
        return "dict_view(%r)" % (self.__d,)

    def get (self, key, default=None):
        return self.__d.get (key, default)

    def iterkeys (self):
        return self.__d.iterkeys()

    def itervalues (self):
        return self.__d.itervalues()

    def iteritems (self):
        return self.__d.iteritems()

class smart_list_view (object):
    """
    This callable accepts a dict and a list (supposed to contain the same
    elements) and return a mixt read-only view of them.
    """
    def __init__ (self, l, d):
        self.__l = l
        self.__d = d

    def __getitem__ (self, i):
        return self.__l[i]

    def __in__ (self, i):
        return i in self.__l

    def __iter__ (self, i):
        return iter (self.__l)

    def __len__ (self):
        return len (self.__l)

    def __repr__ (self):
        return "smart_list_view(%r)" % (self.__d,)

    def get (self, key, default=None):
        return self.__d.get (key, default)

    def iterkeys (self):
        for i in self.__l:
            yield i.id

    def itervalues (self):
        return iter (self.__l)

    def iteritems (self):
        for i in self._l:
            yield i.id, i
