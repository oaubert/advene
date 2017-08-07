#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
"""Generic properties editor widget.

Code adapted from gDesklets.
"""

import logging
logger = logging.getLogger(__name__)

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

import os
import sys
import time

from gettext import gettext as _

class Popup(Gtk.Window):
    """Popup widget (for KeyGrabber)

    Code taken from GPLv2 UbuntuTweak which got it from GPLv2 ccsm.
    """
    def __init__(self, parent, text=None, child=None,
                 decorated=True, mouse=False, modal=True):
        GObject.GObject.__init__(self, type=Gtk.WindowType.TOPLEVEL)
        self.set_type_hint(Gdk.WindowTypeHint.UTILITY)
        self.set_position(mouse and Gtk.WindowPosition.MOUSE or
                          Gtk.WindowPosition.CENTER_ALWAYS)

        if parent:
            self.set_transient_for(parent.get_toplevel())

        self.set_modal(modal)
        self.set_decorated(decorated)
        self.set_title("")

        if text:
            label = Gtk.Label(label=text)
            align = Gtk.Alignment()
            align.set_padding(20, 20, 20, 20)
            align.add(label)
            self.add(align)
        elif child:
            self.add(child)

        while Gtk.events_pending():
            Gtk.main_iteration()

    def destroy(self):
        Gtk.Window.destroy(self)
        while Gtk.events_pending():
            Gtk.main_iteration()

class KeyGrabber(Gtk.Button):
    """KeyGrabber widget.

    Code taken from GPLv2 UbuntuTweak which got it from GPLv2 ccsm.
    """
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None,
                    (GObject.TYPE_INT, GObject.TYPE_INT)),
        "current-changed": (GObject.SignalFlags.RUN_FIRST, None,
                            (GObject.TYPE_INT, Gdk.ModifierType))
    }

    key = 0
    mods = 0
    handler = None
    popup = None

    label = None

    def __init__ (self, parent=None, key=0, mods=0, label=None):
        '''Prepare widget'''
        GObject.GObject.__init__(self)

        self.main_window = parent
        self.key = key
        self.mods = mods

        self.label = label

        self.connect("clicked", self.begin_key_grab)
        self.set_label()

    def begin_key_grab(self, widget):
        self.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        if self.main_window is None:
            self.main_window = self.get_toplevel()
        self.popup = Popup(self.main_window,
                           _("Please press the new key combination"))
        self.popup.show_all()

        self.handler = self.popup.connect("key-press-event",
                                          self.on_key_press_event)

        while Gdk.keyboard_grab(self.main_window.get_window(),
                                True,
                                Gtk.get_current_event_time()) != Gdk.GrabStatus.SUCCESS:
            time.sleep (0.1)

    def end_key_grab(self):
        Gdk.keyboard_ungrab(Gtk.get_current_event_time())
        self.popup.disconnect(self.handler)
        self.popup.destroy()

    def on_key_press_event(self, widget, event):
        mods = event.get_state()

        if event.keyval in (Gdk.KEY_Escape, Gdk.KEY_Return) and not mods:
            if event.keyval == Gdk.KEY_Escape:
                self.emit("changed", self.key, self.mods)
            self.end_key_grab()
            self.set_label()
            return

        key = Gdk.keyval_to_lower(event.keyval)
        if (key == Gdk.KEY_ISO_Left_Tab):
            key = Gdk.KEY_Tab

        if Gtk.accelerator_valid(key, mods) or (key == Gdk.KEY_Tab and mods):
            self.set_label(key, mods)
            self.end_key_grab()
            self.key = key
            self.mods = mods
            self.emit("changed", self.key, self.mods)
            return

        self.set_label(key, mods)

    def set_label(self, key=None, mods=None):
        if self.label:
            if key != None and mods != None:
                self.emit("current-changed", key, mods)
            Gtk.Button.set_label(self, self.label)
            return
        if key == None and mods == None:
            key = self.key
            mods = self.mods
        label = Gtk.accelerator_name(key, mods)
        if not len(label):
            label = _("Disabled")
        Gtk.Button.set_label(self, label)


class EditNotebook(object):
    def __init__(self, set_config, get_config):
        self.__name = _("Properties")
        self._set_config = set_config
        self._get_config = get_config
        self.book = Gtk.Notebook()
        self.current_widget = None

    def __getattribute__ (self, name):
        """Use the defined method if necessary. Else, forward the request
        to the current_widget object
        """
        try:
            return object.__getattribute__ (self, name)
        except AttributeError:
            if self.current_widget is None:
                self.add_title(_("Preferences"))
            return self.current_widget.__getattribute__ (name)

    def set_name(self, name):
        self.__name = name

    def get_name(self):
        return self.__name

    def add_title(self, title):
        self.current_widget = EditWidget(self._set_config, self._get_config)
        self.current_widget.set_name(title)
        self.book.append_page(self.current_widget, Gtk.Label(label=title))
        return

    def popup(self):
        d = Gtk.Dialog(title=self.get_name(),
                       parent=None,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ))
        d.vbox.add(self.book)
        self.book.show_all()
        res=d.run()
        d.destroy()
        if res == Gtk.ResponseType.OK:
            return True
        else:
            return False


class EditWidget(Gtk.VBox):
    """Configuration edit widget.

    Adapted from (GPL) gdesklets code.
    """
    CHANGE_ENTRY = 0
    CHANGE_OPTION = 1
    CHANGE_SPIN = 2
    CHANGE_CHECKBOX = 3
    CHANGE_TEXT = 4
    CHANGE_FLOAT_SPIN = 5
    CHANGE_ACCELERATOR = 6

    def __init__(self, set_config, get_config):

        # functions for setting / getting configuration values
        self.__set_config = set_config
        self.__get_config = get_config

        # name of the configurator
        self.__name = ""

        # the number of widget lines
        self.__lines = 0


        GObject.GObject.__init__(self)
        self.set_border_width(12)
        self.show()

        self.__table = Gtk.Table(1, 2)
        self.__table.show()
        self.add(self.__table)

    #
    # Adds a line of widgets to the configurator. The line can be indented.
    #
    def __add_line(self, indent, w1, w2 = None):

        self.__lines += 1
        self.__table.resize(self.__lines, 2)

        if (indent): x, y = 12, 3
        else: x, y = 0, 3

        if (w2):
            self.__table.attach(w1, 0, 1, self.__lines - 1, self.__lines,
                                Gtk.AttachOptions.FILL, 0, x, y)
            self.__table.attach(w2, 1, 2, self.__lines - 1, self.__lines,
                                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, 0, 0, y)

        else:
            self.__table.attach(w1, 0, 2, self.__lines - 1, self.__lines,
                                Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, 0, x, y)



    #
    # Reacts on changing a setting.
    #
    def __on_change(self, src, *args):

        property, mode = args[-2:]
        args = args[:-2]
        value = None

        if (mode == self.CHANGE_ENTRY):
            value = src.get_text()

        elif (mode == self.CHANGE_OPTION):
            value = src.get_model()[src.get_active()][1]

        elif (mode == self.CHANGE_CHECKBOX):
            value = src.get_active()

        elif (mode == self.CHANGE_SPIN):
            value = src.get_value_as_int()

        elif (mode == self.CHANGE_FLOAT_SPIN):
            value = src.get_value()

        elif (mode == self.CHANGE_TEXT):
            value = src.get_text(*src.get_bounds() + ( False, ))

        elif (mode == self.CHANGE_ACCELERATOR):
            value = Gtk.accelerator_name(src.key, src.mods)

        else:
            logger.info("Unknown type %s", str(mode))

        if value is not None:
            self.__set_config(property, value)

    #
    # Sets/returns the name of this configurator. That name will appear in the
    # notebook tab.
    #
    def set_name(self, name): self.__name = name
    def get_name(self): return self.__name

    def add_label(self, label):

        lbl = Gtk.Label(label="")
        lbl.set_markup(label)
        lbl.set_line_wrap(True)
        lbl.show()
        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        self.__add_line(0, align)

    def add_title(self, label):

        self.add_label("<b>" + label + "</b>")

    def add_checkbox(self, label, property, help):

        check = Gtk.CheckButton(label)
        check.show()

        check.set_tooltip_text(help)
        self.__add_line(1, check)

        value = self.__get_config(property)
        check.set_active(value)
        check.connect('toggled', self.__on_change, property,
                      self.CHANGE_CHECKBOX)



    def add_entry(self, label, property, help, passwd = 0, entries=None):

        lbl = Gtk.Label(label=label)
        lbl.show()
        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        if entries:
            combo = Gtk.ComboBoxText.new_with_entry()
            entry = combo.get_child()
            combo.show()
            for e in entries:
                combo.append_text(e)
            combo.set_tooltip_text(help)
            self.__add_line(1, align, combo)
        else:
            combo = None
            entry = Gtk.Entry()
            entry.show()
            entry.set_tooltip_text(help)
            self.__add_line(1, align, entry)

        if (passwd):
            entry.set_visibility(False)
            entry.set_invisible_char('\u0222')

        value = self.__get_config(property)
        entry.set_text(value)
        entry.connect('changed', self.__on_change, property,
                      self.CHANGE_ENTRY)

    def add_entry_button(self, label, property, help, button_label, callback):
        """Text entry with an action button.

        The callback function has the following signature:
        callback(button, entry)
        """
        lbl = Gtk.Label(label=label)
        lbl.show()
        entry = Gtk.Entry()
        entry.show()
        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        hbox = Gtk.HBox()
        hbox.show()
        hbox.add(entry)
        b = Gtk.Button(button_label)
        b.connect('clicked', callback, entry)
        hbox.pack_start(b, False, True, 0)

        entry.set_tooltip_text(help)
        self.__add_line(1, align, hbox)

        value = self.__get_config(property)
        entry.set_text(value)
        entry.connect('changed', self.__on_change, property,
                      self.CHANGE_ENTRY)


    def add_text(self, label, property, help):

        lbl = Gtk.Label(label=label)
        lbl.show()
        sw = Gtk.ScrolledWindow()
        entry = Gtk.TextView()
        sw.add(entry)
        entry.show()
        sw.show()
        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        entry.set_tooltip_text(help)
        self.__add_line(1, align)
        self.__add_line(1, sw)

        value = self.__get_config(property)
        entry.get_buffer().set_text(value)
        entry.get_buffer().connect('changed', self.__on_change, property,
                                   self.CHANGE_TEXT)

    def add_spin(self, label, property, help, low, up):

        lbl = Gtk.Label(label=label)
        lbl.show()

        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        adjustment = Gtk.Adjustment.new(0, low, up, 1, 1, 0)
        spin_button = Gtk.SpinButton.new(adjustment, 1, 0)
        spin_button.set_numeric(True)
        spin_button.show()

        value = self.__get_config(property)

        spin_button.set_tooltip_text(help)
        self.__add_line(1, align, spin_button)

        spin_button.set_value(value)
        spin_button.connect('value-changed', self.__on_change, property,
                            self.CHANGE_SPIN)

    def add_float_spin(self, label, property, help, low, up, digits=2):

        lbl = Gtk.Label(label=label)
        lbl.show()

        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        value = self.__get_config(property)

        adjustment = Gtk.Adjustment.new(value, low, up, 10 ** -digits, 1, 0)
        spin_button = Gtk.SpinButton.new(adjustment, 10 ** -digits, digits)
        spin_button.set_numeric(True)
        spin_button.show()


        spin_button.set_tooltip_text(help)
        self.__add_line(1, align, spin_button)

        spin_button.set_value(value)
        spin_button.connect('value-changed', self.__on_change, property,
                            self.CHANGE_FLOAT_SPIN)

    def add_accelerator(self, label, property, help):

        lbl = Gtk.Label(label=label)
        lbl.show()

        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        value = self.__get_config(property)

        key, mods = Gtk.accelerator_parse(value)
        grabber = KeyGrabber(parent=self.get_toplevel(),
                             key=key,
                             mods=mods)
        grabber.connect('changed', self.__on_change, property, self.CHANGE_ACCELERATOR)

        grabber.set_tooltip_text(help)
        grabber.show_all()
        self.__add_line(1, align, grabber)

    def add_option(self, label, property, help, options):

        lbl = Gtk.Label(label=label)
        lbl.show()

        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        value = self.__get_config(property)

        store=Gtk.ListStore(str, object)
        active_iter=None
        for k, v in options.items():
            i=store.append( ( k, v ) )
            if v == value:
                active_iter=i

        if active_iter is None:
            active_iter = store.get_iter_first()

        combo = Gtk.ComboBox.new_with_model(store)
        cell = Gtk.CellRendererText()
        combo.pack_start(cell, True)
        combo.add_attribute(cell, 'text', 0)
        combo.set_active_iter(active_iter)

        combo.connect('changed', self.__on_change, property, self.CHANGE_OPTION)

        combo.set_tooltip_text(help)
        combo.show_all()
        self.__add_line(1, align, combo)

    def add_file_selector(self, label, property, help):

        def open_filedialog(self, default_file, entry):
            fs=Gtk.FileChooserDialog(title=_("Choose a file"),
                                     parent=None,
                                     action=Gtk.FileChooserAction.OPEN,
                                     buttons=( Gtk.STOCK_OPEN,
                                               Gtk.ResponseType.OK,
                                               Gtk.STOCK_CANCEL,
                                               Gtk.ResponseType.CANCEL ))
            if default_file and os.path.exists(default_file):
                fs.set_filename(default_file)
            res=fs.run()
            filename=None
            if res == Gtk.ResponseType.OK:
                filename=fs.get_filename()
                entry.set_text(filename)
            fs.destroy()

        lbl = Gtk.Label(label=label)
        lbl.show()
        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        hbox = Gtk.HBox()
        hbox.show()
        entry = Gtk.Entry()
        entry.show()
        hbox.pack_start(entry, True, True, 0)

        btn = Gtk.Button(stock = Gtk.STOCK_OPEN)
        btn.show()
        hbox.pack_end(btn, True, True, 4)

        value = self.__get_config(property)

        btn.connect('clicked', open_filedialog, value, entry)

        entry.set_text(value)
        entry.connect('changed', self.__on_change, property,
                      self.CHANGE_ENTRY)

        entry.set_tooltip_text(help)
        btn.set_tooltip_text(help)
        self.__add_line(1, align, hbox)

    def add_dir_selector(self, label, property, help):

        def open_filedialog(self, default_file, entry):
            fs=Gtk.FileChooserDialog(title=_("Choose a directory"),
                                     parent=None,
                                     action=Gtk.FileChooserAction.SELECT_FOLDER,
                                     buttons=( Gtk.STOCK_OPEN,
                                               Gtk.ResponseType.OK,
                                               Gtk.STOCK_CANCEL,
                                               Gtk.ResponseType.CANCEL ))
            if default_file:
                fs.set_filename(default_file)
            res=fs.run()
            filename=None
            if res == Gtk.ResponseType.OK:
                filename=fs.get_filename()
                entry.set_text(filename)
            fs.destroy()

        lbl = Gtk.Label(label=label)
        lbl.show()
        align = Gtk.Alignment()
        align.show()
        align.add(lbl)

        hbox = Gtk.HBox()
        hbox.show()
        entry = Gtk.Entry()
        entry.show()
        hbox.pack_start(entry, True, True, 0)

        btn = Gtk.Button(stock = Gtk.STOCK_OPEN)
        btn.show()
        hbox.pack_end(btn, True, True, 4)

        value = self.__get_config(property)

        btn.connect('clicked', open_filedialog, value, entry)

        entry.set_text(value)
        entry.connect('changed', self.__on_change, property,
                      self.CHANGE_ENTRY)

        entry.set_tooltip_text(help)
        btn.set_tooltip_text(help)
        self.__add_line(1, align, hbox)

    def popup(self):
        d = Gtk.Dialog(title=self.get_name(),
                       parent=None,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ))
        d.vbox.add(self)

        def dialog_keypressed_cb(widget=None, event=None):
            """Generic dialog keypress handler.
            """
            if event.keyval == Gdk.KEY_Return:
                widget.response(Gtk.ResponseType.OK)
                return True
            elif event.keyval == Gdk.KEY_Escape:
                widget.response(Gtk.ResponseType.CANCEL)
                return True
            return False
        d.connect('key-press-event', dialog_keypressed_cb)

        self.show_all()
        res=d.run()
        d.destroy()
        if res == Gtk.ResponseType.OK:
            return True
        else:
            return False

class OptionParserGUI(EditWidget):
    """Generic GUI view to propose a dialog matching OptionParser definitions.

    @ivar parser: the OptionParser instance which holds option definitions
    @ivar default: an optional object, that holds default values as attributes.
    """
    def __init__(self, parser, default=None):
        self.parser = parser
        self.default = default
        self.options = {}
        super(OptionParserGUI, self).__init__(self.options.__setitem__, self.options.get)
        self.parse_options(parser)

    def parse_options(self, parser):
        for o in parser.option_list:
            name = o.get_opt_string().replace('--', '')
            if o.dest and hasattr(self.default, o.dest):
                val = getattr(self.default, o.dest)
            else:
                val = o.default
            # FIXME: should implement store_const, append, count? and (less likely) callback
            if o.action == 'store_true':
                self.options[o.dest] = val
                self.add_checkbox(name, o.dest, o.help)
            elif o.action == 'store_false':
                self.options[o.dest] = not val
                self.add_checkbox(name, o.dest, o.help)
            elif o.action == 'store':
                if o.type in ('int', 'long'):
                    self.options[o.dest] = val
                    self.add_spin(name, o.dest, o.help, -1e300, 1e300)
                elif o.type == 'string':
                    self.options[o.dest] = val or ""
                    if o.help.endswith('[F]'):
                        # Filename
                        self.add_file_selector(name, o.dest, o.help)
                    elif o.help.endswith('[D]'):
                        # Directory
                        self.add_dir_selector(name, o.dest, o.help)
                    else:
                        self.add_entry(name, o.dest, o.help)
                elif o.type == 'float':
                    self.options[o.dest] = val
                    self.add_float_spin(name, o.dest, o.help, -sys.maxsize, sys.maxsize, 2)
                elif o.type == 'choice':
                    self.options[o.dest] = val
                    self.add_option(name, o.dest, o.help, dict( (c, c) for c in o.choices) )
            else:
                if name != 'help':
                    logger.info("Ignoring option %s", name)
                continue

def test():
    val = {
        'string': 'String',
        'option': 'fee',
        'float': .42,
        'filename': '/tmp',
        }
    def set_config(name, value):
        val[name] = value

    def get_config(name):
        return val[name]

    ew=EditWidget(set_config, get_config)
    ew.set_name("Test")
    ew.add_title("Main values")
    ew.add_entry("Name", "string", "Enter a valid name")
    ew.add_float_spin("Float", "float", "Choose a float value", -1, 1, 2)
    ew.add_option("Option", 'option', "Choose the option", {"Fee": "fee",
                                                            "Fi": "fi",
                                                            "Fo": "fo",
                                                            "Fum": "fum" })
    ew.add_file_selector("File", 'filename', "Select a filename")

    res=ew.popup()
    if res:
        logger.info("Modified: %s", str(val))
    else:
        logger.info("Cancel")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    test()
