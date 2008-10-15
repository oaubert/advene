from bisect import bisect, insort

_NO_DEFAULT = object()

class SortedDict(dict):
    __slots__ = ["_keys",]

    def __init__ (self, arg=None, **kw):
        if arg:
            dict.__init__(self, arg, **kw)
        else:
            dict.__init__(self, **kw)
        arg_keys = getattr(arg, "keys", None)
        if callable(arg_keys):
            keys = self._keys = arg_keys()
            self._keys.sort()
        else:
            keys = self._keys = []
            if arg is not None:
                for k,_ in arg:
                    insort(keys, k)
        for k in kw:
            insort(keys, k)

    def __delitem__(self, k):
        if k in self:
            keys = self._keys
            i = bisect(keys, k)
            del keys[i-1:i]
        return dict.__delitem__(self, k)    

    def __setitem__(self, k, v):
        if k not in self:
            insort(self._keys, k)
        return dict.__setitem__(self, k, v)

    def clear(self):
        del self._keys[:]
        return dict.clear(self)

    def pop(self, k, d=_NO_DEFAULT):
        v = dict.pop(self, k, _NO_DEFAULT)
        if v is not _NO_DEFAULT:
            keys = self._keys
            i = bisect(keys, k)
            del keys[i-1:i]
            return v
        elif d is _NO_DEFAULT:
            raise KeyError, k
        else:
            return d

    def popitem(self):
        r = dict.popitem(self)
        keys = self._keys
        i = bisect(keys, r[0])
        del keys[i-1:i]
        return r

    def setdefaults(self, k, d=None):
        v = self.get(k, _NO_DEFAULT)
        if v is _NO_DEFAULT:
            self[k] = d
            v = d
        return v

    def update(self, e=None, **f):
        e_keys = getattr(e, "keys", None)
        if callable(e_keys):
            for k in e_keys():
                self[k] = e[k]
        elif e is not None:
            for k, v in e:
                self[k] = v
        for k, v in f.iteritems():
            self[k] = v

    def keys(self):
        return list(self._keys)

    def values(self):
        return [ self[k] for k in self._keys ]

    def items(self):
        return [ (k, self[k]) for k in self._keys ]

    def iterkeys(self):
        return iter(self._keys)

    def itervalues(self):
        return ( self[k] for k in self._keys )

    def iteritems(self):
        return ( (k, self[k]) for k in self._keys )


if __name__ == "__main__":
    d = SortedDict({"c":"C"}, b="B", d="D")
    print d.items()
    d["a"] = "A"
    print d.items()
    del d["b"]
    print d.items()
    d.pop("e", "E")
    d.pop("d")
    print d.items()
    print d.popitem(),
    print d.items()
    d.update({"b":"BB"}, c="CC")
    d.update([("a", "AA")])
    print d.items()
    print d.setdefaults("a", "AAA"),
    print d.setdefaults("d", "DD"),
    print d.items()
    d.clear()
    print d.items()
    
