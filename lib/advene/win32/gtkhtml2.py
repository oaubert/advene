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
"""Dummy gtkhtml2 package"""

import pygtk
#pygtk.require('2.0')
import gtk

class View(gtk.Layout):
    def set_document (self, doc):
        pass
    
class Document:
    def connect (self, *p, **kw):
        pass

    def clear(self):
        pass

    def open_stream(self, contenttype):
        pass

    def write_stream(self, s):
        pass

    def close_stream(self):
        pass

