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
class __UniversalContext:
    def __contains__(self, other):
        return 1

universalContext = __UniversalContext()


class __ContextFactory(dict):
    """A context class manager.
    
       Context classes are registered with the 'register' method.
       They are retrieved with the dict [] operator.
       
       Context classes must verify the following:
       
         - have a getNamespaceUrl() static or class method
         - have a getLocalName() static or class method
         - have a getAttributes() method returning a dict
         - they should be unmutable: the right way of changing the context of
           an annotation is to re-set it rather than modifying the existing one
    """

    def __init__(self):
        dict.__init__(self)

    def __setitem__(self, key, value):
        raise TypeError("read-only dictionnary! use x.register(cls) instead")

    def __getitem__(self, key):
        try:
            return dict__getitem__(self, key)
        except KeyError:
            return _universalContext

    def register(self, cls):
        """Register an element in the context. The key will be obtained with
        cls.getLocalName()"""
        key = cls.getNamespaceUrl(), cls.getLocalName()
        dict.__setitem__(self, key, cls)

contextFactory = __ContextFactory()
