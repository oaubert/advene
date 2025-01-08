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
"""Advene GUI.

This module defines the main GUI class, L{AdveneApp}. It defines the
important methods and the various GUI callbacks (generally all methods
with the C{on_} prefix).
"""

import logging
logger = logging.getLogger(__name__)

from collections import OrderedDict

import io
import locale
import os
from pathlib import Path
import pprint
import re
import socket
import sys
import textwrap
import threading
import time
from urllib.parse import unquote
import urllib.request, urllib.error

import advene.core.config as config
import advene.core.version
from advene.gui.menus import RecentFilesMenu, update_player_menu, update_package_list

import gi
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import Gtk
from gi.repository import Pango

if config.data.debug:
    #Gdk.set_show_events(True)
    try:
        from advene.util.debug import debug_slow_update_hook
    except ImportError:
        logger.debug("No debug_slow_update_hook function in advene.util.debug")
        debug_slow_update_hook = None

logger.info("Using localedir %s", config.data.path['locale'])

# Locale initialisation
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    logger.error("Error in locale initialization. Interface translation may be incorrect.")
config.init_gettext()
# The following line is useless, since gettext.install defines _ as a
# builtin. However, code checking applications need to be explicitly
# told that _ is imported.
from gettext import gettext as _

import advene.core.controller

import advene.rules.elements

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.query import Query
import advene.model.constants
import advene.model.tal.context

import advene.core.mediacontrol
import advene.util.helper as helper
from advene.util.tools import unescape_string, open_in_filebrowser, detect_by_bom, printable
from advene.core.corpustools import corpus_website_export
import xml.etree.ElementTree as ET

import advene.util.importer
from advene.gui.util.completer import Indexer, Completer
import advene.util.merger

# GUI elements
from advene.gui.util import get_pixmap_button, get_small_stock_button, image_from_position,\
    dialog, encode_drop_parameters, overlay_svg_as_png,\
    name2color, predefined_content_mimetypes, get_drawable
from advene.gui.actions import to_variant, named_action, register_named_actions
from advene.gui.util.playpausebutton import PlayPauseButton
import advene.gui.plugins.actions
import advene.gui.plugins.contenthandlers
from advene.gui.views import AdhocViewParametersParser
import advene.gui.views.checker
import advene.gui.views.timeline
import advene.gui.views.table
import advene.gui.views.logwindow
import advene.gui.views.interactivequery
import advene.gui.views.finder
import advene.gui.views.activebookmarks
from advene.gui.views.bookmarks import Bookmarks
from advene.gui.edit.rules import EditRuleSet
from advene.gui.edit.dvdselect import DVDSelect
from advene.gui.edit.elements import get_edit_popup
from advene.gui.edit.create import CreateElementPopup
from advene.gui.edit.merge import MergerView
from advene.gui.edit.corpusmerge import MultiMergerView
from advene.gui.evaluator import Evaluator
from advene.gui.views.accumulatorpopup import AccumulatorPopup
import advene.gui.edit.imports
import advene.gui.edit.properties
import advene.gui.edit.montage
from advene.gui.edit.timeadjustment import TimeAdjustment
from advene.gui.edit.frameselector import FrameSelector
import advene.gui.popup
from advene.gui.views.viewbook import ViewBook
from advene.gui.views.html import HTMLView
from advene.gui.views.scroller import ScrollerView
from advene.gui.views.caption import CaptionView

class AdveneWindow(Gtk.ApplicationWindow):
    def __init__(self, application, *p, menu_definition=None):
        super().__init__(application=application, *p)

        self.application = application

        # For backward compatibility
        self.win = self

        self.insert_action_group("app", application)
        self.menu_map = {}
        self.menu_model = self.build_menu(menu_definition, self.menu_map)

        # layout
        self.layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self.layout)

        # create menubar widget from the model
        self.menubar = Gtk.MenuBar.new_from_model(self.menu_model)
        self.layout.pack_start(self.menubar, False, False, 0)

        self.toolbar_container=Gtk.HBox()

        self.fileop_toolbar=Gtk.Toolbar()
        self.fileop_toolbar.set_style(Gtk.ToolbarStyle.ICONS)
        self.fileop_toolbar.set_show_arrow(False)
        self.toolbar_container.pack_start(self.fileop_toolbar, True, True, 0)

        self.adhoc_hbox=Gtk.HBox()
        self.toolbar_container.pack_start(self.adhoc_hbox, True, True, 0)

        self.search_hbox=Gtk.HBox()
        self.toolbar_container.pack_start(self.search_hbox, False, True, 0)
        self.layout.pack_start(self.toolbar_container, False, True, 0)

        self.application_space = Gtk.VBox()
        self.layout.pack_start(self.application_space, True, True, 0)

        # Bottom bar
        self.bottombar = Gtk.HBox()
        self.statusbar = Gtk.Statusbar()
        self.bottombar.pack_start(self.statusbar, True, False, 0)
        self.layout.pack_start(self.bottombar, False, False, 0)

        # self.connect('destroy', Gtk.main_quit)
        self.show_all()

    def make_shortcuts(self, shortcuts):
        # See https://github.com/sk1project/color-picker/blob/master/src/wal-gtk3/base.py
        accel = Gtk.AccelGroup()
        for shortcut, callback in shortcuts:
            modifier = {
                'None': 0,
                'Ctrl': Gdk.ModifierType.CONTROL_MASK,
                'Alt': Gdk.ModifierType.META_MASK,
                'Shift': Gdk.ModifierType.SHIFT_MASK,
                'Ctrl-Shift': Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK}.get(shortcut[0])
            accel.connect(Gdk.keyval_from_name(shortcut[1]), modifier,
                          0, callback)
        self.add_accel_group(accel)

    def build_menu(self, items, menu_map=None, menu=None):

        if menu_map is None:
            menu_map = {}

        if menu is None:
            menu = Gio.Menu()

        for (label, action, tooltip, name) in items:
            if not label:
                # New section
                menu.append_section("", self.build_menu(action, menu_map))
            else:
                if isinstance(action, tuple):
                    # Submenu
                    i = self.build_menu(action, menu_map)
                    menu.append_submenu(label, i)
                    menu_map[name] = i
                elif isinstance(action, Gio.Menu):
                    menu.append_submenu(label, action)
                    menu_map[name] = action
                elif action:
                    i = Gio.MenuItem.new(label, action)
                    menu.append_item(i)
                    menu_map[name] = i

        return menu

class AdveneApplication(Gtk.Application):
    """Main application class.

    Some entry points in the methods:
      - L{__init__} and L{main} : GUI initialization
      - L{update_display} : method regularly called to refresh the display
      - L{on_win_key_press_event} : key press handling

    @ivar gui: the GUI model
    @ivar gui.slider: the slider widget
    @ivar gui.player_status: the player_status widget

    @ivar logbuffer: the log messages text buffer
    @ivar oldstatus: a status cache to check whether a GUI update is necessary

    @ivar annotation: the currently edited annotation (or I{None})
    @type annotation: advene.model.Annotation

    @ivar last_slow_position: a cache to check whether a GUI update is necessary
    @type last_slow_position: int

    @ivar preferences: the current preferences
    @type preferences: dict
    """
    def __init__(self, application_id="org.advene.application",
                 *args, **kwargs):
        super().__init__(*args, application_id=application_id,
                         flags=Gio.ApplicationFlags.HANDLES_OPEN,
                         **kwargs)
        self.gui = None
        #self.settings = Settings.new()

        self.init_config()
        self.main_thread = threading.currentThread()
        self.logbuffer = Gtk.TextBuffer()
        self.busy_cursor = Gdk.Cursor.new(Gdk.CursorType.WATCH)

        # Default value
        self.player_shortcuts_modifier = Gdk.ModifierType.CONTROL_MASK
        self.update_player_control_modifier()

        self.controller = advene.core.controller.AdveneController()
        self.controller.register_gui(self)
        # Text abbreviations
        self.text_abbreviations = dict( line.split(" ", 1)
                                        for line in config.data.preferences['text-abbreviations'].splitlines() )

        # Register defined actions in this instance
        register_named_actions(self)

        # The KeyboardInput event has a 'keyname' parameter ("F1" to "F12")
        # available through the request/keyname TALES expression
        self.controller.register_event('KeyboardInput', _("Input from the keyboard (function keys)"))

        self.menu_definition=(
            (_("_File"), (
                ("", # Empty label -> section (and not submenu)
                 (( _("_New package"), (
                     ( _("Standard template"), 'app.new-package', _("Create a new package with the standard template"), 'new-basic'),
                     ( _("REMIND template"), 'app.new-package-remind', _("Create a new package with the REMIND template"), 'new-remind'),
                     ( _("AdA template"), 'app.new-package-ada', _("Create a new package with the AdA template"), 'new-ada')
                 ),
                    "", ""),
                  ( _("_Open package"), 'app.open-dialog', _("Open a package"), 'open' ),
                  ( _("Open recent"), RecentFilesMenu(
                      Gtk.RecentManager.get_default(),
                      filter=lambda item: item.get_uri().endswith('.azp') or item.get_uri().endswith('.apl')
                  ), _("Show recently opened packages"), 'open_recent' ),
                  ( _("_Save package") + " [Ctrl-S]", 'app.save', _("Save the package"), 'save' ),
                  ( _("Save package as..."), 'app.save-as', _("Save the package as..."), 'save_as' ),
                  ( _("Close package"), 'app.close', _("Close the package"), 'close' ),
                  ),
                 "", ""),
                ("",
                 (( _("Save session"), 'app.save-session', _("Save the current session (list of opened packages)"), "session_save" ),
                  ( _("Save workspace"), (
                      ( _("...as package view"), 'app.save-workspace-as-view', "", "workspace_save" ),
                      ( _("...as standard workspace"), 'app.save-workspace-as-default', _("Use the current layout as standard workspace in the future"), "workspace_save_as_default")),
                    "", ""),
                  ),
                 "", ""),
                ("",
                 (( _("Associate a video _File"), 'app.open-video', _("Associate a video file"), "open_video_file" ),
                  ( _("Associate a _DVD"), 'app.open-dvd', _("Associate a chapter from a DVD"), "open_video_dvd" ),
                  ( _("Associate a _Video URL"), 'app.open-video-stream', _("Enter a video URL address"), "open_video_stream" ),
                  ),
                 "", ""),
                ("",
                 (( _("_Import File"), 'app.import-file', _("Import data from an external source"), "import_file" ),
                  ( _("_Process video"), 'app.process-video', _("Import data from video processing algorithms"), "process_video"),
                  ), "", ""),
                ("",
                 (( _("_Merge packages"), 'app.merge-package', _("Merge elements from other packages"), "package_merge" ),
                  ( _("Import package"), 'app.import-package', _("Import elements from another package"), "package_import" ),
                  ( _("Import _DVD chapters"), 'app.import-dvd-chapters', _("Create annotations based on DVD chapters"), "dvd_chapters_import" ),
                  ),
                 "", ""),
                ("",
                 (( _("_Export..."), 'app.export', _("Export data to another format"), "package_export" ),
                  ( _("_Website export..."), 'app.export-website', _("Export views to a website"), "package_export_website" ),
                  ),
                 "", ""),
                ( _("_Quit"), 'app.quit', "", "quit" ),
            ), "", "" ),
            (_("_Edit"), (
                ( _("_Undo") + " [Ctrl-Z]", 'app.undo', "", "undo" ),
                ( _("_Find"), 'app.find', "", "find" ),
                ( _("Create"), (
                    ( _("Schema"), 'app.create-schema', "", "create_schema"),
                    ( _("View"), 'app.create-view', "", "create_view"),
                    ( _("Query"), 'app.create-query', "", "create_query"),
                    ( _("Annotation Type"), 'app.create-annotation-type', "", "create_annotation_type"),
                    ( _("Relation Type"), 'app.create-relation-type', "", "create_relation_type"),
                ), "", "" ),
                ( _("_Global actions"), 'app.global_actions', "", "global_actions" ),
                ( _("P_ackage properties"), 'app.edit-package-properties', _("Edit package properties"), "package_properties" ),
                ( _("P_references"), 'app.edit-preferences', _("Interface preferences"), "preferences" ),
            ), "", "" ),
            (_("_View"), (
                # Note: this will be populated from registered_adhoc_views
                ( _("_Start Web Browser"), "app.open-adhoc-view('webbrowser')", _("Start the web browser"), "open_web_browser" ),
                ( _("Simplify interface"), "app.simplify-interface", _("Simplify the application interface (toggle)"), "simplify_interface"),
                ( _("Evaluator") + " [Ctrl-e]", "app.evaluator", _("Open python evaluator window"), "evaluator" ),
                ( _("Webserver log"), "app.show-webserver-log", "", "open_web_logs" ),
                ( _("Open view"), Gio.Menu(), "", "adhoc_view_menu")
            ), "", "adhoc_view" ),
            (_("_Player"), (
                ( _("Go to _Time"), "app.goto-time-dialog", _("Goto a specified time code"), "goto_timecode" ),
                ( _("Verify video _Checksum"), "app.verify-video-checksum", _("Verify the video checksum, if available."), "verify_video_checksum" ),
                ( _("Save _ImageCache"), "app.save-imagecache", _("Save the contents of the ImageCache to disk"), "imagecache_save" ),
                ( _("Reset ImageCache"), "app.reset-imagecache", _("Reset the ImageCache"), "imagecache_reset" ),
                ( _("_Restart player"), "app.player-restart", _("Restart the player"), "player_restart" ),
                ( _("Display _Media information"), "app.show-media-information", _("Display information about the current media"), "media_information" ),
                ( _("Update annotation screenshots"), "app.update-screenshots", _("Update screenshots for annotation bounds"), "screenshot_update" ),
                ( _("_Select player"), Gio.Menu(), _("Select the player plugin"), "player_select_menu" ),
            ), "", "" ),
            (_("Corpus"), (
                ( _("Build corpus"), "app.corpus-build", _("Build a corpus by package selection"), "corpus_build" ),
                ( _("Load corpus"), "app.corpus-load", _("Load a corpus"), "corpus_load" ),
                ( _("Open recent corpuses"), RecentFilesMenu(
                    Gtk.RecentManager.get_default(),
                    filter=lambda item: item.get_uri().endswith('.apl')
                ), _("Show recently opened corpuses"), 'open_recent_corpus' ),
                ( _("Save corpus"), "app.corpus-save", _("Save all loaded packages"), "corpus_save" ),
                ( _("Update template in corpus"), "app.corpus-update-template" , _("Update loaded packages with the given template"), "corpus_update_template" ),
                ( _("Corpus _actions"), 'app.corpus_actions', "", "corpus_actions" ),
                ( _("Export corpus as XLSX"), "app.corpus-export" , _("Export loaded packages as XLSX"), "corpus_export" ),
                ( _("Export corpus as website"), "app.corpus-website-export" , _("Export loaded packages as website"), "corpus_website_export" ),
                ( _("Table of annotations"), "app.corpus-annotations", _("Display all annotations in a table"), "corpus_annotations" ),
                #( _("Corpus analysis"), "app.corpus-analysis", _("Analyse loaded corpus"), "corpus_analysis" ),
                ( _("Corpus statistics"), "app.corpus-statistics", _("Display statistics about loaded corpus"), "corpus_statistics" ),
                ), "", ""),
            (_("Packages"), Gio.Menu(), "", "package_list_menu" ),
            (_("_Help"), (
                ( _("Help"), "app.help", "", "help" ),
                ( _("Get support"), "app.help-support", "", "help_support" ),
                ( _("Check for updates"), "app.check-for-update", "", "help_updates" ),
                ( _("Display shortcuts"), "app.help-shortcuts", "", "help_shortcuts" ),
                ( _("Display logfile"), "app.show-log", _("Display log messages"), "help_open_log"),
                ( _("Open logfile folder"), "app.show-logfile", _("Display logfile folder. It can help when sending the advene.log file by e-mail."), "help_open_log_folder"),
                ( _("_About"), "app.about", "", "help_about" ),
            ), "", "" ),
        )

    def menu_to_actiondict(self, m=None):
        if m is None:
            m = self.get_menubar()
        ad = dict()
        for i in range(m.get_n_items()):
            action = m.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_ACTION)
            if action is not None:
                ad[str(action).strip("'")] = (m, i)
            if m.get_item_link(i, Gio.MENU_LINK_SECTION):
                ad.update(self.menu_to_actiondict(m.get_item_link(i, Gio.MENU_LINK_SECTION)))
            if m.get_item_link(i, Gio.MENU_LINK_SUBMENU):
                ad.update(self.menu_to_actiondict(m.get_item_link(i, Gio.MENU_LINK_SUBMENU)))
        return ad

    def menu_dump(self, m=None):
        if m is None:
            m = self.get_menubar()
        # Dump a menu structure definition
        return [
            {
                'icon': m.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_ICON),
                'label': m.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_LABEL),
                'target': m.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_TARGET),
                'action': m.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_ACTION),
                'action_namespace': m.get_item_attribute_value(i, Gio.MENU_ATTRIBUTE_ACTION_NAMESPACE),
                'section': None if m.get_item_link(i, Gio.MENU_LINK_SECTION) is None else self.menu_dump(m.get_item_link(i, Gio.MENU_LINK_SECTION)),
                'submenu': None if m.get_item_link(i, Gio.MENU_LINK_SUBMENU) is None else self.menu_dump(m.get_item_link(i, Gio.MENU_LINK_SUBMENU))
            }
            for i in range(m.get_n_items())
            ]

    def initialize_gui(self):
        logger.debug("initialize_gui")
        # Windows are associated with the application
        # when the last one is closed the application shuts down
        self.gui = AdveneWindow(application=self, menu_definition=self.menu_definition)
        self.set_menubar(self.gui.menu_model)

        dialog.set_default_transient_parent(self.gui)

        self.toolbuttons = {}
        for (ident, stock, action_name, tip) in (
                ('open', Gtk.STOCK_OPEN, 'open-dialog', _("Open a package file")),
                ('save', Gtk.STOCK_SAVE, 'save', _("Save the current package")),
                ('save_as', Gtk.STOCK_SAVE_AS, 'save-as', _("Save the package with a new name")),
                ('select_file', 'moviefile.png', 'open-video', _("Open video file...")),
                ('select_dvd', Gtk.STOCK_CDROM, 'open-dvd', _("Open DVD")),
                (None, None, None, None),
                ('undo', Gtk.STOCK_UNDO, 'undo', _("Undo")),
                (None, None, None, None),
                ('create_text_annotation', 'text_annotation.png', 'create-text-annotation', _("Create a text annotation")),
                ('create_svg_annotation', 'svg_annotation.png', 'create-svg-annotation', _("Create a graphical annotation")),
        ):
            if stock is None:
                b = Gtk.SeparatorToolItem()
            elif ident == 'open':
                b = Gtk.MenuToolButton(stock)
                b.set_arrow_tooltip_text(_("List recently opened packages"))
                f = Gtk.RecentFilter()
                f.add_application(GObject.get_application_name())
                recent = Gtk.RecentChooserMenu()
                recent.add_filter(f)
                recent.set_show_icons(False)
                recent.set_sort_type(Gtk.RecentSortType.MRU)
                b.set_menu(recent)
                recent.connect('item-activated', lambda rcmenu: self.activate_action('open', to_variant(rcmenu.get_current_uri())))
            elif stock.startswith('gtk-'):
                b = Gtk.ToolButton(stock)
            else:
                i = Gtk.Image()
                i.set_from_file( config.data.advenefile( ('pixmaps', stock ) ) )
                b = Gtk.ToolButton(icon_widget=i)
            if tip is not None:
                b.set_tooltip_text(tip)
            if action_name is not None:
                b.connect('clicked', lambda b, a: self.activate_action(a), action_name)

            self.gui.fileop_toolbar.insert(b, -1)
            if ident is not None:
                self.toolbuttons[ident] = b
        self.gui.fileop_toolbar.show_all()

        # Snapshotter activity monitor
        def display_snapshot_monitor_menu(v):
            s = getattr(self.controller.player, 'snapshotter', None)

            m = Gtk.Menu()
            if s:
                m.append(Gtk.MenuItem(_("Snapshotter activity")))
                m.append(Gtk.SeparatorMenuItem())
                m.append(Gtk.MenuItem(_("%d queued requests") % s.timestamp_queue.qsize()))
                i = Gtk.MenuItem(_("Cancel all requests"))
                i.connect('activate', lambda i: s.clear() or True)
                m.append(i)

            else:
                m.append(Gtk.MenuItem(_("No snapshotter")))
            m.show_all()
            m.popup_at_pointer(None)
            return True

        self.snapshotter_image = {
            'idle': Gtk.Image.new_from_file( config.data.advenefile( ( 'pixmaps', 'snapshotter-idle.png') )),
            'running': Gtk.Image.new_from_file( config.data.advenefile( ( 'pixmaps', 'snapshotter-running.png') )),
            }

        def set_state(b, state=None):
            """Set the state of the snapshotter icon.

            state can be either None (no snapshotter), 'idle', 'running'
            """
            if state == b._state:
                return True
            b._state = state
            if state is None:
                b.hide()
            elif state == 'idle':
                b.set_image(self.snapshotter_image[state])
                b.set_tooltip_text(_("No snapshotting activity"))
                b.show()
            elif state == 'running':
                b.set_image(self.snapshotter_image[state])
                b.set_tooltip_text(_("Snapshotting"))
                b.show()
            return True

        b = get_pixmap_button('snapshotter-idle.png', display_snapshot_monitor_menu)
        b._state = None
        b.set_relief(Gtk.ReliefStyle.NONE)
        self.gui.bottombar.pack_start(b, False, True, 0)
        self.snapshotter_monitor_icon = b
        b.set_state=set_state.__get__(b)

        # Log messages button
        def display_log_messages(v):
            self.open_adhoc_view('logmessages', destination='south')
            return True
        b=get_pixmap_button('logmessages.png', display_log_messages)
        b.set_tooltip_text(_("Display application log messages"))
        b.set_relief(Gtk.ReliefStyle.NONE)
        self.gui.bottombar.pack_start(b, False, True, 0)
        b.show()

        # Resize the main window
        window=self.gui
        window.connect('key-press-event', self.on_win_key_press_event)
        window.connect('delete-event', self.on_exit)
        self.init_window_size(window, 'main')
        window.set_icon_list(self.get_icon_list())

        # Last auto-save time (in ms)
        self.last_auto_save=time.time()*1000

        # n-sized list of last edited/created elements.
        # n=config.data.preferences['edition-history-size']
        self.last_edited=[]
        self.last_created=[]

        # Frequently used GUI widgets
        self.slider_move = False
        # Will be initialized in get_visualisation_widget
        self.gui.stbv_combo = None

        # Dictionary of registered adhoc views
        self.registered_adhoc_views={}
        self.gui_plugins=[]
        # Register plugins.
        for n in ('plugins', 'views', 'edit'):
            try:
                plugins = self.controller.load_plugins(os.path.join(
                                                       os.path.dirname(advene.__file__), 'gui', n),
                                                       prefix="advene_gui_%s" % n)
                self.gui_plugins.extend(plugins)
            except OSError:
                logger.error("OSerror while trying to load %s plugins" % n)
        # Explicitly register checker view (which is no longer a plugin)
        self.register_viewclass(advene.gui.views.checker.CheckerView)
        self.register_viewclass(MultiMergerView)
        self.register_viewclass(MergerView)

        def update_quicksearch_sources(mi):
            """Display a dialog allowing to edit quicksearch-sources setting.
            """
            d = Gtk.Dialog(title=_("Quicksearch lists"),
                           parent=self.gui,
                           flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                           buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                     Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ))

            d.vbox.pack_start(Gtk.Label(_("Please specify the lists of elements to be searched.")), False, False, 0)
            sw = Gtk.ScrolledWindow ()
            sw.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            typelist = Gtk.VBox()
            for el in self.controller.defined_quicksearch_sources:
                b=Gtk.CheckButton(el.title, use_underline=False)
                b._element = el
                b.set_active(el.value in config.data.preferences['quicksearch-sources'])
                typelist.pack_start(b, False, True, 0)
            sw.add(typelist)
            d.vbox.pack_start(sw, True, True, 1)
            d.vbox.show_all()
            d.connect('key-press-event', dialog.dialog_keypressed_cb)
            d.show()
            dialog.center_on_mouse(d)
            res=d.run()
            if res == Gtk.ResponseType.OK:
                # Update quicksearch-sources
                elements=[ but._element
                           for but in typelist.get_children()
                           if hasattr(but, 'get_active') and but.get_active() ]
                config.data.preferences['quicksearch-sources']=[ el.value for el in elements ]
                # Update tooltip
                label="\n".join( el.title for el in elements )
                self.quicksearch_button.set_tooltip_text(_("Searching on %s.\nLeft click to launch the search, right-click to set the quicksearch options") % label)
                self.quicksearch_entry.set_tooltip_text(_('String to search in %s') % label)
            d.destroy()
            return True

        self.quicksearch_button=get_small_stock_button(Gtk.STOCK_FIND)
        self.quicksearch_entry=Gtk.Entry()
        self.quicksearch_entry.set_tooltip_text(_('String to search'))

        def quicksearch_options(button, event):
            """Generate the quicksearch options menu.
            """
            if event.type != Gdk.EventType.BUTTON_PRESS:
                return False
            menu=Gtk.Menu()
            item=Gtk.MenuItem(_("Launch search"))
            item.connect('activate', self.do_quicksearch)
            if not self.quicksearch_entry.get_text():
                item.set_sensitive(False)
            menu.append(item)
            item=Gtk.CheckMenuItem(_("Ignore case"))
            item.set_active(config.data.preferences['quicksearch-ignore-case'])
            item.connect('toggled', lambda i: config.data.preferences.__setitem__('quicksearch-ignore-case', i.get_active()))
            menu.append(item)

            item=Gtk.MenuItem(_("Searched elements"))
            item.connect('activate', update_quicksearch_sources)
            menu.append(item)

            menu.show_all()
            menu.popup_at_pointer(None)
            return True

        hb=self.gui.search_hbox
        self.quicksearch_entry.connect('activate', self.do_quicksearch)
        hb.pack_start(self.quicksearch_entry, False, True, 0)
        self.quicksearch_button.connect('button-press-event', quicksearch_options)
        hb.pack_start(self.quicksearch_button, False, False, 0)
        hb.show_all()

        # Player status
        self.update_player_labels()
        self.oldstatus = "NotStarted"
        self.last_slow_position = 0

        self.current_annotation = None
        # Internal rule used for annotation loop
        self.annotation_loop_rule=None

        # Edited data in fullscreen mode
        self.edited_annotation_text = None
        self.edited_annotation_begin = None

        # List of active annotation views (timeline, tree, ...)
        self.adhoc_views = []
        # List of active element edit popups
        self.edit_popups = []

        self.edit_accumulator = None

        # Populate default STBV and type lists
        self.update_gui()

        # FIXME: We have to register LogWindow actions before we load the ruleset
        # but we should have an introspection method to do this automatically
        self.logwindow = advene.gui.views.logwindow.LogWindow(controller=self.controller)
        self.register_view(self.logwindow)

        self.visualisationwidget = self.get_visualisation_widget()
        self.gui.application_space.add(self.visualisationwidget)

        self.visual_id = None

        # Adhoc view toolbuttons signal handling
        def adhoc_view_drag_sent(widget, context, selection, targetType, eventTime, name):
            if targetType == config.data.target_type['adhoc-view']:
                selection.set(selection.get_target(), 8, encode_drop_parameters(name=name))
                return True
            return False

        def adhoc_view_drag_begin(widget, context, pixmap, view_name):
            w=Gtk.Window(Gtk.WindowType.POPUP)
            w.set_decorated(False)
            hb=Gtk.HBox()
            i=Gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            hb.pack_start(i, False, True, 0)
            hb.pack_start(Gtk.Label(view_name), False, False, 0)
            w.add(hb)
            w.show_all()
            Gtk.drag_set_icon_widget(context, w, 16, 16)
            return True

        # Populate the Views submenu
        adhoc_views = [ self.registered_adhoc_views[name] for name in sorted(self.registered_adhoc_views) ]
        adhoc_views_menu_dict = dict( (cl.view_name, (cl.view_name,
                                                      f"app.open-adhoc-view('{cl.view_id}')",
                                                      cl.tooltip,
                                                      f"toolbar-adhoc-view-{cl.view_id}") )
                                      for cl in adhoc_views)

        # Build the menu of all defined views
        adhoc_views_menu = self.gui.build_menu(sorted(adhoc_views_menu_dict.values(),
                                                      key=lambda t: t[0]),
                                               menu=self.gui.menu_map['adhoc_view_menu'])

        # Generate the adhoc view buttons
        hb=self.gui.adhoc_hbox
        for name, tip, pixmap in (
                ('timeline', _('Timeline'), 'timeline.png'),
                ('finder', _('Package finder'), 'finder.png'),
                ('transcription', _('Transcription of annotations'), 'transcription.png'),
                ('table', _('Annotation table'), 'table.png'),

                ('', '', ''),
                ('transcribe', _('Note-taking editor'), 'transcribe.png'),
                ('activebookmarks', _('Active bookmarks'), 'bookmarks.png'),
                ('', '', ''),

                ('tagbag', _("Bag of tags"), 'tagbag.png'),
                ('browser', _('TALES explorer'), 'browser.png'),
                ('checker', _('Constraint checker'), 'checker.png'),
                ('montage', _("Dynamic montage"), 'montage.png'),
                ('videoplayer', _("Video player"), 'videoplayer.png'),
                ('', '', ''),

                ('webbrowser', _('Open a comment view in the web browser'), 'web.png'),
                ('comment', _("Create or open a comment view"), 'comment.png'),
                ('', '', ''),

                ('editaccumulator', _('Edit window placeholder (annotation and relation edit windows will be put here)'), 'editaccumulator.png'),
                ('editionhistory', _("Display edition history"), 'editionhistory.png'),
            ):
            if not name:
                # Separator
                # FIXME: let's ignore it for the moment (conversion to Gio.Menu)
                continue
            if name in ('browser', 'schemaeditor') and not config.data.preferences['expert-mode']:
                continue
            if name not in ('webbrowser', 'comment') and name not in self.registered_adhoc_views:
                self.log("Missing basic adhoc view %s" % name)
                continue
            b=Gtk.Button()
            i=Gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            b.add(i)
            b.set_tooltip_text(tip)
            b.connect('drag-begin', adhoc_view_drag_begin, pixmap, tip)
            b.connect('drag-data-get', adhoc_view_drag_sent, name)
            b.connect('clicked', lambda b, v: self.activate_action("open-adhoc-view", v), to_variant(name))
            b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                              config.data.get_target_types('adhoc-view'), Gdk.DragAction.COPY)
            hb.pack_start(b, False, True, 0)
            if name == 'webbrowser' and (self.controller.server is None or not self.controller.server.is_running()):
                b.set_sensitive(False)
                b.set_tooltip_text(_("The webserver could not be started. Static views cannot be accessed."))
            if name in adhoc_views_menu_dict:
                (label, callback, tooltip, action_name) = adhoc_views_menu_dict
                adhoc_views_menu.append_item(Gio.MenuItem.new(label, action_name))
        hb.show_all()

        update_player_menu(self.gui.menu_map['player_select_menu'], self.controller.player.player_id)

        defaults=config.data.advenefile( ('defaults', 'workspace.xml'), 'settings')
        if os.path.exists(defaults):
            try:
                # a default workspace has been saved. Load it and
                # ignore the default adhoc view specification.
                stream=open(defaults, encoding='utf-8')
                tree=ET.parse(stream)
                stream.close()
                self.workspace_restore(tree.getroot())
            except Exception:
                logger.error("Cannot restore default workspace", exc_info=True)
        else:
            # Open default views
            self.open_adhoc_view('timeline', destination='south')
            self.open_adhoc_view('tree', destination='fareast')

        # If there were unknown arguments, propose to import them
        for uri in self.controller.unknown_args:
            self.open_adhoc_view('importerview', filename=uri)

        # Use small toolbar button everywhere
        Gtk.Settings.get_default().set_property('gtk_toolbar_icon_size', Gtk.IconSize.SMALL_TOOLBAR)
        play=self.player_toolbar.get_children()[0]
        play.set_can_focus(True)
        play.grab_focus()
        self.update_control_toolbar(self.player_toolbar)

        self.event_source_update_display=GObject.timeout_add (100, self.update_display)
        self.event_source_slow_update_display=GObject.timeout_add (1000, self.slow_update_display)
        # Do we need to make an update check
        if (config.data.preferences['update-check']
            and time.time() - config.data.preferences['last-update'] >= 7 * 24 * 60 * 60):
            config.data.preferences['last-update']=time.time()
            self.check_for_update()
        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        if config.data.debug:
            self.controller._state=self.controller.event_handler.dump()
        Gtk.main ()
        self.controller.notify ("ApplicationEnd")

    def do_startup(self, *args, **kwargs):
        logger.debug(f"do_startup {args}")
        Gtk.Application.do_startup(self)

        # self.settings.connect("changed", self.on_settings_changed)
        if not self.gui:
            self.initialize_gui()

    def do_activate(self, *args, **kwargs):
        logger.debug(f"do_activate {args}")
        # Gtk.Application.do_activate(self)
        #if self._application_id == 'org.gnome.gitlab.somas.Apostrophe.Devel':
        #    self.window.get_style_context().add_class('devel')
        if self.gui:
            self.gui.present()

    def init_gettext(self):
        """Proxy for the module-level init_gettext method.
        """
        config.init_gettext()

    def init_config(self):
        """Enrich config module with Gtk-related elements.
        """
        def log_error(prov, section, error):
            logger.error("Error while parsing advene.css file in %s: %s" % (section, error))
        for name, item in config.data.drag_type.items():
            config.data.target_entry[name] = Gtk.TargetEntry.new(item[0][0], 0, item[0][2])
        # Load advene.css file
        css_provider = Gtk.CssProvider()
        css_provider.connect('parsing-error', log_error)
        css_provider.load_from_path(str(config.data.advenefile('advene.css')))
        context = Gtk.StyleContext()
        context.add_provider_for_screen(Gdk.Screen.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


    def get_icon_list(self):
        """Return the list of icon pixbuf appropriate for Window.set_icon_list.
        """
        if not hasattr(self, '_icon_list'):
            icons = [ GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile(
                                                     ( 'pixmaps', 'icon_advene%d.png' % size ) ))
                      for size in (16, 32, 48, 64, 128) ]
            self._icon_list = [ i for i in icons if i is not None ]
        return self._icon_list

    def set_busy_cursor(self, busy=False):
        """Un/Set the busy cursor for the main window.
        """
        window = self.gui.win.get_window()
        if window:
           window.set_cursor(self.busy_cursor if busy else None)

    def update_player_labels(self):
        """Update the representation of player status.

        They may change when another player is selected.
        """
        p=self.controller.player
        self.active_player_status=(p.PlayingStatus, p.PauseStatus)
        self.statustext={
            p.PlayingStatus  : _("Playing"),
            p.PauseStatus    : _("Pause"),
            p.InitStatus     : _("Init"),
            p.EndStatus      : _("End"),
            p.UndefinedStatus: _("Undefined"),
            }

    def update_player_control_modifier(self):
        """Update the actual value of player control modifier.
        """
        pref = config.data.preferences['player-shortcuts-modifier']
        modifier = Gtk.accelerator_parse(pref).accelerator_mods
        if int(modifier) != 0:
            self.player_shortcuts_modifier = modifier
        else:
            logger.error(_("Wrong player shortcut modifier %s in configuration. Fallback on Control."), pref)
            self.player_shortcuts_modifier = Gdk.ModifierType.CONTROL_MASK

    def annotation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        annotation=context.evaluateValue('annotation')
        event=context.evaluateValue('event')
        if annotation.ownerPackage != self.controller.package:
            return True
        self.updated_element(event, annotation)
        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_annotation', None)
                if m:
                    m(annotation=annotation, event=event)
            except Exception:
                logger.error(_("Exception in update_annotation"), exc_info=True)
        # Update the content indexer
        if event.endswith('EditEnd') or event.endswith('Create'):
            # Update the type fieldnames
            if annotation.content.mimetype.endswith('/x-advene-structured'):
                annotation.type._fieldnames.update(helper.common_fieldnames([ annotation ]))

        # Refresh the edit popup for the associated relations
        for e in [ el for el in self.edit_popups if el.element in annotation.relations ]:
            e.refresh()
        return True

    def relation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        relation=context.evaluateValue('relation')
        event=context.evaluateValue('event')
        if relation.ownerPackage != self.controller.package:
            return True
        self.updated_element(event, relation)
        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_relation', None)
                if m:
                    m(relation=relation, event=event)
            except Exception:
                logger.error(_("Exception in update_relation"), exc_info=True)
        # Refresh the edit popup for the members
        for e in [ el for el in self.edit_popups if el.element in relation.members ]:
            e.refresh()
        return True

    def view_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        view=context.evaluateValue('view')
        event=context.evaluateValue('event')
        if view.ownerPackage != self.controller.package:
            return True
        self.updated_element(event, view)
        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_view', None)
                if m:
                    m(view=view, event=event)
            except Exception:
                logger.error(_("Exception in update_view"), exc_info=True)

        if view.content.mimetype == 'application/x-advene-ruleset':
            # Update the combo box
            self.update_stbv_list()
            if event == 'ViewEditEnd' and self.controller.current_stbv == view:
                # We were editing the current STBV: take the changes
                # into account
                self.controller.activate_stbv(view, force=True)

        return True

    def query_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        query=context.evaluateValue('query')
        event=context.evaluateValue('event')
        if query.ownerPackage != self.controller.package:
            return True
        self.updated_element(event, query)
        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_query', None)
                if m:
                    m(query=query, event=event)
            except Exception:
                logger.error(_("Exception in update_query"), exc_info=True)
        return True

    def resource_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        resource=context.evaluateValue('resource')
        event=context.evaluateValue('event')
        if resource.ownerPackage != self.controller.package:
            return True
        self.updated_element(event, resource)

        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_resource', None)
                if m:
                    m(resource=resource, event=event)
            except Exception:
                logger.error(_("Exception in update_resource"), exc_info=True)
        return True

    def schema_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        schema=context.evaluateValue('schema')
        event=context.evaluateValue('event')
        if schema.ownerPackage != self.controller.package:
            return True
        self.updated_element(event, schema)

        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_schema', None)
                if m:
                    m(schema=schema, event=event)
            except Exception:
                logger.error(_("Exception in update_schema"), exc_info=True)
        return True

    def annotationtype_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        at=context.evaluateValue('annotationtype')
        event=context.evaluateValue('event')
        if at.ownerPackage != self.controller.package:
            return True

        # Update the content indexer
        if event.endswith('Create'):
            self.controller.package._indexer.element_update(at)
            if not hasattr(at, '_fieldnames'):
                at._fieldnames = set()
        self.updated_element(event, at)
        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_annotationtype', None)
                if m:
                    m(annotationtype=at, event=event)
            except Exception:
                logger.error(_("Exception in update_annotationtype"), exc_info=True)
        # Update the current type menu
        self.update_gui()
        return True

    def relationtype_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        rt=context.evaluateValue('relationtype')
        event=context.evaluateValue('event')
        if rt.ownerPackage != self.controller.package:
            return True

        self.updated_element(event, rt)
        for v in self.adhoc_views:
            try:
                m = getattr(v, 'update_relationtype', None)
                if m:
                    m(relationtype=rt, event=event)
            except AttributeError:
                pass
            except Exception:
                logger.error(_("Exception in update_relationtype"), exc_info=True)
        # Update the content indexer
        if event.endswith('Create'):
            self.controller.package._indexer.element_update(rt)

        return True

    def updated_element(self, event, element):
        if event.endswith('EditEnd'):
            # Update the content indexer
            self.controller.package._indexer.element_update(element)

            elements = self.last_edited
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == element ]:
                e.refresh()
        elif event.endswith('Create'):
            # Update the content indexer
            self.controller.package._indexer.element_update(element)
            elements = self.last_created
        elif event.endswith('Delete'):
            # Close the edit popups
            for e in [ e for e in self.edit_popups if e.element == element ]:
                e.close()
            try:
                self.last_edited.remove(element)
            except ValueError:
                pass
            try:
                self.last_created.remove(element)
            except ValueError:
                pass
            return True
        else:
            return True
        s = config.data.preferences['edition-history-size']
        if element in elements:
            elements.remove(element)
        elements.append(element)
        if len(elements) > s:
            elements.pop(0)
        return True

    def handle_element_delete(self, context, parameters):
        """Handle element deletion.

        It notably closes all edit windows for the element.
        """
        event=context.evaluateValue('event')
        if not event.endswith('Delete'):
            return True
        el=event.replace('Delete', '').lower()
        element=context.evaluateValue(el)
        for e in [ e for e in self.edit_popups if e.element == element ]:
            e.close_cb()
        return True

    def on_view_activation(self, context, parameters):
        """Handler used to update the STBV GUI.
        """
        combo = self.gui.stbv_combo
        store = combo.get_model()
        i = store.get_iter_first()
        while i is not None:
            if store.get_value(i, 1) == self.controller.current_stbv:
                combo.set_active_iter(i)
                return True
            i=store.iter_next(i)

        return True

    def updated_position_cb (self, context, parameters):
        """Method called upon video player position change.
        """
        position_before=context.evaluateValue('position_before')
        self.navigation_history.append(position_before)
        # Notify views that the position has been reset.
        for v in self.adhoc_views:
            try:
                v.position_reset ()
            except AttributeError:
                pass
        return True

    def player_stop_cb (self, context, parameters):
        """Method called upon video player stop.
        """
        # Notify views that the position has been reset.
        for v in self.adhoc_views:
            try:
                v.position_reset ()
            except AttributeError:
                pass
        return True

    @named_action(name="app.select-player")
    def select_player(self, player: str):
        player = config.data.players[player]
        self.controller.select_player(player)
        return True

    @named_action(name="app.activate-package")
    def activate_package(self, alias: str):
        self.controller.activate_package(alias)
        return True

    @named_action(name="app.goto-time-dialog")
    def goto_time_dialog(self, *p):
        """Display a dialog to go to a given time.
        """
        t = self.input_time_dialog()
        if t is not None:
            self.controller.update_status("seek", t)
        return True

    @named_action(name="app.verify-video-checksum")
    def verify_video_checksum(self, *p):
        name = helper.uri2path(self.controller.get_default_media())
        if not name:
            dialog.message_dialog(_("The video does not seem to be a local resource. Cannot verify its checksum."),
                                  icon=Gtk.MessageType.ERROR)
            return True

        stored = self.controller.package.getMetaData(config.data.namespace, "media_checksum")

        def do_verify(callback):
            computed = helper.mediafile_checksum(name, callback)
            if computed is None:
                dialog.message_dialog(_("Checksum was cancelled."))
                return True
            logger.warning("Checksum: stored %s - computed %s", stored, computed)
            if stored:
                if stored != computed:
                    if dialog.message_dialog(_("The %s checksum does not match the information that was stored in the package. You should check that the file is appropriate. Do you want to update the stored checksum?") % name,
                                             icon=Gtk.MessageType.QUESTION):
                        self.controller.package.setMetaData(config.data.namespace, "media_checksum", str(computed))
                        return True
                else:
                    dialog.message_dialog(_("The %s checksum matches the stored checksum.") % name)
                    return True
            else:
                if dialog.message_dialog(_("No checksum was stored in the package. Do you want to store this information?"),
                                         icon=Gtk.MessageType.QUESTION):
                    self.controller.package.setMetaData(config.data.namespace, "media_checksum", str(computed))
                    return True

        dialog.progress_dialog(title=_("Computing video checksum"),
                               label=_("Computing checksum"),
                               controller=self.controller,
                               runner=do_verify)
        return True

    def input_time_dialog(self, *p):
        """Display a dialog to enter a time value.
        """
        d = Gtk.Dialog(title=_("Enter the new time value"),
                       parent=self.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ))

        ta=TimeAdjustment(value=self.gui.slider.get_value(),
                          controller=self.controller,
                          videosync=False,
                          editable=True,
                          compact=False)
        ta.entry.connect("activate", lambda w: d.response(Gtk.ResponseType.OK))
        d.vbox.pack_start(ta.widget, False, True, 0)
        d.show_all()
        dialog.center_on_mouse(d)
        ta.entry.select_region(0, -1)
        ta.entry.grab_focus()
        res=d.run()
        retval=None
        if res == Gtk.ResponseType.OK:
            retval = ta.get_value()
        d.destroy()
        return retval

    def search_replace_dialog(self, elements, title=None, default_search=None):
        """Display a search-replace dialog.
        """
        if title is None:
            title = _("Replace content in %d elements") % len(elements)
        d = Gtk.Dialog(title=title,
                       parent=self.gui.win,
                       flags=Gtk.DialogFlags.MODAL | Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                 Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 ))
        label = Gtk.Label(label=title + "\nLeave the first field empty to unconditionnaly replace all contents.\nYou can use special characters \\n or \\t.")
        label.set_line_wrap(True)
        label.show()
        d.vbox.pack_start(label, False, True, 0)

        hb = Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Find word") + " "), False, False, 0)
        search_entry = Gtk.Entry()
        search_entry.set_text(default_search or "")
        hb.pack_start(search_entry, True, True, 0)
        d.vbox.pack_start(hb, False, True, 0)

        hb = Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Replace by") + " "), False, False, 0)
        replace_entry = Gtk.Entry()
        hb.pack_start(replace_entry, True, True, 0)
        d.vbox.pack_start(hb, False, True, 0)

        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        d.show_all()
        dialog.center_on_mouse(d)
        res = d.run()
        if res == Gtk.ResponseType.OK:

            # When copy/pasting from the transcription
            # (e.g.[SPEAKER_00]) non-printable characters are present
            # It would be best to fix it in the source of the copy, but we can do it here too
            search = unescape_string(printable(search_entry.get_text()))
            replace = unescape_string(printable(replace_entry.get_text()))
            count = 0
            batch_id = object()
            for a in elements:
                if not isinstance(a, (Annotation, Relation, View)):
                    continue
                if search == "" or search in a.content.data:
                    self.controller.notify('EditSessionStart', element=a, immediate=True)
                    if search:
                        a.content.data = a.content.data.replace(search, replace)
                    else:
                        a.content.data = replace
                    if isinstance(a, Annotation):
                        self.controller.notify('AnnotationEditEnd', annotation=a, batch=batch_id)
                    elif isinstance(a, Relation):
                        self.controller.notify('RelationEditEnd', relation=a, batch=batch_id)
                    elif isinstance(a, View):
                        self.controller.notify('ViewEditEnd', view=a, batch=batch_id)
                    self.controller.notify('EditSessionEnd', element=a)
                    count += 1
            self.log(_('%(search)s has been replaced by %(replace)s in %(count)d element(s).') % locals())
        d.destroy()
        return True

    def render_montage_dialog(self, elements, basename=None, title=None, label=None):
        """Extract a montage/annotation to a new video.
        """
        MontageRenderer = self.controller.generic_features.get('montagerenderer')
        if MontageRenderer is None:
            dialog.message_dialog(_("The video extracting feature is not available."))
            return True
        duration = helper.format_time(sum(a.fragment.duration for a in elements))
        filename = dialog.get_filename(title=_("Destination filename (duration: %s)") % duration,
                                       action=Gtk.FileChooserAction.SAVE,
                                       button=Gtk.STOCK_SAVE,
                                       default_file = basename,
                                       filter='video')
        if filename is None:
            return
        if title is None:
            title = _("Exporting to %s") % filename
        if label is None:
            label = _("Exporting %(duration)s video to\n%(filename)s") % { 'filename': filename,
                                                                           'duration': duration }

        m = MontageRenderer(self.controller, elements)

        w = Gtk.Window()
        w.set_title(title)
        v = Gtk.VBox()
        label = Gtk.Label(label=label % { 'filename': filename } )
        v.add(label)

        pg = Gtk.ProgressBar()
        v.pack_start(pg, False, True, 0)

        hb = Gtk.HButtonBox()
        b = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        def close_encoder(b):
            m.finalize()
            w.destroy()
            return True
        b.connect('clicked', close_encoder)
        hb.pack_start(b, False, True, 0)
        v.pack_start(hb, False, True, 0)

        w.add(v)
        w.show_all()

        def pg_callback(value, msg=''):
            if value is None:
                w.destroy()
                return True
            pg.set_fraction(value)
            if msg:
                pg.set_text(msg)
            return True
        m.render(filename, pg_callback)

        # Keep a reference so that the MontageRenderer is not
        # garbage-collected before the window is closed.
        w.renderer = m

        # FIXME: for debugging
        self.renderer = m
        return True

    def main(self, args=None):
        """Mainloop : App mainloop setup.

        @param args: list of arguments
        @type args: list
        """
        if args is None:
            args=[]

        def media_changed(context, parameters):
            if config.data.preferences['player-autostart'] and 'record' not in self.controller.player.player_capabilities:
                self.controller.queue_action(self.controller.update_status, "start")
                self.controller.queue_action(self.controller.update_status, "pause")

            if config.data.preferences['expert-mode']:
                return True
            uri=context.globals['uri']
            if not uri:
                msg=_("No media association is defined in the package. Please use the 'File/Associate a video file' menu item to associate a media file.")
            elif not os.path.exists(helper.uri2path(uri)) and not helper.is_uri(uri):
                msg=_("The associated media %s could not be found. Please use the 'File/Associate a video file' menu item to associate a media file.") % uri
            else:
                msg=_("You are now working with the following video:\n%s") % uri
            self.controller.queue_action(dialog.message_dialog, msg, modal=False)
            return True

        for events, method in (
                ("PackageLoad", self.manage_package_load),
                ("PackageActivate", self.manage_package_activate),
                ("PackageEditEnd", lambda e, c: self.update_window_title()),
                ("PackageSave", self.manage_package_save),
                ( ('AnnotationCreate', 'AnnotationEditEnd',
                   'AnnotationDelete', 'AnnotationActivate',
                   'AnnotationDeactivate'),
                  self.annotation_lifecycle ),
                ( ('RelationCreate', 'RelationEditEnd',
                   'RelationDelete'),
                  self.relation_lifecycle ),
                ( ('ViewCreate', 'ViewEditEnd', 'ViewDelete'),
                  self.view_lifecycle ),
                ( ('QueryCreate', 'QueryEditEnd', 'QueryDelete'),
                  self.query_lifecycle),
                ( ('ResourceCreate', 'ResourceEditEnd', 'ResourceDelete'),
                  self.resource_lifecycle),
                ( ('SchemaCreate', 'SchemaEditEnd', 'SchemaDelete'),
                  self.schema_lifecycle),
                ( ('AnnotationTypeCreate', 'AnnotationTypeEditEnd',
                   'AnnotationTypeDelete'),
                  self.annotationtype_lifecycle),
                ( ('RelationTypeCreate', 'RelationTypeEditEnd',
                   'RelationTypeDelete'),
                  self.relationtype_lifecycle),
                ("PlayerSeek", self.updated_position_cb),
                ("PlayerStop", self.player_stop_cb),
                ("PlayerChange", self.updated_player_cb),
                ("ViewActivation", self.on_view_activation),
                ( [ '%sDelete' % v for v in ('Annotation', 'Relation', 'View',
                                             'AnnotationType', 'RelationType', 'Schema',
                                             'Resource') ],
                  self.handle_element_delete),
                ('MediaChange', media_changed),
            ):
            if isinstance(events, str):
                self.controller.event_handler.internal_rule (event=events,
                                                             method=method)
            else:
                for e in events:
                    self.controller.event_handler.internal_rule (event=e,
                                                                 method=method)

        self.controller.init(args)
        logger.debug(" Before self.run")
        self.run()
        logger.debug(" After self.run")

    @named_action(name="app.check-for-update")
    def check_for_update(self, *p):
        timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(1)
            u = urllib.request.urlopen('http://www.advene.org/version.txt')
        except Exception:
            socket.setdefaulttimeout(timeout)
            return
        socket.setdefaulttimeout(timeout)
        try:
            data = u.read().decode('utf-8')
        except Exception:
            data = ""
        u.close()
        if not data:
            return False
        info = dict(line.split(':') for line in data.splitlines())
        major, minor = info['version'].split('.')
        major = int(major)
        minor = int(minor)
        info['current'] = advene.core.version.version
        if (1000 * major + minor) > (1000 * advene.core.version.major + advene.core.version.minor):
            # An update is available.
            v = Gtk.VBox()
            msg = textwrap.fill(_("""<span background="#ff8888" size="large"><b>Advene %(version)s has been released</b> on %(date)s, but you are running version %(current)s.\nYou can download the latest version from the Advene website: http://advene.org/</span>""") % info, 55)
            label = Gtk.Label()
            label.set_markup(msg)
            #l.set_line_wrap_mode(True)
            v.add(label)
            b = Gtk.Button(_("Go to the website"))
            def open_site(b):
                self.controller.open_url('http://www.advene.org/download.html')
                return True
            b.connect('clicked', open_site)
            v.pack_start(b, False, True, 0)
            self.popupwidget.display(v, title=_("Advene release"))
        elif p:
            # There were parameters, then we were called from a menu
            # item. In this case, display a dialog stating that there
            # is no update.
            # An update is available.
            self.popupwidget.display_message(_("You are using a up-to-date version of Advene (%(current)s).""") % info, timeout=10000, title=_("Advene is up-to-date"))
        return False

    def update_color(self, element):
        """Update the color for the given element.

        element may be AnnotationType, RelationType or Schema
        """
        try:
            c = self.controller.build_context(here=element)
            colname = c.evaluateValue(element.getMetaData(config.data.namespace, 'color'))
            gtk_color = name2color(colname)
        except Exception:
            gtk_color = None
        d = Gtk.ColorSelectionDialog(_("Choose a color"), parent=self.gui.win)
        if gtk_color:
            d.get_color_selection().set_current_color(gtk_color)
        res = d.run()
        if res == Gtk.ResponseType.OK:
            col = d.get_color_selection().get_current_color()
            element.setMetaData(config.data.namespace, 'color', "string:#%04x%04x%04x" % (col.red,
                                                                                          col.green,
                                                                                          col.blue))
            # Notify the change
            if isinstance(element, AnnotationType):
                self.controller.notify('AnnotationTypeEditEnd', annotationtype=element)
            elif isinstance(element, RelationType):
                self.controller.notify('RelationTypeEditEnd', relationtype=element)
            elif isinstance(element, Schema):
                self.controller.notify('SchemaEditEnd', schema=element)
        else:
            col = None
        d.destroy()
        return col

    def set_current_annotation(self, a):
        """Set the current annotation.
        """
        self.current_annotation=a
        self.update_loop_button()

    def update_loop_button(self):
        """Update the loop button tooltip.
        """
        b=self.player_toolbar.buttons['loop']
        if self.current_annotation is None:
            mes=_("Select an annotation to loop on it")
        else:
            mes=_("Looping on %s") % self.controller.get_title(self.current_annotation)
        b.set_tooltip_text(mes)
        return True

    def get_visualisation_widget(self):
        """Return the main visualisation widget.

        It consists in the embedded video window plus the various views.
        """
        # Viewbooks indexed by zone name (east, west, south, fareast)
        self.viewbook={}
        # Panes indexed by zone name they relate to (east, west,
        # south, fareast)
        self.pane={}

        # self.drawable is used to embed the video player. It was
        # necessary as a generic way of embedding widgets, but now Gst
        # implements a Gtk widget so it could probably be removed, but
        # we need to test this cross-platform
        self.drawable = get_drawable()
        black=Gdk.Color(0, 0, 0)
        for state in (Gtk.StateType.ACTIVE, Gtk.StateType.NORMAL,
                      Gtk.StateType.SELECTED, Gtk.StateType.INSENSITIVE,
                      Gtk.StateType.PRELIGHT):
            self.drawable.modify_bg (state, black)

        self.drawable.add_events(Gdk.EventType.BUTTON_PRESS)
        self.player_toolbar = self.get_player_control_toolbar()
        self.playpause_button = self.player_toolbar.buttons['playpause']

        # Dynamic view selection
        hb=Gtk.HBox()
        #hb.pack_start(Gtk.Label(_('D.view')), False, False, 0)
        self.gui.stbv_combo = Gtk.ComboBox()
        cell = Gtk.CellRendererText()
        cell.props.ellipsize = Pango.EllipsizeMode.MIDDLE
        self.gui.stbv_combo.pack_start(cell, True)
        self.gui.stbv_combo.add_attribute(cell, 'text', 0)
        self.gui.stbv_combo.props.tooltip_text=_("No active dynamic view")

        hb.pack_start(self.gui.stbv_combo, True, True, 0)

        def new_stbv(*p):
            cr = CreateElementPopup(type_=View,
                                    parent=self.controller.package,
                                    controller=self.controller)
            cr.popup()
            return True
        b=get_small_stock_button(Gtk.STOCK_ADD, new_stbv)
        b.set_tooltip_text(_("Create a new dynamic view."))
        hb.pack_start(b, False, True, 0)

        def on_edit_current_stbv_clicked(button):
            """Handle current stbv edition.
            """
            combo=self.gui.stbv_combo
            i=combo.get_active_iter()
            stbv=combo.get_model().get_value(i, 1)
            if stbv is None:
                cr = CreateElementPopup(type_=View,
                                        parent=self.controller.package,
                                        controller=self.controller)
                cr.popup()
                return True
            self.edit_element(stbv)
            return True

        edit_stbv_button=get_small_stock_button(Gtk.STOCK_EDIT, on_edit_current_stbv_clicked)
        edit_stbv_button.set_tooltip_text(_("Edit the current dynamic view."))
        hb.pack_start(edit_stbv_button, False, True, 0)

        def on_stbv_combo_changed (combo=None):
            """Callback used to select the current stbv.
            """
            i=combo.get_active_iter()
            if i is None:
                return False
            stbv=combo.get_model().get_value(i, 1)
            if stbv is None:
                edit_stbv_button.set_sensitive(False)
                combo.props.tooltip_text=_("No dynamic view")
            else:
                edit_stbv_button.set_sensitive(True)
                combo.props.tooltip_text=self.controller.get_title(stbv)
            self.controller.activate_stbv(stbv)
            return True
        self.gui.stbv_combo.connect('changed', on_stbv_combo_changed)
        self.update_stbv_list()

        # Append the volume control to the toolbar
        def volume_change(scale, value):
            if self.controller.player.sound_get_volume() != int(value * 100):
                self.controller.player.sound_set_volume(int(value * 100))
            return True

        self.audio_volume = Gtk.VolumeButton()
        self.audio_volume.set_value(self.controller.player.sound_get_volume() / 100.0)
        ti = Gtk.ToolItem()
        ti.add(self.audio_volume)
        self.audio_volume.connect('value-changed', volume_change)
        self.player_toolbar.insert(ti, -1)
        self.player_toolbar.buttons['volume'] = ti

        # Append the volume control to the toolbar
        def rate_change(spin):
            v = spin.get_value()
            if self.controller.player.get_rate() != v:
                self.controller.player.set_rate(v)
            return True

        self.rate_control = Gtk.SpinButton.new(Gtk.Adjustment.new(1.0, 0.1, 100.0, 0.2, 0.5, 10), 0.2, 1)
        self.rate_control.set_tooltip_text(_("Playing rate"))
        ti = Gtk.ToolItem()
        ti.add(self.rate_control)
        self.rate_control.connect('value-changed', rate_change)
        self.player_toolbar.insert(ti, -1)
        self.player_toolbar.buttons['rate'] = ti

        # Append the loop checkitem to the toolbar
        def loop_toggle_cb(b):
            """Handle loop button action.
            """
            if b.get_active():
                if self.current_annotation:
                    def action_loop(context, target):
                        if (self.player_toolbar.buttons['loop'].get_active()
                            and context.globals['annotation'] == self.current_annotation):
                            self.controller.update_status('seek', self.current_annotation.fragment.begin)
                        return True

                    def reg():
                        # If we are already in the current annotation, do not goto it
                        if self.controller.player.current_position_value not in self.current_annotation.fragment:
                            self.controller.update_status('seek', self.current_annotation.fragment.begin)
                        self.annotation_loop_rule=self.controller.event_handler.internal_rule (event="AnnotationEnd",
                                                                                               method=action_loop)
                        return True
                    self.controller.queue_action(reg)
                else:
                    # No annotation was previously defined, deactivate the button, unset the rule
                    b.set_active(False)
                    if self.annotation_loop_rule is not None:
                        self.controller.event_handler.remove_rule(self.annotation_loop_rule, type_="internal")
            return True

        b = Gtk.ToggleToolButton(Gtk.STOCK_REFRESH)
        self.player_toolbar.buttons['loop'] = b
        self.update_loop_button()
        b.connect('toggled', loop_toggle_cb)
        self.player_toolbar.insert(b, -1)

        # Append the player status label to the toolbar
        ts=Gtk.SeparatorToolItem()
        ts.set_draw(False)
        ts.set_expand(True)
        self.player_toolbar.insert(ts, -1)

        ti=Gtk.ToolItem()
        self.gui.player_status=Gtk.Label(label='--')
        ti.add(self.gui.player_status)
        self.player_toolbar.insert(ti, -1)

        # Create the slider
        adj = Gtk.Adjustment.new(0, 0, 100, 1, 1, 10)
        self.gui.slider = Gtk.Scale.new(Gtk.Orientation.HORIZONTAL, adj)
        self.gui.slider.set_draw_value(False)
        self.gui.slider.connect('button-press-event', self.on_slider_button_press_event)
        self.gui.slider.connect('button-release-event', self.on_slider_button_release_event)
        self.gui.slider.connect('scroll-event', self.on_slider_scroll_event)
        def update_timelabel(s):
            self.time_label.set_time(s.get_value())
            return False
        self.gui.slider.connect('value-changed', update_timelabel)

        # Stack the video components
        v=Gtk.VBox()
        v.pack_start(hb, False, True, 0)
        eb=Gtk.EventBox()
        eb.set_above_child(True)
        eb.set_visible_window(True)
        container = Gtk.VBox()
        container.add(self.drawable)
        eb.add(container)
        v.pack_start(eb, True, True, 0)
        eb.connect('scroll-event', self.on_slider_scroll_event)
        eb.connect('button-press-event', self.on_video_button_press_event)
        eb.connect('key-press-event', self.on_win_key_press_event)


        def register_drawable(drawable, container):
            # The player is initialized. We can register the drawable id
            try:
                if not config.data.player['embedded']:
                    raise Exception()
                self.controller.player.set_widget(self.drawable, container)
            except Exception:
                logger.error("Cannot embed video player", exc_info=True)
            return True
        self.drawable_container = container
        self.drawable.connect_after('realize', register_drawable, container)

        if config.data.preferences['display-scroller']:
            self.scroller=ScrollerView(controller=self.controller)
            v.pack_start(self.scroller.widget, False, True, 0)
        if config.data.preferences['display-caption']:
            self.captionview=CaptionView(controller=self.controller)
            self.register_view(self.captionview)
            v.pack_start(self.captionview.widget, False, True, 0)
        else:
            self.captionview=None

        h=Gtk.HBox()
        eb=Gtk.EventBox()
        self.time_label = Gtk.Label()
        self.time_label.value = None
        def set_time(s, t):
            s.set_text(helper.format_time(t))
            s.value = t
            return t
        self.time_label.set_time=set_time.__get__(self.time_label)
        # Make sure that we use a fixed-size font, so that the
        # time_label width is constant and does not constantly modify
        # the slider available width.
        self.time_label.modify_font(Pango.FontDescription("monospace 10"))
        self.time_label.set_time(None)
        eb.add(self.time_label)

        def time_pressed(w, event):
            if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                self.goto_time_dialog()
                return True
            return True

        eb.connect('button-press-event', time_pressed)
        h.pack_start(eb, False, True, 0)
        h.pack_start(self.gui.slider, True, True, 0)
        v.pack_start(h, False, True, 0)

        v.pack_start(self.player_toolbar, False, True, 0)

        # create the viewbooks
        for pos in ('east', 'west', 'south', 'fareast'):
            self.viewbook[pos] = ViewBook(controller=self.controller, location=pos)

        self.pane['west'] = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        self.pane['east'] = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        self.pane['south'] = Gtk.Paned.new(Gtk.Orientation.VERTICAL)
        self.pane['fareast'] = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)

        # Specify wide handles
        self.pane['south'].set_wide_handle(True)
        self.pane['fareast'].set_wide_handle(True)

        # pack all together
        self.pane['west'].add1(self.viewbook['west'].widget)
        self.pane['west'].add2(self.pane['east'])

        self.pane['east'].pack1(v, shrink=False)
        self.pane['east'].add2(self.viewbook['east'].widget)

        self.pane['south'].add1(self.pane['west'])
        self.pane['south'].add2(self.viewbook['south'].widget)

        self.pane['fareast'].pack1(self.pane['south'], resize=True, shrink=False)
        self.pane['fareast'].pack2(self.viewbook['fareast'].widget, resize=True, shrink=True)
        # Set position to a huge value to ensure that by default, the
        # right pane is hidden
        self.pane['fareast'].set_position(5000)

        # Open default views:

        # URL stack
        self.viewbook['west'].add_view(self.logwindow, permanent=True)

        # Navigation history
        self.navigation_history=Bookmarks(controller=self.controller, closable=True, display_comments=False)
        self.viewbook['west'].add_view(self.navigation_history, name=_("History"), permanent=True)
        # Make the history snapshots + border visible
        self.pane['west'].set_position (config.data.preferences['bookmark-snapshot-width'] + 20)

        # Popup widget
        self.popupwidget=AccumulatorPopup(controller=self.controller,
                                          autohide=False)
        self.viewbook['east'].add_view(self.popupwidget, _("Popups"), permanent=True)

        self.pane['fareast'].show_all()

        self.popupwidget.display_message(_("You can drag and drop view icons (timeline, treeview, transcription...) in notebooks to embed various views."), timeout=30000, title=_("Information"))

        return self.pane['fareast']

    def make_pane_visible(self, paneid='fareast'):
        """Ensure that the given pane is visible.
        """
        pane = self.pane.get(paneid)
        if not pane:
            return
        width = pane.get_allocation().width
        height = pane.get_allocation().height
        if paneid == 'fareast':
            need_adjust = (abs(width - pane.get_position()) < 200)
            step = - int((pane.get_position() - (width - 256)) / 8)
            condition = lambda p: (p < width - 256)
        elif paneid == 'south':
            need_adjust = (abs(height - pane.get_position()) < 200)
            step = - int((pane.get_position() - (height - 256)) / 8)
            condition = lambda p: (p < height - 256)
        elif paneid == 'west':
            # We should ideally also check for height adjustment (in
            # south pane), but the video player is generally always
            # visible anyway, so height should already be OK.
            need_adjust = (pane.get_position() < 200)
            step = int(256 / 8)
            condition = lambda p: (p > 256)
        elif paneid == 'east':
            need_adjust = (abs(width - pane.get_position()) < 200)
            step = - int((pane.get_position() - (width - 256)) / 8)
            condition = lambda p: (p < width - 256)
        else:
            need_adjust = False

        if need_adjust:
            def enlarge_view():
                pos=pane.get_position() + step
                if condition(pos):
                    return False
                pane.set_position(pos)
                return True
            GObject.timeout_add(100, enlarge_view)
        return True

    def find_bookmark_view(self):
        views = [ w for w in self.adhoc_views if w.view_id == 'activebookmarks' ]
        if views:
            # There is at least one open view. Use the latest.
            a = views[-1]
            self.make_pane_visible(a._destination)
        else:
            # No existing view. Create one.
            a = self.open_adhoc_view('activebookmarks', destination='fareast')
            self.make_pane_visible('fareast')
        return a

    def create_bookmark(self, position, insert_after_current=False, comment=None):
        # Capture a screenshot
        self.controller.update_snapshot(position)
        # Insert an active bookmark
        a=self.find_bookmark_view()

        if a is not None:
            b=a.append(position, after_current=insert_after_current, comment=comment)
            b.grab_focus()
            # We can scroll to the bookmark only after it has
            # been allocated a space (and thus the
            # scroll_to_bookmark method can know its position
            # inside its parent).
            b.widget.connect('size-allocate', lambda w, e: a.scroll_to_bookmark(b) and False)
        return True

    def connect_fullscreen_handlers(self, widget):
        """Connect handlers to the fullscreen widget.
        """
        widget.connect('key-press-event', self.process_fullscreen_shortcuts)
        widget.connect('key-press-event', self.process_player_shortcuts)
        widget.connect('scroll-event', self.on_slider_scroll_event)

    def updated_player_cb(self, context, parameter):
        self.update_player_labels()
        p=self.controller.player
        # The player is initialized. We can register the drawable id
        p.set_widget(self.drawable, self.drawable_container)
        self.update_control_toolbar(self.player_toolbar)
        update_player_menu(self.gui.menu_map['player_select_menu'], self.controller.player.player_id)

    @named_action(name="app.player-play-pause")
    def player_play_pause(self, event=None):
        p = self.controller.player
        if not p.get_uri() and 'record' not in p.player_capabilities:
            # No movie file is defined yet. Propose to choose one.
            self.on_b_addfile_clicked()
            return True
        if p.is_playing():
            if 'record' in p.player_capabilities:
                self.controller.update_status("stop")
            else:
                self.controller.update_status("pause")
        else:
            if 'record' in p.player_capabilities:
                self.controller.update_status("start")
            else:
                self.controller.update_status("resume")
        return True

    @named_action(name="app.player-forward")
    def player_forward(self, event=None):
        if event and event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            i='second-time-increment'
        else:
            i='time-increment'
        self.controller.update_status("seek_relative", config.data.preferences[i], notify=False)

    @named_action(name="app.player-rewind")
    def player_rewind(self, event=None):
        if event and event.get_state() & Gdk.ModifierType.SHIFT_MASK:
            i='second-time-increment'
        else:
            i='time-increment'
        self.controller.update_status("seek_relative", -config.data.preferences[i], notify=False)

    @named_action(name="app.player-forward-frame")
    def player_forward_frame(self, event=None):
        if config.data.preferences['custom-updown-keys'] or (event and event.get_state() & Gdk.ModifierType.SHIFT_MASK):
            self.controller.update_status("seek_relative", +config.data.preferences['third-time-increment'], notify=False)
        else:
            self.controller.move_frame(+1)

    @named_action(name="app.player-rewind-frame")
    def player_rewind_frame(self, event=None):
        if config.data.preferences['custom-updown-keys'] or (event and event.get_state() & Gdk.ModifierType.SHIFT_MASK):
            self.controller.update_status("seek_relative", -config.data.preferences['third-time-increment'], notify=False)
        else:
            self.controller.move_frame(-1)

    @named_action(name="app.player-create-bookmark")
    def player_create_bookmark(self, event=None):
        p=self.controller.player
        if p.is_playing():
            self.create_bookmark(p.current_position_value,
                                 insert_after_current=(event and event.get_state() & Gdk.ModifierType.SHIFT_MASK))

    @named_action(name="app.player-goto-start")
    def player_home(self, event=None):
        self.controller.update_status("seek", 0)

    @named_action(name="app.player-goto-end")
    def player_end(self, event=None):
        c=self.controller
        c.update_status("seek_relative", -config.data.preferences['time-increment'])

    def player_set_fraction(self, f):
        self.controller.update_status("seek", self.controller.cached_duration * f)

    def function_key(self, event):
        if Gdk.KEY_F1 <= event.keyval <= Gdk.KEY_F12:
            self.controller.notify('KeyboardInput', request={ 'keyname': Gdk.keyval_name(event.keyval) })

    control_key_shortcuts={
        Gdk.KEY_Tab: player_play_pause,
        Gdk.KEY_space: player_play_pause,
        Gdk.KEY_Up: player_forward_frame,
        Gdk.KEY_Down: player_rewind_frame,
        Gdk.KEY_Right: player_forward,
        Gdk.KEY_Left: player_rewind,
        Gdk.KEY_Home: player_home,
        Gdk.KEY_End: player_end,
        Gdk.KEY_Insert: player_create_bookmark,
        }

    key_shortcuts={
        Gdk.KEY_Insert: player_create_bookmark,

        # Numeric keypad
        Gdk.KEY_KP_5: player_play_pause,
        Gdk.KEY_KP_8: player_forward_frame,
        Gdk.KEY_KP_2: player_rewind_frame,
        Gdk.KEY_KP_6: player_forward,
        Gdk.KEY_KP_4: player_rewind,
        Gdk.KEY_KP_7: player_home,
        Gdk.KEY_KP_1: player_end,
        Gdk.KEY_KP_0: player_create_bookmark,

        # Symbolic keypad
        Gdk.KEY_KP_Begin: player_play_pause,
        Gdk.KEY_KP_Up: player_forward_frame,
        Gdk.KEY_KP_Down: player_rewind_frame,
        Gdk.KEY_KP_Right: player_forward,
        Gdk.KEY_KP_Left: player_rewind,
        Gdk.KEY_KP_Home: player_home,
        Gdk.KEY_KP_End: player_end,
        Gdk.KEY_KP_Insert: player_create_bookmark,

        # Function keys
        Gdk.KEY_F1:   function_key,
        Gdk.KEY_F2:   function_key,
        Gdk.KEY_F3:   function_key,
        Gdk.KEY_F4:   function_key,
        Gdk.KEY_F5:   function_key,
        Gdk.KEY_F6:   function_key,
        Gdk.KEY_F7:   function_key,
        Gdk.KEY_F8:   function_key,
        Gdk.KEY_F9:   function_key,
        Gdk.KEY_F10:  function_key,
        Gdk.KEY_F11:  function_key,
        Gdk.KEY_F12:  function_key,
        }

    fullscreen_key_shortcuts = {
        Gdk.KEY_Tab: player_play_pause,
        Gdk.KEY_space: player_play_pause,
        Gdk.KEY_Up: player_forward_frame,
        Gdk.KEY_Down: player_rewind_frame,
        Gdk.KEY_Right: player_forward,
        Gdk.KEY_Left: player_rewind,
        Gdk.KEY_Home: player_home,
        Gdk.KEY_Insert: player_create_bookmark,

        # AZERTY keyboard navigation
        Gdk.KEY_ampersand:  lambda s, e: s.player_set_fraction(.0),
        Gdk.KEY_eacute:     lambda s, e: s.player_set_fraction(.1),
        Gdk.KEY_quotedbl:   lambda s, e: s.player_set_fraction(.2),
        Gdk.KEY_apostrophe: lambda s, e: s.player_set_fraction(.3),
        Gdk.KEY_parenleft:  lambda s, e: s.player_set_fraction(.4),
        Gdk.KEY_minus:      lambda s, e: s.player_set_fraction(.5),
        Gdk.KEY_egrave:     lambda s, e: s.player_set_fraction(.6),
        Gdk.KEY_underscore: lambda s, e: s.player_set_fraction(.7),
        Gdk.KEY_ccedilla:   lambda s, e: s.player_set_fraction(.8),
        Gdk.KEY_agrave:     lambda s, e: s.player_set_fraction(.9),

        # QWERTY keyboard navigation
        Gdk.KEY_1:  lambda s, e: s.player_set_fraction(.0),
        Gdk.KEY_2:  lambda s, e: s.player_set_fraction(.1),
        Gdk.KEY_3:  lambda s, e: s.player_set_fraction(.2),
        Gdk.KEY_4:  lambda s, e: s.player_set_fraction(.3),
        Gdk.KEY_5:  lambda s, e: s.player_set_fraction(.4),
        Gdk.KEY_6:  lambda s, e: s.player_set_fraction(.5),
        Gdk.KEY_7:  lambda s, e: s.player_set_fraction(.6),
        Gdk.KEY_8:  lambda s, e: s.player_set_fraction(.7),
        Gdk.KEY_9:  lambda s, e: s.player_set_fraction(.8),
        Gdk.KEY_0:  lambda s, e: s.player_set_fraction(.9),

        }

    def is_focus_on_editable(self):
        """Returns True if the focus is in an editable component.

        If not, we can activate control_key_shortcuts without the Control modifier.
        """
        # For the moment, we only check if we are in full or simplified GUI state.
        # FIXME: it is not as simple as this:
        #print "FOCUS", [ isinstance(w.get_focus(), Gtk.Editable) for w in  Gtk.window_list_toplevels() if w.get_focus() is not None ]
        # since we can want to use the standard gtk keyboard navigation among widgets.
        return self.viewbook['east'].widget.get_visible()

    def process_player_shortcuts(self, win, event):
        """Generic player control shortcuts.

        Tab: pause/play
        Control-right/-left: move in the stream
        Control-home/-end: start/end of the stream
        """

        if event.keyval in self.key_shortcuts:
            self.key_shortcuts[event.keyval](self, event)
            return True
        elif event.keyval in self.control_key_shortcuts and (
                event.get_state() & self.player_shortcuts_modifier == self.player_shortcuts_modifier
                or not self.is_focus_on_editable()):
            self.control_key_shortcuts[event.keyval](self, event)
            return True
        return False

    def process_fullscreen_shortcuts(self, win, event):
        """Fullscreen player control shortcuts.
        """
        c=self.controller
        p=self.controller.player
        if event.keyval == Gdk.KEY_Return:
            # FIXME: reset data (validate or abort?) when leaving fullscreen
            if self.edited_annotation_text is None:
                # Not yet editing, entering edit mode
                self.edited_annotation_text = ''
                self.edited_annotation_begin = p.current_position_value
                p.display_text(self.edited_annotation_text + '_', p.current_position_value, p.current_position_value + 5000)
            else:
                # Was editing. Creating annotation
                at = c.package.get_element_by_id('annotation')
                if at is None or not isinstance(at, AnnotationType):
                    # Non-existent. This code path should be pretty unfrequent.
                    if len(c.package.annotation_types):
                        # Use the first defined type
                        at = c.package.annotation_types[0]
                    else:
                        # No type. We must create one.
                        sc = c.package.get_element_by_id('basic-schema')
                        if sc is None or not isinstance(sc, Schema):
                            if len(c.package.schemas):
                                sc = c.package.schemas[0]
                            else:
                                # Do not bother
                                self.log(_("Cannot create annotation. There is no schema to put it in."))
                                return True
                        if at is None:
                            ident = 'annotation'
                        else:
                            ident = 'default_annotation_type'
                        at = sc.createAnnotationType(ident=ident)
                        at.author = config.data.userid
                        at.date = helper.get_timestamp()
                        at.title = _("Default annotation type")
                        at.mimetype = 'text/plain'
                        at.setMetaData(config.data.namespace, 'color', next(self.controller.package._color_palette))
                        at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                        at._fieldnames = set()
                        sc.annotationTypes.append(at)
                        self.controller.notify('AnnotationTypeCreate', annotationtype=at)
                c.create_annotation(self.edited_annotation_begin, at,
                                    p.current_position_value - self.edited_annotation_begin,
                                    self.edited_annotation_text)
                self.edited_annotation_text = None
                self.edited_annotation_begin = None
                p.display_text(_('Annotation created'), p.current_position_value, p.current_position_value + 1000)
            return True
        elif Gdk.keyval_to_unicode(event.keyval):
            c = str(Gdk.keyval_name(event.keyval))
            if len(c) == 1 and (c.isalnum() or c.isspace()):
                if self.edited_annotation_text is None:
                    # Not yet editing, entering edit mode
                    self.edited_annotation_text = ''
                    self.edited_annotation_begin = p.current_position_value
                self.edited_annotation_text += c
                # Display feedback
                p.display_text(self.edited_annotation_text + '_', p.current_position_value, p.current_position_value + 10000)
                return True
        elif event.keyval == Gdk.KEY_BackSpace and self.edited_annotation_text is not None:
            # Delete last char
            self.edited_annotation_text = self.edited_annotation_text[:-1]
            p.display_text(self.edited_annotation_text + '_', p.current_position_value, p.current_position_value + 10000)
            return True
        if event.keyval in self.fullscreen_key_shortcuts:
            self.fullscreen_key_shortcuts[event.keyval](self, event)
            return True
        return False

    def get_player_control_toolbar(self):
        """Return a player control toolbar.

        It has a buttons attribute, which holds references to the buttons according to an identifier.
        """
        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        tb_list = [
            ('playpause',
             _("Play/Pause [Control-Tab / Control-Space]"),
             Gtk.STOCK_MEDIA_PLAY,
             self.player_play_pause),
            ('rewind',
             _("Rewind (%.02f s) [Control-Left]") % (config.data.preferences['time-increment'] / 1000.0),
             Gtk.STOCK_MEDIA_REWIND,
             lambda i: self.controller.update_status("seek_relative", -config.data.preferences['time-increment'])),
            ('forward',
             _("Forward (%.02f s) [Control-Right]" % (config.data.preferences['time-increment'] / 1000.0)),
             Gtk.STOCK_MEDIA_FORWARD,
             lambda i: self.controller.update_status("seek_relative", config.data.preferences['time-increment'])),
            ('previous_frame',
             _("Previous frame [Control-Down]"),
             Gtk.STOCK_MEDIA_PREVIOUS,
             lambda i: self.controller.move_frame(-1)),
            ('next_frame',
             _("Next frame [Control-Up]"),
             Gtk.STOCK_MEDIA_NEXT,
             lambda i: self.controller.move_frame(+1)),
            ('fullscreen',
             _("Fullscreen"),
             Gtk.STOCK_FULLSCREEN,
             lambda i: self.controller.player.fullscreen(self.connect_fullscreen_handlers) ),
            ]

        tb.buttons = {}
        for name, text, stock, callback in tb_list:
            if name == 'playpause':
                b = PlayPauseButton(stock)
            else:
                b = Gtk.ToolButton(stock)
            b.set_tooltip_text(text)
            b.connect('clicked', callback)
            tb.insert(b, -1)
            tb.buttons[name] = b

        tb.show_all()
        # Call update_control_toolbar()
        self.update_control_toolbar(tb)
        return tb

    def update_control_toolbar(self, tb=None):
        """Update player control toolbar.

        It modifies buttons according to the player capabilities.
        """
        if tb is None:
            tb=self.player_toolbar
        p=self.controller.player

        if 'record' in p.player_capabilities:
            tb.buttons['playpause'].set_stock_ids(Gtk.STOCK_MEDIA_RECORD, Gtk.STOCK_MEDIA_STOP)
            for name, b in tb.buttons.items():
                if name == 'playpause':
                    continue
                b.set_sensitive(False)
        else:
            tb.buttons['playpause'].set_stock_ids(Gtk.STOCK_MEDIA_PLAY, Gtk.STOCK_MEDIA_PAUSE)
            for b in tb.buttons.values():
                b.set_sensitive(True)

        if 'frame-by-frame' in p.player_capabilities:
            tb.buttons['previous_frame'].show()
            tb.buttons['next_frame'].show()
        else:
            tb.buttons['previous_frame'].hide()
            tb.buttons['next_frame'].hide()

        if hasattr(p, 'fullscreen'):
            tb.buttons['fullscreen'].show()
        else:
            tb.buttons['fullscreen'].hide()

        if hasattr(self, 'rate_control'):
            if 'set-rate' in p.player_capabilities:
                self.rate_control.show()
            else:
                self.rate_control.hide()

    def loop_on_annotation_gui(self, a, goto=False):
        """Loop over an annotation

        If "goto" is True, then go to the beginning of the annotation
        In addition to the standard "Loop on annotation", it updates a
        checkbox to activate/deactivate looping.
        """
        self.set_current_annotation(a)
        self.player_toolbar.buttons['loop'].set_active(True)
        return True

    def debug_cb(self, *p):
        logger.warning(" / ".join(str(i) for i in p))
        return False

    def init_window_size(self, window, name):
        """Initialize window size according to stored values.
        """
        if name == 'editwindow':
            # Do not update position/size for edit popups
            return True
        if config.data.preferences['remember-window-size']:
            screen = window.get_screen()
            screen_width = screen.get_width() or config.data.preferences['fallback-screen-width']
            screen_height = screen.get_height() or config.data.preferences['fallback-screen-height']
            stored_resolution = config.data.preferences['windowsize'].setdefault(name, (640,480))
            stored_resolution = (min(stored_resolution[0], screen_width),
                                 min(stored_resolution[1], screen_height))
            window.resize(*stored_resolution)
            position = config.data.preferences['windowposition'].get(name, None)
            if position:
                if position[0] < screen_width and position[1] < screen_height:
                    # Do not use if it would display the window out of the screen
                    window.move(*position)
            if name != 'main':
                # The main GUI is regularly reallocated (at each update_display), so
                # do not update continuously. Just do it on application exit.
                window.connect_after('size-allocate', self.resize_cb, name)
        return True

    def resize_cb (self, widget, allocation, name):
        """Memorize the new dimensions of the widget.
        """
        parent=widget.get_toplevel()
        config.data.preferences['windowsize'][name] = parent.get_size()
        config.data.preferences['windowposition'][name] = parent.get_position()
        #print "New size for %s: %s" %  (name, config.data.preferences['windowsize'][name])
        return False

    def overlay(self, png_data, svg_data, other_thread=False):
        # if other_thread and config.data.os == 'win32':
        #     # If executed in a thread other than the one that was
        #     # initialized, pixbuf loader (do not know if it is
        #     # specific to svg though) crashes in the write method on
        #     # win32.  So we have to make sure the method is executed
        #     # in the main thread context.
        #     q=queue.Queue(1)
        #     def process_overlay(queue=None):
        #         queue.put(overlay_svg_as_png(png_data, svg_data))
        #         return False
        #     GObject.timeout_add(0, process_overlay, q)
        #     try:
        #         data=q.get(True, 2)
        #     except queue.Empty:
        #         data=None
        #     return data
        # else:
        return overlay_svg_as_png(png_data, svg_data)

    def edit_element(self, element, destination='default'):
        """Edit the element.
        """
        if self.edit_accumulator and (
                isinstance(element, Annotation) or isinstance(element, Relation)):
            self.edit_accumulator.edit(element)
            return True

        pop=self.open_adhoc_view('edit', element=element, destination=destination)
        return pop

    @named_action(name="app.undo", shortcut="<Primary>z")
    def undo(self, *p):
        """Undo the last modifying action.
        """
        try:
            self.controller.undomanager.undo()
        except AttributeError:
            pass
        return True

    @named_action(name="app.save-snapshot")
    def save_snapshot_as(self, position=None, filename=None, retry=True):
        """Save the snapshot for the given position into a file.

        If supported by the player, it will save the full-resolution screenshot.
        """
        def do_save_as(fname, png_data, notify=False):
            try:
                f = open(fname, 'wb')
                f.write(bytes(png_data))
                f.close()
                self.controller.log(_("Screenshot saved to %s") % fname)
                if notify:
                    self.controller.queue_action(dialog.message_dialog, _("Screenshot saved in\n %s") % str(fname), modal=False)
            except Exception as e:
                self.controller.queue_action(dialog.message_dialog, _("Could not save screenshot:\n %s") % str(e), icon=Gtk.MessageType.ERROR, modal=False)

        if position is None:
            position = self.controller.update()

        if filename is None:
            name = "%s-%010d.png" % (
                os.path.splitext(
                    os.path.basename(
                        self.controller.get_default_media()))[0],
                position)
            filename = dialog.get_filename(title=_("Save screenshot to..."),
                                           action=Gtk.FileChooserAction.SAVE,
                                           button=Gtk.STOCK_SAVE,
                                           default_file=name)

        if filename is not None:
            if hasattr(self.controller.player, 'async_fullres_snapshot'):
                def save_callback(snapshot=None, message=None):
                    if snapshot is None and message is not None:
                        self.controller.queue_action(dialog.message_dialog, message)
                    elif snapshot:
                        if abs(snapshot.date - position) > 100:
                            # FIXME: It can be due to an
                            # initialisation issue in the snapshotter,
                            # on first invocation. Hack around the issue for now.
                            if retry:
                                self.controller.queue_action(self.save_snapshot_as, position, filename, retry=False)
                            else:
                                self.controller.queue_action(dialog.message_dialog, _("Could not take snapshot with enough precision"), modal=False)
                        else:
                            do_save_as(filename, snapshot.data, notify=True)
                    else:
                        self.controller.log("Unknown problem in full-resolution snapshot")
                # Can capture full-res snapshot
                self.controller.player.async_fullres_snapshot(position - 20, save_callback)
            else:
                do_save_as(filename,
                           self.controller.package.imagecache.get(position))
        return True

    @named_action(name="app.export-package")
    def export_element(self, element=None, filter_id=None, filename=None):
        if element is None:
            element = self.controller.package

        if isinstance(element, Package):
            title = _("Export package data")
        elif isinstance(element, AnnotationType):
            title = _("Export annotation type %s") % self.controller.get_title(element)
        else:
            title = _("Export element %s") % self.controller.get_title(element)
        exporterclass = None
        if filter_id is not None:
            exporterclass = self.controller.get_export_filters(ident=filter_id)
        self.open_adhoc_view('exporterview', title=title, source=element, exporterclass=exporterclass, filename=filename)
        return True

    arrow_list={ 'linux': '\u25b8',
                 'darwin': '\u25b6',
                 'win32': '>' }
    def update_stbv_list (self):
        """Update the STBV list.
        """
        stbv_combo = self.gui.stbv_combo
        if stbv_combo is None:
            return True
        elements = [ helper.TitledElement(value=None, title=_("No active dynamic view")) ]
        elements.extend( [ helper.TitledElement(value=i, title='%s %s %s' % (self.arrow_list[config.data.os],
                                                                             self.controller.get_title(i),
                                                                             self.arrow_list[config.data.os]))
                           for i in self.controller.get_stbv_list() ] )
        st, i = dialog.generate_list_model([ (i.value, i.title) for i in elements ],
                                           active_element=self.controller.current_stbv)
        stbv_combo.set_model(st)
        if i is None:
            i = st.get_iter_first()
        # To ensure that the display is updated
        stbv_combo.set_active(-1)
        stbv_combo.set_active_iter(i)
        stbv_combo.show_all()
        return True

    def build_utbv_menu(self, action=None):
        if action is None:
            action = self.controller.open_url

        def open_utbv(button, u):
            action (u)
            return True

        menu=Gtk.Menu()
        for title, url in self.controller.get_utbv_list():
            i=Gtk.MenuItem(label=title, use_underline=False)
            i.connect('activate', open_utbv, url)
            menu.append(i)
        menu.show_all()
        return menu

    def workspace_clear(self):
        """Clear the workspace.
        """
        for d in ('west', 'east', 'south', 'fareast'):
            self.viewbook[d].clear()
        # Also clear popup views
        for v in self.adhoc_views:
            dest=None
            try:
                dest=v._destination
            except AttributeError:
                # Some default views do not have this attribute,
                # because they are not opened through open_adhoc_view
                pass
            if dest == 'popup':
                v.close()

    def workspace_serialize(self, with_arguments=True):
        """Serialize the current workspace as an ElementTree element.

        Looks like this (+ advene namespace):
        <workspace>
         <!-- Application layout -->
         <layout x="12" y="23" width="800" height="600">
          <pane id="main" position="123" />
          <pane id="west" position="123" />
          <pane id="east" position="123" />
          <pane id="south" position="123" />
          <pane id="fareast" position="123" />
         </layout>
         <!-- Opened adhoc views. -->
         <!-- We reuse the adhoc view syntax with additional attributes -->
         <!-- destination + title attributes for embedded views -->
         <advene:adhoc id="timeline" xmlns:advene="http://experience.univ-lyon1.fr/advene/ns/advenetool" destination="east" title="My embedded timeline">
           <advene:option name="autoscroll" value="2" />
           <advene:option name="highlight" value="True" />
           <advene:option name="display-relations" value="True" />
           <advene:option name="display-relation-type" value="True" />
           <advene:option name="display-relation-content" value="True" />
         </advene:adhoc>
         <!-- destination (popup) + title + x,y,width,height attributes for popup views -->
         <advene:adhoc id="history" xmlns:advene="http://experience.univ-lyon1.fr/advene/ns/advenetool" destination="popup" title="My popup timeline" x="12" y="20" width="640" height="480" >
           <advene:option name="autoscroll" value="2" />
           <advene:option name="highlight" value="True" />
           <advene:option name="display-relations" value="True" />
           <advene:option name="display-relation-type" value="True" />
           <advene:option name="display-relation-content" value="True" />
         </advene:adhoc>
        </workspace>
        """
        workspace=ET.Element('workspace')
        w=self.gui.win
        d={}
        d['x'], d['y']=w.get_position()
        d['width'], d['height'] = w.get_size()
        for k, v in d.items():
            d[k]=str(v)
        layout=ET.SubElement(workspace, 'layout', d)
        for n in ('west', 'east', 'fareast', 'south'):
            ET.SubElement(layout, 'pane', id=n, position=str(self.pane[n].get_position()))
        # Now save adhoc views
        for v in self.adhoc_views:
            if not hasattr(v, '_destination'):
                continue
            # Do not save permanent widgets
            book = self.viewbook.get(v._destination)
            if book and v in book.permanent_widgets:
                continue
            options, args = v.get_save_arguments()
            if not with_arguments:
                # If we save the default workspace, we do not want to
                # get package-specific information (for instance,
                # displayed types in the timeline).
                args=[]
            element=v.parameters_to_element(options, args)
            element.attrib['destination']=v._destination
            element.attrib['title']=v._label
            if v._destination == 'popup':
                # Additional parameters
                w=v.get_window()
                d={}
                d['x'], d['y']=w.get_position()
                d['width'], d['height'] = w.get_width(), w.get_height()
                for k, v in d.items():
                    element.attrib[k]=str(v)
            workspace.append(element)
        return workspace

    def workspace_restore(self, workspace, preserve_layout=False):
        """Restore the workspace from a given ElementTree element.

        It is the responsibility of the caller to clear the workspace if needed.
        """
        if workspace.tag != 'workspace':
            raise Exception('Invalid XML element for workspace: ' + workspace.tag)

        # First pass to set layout.
        if not preserve_layout:
            for node in workspace:
                if node.tag == 'layout':
                    layout=node
                    w=self.gui.win
                    w.move(int(layout.attrib['x']), int(layout.attrib['y']))
                    w.resize(min(int(layout.attrib['width']), Gdk.Screen.width()),
                             min(int(layout.attrib['height']), Gdk.Screen.height()))
                    for pane in layout:
                        if pane.tag == 'pane' and pane.attrib['id'] in self.pane:
                            self.pane[pane.attrib['id']].set_position(int(pane.attrib['position']))

        # Second pass to open adhoc views
        for node in workspace:
            if node.tag == ET.QName(config.data.namespace, 'adhoc'):
                # It is a adhoc-view definition
                v=self.open_adhoc_view(name=node.attrib['id'],
                                       label=node.attrib['title'],
                                       destination=node.attrib['destination'],
                                       parameters=node)
                if node.attrib['destination'] == 'popup':
                    # Restore popup windows positions
                    v.get_window().move(int(node.attrib['x']), int(node.attrib['y']))
                    v.get_window().resize(int(node.attrib['width']), int(node.attrib['height']))

    def workspace_save(self, viewid=None):
        """Save the workspace in the given viewid.
        """
        title=_("Saved workspace")
        v=helper.get_id(self.controller.package.views, viewid)
        if v is None:
            create=True
            v=self.controller.package.createView(ident=viewid, clazz='package')
            v.content.mimetype='application/x-advene-workspace-view'
        else:
            # Existing view. Overwrite it.
            create=False
        v.title=title
        v.author=config.data.userid
        v.date=helper.get_timestamp()

        workspace=self.workspace_serialize()
        stream=io.StringIO()
        helper.indent(workspace)
        tree = ET.ElementTree(workspace)
        tree.write(stream, encoding='unicode')
        v.content.setData(stream.getvalue())
        stream.close()

        if create:
            self.controller.package.views.append(v)
            self.controller.notify("ViewCreate", view=v)
        else:
            self.controller.notify("ViewEditEnd", view=v)
        return True

    @named_action(name="app.open-adhoc-view")
    def open_adhoc_view(self, name: str, label=None, destination='default', parameters=None, **kw):
        """Open the given adhoc view.

        Destination can be: 'popup', 'south', 'west', 'east', 'fareast' or None.
        If it is 'default', then it will use config.data.preferences['popup-destination']

        In the last case (None), the view is returned initialized, but not
        added to its destination, it is the responsibility of the
        caller to display it and set the _destinaton attribute to the
        correct value.

        If name is a 'view' object, then try to interpret it as a
        application/x-advene-adhoc-view or
        application/x-advene-adhoc-view and open the appropriate view
        with the given parameters.
        """
        if destination == 'default':
            destination = config.data.preferences['popup-destination']

        view = None
        if isinstance(name, View):
            if name.content.mimetype == 'application/x-advene-workspace-view':
                tree = ET.parse(name.content.stream)

                if kw.get('ask', True):
                    d = Gtk.Dialog(title=_("Restoring workspace..."),
                                   parent=self.gui.win,
                                   flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                                   buttons=( Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                             Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                             ))
                    label = Gtk.Label(label=_("Do you wish to restore the %s workspace ?") % name.title)
                    label.set_line_wrap(True)
                    label.show()
                    d.vbox.pack_start(label, False, True, 0)

                    delete_existing_toggle = Gtk.CheckButton(_("Clear the current workspace"))
                    delete_existing_toggle.set_active(True)
                    delete_existing_toggle.show()
                    d.vbox.pack_start(delete_existing_toggle, False, True, 0)

                    res =  d.run()
                    clear = delete_existing_toggle.get_active()
                    d.destroy()
                else:
                    res = Gtk.ResponseType.OK
                    clear = True

                if res == Gtk.ResponseType.OK:
                    def restore(clr):
                        if clr:
                            self.workspace_clear()
                        self.workspace_restore(tree.getroot())
                        return True
                    self.controller.queue_action(restore, clear)
                return None
            if name.content.mimetype != 'application/x-advene-adhoc-view':
                self.log(_("View %s is not an adhoc view") % name.id)
                return None
            # Parse the content, extract the view id
            # Override parameters
            parameters = name.content
            p = AdhocViewParametersParser(name.content.stream)
            if p.view_id:
                if label is None:
                    label = name.title
                name = p.view_id
            else:
                self.log(_("Cannot identify the adhoc view %s") % name.id)
                return None

        if name == 'transcription':
            kwargs = { 'controller': self.controller,
                       'parameters': parameters }
            if 'source' in kw:
                kwargs['source'] = kw['source']
            elif 'elements' in kw:
                kwargs['elements'] = kw['elements']
            elif parameters is not None:
                # source may be defined in parameters
                kwargs['source'] = None
            else:
                at = self.ask_for_annotation_type(text=_("Choose the annotation type to display as transcription."),
                                                  create=False)
                if at is None:
                    return None
                else:
                    kwargs['source']="here/annotationTypes/%s/annotations/sorted" % at.id
                    if label is None:
                        label = self.controller.get_title(at)
            view = self.registered_adhoc_views[name](**kwargs)
        elif name in ('webbrowser', 'htmlview'):
            if destination is None and HTMLView._engine is not None:
                # Embedded version.
                view = HTMLView(controller=self.controller)
                view.open_url(self.controller.get_default_url(alias='advene'))
            elif self.controller.package is not None:
                m = self.build_utbv_menu()
                m.popup_at_pointer(None)
            else:
                self.log (("No current package"))
        elif name == 'transcribe':
            try:
                filename = kw['filename']
            except KeyError:
                filename = None
            view = self.registered_adhoc_views[name](controller=self.controller, filename=filename, parameters=parameters, **kw)
        elif name == 'edit':
            try:
                element = kw['element']
            except KeyError:
                element = None
            if element is None:
                return None
            try:
                view = get_edit_popup(element, self.controller)
            except TypeError:
                logger.warning(_("Error: unable to find an edit popup for %(element)s") % {
                    'element': str(element) })
                view = None
            if view is not None and view.widget.get_parent() is not None:
                # Widget is already displayed. Present it.
                view.widget.get_toplevel().present()
                view = None
            label = _("Editing %s") % self.controller.get_title(element)
        elif name == 'editaccumulator':
            view = self.registered_adhoc_views[name](controller=self.controller, scrollable=True)
            if not self.edit_accumulator:
                # The first opened accumulator becomes the default one.
                self.edit_accumulator = view
                def handle_accumulator_close(w):
                    self.edit_accumulator = None
                    return False
                self.edit_accumulator.widget.connect('destroy', handle_accumulator_close)
        elif name == 'comment':
            v = self.controller.create_static_view(elements=[])
            label = _("Comment view (%s)" % time.strftime('%Y%m%d - %H:%M'))
            v.title = label
            view = get_edit_popup(v, controller=self.controller)
        elif name in self.registered_adhoc_views:
            view = self.registered_adhoc_views[name](controller=self.controller,
                                                     parameters=parameters, **kw)

        if view is None:
            return view
        # Store destination and label, used when moving the view
        view._destination = destination
        label = str(label or view.view_name)
        view.set_label(label)

        if destination == 'popup':
            w = view.popup(label=label)
            if isinstance(w, Gtk.Window):
                dialog.center_on_mouse(w)
        elif destination in ('south', 'east', 'west', 'fareast'):
            self.viewbook[destination].add_view(view, name=str(label))
            # Make sure the pane is minimally visible
            min_size = config.data.preferences['gui']['min-pane-size']
            pane = self.pane[destination]
            if destination == 'west':
                # position > min_size
                if pane.get_position() < min_size:
                    pane.set_position(min_size)
            else:
                # Other side: max_position - position > min_size
                if pane.props.max_position - pane.props.position < min_size:
                    pane.set_position(pane.props.max_position - min_size)
        return view

    @named_action(name="app.open-adhoc-view-menu")
    def open_adhoc_view_menu(self, viewname: str):
        """Open a adhoc view, with a menu to specify destination

        In expert mode, directly open the view. Else, display a
        popup menu proposing the various places where the view can
        be opened.
        """
        if config.data.preferences['expert-mode']:
            # In expert mode, directly open the view. Experts know
            # how to use drag and drop anyway.
            self.open_adhoc_view(viewname)
            return True

        menu = Gtk.Menu()

        for (label, destination) in (
                (_("Open this view..."), 'default'),
                (_("...in its own window"), 'popup'),
                (_("...embedded east of the video"), 'east'),
                (_("...embedded west of the video"), 'west'),
                (_("...embedded south of the video"), 'south'),
                (_("...embedded at the right of the window"), 'fareast')):
            item = Gtk.MenuItem(label)
            item.connect('activate', lambda b, n, d: self.open_adhoc_view(n, destination=d))
            menu.append(item)

        menu.show_all()
        menu.popup_at_pointer(None)

        return True

    def get_adhoc_view_instance_from_id(self, ident):
        """Return the adhoc view instance matching the identifier.
        """
        views = [ v for v in self.adhoc_views if repr(v) == ident ]
        if views:
            return views[0]
        else:
            return None

    def get_adhoc_view_instance_id(self, view):
        """Return the identifier for the adhoc view instance.
        """
        return repr(view)

    def open_url_embedded(self, url):
        """Open an URL in the embedded web browser.

        If no embedded web browser is present, return False.
        """
        views = [ v for v in self.adhoc_views if v.view_id == 'htmlview' ]
        if views:
            # We use the first one available.
            views[0].open_url(url)
            return True
        else:
            return False

    def update_gui (self):
        """Update the GUI.

        This method should be called upon package loading, or when a
        new view or type is created, or when an existing one is
        modified, in order to reflect changes.
        """
        self.update_stbv_list()
        update_package_list(self.gui.menu_map['package_list_menu'], self.controller)
        return

    def manage_package_save (self, context, parameters):
        """Event Handler executed after saving a package.

        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        self.log (_("Package %(uri)s saved: %(annotations)s and %(relations)s.")
                  % {
                      'uri': self.controller.package.uri,
                      'annotations': helper.format_element_name('annotation',
                                                                len(self.controller.package.annotations)),
                      'relations': helper.format_element_name('relation',
                                                              len(self.controller.package.relations))
                  })
        return True

    def manage_package_activate (self, context, parameters):
        self.log(_("Activating package %s") % self.controller.get_title(self.controller.package))
        self.update_gui()

        self.last_created=[]
        self.last_edited=[]

        self.update_window_title()
        for v in self.adhoc_views:
            if (not hasattr(v, 'close_on_package_load')
                or v.close_on_package_load == True):
                v.close()
            else:
                try:
                    v.update_model(self.controller.package)
                except AttributeError:
                    pass
        # Reset quicksearch source value
        config.data.preferences['quicksearch-sources']=[ "all_annotations" ]
        self.set_busy_cursor(False)

    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.

        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        p = context.evaluateValue('package')
        self.log (_("Package %(uri)s loaded: %(annotations)s and %(relations)s.")
                  % {
                      'uri': p.uri,
                      'annotations': helper.format_element_name('annotation',
                                                                len(p.annotations)),
                      'relations': helper.format_element_name('relation',
                                                              len(p.relations))
                  })
        if not p.uri.endswith('new_pkg'):
            Gtk.RecentManager.get_default().add_item(p.uri)

        # Create the content indexer
        p._indexer=Indexer(controller=self.controller,
                           package=p,
                           abbreviations=self.text_abbreviations)
        p._indexer.initialize()

        # FIXME: it should not be here, but in activate, and called only once
        self.controller.queue_action(self.check_for_default_adhoc_view, p)
        return True

    def check_for_default_adhoc_view(self, package):
        # Open the default adhoc view (which is commonly the _default_workspace)
        default_adhoc = package.getMetaData (config.data.namespace, "default_adhoc")
        view=helper.get_id(package.views, default_adhoc)
        if view:
            if config.data.preferences['restore-default-workspace'] == 'always':
                self.controller.queue_action(self.open_adhoc_view, view, ask=False)
            elif config.data.preferences['restore-default-workspace'] == 'ask':
                def open_view():
                    self.open_adhoc_view(view, ask=False)
                    return True
                dialog.message_dialog(_("Do you want to restore the saved workspace ?"),
                                      icon=Gtk.MessageType.QUESTION,
                                      callback=open_view)
        return False

    def update_window_title(self):
        # Update the main window title
        t=" - ".join((_("Advene"), unquote(str(os.path.basename(self.controller.package.uri))), self.controller.get_title(self.controller.package)))
        if self.controller.package._modified:
            t += " (*)"
            self.toolbuttons['save'].set_sensitive(True)
        else:
            self.toolbuttons['save'].set_sensitive(False)
        self.gui.win.set_title(t)
        return True

    def log(self, msg, level=None):
        """Display log messages.
        """
        logger.info(msg)

    def log_message(self, msg, level=None):
        """Add a new log message to the logmessage window.

        @param msg: the message
        @type msg: string
        @param level: the error level
        @type level: int
        """
        if threading.currentThread().ident != self.main_thread.ident:
            GObject.timeout_add(0, self.log_message, msg, level)
            return False

        # Do not clobber GUI log with Cherrypy log
        if 'cherrypy.error' in msg:
            return

        def undisplay(ctxid, msgid):
            self.gui.statusbar.remove(ctxid, msgid)
            return False

        # Display in statusbar
        if self.gui:
            cid = self.gui.statusbar.get_context_id('info')
            if not isinstance(msg, str):
                msg = str(msg, 'utf-8', 'replace')
            message_id=self.gui.statusbar.push(cid, msg.replace("\n", " - "))
            # Display the message only 4 seconds
            GObject.timeout_add(4000, undisplay, cid, message_id)

        # Store into logbuffer
        buf = self.logbuffer
        mes = "".join(("\n", time.strftime("%H:%M:%S"), " - ", str(msg)))
        # FIXME: handle level (bold?)
        buf.place_cursor(buf.get_end_iter ())
        buf.insert_at_cursor (mes)

        if 'gst-stream-error' in msg:
            dialog.message_dialog(_("Video player error: %s") % msg, modal=False, icon=Gtk.MessageType.WARNING)
        return False

    def get_illustrated_text(self, text, position=None, vertical=False, height=40, color=None):
        """Return a HBox with the given text and a snapshot corresponding to position.
        """
        if vertical:
            box=Gtk.VBox()
        else:
            box=Gtk.HBox()
        box.pack_start(image_from_position(self.controller,
                                           position=position,
                                           height=height), False, False, 0)
        label = Gtk.Label()
        if color:
            label.set_markup('<span background="%s">%s</span>' % (color, text))
        else:
            label.set_text(text)
        box.pack_start(label, False, True, 0)
        return box

    def register_viewclass(self, viewclass, name=None):
        """Register a ViewPlugin class.

        @param viewclass: the viewclass to register
        @type viewclass: a subclass of gui.views.AdhocView
        @param name: the name of the class
        @type name: string
        """
        if name is None:
            name=viewclass.view_id
        if name in self.registered_adhoc_views:
            self.log('Cannot register the %s view, the name is already used.' % name)
            return False
        self.registered_adhoc_views[name]=viewclass
        return True

    def register_view (self, view):
        """Register a view plugin instance.

        @param view: the view to register
        @type view: a view plugin (cf advene.gui.views)
        """
        if view not in self.adhoc_views:
            self.adhoc_views.append (view)
            if hasattr(view, 'register_callback'):
                view.register_callback (controller=self.controller)
        return True

    def unregister_view (self, view):
        """Unregister a view plugin
        """
        if view in self.adhoc_views:
            self.adhoc_views.remove (view)
            try:
                view.unregister_callback (controller=self.controller)
            except AttributeError:
                pass
        return True

    def register_edit_popup (self, e):
        """Register an edit popup.

        @param e: the popup to register
        @type popup: an edit popup (cf advene.gui.edit.elements)
        """
        if e not in self.edit_popups:
            self.edit_popups.append (e)
        return True

    def unregister_edit_popup (self, e):
        """Unregister an edit popup.
        """
        if e in self.edit_popups:
            self.controller.notify("ElementEditDestroy", element=e.element, comment="Window destroyed")
            self.edit_popups.remove (e)
        return True

    def close_view_cb (self, win=None, widget=None, view=None):
        """Generic handler called when a view is closed.
        """
        self.unregister_view (view)
        widget.destroy ()

    def create_element_popup(self, *p, **kw):
        """Wrapper for CreateElementPopup

        This helps to solve a circular import dependency...
        """
        return CreateElementPopup(*p, **kw)

    @named_action(name="app.evaluator", shortcut="<Primary>e")
    def popup_evaluator(self, localsdict=None):
        p=self.controller.package
        try:
            a=p.annotations[-1]
        except IndexError:
            a=None
        try:
            at=p.annotationTypes[-1]
        except IndexError:
            at=None

        class PackageWrapper:
            def __getattr__(self, name):
                e = p.get_element_by_id(name)
                if e is not None:
                    return e
                else:
                    return getattr(p, name)
            def _get_dict(self):
                return dict( (el.id, el) for elements in (p.annotations, p.relations,
                                                          p.schemas,
                                                          p.annotationTypes, p.relationTypes,
                                                          p.views, p.queries) for el in elements )
            __dict__ = property(_get_dict)

        if localsdict is None:
            localsdict = {'package': p,
                          'p': p,
                          'P': PackageWrapper(),
                          'a': a,
                          'at': at,
                          'c': self.controller,
                          'g': self,
                          'pp': pprint.pformat }
        ev=Evaluator(globals_=globals(),
                     locals_=localsdict,
                     historyfile=config.data.advenefile('evaluator.log', 'settings')
                     )
        ev.locals_['self']=ev
        # Define variables referencing the opened views
        for v in self.adhoc_views:
            ev.locals_[v.view_id]=v

        # Hook completer
        ev.completer=Completer(textview=ev.source,
                               controller=self.controller,
                               indexer=getattr(self.controller, '_indexer', None))

        w=ev.popup()
        w.set_icon_list(self.get_icon_list())
        return True

    def update_display (self):
        """Update the interface.

        This method is regularly called by the Gtk mainloop, and
        continually checks whether the interface should be updated.

        Hence, it is a critical execution path and care should be
        taken with the code used here.
        """
        p = self.controller.player
        # Synopsis:
        # Ask the controller to update its status
        # If we are moving the slider, don't update the display
        #Gtk.threads_enter()
        try:
            pos = self.controller.update()
        except Exception:
            logger.exception("Internal exception on video player")
            return True

        if self.slider_move:
            # FIXME: we could have a cache of key images (i.e. 50 equidistant
            # snapshots, and display them to make the navigation in the
            # stream easier
            pass
        elif p.status in self.active_player_status:
            if pos != self.time_label.value:
                self.time_label.set_time(pos)
            # Update the display
            d = self.controller.cached_duration
            if d > 0 and d != self.gui.slider.get_adjustment ().get_upper():
                self.gui.slider.set_range (0, d)
                self.gui.slider.set_increments (int(d / 100), int(d / 10))

            if self.gui.slider.get_value() != pos:
                self.gui.slider.set_value(pos)

            if p.status != self.oldstatus:
                self.oldstatus = p.status
                self.gui.player_status.set_text(self.statustext.get(p.status, _("Unknown")))
                self.playpause_button.set_active(self.oldstatus != p.PlayingStatus)

            # Update the position mark in the registered views
            # Note: beware when implementing update_position in views:
            # it is a critical execution path
            if (abs(self.last_slow_position - pos) > config.data.slow_update_delay
                or pos < self.last_slow_position):
                self.last_slow_position = pos
                for v in self.adhoc_views:
                    try:
                        v.update_position (pos)
                    except AttributeError:
                        pass

        else:
            self.gui.slider.set_value (0)
            if self.time_label.value is not None:
                self.time_label.set_time(None)
            if p.status != self.oldstatus:
                self.oldstatus = self.controller.player.status
                self.gui.player_status.set_text(self.statustext.get(p.status, _("Unknown")))
                self.playpause_button.set_active(self.oldstatus != p.PlayingStatus)
            # New position_update call to handle the starting case (the first
            # returned status is None)
            self.controller.position_update ()

        return True

    def slow_update_display (self):
        """Update the interface (slow version)

        This method is regularly called by the Gtk mainloop, and
        updates elements with a slower rate than update_display
        """
        c = self.controller
        vol = c.player.sound_get_volume() / 100.0
        if self.audio_volume.get_value() != vol:
            self.audio_volume.set_value(vol)

        def do_save(aliases):
            for alias, p in c.packages.items():
                if alias == 'advene':
                    continue
                if p._modified:
                    n, e = os.path.splitext(p.uri)
                    if n.startswith('http:'):
                        continue
                    if n.startswith('file://'):
                        n = n[7:]
                    n = unquote(n + '.backup' + e)
                    p.save(name=n)
            return True

        if c.package and self.gui.win.get_title().endswith('(*)') ^ c.package._modified:
            self.update_window_title()
        self.toolbuttons['undo'].set_sensitive(bool(c.undomanager.history))
        is_playing = c.player.is_playing()
        self.toolbuttons['create_text_annotation'].set_sensitive(is_playing)
        self.toolbuttons['create_svg_annotation'].set_sensitive(is_playing)
        for label in ('rewind', 'forward', 'previous_frame', 'next_frame', 'loop'):
            self.player_toolbar.buttons[label].set_sensitive(is_playing)

        # Check snapshotter activity
        s = getattr(c.player, 'snapshotter', None)
        if c.package and s:
            if s.timestamp_queue.empty():
                self.snapshotter_monitor_icon.set_state('idle')
                # Since the snapshotter is idle, check
                # imagecache.missing_snapshots.
                ic = c.package.imagecache
                if (len(ic.missing_snapshots()) > 0
                    and ic.refetch_count < ic.MAX_IMAGECACHE_REFETCH_COUNT):
                    # There are some missing snapshots, try to get
                    # them again.
                    for t in sorted(ic.missing_snapshots()):
                        c.update_snapshot(t)
                    ic.refetch_count += 1
            else:
                self.snapshotter_monitor_icon.set_state('running')
        else:
            self.snapshotter_monitor_icon.set_state(None)

        # Check auto-save
        if config.data.preferences['package-auto-save'] != 'never':
            t = time.time() * 1000
            if t - self.last_auto_save > config.data.preferences['package-auto-save-interval']:
                # Need to save
                modified = [ alias
                             for (alias, p) in self.controller.packages.items()
                             if p._modified and alias != 'advene' ]
                if modified:
                    if config.data.preferences['package-auto-save'] == 'always':
                        c.queue_action(do_save, modified)
                    else:
                        # Ask before saving. Use the non-modal dialog
                        # to avoid locking the interface
                        dialog.message_dialog(label=_("""The package(s) %s are modified.\nSave them now?""") % ", ".join(modified),
                                              icon=Gtk.MessageType.QUESTION,
                                              callback=lambda: do_save(modified))
                self.last_auto_save=t
        if config.data.debug and debug_slow_update_hook:
            debug_slow_update_hook(self.controller)
        return True

    @named_action(name="app.search-string")
    def search_string(self, s: str):
        if ' ' not in s:
            # Single-word search. Forward to existing note-taking or
            # transcription views.
            # Note: it could maybe be better achieved through a new signal WordSearch
            # which could be handled by the views
            tr = [ v for v in self.adhoc_views if v.view_id in ('transcribe', 'transcription') ]
            for v in tr:
                v.highlight_search_forward(s)
        return self.controller.search_string(searched=s,
                                             sources=config.data.preferences['quicksearch-sources'],
                                             case_sensitive=not config.data.preferences['quicksearch-ignore-case'])

    def do_quicksearch(self, *p):
        s=self.quicksearch_entry.get_text()
        if not s:
            self.log(_("Empty quicksearch string"))
            return True
        res=self.search_string(s)
        self.open_adhoc_view('interactiveresult', destination='east', result=res, label=_("'%s'") % s, query=s)
        return True

    def ask_for_annotation_type(self, text=None, create=False, force_create=False, default=None):
        """Display a popup asking to choose an annotation type.

        If create, then offer the possibility to create a new one.

        @param text: the displayed text
        @type text: str
        @param create: offer to create a new type ?
        @type create: boolean
        @return: the AnnotationType, or None if the action was cancelled.
        """
        if text is None:
            text=_("Choose an annotation type.")
        d = Gtk.Dialog(title=text,
                       parent=self.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                 Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 ))
        label = Gtk.Label(label=text)
        label.set_line_wrap(True)
        label.show()
        d.vbox.pack_start(label, False, True, 0)

        if create and force_create:
            ats=[]
        else:
            ats=list(self.controller.package.annotationTypes)
        newat = None
        if create:
            newat=helper.TitledElement(value=None,
                                       title=_("Create a new annotation type"))
            ats.append(newat)

        # Anticipated declaration of some widgets, which need to be
        # updated in the handle_new_type/schema_selection callback.
        new_type_dialog=Gtk.VBox()
        new_schema_dialog=Gtk.VBox()

        def handle_new_type_selection(combo):
            el=combo.get_current_element()
            if el == newat:
                new_type_dialog.show()
            else:
                new_type_dialog.hide()
            return True

        if len(ats) > 0:
            if create and force_create:
                preselect=newat
            else:
                preselect=default
            type_selector=dialog.list_selector_widget(members=[ (a, self.controller.get_title(a), self.controller.get_element_color(a)) for a in ats],
                                                      preselect=preselect,
                                                      callback=handle_new_type_selection)
        else:
            dialog.message_dialog(_("No annotation type is defined."),
                                  icon=Gtk.MessageType.ERROR)
            return None

        d.vbox.pack_start(type_selector, False, True, 0)
        type_selector.show_all()

        if create:
            d.vbox.pack_start(new_type_dialog, False, True, 0)
            new_type_dialog.pack_start(Gtk.Label(_("Creating a new type.")), True, True, 0)
            ident=self.controller.package._idgenerator.get_id(AnnotationType)
            new_type_title_dialog=dialog.title_id_widget(element_title=ident,
                                                         element_id=ident)
            new_type_title_dialog.title_entry.set_tooltip_text(_("Title of the new type"))
            new_type_title_dialog.id_entry.set_tooltip_text(_("Id of the new type. It is generated from the title, but you may change it if necessary."))
            new_type_dialog.pack_start(new_type_title_dialog, False, True, 0)

            mimetype_selector = dialog.list_selector_widget(members=predefined_content_mimetypes, entry=True)
            mimetype_selector.set_tooltip_text(_("Specify the content-type for the annotation type"))

            new_type_title_dialog.attach(Gtk.Label(label=_("Content type")), 0, 1, 2, 3)
            new_type_title_dialog.attach(mimetype_selector, 1, 2, 2, 3)

            new_type_title_dialog.attach(Gtk.Label(label=_("Schema")), 0, 1, 3, 4)

            schemas=list(self.controller.package.schemas)
            newschema=helper.TitledElement(value=None,
                                           title=_("Create a new schema"))
            schemas.append(newschema)

            def handle_new_schema_selection(combo):
                el=combo.get_current_element()
                if el == newschema:
                    new_schema_dialog.show()
                else:
                    new_schema_dialog.hide()
                return True

            schema_selector=dialog.list_selector_widget(members=[ (s, self.controller.get_title(s), self.controller.get_element_color(s)) for s in schemas],
                                                        callback=handle_new_schema_selection)
            schema_selector.set_tooltip_text(_("Choose an existing schema for the new type, or create a new one"))
            new_type_title_dialog.attach(schema_selector, 1, 2, 3, 4)
            new_type_title_dialog.attach(new_schema_dialog, 1, 2, 4, 5)
            new_schema_dialog.pack_start(Gtk.Label(_("Specify the schema title")), False, False, 0)
            ident=self.controller.package._idgenerator.get_id(Schema)
            new_schema_title_dialog=dialog.title_id_widget(element_title=ident,
                                                           element_id=ident)
            new_schema_title_dialog.title_entry.set_tooltip_text(_("Title of the new schema"))
            new_schema_title_dialog.id_entry.set_tooltip_text(_("Id of the new schema. It is generated from the title, but you may change it if necessary."))
            new_schema_dialog.pack_start(new_schema_title_dialog, False, True, 0)

        d.vbox.show_all()
        if force_create:
            new_type_title_dialog.title_entry.grab_focus()
            type_selector.hide()
        else:
            new_type_dialog.hide()
        new_schema_dialog.hide()

        d.show()
        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        dialog.center_on_mouse(d)
        res=d.run()
        if res == Gtk.ResponseType.OK:
            at=type_selector.get_current_element()
            if at == newat:
                # Creation of a new type.
                attitle=new_type_title_dialog.title_entry.get_text()
                atid=new_type_title_dialog.id_entry.get_text()
                at=self.controller.package.get_element_by_id(atid)
                if at is not None:
                    dialog.message_dialog(_("You specified a annotation-type identifier that already exists. Aborting."))
                    d.destroy()
                    return None
                sc=schema_selector.get_current_element()
                if sc == newschema:
                    sctitle=new_schema_title_dialog.title_entry.get_text()
                    scid=new_schema_title_dialog.id_entry.get_text()
                    sc=self.controller.package.get_element_by_id(scid)
                    if sc is None:
                        # Create the schema
                        sc=self.controller.package.createSchema(ident=scid)
                        sc.author=config.data.userid
                        sc.date=helper.get_timestamp()
                        sc.title=sctitle
                        self.controller.package.schemas.append(sc)
                        self.controller.notify('SchemaCreate', schema=sc)
                    elif isinstance(sc, Schema):
                        # Warn the user that he is reusing an existing one
                        dialog.message_dialog(_("You specified a existing schema identifier. Using the existing schema."))
                    else:
                        dialog.message_dialog(_("You specified an existing identifier that does not reference a schema. Aborting."))
                        d.destroy()
                        return None
                # Create the type
                at=sc.createAnnotationType(ident=atid)
                at.author=config.data.userid
                at.date=helper.get_timestamp()
                at.title=attitle
                at.mimetype=mimetype_selector.get_current_element()
                at.setMetaData(config.data.namespace, 'color', next(self.controller.package._color_palette))
                at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                at._fieldnames=set()
                sc.annotationTypes.append(at)
                self.controller.notify('AnnotationTypeCreate', annotationtype=at)
        else:
            at=None
        d.destroy()
        return at

    def ask_for_schema(self, text=None, create=False):
        """Display a popup asking to choose a schema.

        If create then offer the possibility to create a new one.

        Return: the Schema, or None if the action was cancelled.
        """
        if text is None:
            text=_("Choose a schema.")
        d = Gtk.Dialog(title=text,
                       parent=self.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                 Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 ))
        label=Gtk.Label(label=text)
        label.set_line_wrap(True)
        label.show()
        d.vbox.pack_start(label, False, True, 0)

        # Anticipated declaration of some widgets, which need to be
        # updated in the handle_new_type/schema_selection callback.
        new_schema_dialog=Gtk.VBox()

        schemas=list(self.controller.package.schemas)
        newschema=helper.TitledElement(value=None,
                                       title=_("Create a new schema"))
        schemas.append(newschema)

        def handle_new_schema_selection(combo):
            el=combo.get_current_element()
            if el == newschema:
                new_schema_dialog.show()
            else:
                new_schema_dialog.hide()
            return True

        schema_selector=dialog.list_selector_widget(members=[ (a, self.controller.get_title(a), self.controller.get_element_color(a)) for a in schemas],
                                                    callback=handle_new_schema_selection)
        d.vbox.pack_start(schema_selector, False, True, 0)
        d.vbox.pack_start(new_schema_dialog, False, True, 0)
        new_schema_dialog.pack_start(Gtk.Label(_("Specify the schema title")), False, False, 0)
        ident=self.controller.package._idgenerator.get_id(Schema)
        new_schema_title_dialog=dialog.title_id_widget(element_title=ident,
                                                       element_id=ident)
        new_schema_dialog.pack_start(new_schema_title_dialog, False, True, 0)

        d.vbox.show_all()
        new_schema_dialog.hide()

        d.show()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == Gtk.ResponseType.OK:
            sc=schema_selector.get_current_element()
            if sc == newschema:
                sctitle=new_schema_title_dialog.title_entry.get_text()
                scid=new_schema_title_dialog.id_entry.get_text()
                sc=self.controller.package.get_element_by_id(scid)
                if sc is None:
                    # Create the schema
                    sc=self.controller.package.createSchema(ident=scid)
                    sc.author=config.data.userid
                    sc.date=helper.get_timestamp()
                    sc.title=sctitle
                    self.controller.package.schemas.append(sc)
                    self.controller.notify('SchemaCreate', schema=sc)
                else:
                    dialog.message_dialog(_("You specified an existing identifier. Aborting."))
                    d.destroy()
                    return None
        else:
            sc=None
        d.destroy()
        return sc

    def popup_edit_accumulator(self, *p):
        self.open_adhoc_view('editaccumulator', destination='fareast')
        self.make_pane_visible('fareast')
        return True

    @named_action(name="app.quit", shortcut="<Primary>q")
    def on_exit(self, source=None, event=None):
        """Generic exit callback."""
        for a, p in self.controller.packages.items():
            if a == 'advene':
                continue
            if p._modified:
                t = self.controller.get_title(p)
                response=dialog.yes_no_cancel_popup(title=_("Package %s modified") % t,
                                                    text=_("The package %s has been modified but not saved.\nSave it now?") % t)
                if response == Gtk.ResponseType.CANCEL:
                    return True
                elif response == Gtk.ResponseType.YES:
                    self.on_save1_activate(package=p)
                elif response == Gtk.ResponseType.NO:
                    p._modified=False
            if p.imagecache._modified and config.data.preferences['imagecache-save-on-exit'] != 'never':
                if config.data.preferences['imagecache-save-on-exit'] == 'ask':
                    media=self.controller.get_default_media(package=p)
                    response=dialog.yes_no_cancel_popup(title=_("%s snapshots") % media,
                                                        text=_("Do you want to save the snapshots for media %s?") % media)
                    if response == Gtk.ResponseType.CANCEL:
                        return True
                    elif response == Gtk.ResponseType.YES:
                        try:
                            p.imagecache.save (helper.mediafile2id (media))
                        except OSError as e:
                            self.log(_("Cannot save imagecache for %(media)s: %(e)s") % { "media": media, "e": e })
                    elif response == Gtk.ResponseType.NO:
                        p.imagecache._modified=False
                        pass
                elif config.data.preferences['imagecache-save-on-exit'] == 'always':
                    media=self.controller.get_default_media(package=p)
                    try:
                        p.imagecache.save (helper.mediafile2id (media))
                    except OSError as e:
                        self.log(_("Cannot save imagecache for %(media)s: %(e)s") % { "media": media, "e": e })


        if self.controller.on_exit():
            # Memorize application window size/position
            self.resize_cb(self.gui.win, None, 'main')
            logger.debug(" before self.quit" )
            self.quit()
            # This is a hack for making the app actually exit. It
            # should be automatic at the end of main(), but some
            # references seem to be held (esp. in registered signal)
            # that seem to prevent the framework to exit itself.
            sys.exit(0)
            logger.debug(" after self.quit" )
            return False
        else:
            return True

    def adjust_annotation_bound(self, annotation, bound='begin'):
        """Display a dialog to adjust the annotation bound.
        """
        translation={
            'begin': _('first frame'),
            'end': _('last frame'),
            }
        border_mode = {
            'begin': 'left',
            'end': 'right',
            }
        t=getattr(annotation.fragment, bound)
        fs = FrameSelector(self.controller, t,
                           label=_("Click on %(bound)s of %(annotation)s") % { 'bound': translation[bound],
                                                                               'annotation': self.controller.get_title(annotation) },
                           border_mode=border_mode[bound])
        new = fs.get_value(_("Update %(bound)s of %(annotation)s") % { 'bound': translation[bound],
                                                                       'annotation': self.controller.get_title(annotation) })
        if new != t:
            self.controller.notify('EditSessionStart', element=annotation, immediate=True)
            setattr(annotation.fragment, bound, new)
            self.controller.notify('AnnotationEditEnd', annotation=annotation)
            self.controller.notify('EditSessionEnd', element=annotation)
        return True

    def adjust_annotationtype_bounds(self, at):
        """Adjust annotation bounds for a given type.
        """
        self.open_adhoc_view('shotvalidation', annotationtype=at)
        return True

    def adjust_timestamp(self, t):
        """Display the FrameSelector and return the selected value.
        """
        fs = FrameSelector(self.controller, t,
                           label=_("Click on the frame corresponding to the timestamp value"),
                           border_mode='both')
        new = fs.get_value(_("Set new timestamp value"))
        return new

    def display_statistics(self, annotations, label=None):
        """Display statistics about the given annotations.
        """
        if label is None:
            label = _("<b>Annotation statistics</b>\n\n")
        dialog.message_dialog(label + helper.get_annotations_statistics(annotations))
        return True

    def display_textfile(self, path, title=None, viewname=None):
        w = Gtk.Window()
        if title is not None:
            w.set_title(title + " - " + path)
        w.set_icon_list(self.get_icon_list())

        def refresh(b, t):
            b=t.get_buffer()
            b.delete(*b.get_bounds ())
            try:
                f=open(path, 'r', encoding=detect_by_bom(path=path, default='utf-8'))
                b.set_text("".join(f.readlines()))
                f.close()
            except (IOError, OSError) as e:
                b.set_text("Cannot read %s:\n%s" % (path, str(e)))
            t.scroll_mark_onscreen(b.get_mark('insert'))
            return True

        def close(b, w):
            w.destroy()
            return True

        vbox=Gtk.VBox()

        t=Gtk.TextView()
        t.set_editable (False)
        t.set_wrap_mode (Gtk.WrapMode.CHAR)

        scroll_win = Gtk.ScrolledWindow ()
        scroll_win.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll_win.add(t)

        vbox.add(scroll_win)

        hbox=Gtk.HButtonBox()

        b=Gtk.Button(stock=Gtk.STOCK_CLOSE)
        b.connect('clicked', close, w)
        hbox.pack_start(b, False, True, 0)

        b=Gtk.Button(stock=Gtk.STOCK_REFRESH)
        b.connect('clicked', refresh, t)
        hbox.pack_start(b, False, True, 0)

        vbox.pack_start(hbox, False, True, 0)

        w.add(vbox)
        refresh(None, t)

        if viewname is not None:
            self.controller.gui.init_window_size(w, viewname)

        w.show_all()

        return True

    # Callbacks functions/actions
    @named_action(name="app.create-text-annotation")
    def on_create_text_annotation(self, win=None, event=None):
        c = self.controller
        if c.player.is_playing():
            # Find out the appropriate type
            at = self.controller.package.get_element_by_id('annotation')
            if not at:
                # Does not exist. Create it.
                sc = self.controller.package.schemas[0]
                at = sc.createAnnotationType(ident='annotation')
                at.author = config.data.userid
                at.date = helper.get_timestamp()
                at.title = _("Text annotation")
                at.mimetype = "text/plain"
                at.setMetaData(config.data.namespace, 'color', next(self.controller.package._color_palette))
                at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                at._fieldnames=set()
                sc.annotationTypes.append(at)
                self.controller.notify('AnnotationTypeCreate', annotationtype=at)
            if not isinstance(at, AnnotationType):
                dialog.message_dialog(_("Cannot find an appropriate annotation type"))
                return True
            a = self.controller.create_annotation(c.player.current_position_value, at, content=_("Comment here"))
            self.edit_element(a)
        return True

    @named_action(name="app.create-svg-annotation")
    def on_create_svg_annotation(self, win=None, event=None):
        c = self.controller
        self.controller.update_snapshot(c.player.current_position_value)
        if c.player.is_playing():
            # Find out the appropriate type
            at = self.controller.package.get_element_by_id('svgannotation')
            if not at:
                # Does not exist. Create it.
                sc = self.controller.package.schemas[0]
                at = sc.createAnnotationType(ident='svgannotation')
                at.author = config.data.userid
                at.date = helper.get_timestamp()
                at.title = _("Graphical annotation")
                at.mimetype = "image/svg+xml"
                at.setMetaData(config.data.namespace, 'color', next(self.controller.package._color_palette))
                at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                sc.annotationTypes.append(at)
                self.controller.notify('AnnotationTypeCreate', annotationtype=at)
            if not isinstance(at, AnnotationType):
                dialog.message_dialog(_("Cannot find an appropriate annotation type"))
                return True
            a = self.controller.create_annotation(c.player.current_position_value, at)
            self.edit_element(a)
        return True

    @named_action(name="app.focus-quicksearch", shortcut="<Primary>k")
    def on_focus_quicksearch(self, *p):
        """Get the cursor in the quicksearch entry
        """
        self.quicksearch_entry.grab_focus()
        self.quicksearch_entry.select_region(0, -1)
        return True

    @named_action(name="app.notebook-close-tab", shortcut="<Primary>w")
    def on_notebook_close_tab(self, *p):
        win = self.get_windows()[0]
        focus = win.get_focus()
        if focus is not None:
            nb = focus.get_ancestor(Gtk.Notebook)
            if nb:
                nb.remove_page(nb.get_current_page())
        return True

    @named_action(name="app.notebook-previous-tab", shortcut="<Primary>Page_Up")
    def on_notebox_previous_tab(self, *p):
        win = self.get_windows()[0]
        nb = win.get_focus().get_ancestor(Gtk.Notebook)
        if nb:
            p = nb.get_current_page()
            if p > 0:
                nb.set_current_page(p - 1)
        return True

    @named_action(name="app.notebook-next-tab", shortcut="<Primary>Page_Down")
    def on_notebox_next_tab(self, *p):
        win = self.get_windows()[0]
        nb = win.get_focus().get_ancestor(Gtk.Notebook)
        if nb:
            p = nb.get_current_page()
            if p < nb.get_n_pages() - 1:
                nb.set_current_page(p + 1)
        return True

    def on_win_key_press_event (self, win=None, event=None):
        """Keypress handling.
        """
        # Player shortcuts
        if self.process_player_shortcuts(win, event):
            return True
        return False

    @named_action(name="app.new-package")
    def on_new1_activate (self, button=None, data=None):
        """New package. Erase the current one.
        """
        self.set_busy_cursor(True)
        self.controller.load_package ()
        return True

    @named_action(name="app.new-package-remind")
    def on_new_remind_activate (self, button=None, data=None):
        """New package with REMIND template.
        """
        self.set_busy_cursor(True)
        self.controller.load_package (template=config.data.advenefile(config.data.templates['remind']))
        return True

    @named_action(name="app.new-package-ada")
    def on_new_ada_activate (self, button=None, data=None):
        """New package with AdA template.
        """
        self.set_busy_cursor(True)
        self.controller.load_package (template=config.data.advenefile(config.data.templates['ada']))
        return True

    @named_action(name="app.close")
    def on_close1_activate (self, button=None, data=None):
        p=self.controller.package
        if p._modified:
            response=dialog.yes_no_cancel_popup(title=_("Package modified"),
                                                text=_("The package that you want to close has been modified but not saved.\nSave it now?"))
            if response == Gtk.ResponseType.CANCEL:
                return True
            if response == Gtk.ResponseType.YES:
                self.on_save1_activate()
                self.controller.remove_package()
                return True
            if response == Gtk.ResponseType.NO:
                self.controller.package._modified=False
                self.controller.remove_package()
                return True
        else:
            self.controller.remove_package()

        # Close all edit popups for this element
        for e in self.edit_popups:
            try:
                if p == e.element.rootPackage and e.get_window():
                    e.get_window().destroy()
            except KeyError:
                pass

        return True

    @named_action(name="app.open")
    def on_open_url(self, url: str):
        self.on_open1_activate(filename=url)

    @named_action(name="app.open-dialog")
    def on_open1_activate (self, button=None, data=None, filename=None, corpus=False):
        """Open a file selector to load a package.
        """
        if filename is None:
            default_file = None
            default_dir = config.data.path.get('data')
            corpus_uri = self.controller.corpus_uri
            if corpus and corpus_uri:
                logger.info(f"Setting default file {corpus_uri}")
                default_file = helper.uri2path(corpus_uri)
                default_dir = os.path.dirname(default_file)
            filename, alias = dialog.get_filename(title=_("Load a corpus") if corpus else _("Load a package"),
                                                  action=Gtk.FileChooserAction.OPEN,
                                                  button=Gtk.STOCK_OPEN,
                                                  default_dir=default_dir,
                                                  default_file=default_file,
                                                  alias=True,
                                                  filter='corpus' if corpus else 'advene')
        else:
            name, ext = os.path.splitext(filename)
            alias = re.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))

        if filename:
            name, ext = os.path.splitext(filename.lower())
            filename = helper.path2uri(filename)
            if helper.is_video_file(filename):
                self.log(_("A video file was selected. Pretend that the user selected 'Select a video file'..."))
                self.controller.set_default_media(filename)
                return True
            if ext not in ('.xml', '.azp', '.apl'):
                # Does not look like a valid package
                answer = dialog.yes_no_cancel_popup(_("Unrecognized package extension"), _("The file %s does not look like a valid Advene package. It should have a .azp or .xml extension. Do you want to try to import it instead of opening it as a package?") % filename)
                if answer == Gtk.ResponseType.YES:
                    # Try to import
                    self.open_adhoc_view('importerview', filename=filename)
                    return True
                elif answer == Gtk.ResponseType.CANCEL:
                    return True
            if ext == '.apl':
                modif=[ (a, p)
                        for (a, p) in self.controller.packages.items()
                        if p._modified ]
                if modif:
                    if not dialog.message_dialog(
                            _("You are trying to load a session file, but there are unsaved packages. Proceed anyway?"),
                            icon=Gtk.MessageType.QUESTION):
                        return True

            try:
                self.set_busy_cursor(True)
                self.controller.load_package (uri=filename, alias=alias)
                Gtk.RecentManager.get_default().add_item(filename)
            except (OSError, IOError) as e:
                dialog.message_dialog(_("Cannot load package %(filename)s:\n%(error)s") % {
                    'filename': filename,
                    'error': str(e)}, Gtk.MessageType.ERROR)
            self.set_busy_cursor(False)
        return True

    @named_action(name="app.save", shortcut="<Primary>s")
    def on_save1_activate (self, button=None, package=None):
        """Save the current package."""
        if package is None:
            package=self.controller.package
        self.controller.update_package_title()
        if (package.uri == ""
            or package.uri.endswith('new_pkg')):
            self.on_save_as1_activate (package=package)
        else:
            # Save the current workspace
            workspace_save = False
            if config.data.preferences['save-default-workspace'] == 'always':
                workspace_save = True
            elif config.data.preferences['save-default-workspace'] == 'ask':
                workspace_save = dialog.message_dialog(_("Do you want to save the current workspace ?"),
                                                       icon=Gtk.MessageType.QUESTION)

            if workspace_save and package.isTemplate() and config.data.preferences['expert-mode']:
                # Handle isTemplate option only in expert-mode,
                # and display a warning - it will be a small
                # hindrance for template edition, but will avoid
                # silently not saving package information by mistake
                dialog.message_dialog(_("Template option is activated - workspace will not be saved.\nModify Edit/Package properties if this is an unwanted behaviour."))
                workspace_save = False

            modified = [ p for p in self.edit_popups if p.get_modified() ]
            if modified and config.data.preferences['apply-edited-elements-on-save']:
                for p in modified:
                    p.apply_cb()
            if workspace_save:
                self.workspace_save('_default_workspace')
                default=self.controller.package.getMetaData (config.data.namespace, "default_adhoc")
                if not default:
                    self.controller.package.setMetaData (config.data.namespace, "default_adhoc", '_default_workspace')
            alias=self.controller.aliases[package]
            try:
                self.controller.save_package (alias=alias)
            except (OSError, IOError, PermissionError) as e:
                dialog.message_dialog(_("Could not save the package: %s") % str(e),
                                      Gtk.MessageType.ERROR)
        return True

    @named_action(name="app.save-as", shortcut="<Primary><Shift>s")
    def on_save_as1_activate (self, button=None, package=None):
        """Save the package with a new name."""
        if package is None:
            package=self.controller.package
        self.controller.update_package_title()
        filename=dialog.get_filename(title=_("Save the package %s") % self.controller.get_title(package),
                                     action=Gtk.FileChooserAction.SAVE,
                                     button=Gtk.STOCK_SAVE,
                                     default_dir=config.data.path.get('data'),
                                     filter='advene')
        if filename:
            (p, ext) = os.path.splitext(filename)
            if ext == '':
                # Add a pertinent extension
                filename = filename + '.azp'

            if (package.resources and package.resources.children()
                and ext.lower() != '.azp'):
                ret=dialog.yes_no_cancel_popup(title=_("Invalid file extension"),
                                               text=_("Your package contains resources,\nthe filename (%s) should have a .azp extension.\nShould I put the correct extension?") % filename)
                if ret == Gtk.ResponseType.YES:
                    filename = p + '.azp'
                elif ret == Gtk.ResponseType.NO:
                    dialog.message_dialog(_("OK, the resources will be lost."))
                else:
                    self.log(_("Aborting package saving"))
                    return True

            # Save the current workspace
            save=False
            if config.data.preferences['save-default-workspace'] == 'always':
                save=True
            elif config.data.preferences['save-default-workspace'] == 'ask':
                save=dialog.message_dialog(_("Do you want to save the current workspace ?"),
                                           icon=Gtk.MessageType.QUESTION)
            if save and package.title != "Export package":
                self.workspace_save('_default_workspace')
                default=self.controller.package.getMetaData (config.data.namespace, "default_adhoc")
                if not default:
                    self.controller.package.setMetaData (config.data.namespace, "default_adhoc", '_default_workspace')
            alias=self.controller.aliases[package]
            modified = [ pop for pop in self.edit_popups if pop.get_modified() ]
            if modified and config.data.preferences['apply-edited-elements-on-save']:
                for p in modified:
                    p.apply_cb()
            try:
                self.controller.save_package(name=filename, alias=alias)
            except (OSError, IOError, PermissionError) as e:
                dialog.message_dialog(_("Could not save the package: %s") % str(e),
                                      Gtk.MessageType.ERROR)
        return True

    @named_action(name="app.save-session")
    def on_save_session1_activate (self, button=None, data=None):
        """Save the current session.
        """
        filename=dialog.get_filename(title=_("Save the session in..."),
                                     action=Gtk.FileChooserAction.SAVE,
                                     button=Gtk.STOCK_SAVE,
                                     default_dir=config.data.path.get('data'),
                                     filter='session')
        if filename:
            (p, ext) = os.path.splitext(filename)
            if ext == '':
                # Add a pertinent extension
                filename = filename + '.apl'
            self.controller.save_session(filename)
            self.log(_("Session saved in %s") % filename)
        return True

    @named_action(name="app.import-dvd-chapters")
    def on_import_dvd_chapters1_activate (self, button=None, data=None):
        # FIXME: loosy test
        if (self.controller.get_default_media() is None
            or 'dvd' in self.controller.get_default_media()):
            if not dialog.message_dialog(
                    _("Do you confirm the creation of annotations matching the DVD chapters?"),
                    icon=Gtk.MessageType.QUESTION):
                return True
            try:
                i=advene.util.importer.get_importer('lsdvd', controller=self.controller)
            except Exception:
                dialog.message_dialog(_("Cannot import DVD chapters. Did you install the lsdvd software?"),
                                      icon=Gtk.MessageType.ERROR)
                return True
            i.package=self.controller.package
            i.process_file('lsdvd')
            self.controller.package._modified = True
            self.controller.notify('PackageLoad', package=self.controller.package)
        else:
            dialog.message_dialog(_("The associated media is not a DVD."),
                                  icon=Gtk.MessageType.ERROR)
        return True

    @named_action(name="app.import-file")
    def on_import_file1_activate (self, button=None, data=None):
        self.open_adhoc_view('importerview')
        return False

    @named_action(name="app.process-video")
    def on_process_video_activate(self, button=None, data=None):
        fname = self.controller.get_default_media()
        # Convert media path to local filename if possible
        fname = helper.uri2path(fname) or fname
        if fname:
            self.open_adhoc_view('importerview', filename=fname, message=_("Processing %s video") % fname,
                                 display_unlikely=False)
        else:
            dialog.message_dialog(_("No associated video file"),
                                  icon=Gtk.MessageType.ERROR)
        return False

    @named_action(name="app.find")
    def on_find1_activate (self, button=None, data=None):
        self.open_adhoc_view('interactivequery', destination='east')
        return True

    @named_action(name="app.global_actions")
    def on_global_actions_activate (self, button=None, data=None):
        menu = advene.gui.popup.Menu(self.controller.package, controller=self.controller)
        menu.popup()
        return True

    @named_action(name="app.edit-ruleset")
    def on_edit_ruleset1_activate (self, button=None, data=None):
        """Default ruleset editing."""
        w=Gtk.Window(Gtk.WindowType.TOPLEVEL)
        w.set_title(_("Standard RuleSet"))
        w.connect('destroy', lambda e: w.destroy())
        w.set_icon_list(self.get_icon_list())

        vbox=Gtk.VBox()
        vbox.set_homogeneous (False)
        w.add(vbox)

        rs = self.controller.event_handler.get_ruleset('default')
        edit=EditRuleSet(rs,
                         catalog=self.controller.event_handler.catalog,
                         controller=self.controller)
        wid = edit.get_packed_widget()
        vbox.add(wid)
        wid.show_all()

        def validate_ruleset(button, type_):
            edit.update_value()
            # edit.model has been edited
            self.controller.event_handler.set_ruleset(edit.model, type_=type_)
            w.destroy()
            return True

        def save_ruleset(button, type_):
            edit.update_value()
            # edit.model has been edited
            self.controller.event_handler.set_ruleset(edit.model, type_=type_)
            # FIXME: implement ruleset save
            logger.error("Not implemented yet")
            return True

        hb=Gtk.HButtonBox()

        b=Gtk.Button(stock=Gtk.STOCK_SAVE)
        b.connect('clicked', save_ruleset, 'default')
        hb.pack_start(b, False, True, 0)

        b=Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', validate_ruleset, 'default')
        hb.pack_start(b, False, True, 0)

        b=Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b.connect('clicked', lambda e: w.destroy())
        hb.pack_end(b, False, True, 0)

        hb.show_all()

        vbox.pack_start(hb, False, True, 0)

        vbox.show()

        w.show()
        return True

    @named_action(name="app.show-media-information")
    def on_view_mediainformation_activate (self, button=None, data=None):
        """View mediainformation.
        """
        self.controller.position_update ()
        p = self.controller.player
        ic = self.controller.package.imagecache
        info = ic.video_info
        info['duration_formatted'] = helper.format_time_reference(info['duration'])
        info['position_formatted'] = helper.format_time_reference(p.current_position_value)
        info['cached_duration_formatted'] = helper.format_time_reference(self.controller.cached_duration)
        info['position'] =  p.current_position_value
        info['imagecache'] = ic.stats_repr()
        msg = _("""Media information

URI: %(uri)s
Framerate: %(framerate_denom)d / %(framerate_num)d (%(framerate).02f )
Duration: %(duration_formatted)s (%(duration)d ms) (cached: %(cached_duration_formatted)s)
Current position: %(position_formatted)s (%(position)d ms)

Original image size: %(width)d x %(height)d

Image cache information: %(imagecache)s
""") % info
        self.popupwidget.display_message(msg, timeout=30000, title=_("Information"))
        logger.info(msg)
        return True

    @named_action(name="app.about")
    def on_about1_activate (self, button=None, data=None):
        """Activate the About window."""
        d=Gtk.AboutDialog()
        d.set_transient_for(self.gui.win)
        d.set_activate_link = lambda dialog, link: self.controller.open_url(link)
        d.set_name('Advene')
        d.set_version(config.data.version_string.replace('Advene ', ''))
        d.set_copyright("Copyright 2002-2020 Olivier Aubert, Pierre-Antoine Champin, Yannick Prié")
        d.set_license_type(Gtk.License.GPL_3_0)
        d.set_website('https://www.advene.org/')
        d.set_website_label(_('Visit the Advene web site for examples and documentation.'))
        d.set_authors( [ 'Olivier Aubert', 'Pierre-Antoine Champin', 'Yannick Prié', 'Bertrand Richard', 'Frank Wagner' ] )
        d.set_logo(GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile( ( 'pixmaps', 'logo_advene.png') )))
        d.connect('response', lambda w, r: w.destroy())
        d.run()

        return True

    @named_action(name="app.open-video")
    def on_b_addfile_clicked (self, button=None, data=None):
        """Open a video file"""
        mp=[ d for d in str(config.data.path['moviepath']).split(os.path.pathsep) if d != '_' ]
        if mp:
            default=mp[0]
        else:
            default=None
        filename=dialog.get_filename(title=_("Select a movie file"),
                                     action=Gtk.FileChooserAction.OPEN,
                                     button=Gtk.STOCK_OPEN,
                                     default_dir=default,
                                     filter='video')
        if filename:
            self.controller.set_default_media(filename)
        return True

    @named_action(name="app.open-dvd")
    def on_b_selectdvd_clicked (self, button=None, data=None):
        """Play a DVD."""
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        window.set_title(_("Title/Chapter selection"))

        window.connect('destroy', lambda e: window.destroy())

        vbox=Gtk.VBox()

        sel=DVDSelect(controller=self.controller,
                      current=self.controller.get_default_media())
        vbox.add(sel.get_widget())

        hbox=Gtk.HButtonBox()

        def validate(button=None, sel=None, window=None):
            self.controller.update_status("stop")
            url=sel.get_url()
            sel.get_widget().destroy()
            self.controller.set_default_media(url)
            #self.controller.update_status ("start")
            window.destroy()
            return True

        def cancel(button=None, window=None):
            self.controller.update_status("stop")
            sel.get_widget().destroy()
            window.destroy()
            return True

        b=Gtk.Button(stock=Gtk.STOCK_OK)
        b.connect('clicked', validate, sel, window)
        hbox.add(b)

        b=Gtk.Button(stock=Gtk.STOCK_CANCEL)
        b.connect('clicked', cancel, window)
        hbox.add(b)

        vbox.add(hbox)
        window.add(vbox)
        window.show_all()

        return True

    @named_action(name="app.open-video-stream")
    def on_select_a_video_stream1_activate(self, button=None, data=None):
        stream=dialog.entry_dialog(title=_("Select a video stream"),
                                   text=_("Enter the address of a video stream"))
        if stream:
            s=helper.get_video_stream_from_website(stream)
            if s is not None:
                dialog.message_dialog(_("Successfully extracted the video stream address (%s) from the url.\n") % s)
                stream=s
            self.controller.set_default_media(stream)
        return True

    @named_action(name="app.edit-imports")
    def on_package_imports1_activate (self, button=None, data=None):
        """Edit imported elements from other packages."""
        imp=advene.gui.edit.imports.Importer(controller=self.controller)
        imp.popup()
        return True

    @named_action(name="app.edit-package-properties")
    def on_package_properties1_activate (self, button=None, data=None):
        self.open_adhoc_view('edit', element=self.controller.package)
        return True

    @named_action(name="app.edit-preferences")
    def on_preferences1_activate (self, button=None, data=None):
        # Direct options are directly retrieved/stored from/into config.data.preferences
        direct_options=('history-size-limit', 'scroll-increment', 'second-scroll-increment',
                        'time-increment', 'second-time-increment', 'third-time-increment',
                        'custom-updown-keys', 'player-autostart',
                        'language',
                        'display-scroller', 'display-caption', 'imagecache-save-on-exit',
                        'remember-window-size', 'expert-mode', 'update-check',
                        'package-auto-save', 'package-auto-save-interval',
                        'bookmark-snapshot-width', 'bookmark-snapshot-precision',
                        'save-default-workspace', 'restore-default-workspace',
                        'slave-player-sync-delay',
                        'tts-language', 'tts-encoding', 'tts-engine',
                        'record-actions', 'popup-destination',
                        'timestamp-format', 'default-fps',
                        'abbreviation-mode', 'text-abbreviations',
                        'completion-mode', 'completion-predefined-only', 'completion-quick-fill',
                        'prefer-wysiwyg',
                        'player-shortcuts-in-edit-windows', 'player-shortcuts-modifier',
                        'apply-edited-elements-on-save', 'use-uuid',
                        'frameselector-count', 'frameselector-width',
        )
        # Direct options needing a restart to be taken into account.
        restart_needed_options = ('tts-engine', 'language', 'timestamp-format', 'expert-mode')

        path_options=('data', 'advene', 'imagecache', 'moviepath', 'shotdetect')
        cache={
            'font-size': config.data.preferences['timeline']['font-size'],
            'button-height': config.data.preferences['timeline']['button-height'],
            'interline-height': config.data.preferences['timeline']['interline-height'],
            }

        cache['player-level'] = config.data.player['verbose'] or -1
        for (k, v) in config.data.player.items():
            cache['player-' + k] = config.data.player[k]

        for k in path_options:
            cache[k] = str(config.data.path[k])
        for k in direct_options:
            cache[k] = config.data.preferences[k]
        cache['package-auto-save-interval']=cache['package-auto-save-interval']/1000
        ew=advene.gui.edit.properties.EditNotebook(cache.__setitem__, cache.get)
        ew.set_name(_("Preferences"))

        ew.add_title(_("Paths"))

        ew.add_dir_selector(_("Data"), "data", _("Standard directory for data files"))
        ew.add_dir_selector(_("Movie path"), "moviepath", _("List of directories (separated by %s) to search for movie files (_ means package directory)") % os.path.pathsep)
        ew.add_dir_selector(_("Imagecache"), "imagecache", _("Directory for storing the snapshot cache"))
        ew.add_file_selector(_("Shotdetect"), "shotdetect", _("Shotdetect application"))

        ew.add_title(_("GUI"))
        ew.add_option(_("Interface language (after restart)"), 'language', _("Language used for the interface (necessitates to restart the application)"), OrderedDict((
            (_("System default"), ''),
            ("English", 'C'),
            ("Esperanto", 'eo'),
            ("Francais", 'fr_FR'),
        )))
        ew.add_checkbox(_("Expert mode"), "expert-mode", _("Offer advanced possibilities"))
        ew.add_checkbox(_("Prefer WYSIWYG"), "prefer-wysiwyg", _("Use WYSIWYG editors when possible (HTML, SVG)"))
        ew.add_accelerator(_("Player control modifier"), 'player-shortcuts-modifier', _("Generic player control modifier: key used in combination with arrows/space/tab to control the player. Click the button and press key+space to choose the modifier."))
        ew.add_checkbox(_("Player control in edit popups"), 'player-shortcuts-in-edit-windows', _("Enable generic player controls in edit windows. This may be undesirable since it overloads some standard text-edition behaviours (esp. control-left/right)."))
        ew.add_option(_("Open popups"), 'popup-destination',
                      _("Where should we open adhoc views?"), OrderedDict((
                          (_("as a popup window"), 'popup'),
                          (_("embedded east of the video"), 'east'),
                          (_("embedded west of the video"), 'west'),
                          (_("embedded south of the video"), 'south'),
                          (_("embedded at the right of the window"), 'fareast'),
                      )))

        ew.add_spin(_("History size"), "history-size-limit", _("History filelist size limit"),
                    -1, 20)
        ew.add_checkbox(_("Remember window size"), "remember-window-size", _("Remember the size of opened windows"))
        ew.add_spin(_("Bookmark snapshot width"), 'bookmark-snapshot-width', _("Width of the snapshots representing bookmarks"), 50, 400)
        ew.add_spin(_("Bookmark snapshot precision"), 'bookmark-snapshot-precision', _("Precision (in ms) of the displayed bookmark snapshots."), 25, 500)

        ew.add_label(_("Frame selector (shotvalidation...)"))
        ew.add_spin(_("Frameselector snapshot width"), 'frameselector-width', _("Width of the snapshots in frameselector"), 50, 600)
        ew.add_spin(_("Frameselector count"), 'frameselector-count', _("Number of frames displayed in frameselector."), 3, 25)

        ew.add_title(_("General"))
        ew.add_checkbox(_("Use UUIDs"), 'use-uuid', _("Use UUIDs for identifying elements instead of more readable shortnames"))
        ew.add_checkbox(_("Weekly update check"), 'update-check', _("Weekly check for updates on the Advene website"))
        ew.add_option(_("On exit,"), 'imagecache-save-on-exit',
                      _("How to handle screenshots on exit"), OrderedDict((
                          (_("never save screenshots"), 'never'),
                          (_("always save screenshots"), 'always'),
                          (_("ask before saving screenshots"), 'ask'),
                      )))
        ew.add_option(_("Auto-save"), 'package-auto-save',
                      _("Data auto-save functionality"), OrderedDict((
                          (_("is desactivated"), 'never'),
                          (_("is done automatically"), 'always'),
                          (_("is done after confirmation"), 'ask'),
                      )))
        ew.add_spin(_("Auto-save interval (in s)"), 'package-auto-save-interval', _("Interval (in seconds) between package auto-saves"), 5, 60 * 60)

        ew.add_title(_("Workspace"))

        ew.add_option(_("On package saving,"), 'save-default-workspace',
                      _("Do you wish to save the default workspace with the package?"), OrderedDict((
                          (_("never save the current workspace"), 'never'),
                          (_("always save the current workspace"), 'always'),
                          (_("ask before saving the current workspace"), 'ask'),
                      )))
        ew.add_checkbox(_("Auto-validation of edited elements"), 'apply-edited-elements-on-save', _("Automatically validate modified elements when saving the package."))

        ew.add_option(_("On package load,"), 'restore-default-workspace',
                      _("Do you wish to load the workspace saved with the package?"), OrderedDict((
                          (_("never load the saved workspace"), 'never'),
                          (_("always load the saved workspace"), 'always'),
                          (_("ask before loading the saved workspace"), 'ask'),
                      )))

        ew.add_title(_("Video Player"))
        ew.add_checkbox(_("Autostart"), 'player-autostart', _("Automatically start the player when loading a media file (either directly or through a package)"))
        ew.add_checkbox(_("Fulscreen timestamp"), 'player-fullscreen-timestamp', _("Display the timestamp over the video when in fullscreen mode"))
        ew.add_checkbox(_("Enable captions"), "player-caption", _("Enable captions over the video"))
        ew.add_file_selector(_("Caption font"), "player-osdfont", _("TrueType font for captions"))
        ew.add_checkbox(_("Enable SVG"), "player-svg", _("Enable SVG captions over the video"))

        ew.add_checkbox(_("Enable snapshots"), "player-snapshot", _("Enable snapshots"))
        ew.add_spin(_("Snapshot width"), "player-snapshot-width", _("Snapshot width in pixels."), 0, 1280)
        ew.add_spin(_("Verbosity"), "player-level", _("Verbosity level. -1 for no messages."),
                    -1, 3)

        ew.add_label(_("Devices"))

        options={_("Standard"): 'default' }
        if config.data.os == 'win32':
            ew.add_entry(_("DVD drive"), 'player-dvd-device', _("Drive letter for the DVD"))
            options[_("Direct3D")] = 'd3d'
            options[_("OpenGL")] = 'gl'
            options[_("Gtk")] = 'gtk'
        else:
            ew.add_entry(_("DVD device"), 'player-dvd-device', _("Device for the DVD"))
            options[_("X11")] = 'x11'
            options[_("XVideo")] = 'xvideo'
            options[_("GL")] = 'gl'
            options[_("Gtk")] = 'gtk'

        ew.add_option(_("Video output"), "player-vout", _("Video output module"), options)

        ew.add_label(_("Recorder options"))
        ew.add_entry(_("Audio input"), 'player-audio-record-device', _("Device name for audio input (with gstrecorder plugin)"))
        ew.add_checkbox(_("Record video"), 'player-record-video', _("Record both video and audio"))

        if config.data.preferences['expert-mode']:
            ew.add_label(_("<i>Experimental</i>"))
            ew.add_checkbox(_("Scroller"), 'display-scroller', _("Embed the caption scroller below the video"))
            ew.add_checkbox(_("Caption"), 'display-caption', _("Embed the caption view below the video"))

        ew.add_title(_("Time-related"))
        ew.add_option(_("Time format"), 'timestamp-format', _("Format used to display timecodes"), OrderedDict( (
            ('HH:MM:SS.sss', '%H:%M:%.S'),
            ('HH:MM:SSfNN (frame number)', '%H:%M:%fS'),
            ('HH:MM:SS', '%H:%M:%S'),
            ('MM:SS.sss', '%M:%.S'),
            ('MM:SS', '%M:%S'),
            ('SS.sss', '%.S'),
            ('SS', '%S'),
        )) )
        fps = [ 10, 12, 24, 25, 30, 40, 50, 60, 72 ]
        d = config.data.preferences['default-fps']
        if d not in fps:
            fps.append(d)
            fps.sort()
        ew.add_option(_("Default FPS"), 'default-fps',
                      _("Default FPS (frame-per-second) value, when the information cannot be read from the media."), OrderedDict( (str(f), f) for f in fps))
        ew.add_spin(_("Time increment"), "time-increment", _("Skip duration, when using control-left/right or forward/rewind buttons (in ms)."), 1, 300000)
        ew.add_spin(_("Second time increment"), "second-time-increment", _("Skip duration, when using control-shift-left/right (in ms)."), 1, 300000)
        ew.add_spin(_("Third time increment"), "third-time-increment", _("Skip duration, when using control-shift-up/down (in ms)."), 1, 300000)
        ew.add_checkbox(_("Custom Up/Down"), 'custom-updown-keys', _("Use third time increment for up/down navigation without having to hold shift."))
        ew.add_label("")
        ew.add_spin(_("Scroll increment"), "scroll-increment", _("On most annotations, control+scrollwheel will increment/decrement their bounds by this value (in ms)."), 10, 10000)
        ew.add_spin(_("Second scroll increment"), "second-scroll-increment", _("On most annotations, control+shift+scrollwheel will increment/decrement their bounds by this value (in ms)."), 10, 10000)
        ew.add_label("")
        ew.add_spin(_("Player sync"), 'slave-player-sync-delay', _("Interval (in ms) with which we synchronize slave players. Setting a too-low value could render the application unusable. Use 0 to disable continuous synchronization."), 0, 60 * 1000)
        ew.add_title(_("Timeline parameters"))
        ew.add_spin(_("Font size"), 'font-size', _("Font size for annotation widgets"), 4, 20)
        ew.add_spin(_("Button height"), 'button-height', _("Height of annotation widgets"), 10, 50)
        ew.add_spin(_("Interline height"), 'interline-height', _("Height of interlines"), 0, 40)

        ew.add_title(_("Text content"))
        ew.add_checkbox(_("Completion mode"), 'completion-mode', _("Enable dynamic completion mode"))
        ew.add_checkbox(_("Predefined terms only"), 'completion-predefined-only', _("If completion is enabled, complete only with predefined terms."))
        ew.add_checkbox(_("Quick fill"), 'completion-quick-fill', _("For types with predefined completions, use a numeric (1-9) shortcut to fill the annotation with the corresponding completion."))
        ew.add_checkbox(_("Abbreviation mode"), 'abbreviation-mode', _("Enable abbreviation mode"))
        ew.add_text(_("Abbreviations"), 'text-abbreviations', _("Text abbreviations. 1 entry per line. Each line consists of the abbreviation followed by its replacement."))

        ew.add_title(_("Text-To-Speech"))
        ew.add_option(_("TTS language"), 'tts-language',
                      _("What language settings should be used for text-to-speech"), OrderedDict((
                          (_("English"), 'en'),
                          (_("French"), 'fr'),
                          (_("Spanish"), 'es'),
                )))
        ew.add_entry(_("TTS Encoding"), 'tts-encoding',
                     _("What encoding should be used to communicate with the TTS engine"), entries = [ 'utf8', 'utf16', 'latin1', 'cp1252' ] )
        ew.add_option(_("TTS Engine"), 'tts-engine',
                      _("Which TTS engine should be used (modification requires restarting Advene to take into account)"), OrderedDict((
                          (_("Automatic"), 'auto'),
                          (_("eSpeak"), 'espeak'),
                          (_("Custom script with standard input"), 'custom'),
                          (_("Custom script with arguments"), 'customarg'),
                          (_("SAPI"), 'sapi'),
                          (_("MacOS X say"), 'macosx'),
                          (_("Generic (text output)"), 'generic'),
                      )))

        res=ew.popup()
        if res:
            player_need_restart = False
            app_need_restart = False

            cache['package-auto-save-interval']=cache['package-auto-save-interval']*1000
            if cache['text-abbreviations'] != config.data.preferences['text-abbreviations']:
                self.text_abbreviations.clear()
                self.text_abbreviations.update( dict( line.split(" ", 1) for line in config.data.preferences['text-abbreviations'].splitlines() ) )

            for k in direct_options:
                if k in restart_needed_options and config.data.preferences[k] != cache[k]:
                    app_need_restart = True
                config.data.preferences[k] = cache[k]

            for k in ('font-size', 'button-height', 'interline-height'):
                config.data.preferences['timeline'][k] = cache[k]
            for k in path_options:
                if cache[k] != str(config.data.path[k]):
                    config.data.path[k] = Path(cache[k])
                    # Store in auto-saved preferences
                    config.data.preferences['path'][k] = Path(cache[k])
                    if k == 'plugins':
                        player_need_restart = True

            self.update_player_control_modifier()

            for n in list(config.data.player.keys()):
                if config.data.player[n] != cache['player-' + n]:
                    config.data.player[n] = cache['player-' + n]
                    player_need_restart = True
            # Special handling for verbose
            if cache['player-level'] == -1:
                config.data.player['verbose'] = None
            else:
                config.data.player['verbose'] = cache['player-level']
            if player_need_restart:
                self.controller.restart_player ()

            # Save preferences
            config.data.save_preferences()

            if app_need_restart:
                dialog.message_dialog(_("You should restart Advene to take some options into account."), modal=False)

        return True

    @named_action(name="app.save-imagecache")
    def on_save_imagecache1_activate (self, button=None, data=None):
        media=self.controller.get_default_media()
        id_ = helper.mediafile2id (media)
        try:
            d=self.controller.package.imagecache.save (id_)
            self.log(_("Imagecache saved to %s") % d)
        except OSError:
            logger.error(_("Cannot save imagecache for %s"), media, exc_info=True)
        return True

    @named_action(name="app.reset-imagecache")
    def on_reset_imagecache_activate (self, button=None, data=None):
        valid = self.controller.package.imagecache.valid_snapshots()
        self.controller.package.imagecache.reset()
        for t in valid:
            self.controller.notify('SnapshotUpdate', position=t, media=self.controller.package.media)
        return True

    @named_action(name="app.player-restart")
    def on_restart_player1_activate (self, button=None, data=None):
        self.log (_("Restarting player..."))
        self.controller.restart_player ()
        return True

    def on_slider_button_press_event (self, button=None, event=None):
        self.slider_move = True
        return

    def on_slider_button_release_event (self, button=None, event=None):
        self.controller.update_status('seek', int(self.gui.slider.get_value ()))
        self.slider_move = False
        return

    def on_slider_scroll_event (self, widget=None, event=None):
        incr = 0
        if event.direction == Gdk.ScrollDirection.DOWN or event.direction == Gdk.ScrollDirection.RIGHT:
            incr=+1
        if event.direction == Gdk.ScrollDirection.UP or event.direction == Gdk.ScrollDirection.LEFT:
            incr=-1
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            deltax = event.get_scroll_deltas()[1]
            if deltax > 0:
                incr = +1
            else:
                incr = -1
        if incr:
            self.controller.move_frame(incr)
        return

    def on_video_button_press_event (self, button=None, event=None):
        if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
            self.controller.player.fullscreen(self.connect_fullscreen_handlers)
        elif event.button == 3:
            self.player_create_bookmark(event)
        return False

    @named_action(name="app.help")
    def on_help1_activate (self, button=None, data=None):
        self.controller.open_url ('https://www.advene.org/wiki/AdveneUserGuide')
        return True

    @named_action(name="app.help-support")
    def on_support1_activate (self, button=None, data=None):
        self.controller.open_url ('https://github.com/oaubert/advene/')
        return True

    @named_action(name="app.help-shorcuts")
    def on_helpshortcuts_activate (self, button=None, data=None):
        helpfile = Path(config.data.advenefile('shortcuts.html', 'web'))
        if helpfile.is_file():
            self.controller.open_url(helpfile.as_uri())
        else:
            self.controller.open_url('https://www.advene.org/wiki/AdveneShortcuts')
        return True

    @named_action(name="app.show-webserver-log")
    def on_webserver_log1_activate (self, button=None, data=None):
        self.display_textfile(config.data.advenefile('webserver.log', 'settings'),
                              title=_("Webserver log"),
                              viewname='weblogview')
        return True

    @named_action(name="app.show-log")
    def on_advene_log_display(self, button=None, data=None):
        self.open_adhoc_view('logmessages', destination='south')
        return True

    @named_action(name="app.show-logfile")
    def on_advene_log_folder_display(self, button=None, data=None):
        open_in_filebrowser(config.data.advenefile('', 'settings'))
        return True

    @named_action(name="app.create-view")
    def on_create_view_activate (self, button=None, data=None):
        cr = CreateElementPopup(type_ = View,
                                parent=self.controller.package,
                                controller=self.controller)
        cr.popup()
        return True

    @named_action(name="app.create-query")
    def on_create_query_activate (self, button=None, data=None):
        cr = CreateElementPopup(type_ = Query,
                                parent=self.controller.package,
                                controller=self.controller)
        cr.popup()
        return True

    @named_action(name="app.create-schema")
    def on_create_schema_activate (self, button=None, data=None):
        cr = CreateElementPopup(type_ = Schema,
                                parent=self.controller.package,
                                controller=self.controller)
        sc=cr.popup()
        return sc

    @named_action(name="app.create-annotation-type")
    def on_create_annotation_type_activate (self, button=None, data=None):
        at=self.ask_for_annotation_type(text=_("Creation of a new annotation type"),
                                        create=True,
                                        force_create=True)
        if at is None:
            return None
        return at

    @named_action(name="app.create-relation-type")
    def on_create_relation_type_activate (self, button=None, data=None):
        sc=self.ask_for_schema(text=_("Select the schema where you want to\ncreate the new relation type."), create=True)
        if sc is None:
            return None
        cr=CreateElementPopup(type_=RelationType,
                              parent=sc,
                              controller=self.controller)
        rt=cr.popup()
        return rt

    @named_action(name="app.merge-package")
    def on_merge_package_activate(self, button=None, data=None):
        filenames = dialog.get_filename(title=_("Select the package to merge"),
                                        action=Gtk.FileChooserAction.OPEN,
                                        button=Gtk.STOCK_OPEN,
                                        default_dir=config.data.path.get('data'),
                                        multiple=True,
                                        filter='advene')
        if not filenames:
            return True

        if len(filenames) == 1:
            filename = filenames[0]
            # Single package - offer interface
            try:
                source=Package(uri=helper.path2uri(filename))
            except Exception as e:
                msg = "Cannot load %s file: %s" % (filename, str(e))
                self.log(msg)
                dialog.message_dialog(msg, icon=Gtk.MessageType.ERROR)
                return True
            self.open_adhoc_view('package_merger', sourcepackage=source, destpackage=self.controller.package)
            return True
        else:
            # Multiple package merging. No interface yet.
            if not dialog.message_dialog(_("Please confirm the merge of %d packages.") % len(filenames),
                                         icon=Gtk.MessageType.QUESTION):
                return True

            def runner_method(callback=None):
                def callback_wrapper(prg, label):
                    logger.info(label)
                    return callback(prg, label)
                advene.util.merger.merge_package(self.controller.package, filenames, exclude={}, callback=callback_wrapper)
                dur = self.controller.package.getMetaData(config.data.namespace, "duration")
                if dur != self.controller.cached_duration:
                    # It may well have been updated
                    self.controller.cached_duration = dur
                    self.controller.notify('DurationUpdate', duration=dur)
                self.controller.notify('PackageActivate', package=self.controller.package)

            dialog.progress_dialog(title=_("Merging %d packages") % len(filenames),
                                   runner=runner_method,
                                   controller=self.controller)
            return True

    @named_action(name="app.import-package")
    def on_import_package_activate(self, button=None, data=None):
        filename = dialog.get_filename(title=_("Select the package to import"),
                                       action=Gtk.FileChooserAction.OPEN,
                                       button=Gtk.STOCK_OPEN,
                                       default_dir=config.data.path.get('data'),
                                       filter='advene')
        if not filename:
            return True
        try:
            source = Package(uri=filename)
        except Exception as e:
            msg = "Cannot load %s file: %s" % (filename, str(e))
            logger.error(msg, exc_info=True)
            dialog.message_dialog(msg, icon=Gtk.MessageType.ERROR)
            return True
        self.open_adhoc_view('packageimporter', sourcepackage=source, destpackage=self.controller.package)
        return True

    @named_action(name="app.merge-template-package")
    def on_merge_template_package_activate(self, button=None, data=None):
        counter = self.controller.update_admin_views_from_template()
        message = _("Template package update - created %(new)d view(s), updated %(update_content)d view(s)") % counter
        logger.info(message)
        dialog.message_dialog(message)
        return True

    @named_action(name="app.save-workspace-as-view")
    def on_save_workspace_as_package_view1_activate (self, button=None, data=None):
        name=self.controller.package._idgenerator.get_id(View)+'_'+'workspace'

        d = dialog.title_id_dialog(title=_("Saving workspace"),
                                   element_title=name,
                                   element_id=name,
                                   text=_("Enter a view name to save the workspace"))
        d.default=Gtk.CheckButton(_("Default workspace"))
        d.default.set_tooltip_text(_("Open this workspace when opening the package"))
        d.vbox.pack_start(d.default, True, True, 0)
        d.show_all()
        dialog.center_on_mouse(d)

        title=None
        ident=None
        default=False

        res=d.run()
        if res == Gtk.ResponseType.OK:
            try:
                title=d.title_entry.get_text()
                ident=d.id_entry.get_text()
                default=d.default.get_active()
            except ValueError:
                pass
        d.destroy()

        if ident is None:
            return True

        if not re.match(r'^[a-zA-Z0-9_]+$', ident):
            dialog.message_dialog(_("Error: the identifier %s contains invalid characters.") % ident, icon=Gtk.MessageType.ERROR)
            return True

        v=helper.get_id(self.controller.package.views, ident)
        if v is None:
            create=True
            v=self.controller.package.createView(ident=ident, clazz='package')
            v.content.mimetype='application/x-advene-workspace-view'
        else:
            # Existing view. Check that it is already an workspace-view
            if v.content.mimetype != 'application/x-advene-workspace-view':
                dialog.message_dialog(_("Error: the view %s exists and is not a workspace view.") % ident, icon=Gtk.MessageType.ERROR)
                return True
            create=False
        v.title=title
        v.author=config.data.userid
        v.date=helper.get_timestamp()

        workspace=self.workspace_serialize()
        stream=io.StringIO()
        helper.indent(workspace)
        ET.ElementTree(workspace).write(stream, encoding='unicode')
        v.content.setData(stream.getvalue())
        stream.close()

        if default:
            self.controller.package.setMetaData (config.data.namespace, "default_adhoc", v.id)

        if create:
            self.controller.package.views.append(v)
            self.controller.notify("ViewCreate", view=v)
        else:
            self.controller.notify("ViewEditEnd", view=v)
        return True

    @named_action(name="app.save-workspace-as-default")
    def on_save_workspace_as_default1_activate (self, button=None, data=None):
        d=config.data.advenefile('defaults', 'settings')
        if not os.path.isdir(d):
            # Create it
            try:
                helper.recursive_mkdir(d)
            except OSError as e:
                self.controller.log(_("Cannot save default workspace: %s") % str(e))
                return True
        defaults=config.data.advenefile( ('defaults', 'workspace.xml'), 'settings')

        # Do not save package-specific arguments.
        root=self.workspace_serialize(with_arguments=False)
        stream=open(defaults, 'w', encoding='utf-8')
        helper.indent(root)
        ET.ElementTree(root).write(stream, encoding='unicode')
        stream.close()
        self.controller.log(_("Standard workspace has been saved"))
        return True

    @named_action(name="app.export-website")
    def on_website_export_activate(self, button=None, data=None):
        self.export_element(self.controller.package, filter_id='WebsiteExporter')
        return True

    @named_action(name="app.export")
    def on_export_activate (self, button=None, data=None):
        """Export a whole package.
        """
        self.export_element(self.controller.package)
        return True

    @named_action(name="app.update-screenshots")
    def update_annotation_screenshots(self, *p):
        """Update screenshot for annotations

        This requires that the player has the async-snapshot capability.
        """
        if 'async-snapshot' not in self.controller.player.player_capabilities:
            dialog.message_dialog(_("This video player is not able to grab specific screenshots"))
            return True
        missing = set(a.fragment.begin
                      for a in self.controller.package.annotations
                      if self.controller.get_snapshot(annotation=a).is_default)
        if missing:
            dialog.message_dialog(_("Updating %d snapshots") % len(missing), modal=False)
            logger.info("Updating %d missing snapshots: %s",
                        len(missing),
                        ", ".join(helper.format_time_reference(t) for t in sorted(missing)))
            for t in sorted(missing):
                self.controller.player.async_snapshot(t)
        else:
            dialog.message_dialog(_("No snapshot to update"), modal=False)
        return True

    # FIXME: this should be a stateful action
    @named_action(name="app.simplify-interface")
    def on_simplify_interface_activate(self, *p):
        if self.viewbook['east'].widget.get_visible():
            # Full state -> go into simplified state
            for v in list(self.viewbook.values()):
                v.widget.hide()
            self.gui.toolbar_container.hide()
            self.gui.stbv_combo.get_parent().hide()
        else:
            # Simplified state -> go into full state
            for v in list(self.viewbook.values()):
                v.widget.show()
            self.gui.toolbar_container.show()
            self.gui.stbv_combo.get_parent().show()
        return True

    @named_action(name="app.corpus-build")
    def on_corpus_build_activate (self, button=None, data=None):
        """Load multiple packages from a directory.
        """
        rootdir = dialog.get_dirname(title=_("Directory to recursively search for packages"))
        if rootdir:
            rootdir = Path(rootdir)
            packages = []
            for dirpath, dirnames, filenames in os.walk(rootdir):
                dirpath = Path(dirpath)
                packages += [ dirpath / filename
                              for filename in filenames
                              if Path(filename).suffix == '.azp' ]
            selection = dialog.list_selector(title=_("Select packages that are part of the corpus"),
                                             text=_(f"{len(packages)} packages found in {rootdir.name}.\nSelect those that must be included in the corpus."),
                                             members=[ (package, str(package), True)
                                                       for package in packages ],
                                             multiple=True)
            if selection:
                for filename in selection:
                    self.controller.load_package(uri=str(filename))
                answer = dialog.message_dialog(_(f"Loaded {len(selection)} packages.\nDo you want to save them as a corpus (.apl) file to load the whole corpus more easily (advised)?"), icon=Gtk.MessageType.QUESTION)
                if answer:
                    self.activate_action('app.corpus-save')

    @named_action(name="app.corpus-load")
    def on_corpus_load_activate (self, button=None, data=None):
        """Load a corpus
        """
        self.on_open1_activate(corpus=True)

    @named_action(name="app.corpus-update-template")
    def on_corpus_update_template_activate (self, button=None, data=None):
        """Updating template in loaded corpus packages

        Load structure and views from a template file, and update all loaded packages with it.
        """
        filenames = dialog.get_filename(title=_("Select the reference template"),
                                        action=Gtk.FileChooserAction.OPEN,
                                        button=Gtk.STOCK_OPEN,
                                        default_dir=config.data.path.get('resources'),
                                        multiple=True,
                                        filter='advene')
        if not filenames:
            return True

        if len(filenames) == 1:
            filename = filenames[0]
            # Single package - offer interface
            try:
                source = Package(uri=helper.path2uri(filename))
            except Exception as e:
                msg = "Cannot load %s file: %s" % (filename, str(e))
                self.log(msg)
                dialog.message_dialog(msg, icon=Gtk.MessageType.ERROR)
                return True

            self.open_adhoc_view('multimerger',
                                 sourcepackage=source,
                                 destpackages=self.controller.packages,
                                 parameters=({'display-result-dialog': True}, []))
            return True

    @named_action(name="app.corpus-save")
    def on_save_corpus_activate (self, button=None, data=None):
        """Save the current corpus (session file + individual packages)
        """
        default_dir = config.data.path.get('data')
        default_file = None
        corpus_uri = self.controller.corpus_uri
        if corpus_uri:
            default_file = helper.uri2path(corpus_uri)
            default_dir = os.path.dirname(default_file)

        filename = dialog.get_filename(title=_("Save the corpus in..."),
                                       action=Gtk.FileChooserAction.SAVE,
                                       button=Gtk.STOCK_SAVE,
                                       default_dir=default_dir,
                                       default_file=default_file,
                                       filter='session')
        if filename:
            (p, ext) = os.path.splitext(filename)
            if ext == '':
                # Add a pertinent extension
                filename = filename + '.apl'
            self.controller.save_session(filename, save_packages=True)
            self.log(_("Session saved in %s") % filename)
            self.update_gui()
        return True

    @named_action(name="app.corpus-export")
    def on_corpus_export_activate (self, button=None, data=None):
        """Export the current corpus as XLSX
        """
        # Build filename from the corpus filename (if available)
        filename = None
        if self.controller.corpus_uri:
            filename = helper.uri2path(self.controller.corpus_uri).replace('.apl', '.xlsx')
        self.export_element(self.controller.global_package, filter_id='CorpusXlsxExporter', filename=filename)
        return True

    @named_action(name="app.corpus-website-export")
    def on_corpus_website_export_activate (self, button=None, data=None):
        """Export the current corpus as a website
        """
        packages = [ p
                     for alias, p in self.controller.packages.items()
                     if alias != 'advene' ]
        destination = dialog.get_dirname(title=_("Select output directory for website export"))
        if not destination:
            return True
        output = corpus_website_export(self.controller, destination)
        logger.info(_(f"Corpus exported to {destination}"))
        message = _("Data exported to\n%s\nDo you want to open it?") % destination
        icon =  Gtk.MessageType.QUESTION
        # Try to open the file
        open_in_filebrowser(output)
        return True

    @named_action(name="app.corpus-statistics")
    def on_corpus_statistics_activate (self, button=None, data=None):
        """Stats on the corpus
        """
        self.open_adhoc_view('corpusstatistics')

    @named_action(name="app.corpus-annotations")
    def on_corpus_annotations_activate (self, button=None, data=None):
        """Display all corpus annotations
        """
        self.open_adhoc_view('table', source='global_annotations', label="Corpus annotations")

    @named_action(name="app.corpus_actions")
    def on_corpus_actions_activate (self, button=None, data=None):
        menu = advene.gui.popup.Menu(self.controller.global_package, controller=self.controller)
        menu.popup()
        return True

if __name__ == '__main__':
    app = AdveneApplication ()
    try:
        app.main(config.data.args)
    except Exception:
        e, v, tb = sys.exc_info()
        logger.error(config.data.version_string)
        logger.error("Got exception %s. Stopping services...", str(e))
        v.on_exit ()
        logger.error("*** Exception ***", exc_info=True)
