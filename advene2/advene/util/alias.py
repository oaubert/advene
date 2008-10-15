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

"""
I define the alias decorator.

The alias decorator aims at replacing the following code inside a class body:

  method_a = method_b

by the following code, considered better:

  @alias(method_b)
  def method_a(self):
      # method_a is the same as method_b
      pass

Why is this considered better:
* it actually has the same effect, so has no performance cost at runtime
* there is a statement that looks like a definition of the method (with def),
  and hence will be found by naive tools, such as grep.

Note that it is a good practice to explain as a comment that this is an alias
and why it is so. It is *not* a good practice to do that in a docstring because
that would seem to imply that the aliased object will have that docstring,
while it will in fact have the same docstring as the original: they really are
the same object (think hard-link, not soft-link).
"""

def alias(real_object):
    def make_alias(named_object):
        return real_object
    return make_alias
