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

