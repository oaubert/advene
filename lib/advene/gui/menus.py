"""Dynamic menus
"""
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

import advene.core.config as config

from advene.gui.actions import to_variant, menuitem_new

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
                menu_item = menuitem_new(item.get_uri_display(),
                                         "app.file-open-recent",
                                         item.get_uri())
                self.append_item(menu_item)
                if self.get_n_items() > 7:
                    break
        if self.get_n_items() == 0:
            self.append_item(menuitem_new(_("No recently opened files")))

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
        menu.append_item(menuitem_new(label,
                                      'app.select-player',
                                      ident))
    return menu

def update_package_list (menu, controller):
    """Update the list of loaded packages.
    """
    # Remove all previous menuitems
    menu.remove_all()

    # Rebuild the list
    for ident, p in controller.packages.items():
        if ident == 'advene':
            continue
        if p == controller.package:
            label = '> ' + ident
        else:
            label = '  ' + ident
        if p._modified:
            label += _(' (modified)')
        i = Gio.MenuItem.new(label, 'app.activate-package')
        i.set_attribute_value("target", to_variant(ident))
        menu.append_item(i)
    return True

