#
# This file is part of Advene.
# 
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

class AutoPropertiesMetaclass(type):
    """Metaclass automatically defining properties.

    If a "_get_foo" or "_set_foo" method is defined, then so will be the
    correponding property "foo"."""
    
    def __init__(self, name, bases, dict):
        cls=self
        super(AutoPropertiesMetaclass, cls).__init__(name, bases, dict)
        props = {}
        for name, f in dict.iteritems():
            try:
                nb_args = (f.func_code.co_argcount
                           - len (f.func_defaults or ()))
            except AttributeError:
                continue
            propname = None
            if name.startswith("_get_"):
                if nb_args == 1:
                    propname = name[5:]
            if name.startswith("_set_"):
                if nb_args == 2:
                    propname = name[5:]
            if propname:
                props[propname] = 1

        for propname in props.iterkeys ():
            fget = getattr(cls, "_get_%s" % propname, None)
            fset = getattr(cls, "_set_%s" % propname, None)
            fdel = getattr(cls, "_del_%s" % propname, None)
            setattr(cls, propname, property(fget, fset, fdel))


if __name__ == "__main__":
    class Test(object):
        __metaclass__ = AutoPropertiesMetaclass

        def _get_the_a(self): return self._a

        def _set_the_b(self,v): self._b = v

        def _get_the_c(self): return self._c
        def _set_the_c(self,v): self._c = v

        def _get_the_d(self): return self._d
        def _set_the_d(self,v): self._d = v
        def _del_the_d(self,v): del self._d

        def _del_the_e(self, e): del self._e

    t = Test()
