def lowerFirstChar(str):
    first = str[0].lower()
    rest = str[1:]
    return first+rest

def upperFirstChar(str):
    first = str[0].upper()
    rest = str[1:]
    return first+rest

class auto_properties(type):
    """Metaclass automatically defining properties.

    If a "getFoo" or "setFoo" method is defined, then so will be the
    correponding property "foo".  """
    
    def __init__(cls, name, bases, dict):
        super(auto_properties, cls).__init__(name, bases, dict)
        props = {}
        for name, f in dict.iteritems():
            try:
                nb_args = (f.func_code.co_argcount
                           - len (f.func_defaults or ()))
            except AttributeError:
                continue
            propname = None
            if name.startswith("get"):
                if nb_args == 1:
                    propname=lowerFirstChar(name[3:])
            if name.startswith("set"):
                if nb_args == 2:
                    propname=lowerFirstChar(name[3:])
            if propname:
                props[propname] = 1

        for propname in props.iterkeys ():
            fget = getattr(cls, "get%s" % upperFirstChar(propname), None)
            fset = getattr(cls, "set%s" % upperFirstChar(propname), None)
            fdel = getattr(cls, "del%s" % upperFirstChar(propname), None)
            setattr(cls, propname, property(fget, fset, fdel))


if __name__ == "__main__":
    class Test(object):
        __metaclass__ = auto_properties

        def getTheA(self): return self._a

        def setTheB(self,v): self._b = v

        def getTheC(self): return self._c
        def setTheC(self,v): self._c = v

        def getTheD(self): return self._d
        def setTheD(self,v): self._d = v
        def delTheD(self,v): del self._d

        def delTheE(self, e): del self._e

    t = Test()
