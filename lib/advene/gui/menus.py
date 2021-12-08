"""Dynamic menus
"""
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

import advene.core.config as config

# Copied from https://github.dev/gaphor/gaphor/blob/master/gaphor/ui/recentfiles.py
class RecentFilesMenu(Gio.Menu):
    def __init__(self, recent_manager):
        super().__init__()

        self._on_recent_manager_changed(recent_manager)
        # TODO: should unregister if the window is closed.
        if Gtk.get_major_version() == 3:
            self._changed_id = recent_manager.connect(
                "changed", self._on_recent_manager_changed
            )
        else:
            # TODO: GTK4 - Why is updating the recent files so slow?
            ...

    def _on_recent_manager_changed(self, recent_manager):
        self.remove_all()
        APPNAME = GObject.get_application_name()
        for item in recent_manager.get_items():
            if APPNAME in item.get_applications():
                menu_item = Gio.MenuItem.new(
                    item.get_uri_display(), "app.file-open-recent"
                )
                filename, _host = GLib.filename_from_uri(item.get_uri())
                menu_item.set_attribute_value(
                    "target", GLib.Variant.new_string(filename)
                )
                self.append_item(menu_item)
                if self.get_n_items() > 7:
                    break
        if self.get_n_items() == 0:
            self.append_item(
                Gio.MenuItem.new(_("No recently opened files"), None)
            )

def update_player_menu(menu, current):
    """Update the Player select menu
    """
    menu.remove_all()
    # Populate the "Select player" menu
    for ident, p in config.data.players.items():
        if current == ident:
            label = "> %s" % ident
        else:
            label = "   %s" % ident
        i = Gio.MenuItem.new(label, 'app.select_player')
        i.set_attribute_value("target", GLib.Variant.new_string(ident))
        menu.append_item(i)

    return menu

