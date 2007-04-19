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
"""GUI-related helper methods"""

from gettext import gettext as _

import gtk
import gobject
import sre
import os
import sys
import StringIO

import advene.core.config as config
import advene.util.helper as helper
from advene.model.exception import AdveneException

# In some cases, sys.getfilesystemencoding returns None
_fs_encoding = sys.getfilesystemencoding() or 'ascii'

def png_to_pixbuf (png_data, width=None, height=None):
    """Load PNG data into a pixbuf
    """
    loader = gtk.gdk.PixbufLoader ('png')
    if not isinstance(png_data, str):
        png_data=str(png_data)
    loader.write (png_data, len (png_data))
    pixbuf = loader.get_pixbuf ()
    loader.close ()
    if width and not height:
        height = width * pixbuf.get_height() / pixbuf.get_width()
    if height and not width:
        width = height * pixbuf.get_width() / pixbuf.get_height()
    if width and height:
        p=pixbuf.scale_simple(width, height, gtk.gdk.INTERP_BILINEAR)
        return p
    else:
        return pixbuf

def image_from_position(controller, position=None, width=None, height=None):
    i=gtk.Image()
    if position is None:
        position=controller.player.current_position_value
    try:
        i.set_from_pixbuf(png_to_pixbuf (controller.package.imagecache[position],
                                         width=width, height=height))
    except:
        # Some png_data corruption have been reported. Handle them here.
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))
    return i

def dialog_keypressed_cb(widget=None, event=None):
    if event.keyval == gtk.keysyms.Return:
        widget.response(gtk.RESPONSE_OK)
        return True
    elif event.keyval == gtk.keysyms.Escape:
        widget.response(gtk.RESPONSE_CANCEL)
        return True
    return False

def generate_list_model(elements, active_element=None):
    """Create a TreeModel matching the elements list.

    Element 0 is the label.
    Element 1 is the element (stbv).

    @param elements: a list of couples (element, label)
    @param active_element: the element that should be preselected
    """
    store=gtk.ListStore(str, object)
    active_iter=None
    for element, label in elements:
        i=store.append( ( label, element ) )
        if element == active_element:
            active_iter=i
    return store, active_iter

def list_selector_widget(members=None,
                         preselect=None,
                         callback=None):
    """Generate a widget to pick an element from a list.


    @param members: list of couples (element, label)
    @type members: list
    """
    store, i=generate_list_model(members,
                                 active_element=preselect)

    combobox=gtk.ComboBox(store)
    cell = gtk.CellRendererText()
    combobox.pack_start(cell, True)
    combobox.add_attribute(cell, 'text', 0)
    combobox.set_active(-1)
    if i is None:
        i = store.get_iter_first()
    if i is not None:
        combobox.set_active_iter(i)

    def get_current_element(combo):
        return combo.get_model().get_value(combo.get_active_iter(), 1)

    # Bind the method to the combobox object
    combobox.get_current_element = get_current_element.__get__(combobox)

    if callback is not None:
        combobox.connect('changed', callback)

    return combobox

def list_selector(title=None,
                  text=None,
                  members=None,
                  controller=None,
                  preselect=None):
    """Pick an element from a list.

    members is a list of couples (element, label).

    Return None if the action is cancelled.
    """
    combobox = list_selector_widget(members=members,
                                    preselect=preselect)

    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                   buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

    if text is not None:
        l=gtk.Label(text)
        l.show()
        d.vbox.add(l)

    d.vbox.add(combobox)
    combobox.show_all()

    d.connect("key_press_event", dialog_keypressed_cb)

    d.show()
    center_on_mouse(d)
    res=d.run()
    retval=None
    if res == gtk.RESPONSE_OK:
        retval=combobox.get_current_element()
    d.destroy()
    return retval

def message_dialog(label="", icon=gtk.MESSAGE_INFO):
    if icon == gtk.MESSAGE_QUESTION:
        button=gtk.BUTTONS_YES_NO
    else:
        button=gtk.BUTTONS_OK
    dialog = gtk.MessageDialog(
        None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        icon, button, label)
    dialog.set_position(gtk.WIN_POS_CENTER_ALWAYS)
    dialog.connect("key_press_event", dialog_keypressed_cb)
    
    dialog.show()
    center_on_mouse(dialog)
    res=dialog.run()
    dialog.destroy()
    if icon == gtk.MESSAGE_QUESTION:
        return (res == gtk.RESPONSE_YES)
    else:
        return True

def yes_no_cancel_popup(title=None,
                        text=None):
    """Build a Yes-No-Cancel popup window.

    Return codes are in (gtk.RESPONSE_YES, gtk.RESPONSE_NO, gtk.RESPONSE_CANCEL)
    """
    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
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
    d.connect("key_press_event", dialog_keypressed_cb)

    d.show()
    center_on_mouse(d)
    retval=d.run()
    d.destroy()
    return retval

def entry_dialog(title=None,
                 text=None,
                 default=""):
    """Display a dialog to enter a short text.
    """
    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                   buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK,
                             ))
    if text:
        l=gtk.Label(text)
        l.show()
        d.vbox.add(l)

    e=gtk.Entry()
    e.show()
    if default:
        e.set_text(default)

    d.connect("key_press_event", dialog_keypressed_cb)

    d.vbox.add(e)

    d.show()
    center_on_mouse(d)

    res=d.run()
    ret=None
    if res == gtk.RESPONSE_OK:
        try:
            ret=e.get_text()
        except ValueError:
            ret=None
    else:
        ret=None

    d.destroy()
    return ret

def build_optionmenu(elements, current, on_change_element, editable=True):
    """Build an ComboBox.

    elements is a dict holding (key, values) where the values will be used as labels
    current is the current activated element (i.e. one of the keys)
    on_change_element is the method which will be called upon option modification.

    Its signature is:

    ``def on_change_element([self,] element):``
    """
    def change_cb(combobox, on_change_element):
        i=combobox.get_active_iter()
        element=combobox.get_model().get_value(i, 1)
        on_change_element(element)
        return True

    store=gtk.ListStore(str, object)
    active_iter=None
    for k, v in elements.iteritems():
        i=store.append( (v, k) )
        if k == current:
            active_iter=i

    optionmenu = gtk.ComboBox(model=store)
    cell = gtk.CellRendererText()
    optionmenu.pack_start(cell, True)
    optionmenu.add_attribute(cell, 'text', 0)
    optionmenu.set_active_iter(active_iter)
    optionmenu.connect("changed", change_cb, on_change_element)
    optionmenu.set_sensitive(editable)
    optionmenu.show_all()
    return optionmenu

def get_filename(title=_("Open a file"),
                 action=gtk.FILE_CHOOSER_ACTION_OPEN,
                 button=gtk.STOCK_OPEN,
                 default_dir=None,
                 default_file=None,
                 alias=None, 
                 filter='any'):
    preview_box = gtk.VBox()

    preview = gtk.Button(_("N/C"))
    preview_box.add(preview)

    if alias:
        h=gtk.HBox()
        l=gtk.Label(_("Alias"))
        h.add(l)
        alias_entry = gtk.Entry()
        h.add(alias_entry)
        preview_box.add(h)

    preview_box.show_all()

    def update_preview(chooser):
        filename=chooser.get_preview_filename()
        setattr(preview, '_filename', filename)
        if filename and (filename.endswith('.xml') or filename.endswith('.azp')):
            preview.set_label(_("Press to\ndisplay\ninformation"))
            if alias:
                name, ext = os.path.splitext(filename)
                al = sre.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))
                alias_entry.set_text(al)
            chooser.set_preview_widget_active(True)
        else:
            preview.set_label(_("N/C"))
            if alias:
                alias_entry.set_text('')
            chooser.set_preview_widget_active(False)
        return True
        
    def do_preview(button):
        if hasattr(button, '_filename') and button._filename:
            button.set_label(_("Wait..."))
            try:
                st=helper.get_statistics(button._filename)
            except AdveneException, e:
                st=_("Error: %s") % unicode(e)
            button.set_label(st)
            button._filename=None
        return True

    preview.connect("clicked", do_preview)

    fs=gtk.FileChooserDialog(title=title,
                             parent=None,
                             action=action,
                             buttons=( button,
                                       gtk.RESPONSE_OK,
                                       gtk.STOCK_CANCEL,
                                       gtk.RESPONSE_CANCEL ))
    fs.set_preview_widget(preview_box)

    # filter may be: 'any', 'advene', 'session', 'video'
    filters={}

    for name, descr, exts in (
        ('any', _("Any type of file"), ( '*', ) ),
        ('advene', 
         _("Advene files (.xml, .azp, .apl)"), 
         ('*.xml', '*.azp', '*.apl')),
        ('session', _("Advene session (.apl)"), ( '*.apl', ) ),
        ('video', _("Video files"), [ "*%s" % e for e in config.data.video_extensions ])
        ):
        filters[name]=gtk.FileFilter()
        filters[name].set_name(descr)
        for e in exts:
            filters[name].add_pattern(e)
        fs.add_filter(filters[name])

    fs.set_filter(filters[filter])
    fs.connect("selection_changed", update_preview)
    fs.connect("key_press_event", dialog_keypressed_cb)

    if default_dir:
        fs.set_current_folder(default_dir)
    if default_file:
        fs.set_filename(default_file)
        fs.set_current_name(default_file)

    fs.show()
    center_on_mouse(fs)
    res=fs.run()
    filename=None
    al=None
    if res == gtk.RESPONSE_OK:
        filename=fs.get_filename()
        if alias:
            al=alias_entry.get_text()
            al = sre.sub('[^a-zA-Z0-9_]', '_', al)
    fs.destroy()

    if filename is not None and not isinstance(filename, unicode):
        filename=unicode(filename, _fs_encoding)

    if alias:
        return filename, al
    else:
        return filename

def get_dirname(title=_("Choose a directory"),
                 action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                 button=gtk.STOCK_OK,
                 default_dir=None):

    fs=gtk.FileChooserDialog(title=title,
                             parent=None,
                             action=action,
                             buttons=( button,
                                       gtk.RESPONSE_OK,
                                       gtk.STOCK_CANCEL,
                                       gtk.RESPONSE_CANCEL ))
    if default_dir:
        fs.set_current_folder(default_dir)

    fs.show()
    center_on_mouse(fs)
    res=fs.run()
    dirname=None
    if res == gtk.RESPONSE_OK:
        dirname=fs.get_filename()
    fs.destroy()

    return dirname

class CategorizedSelector:
    """Widget displaying items sorted along categories.

    We use a treeview to display elements.

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
    @ivar button: a gtk.Button with a label matching the selected value
    @type button: gtk.Button
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

        sw=gtk.ScrolledWindow()
        sw.add(treeview)
        vbox.pack_start(sw, expand=True)

        hbox=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect("clicked", lambda w: treeview.row_activated(*treeview.get_cursor()))
        hbox.add(b)
        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect("clicked", lambda w: self.popup_hide())
        hbox.add(b)
        vbox.pack_start(hbox, expand=False)

        vbox.show_all()

        return vbox

    def get_button(self):
        """Return a button with the current element description as label.
        """
        if self.button is not None:
            return self.button
        b=gtk.Button(self.description_getter(self.current))
        if self.editable:
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
            # FIXME: hardcoded values are bad
            # but we do not have access to
            # advene.gui.main.init_window_size
            w.set_default_size(240,300)
            self.popup=w
        self.popup.show_all()
        center_on_mouse(self.popup)
        return True

    def popup_hide(self):
        if self.popup is not None:
            self.popup.hide()
        return True

def center_on_mouse(w):
    """Center the given gtk.Window on the mouse position.
    """
    d=gtk.gdk.device_get_core_pointer()
    root=w.get_toplevel().get_root_window()
    (x, y) = d.get_state(root)[0]
    x, y = long(x), long(y)

    # Let's try to center the window on the mouse as much as possible.
    width, height=w.get_size()
    rw, rh = root.get_size()
    w.move( min( max(0, x - width/2), rw-width ),
            min( max(0, y - height/2), rh-height) )

def get_small_stock_button(sid, callback=None):
    b=gtk.Button()
    b.add(gtk.image_new_from_stock(sid, gtk.ICON_SIZE_SMALL_TOOLBAR))
    if callback:
        b.connect('clicked', callback)
    return b

