"""VLC library functions."""

from gettext import gettext as _

import gtk
import gobject
import StringIO

import advene.util.vlclib as vlclib

def image_to_pixbuf (image):
    file = StringIO.StringIO ()
    image.save (file, 'ppm')
    contents = file.getvalue()
    file.close ()
    loader = gtk.gdk.PixbufLoader ('pnm')
    loader.write (contents, len (contents))
    pixbuf = loader.get_pixbuf ()
    loader.close ()
    return pixbuf

def png_to_pixbuf (png_data):
    loader = gtk.gdk.PixbufLoader ('png')
    loader.write (png_data, len (png_data))
    pixbuf = loader.get_pixbuf ()
    loader.close ()
    return pixbuf

def list_selector(title=None,
                  text=None,
                  members=None,
                  controller=None):
    """Pick an element from a list.

    vlclib.get_title is invoked to get a textual representation of
    the elements of members.
    
    Return None if the action is canceled.
    """
    store=gtk.ListStore(
        gobject.TYPE_PYOBJECT,
        gobject.TYPE_STRING
        )
    for el in members:
        store.append( [el,
                       vlclib.get_title(controller, el)] )
    treeview=gtk.TreeView(store)
    treeview.set_headers_visible(False)
    
    renderer = gtk.CellRendererText()
    column = gtk.TreeViewColumn(None, renderer, text=1)
    treeview.append_column(column)

    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                   buttons=( gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT ))

    if text is not None:
        l=gtk.Label(text)
        l.show()
        d.vbox.add(l)

    d.vbox.add(treeview)
    treeview.show()

    res=d.run()
    retval=None
    if res == gtk.RESPONSE_ACCEPT:
        model, iter=treeview.get_selection().get_selected()
        if iter is not None:
            retval=model.get_value(iter, 0)
    d.destroy()
    return retval

def yes_no_cancel_popup(title=None,
                        text=None):
    """Build a Yes-No-Cancel popup window.

    Return codes will be in (gtk.RESPONSE_YES, gtk.RESPONSE_NO, gtk.RESPONSE_CANCEL)
    """
    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                   buttons=( gtk.STOCK_YES, gtk.RESPONSE_YES,
                             gtk.STOCK_NO, gtk.RESPONSE_NO,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

    if text is not None:
        l=gtk.Label(text)
        l.show()
        d.vbox.add(l)        
    retval=d.run()
    d.destroy()
    return retval
