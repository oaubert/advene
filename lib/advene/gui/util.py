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

def build_optionmenu(elements, current, on_change_element, editable=True):
    """Build an OptionMenu.

    elements is a dict holding (key, values) where the values will be used as labels
    current is the current activated element (i.e. one of the keys)
    on_change_element is the method which will be called upon option modification.

    Its signature is:

    ``def on_change_element([self,] element):``
    """
    def change_cb(optionmenu, elements):
        self.on_change_element(elements[optionmenu.get_history()])
        return True

    # List of elements, with the same index as the menus
    optionmenu = gtk.OptionMenu()

    items=[]
    cnt=0
    index=0
    menu=gtk.Menu()
    for k, v in elements.iteritems():
        item = gtk.MenuItem(v)
        item.show()
        menu.append(item)
        items.append(k)
        if (k == current): index = cnt
        cnt += 1

    optionmenu.set_menu(menu)
    optionmenu.set_history(index)
    optionmenu.connect("changed", change_cb, items)
    optionmenu.set_sensitive(editable)
    optionmenu.show()
    return optionmenu

class CategorizedSelector:
    """Widget displaying items sorted along categories.

    We use a treeview to display elements.

    FIXME: we could also return a gtk.Button with a label that changes
    according to the selected value, to save time for the calling application


    @ivar elements: list of  elements
    @type elements: list
    @ivar categories: list of categories
    @type categories: list
    @ivar current: current element
    @type current: object
    @ivar description_getter: method to get the description of the element or the category
    @type description_getter: method
    @ivar category_getter: method to get the category of the element
    @type category_getter: method
    @ivar callback: method to be called upon modification
    @type callback: method
    @ivar editable: indicates if the data is editable
    @type editable: boolean
    """
    COLUMN_ELEMENT=0
    COLUMN_LABEL=1
    COLUMN_MODE=2
    def __init__(self, title=_("Select an element"),
                 elements=None, categories=None, current=None,
                 description_getter=None, category_getter=None, callback=None,
                 editable=True):
        self.title=title
        self.elements=elements
        self.categories=categories
        self.current=current
        self.description_getter=description_getter
        self.category_getter=category_getter
        self.callback=callback
        self.editable=editable
        self.store=None
        # A button representing the current element
        self.button=None
        # The popup window
        self.popup=None
        self.widget=self.build_widget()

    def build_liststore(self):
        # We store the object itself and its representation
        store=gtk.TreeStore(
            gobject.TYPE_PYOBJECT,
            gobject.TYPE_STRING,
            gobject.TYPE_INT,
            )

        catrow={}
        for i in self.categories:
            catrow[i]=store.append(parent=None,
                                   row=[i,
                                        self.description_getter(i),
                                        gtk.CELL_RENDERER_MODE_INERT])
        currentrow=None
        for e in self.elements:
            row=store.append(parent=catrow[self.category_getter(e)],
                             row=[e,
                                  self.description_getter(e),
                                  gtk.CELL_RENDERER_MODE_ACTIVATABLE])
            if e == self.current:
                currentrow=row
        return store, currentrow

    def row_activated_cb(self, treeview, path, column):
        element=treeview.get_model()[path][self.COLUMN_ELEMENT]
        if not element in self.elements:
            # It is a category
            return False
        self.update_element(element)
        # Hide the selection
        self.popup_hide()
        return True
        
    def build_widget(self):
        vbox=gtk.VBox()

        self.store, currentrow=self.build_liststore()

        treeview=gtk.TreeView(model=self.store)
        #treeview.connect("button_press_event", self.tree_view_button_cb)
        treeview.connect("row_activated", self.row_activated_cb)
        path=self.store.get_path(currentrow)
        treeview.expand_to_path(path)
        treeview.scroll_to_cell(path)
        treeview.set_cursor_on_cell(path)
        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Name'), renderer,
                                    text=self.COLUMN_LABEL,
                                    mode=self.COLUMN_MODE)
        column.set_resizable(True)
        treeview.append_column(column)
        
        vbox.add(treeview)

        hbox=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect("clicked", lambda w: treeview.row_activated(*treeview.get_cursor()))
        hbox.add(b)
        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect("clicked", lambda w: self.popup_hide())
        hbox.add(b)
        vbox.add(hbox)
        
        vbox.show_all()
        
        return vbox

    def get_button(self):
        """Return a button with the current element description as label.
        """
        if self.button is not None:
            return self.button
        b=gtk.Button(self.description_getter(self.current))
        b.connect("clicked", lambda w: self.popup_show())
        b.show()
        self.button=b
        return b

    def update_element(self, element=None):
        self.current=element
        if self.button is not None:
            self.button.set_label(self.description_getter(element))
        if self.callback is not None:
            self.callback(element)
        return True

    def popup_show(self):
        if self.popup is None:
            w=gtk.Window()
            w.set_title(self.title)
            w.add(self.widget)
            self.popup=w
        self.popup.show_all()
        return True

    def popup_hide(self):
        if self.popup is not None:
            self.popup.hide()
        return True

