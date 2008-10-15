#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Dialog building facilities.
"""

from gettext import gettext as _

import gtk
import gobject
import re
import os
import sys

import advene.core.config as config
import advene.util.helper as helper

_fs_encoding = sys.getfilesystemencoding()
# In some cases, sys.getfilesystemencoding returns None. And if the
# system is misconfigured, it will return ANSI_X3.4-1968
# (apparently). In these cases, fallback to a sensible default value
if _fs_encoding in ('ascii', 'ANSI_X3.4-1968', None):
    _fs_encoding='utf8'

def dialog_keypressed_cb(widget=None, event=None):
    """Generic dialog keypress handler.
    """
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
    Element 1 is the element
    Element 2 is the color (optional)

    @param elements: a list of couples (element, label) or tuples (element, label, color)
    @param active_element: the element that should be preselected
    """
    store=gtk.ListStore(str, object, str)
    active_iter=None
    if elements:
        if len(elements[0]) == 3:
            for element, label, color in elements:
                i=store.append( ( label, element, color ) )
                if element == active_element:
                    active_iter=i
        else:
            for element, label in elements:
                i=store.append( ( label, element, None ) )
                if element == active_element:
                    active_iter=i
    return store, active_iter

def list_selector_widget(members=None,
                         preselect=None,
                         entry=False,
                         callback=None):
    """Generate a widget to pick an element from a list.


    @param members: list of couples (element, label) or tuples (element, label, color)
    @type members: list
    @param preselect: the element to preselect
    @type preselect: object
    @param entry: use a comboboxentry ?
    @type entry: boolean
    @param callback: a callback to call on value change
    @type callback: method
    """
    store, i=generate_list_model(members,
                                 active_element=preselect)

    if entry:
        combobox=gtk.ComboBoxEntry(store, column=0)
    else:
        combobox=gtk.ComboBox(store)
        cell = gtk.CellRendererText()
        combobox.pack_start(cell, expand=True)
        combobox.add_attribute(cell, 'text', 0)
        combobox.add_attribute(cell, 'background', 2)

    combobox.set_active(-1)
    if i is None:
        i = store.get_iter_first()
    if i is not None:
        combobox.set_active_iter(i)

    if entry:
        def get_current_element(combo):
            try:
                return combo.get_model().get_value(combo.get_active_iter(), 1)
            except (TypeError, AttributeError):
                return combo.child.get_text()
        def set_current_element(combo, t):
            combo.child.set_text(t)
    else:
        def get_current_element(combo):
            return combo.get_model().get_value(combo.get_active_iter(), 1)
        def set_current_element(combo, el):
            # Find the index of the element
            l=[ t[0] for t in enumerate(combo.get_model()) if t[1][1] == el ]
            if l:
                # The element is present.
                combo.set_active(l[0])

    # Bind the method to the combobox object
    combobox.get_current_element = get_current_element.__get__(combobox)
    combobox.set_current_element = set_current_element.__get__(combobox)

    if callback is not None:
        combobox.connect('changed', callback)

    return combobox

def list_selector(title=None,
                  text=None,
                  members=None,
                  controller=None,
                  preselect=None,
                  entry=False):
    """Pick an element from a list.

    members is a list of couples (element, label) or tuples (element, label, color)

    Return None if the action is cancelled.
    """
    combobox = list_selector_widget(members=members,
                                    preselect=preselect,
                                    entry=entry)

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

    d.connect('key-press-event', dialog_keypressed_cb)

    d.show()
    center_on_mouse(d)
    res=d.run()
    retval=None
    if res == gtk.RESPONSE_OK:
        retval=combobox.get_current_element()
    d.destroy()
    return retval

def message_dialog(label="", icon=gtk.MESSAGE_INFO, modal=True, callback=None):
    """Message dialog.

    If callback is not None, then the dialog will not be modal and
    the callback function will be called upon validation.
    """
    if icon == gtk.MESSAGE_QUESTION:
        button=gtk.BUTTONS_YES_NO
    else:
        button=gtk.BUTTONS_OK
    if callback is not None:
        # Force non-modal behaviour when there is a callback
        modal=False
    if modal:
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT
    else:
        flags=gtk.DIALOG_DESTROY_WITH_PARENT

    dialog = gtk.MessageDialog(None, flags,
                               icon, button)
    dialog.set_markup(label)
    if not dialog.label.get_text():
        # Hackish way of determining if there was an error while
        # parsing the markup. In this case, fallback to simple text
        dialog.label.set_text(label)
    dialog.set_position(gtk.WIN_POS_CENTER_ALWAYS)
    dialog.connect('key-press-event', dialog_keypressed_cb)

    dialog.show()
    center_on_mouse(dialog)

    if modal:
        res=dialog.run()
        dialog.destroy()
        if icon == gtk.MESSAGE_QUESTION:
            return (res == gtk.RESPONSE_YES)
        else:
            return True
    else:
        # Callback is defined, non-modal behaviour.
        # Connect the signal handler.
        def handle_response(d, res):
            d.destroy()
            if res == gtk.RESPONSE_YES and callback is not None:
                callback()
            return True
        dialog.connect('response', handle_response)
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
    d.connect('key-press-event', dialog_keypressed_cb)

    d.show()
    center_on_mouse(d)
    retval=d.run()
    d.destroy()
    return retval

def entry_dialog(title=None,
                 text=None,
                 default="",
                 completions=None):
    """Display a dialog to enter a short text.

    @param title: title of the dialog
    @type title: string
    @param text: text of the dialog
    @type text: string
    @param default: default value for the entry
    @type default: string
    @param completions: a list of possible completions
    @type completions: list of strings
    @return: the entry value or None if the dialog was cancelled
    @rtype: string
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

    if completions:
        completion = gtk.EntryCompletion()
        e.set_completion(completion)
        liststore = gtk.ListStore(str)
        completion.set_text_column(0)
        completion.set_model(liststore)
        for s in completions:
            liststore.append([ s ])

    d.connect('key-press-event', dialog_keypressed_cb)

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
    """Build a ComboBox.

    The `on_change_element` method signature is:

    ``def on_change_element([self,] element):``

    @param elements: dict holding (key, values) where the values will be used as labels
    @type elements: dict
    @param current: current activated element (i.e. one of the keys)
    @param on_change_element: method be called upon option modification
    @type on_change_element: method
    @return: the combobox widget
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
    optionmenu.connect('changed', change_cb, on_change_element)
    optionmenu.set_sensitive(editable)
    optionmenu.show_all()
    return optionmenu

def title_id_widget(element_title=None,
                    element_id=None):
    """Build a widget to get title and id.

    @param element_title: default title
    @type element_title: string
    @param element_id: default id
    @type element_id: string
    @return: the widget
    """
    v=gtk.Table(rows=2, columns=2)

    l=gtk.Label(_("Title"))
    v.attach(l, 0, 1, 0, 1)

    title_entry=gtk.Entry()
    title_entry.show()
    if element_title:
        title_entry.set_text(element_title)
    v.attach(title_entry, 1, 2, 0, 1)

    l=gtk.Label(_("Id"))
    v.attach(l, 0, 1, 1, 2)

    id_entry=gtk.Entry()
    id_entry.show()
    if element_id:
        id_entry.set_text(element_id)
    v.attach(id_entry, 1, 2, 1, 2)

    def update_id(entry):
        id_entry.set_text(helper.title2id(unicode(entry.get_text())))
        return True

    title_entry.connect('changed', update_id)

    v.id_entry=id_entry
    v.title_entry=title_entry
    return v

def title_id_dialog(title=_("Name the element"),
                    element_title=None,
                    element_id=None,
                    text=_("Choose a name for the element"),
                    flags=None):
    """Build a dialog to get title and id.

    @param title: title of the dialog
    @type title: string
    @param text: text of the dialog
    @type text: string
    @param element_title: default title
    @type element_title: string
    @param element_id: default id
    @type element_id: string
    @param flags: optional gtk.Dialog flags (such as gtk.DIALOG_MODAL)

    @return: the dialog widget
    """
    if flags is None:
        flags=gtk.DIALOG_DESTROY_WITH_PARENT
    d = gtk.Dialog(title=title,
                   parent=None,
                   flags=flags,
                   buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                             gtk.STOCK_OK, gtk.RESPONSE_OK,
                             ))
    if text:
        l=gtk.Label(text)
        l.show()
        d.vbox.add(l)

    v=title_id_widget(element_title, element_id)
    d.vbox.pack_start(v, expand=False)
    d.connect('key-press-event', dialog_keypressed_cb)
    d.id_entry=v.id_entry
    d.title_entry=v.title_entry
    return d

def get_title_id(title=_("Name the element"),
                 text=_("Choose a name for the element"),
                 element_title=None,
                 element_id=None):
    """Get a title and id pair.

    @param title: title of the dialog
    @type title: string
    @param text: text of the dialog
    @type text: string
    @param element_title: default title
    @type element_title: string
    @param element_id: default id
    @type element_id: string
    @return: a tuple (title, id). Both will be None if the dialog was cancelled
    """
    d = title_id_dialog(title=title,
                        element_title=element_title,
                        element_id=element_id,
                        text=text)
    d.show_all()
    center_on_mouse(d)

    res=d.run()
    if res == gtk.RESPONSE_OK:
        try:
            t=unicode(d.title_entry.get_text())
            i=unicode(d.id_entry.get_text())
        except ValueError:
            t=None
            i=None
    else:
        t=None
        i=None

    d.destroy()

    return t, i

def get_filename(title=_("Open a file"),
                 action=gtk.FILE_CHOOSER_ACTION_OPEN,
                 button=gtk.STOCK_OPEN,
                 default_dir=None,
                 default_file=None,
                 alias=False,
                 filter='any'):
    """Get a filename.

    @param title: the dialog title
    @type title: string
    @param action: the dialog action: gtk.FILE_CHOOSER_ACTION_OPEN (default) or gtk.FILE_CHOOSER_ACTION_SAVE
    @param button: the validation button id: gtk.STOCK_OPEN (default) or gtk.STOCK_SAVE
    @param default_dir: the default directory
    @type default_dir: string
    @param default_file: the default file
    @type default_file: string
    @param alias: wether to display the alias entry
    @type alias: boolean
    @param filter: the filename filter ('any', 'advene', 'session', 'video')
    @type filter: string
    @return: if alias, a tuple (filename, alias), else the filename
    """
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

    def generate_alias(fname):
        name, ext = os.path.splitext(fname)
        al = re.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))
        return al

    def update_preview(chooser):
        filename=chooser.get_preview_filename()
        setattr(preview, '_filename', filename)
        if filename and (filename.endswith('.xml') or filename.endswith('.azp')):
            preview.set_label(_("Press to\ndisplay\ninformation"))
            if alias:
                alias_entry.set_text(generate_alias(filename))
            chooser.set_preview_widget_active(True)
            if config.data.os == 'win32':
                # Force resize for win32
                oldmode=chooser.get_resize_mode()
                chooser.set_resize_mode(gtk.RESIZE_IMMEDIATE)
                chooser.resize_children()
                chooser.set_resize_mode(oldmode)
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
            except Exception, e:
                st=_("Error: %s") % unicode(e)
            button.set_label(st)
            button._filename=None
        return True

    preview.connect('clicked', do_preview)

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
    fs.connect('selection-changed', update_preview)
    fs.connect('key-press-event', dialog_keypressed_cb)

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
            if not al:
                # It may not have been updated, if the user typed the
                # filename in the entry box.
                al=generate_alias(filename)
            al = re.sub('[^a-zA-Z0-9_]', '_', al)
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
    """Get a directory name.

    @param title: the dialog title
    @type title: string
    @param action: the dialog action: gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER (default)
    @param button: the validation button id: gtk.STOCK_OK (default)
    @param default_dir: the default directory
    @type default_dir: string
    @return: the directory name
    """

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
    """Widget displaying a menu with items sorted along categories.

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
        self.button=None

    def popup_menu(self, *p):
        m=gtk.Menu()

        i=gtk.MenuItem(self.title, use_underline=False)
        i.set_sensitive(False)
        m.append(i)
        i=gtk.SeparatorMenuItem()
        m.append(i)

        submenu={}
        for c in self.categories:
            i=gtk.MenuItem(self.description_getter(c), use_underline=False)
            m.append(i)
            submenu[c]=gtk.Menu()
            i.set_submenu(submenu[c])
        for e in self.elements:
            i=gtk.MenuItem(self.description_getter(e), use_underline=False)
            submenu[self.category_getter(e)].append(i)
            i.connect('activate', lambda menuitem, element: self.update_element(element), e)
        m.show_all()
        m.popup(None, None, None, 0, gtk.get_current_event_time())
        return m

    def get_button(self):
        """Return a button with the current element description as label.
        """
        if self.button is not None:
            return self.button
        b=gtk.Button(self.description_getter(self.current))
        if self.editable:
            b.connect('clicked', lambda w: self.popup_menu())
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
