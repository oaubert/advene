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
    """Load PNG data into a pixbuf
    """
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

    def button_cb(widget=None, event=None):
        if event.type == gtk.gdk._2BUTTON_PRESS:
            # Validate the activated entry on double click.
            d.response(gtk.RESPONSE_ACCEPT)
            return True
        return False
    treeview.connect("button_press_event", button_cb)

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

    Return codes are in (gtk.RESPONSE_YES, gtk.RESPONSE_NO, gtk.RESPONSE_CANCEL)
    """
    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                   buttons=( gtk.STOCK_YES, gtk.RESPONSE_YES,
                             gtk.STOCK_NO, gtk.RESPONSE_NO,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

    hb=gtk.HBox()
    hb.show()
    d.vbox.add(hb)
    
    i=gtk.Image()
    i.set_from_stock(gtk.STOCK_DIALOG_QUESTION, gtk.ICON_SIZE_DIALOG)
    i.show()
    hb.pack_start(i, expand=False)
    
    if text is not None:
        l=gtk.Label(text)
        l.show()
        hb.add(l)

    retval=d.run()
    d.destroy()
    return retval


def entry_dialog(title=None,
                 text=None,
                 default=""):
    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                   buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                             ))
    if text:
        l=gtk.Label(text)
        l.show()
        d.vbox.add(l)

    e=gtk.Entry()
    e.show()
    if default:
        e.set_text(default)
    
    def keypressed_cb(widget=None, event=None):
        if event.keyval == gtk.keysyms.Return:
            # Validate the activated entry
            d.response(gtk.RESPONSE_ACCEPT)
            return True
        return False
    e.connect("key_press_event", keypressed_cb)

    d.vbox.add(e)

    res=d.run()
    ret=None
    if res == gtk.RESPONSE_ACCEPT:
        try:
            ret=e.get_text()
        except ValueError:
            ret=None
    else:
        ret=None

    d.destroy()
    return ret
