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

from sys import _getframe

def autoproperty(*args):
    """Decorate a class method to create or update a property of the class.

    Usage #1:::
        @autoproperty
        def _get_foobar(self):
            # some code

        @autoproperty
        def set_foobar(self, val, option=0)
            # some code

    Usage #2:::
        @autoproperty("foo", "get")
        def bar(self):
            # some code

        @autoproperty
        def baz(self, val):
            # some code

    In the first usage, the name of the property and the role of the method
    (get, set or del) are inferred from the name of the method. The following
    name patterns are recognized: role_name, _role_name, roleName, _roleName,
    where role can be any combination of case. In the two latter cases, the
    first letter of the name will automatically be downcased.

    The docstring of the property is set to the docstring of the first method
    used to define the property.
    """
    L = len(args)
    assert 1 <= L <= 2
    if len(args) == 1:
        func = args[0]
        name, role = _infer_name_and_role(*args)
        return _autoproperty(func, name, role)
    else:
        name, role = args
        return lambda func, n=name, r=role: _autoproperty(func, n, r)


def _infer_name_and_role(method):
    n = method.__name__
    if n[0] == "_": n = n[1:]
    role, name = n[:3].lower(), n[3:]
    if name[0] == "_":
        name = name[1:]
    else:
        name = name[0].lower() + name[1:]
    assert role in ("get", "set", "del")
    return name, role

def _autoproperty(method, name, role):
    ## this is the way it is supposed to be done:
    #locals = inspect.stack()[2][0].f_locals
    ## but that breaks (in python 2.5) so we do it the dirty way:
    locals = _getframe(2).f_locals
    prop = locals.get(name)
    if prop is None:
        kw = {"f%s" % role: method, "doc": method.__doc__}
    else:
        kw = {"fget": prop.fget, "fset": prop.fset, "fdel": prop.fdel,
              "doc": prop.__doc__,}
        kw["f%s" % role] = method
    locals[name] = property(**kw)
    return method



if __name__ == "__main__":
    class Test2(object):

        _foo = None
        _foobar = None

        @autoproperty
        def _get_answer(self):
            """A read only property."""
            return 42

        @autoproperty
        def setFoo(self, val):
            """A dummy property.

            To get this property, use self.foo or self.getFoo(default_value).
            """
            self._foo = val

        @autoproperty
        def getFoo(self, ifNone=None):
            r = self._foo
            if r is None: return ifNone
            else:         return r

        @autoproperty("foo_bar", "get")
        def GetFooBar(self):
            return self._foobar

        @autoproperty("foo_bar", "set")
        def SetFooBar(self, val):
            self._foobar = val

    t2 = Test2()
