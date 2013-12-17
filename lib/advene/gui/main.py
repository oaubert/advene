#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2012 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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

This module defines the main GUI class, L{AdveneGUI}. It defines the
important methods and the various GUI callbacks (generally all methods
with the C{on_} prefix).
"""

import sys
import time
import os
import subprocess
import signal
import shutil
import tempfile
import StringIO
import textwrap
import re
import urllib2
import socket
import threading
import Queue

import advene.core.config as config
import advene.core.version

if config.data.os == 'win32':
    import win32process

import gtk
import gobject
import pango
import pprint

import gettext
import locale

print "Using localedir %s" % config.data.path['locale']

# Locale initialisation
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    print "Error in locale initialization. Interface translation may be incorrect."
    pass
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
import xml.etree.ElementTree as ET
from advene.util.odict import odict

import advene.util.importer
from advene.gui.util.completer import Indexer, Completer

# GUI elements
from advene.gui.util import get_pixmap_button, get_small_stock_button, image_from_position, dialog, encode_drop_parameters, overlay_svg_as_png, name2color, predefined_content_mimetypes
from advene.gui.util.playpausebutton import PlayPauseButton
import advene.gui.plugins.actions
import advene.gui.plugins.contenthandlers
import advene.gui.views.tree
from advene.gui.views import AdhocViewParametersParser
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
from advene.gui.edit.merge import Merger
from advene.gui.evaluator import Evaluator
from advene.gui.views.accumulatorpopup import AccumulatorPopup
import advene.gui.edit.imports
import advene.gui.edit.properties
import advene.gui.edit.montage
from advene.gui.edit.timeadjustment import TimeAdjustment
from advene.gui.edit.frameselector import FrameSelector
from advene.gui.views.viewbook import ViewBook
from advene.gui.views.html import HTMLView
from advene.gui.views.scroller import ScrollerView
from advene.gui.views.caption import CaptionView

class DummyGlade:
    """Transition class.
    """
    def __init__(self, menu_definition):
        """Main window definition.
        """
        self.win=gtk.Window()

        v=gtk.VBox()
        self.win.add(v)

        self.menubar=gtk.MenuBar()
        self.build_menubar(menu_definition, self.menubar)
        v.pack_start(self.menubar, expand=False)

        self.toolbar_container=gtk.HBox()

        self.fileop_toolbar=gtk.Toolbar()
        self.fileop_toolbar.set_style(gtk.TOOLBAR_ICONS)
        self.fileop_toolbar.set_show_arrow(False)
        self.toolbar_container.pack_start(self.fileop_toolbar, expand=True)

        self.adhoc_hbox=gtk.HBox()
        self.toolbar_container.pack_start(self.adhoc_hbox, expand=True)

        self.traces_switch=gtk.HBox()
        self.toolbar_container.pack_start(self.traces_switch, expand=False)

        self.search_hbox=gtk.HBox()
        self.toolbar_container.pack_start(self.search_hbox, expand=False)
        v.pack_start(self.toolbar_container, expand=False)

        self.application_space = gtk.VBox()
        v.add(self.application_space)

        self.bottombar = gtk.HBox()

        self.statusbar = gtk.Statusbar()

        # Modify font size. First find the embedded label
        w=self.statusbar
        while hasattr(w, 'get_children'):
            w=w.get_children()[0]
        w.modify_font(pango.FontDescription("sans 9"))

        self.statusbar.set_has_resize_grip(False)
        self.bottombar.pack_start(self.statusbar, expand=True)
        v.pack_start(self.bottombar, expand=False)

        self.win.show_all()

    def build_menubar(self, items, menu=None):
        """Populate the menu with data taken from items.
        """
        if menu is None:
            menu=gtk.Menu()
        for (name, action, tooltip) in items:
            if name.startswith('gtk-'):
                i=gtk.ImageMenuItem(stock_id=name)
            elif not name:
                i=gtk.SeparatorMenuItem()
            else:
                i=gtk.MenuItem(name)
            if isinstance(action, tuple):
                # There is a submenu
                m=self.build_menubar(action)
                i.set_submenu(m)
            elif action is not None:
                i.connect('activate', action)
            if tooltip:
                i.set_tooltip_text(tooltip)

            # Menu-specific customizations
            if name == _("_Select player"):
                self.select_player_menuitem=i
            elif name == _("_View"):
                self.adhoc_view_menuitem=i
            elif name == _("Packages"):
                self.package_list_menu=gtk.Menu()
                i.set_submenu(self.package_list_menu)
            elif name == _("Open recent"):
                self.recent_menuitem = i
            menu.append(i)
        return menu

class AdveneGUI(object):
    """Main GUI class.

    Some entry points in the methods:
      - L{__init__} and L{main} : GUI initialization
      - L{update_display} : method regularly called to refresh the display
      - L{on_win_key_press_event} : key press handling

    @ivar gui: the GUI model from libglade
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
    def __init__ (self):
        """Initializes the GUI and other attributes.
        """
        self.logbuffer = gtk.TextBuffer()
        self.busy_cursor = gtk.gdk.Cursor(gtk.gdk.WATCH)

        self.controller = advene.core.controller.AdveneController()
        self.controller.register_gui(self)
        # The KeyboardInput event has a 'keyname' parameter ("F1" to "F12")
        # available through the request/keyname TALES expression
        self.controller.register_event('KeyboardInput', _("Input from the keyboard (function keys)"))

        # FIXME: we should use gtk.UIManager
        menu_definition=(
            (_("_File"), (
                    ( _("_New package"), self.on_new1_activate, _("Create a new package")),
                    ( _("_Open package"), self.on_open1_activate, _("Open a package") ),
                    ( _("Open recent"), None, _("Show recently opened packages") ),
                    ( _("_Save package") + " [Ctrl-S]", self.on_save1_activate, _("Save the package") ),
                    ( _("Save package as..."), self.on_save_as1_activate, _("Save the package as...") ),
                    ( _("Close package"), self.on_close1_activate, _("Close the package") ),
                    ( "", None, "" ),
                    ( _("Save session"), self.on_save_session1_activate, _("Save the current session (list of opened packages)") ),
                    ( _("Save workspace"), (
                            ( _("...as package view"), self.on_save_workspace_as_package_view1_activate, "" ),
                            ( _("...as standard workspace"), self.on_save_workspace_as_default1_activate, _("Use the current layout as standard workspace in the future") )), ""),
                    ( "", None, "" ),
                    ( _("Associate a video _File"), self.on_b_addfile_clicked, _("Associate a video file") ),
                    ( _("Associate a _DVD"), self.on_b_selectdvd_clicked, _("Associate a chapter from a DVD") ),
                    ( _("Associate a _Video stream"), self.on_select_a_video_stream1_activate, _("Enter a video stream address") ),
                    ( "", None, "" ),
                    ( _("_Import File"), self.on_import_file1_activate, _("Import data from an external source") ),
                    ( _("_Process video"), self.on_process_video_activate, _("Import data from video processing algorithms")),
                    ( "", None, "" ),
                    ( _("Merge package"), self.on_merge_package_activate, _("Merge elements from another package") ),
                    ( _("Import _DVD chapters"), self.on_import_dvd_chapters1_activate, _("Create annotations based on DVD chapters") ),
                    ( "", None, "" ),
                    ( _("_Export..."), self.on_export_activate, _("Export data to another format") ),
                    ( _("_Website export..."), self.on_website_export_activate, _("Export views to a website") ),
                    ( "", None, "" ),
                    ( _("_Quit"), self.on_exit, "" ),
                    ), "" ),
            (_("_Edit"), (
                    ( _("_Undo") + " [Ctrl-Z]", self.undo, "" ),
                    ( _("_Find"), self.on_find1_activate, "" ),
                    ( _("_Delete") + " [Del]", self.on_delete1_activate, "" ),
                    ( _("Create"), (
                            ( _("Schema"), self.on_create_schema_activate, "" ),
                            ( _("View"), self.on_create_view_activate, "" ),
                            ( _("Query"), self.on_create_query_activate, "" ),
                            ( _("Annotation Type"), self.on_create_annotation_type_activate, "" ),
                            ( _("Relation Type"), self.on_create_relation_type_activate, "" ),
                            ), "" ),
#                    ( _("Package _Imports"), self.on_package_imports1_activate, _("Edit imported element from other packages") ),
#                    ( _("_Standard Ruleset"), self.on_edit_ruleset1_activate, _("Edit the standard rules") ),
                    ( _("P_ackage properties"), self.on_package_properties1_activate, _("Edit package properties") ),
                    ( _("P_references"), self.on_preferences1_activate, _("Interface preferences") ),
                    ), "" ),
            (_("_View"), (
                    # Note: this will be populated from registered_adhoc_views
                    ( _("_Start Web Browser"), self.on_adhoc_web_browser_activate, _("Start the web browser") ),
                    ( "", None, "" ),
                    ( _("Simplify interface"), self.on_simplify_interface_activate, _("Simplify the application interface (toggle)")),
                    ( _("Evaluator") + " [Ctrl-e]", self.on_evaluator2_activate, _("Open python evaluator window") ),
                    ( _("Webserver log"), self.on_webserver_log1_activate, "" ),
                    #( _("_MediaInformation"), self.on_view_mediainformation_activate, _("Display information about the media") ),
                    ), "" ),
            (_("_Player"), (
                    ( _("Go to _Time"), self.goto_time_dialog, _("Goto a specified time code") ),
                    ( _("Save _ImageCache"), self.on_save_imagecache1_activate, _("Save the contents of the ImageCache to disk") ),
                    ( _("Reset ImageCache"), self.on_reset_imagecache_activate, _("Reset the ImageCache") ),
                    ( _("_Restart player"), self.on_restart_player1_activate, _("Restart the player") ),
                    #( _("Capture screenshots"), self.generate_screenshots, _("Generate screenshots for the current video") ),
                    ( _("Update annotation screenshots"), self.update_annotation_screenshots, _("Update screenshots for annotation bounds") ),
                    ( _("Detect shots"), self.on_shotdetect_activate, _("Automatically detect shots")),
                    ( _("_Select player"), None, _("Select the player plugin") ),
                    ), "" ),
            (_("Packages"), (
                    ( _("No package"), None, "" ),
                    ), "" ),
            (_("_Help"), (
                    ( _("Help"), self.on_help1_activate, "" ),
                    ( _("Get support"), self.on_support1_activate, "" ),
                    ( _("Check for updates"), self.check_for_update, "" ),
                    ( _("Display shortcuts"), self.on_helpshortcuts_activate, "" ),
                    ( _("Display logfile"), self.on_advene_log_display, _("Display log file")),
                    ( _("Open logfile folder"), self.on_advene_log_folder_display, _("Display logfile folder. It can help when sending the advene.log file by e-mail.")),
                    ( _("_About"), self.on_about1_activate, "" ),
                    ), "" ),
            )

        self.gui = DummyGlade(menu_definition)

        f = gtk.RecentFilter()
        f.add_application(gobject.get_application_name())
        recent = gtk.RecentChooserMenu()
        recent.add_filter(f)
        recent.set_show_icons(False)
        recent.set_sort_type(gtk.RECENT_SORT_MRU)
        self.gui.recent_menuitem.set_submenu(recent)
        def open_history_file(rec):
            fname = rec.get_current_uri()
            try:
                self.set_busy_cursor(True)
                self.controller.load_package (uri=fname)
            except (OSError, IOError), e:
                self.set_busy_cursor(False)
                dialog.message_dialog(_("Cannot load package %(filename)s:\n%(error)s") % {
                        'filename': fname,
                        'error': unicode(e)}, gtk.MESSAGE_ERROR)
            return True
        recent.connect('item-activated', open_history_file)

        self.toolbuttons = {}
        for (ident, stock, callback, tip) in (
            ('open', gtk.STOCK_OPEN, self.on_open1_activate, _("Open a package file")),
            ('save', gtk.STOCK_SAVE, self.on_save1_activate, _("Save the current package")),
            ('save_as', gtk.STOCK_SAVE_AS, self.on_save_as1_activate, _("Save the package with a new name")),
            ('select_file', 'moviefile.png', self.on_b_addfile_clicked, _("Select movie file...")),
            ('select_dvd', gtk.STOCK_CDROM, self.on_b_selectdvd_clicked, _("Select DVD")),
            (None, None, None, None),
            ('undo', gtk.STOCK_UNDO, self.undo, _("Undo")),
            (None, None, None, None),
            ('create_text_annotation', 'text_annotation.png', self.on_create_text_annotation, _("Create a text annotation")),
            ('create_svg_annotation', 'svg_annotation.png', self.on_create_svg_annotation, _("Create a graphical annotation")),
           ):
            if stock is None:
                b = gtk.SeparatorToolItem()
            elif ident == 'open':
                b = gtk.MenuToolButton(stock)
                b.set_arrow_tooltip_text(_("List recently opened packages"))
                f = gtk.RecentFilter()
                f.add_application(gobject.get_application_name())
                recent = gtk.RecentChooserMenu()
                recent.add_filter(f)
                recent.set_show_icons(False)
                recent.set_sort_type(gtk.RECENT_SORT_MRU)
                b.set_menu(recent)
                recent.connect('item-activated', open_history_file)
            elif stock.startswith('gtk-'):
                b = gtk.ToolButton(stock)
            else:
                i = gtk.Image()
                i.set_from_file( config.data.advenefile( ('pixmaps', stock ) ) )
                b = gtk.ToolButton(icon_widget=i)
            if tip is not None:
                b.set_tooltip_text(tip)
            if callback is not None:
                b.connect('clicked', callback)
            self.gui.fileop_toolbar.insert(b, -1)
            if ident is not None:
                self.toolbuttons[ident] = b
        self.gui.fileop_toolbar.show_all()

        # Snapshotter activity monitor
        def display_snapshot_monitor_menu(v):
            s = getattr(self.controller.player, 'snapshotter', None)

            m = gtk.Menu()
            if s:
                m.append(gtk.MenuItem(_("Snapshotter activity")))
                m.append(gtk.SeparatorMenuItem())
                m.append(gtk.MenuItem(_("%d queued requests") % s.timestamp_queue.qsize()))
                i = gtk.MenuItem(_("Cancel all requests"))
                i.connect('activate', lambda i: s.clear() or True)
                m.append(i)

            else:
                m.append(gtk.MenuItem(_("No snapshotter")))
            m.show_all()
            m.popup(None, None, None, 0, gtk.get_current_event_time())
            return True

        self.snapshotter_image = {
            'idle': gtk.image_new_from_file( config.data.advenefile( ( 'pixmaps', 'snapshotter-idle.png') )),
            'running': gtk.image_new_from_file( config.data.advenefile( ( 'pixmaps', 'snapshotter-running.png') )),
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
        b.set_relief(gtk.RELIEF_NONE)
        self.gui.bottombar.pack_start(b, expand=False)
        self.snapshotter_monitor_icon = b
        b.set_state=set_state.__get__(b)

        # Log messages button
        def display_log_messages(v):
            v=self.open_adhoc_view('logmessages', destination='south')
            v.autoscroll()
            return True
        b=get_pixmap_button('logmessages.png', display_log_messages)
        b.set_tooltip_text(_("Display application log messages"))
        b.set_relief(gtk.RELIEF_NONE)
        self.gui.bottombar.pack_start(b, expand=False)
        b.show()

        # Resize the main window
        window=self.gui.win
        window.connect('key-press-event', self.on_win_key_press_event)
        window.connect('destroy', self.on_exit)
        self.init_window_size(window, 'main')
        window.set_icon_list(*self.get_icon_list())

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
                l=self.controller.load_plugins(os.path.join(
                        os.path.dirname(advene.__file__), 'gui', n),
                                               prefix="advene_gui_%s" % n)
                self.gui_plugins.extend(l)
            except OSError:
                print "OSerror"
                pass

        def update_quicksearch_sources(mi):
            """Display a dialog allowing to edit quicksearch-sources setting.
            """
            d = gtk.Dialog(title=_("Quicksearch lists"),
                   parent=None,
                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                   buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK,
                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

            d.vbox.pack_start(gtk.Label(_("Please specify the lists of elements to be searched.")), expand=False)
            for el in self.controller.defined_quicksearch_sources:
                b=gtk.CheckButton(el.title, use_underline=False)
                b._element = el
                b.set_active(el.value in config.data.preferences['quicksearch-sources'])
                d.vbox.pack_start(b, expand=False)
            d.vbox.show_all()
            d.connect('key-press-event', dialog.dialog_keypressed_cb)
            d.show()
            dialog.center_on_mouse(d)
            res=d.run()
            if res == gtk.RESPONSE_OK:
                # Update quicksearch-sources
                elements=[ b._element
                           for b in d.vbox.get_children()
                           if hasattr(b, 'get_active') and b.get_active() ]
                config.data.preferences['quicksearch-sources']=[ el.value for el in elements ]
                # Update tooltip
                label="\n".join( el.title for el in elements )
                self.quicksearch_button.set_tooltip_text(_("Searching on %s.\nLeft click to launch the search, right-click to set the quicksearch options") % label)
                self.quicksearch_entry.set_tooltip_text(_('String to search in %s') % label)
            d.destroy()
            return True

        # Trace switch button
        tsb = self.gui.traces_switch
        b=gtk.Button()

        def trace_toggle(w):
            i=gtk.Image()
            if config.data.preferences['record-actions']:
                config.data.preferences['record-actions']=False
                i.set_from_file(config.data.advenefile( ( 'pixmaps', 'traces_off.png') ))
                w.set_tooltip_text(_('Tracing : ') + _('off'))
            else:
                config.data.preferences['record-actions']=True
                i.set_from_file(config.data.advenefile( ( 'pixmaps', 'traces_on.png') ))
                w.set_tooltip_text(_('Tracing : ') + _('on'))
            w.set_image(i)
            return
        # Invert the preference, so that calling the trace_toggle
        # will correctly update the button as well as the setting.
        config.data.preferences['record-actions']=not config.data.preferences['record-actions']
        trace_toggle(b)
        b.connect('clicked', trace_toggle)
        tsb.pack_start(b, expand=False)
        tsb.show_all()
        self.quicksearch_button=get_small_stock_button(gtk.STOCK_FIND)
        self.quicksearch_entry=gtk.Entry()
        self.quicksearch_entry.set_tooltip_text(_('String to search'))

        def quicksearch_options(button, event):
            """Generate the quicksearch options menu.
            """
            if event.type != gtk.gdk.BUTTON_PRESS:
                return False
            menu=gtk.Menu()
            item=gtk.MenuItem(_("Launch search"))
            item.connect('activate', self.do_quicksearch)
            if not self.quicksearch_entry.get_text():
                item.set_sensitive(False)
            menu.append(item)
            item=gtk.CheckMenuItem(_("Ignore case"))
            item.set_active(config.data.preferences['quicksearch-ignore-case'])
            item.connect('toggled', lambda i: config.data.preferences.__setitem__('quicksearch-ignore-case', i.get_active()))
            menu.append(item)

            item=gtk.MenuItem(_("Searched elements"))
            item.connect('activate', update_quicksearch_sources)
            menu.append(item)

            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True

        hb=self.gui.search_hbox
        self.quicksearch_entry.connect('activate', self.do_quicksearch)
        hb.pack_start(self.quicksearch_entry, expand=False)
        self.quicksearch_button.connect('button-press-event', quicksearch_options)
        hb.pack_start(self.quicksearch_button, expand=False, fill=False)
        hb.show_all()

        # Player status
        p=self.controller.player
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

        # Text abbreviations
        self.text_abbreviations =  dict( l.split(" ", 1) for l in config.data.preferences['text-abbreviations'].splitlines() )

        # Populate default STBV and type lists
        self.update_gui()

    def init_gettext(self):
        """Proxy for the module-level init_gettext method.
        """
        config.init_gettext()

    def get_icon_list(self):
        """Return the list of icon pixbuf appropriate for Window.set_icon_list.
        """
        if not hasattr(self, '_icon_list'):
            l=[ gtk.gdk.pixbuf_new_from_file(config.data.advenefile(
                        ( 'pixmaps', 'icon_advene%d.png' % size ) ))
                              for size in (16, 32, 48, 64, 128) ]
            self._icon_list=[ i for i in l if i is not None ]
        return self._icon_list

    def set_busy_cursor(self, busy=False):
        """Un/Set the busy cursor for the main window.
        """
        self.gui.win.window.set_cursor(self.busy_cursor if busy else None)

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
                v.update_annotation(annotation=annotation, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('EditEnd') or event.endswith('Create'):
            # Update the type fieldnames
            if annotation.content.mimetype.endswith('/x-advene-structured'):
                annotation.type._fieldnames.update(helper.common_fieldnames([ annotation ]))

        # Refresh the edit popup for the associated relations
        for e in [ e for e in self.edit_popups if e.element in annotation.relations ]:
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
                v.update_relation(relation=relation, event=event)
            except AttributeError:
                pass
        # Refresh the edit popup for the members
        for e in [ e for e in self.edit_popups if e.element in relation.members ]:
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
                v.update_view(view=view, event=event)
            except AttributeError:
                pass

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
                v.update_query(query=query, event=event)
            except AttributeError:
                pass
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
                v.update_resource(resource=resource, event=event)
            except AttributeError:
                pass
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
                v.update_schema(schema=schema, event=event)
            except AttributeError:
                pass
        return True

    def annotationtype_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        at=context.evaluateValue('annotationtype')
        event=context.evaluateValue('event')
        if at.ownerPackage != self.controller.package:
            return True

        self.updated_element(event, at)
        for v in self.adhoc_views:
            try:
                v.update_annotationtype(annotationtype=at, event=event)
            except AttributeError:
                pass
        # Update the current type menu
        self.update_gui()
        # Update the content indexer
        if event.endswith('Create'):
            self.controller.package._indexer.element_update(at)
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
                v.update_relationtype(relationtype=rt, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('Create'):
            self.controller.package._indexer.element_update(rt)

        return True

    def updated_element(self, event, element):
        if event.endswith('EditEnd'):
            # Update the content indexer
            self.controller.package._indexer.element_update(element)

            l=self.last_edited
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == element ]:
                e.refresh()
        elif event.endswith('Create'):
            # Update the content indexer
            self.controller.package._indexer.element_update(element)
            l=self.last_created
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
        s=config.data.preferences['edition-history-size']
        if element in l:
            l.remove(element)
        l.append(element)
        if len(l) > s:
            l.pop(0)
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

    def goto_time_dialog(self, *p):
        """Display a dialog to go to a given time.
        """
        t = self.input_time_dialog()
        if t is not None:
            self.controller.update_status ("set", self.controller.create_position(t))
        return True

    def input_time_dialog(self, *p):
        """Display a dialog to enter a time value.
        """
        d = gtk.Dialog(title=_("Enter the new time value"),
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

        ta=TimeAdjustment(value=self.gui.slider.get_value(), controller=self.controller, videosync=False, editable=True, compact=False)
        ta.entry.connect("activate", lambda w: d.response(gtk.RESPONSE_OK))
        d.vbox.pack_start(ta.widget, expand=False)
        d.show_all()
        dialog.center_on_mouse(d)
        ta.entry.select_region(0, -1)
        ta.entry.grab_focus()
        res=d.run()
        retval=None
        if res == gtk.RESPONSE_OK:
            retval = ta.get_value()
        d.destroy()
        return retval

    def search_replace_dialog(self, elements, title=None, default_search=None):
        """Display a search-replace dialog.
        """
        if title is None:
            title = _("Replace content in %d elements") % len(elements)
        d = gtk.Dialog(title=title,
                       parent=None,
                       flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 ))
        l=gtk.Label(title)
        l.set_line_wrap(True)
        l.show()
        d.vbox.pack_start(l, expand=False)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Find word") + " "), expand=False)
        search_entry=gtk.Entry()
        search_entry.set_text(default_search or "")
        hb.pack_start(search_entry, expand=False)
        d.vbox.pack_start(hb, expand=False)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Replace by") + " "), expand=False)
        replace_entry=gtk.Entry()
        hb.pack_start(replace_entry, expand=False)
        d.vbox.pack_start(hb, expand=False)

        d.connect('key-press-event', dialog.dialog_keypressed_cb)
        d.show_all()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == gtk.RESPONSE_OK:
            search=unicode(search_entry.get_text()).replace('\\n', '\n').replace('%n', '\n').replace('\\t', '\t').replace('%t', '\t')
            replace=unicode(replace_entry.get_text()).replace('\\n', '\n').replace('%n', '\n').replace('\\t', '\t').replace('%t', '\t')
            count=0
            batch_id=object()
            for a in elements:
                if not isinstance(a, (Annotation, Relation, View)):
                    continue
                if search in a.content.data:
                    self.controller.notify('EditSessionStart', element=a, immediate=True)
                    a.content.data = a.content.data.replace(search, replace)
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
        if title is None:
            title = _("Video export")
        if label is None:
            label = _("Exporting video montage/fragment to %%(filename)s")

        filename = dialog.get_filename(title=_("Please choose a destination filename"),
                                       action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                       button=gtk.STOCK_SAVE,
                                       default_file = basename,
                                       filter='video')
        if filename is None:
            return
        m = MontageRenderer(self.controller, elements)

        w = gtk.Window()
        w.set_title(title)
        v = gtk.VBox()
        l = gtk.Label(label % { 'filename': filename } )
        v.add(l)

        pg = gtk.ProgressBar()
        v.pack_start(pg, expand=False)

        hb = gtk.HButtonBox()
        b = gtk.Button(stock=gtk.STOCK_CLOSE)
        def close_encoder(b):
            m.finalize()
            w.destroy()
            return True
        b.connect('clicked', close_encoder)
        hb.pack_start(b, expand=False)
        v.pack_start(hb, expand=False)

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

    def main (self, args=None):
        """Mainloop : Gtk mainloop setup.

        @param args: list of arguments
        @type args: list
        """
        if args is None:
            args=[]
        try:
            gtk.gdk.threads_init ()
        except RuntimeError:
            print "*** WARNING*** : gtk.threads_init not available.\nThis may lead to unexpected behaviour."
        # FIXME: We have to register LogWindow actions before we load the ruleset
        # but we should have an introspection method to do this automatically
        self.logwindow=advene.gui.views.logwindow.LogWindow(controller=self.controller)
        self.register_view(self.logwindow)

        self.visualisationwidget=self.get_visualisation_widget()
        self.gui.application_space.add(self.visualisationwidget)

        def media_changed(context, parameters):
            if config.data.preferences['player-autostart'] and not 'record' in self.controller.player.player_capabilities:
                self.controller.queue_action(self.controller.update_status, "start")
                self.controller.queue_action(self.controller.update_status, "pause")

            if config.data.preferences['expert-mode']:
                return True
            uri=context.globals['uri']
            if not uri:
                msg=_("No media association is defined in the package. Please use the 'File/Associate a video file' menu item to associate a media file.")
            elif not os.path.exists(unicode(uri).encode(sys.getfilesystemencoding(), 'ignore')) and not uri.startswith('http:') and not uri.startswith('dvd'):
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
            ("PlayerSet", self.updated_position_cb),
            ("PlayerStop", self.player_stop_cb),
            ("PlayerChange", self.updated_player_cb),
            ("ViewActivation", self.on_view_activation),
            ( [ '%sDelete' % v for v in ('Annotation', 'Relation', 'View',
                                         'AnnotationType', 'RelationType', 'Schema',
                                         'Resource') ],
              self.handle_element_delete),
            ('MediaChange', media_changed),
            ):
            if isinstance(events, basestring):
                self.controller.event_handler.internal_rule (event=events,
                                                             method=method)
            else:
                for e in events:
                    self.controller.event_handler.internal_rule (event=e,
                                                                 method=method)

        self.controller.init(args)

        self.visual_id = None

        def build_player_menu(menu):
            if menu.get_children():
                # The menu was previously populated, but the player may have changed.
                # Clear it to update it.
                menu.foreach(menu.remove)

            # Populate the "Select player" menu
            for ident, p in config.data.players.iteritems():
                def select_player(i, p):
                    self.controller.select_player(p)
                    return True
                if self.controller.player.player_id == ident:
                    ident="> %s" % ident
                else:
                    ident="   %s" % ident
                i=gtk.MenuItem(ident)
                i.connect('activate', select_player, p)
                menu.append(i)
                i.show()
            return True

        # Adhoc view toolbuttons signal handling
        def adhoc_view_drag_sent(widget, context, selection, targetType, eventTime, name):
            if targetType == config.data.target_type['adhoc-view']:
                selection.set(selection.target, 8, encode_drop_parameters(name=name))
                return True
            return False

        def adhoc_view_drag_begin(widget, context, pixmap, view_name):
            w=gtk.Window(gtk.WINDOW_POPUP)
            w.set_decorated(False)
            hb=gtk.HBox()
            i=gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            hb.pack_start(i, expand=False)
            hb.pack_start(gtk.Label(view_name), expand=False)
            w.add(hb)
            w.show_all()
            context.set_icon_widget(w, 16, 16)
            return True

        def open_view(widget, name, destination='default'):
            self.open_adhoc_view(name, destination=destination)
            return True

        def open_view_menu(widget, name):
            """Open the view menu.

            In expert mode, directly open the view. Else, display a
            popup menu proposing the various places where the view can
            be opened.
            """
            if name == 'webbrowser':
                open_view(widget, name)
                return True

            if config.data.preferences['expert-mode']:
                # In expert mode, directly open the view. Experts know
                # how to use drag and drop anyway.
                open_view(widget, name)
                return True

            menu=gtk.Menu()

            for (label, destination) in (
                (_("Open this view..."), 'default'),
                (_("...in its own window"), 'popup'),
                (_("...embedded east of the video"), 'east'),
                (_("...embedded west of the video"), 'west'),
                (_("...embedded south of the video"), 'south'),
                (_("...embedded at the right of the window"), 'fareast')):
                item = gtk.MenuItem(label)
                item.connect('activate', open_view, name, destination)
                menu.append(item)

            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())

            return True

        # Populate the View submenu
        menu = self.gui.adhoc_view_menuitem.get_submenu()
        it = gtk.MenuItem(_("_All available views"))
        menu.prepend(it)
        it.show()
        m = gtk.Menu()
        it.set_submenu(m)
        for name in sorted(self.registered_adhoc_views, reverse=True):
            cl=self.registered_adhoc_views[name]
            it=gtk.MenuItem('_' + cl.view_name, use_underline=True)
            it.set_tooltip_text(cl.tooltip)
            it.connect('activate', open_view_menu, name)
            m.prepend(it)

        # Generate the adhoc view buttons
        hb=self.gui.adhoc_hbox
        item_index = 0
        for name, tip, pixmap in (
            ('timeline', _('Timeline'), 'timeline.png'),
            ('tree', _('Tree view'), 'treeview.png'),
            ('finder', _('Package finder'), 'finder.png'),
            ('transcription', _('Transcription of annotations'), 'transcription.png'),

            ('', '', ''),
            ('transcribe', _('Note-taking editor'), 'transcribe.png'),
            ('activebookmarks', _('Active bookmarks'), 'bookmarks.png'),
            ('schemaeditor', _("Schema editor"), 'schemaeditor.png'),
            ('', '', ''),

            ('tagbag', _("Bag of tags"), 'tagbag.png'),
            ('browser', _('TALES explorer'), 'browser.png'),
            ('montage', _("Dynamic montage"), 'montage.png'),
            ('videoplayer', _("Video player"), 'videoplayer.png'),
            ('', '', ''),

            ('webbrowser', _('Open a comment view in the web browser'), 'web.png'),
            ('comment', _("Create or open a comment view"), 'comment.png'),
            ('', '', ''),

            ('editaccumulator', _('Edit window placeholder (annotation and relation edit windows will be put here)'), 'editaccumulator.png'),
            ('editionhistory', _("Display edition history"), 'editionhistory.png'),
            ('tracepreview', _("Visualise the activity trace preview"), 'trace.png'),
            ('tracetimeline', _("Visualise the activity trace as a timeline"), 'tracetimeline.png'),
            ):
            if not name:
                # Separator
                b=gtk.VSeparator()
                hb.pack_start(b, expand=False, padding=5)

                it = gtk.SeparatorMenuItem()
                menu.insert(it, item_index)
                item_index = item_index + 1
                continue
            if name in ('browser', 'schemaeditor') and not config.data.preferences['expert-mode']:
                continue
            if name not in ('webbrowser', 'comment') and not name in self.registered_adhoc_views:
                self.log("Missing basic adhoc view %s" % name)
                continue
            b=gtk.Button()
            i=gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            b.add(i)
            b.set_tooltip_text(tip)
            b.connect('drag-begin', adhoc_view_drag_begin, pixmap, tip)
            b.connect('drag-data-get', adhoc_view_drag_sent, name)
            b.connect('clicked', open_view_menu, name)
            b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)
            hb.pack_start(b, expand=False)
            if name == 'webbrowser' and (self.controller.server is None or not self.controller.server.is_running()):
                b.set_sensitive(False)
                b.set_tooltip_text(_("The webserver could not be started. Static views cannot be accessed."))
            if name in self.registered_adhoc_views:
                it = gtk.MenuItem(self.registered_adhoc_views[name].view_name, use_underline=False)
                it.connect('activate', open_view_menu, name)
                it.set_tooltip_text(tip)
                menu.insert(it, item_index)
                item_index = item_index + 1
        hb.show_all()
        menu.show_all()

        menu=gtk.Menu()
        self.gui.select_player_menuitem.set_submenu(menu)
        menu.connect('map', build_player_menu)

        defaults=config.data.advenefile( ('defaults', 'workspace.xml'), 'settings')
        if os.path.exists(defaults):
            # a default workspace has been saved. Load it and
            # ignore the default adhoc view specification.
            stream=open(defaults)
            tree=ET.parse(stream)
            stream.close()
            self.workspace_restore(tree.getroot())
        else:
            # Open default views
            self.open_adhoc_view('timeline', destination='south')
            self.open_adhoc_view('tree', destination='fareast')

        # If there were unknown arguments, propose to import them
        for uri in self.controller.unknown_args:
            self.open_adhoc_view('importerview', filename=uri)

        # Use small toolbar button everywhere
        gtk.settings_get_default().set_property('gtk_toolbar_icon_size', gtk.ICON_SIZE_SMALL_TOOLBAR)
        play=self.player_toolbar.get_children()[0]
        play.set_flags(play.flags() | gtk.CAN_FOCUS)
        play.grab_focus()
        self.update_control_toolbar(self.player_toolbar)

        self.event_source_update_display=gobject.timeout_add (100, self.update_display)
        self.event_source_slow_update_display=gobject.timeout_add (1000, self.slow_update_display)
        # Do we need to make an update check
        if (config.data.preferences['update-check']
            and time.time() - config.data.preferences['last-update'] >= 7 * 24 * 60 * 60):
            config.data.preferences['last-update']=time.time()
            self.check_for_update()
        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        if config.data.debug:
            self.controller._state=self.controller.event_handler.dump()
        gtk.gdk.threads_enter()
        gtk.main ()
        gtk.gdk.threads_leave()
        self.controller.notify ("ApplicationEnd")

    def check_for_update(self, *p):
        timeout=socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(1)
            u=urllib2.urlopen('http://liris.cnrs.fr/advene/version.txt')
        except Exception, e:
            socket.setdefaulttimeout(timeout)
            return
        socket.setdefaulttimeout(timeout)
        try:
            data=u.read()
        except:
            data=""
        u.close()
        if not data:
            return False
        info=dict( [ l.split(':') for l in data.splitlines() ] )
        major, minor = info['version'].split('.')
        major=int(major)
        minor=int(minor)
        info['current']=advene.core.version.version
        if (1000 * major + minor) > (1000 * advene.core.version.major + advene.core.version.minor):
            # An update is available.
            v=gtk.VBox()
            msg=textwrap.fill(_("""<span background="#ff8888" size="large"><b>Advene %(version)s has been released</b> on %(date)s, but you are running version %(current)s.\nYou can download the latest version from the Advene website: http://liris.cnrs.fr/advene/</span>""") % info, 55)
            l=gtk.Label()
            l.set_markup(msg)
            #l.set_line_wrap_mode(True)
            v.add(l)
            b=gtk.Button(_("Go to the website"))
            def open_site(b):
                self.controller.open_url('http://liris.cnrs.fr/advene/download.html')
                return True
            b.connect('clicked', open_site)
            v.pack_start(b, expand=False)
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
            c=self.controller.build_context(here=element)
            colname=c.evaluateValue(element.getMetaData(config.data.namespace, 'color'))
            gtk_color=name2color(colname)
        except:
            gtk_color=None
        d=gtk.ColorSelectionDialog(_("Choose a color"))
        if gtk_color:
            d.colorsel.set_current_color(gtk_color)
        res=d.run()
        if res == gtk.RESPONSE_OK:
            col=d.colorsel.get_current_color()
            element.setMetaData(config.data.namespace, 'color', u"string:#%04x%04x%04x" % (col.red,
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
            col=None
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

        # Video player socket
        self.drawable=gtk.Socket()

        def handle_remove(socket):
            # Do not kill the widget if the application exits
            return True
        self.drawable.connect('plug-removed', handle_remove)

        def register_drawable(drawable):
            # The player is initialized. We can register the drawable id
            try:
                if not config.data.player['embedded']:
                    raise Exception()
                try:
                    self.controller.player.set_widget(self.drawable)
                except AttributeError:
                    self.visual_id = self.drawable.get_id()
                    self.controller.player.set_visual(self.visual_id)
            except Exception, e:
                self.log("Cannot set visual: %s" % unicode(e))
            return True
        self.drawable.connect_after('realize', register_drawable)

        black=gtk.gdk.Color(0, 0, 0)
        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            self.drawable.modify_bg (state, black)

        self.drawable.set_size_request(320, 200)
        self.drawable.add_events(gtk.gdk.BUTTON_PRESS)
        self.drawable.connect_object('button-press-event', self.debug_cb, self.drawable)

        self.player_toolbar = self.get_player_control_toolbar()
        self.playpause_button = self.player_toolbar.buttons['playpause']

        # Dynamic view selection
        hb=gtk.HBox()
        #hb.pack_start(gtk.Label(_('D.view')), expand=False)
        self.gui.stbv_combo = gtk.ComboBox()
        cell = gtk.CellRendererText()
        cell.props.ellipsize = pango.ELLIPSIZE_MIDDLE
        self.gui.stbv_combo.pack_start(cell, True)
        self.gui.stbv_combo.add_attribute(cell, 'text', 0)
        self.gui.stbv_combo.props.tooltip_text=_("No active dynamic view")

        hb.pack_start(self.gui.stbv_combo, expand=True)

        def new_stbv(*p):
            cr = CreateElementPopup(type_=View,
                                    parent=self.controller.package,
                                    controller=self.controller)
            cr.popup()
            return True
        b=get_small_stock_button(gtk.STOCK_ADD, new_stbv)
        b.set_tooltip_text(_("Create a new dynamic view."))
        hb.pack_start(b, expand=False)

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

        edit_stbv_button=get_small_stock_button(gtk.STOCK_EDIT, on_edit_current_stbv_clicked)
        edit_stbv_button.set_tooltip_text(_("Edit the current dynamic view."))
        hb.pack_start(edit_stbv_button, expand=False)

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

        self.audio_volume = gtk.VolumeButton()
        self.audio_volume.set_value(self.controller.player.sound_get_volume() / 100.0)
        ti = gtk.ToolItem()
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

        self.rate_control = gtk.SpinButton(gtk.Adjustment(1.0, 0.1, 100.0, 0.2, 0.5),
                                           0.2, 1)
        self.rate_control.set_tooltip_text(_("Playing rate"))
        ti = gtk.ToolItem()
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
                            self.controller.update_status('set', self.current_annotation.fragment.begin)
                        return True

                    def reg():
                        # If we are already in the current annotation, do not goto it
                        if not self.controller.player.current_position_value in self.current_annotation.fragment:
                            self.controller.update_status('set', self.current_annotation.fragment.begin)
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

        b = gtk.ToggleToolButton(gtk.STOCK_REFRESH)
        self.player_toolbar.buttons['loop'] = b
        self.update_loop_button()
        b.connect('toggled', loop_toggle_cb)
        self.player_toolbar.insert(b, -1)

        # Append the player status label to the toolbar
        ts=gtk.SeparatorToolItem()
        ts.set_draw(False)
        ts.set_expand(True)
        self.player_toolbar.insert(ts, -1)

        ti=gtk.ToolItem()
        self.gui.player_status=gtk.Label('--')
        ti.add(self.gui.player_status)
        self.player_toolbar.insert(ti, -1)

        # Create the slider
        adj = gtk.Adjustment(0, 0, 100, 1, 1, 10)
        self.gui.slider = gtk.HScale(adj)
        self.gui.slider.set_draw_value(False)
        self.gui.slider.connect('button-press-event', self.on_slider_button_press_event)
        self.gui.slider.connect('button-release-event', self.on_slider_button_release_event)
        self.gui.slider.connect('scroll-event', self.on_slider_scroll_event)
        def update_timelabel(s):
            self.time_label.set_time(s.get_value())
            return False
        self.gui.slider.connect('value-changed', update_timelabel)

        # Stack the video components
        v=gtk.VBox()
        v.pack_start(hb, expand=False)
        eb=gtk.EventBox()
        eb.set_above_child(True)
        eb.set_visible_window(True)
        eb.add(self.drawable)
        v.pack_start(eb, expand=True)
        eb.connect('scroll-event', self.on_slider_scroll_event)
        eb.connect('button-press-event', self.on_video_button_press_event)
        eb.connect('key-press-event', self.on_win_key_press_event)

        if config.data.preferences['display-scroller']:
            self.scroller=ScrollerView(controller=self.controller)
            v.pack_start(self.scroller.widget, expand=False)
        if config.data.preferences['display-caption']:
            self.captionview=CaptionView(controller=self.controller)
            self.register_view(self.captionview)
            v.pack_start(self.captionview.widget, expand=False)
        else:
            self.captionview=None

        h=gtk.HBox()
        eb=gtk.EventBox()
        self.time_label = gtk.Label()
        self.time_label.value = None
        def set_time(s, t):
            s.set_text(helper.format_time(t))
            s.value = t
            return t
        self.time_label.set_time=set_time.__get__(self.time_label)
        # Make sure that we use a fixed-size font, so that the
        # time_label width is constant and does not constantly modify
        # the slider available width.
        self.time_label.modify_font(pango.FontDescription("courier 10"))
        if config.data.os == 'darwin':
            self.time_label.set_size_request(90, -1)
        self.time_label.set_time(None)
        eb.add(self.time_label)

        def time_pressed(w, event):
            if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                self.goto_time_dialog()
                return True
            return True

        eb.connect('button-press-event', time_pressed)
        h.pack_start(eb, expand=False)
        h.pack_start(self.gui.slider, expand=True)
        v.pack_start(h, expand=False)

        v.pack_start(self.player_toolbar, expand=False)

        # create the viewbooks
        for pos in ('east', 'west', 'south', 'fareast'):
            self.viewbook[pos]=ViewBook(controller=self.controller, location=pos)

        self.pane['west']=gtk.HPaned()
        self.pane['east']=gtk.HPaned()
        self.pane['south']=gtk.VPaned()
        self.pane['fareast']=gtk.HPaned()

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
            step = - (pane.get_position() - (width - 256)) / 8
            condition = lambda p: (p < width - 256)
        elif paneid == 'south':
            need_adjust = (abs(height - pane.get_position()) < 200)
            step = - (pane.get_position() - (height - 256)) / 8
            condition = lambda p: (p < height - 256)
        elif paneid == 'west':
            # We should ideally also check for height adjustment (in
            # south pane), but the video player is generally always
            # visible anyway, so height should already be OK.
            need_adjust = (pane.get_position() < 200)
            step = 256 / 8
            condition = lambda p: (p > 256)
        elif paneid == 'east':
            need_adjust = (abs(width - pane.get_position()) < 200)
            step = - (pane.get_position() - (width - 256)) / 8
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
            gobject.timeout_add(100, enlarge_view)
        return True

    def find_bookmark_view(self):
        l=[ w for w in self.adhoc_views if w.view_id == 'activebookmarks' ]
        if l:
            # There is at least one open view. Use the latest.
            a=l[-1]
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
        try:
            p.set_widget(self.drawable)
        except AttributeError:
            p.set_visual(self.drawable.get_id())
        self.update_control_toolbar(self.player_toolbar)

    def player_play_pause(self, event):
        p=self.controller.player
        if p.status == p.PlayingStatus or p.status == p.PauseStatus:
            self.controller.update_status('pause')
        else:
            self.controller.update_status('start')

    def player_forward(self, event):
        if event.state & gtk.gdk.SHIFT_MASK:
            i='second-time-increment'
        else:
            i='time-increment'
        self.controller.move_position (config.data.preferences[i], notify=False)

    def player_rewind(self, event):
        if event.state & gtk.gdk.SHIFT_MASK:
            i='second-time-increment'
        else:
            i='time-increment'
        self.controller.move_position (-config.data.preferences[i], notify=False)

    def player_forward_frame(self, event):
        if config.data.preferences['custom-updown-keys'] or event.state & gtk.gdk.SHIFT_MASK:
            self.controller.move_position(+config.data.preferences['third-time-increment'], notify=False)
        else:
            self.controller.move_frame(+1)

    def player_rewind_frame(self, event):
        if config.data.preferences['custom-updown-keys'] or event.state & gtk.gdk.SHIFT_MASK:
            self.controller.move_position(-config.data.preferences['third-time-increment'], notify=False)
        else:
            self.controller.move_frame(-1)

    def player_create_bookmark(self, event):
        p=self.controller.player
        if p.status in (p.PlayingStatus, p.PauseStatus):
            self.create_bookmark(p.current_position_value,
                                 insert_after_current=(event.state & gtk.gdk.SHIFT_MASK))

    def player_home(self, event):
        self.controller.update_status ("set", self.controller.create_position (0))

    def player_end(self, event):
        c=self.controller
        pos = c.create_position (value = -config.data.preferences['time-increment'],
                                 key = c.player.MediaTime,
                                 origin = c.player.ModuloPosition)
        c.update_status ("set", pos)

    def player_set_fraction(self, f):
        self.controller.update_status("set", self.controller.create_position(long(self.controller.cached_duration * f)))

    def function_key(self, event):
        if gtk.keysyms.F1 <= event.keyval <= gtk.keysyms.F12:
            self.controller.notify('KeyboardInput', request={ 'keyname': gtk.gdk.keyval_name(event.keyval) })

    control_key_shortcuts={
        gtk.keysyms.Tab: player_play_pause,
        gtk.keysyms.space: player_play_pause,
        gtk.keysyms.Up: player_forward_frame,
        gtk.keysyms.Down: player_rewind_frame,
        gtk.keysyms.Right: player_forward,
        gtk.keysyms.Left: player_rewind,
        gtk.keysyms.Home: player_home,
        gtk.keysyms.End: player_end,
        gtk.keysyms.Insert: player_create_bookmark,
        }

    key_shortcuts={
        gtk.keysyms.Insert: player_create_bookmark,

        # Numeric keypad
        gtk.keysyms.KP_5: player_play_pause,
        gtk.keysyms.KP_8: player_forward_frame,
        gtk.keysyms.KP_2: player_rewind_frame,
        gtk.keysyms.KP_6: player_forward,
        gtk.keysyms.KP_4: player_rewind,
        gtk.keysyms.KP_7: player_home,
        gtk.keysyms.KP_1: player_end,
        gtk.keysyms.KP_0: player_create_bookmark,

        # Symbolic keypad
        gtk.keysyms.KP_Begin: player_play_pause,
        gtk.keysyms.KP_Up: player_forward_frame,
        gtk.keysyms.KP_Down: player_rewind_frame,
        gtk.keysyms.KP_Right: player_forward,
        gtk.keysyms.KP_Left: player_rewind,
        gtk.keysyms.KP_Home: player_home,
        gtk.keysyms.KP_End: player_end,
        gtk.keysyms.KP_Insert: player_create_bookmark,

        # Function keys
        gtk.keysyms.F1:   function_key,
        gtk.keysyms.F2:   function_key,
        gtk.keysyms.F3:   function_key,
        gtk.keysyms.F4:   function_key,
        gtk.keysyms.F5:   function_key,
        gtk.keysyms.F6:   function_key,
        gtk.keysyms.F7:   function_key,
        gtk.keysyms.F8:   function_key,
        gtk.keysyms.F9:   function_key,
        gtk.keysyms.F10:  function_key,
        gtk.keysyms.F11:  function_key,
        gtk.keysyms.F12:  function_key,
        }

    fullscreen_key_shortcuts = {
        gtk.keysyms.Tab: player_play_pause,
        gtk.keysyms.space: player_play_pause,
        gtk.keysyms.Up: player_forward_frame,
        gtk.keysyms.Down: player_rewind_frame,
        gtk.keysyms.Right: player_forward,
        gtk.keysyms.Left: player_rewind,
        gtk.keysyms.Home: player_home,
        gtk.keysyms.Insert: player_create_bookmark,

        # AZERTY keyboard navigation
        gtk.keysyms.ampersand:  lambda s, e: s.player_set_fraction(.0),
        gtk.keysyms.eacute:     lambda s, e: s.player_set_fraction(.1),
        gtk.keysyms.quotedbl:   lambda s, e: s.player_set_fraction(.2),
        gtk.keysyms.apostrophe: lambda s, e: s.player_set_fraction(.3),
        gtk.keysyms.parenleft:  lambda s, e: s.player_set_fraction(.4),
        gtk.keysyms.minus:      lambda s, e: s.player_set_fraction(.5),
        gtk.keysyms.egrave:     lambda s, e: s.player_set_fraction(.6),
        gtk.keysyms.underscore: lambda s, e: s.player_set_fraction(.7),
        gtk.keysyms.ccedilla:   lambda s, e: s.player_set_fraction(.8),
        gtk.keysyms.agrave:     lambda s, e: s.player_set_fraction(.9),

        # QWERTY keyboard navigation
        gtk.keysyms._1:  lambda s, e: s.player_set_fraction(.0),
        gtk.keysyms._2:  lambda s, e: s.player_set_fraction(.1),
        gtk.keysyms._3:  lambda s, e: s.player_set_fraction(.2),
        gtk.keysyms._4:  lambda s, e: s.player_set_fraction(.3),
        gtk.keysyms._5:  lambda s, e: s.player_set_fraction(.4),
        gtk.keysyms._6:  lambda s, e: s.player_set_fraction(.5),
        gtk.keysyms._7:  lambda s, e: s.player_set_fraction(.6),
        gtk.keysyms._8:  lambda s, e: s.player_set_fraction(.7),
        gtk.keysyms._9:  lambda s, e: s.player_set_fraction(.8),
        gtk.keysyms._0:  lambda s, e: s.player_set_fraction(.9),

        }

    def is_focus_on_editable(self):
        """Returns True if the focus is in an editable component.

        If not, we can activate control_key_shortcuts without the Control modifier.
        """
        # For the moment, we only check if we are in full or simplified GUI state.
        # FIXME: it is not as simple as this:
        #print "FOCUS", [ isinstance(w.get_focus(), gtk.Editable) for w in  gtk.window_list_toplevels() if w.get_focus() is not None ]
        # since we can want to use the standard gtk keyboard navigation among widgets.
        return self.viewbook['east'].widget.get_visible()

    def process_player_shortcuts(self, win, event):
        """Generic player control shortcuts.

        Tab: pause/play
        Control-right/-left: move in the stream
        Control-home/-end: start/end of the stream
        """

        p=self.controller.player

        if (event.keyval == gtk.keysyms.nobreakspace
            or (event.state & gtk.gdk.MOD1_MASK and event.keyval == gtk.keysyms.space)):
            # Alt-Space on MacOS X generates nobreakspace
            self.player_create_bookmark(event)
            return True
        elif event.keyval in self.key_shortcuts:
            self.key_shortcuts[event.keyval](self, event)
            return True
        elif event.keyval in self.control_key_shortcuts and (
            event.state & gtk.gdk.CONTROL_MASK
            or not self.is_focus_on_editable()):
            self.control_key_shortcuts[event.keyval](self, event)
            return True
        return False

    def process_fullscreen_shortcuts(self, win, event):
        """Fullscreen player control shortcuts.
        """
        c=self.controller
        p=self.controller.player
        if event.keyval == gtk.keysyms.Return:
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
                        at.date = self.controller.get_timestamp()
                        at.title = _("Default annotation type")
                        at.mimetype = 'text/plain'
                        at.setMetaData(config.data.namespace, 'color', self.controller.package._color_palette.next())
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
        elif gtk.gdk.keyval_to_unicode(event.keyval):
            c = unicode(gtk.gdk.keyval_name(event.keyval))
            if len(c) == 1 and (c.isalnum() or c.isspace()):
                if self.edited_annotation_text is None:
                    # Not yet editing, entering edit mode
                    self.edited_annotation_text = ''
                    self.edited_annotation_begin = p.current_position_value
                self.edited_annotation_text += c
                # Display feedback
                p.display_text(self.edited_annotation_text + '_', p.current_position_value, p.current_position_value + 10000)
                return True
        elif event.keyval == gtk.keysyms.BackSpace and self.edited_annotation_text is not None:
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
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        tb_list = [
            ('playpause', _("Play/Pause [Control-Tab / Control-Space]"), gtk.STOCK_MEDIA_PLAY, self.on_b_play_clicked),
            ('rewind', _("Rewind (%.02f s) [Control-Left]") % (config.data.preferences['time-increment'] / 1000.0), gtk.STOCK_MEDIA_REWIND, lambda i: self.controller.move_position (-config.data.preferences['time-increment'])),
            ('forward', _("Forward (%.02f s) [Control-Right]" % (config.data.preferences['time-increment'] / 1000.0)), gtk.STOCK_MEDIA_FORWARD, lambda i: self.controller.move_position (config.data.preferences['time-increment'])),
            ('previous_frame', _("Previous frame [Control-Down]"), gtk.STOCK_MEDIA_PREVIOUS, lambda i: self.controller.move_frame(-1)),
            ('next_frame', _("Next frame [Control-Up]"), gtk.STOCK_MEDIA_NEXT, lambda i: self.controller.move_frame(+1)),
            ('fullscreen', _("Fullscreen"), gtk.STOCK_FULLSCREEN, lambda i: self.controller.player.fullscreen(self.connect_fullscreen_handlers) ),
            ]

        tb.buttons = {}
        for name, text, stock, callback in tb_list:
            if name == 'playpause':
                b = PlayPauseButton(stock)
            else:
                b = gtk.ToolButton(stock)
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
            tb.buttons['playpause'].set_stock_ids(gtk.STOCK_MEDIA_RECORD, gtk.STOCK_MEDIA_STOP)
            for name, b in tb.buttons.iteritems():
                if name == 'playpause':
                    continue
                b.set_sensitive(False)
        else:
            tb.buttons['playpause'].set_stock_ids(gtk.STOCK_MEDIA_PLAY, gtk.STOCK_MEDIA_PAUSE)
            for b in tb.buttons.itervalues():
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

    def debug_cb(self, window, event, *p):
        print "Got event %s (%d, %d) in window %s" % (str(event),
                                                      event.x,
                                                      event.y,
                                                      str(window))
        return False

    def init_window_size(self, window, name):
        """Initialize window size according to stored values.
        """
        if name == 'editwindow':
            # Do not update position/size for edit popups
            return True
        if config.data.preferences['remember-window-size']:
            s=config.data.preferences['windowsize'].setdefault(name, (640,480))
            window.resize(*s)
            pos=config.data.preferences['windowposition'].get(name, None)
            if pos:
                window.move(*pos)
            if name != 'main':
                # The main GUI is regularly reallocated (at each update_display), so
                # do not update continuously. Just do it on application exit.
                window.connect('size-request', self.resize_cb, name)
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
        if other_thread and config.data.os == 'win32':
            # If executed in a thread other than the one that was
            # initialized, pixbuf loader (do not know if it is
            # specific to svg though) crashes in the write method on
            # win32.  So we have to make sure the method is executed
            # in the main thread context.
            q=Queue.Queue(1)
            def process_overlay(queue=None):
                queue.put(overlay_svg_as_png(png_data, svg_data))
                return False
            gobject.timeout_add(0, process_overlay, q)
            try:
                data=q.get(True, 2)
            except Queue.Empty:
                data=None
            return data
        else:
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

    def undo(self, *p):
        """Undo the last modifying action.
        """
        try:
            self.controller.undomanager.undo()
        except AttributeError:
            pass
        return True

    def save_snapshot_as(self, position, filename=None, retry=True):
        """Save the snapshot for the given position into a file.

        If supported by the player, it will save the full-resolution screenshot.
        """
        def do_save_as(fname, png_data, notify=False):
            try:
                f = open(fname, 'wb')
                f.write(str(png_data))
                f.close()
                self.controller.log(_("Screenshot saved to %s") % fname)
                if notify:
                    self.controller.queue_action(dialog.message_dialog, _("Screenshot saved in\n %s") % unicode(fname), modal=False)
            except (IOError, OSError), e:
                self.controller.queue_action(dialog.message_dialog, _("Could not save screenshot:\n %s") % unicode(e), icon=gtk.MESSAGE_ERROR, modal=False)

        if filename is None:
            name = "%s-%010d.png" % (
                os.path.splitext(
                    os.path.basename(
                        self.controller.get_default_media()))[0],
                position)
            filename = dialog.get_filename(title=_("Save screenshot to..."),
                                           action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                           button=gtk.STOCK_SAVE,
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

    def export_element(self, element):
        def generate_default_filename(filter, filename=None):
            """Generate a filename for the given filter.
            """
            if not filename:
                # Get the current package title.
                if isinstance(element, Package):
                    filename=self.controller.package.title
                    if not filename or filename == 'Template package':
                        # Use a better name
                        filename=os.path.splitext(os.path.basename(self.controller.package.uri))[0]
                    filename=helper.title2id(filename)
                else:
                    filename=helper.title2id(element.title or element.id)
            else:
                # A filename was provided. Strip the extension.
                filename=os.path.splitext(filename)[0]
            # Add a pertinent extension
            if filter is None:
                return filename
            ext=filter.getMetaData(config.data.namespace, 'extension')
            if not ext:
                ext = helper.title2id(filter.id)
            return '.'.join( (filename, ext) )

        if isinstance(element, Package):
            title=_("Export package data")
        elif isinstance(element, AnnotationType):
            title=_("Export annotation type %s") % self.controller.get_title(element)
        else:
            title=_("Export element %s") % self.controller.get_title(element)
        fs = gtk.FileChooserDialog(title=title,
                                   parent=self.gui.win,
                                   action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                   buttons=( gtk.STOCK_CONVERT, gtk.RESPONSE_OK,
                                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))
        def update_extension(sel):
            filter=sel.get_current_element()
            f=generate_default_filename(filter, os.path.basename(fs.get_filename() or ""))
            fs.set_current_name(f)
            return True
        def valid_always(v):
            return True
        def valid_for_package(v):
            return v.matchFilter['class'] in ('package', '*')
        def valid_for_annotation_type(v):
            return v.matchFilter['class'] in ('annotation-type', '*')
        valid_filter=valid_always
        if isinstance(element, Package):
            valid_filter=valid_for_package
        elif isinstance(element, AnnotationType):
            valid_filter=valid_for_annotation_type
        exporters=dialog.list_selector_widget( [ (v, v.title) for v in self.controller.get_export_filters()
                                                 if valid_filter(v) ],
                                               callback=update_extension )
        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Export format")), expand=False)
        hb.pack_start(exporters)
        fs.set_extra_widget(hb)

        fs.show_all()
        fs.set_current_name(generate_default_filename(exporters.get_current_element()))
        self.fs=fs
        res=fs.run()

        if res == gtk.RESPONSE_OK:
            self.controller.apply_export_filter(element,
                                                exporters.get_current_element(),
                                                fs.get_filename())
        fs.destroy()
        return True

    def update_package_list (self):
        """Update the list of loaded packages.
        """
        menu=self.gui.package_list_menu

        def activate_package(button, alias):
            self.controller.activate_package (alias)
            return True

        # Remove all previous menuitems
        menu.foreach(menu.remove)

        # Rebuild the list
        for a, p in self.controller.packages.iteritems():
            if a == 'advene':
                continue
            if p == self.controller.package:
                name = '> ' + a
            else:
                name = '  ' + a
            if p._modified:
                name += _(' (modified)')
            i=gtk.MenuItem(label=unicode(name), use_underline=False)
            i.connect('activate', activate_package, a)
            i.set_tooltip_text(_("Activate %s") % self.controller.get_title(p))
            menu.append(i)

        menu.show_all()
        return True

    arrow_list={ 'linux': u'\u25b8',
                 'darwin': u'\u25b6',
                 'win32': u'>' }
    def update_stbv_list (self):
        """Update the STBV list.
        """
        stbv_combo = self.gui.stbv_combo
        if stbv_combo is None:
            return True
        l=[ helper.TitledElement(value=None, title=_("No active dynamic view")) ]
        l.extend( [ helper.TitledElement(value=i, title=u'%s %s %s' % (self.arrow_list[config.data.os],
                                                                       self.controller.get_title(i),
                                                                       self.arrow_list[config.data.os]))
                    for i in self.controller.get_stbv_list() ] )
        st, i = dialog.generate_list_model([ (i.value, i.title) for i in l ],
                                           active_element=self.controller.current_stbv)
        stbv_combo.set_model(st)
        if i is None:
            i=st.get_iter_first()
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

        menu=gtk.Menu()
        for title, url in self.controller.get_utbv_list():
            i=gtk.MenuItem(label=title, use_underline=False)
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
                print "Closing ", v
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
        d['width'], d['height']=w.get_size()
        for k, v in d.iteritems():
            d[k]=unicode(v)
        layout=ET.SubElement(workspace, 'layout', d)
        for n in ('west', 'east', 'fareast', 'south'):
            ET.SubElement(layout, 'pane', id=n, position=unicode(self.pane[n].get_position()))
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
                w=v.window
                d={}
                d['x'], d['y']=w.get_position()
                d['width'], d['height']=w.get_size()
                for k, v in d.iteritems():
                    element.attrib[k]=unicode(v)
            workspace.append(element)
        return workspace

    def workspace_restore(self, workspace, preserve_layout=False):
        """Restore the workspace from a given ElementTree element.

        It is the responsibility of the caller to clear the workspace if needed.
        """
        if workspace.tag != 'workspace':
            raise Exception('Invalid XML element for workspace: ' + workspace.tag)
        layout=None
        # Open adhoc views
        for node in workspace:
            if node.tag == ET.QName(config.data.namespace, 'adhoc'):
                # It is a adhoc-view definition
                v=self.open_adhoc_view(name=node.attrib['id'],
                                       label=node.attrib['title'],
                                       destination=node.attrib['destination'],
                                       parameters=node)
                if node.attrib['destination'] == 'popup':
                    # Restore popup windows positions
                    v.window.move(long(node.attrib['x']), long(node.attrib['y']))
                    v.window.resize(long(node.attrib['width']), long(node.attrib['height']))
            elif node.tag == 'layout':
                layout=node
        # Restore layout
        if layout is not None and not preserve_layout:
            w=self.gui.win
            w.move(long(layout.attrib['x']), long(layout.attrib['y']))
            w.resize(min(long(layout.attrib['width']), gtk.gdk.screen_width()),
                     min(long(layout.attrib['height']), gtk.gdk.screen_height()))
            for pane in layout:
                if pane.tag == 'pane' and pane.attrib['id'] in self.pane:
                    self.pane[pane.attrib['id']].set_position(long(pane.attrib['position']))

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
        v.date=self.controller.get_timestamp()

        workspace=self.workspace_serialize()
        stream=StringIO.StringIO()
        helper.indent(workspace)
        ET.ElementTree(workspace).write(stream, encoding='utf-8')
        v.content.setData(stream.getvalue())
        stream.close()

        if create:
            self.controller.package.views.append(v)
            self.controller.notify("ViewCreate", view=v)
        else:
            self.controller.notify("ViewEditEnd", view=v)
        return True

    def open_adhoc_view(self, name, label=None, destination='default', parameters=None, **kw):
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
            destination=config.data.preferences['popup-destination']

        view=None
        if isinstance(name, View):
            if name.content.mimetype == 'application/x-advene-workspace-view':
                tree=ET.parse(name.content.stream)

                if kw.get('ask', True):
                    d = gtk.Dialog(title=_("Restoring workspace..."),
                                   parent=None,
                                   flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                                   buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                             gtk.STOCK_OK, gtk.RESPONSE_OK,
                                             ))
                    l=gtk.Label(_("Do you wish to restore the %s workspace ?") % name.title)
                    l.set_line_wrap(True)
                    l.show()
                    d.vbox.pack_start(l, expand=False)

                    delete_existing_toggle=gtk.CheckButton(_("Clear the current workspace"))
                    delete_existing_toggle.set_active(True)
                    delete_existing_toggle.show()
                    d.vbox.pack_start(delete_existing_toggle, expand=False)

                    res=d.run()
                    clear=delete_existing_toggle.get_active()
                    d.destroy()
                else:
                    res=gtk.RESPONSE_OK
                    clear=True

                if res == gtk.RESPONSE_OK:
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
            parameters=name.content
            p=AdhocViewParametersParser(name.content.stream)
            if p.view_id:
                if label is None:
                    label=name.title
                name=p.view_id
            else:
                self.log(_("Cannot identify the adhoc view %s") % name.id)
                return None

        if name == 'transcription':
            kwargs={ 'controller': self.controller,
                     'parameters': parameters }
            if 'source' in kw:
                kwargs['source']=kw['source']
            elif 'elements' in kw:
                kwargs['elements']=kw['elements']
            elif parameters is not None:
                # source may be defined in parameters
                kwargs['source']=None
            else:
                at=self.ask_for_annotation_type(text=_("Choose the annotation type to display as transcription."),
                                                create=False)
                if at is None:
                    return None
                else:
                    kwargs['source']="here/annotationTypes/%s/annotations/sorted" % at.id
                    if label is None:
                        label=self.controller.get_title(at)
            view = self.registered_adhoc_views[name](**kwargs)
        elif name == 'webbrowser' or name == 'htmlview':
            if destination is None and HTMLView._engine is not None:
                # Embedded version.
                view = HTMLView(controller=self.controller)
                view.open_url(self.controller.get_default_url(alias='advene'))
            elif self.controller.package is not None:
                m=self.build_utbv_menu()
                m.popup(None, None, None, 0, gtk.get_current_event_time())
            else:
                self.log (("No current package"))
        elif name == 'transcribe':
            try:
                filename=kw['filename']
            except KeyError:
                filename=None
            view=self.registered_adhoc_views[name](controller=self.controller, filename=filename, parameters=parameters, **kw)
        elif name == 'edit':
            try:
                element=kw['element']
            except KeyError:
                element=None
            if element is None:
                return None
            try:
                view=get_edit_popup(element, self.controller)
            except TypeError, e:
                print (_(u"Error: unable to find an edit popup for %(element)s:\n%(error)s") % {
                        'element': unicode(element),
                        'error': unicode(e)}).encode('latin1')
                view=None
            if view is not None and view.widget.get_parent() is not None:
                # Widget is already displayed. Present it.
                view.widget.get_toplevel().present()
                view=None
            label=_("Editing %s") % self.controller.get_title(element)
        elif name == 'editaccumulator':
            view=self.registered_adhoc_views[name](controller=self.controller, scrollable=True)
            if not self.edit_accumulator:
                # The first opened accumulator becomes the default one.
                self.edit_accumulator=view
                def handle_accumulator_close(w):
                    self.edit_accumulator = None
                    return False
                self.edit_accumulator.widget.connect('destroy', handle_accumulator_close)
        elif name == 'comment':
            v=self.controller.create_static_view(elements=[])
            label=_("Comment view (%s)" % time.strftime('%Y%m%d - %H:%M'))
            v.title=label
            view=get_edit_popup(v, controller=self.controller)
        elif name in self.registered_adhoc_views:
            view=self.registered_adhoc_views[name](controller=self.controller,
                                                   parameters=parameters, **kw)

        if view is None:
            return view
        # Store destination and label, used when moving the view
        view._destination=destination
        label=unicode(label or view.view_name)
        view.set_label(label)

        if destination == 'popup':
            w=view.popup(label=label)
            if isinstance(w, gtk.Window):
                dialog.center_on_mouse(w)
        elif destination in ('south', 'east', 'west', 'fareast'):
            self.viewbook[destination].add_view(view, name=unicode(label))
        return view

    def get_adhoc_view_instance_from_id(self, ident):
        """Return the adhoc view instance matching the identifier.
        """
        l=[v for v in self.adhoc_views if repr(v) == ident ]
        if l:
            return l[0]
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
        l=[ v for v in self.adhoc_views if v.view_id == 'htmlview' ]
        if l:
            # We use the first one available.
            l[0].open_url(url)
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
        self.update_package_list()
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
        p=context.evaluateValue('package')
        self.log (_("Package %(uri)s loaded: %(annotations)s and %(relations)s.")
                  % {
                'uri': p.uri,
                'annotations': helper.format_element_name('annotation',
                                                          len(p.annotations)),
                'relations': helper.format_element_name('relation',
                                                        len(p.relations))
                })
        if not p.uri.endswith('new_pkg'):
            gtk.recent_manager_get_default().add_item(p.uri)

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
            load=False
            if config.data.preferences['restore-default-workspace'] == 'always':
                self.controller.queue_action(self.open_adhoc_view, view, ask=False)
            elif config.data.preferences['restore-default-workspace'] == 'ask':
                def open_view():
                    self.open_adhoc_view(view, ask=False)
                    return True
                load=dialog.message_dialog(_("Do you want to restore the saved workspace ?"),
                                           icon=gtk.MESSAGE_QUESTION,
                                           callback=open_view)
        return False

    def update_window_title(self):
        # Update the main window title
        t=" - ".join((_("Advene"), unicode(os.path.basename(self.controller.package.uri)), self.controller.get_title(self.controller.package)))
        if self.controller.package._modified:
            t += " (*)"
            self.toolbuttons['save'].set_sensitive(True)
        else:
            self.toolbuttons['save'].set_sensitive(False)
        self.gui.win.set_title(t)
        return True

    def log (self, msg, level=None):
        """Add a new log message to the logmessage window.

        @param msg: the message
        @type msg: string
        @param level: the error level
        @type level: int
        """
        def undisplay(ctxid, msgid):
            self.gui.statusbar.remove_message(ctxid, msgid)
            return False

        # Display in statusbar
        cid=self.gui.statusbar.get_context_id('info')
        message_id=self.gui.statusbar.push(cid, unicode(msg).replace("\n", " - "))
        # Display the message only 4 seconds
        gobject.timeout_add(4000, undisplay, cid, message_id)

        # Store into logbuffer
        buf = self.logbuffer
        mes = "".join(("\n", time.strftime("%H:%M:%S"), " - ", unicode(msg)))
        # FIXME: handle level (bold?)
        buf.place_cursor(buf.get_end_iter ())
        buf.insert_at_cursor (mes)

        # Dump to terminal
        if config.data.preferences['log-to-terminal']:
            print unicode(msg).encode('utf-8')
        return

    def get_illustrated_text(self, text, position=None, vertical=False, height=40, color=None):
        """Return a HBox with the given text and a snapshot corresponding to position.
        """
        if vertical:
            box=gtk.VBox()
        else:
            box=gtk.HBox()
        box.pack_start(image_from_position(self.controller,
                                           position=position,
                                           height=height), expand=False)
        l=gtk.Label()
        if color:
            l.set_markup('<span background="%s">%s</span>' % (color, text))
        else:
            l.set_text(text)
        box.pack_start(l, expand=False)
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

    def popup_evaluator(self, *p, **kw):
        p=self.controller.package
        try:
            a=p.annotations[-1]
        except IndexError:
            a=None
        try:
            at=p.annotationTypes[-1]
        except IndexError:
            at=None

        class PackageWrapper(object):
            def __getattr__(self, name):
                e = p.get_element_by_id(name)
                if e is not None:
                    return e
                else:
                    return getattr(p, name)
            def _get_dict(self):
                return dict( (el.id, el) for l in (p.annotations, p.relations,
                                                   p.schemas,
                                                   p.annotationTypes, p.relationTypes,
                                                   p.views, p.queries) for el in l )
            __dict__ = property(_get_dict)

        ev=Evaluator(globals_=globals(),
                     locals_={'package': p,
                              'p': p,
                              'P': PackageWrapper(),
                              'a': a,
                              'at': at,
                              'c': self.controller,
                              'g': self,
                              'pp': pprint.pformat },
                     historyfile=config.data.advenefile('evaluator.log', 'settings')
                     )
        ev.locals_['self']=ev
        # Define variables referencing the opened views
        for v in self.adhoc_views:
            ev.locals_[v.view_id]=v

        # Hook completer
        completer=Completer(textview=ev.source,
                            controller=self.controller,
                            indexer=self.controller.package._indexer)

        w=ev.popup()
        w.set_icon_list(*self.get_icon_list())
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
        #gtk.threads_enter()
        try:
            pos=self.controller.update()
        except p.InternalException:
            # FIXME: something sensible to do here ?
            print "Internal error on video player"
            #gtk.threads_leave()
            return True
        except Exception, e:
            # Catch-all exception, in order to keep the mainloop
            # runnning
            #gtk.threads_leave()
            import traceback
            s=StringIO.StringIO()
            traceback.print_exc (file = s)
            self.log(_("Got exception %s. Trying to continue.") % str(e), s.getvalue())
            traceback.print_exc()
            return True
        #gtk.threads_leave()

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
            if d > 0 and d != self.gui.slider.get_adjustment ().upper:
                self.gui.slider.set_range (0, d)
                self.gui.slider.set_increments (d / 100, d / 10)

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
            for alias, p in c.packages.iteritems():
                if alias == 'advene':
                    continue
                if p._modified:
                    n, e = os.path.splitext(p.uri)
                    if n.startswith('http:'):
                        continue
                    if n.startswith('file://'):
                        n = n[7:]
                    n = n + '.backup' + e
                    p.save(name=n)
            return True

        if self.gui.win.get_title().endswith('(*)') ^ c.package._modified:
            self.update_window_title()
        self.toolbuttons['undo'].set_sensitive(bool(c.undomanager.history))
        is_playing = (c.player.status in (c.player.PlayingStatus, c.player.PauseStatus))
        self.toolbuttons['create_text_annotation'].set_sensitive(is_playing)
        self.toolbuttons['create_svg_annotation'].set_sensitive(is_playing)
        for l in ('rewind', 'forward', 'previous_frame', 'next_frame', 'loop'):
            self.player_toolbar.buttons[l].set_sensitive(is_playing)

        # Check snapshotter activity
        s = getattr(c.player, 'snapshotter', None)
        if s:
            if s.timestamp_queue.empty():
                self.snapshotter_monitor_icon.set_state('idle')
            else:
                self.snapshotter_monitor_icon.set_state('running')
        else:
            self.snapshotter_monitor_icon.set_state(None)

        # Check auto-save
        if config.data.preferences['package-auto-save'] != 'never':
            t=time.time() * 1000
            if t - self.last_auto_save > config.data.preferences['package-auto-save-interval']:
                # Need to save
                l=[ alias for (alias, p) in self.controller.packages.iteritems() if p._modified and alias != 'advene' ]
                if l:
                    if c.tracers and config.data.preferences['record-actions']:
                        try:
                            fn = c.tracers[0].export()
                            print "trace exported to %s" % fn
                        except Exception, e:
                            print "error exporting trace : %s" % unicode(e).encode('utf-8')
                    if config.data.preferences['package-auto-save'] == 'always':
                        c.queue_action(do_save, l)
                    else:
                        # Ask before saving. Use the non-modal dialog
                        # to avoid locking the interface
                        dialog.message_dialog(label=_("""The package(s) %s are modified.\nSave them now?""") % ", ".join(l),
                                              icon=gtk.MESSAGE_QUESTION,
                                              callback=lambda: do_save(l))
                self.last_auto_save=t

        # Fix the webserver reaction time on win32
        if config.data.os == 'win32':
            if c.player.status in self.active_player_status:
                i = config.data.play_interval
            else:
                i = config.data.noplay_interval
            if sys.getcheckinterval() != i:
                sys.setcheckinterval(i)

        return True

    def search_string(self, s):
        if not ' ' in s:
            # Single-word search. Forward to existing note-taking or
            # transcription views.
            # Note: it could maybe be better achieved through a new signal WordSearch
            # which could be handled by the views
            tr=[ v for v in self.adhoc_views if v.view_id in ('transcribe', 'transcription') ]
            for v in tr:
                v.highlight_search_forward(s)
        return self.controller.search_string(searched=s,
                                             sources=config.data.preferences['quicksearch-sources'],
                                             case_sensitive=not config.data.preferences['quicksearch-ignore-case'])

    def do_quicksearch(self, *p):
        s=unicode(self.quicksearch_entry.get_text())
        if not s:
            self.log(_("Empty quicksearch string"))
            return True
        res=self.search_string(unicode(s))
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
        d = gtk.Dialog(title=text,
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 ))
        l=gtk.Label(text)
        l.set_line_wrap(True)
        l.show()
        d.vbox.pack_start(l, expand=False)

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
        new_type_dialog=gtk.VBox()
        new_schema_dialog=gtk.VBox()

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
                                  icon=gtk.MESSAGE_ERROR)
            return None

        d.vbox.pack_start(type_selector, expand=False)
        type_selector.show_all()

        if create:
            d.vbox.pack_start(new_type_dialog, expand=False)
            new_type_dialog.pack_start(gtk.Label(_("Creating a new type.")))
            ident=self.controller.package._idgenerator.get_id(AnnotationType)
            new_type_title_dialog=dialog.title_id_widget(element_title=ident,
                                                         element_id=ident)
            new_type_title_dialog.title_entry.set_tooltip_text(_("Title of the new type"))
            new_type_title_dialog.id_entry.set_tooltip_text(_("Id of the new type. It is generated from the title, but you may change it if necessary."))
            new_type_dialog.pack_start(new_type_title_dialog, expand=False)

            mimetype_selector = dialog.list_selector_widget(members=predefined_content_mimetypes, entry=True)
            mimetype_selector.set_tooltip_text(_("Specify the content-type for the annotation type"))

            new_type_title_dialog.attach(gtk.Label(_("Content type")), 0, 1, 2, 3)
            new_type_title_dialog.attach(mimetype_selector, 1, 2, 2, 3)

            new_type_title_dialog.attach(gtk.Label(_("Schema")), 0, 1, 3, 4)

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
            new_schema_dialog.pack_start(gtk.Label(_("Specify the schema title")), expand=False)
            ident=self.controller.package._idgenerator.get_id(Schema)
            new_schema_title_dialog=dialog.title_id_widget(element_title=ident,
                                                           element_id=ident)
            new_schema_title_dialog.title_entry.set_tooltip_text(_("Title of the new schema"))
            new_schema_title_dialog.id_entry.set_tooltip_text(_("Id of the new schema. It is generated from the title, but you may change it if necessary."))
            new_schema_dialog.pack_start(new_schema_title_dialog, expand=False)

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
        if res == gtk.RESPONSE_OK:
            at=type_selector.get_current_element()
            if at == newat:
                # Creation of a new type.
                attitle=unicode(new_type_title_dialog.title_entry.get_text())
                atid=unicode(new_type_title_dialog.id_entry.get_text())
                at=self.controller.package.get_element_by_id(atid)
                if at is not None:
                    dialog.message_dialog(_("You specified a annotation-type identifier that already exists. Aborting."))
                    d.destroy()
                    return None
                sc=schema_selector.get_current_element()
                if sc == newschema:
                    sctitle=unicode(new_schema_title_dialog.title_entry.get_text())
                    scid=unicode(new_schema_title_dialog.id_entry.get_text())
                    sc=self.controller.package.get_element_by_id(scid)
                    if sc is None:
                        # Create the schema
                        sc=self.controller.package.createSchema(ident=scid)
                        sc.author=config.data.userid
                        sc.date=self.controller.get_timestamp()
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
                at.date=self.controller.get_timestamp()
                at.title=attitle
                at.mimetype=mimetype_selector.get_current_element()
                at.setMetaData(config.data.namespace, 'color', self.controller.package._color_palette.next())
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
        d = gtk.Dialog(title=text,
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 ))
        l=gtk.Label(text)
        l.set_line_wrap(True)
        l.show()
        d.vbox.pack_start(l, expand=False)

        # Anticipated declaration of some widgets, which need to be
        # updated in the handle_new_type/schema_selection callback.
        new_schema_dialog=gtk.VBox()

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
        d.vbox.pack_start(schema_selector, expand=False)
        d.vbox.pack_start(new_schema_dialog, expand=False)
        new_schema_dialog.pack_start(gtk.Label(_("Specify the schema title")), expand=False)
        ident=self.controller.package._idgenerator.get_id(Schema)
        new_schema_title_dialog=dialog.title_id_widget(element_title=ident,
                                                       element_id=ident)
        new_schema_dialog.pack_start(new_schema_title_dialog, expand=False)

        d.vbox.show_all()
        new_schema_dialog.hide()

        d.show()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == gtk.RESPONSE_OK:
            sc=schema_selector.get_current_element()
            if sc == newschema:
                sctitle=unicode(new_schema_title_dialog.title_entry.get_text())
                scid=unicode(new_schema_title_dialog.id_entry.get_text())
                sc=self.controller.package.get_element_by_id(scid)
                if sc is None:
                    # Create the schema
                    sc=self.controller.package.createSchema(ident=scid)
                    sc.author=config.data.userid
                    sc.date=self.controller.get_timestamp()
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

    def on_exit(self, source=None, event=None):
        """Generic exit callback."""
        for a, p in self.controller.packages.iteritems():
            if a == 'advene':
                continue
            if p._modified:
                t = self.controller.get_title(p)
                response=dialog.yes_no_cancel_popup(title=_("Package %s modified") % t,
                                                             text=_("The package %s has been modified but not saved.\nSave it now?") % t)
                if response == gtk.RESPONSE_CANCEL:
                    return True
                elif response == gtk.RESPONSE_YES:
                    self.on_save1_activate(package=p)
                elif response == gtk.RESPONSE_NO:
                    p._modified=False
            if p.imagecache._modified and config.data.preferences['imagecache-save-on-exit'] != 'never':
                if config.data.preferences['imagecache-save-on-exit'] == 'ask':
                    media=self.controller.get_default_media(package=p)
                    response=dialog.yes_no_cancel_popup(title=_("%s snapshots") % media,
                                                             text=_("Do you want to save the snapshots for media %s?") % media)
                    if response == gtk.RESPONSE_CANCEL:
                        return True
                    elif response == gtk.RESPONSE_YES:
                        try:
                            p.imagecache.save (helper.mediafile2id (media))
                        except OSError, e:
                            self.log(_("Cannot save imagecache for %(media)s: %(e)s") % locals())
                    elif response == gtk.RESPONSE_NO:
                        p.imagecache._modified=False
                        pass
                elif config.data.preferences['imagecache-save-on-exit'] == 'always':
                    media=self.controller.get_default_media(package=p)
                    try:
                        p.imagecache.save (helper.mediafile2id (media))
                    except OSError, e:
                        self.log(_("Cannot save imagecache for %(media)s: %(e)s") % locals())

        if self.controller.on_exit():
            # Memorize application window size/position
            self.resize_cb(self.gui.win, None, 'main')
            gtk.main_quit()
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
        msg =  label
        msg += "%d annotations\n" % len(annotations)
        if annotations:
            msg += "Min duration : %s\n" % helper.format_time(min( a.fragment.duration for a in annotations))
            msg += "Max duration : %s\n" % helper.format_time(max( a.fragment.duration for a in annotations))
            msg += "Mean duration : %s\n" % helper.format_time(sum( a.fragment.duration for a in annotations) / len(annotations))
            msg += "Total duration : %s\n" % helper.format_time(sum( a.fragment.duration for a in annotations))
        dialog.message_dialog(msg)
        return True

    def display_textfile(self, path, title=None, viewname=None):
        w=gtk.Window()
        if title is not None:
            w.set_title(title + " - " + path)
        w.set_icon_list(*self.get_icon_list())

        def refresh(b, t):
            b=t.get_buffer()
            b.delete(*b.get_bounds ())
            try:
                f=open(path, 'r')
                b.set_text("".join(f.readlines()))
                f.close()
            except (IOError, OSError), e:
                b.set_text("Cannot read %s:\n%s" % (path, unicode(e)))
            t.scroll_mark_onscreen(b.get_mark('insert'))
            return True

        def close(b, w):
            w.destroy()
            return True

        vbox=gtk.VBox()

        t=gtk.TextView()
        t.set_editable (False)
        t.set_wrap_mode (gtk.WRAP_CHAR)

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_win.add(t)

        vbox.add(scroll_win)

        hbox=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect('clicked', close, w)
        hbox.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_REFRESH)
        b.connect('clicked', refresh, t)
        hbox.pack_start(b, expand=False)

        vbox.pack_start(hbox, expand=False)

        w.add(vbox)
        refresh(None, t)

        if viewname is not None:
            self.controller.gui.init_window_size(w, viewname)

        w.show_all()

        return True

    # Callbacks function. Skeletons can be generated by glade2py
    def on_create_text_annotation(self, win=None, event=None):
        c = self.controller
        if c.player.status in (c.player.PlayingStatus, c.player.PauseStatus):
            # Find out the appropriate type
            at = self.controller.package.get_element_by_id('annotation')
            if not at:
                # Does not exist. Create it.
                sc = self.controller.package.schemas[0]
                at = sc.createAnnotationType(ident='annotation')
                at.author = config.data.userid
                at.date = self.controller.get_timestamp()
                at.title = _("Text annotation")
                at.mimetype = "text/plain"
                at.setMetaData(config.data.namespace, 'color', self.controller.package._color_palette.next())
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

    def on_create_svg_annotation(self, win=None, event=None):
        c = self.controller
        self.controller.update_snapshot(c.player.current_position_value)
        if c.player.status in (c.player.PlayingStatus, c.player.PauseStatus):
            # Find out the appropriate type
            at = self.controller.package.get_element_by_id('svgannotation')
            if not at:
                # Does not exist. Create it.
                sc = self.controller.package.schemas[0]
                at = sc.createAnnotationType(ident='svgannotation')
                at.author = config.data.userid
                at.date = self.controller.get_timestamp()
                at.title = _("Graphical annotation")
                at.mimetype = "image/svg+xml"
                at.setMetaData(config.data.namespace, 'color', self.controller.package._color_palette.next())
                at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                sc.annotationTypes.append(at)
                self.controller.notify('AnnotationTypeCreate', annotationtype=at)
            if not isinstance(at, AnnotationType):
                dialog.message_dialog(_("Cannot find an appropriate annotation type"))
                return True
            a = self.controller.create_annotation(c.player.current_position_value, at)
            self.edit_element(a)
        return True

    def on_win_key_press_event (self, win=None, event=None):
        """Keypress handling.
        """
        # Player shortcuts
        if self.process_player_shortcuts(win, event):
            return True

        # Control-shortcuts
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.e:
                # Popup the evaluator window
                self.popup_evaluator()
                return True
            elif event.keyval == gtk.keysyms.k:
                # Get the cursor in the quicksearch entry
                self.quicksearch_entry.grab_focus()
                self.quicksearch_entry.select_region(0, -1)
                return True
            elif event.keyval == gtk.keysyms.q:
                self.on_exit()
                return True
            elif event.keyval == gtk.keysyms.s:
                if event.state & gtk.gdk.SHIFT_MASK:
                    self.on_save_as1_activate()
                else:
                    self.on_save1_activate()
                return True
            elif event.keyval == gtk.keysyms.z:
                self.undo()
                return True
        return False

    def on_new1_activate (self, button=None, data=None):
        """New package. Erase the current one.
        """
        if 'new_pkg' in self.controller.packages:
            # An unsaved template package already exists.
            # Ask to save it first.
            dialog.message_dialog(_("An unsaved template package exists\nSave it first."))
        else:
            self.set_busy_cursor(True)
            self.controller.load_package ()
        return True

    def on_close1_activate (self, button=None, data=None):
        p=self.controller.package
        if p._modified:
            response=dialog.yes_no_cancel_popup(title=_("Package modified"),
                                         text=_("The package that you want to close has been modified but not saved.\nSave it now?"))
            if response == gtk.RESPONSE_CANCEL:
                return True
            if response == gtk.RESPONSE_YES:
                self.on_save1_activate()
                self.controller.remove_package()
                return True
            if response == gtk.RESPONSE_NO:
                self.controller.package._modified=False
                self.controller.remove_package()
                return True
        else:
            self.controller.remove_package()

        # Close all edit popups for this element
        for e in self.edit_popups:
            try:
                if p == e.element.rootPackage and e.window:
                    e.window.destroy()
            except KeyError:
                pass

        return True

    def on_open1_activate (self, button=None, data=None):
        """Open a file selector to load a package."""
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None

        filename, alias=dialog.get_filename(title=_("Load a package"),
                                            action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                            button=gtk.STOCK_OPEN,
                                            default_dir=d,
                                            alias=True,
                                            filter='advene')
        if filename:
            name, ext = os.path.splitext(filename.lower())
            if ext in config.data.video_extensions:
                self.log(_("A video file was selected. Pretend that the user selected 'Select a video file'..."))
                self.controller.set_default_media(filename)
                return True
            if not ext in ('.xml', '.azp', '.apl'):
                # Does not look like a valid package
                if not dialog.message_dialog(_("The file %s does not look like a valid Advene package. It should have a .azp or .xml extension. Try to open anyway?") % filename,
                                      icon=gtk.MESSAGE_QUESTION):
                    return True
            if ext == '.apl':
                modif=[ (a, p)
                        for (a, p) in self.controller.packages.iteritems()
                        if p._modified ]
                if modif:
                    if not dialog.message_dialog(
                        _("You are trying to load a session file, but there are unsaved packages. Proceed anyway?"),
                        icon=gtk.MESSAGE_QUESTION):
                        return True

            try:
                self.set_busy_cursor(True)
                self.controller.load_package (uri=filename, alias=alias)
            except (OSError, IOError), e:
                self.set_busy_cursor(False)
                dialog.message_dialog(_("Cannot load package %(filename)s:\n%(error)s") % {
                        'filename': filename,
                        'error': unicode(e)}, gtk.MESSAGE_ERROR)
        return True

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
            save=False
            if config.data.preferences['save-default-workspace'] == 'always':
                save=True
            elif config.data.preferences['save-default-workspace'] == 'ask':
                save=dialog.message_dialog(_("Do you want to save the current workspace ?"),
                                           icon=gtk.MESSAGE_QUESTION)
            if save:
                self.workspace_save('_default_workspace')
                default=self.controller.package.getMetaData (config.data.namespace, "default_adhoc")
                if not default:
                    self.controller.package.setMetaData (config.data.namespace, "default_adhoc", '_default_workspace')
            alias=self.controller.aliases[package]
            modified = [ p for p in self.edit_popups if p.get_modified() ]
            if modified and config.data.preferences['apply-edited-elements-on-save']:
                for p in modified:
                    p.apply_cb()
            try:
                self.controller.save_package (alias=alias)
            except (OSError, IOError), e:
                dialog.message_dialog(_("Could not save the package: %s") % unicode(e),
                                               gtk.MESSAGE_ERROR)
        return True

    def on_save_as1_activate (self, button=None, package=None):
        """Save the package with a new name."""
        if package is None:
            package=self.controller.package
        self.controller.update_package_title()
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None
        filename=dialog.get_filename(title=_("Save the package %s") % self.controller.get_title(package),
                                              action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                              button=gtk.STOCK_SAVE,
                                              default_dir=d,
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
                if ret == gtk.RESPONSE_YES:
                    filename = p + '.azp'
                elif ret == gtk.RESPONSE_NO:
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
                                           icon=gtk.MESSAGE_QUESTION)
            if save:
                self.workspace_save('_default_workspace')
                default=self.controller.package.getMetaData (config.data.namespace, "default_adhoc")
                if not default:
                    self.controller.package.setMetaData (config.data.namespace, "default_adhoc", '_default_workspace')
            alias=self.controller.aliases[package]
            modified = [ p for p in self.edit_popups if p.get_modified() ]
            if modified and config.data.preferences['apply-edited-elements-on-save']:
                for p in modified:
                    p.apply_cb()
            try:
                self.controller.save_package(name=filename, alias=alias)
            except (OSError, IOError), e:
                dialog.message_dialog(_("Could not save the package: %s") % unicode(e),
                                               gtk.MESSAGE_ERROR)
        return True

    def on_save_session1_activate (self, button=None, data=None):
        """Save the current session.
        """
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None
        filename=dialog.get_filename(title=_("Save the session in..."),
                                              action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                              button=gtk.STOCK_SAVE,
                                              default_dir=d,
                                              filter='session')
        if filename:
            (p, ext) = os.path.splitext(filename)
            if ext == '':
                # Add a pertinent extension
                filename = filename + '.apl'
            self.controller.save_session(filename)
            self.log(_("Session saved in %s") % filename)
        return True


    def on_import_dvd_chapters1_activate (self, button=None, data=None):
        # FIXME: loosy test
        if (self.controller.get_default_media() is None
            or 'dvd' in self.controller.get_default_media()):
            if not dialog.message_dialog(
                _("Do you confirm the creation of annotations matching the DVD chapters?"),
                icon=gtk.MESSAGE_QUESTION):
                return True
            try:
                i=advene.util.importer.get_importer('lsdvd', controller=self.controller)
            except Exception:
                dialog.message_dialog(_("Cannot import DVD chapters. Did you install the lsdvd software?"),
                                        icon=gtk.MESSAGE_ERROR)
                return True
            i.package=self.controller.package
            i.process_file('lsdvd')
            self.controller.package._modified = True
            self.controller.notify('PackageLoad', package=self.controller.package)
        else:
            dialog.message_dialog(_("The associated media is not a DVD."),
                                           icon=gtk.MESSAGE_ERROR)
        return True

    def on_import_file1_activate (self, button=None, data=None):
        self.open_adhoc_view('importerview')
        return False

    def on_process_video_activate(self, button=None, data=None):
        fname = self.controller.get_default_media()
        if fname:
            self.open_adhoc_view('importerview', filename=fname, message=_("Processing %s video") % fname,
                                 display_unlikely=False)
        else:
            dialog.message_dialog(_("No associated video file"),
                                  icon=gtk.MESSAGE_ERROR)
        return False

    def on_find1_activate (self, button=None, data=None):
        self.open_adhoc_view('interactivequery', destination='east')
        return True

    def on_cut1_activate (self, button=None, data=None):
        print "Cut: Not implemented yet."
        return False

    def on_copy1_activate (self, button=None, data=None):
        print "Copy: Not implemented yet."
        return False

    def on_paste1_activate (self, button=None, data=None):
        print "Paste: Not implemented yet."
        return False

    def on_delete1_activate (self, button=None, data=None):
        print "Delete: Not implemented yet (cf popup menu)."
        return False

    def on_edit_ruleset1_activate (self, button=None, data=None):
        """Default ruleset editing."""
        w=gtk.Window(gtk.WINDOW_TOPLEVEL)
        w.set_title(_("Standard RuleSet"))
        w.connect('destroy', lambda e: w.destroy())
        w.set_icon_list(*self.get_icon_list())

        vbox=gtk.VBox()
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
            print "Not implemented yet"
            return True

        hb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_SAVE)
        b.connect('clicked', save_ruleset, 'default')
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect('clicked', validate_ruleset, 'default')
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect('clicked', lambda e: w.destroy())
        hb.pack_end(b, expand=False)

        hb.show_all()

        vbox.pack_start(hb, expand=False)

        vbox.show()

        w.show()
        return True

    def on_adhoc_treeview_activate (self, button=None, data=None):
        self.open_adhoc_view('tree')
        return True

    def on_adhoc_timeline_activate (self, button=None, data=None):
        self.open_adhoc_view('timeline')
        return True

    def on_view_urlstack_activate (self, button=None, data=None):
        """Open the URL stack view plugin.

        Useless now, the urlstack is always here. This code will be
        removed sometime...
        """
        return True

    def on_adhoc_transcription_activate (self, button=None, data=None):
        self.open_adhoc_view('transcription')
        return True

    def on_adhoc_transcribe_activate (self, button=None, data=None):
        self.open_adhoc_view('transcribe')
        return True

    def on_adhoc_transcription_package_activate (self, button=None, data=None):
        self.open_adhoc_view('transcription', source="here/annotations/sorted")
        return True

    def on_adhoc_browser_activate (self, button=None, data=None):
        self.open_adhoc_view('browser')
        return True

    def on_adhoc_web_browser_activate (self, button=None, data=None):
        self.open_adhoc_view('webbrowser')
        return True

    def on_evaluator2_activate (self, button=None, data=None):
        self.popup_evaluator()
        return True

    def on_webserver_log1_activate (self, button=None, data=None):
        self.display_textfile(config.data.advenefile('webserver.log', 'settings'),
                              title=_("Webserver log"),
                              viewname='weblogview')
        return True

    def on_view_mediainformation_activate (self, button=None, data=None):
        """View mediainformation."""
        self.controller.position_update ()
        p=self.controller.player
        if p.is_active() and p.playlist_get_list():
            self.controller.log("%(status)s %(filename)s %(position)s / %(duration)s (cached %(cached)s) - %(positionms)dms / %(durationms)dms (cached %(cachedms)dms)" % {
                    'filename': unicode(p.playlist_get_list ()[0]),
                    'status': self.statustext.get(p.status, _("Unknown")),
                    'position': helper.format_time(p.current_position_value),
                    'positionms': p.current_position_value,
                    'duration': helper.format_time_reference(p.stream_duration),
                    'durationms': p.stream_duration,
                    'cached': helper.format_time_reference(self.controller.cached_duration),
                    'cachedms': self.controller.cached_duration
                    })
        else:
            self.controller.log(_("Player not active - cached duration   : %(duration)s (%(durationms)d ms)") % {
                    'duration': helper.format_time_reference(self.controller.cached_duration),
                    'durationms': self.controller.cached_duration })
        return True

    def on_about1_activate (self, button=None, data=None):
        """Activate the About window."""
        gtk.about_dialog_set_url_hook(lambda dialog, link: self.controller.open_url(link))
        d=gtk.AboutDialog()
        d.set_name('Advene')
        d.set_version(config.data.version_string.replace('Advene ', ''))
        d.set_copyright("Copyright 2002-2012 Olivier Aubert, Pierre-Antoine Champin")
        d.set_license(_('GNU General Public License v. 2\nSee http://www.gnu.org/copyleft/gpl.html for more details'))
        d.set_website('http://www.advene.org/')
        d.set_website_label(_('Visit the Advene web site for examples and documentation.'))
        d.set_authors( [ 'Olivier Aubert', 'Pierre-Antoine Champin', 'Yannick Prie', 'Bertrand Richard', 'Frank Wagner' ] )
        d.set_logo(gtk.gdk.pixbuf_new_from_file(config.data.advenefile( ( 'pixmaps', 'logo_advene.png') )))
        d.connect('response', lambda w, r: w.destroy())
        d.run()

        return True

    def on_b_play_clicked (self, button=None, data=None):
        p = self.controller.player
        if not p.playlist_get_list() and not 'record' in p.player_capabilities:
            # No movie file is defined yet. Propose to choose one.
            self.on_b_addfile_clicked()
            return True
        if p.status == p.PlayingStatus:
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

    def on_b_addfile_clicked (self, button=None, data=None):
        """Open a movie file"""
        mp=[ d for d in config.data.path['moviepath'].split(os.path.pathsep) if d != '_' ]
        if mp:
            default=mp[0]
        else:
            default=None
        filename=dialog.get_filename(title=_("Select a movie file"),
                                     action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                     button=gtk.STOCK_OPEN,
                                     default_dir=default,
                                     filter='video')
        if filename:
            self.controller.set_default_media(filename)
        return True

    def on_b_selectdvd_clicked (self, button=None, data=None):
        """Play a DVD."""
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title(_("Title/Chapter selection"))

        window.connect('destroy', lambda e: window.destroy())

        vbox=gtk.VBox()

        sel=DVDSelect(controller=self.controller,
                      current=self.controller.get_default_media())
        vbox.add(sel.get_widget())

        hbox=gtk.HButtonBox()

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

        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect('clicked', validate, sel, window)
        hbox.add(b)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect('clicked', cancel, window)
        hbox.add(b)

        vbox.add(hbox)
        window.add(vbox)
        window.show_all()

        return True

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

    def on_package_imports1_activate (self, button=None, data=None):
        """Edit imported elements from other packages."""
        imp=advene.gui.edit.imports.Importer(controller=self.controller)
        imp.popup()
        return True

    def on_package_properties1_activate (self, button=None, data=None):
        cache={
            'author': self.controller.package.author,
            'date': self.controller.package.date,
            'media': self.controller.get_default_media() or "",
            'duration': str(self.controller.package.cached_duration),
            'title': self.controller.package.title or ""
            }
        def reset_duration(b, entry):
            v=long(self.controller.player.stream_duration)
            entry.set_text(str(v))
            return True

        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Package properties"))
        ew.add_entry(_("Author"), "author", _("Author name"))
        ew.add_entry(_("Date"), "date", _("Package creation date"))
        ew.add_entry(_("Title"), "title", _("Package title"))
        ew.add_file_selector(_("Associated media"), 'media', _("Select a movie file"))
        ew.add_entry_button(_("Duration"), "duration", _("Media duration in ms"), _("Reset"), reset_duration)

        res=ew.popup()

        if res:
            self.controller.package.author = cache['author']
            self.controller.package.date = cache['date']
            self.controller.package.title = cache['title']
            self.update_window_title()
            self.controller.set_default_media(cache['media'])
            try:
                d=long(cache['duration'])
                if d != self.controller.package.cached_duration:
                    self.controller.package.cached_duration = d
                    self.controller.notify('DurationUpdate', duration=d)
            except ValueError, e:
                print "Cannot convert duration", str(e)
                pass
        return True

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
                        'abbreviation-mode', 'text-abbreviations', 'completion-mode',
                        'prefer-wysiwyg', 'player-shortcuts-in-edit-windows', 'apply-edited-elements-on-save' )
        # Direct options needing a restart to be taken into account.
        restart_needed_options = ('tts-engine', 'language')

        path_options=('data', 'plugins', 'advene', 'imagecache', 'moviepath', 'shotdetect')
        cache={
            'font-size': config.data.preferences['timeline']['font-size'],
            'button-height': config.data.preferences['timeline']['button-height'],
            'interline-height': config.data.preferences['timeline']['interline-height'],
            }

        cache['player-level'] = config.data.player['verbose'] or -1
        for (k, v) in config.data.player.iteritems():
            cache['player-' + k] = config.data.player[k]

        for k in path_options:
            cache[k] = config.data.path[k]
        for k in direct_options:
            cache[k] = config.data.preferences[k]
        cache['package-auto-save-interval']=cache['package-auto-save-interval']/1000
        ew=advene.gui.edit.properties.EditNotebook(cache.__setitem__, cache.get)
        ew.set_name(_("Preferences"))

        ew.add_title(_("Paths"))

        ew.add_dir_selector(_("Data"), "data", _("Standard directory for data files"))
        ew.add_dir_selector(_("Movie path"), "moviepath", _("List of directories (separated by %s) to search for movie files (_ means package directory)") % os.path.pathsep)
        ew.add_dir_selector(_("Imagecache"), "imagecache", _("Directory for storing the snapshot cache"))
        ew.add_dir_selector(_("Player"), "plugins", _("Directory of the video player"))
        ew.add_file_selector(_("Shotdetect"), "shotdetect", _("Shotdetect application"))

        ew.add_title(_("GUI"))
        ew.add_option(_("Interface language (after restart)"), 'language', _("Language used for the interface (necessitates to restart the application)"), odict((
                (_("System default"), ''),
                ("English", 'C'),
                ("Esperanto", 'eo'),
                ("Francais", 'fr_FR'),
                )))
        ew.add_checkbox(_("Record activity trace"), "record-actions", _("Record activity trace"))
        ew.add_checkbox(_("Expert mode"), "expert-mode", _("Offer advanced possibilities"))
        ew.add_checkbox(_("Prefer WYSIWYG"), "prefer-wysiwyg", _("Use WYSIWYG editors when possible (HTML, SVG)"))
        ew.add_checkbox(_("Player control in edit popups"), 'player-shortcuts-in-edit-windows', _("Enable generic player controls in edit windows. This may be undesirable since it overloads some standard text-edition behaviours (esp. control-left/right)."))

        ew.add_option(_("Open popups"), 'popup-destination',
                      _("Where should we open adhoc views?"), odict((
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

        ew.add_title(_("General"))
        ew.add_checkbox(_("Weekly update check"), 'update-check', _("Weekly check for updates on the Advene website"))
        ew.add_option(_("On exit,"), 'imagecache-save-on-exit',
                      _("How to handle screenshots on exit"), odict((
                (_("never save screenshots"), 'never'),
                (_("always save screenshots"), 'always'),
                (_("ask before saving screenshots"), 'ask'),
                )))
        ew.add_option(_("Auto-save"), 'package-auto-save',
                      _("Data auto-save functionality"), odict((
                (_("is desactivated"), 'never'),
                (_("is done automatically"), 'always'),
                (_("is done after confirmation"), 'ask'),
                )))
        ew.add_spin(_("Auto-save interval (in s)"), 'package-auto-save-interval', _("Interval (in seconds) between package auto-saves"), 5, 60 * 60)

        ew.add_title(_("Workspace"))

        ew.add_option(_("On package saving,"), 'save-default-workspace',
                      _("Do you wish to save the default workspace with the package?"), odict((
                (_("never save the current workspace"), 'never'),
                (_("always save the current workspace"), 'always'),
                (_("ask before saving the current workspace"), 'ask'),
                )))
        ew.add_checkbox(_("Auto-validation of edited elements"), 'apply-edited-elements-on-save', _("Automatically validate modified elements when saving the package."))

        ew.add_option(_("On package load,"), 'restore-default-workspace',
                      _("Do you wish to load the workspace saved with the package?"), odict((
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
            options[_("GDI")] = 'wingdi'
            options[_("Direct X")] = 'directx'
        else:
            ew.add_entry(_("DVD device"), 'player-dvd-device', _("Device for the DVD"))
            options[_("X11")] = 'x11'
            options[_("XVideo")] = 'xvideo'
            options[_("GL")] = 'gl'

        ew.add_option(_("Video output"), "player-vout", _("Video output module"), options)

        ew.add_label(_("Recorder options"))
        ew.add_entry(_("Audio input"), 'player-audio-record-device', _("Device name for audio input (with gstrecorder plugin)"))
        ew.add_checkbox(_("Record video"), 'player-record-video', _("Record both video and audio"))

        if config.data.preferences['expert-mode']:
            ew.add_label(_("<i>Experimental</i>"))
            ew.add_checkbox(_("Scroller"), 'display-scroller', _("Embed the caption scroller below the video"))
            ew.add_checkbox(_("Caption"), 'display-caption', _("Embed the caption view below the video"))

        ew.add_title(_("Time-related"))
        ew.add_option(_("Time format"), 'timestamp-format', _("Format used to display timecodes"), odict( (
                    ('HH:MM:SS.sss', '%H:%M:%.S'),
                    ('HH:MM:SSfNN (frame number)', '%H:%M:%fS'),
                    ('HH:MM:SS', '%H:%M:%S'),
                    ('MM:SS.sss', '%M:%.S'),
                    ('MM:SS', '%M:%S'),
                    ('SS.sss', '%.S'),
                    ('SS', '%S'),
                    )) )
        fps = [ 10, 12, 24, 25, 40, 50, 60, 72 ]
        d = config.data.preferences['default-fps']
        if not d in fps:
            fps.append(d)
            fps.sort()
        ew.add_option(_("Default FPS"), 'default-fps',
                      _("Default FPS (frame-per-second) value, when entering or displaying timestamps with frame numbers."), odict( (str(f), f) for f in fps))
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
        ew.add_checkbox(_("Abbreviation mode"), 'abbreviation-mode', _("Enable abbreviation mode"))
        ew.add_text(_("Abbreviations"), 'text-abbreviations', _("Text abbreviations. 1 entry per line. Each line consists of the abbreviation followed by its replacement."))

        ew.add_title(_("Text-To-Speech"))
        ew.add_option(_("TTS language"), 'tts-language',
                      _("What language settings should be used for text-to-speech"), odict((
                (_("English"), 'en'),
                (_("French"), 'fr'),
                (_("Spanish"), 'es'),
                )))
        ew.add_entry(_("TTS Encoding"), 'tts-encoding',
                      _("What encoding should be used to communicate with the TTS engine"), entries = [ 'utf8', 'utf16', 'latin1', 'cp1252' ] )
        ew.add_option(_("TTS Engine"), 'tts-engine',
                      _("Which TTS engine should be used (modification requires restarting Advene to take into account)"), odict((
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
                self.text_abbreviations.update( dict( l.split(" ", 1) for l in config.data.preferences['text-abbreviations'].splitlines() ) )

            for k in direct_options:
                if k in restart_needed_options and config.data.preferences[k] != cache[k]:
                    app_need_restart = True
                config.data.preferences[k] = cache[k]

            for k in ('font-size', 'button-height', 'interline-height'):
                config.data.preferences['timeline'][k] = cache[k]
            for k in path_options:
                if cache[k] != config.data.path[k]:
                    config.data.path[k]=cache[k]
                    # Store in auto-saved preferences
                    config.data.preferences['path'][k]=cache[k]
                    if k == 'plugins':
                        player_need_restart = True

            for n in config.data.player.keys():
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

    def on_save_imagecache1_activate (self, button=None, data=None):
        media=self.controller.get_default_media()
        id_ = helper.mediafile2id (media)
        try:
            d=self.controller.package.imagecache.save (id_)
            self.log(_("Imagecache saved to %s") % d)
        except OSError, e:
            self.log(_("Cannot save imagecache for %(media)s: %(e)s") % locals())
        return True

    def on_reset_imagecache_activate (self, button=None, data=None):
        valid = self.controller.package.imagecache.valid_snapshots()
        self.controller.package.imagecache.reset()
        for t in valid:
            self.controller.notify('SnapshotUpdate', position=t)
        return True

    def on_restart_player1_activate (self, button=None, data=None):
        self.log (_("Restarting player..."))
        self.controller.restart_player ()
        return True

    def on_slider_button_press_event (self, button=None, event=None):
        self.slider_move = True
        if event.button == 1:
            event.button = 2
        return False

    def on_slider_button_release_event (self, button=None, event=None):
        if self.controller.player.playlist_get_list():
            p = self.controller.create_position (value = long(self.gui.slider.get_value ()))
            self.controller.update_status('set', p)
        self.slider_move = False
        if event.button == 1:
            event.button = 2
        return False

    def on_slider_scroll_event (self, widget=None, event=None):
        if event.direction == gtk.gdk.SCROLL_DOWN or event.direction == gtk.gdk.SCROLL_RIGHT:
            incr=+1
        if event.direction == gtk.gdk.SCROLL_UP or event.direction == gtk.gdk.SCROLL_LEFT:
            incr=-1
        self.controller.move_frame(incr)
        return False

    def on_video_button_press_event (self, button=None, event=None):
        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            self.controller.player.fullscreen(self.connect_fullscreen_handlers)
        elif event.button == 3:
            self.player_create_bookmark(event)
        return False

    def on_help1_activate (self, button=None, data=None):
        self.controller.open_url ('http://liris.cnrs.fr/advene/wiki/index.php/AdveneUserGuide')
        return True

    def on_support1_activate (self, button=None, data=None):
        self.controller.open_url ('http://liris.cnrs.fr/advene/forum/')
        return True

    def on_helpshortcuts_activate (self, button=None, data=None):
        helpfile=os.path.join( config.data.path['web'], 'shortcuts.html' )
        if os.access(helpfile, os.R_OK):
            self.controller.open_url ('file:///' + helpfile)
        else:
            self.controller.open_url ('http://liris.cnrs.fr/advene/wiki/index.php/AdveneShortcuts')
        return True

    def on_advene_log_display(self, button=None, data=None):
        self.display_textfile(config.data.advenefile('advene.log', 'settings'),
                              title=_("Advene log"),
                              viewname='advenelogview')
        return True

    def on_advene_log_folder_display(self, button=None, data=None):
        d = config.data.advenefile('', 'settings')
        if config.data.os == 'win32':
            os.startfile(d)
        elif config.data.os == 'darwin':
            os.system('open "%s"' % d)
        else:
            # Linux is more problematic...
            for p in ('kfmclient', 'gnome-open', 'xdg-open'):
                prg = helper.find_in_path(p)
                if prg is not None:
                    if p == 'kfmclient':
                        prg = prg + " openURL"
                    os.system('%s "%s"' % (prg, d))
                    break
        return True

    def on_create_view_activate (self, button=None, data=None):
        cr = CreateElementPopup(type_ = View,
                                parent=self.controller.package,
                                controller=self.controller)
        cr.popup()
        return True

    def on_create_query_activate (self, button=None, data=None):
        cr = CreateElementPopup(type_ = Query,
                                parent=self.controller.package,
                                controller=self.controller)
        cr.popup()
        return True

    def on_create_schema_activate (self, button=None, data=None):
        cr = CreateElementPopup(type_ = Schema,
                                parent=self.controller.package,
                                controller=self.controller)
        sc=cr.popup()
        return sc

    def on_create_annotation_type_activate (self, button=None, data=None):
        at=self.ask_for_annotation_type(text=_("Creation of a new annotation type"),
                                        create=True,
                                        force_create=True)
        if at is None:
            return None
        return at

    def on_create_relation_type_activate (self, button=None, data=None):
        sc=self.ask_for_schema(text=_("Select the schema where you want to\ncreate the new relation type."), create=True)
        if sc is None:
            return None
        cr=CreateElementPopup(type_=RelationType,
                              parent=sc,
                              controller=self.controller)
        rt=cr.popup()
        return rt

    def on_package_list_activate(self, menu=None):
        self.update_package_list()
        return True

    def on_merge_package_activate(self, button=None, data=None):
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None
        filename=dialog.get_filename(title=_("Select the package to merge"),
                                              action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                              button=gtk.STOCK_OPEN,
                                              default_dir=d,
                                              filter='advene')
        if not filename:
            return True
        try:
            source=Package(uri=filename)
        except Exception, e:
            msg = "Cannot load %s file: %s" % (filename, unicode(e))
            self.log(msg)
            dialog.message_dialog(msg, icon=gtk.MESSAGE_ERROR)
            return True
        m=Merger(self.controller, sourcepackage=source, destpackage=self.controller.package)
        m.popup()
        return True

    def on_save_workspace_as_package_view1_activate (self, button=None, data=None):
        name=self.controller.package._idgenerator.get_id(View)+'_'+'workspace'

        d = dialog.title_id_dialog(title=_("Saving workspace"),
                                   element_title=name,
                                   element_id=name,
                                   text=_("Enter a view name to save the workspace"))
        d.default=gtk.CheckButton(_("Default workspace"))
        d.default.set_tooltip_text(_("Open this workspace when opening the package"))
        d.vbox.pack_start(d.default)
        d.show_all()
        dialog.center_on_mouse(d)

        title=None
        ident=None
        default=False

        res=d.run()
        if res == gtk.RESPONSE_OK:
            try:
                title=unicode(d.title_entry.get_text())
                ident=unicode(d.id_entry.get_text())
                default=d.default.get_active()
            except ValueError:
                pass
        d.destroy()

        if ident is None:
            return True

        if not re.match(r'^[a-zA-Z0-9_]+$', ident):
            dialog.message_dialog(_("Error: the identifier %s contains invalid characters.") % ident, icon=gtk.MESSAGE_ERROR)
            return True

        v=helper.get_id(self.controller.package.views, ident)
        if v is None:
            create=True
            v=self.controller.package.createView(ident=ident, clazz='package')
            v.content.mimetype='application/x-advene-workspace-view'
        else:
            # Existing view. Check that it is already an workspace-view
            if v.content.mimetype != 'application/x-advene-workspace-view':
                dialog.message_dialog(_("Error: the view %s exists and is not a workspace view.") % ident, icon=gtk.MESSAGE_ERROR)
                return True
            create=False
        v.title=title
        v.author=config.data.userid
        v.date=self.controller.get_timestamp()

        workspace=self.workspace_serialize()
        stream=StringIO.StringIO()
        helper.indent(workspace)
        ET.ElementTree(workspace).write(stream, encoding='utf-8')
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

    def on_save_workspace_as_default1_activate (self, button=None, data=None):
        d=config.data.advenefile('defaults', 'settings')
        if not os.path.isdir(d):
            # Create it
            try:
                helper.recursive_mkdir(d)
            except OSError, e:
                self.controller.log(_("Cannot save default workspace: %s") % unicode(e))
                return True
        defaults=config.data.advenefile( ('defaults', 'workspace.xml'), 'settings')

        # Do not save package-specific arguments.
        root=self.workspace_serialize(with_arguments=False)
        stream=open(defaults, 'w')
        helper.indent(root)
        ET.ElementTree(root).write(stream, encoding='utf-8')
        stream.close()
        self.controller.log(_("Standard workspace has been saved"))
        return True

    def on_website_export_activate(self, button=None, data=None):
        w=gtk.Window()

        v=gtk.VBox()
        w.set_title(_("Website export"))
        v.add(gtk.Label(_("Exporting views to a website")))

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Output directory")), expand=False)
        dirname_entry=gtk.Entry()
        d=self.controller.package.getMetaData(config.data.namespace, 'website-export-directory')
        if d is not None:
            dirname_entry.set_text(d)
        hb.add(dirname_entry)

        d=gtk.Button(stock=gtk.STOCK_OPEN)
        def select_dir(*p):
            d=dialog.get_dirname(_("Specify the output directory"))
            if d is not None:
                dirname_entry.set_text(d)
            return True
        d.connect('clicked', select_dir)
        hb.pack_start(d, expand=False)
        v.pack_start(hb, expand=False)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Maximum recursion depth")), expand=False)
        adj=gtk.Adjustment(3, 1, 9, 1)
        max_depth=gtk.SpinButton(adj)
        hb.pack_start(max_depth, expand=False)
        v.pack_start(hb, expand=False)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Video URL")), expand=False)
        video_entry=gtk.Entry()
        video_entry.set_tooltip_text(_("URL for the video, if it is available on a sharing website (Only Youtube for the moment).\n It can also be a h264/ogg file, which will in this case be handled by the HTML5 video player."))
        u=self.controller.package.getMetaData(config.data.namespace, 'website-export-video-url')
        if u is None:
            u = self.controller.get_default_media()
            if u:
                u = os.path.basename(u)
        if u is not None:
            video_entry.set_text(u)

        hb.add(video_entry)
        v.pack_start(hb, expand=False)

        pb=gtk.ProgressBar()
        v.pack_start(pb, expand=False)

        w.should_continue = False

        def cb(val, msg):
            if val > 0 and val <= 1.0:
                pb.set_fraction(val)
            if len(msg) > 80:
                msg = msg[:36] + "(...)" + msg[-36:]
            pb.set_text(msg)
            while gtk.events_pending():
                gtk.main_iteration()
            return w.should_continue

        def do_conversion(b):
            d=unicode(dirname_entry.get_text())
            if not d:
                return False

            video=unicode(video_entry.get_text())

            if (self.controller.package.getMetaData(config.data.namespace, 'website-export-directory') != d
                or self.controller.package.getMetaData(config.data.namespace, 'website-export-video-url') != video):
                self.controller.package._modified = True
            self.controller.package.setMetaData(config.data.namespace, 'website-export-directory', d)
            if video:
                self.controller.package.setMetaData(config.data.namespace, 'website-export-video-url', video)

            b.set_sensitive(False)
            w.should_continue = True

            try:
                self.controller.website_export(destination=d,
                                               max_depth=max_depth.get_value_as_int(),
                                               progress_callback=cb,
                                               video_url=video)
            except OSError, e:
                dialog.message_dialog(_("Could not export data: ") + unicode(e), icon=gtk.MESSAGE_ERROR)
                b.set_sensitive(True)
            self.log(_("Website export to %s completed") % d)
            w.destroy()
            return True

        dirname_entry.connect('activate', do_conversion)

        def do_cancel(*p):
            if w.should_continue:
                w.should_continue = False
            else:
                w.destroy()
            return True

        hb=gtk.HButtonBox()
        b=gtk.Button(stock=gtk.STOCK_CONVERT)
        b.connect('clicked', do_conversion)
        hb.add(b)
        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect('clicked', do_cancel)
        hb.add(b)
        v.pack_start(hb, expand=False)

        w.add(v)

        w.show_all()
        return True

    def on_export_activate (self, button=None, data=None):
        """Export a whole package.
        """
        self.export_element(self.controller.package)
        return True

    def update_annotation_screenshots(self, *p):
        """Update screenshot for annotations bounds.

        This requires that the player has the async-snapshot capability.
        """
        if not 'async-snapshot' in self.controller.player.player_capabilities:
            dialog.message_dialog(_("This video player is not able to grab specific screenshots"))
            return True
        missing = set()
        ic=self.controller.package.imagecache
        for a in self.controller.package.annotations:
            if not ic.is_initialized(a.fragment.begin):
                missing.add(a.fragment.begin)
            if not ic.is_initialized(a.fragment.end):
                missing.add(a.fragment.end)
        if missing:
            dialog.message_dialog(_("Updating %d snapshots") % len(missing), modal=False)
            print "Updating %d missing snapshots: " % len(missing), ", ".join(helper.format_time_reference(t) for t in sorted(missing))
            for t in sorted(missing):
                self.controller.player.async_snapshot(t)
        else:
            dialog.message_dialog(_("No snapshot to update"), modal=False)
        return True

    def generate_screenshots(self, *p):
        """Generate screenshots.
        """
        movie=self.controller.get_default_media()
        if not movie:
            # No defined movie.
            dialog.message_dialog(_("You first must load a movie into Advene" ), icon=gtk.MESSAGE_ERROR)
            return True
        if not os.path.exists(movie):
            dialog.message_dialog(_("The movie %s does not seem to exist.") % movie, icon=gtk.MESSAGE_ERROR)
            return True

        c=self.controller
        p=c.player

        def do_cancel(b, pb):
            if pb.event_source_generate is not None:
                gobject.source_remove(pb.event_source_generate)
            c.package.imagecache.autosync=pb.old_autosync

            # Restore standard update display methods
            self.event_source_update_display=gobject.timeout_add (100, self.update_display)
            self.event_source_slow_update_display=gobject.timeout_add (1000, self.slow_update_display)
            pb._window.destroy()
            return True

        def take_screenshot(pb):
            """Method called every second.
            """
            try:
                p.position_update()
                i = p.snapshot (p.relative_position)
            except p.InternalException, e:
                print "Exception in snapshot: %s" % e
                return True
            if i is not None and i.height != 0:
                self.controller.package.imagecache[p.current_position_value] = helper.snapshot2png (i)
                prg=1.0 * p.current_position_value / p.stream_duration
                pb.set_fraction(prg)
                pb.set_text(helper.format_time_reference(p.current_position_value))
                if prg > .999:
                    do_cancel(None, pb)
            return True

        def do_generate(b, pb):
            b.set_sensitive(False)
            # Deactivate the GUI update method
            gobject.source_remove(self.event_source_update_display)
            gobject.source_remove(self.event_source_slow_update_display)

            # Make the imagecache directly store data on disk
            pb.old_autosync=c.package.imagecache.autosync
            c.package.imagecache.autosync=True
            if c.package.imagecache.name is None:
                c.package.imagecache.name=helper.mediafile2id(c.get_default_media())

            if p.status == p.PauseStatus:
                # If we were paused, resume from this position
                c.update_status('resume', position=p.relative_position)
            elif p.status != p.PlayingStatus:
                # If we were not already playing, capture from the start
                c.update_status('start', position=0)
            pb.event_source_generate=gobject.timeout_add(400, take_screenshot, pb)
            return True

        w=gtk.Window()
        w.set_title(_("Generating screenshots"))
        v=gtk.VBox()
        w.add(v)

        l=gtk.Label()
        l.set_markup(_("<b>Screenshot generation</b>\n\nScreenshots will be captured approximately every 500ms.\n\nIf the movie was paused or playing, the capture will begin at the current position. Else, it will begin at the beginning of the movie.\nNote that the main interface will not be refreshed as long as this window is open."))
        l.set_line_wrap(True)
        v.pack_start(l, expand=False)

        progressbar=gtk.ProgressBar()
        progressbar.event_source_generate=None
        v.pack_start(progressbar, expand=False)

        progressbar._window=w
        progressbar.old_autosync=c.package.imagecache.autosync
        hb=gtk.HBox()

        b=gtk.Button(stock=gtk.STOCK_MEDIA_RECORD)
        b.connect('clicked', do_generate, progressbar)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect('clicked', do_cancel, progressbar)
        hb.pack_start(b, expand=False)

        v.pack_start(hb, expand=False)
        w.show_all()
        w.set_modal(True)

    def on_simplify_interface_activate(self, *p):
        if self.viewbook['east'].widget.get_visible():
            # Full state -> go into simplified state
            for v in self.viewbook.values():
                v.widget.hide()
            self.gui.toolbar_container.hide()
            self.gui.stbv_combo.get_parent().hide()
        else:
            # Simplified state -> go into full state
            for v in self.viewbook.values():
                v.widget.show()
            self.gui.toolbar_container.show()
            self.gui.stbv_combo.get_parent().show()
        return True

    def on_shotdetect_activate(self, *p):
        if not os.path.exists(config.data.path['shotdetect']):
            dialog.message_dialog(_("The <b>shotdetect</b> application does not seem to be installed. Please check that it is present and that its path is correctly specified in preferences." ), icon=gtk.MESSAGE_ERROR)
            return True
        p=self.controller.player
        movie=self.controller.get_default_media()
        if not movie:
            # No defined movie.
            dialog.message_dialog(_("You first must load a movie into Advene" ), icon=gtk.MESSAGE_ERROR)
            return True
        if not os.path.exists(movie):
            dialog.message_dialog(_("The movie %s does not seem to exist.") % movie, icon=gtk.MESSAGE_ERROR)
            return True

        def do_gui_operation(function, *args, **kw):
            """Execute a method in the main loop.

            Ensure that we execute all Gtk operations in the mainloop.
            """
            def idle_func():
                gtk.gdk.threads_enter()
                try:
                    function(*args, **kw)
                    return False
                finally:
                    gtk.gdk.threads_leave()
            gobject.idle_add(idle_func)

        def import_data(progressbar, filename):
            """Import data from filename.

            filename is either result.xml (shotdetect output) or a
            .txt file (generated from the intermediary data in case of
            cancellation).
            """
            if filename.endswith('result.xml'):
                iname='shotdetect'
            else:
                iname=filename
            try:
                i=advene.util.importer.get_importer(iname, controller=self.controller)
            except Exception:
                dialog.message_dialog(_("Cannot import shotdetect output. Did you install the shotdetect software?"),
                                        icon=gtk.MESSAGE_ERROR,
                                      modal=False)
                return True
            def progress_callback(value=None, label=''):
                progressbar.set_label_value(label or '', value)
                while gtk.events_pending():
                    gtk.main_iteration()
                return True
            i.package=self.controller.package
            i.callback=progress_callback
            i.process_file(filename)
            if filename.endswith('.txt'):
                # Intermediary import. Fix some details.
                at=i.defaulttype
                at.mimetype='application/x-advene-structured'
                at.setMetaData(config.data.namespace, "representation", 'here/content/parsed/num')
                at.title=_("Incomplete shots")
            self.controller.package._modified = True
            self.controller.notify('PackageLoad', package=self.controller.package)
            msg=_("Detected %s shots") % i.statistics['annotation']
            dialog.message_dialog(msg, modal=False)
            self.log(msg)
            return True

        def do_cancel(b, pb, forced=False):
            """Cancel action.

            Close dialog and do various cleanups
            """
            s=getattr(pb, '_source', None)
            if s:
                gobject.source_remove(s)

            # Terminate the process if necessary
            shots=getattr(pb, '_shots', None)
            if shots:
                if config.data.os == 'win32':
                    import ctypes
                    ctypes.windll.kernel32.TerminateProcess(int(shots._handle), -1)
                else:
                    try:
                        # Python 2.6 only
                        shots.terminate()
                    except AttributeError:
                        try:
                            os.kill(shots.pid, 9)
                            os.waitpid(shots.pid, os.WNOHANG)
                        except OSError, e:
                            print "Cannot kill shotdetect", unicode(e)

            # Cleanup temp. dir.
            td=getattr(pb, '_tempdir', None)
            if td and os.path.isdir(td):
                # Remove temp dir.
                shutil.rmtree(td, ignore_errors=True)

            # Process intermediary data if present.
            if forced and pb._datapoints:
                # Shot detection was cancelled, but we got
                # intermediary data points. Convert them anyway.
                (fd, datafile)=tempfile.mkstemp('.txt', text=True)
                pb._datapoints.insert(0, 0)
                pb._datapoints.append(self.controller.cached_duration or (pb._datapoints[-1] + 5000))
                for (i, t) in enumerate(zip( pb._datapoints[:-1], pb._datapoints[1:] )):
                    os.write(fd, '%d %d num=%d\n' % (t[0], t[1], i + 1))
                os.close(fd)
                import_data( pb, datafile )
                os.unlink(datafile)
            pb._window.destroy()
            return True

        def on_shotdetect_end(progressbar):
            # Detection is over. Import resulting file.

            # First disconnect the automatic pulse (win32 only)
            s=getattr(progressbar, '_source', None)
            if s:
                gobject.source_remove(s)
                progressbar._source=None

            filename=os.path.join( progressbar._tempdir, 'result.xml' )
            if os.path.exists(filename):
                # If the file does not exist, it should mean that
                # the process was killed, so cancel was already
                # invoked.
                import_data(progressbar, filename)
                progressbar._datapoints=[]
                do_cancel(None, progressbar)
            return False

        def execute_shotdetect(pb):
            """Execute shotdetect.

            This method is meant to be run in its own thread.
            """
            def subprocess_setup():
                # Python installs a SIGPIPE handler by default. This is usually not what
                # non-Python subprocesses expect.
                signal.signal(signal.SIGPIPE, signal.SIG_DFL)

            shot_re=re.compile('Shot log\s+::\s+(.+)')
            exp_re = re.compile('(\d*\.\d*)e\+(\d+)')

            argv=[ config.data.path['shotdetect'],
                   '-i', gobject.filename_from_utf8(movie.encode('utf8')),
                   '-o', gobject.filename_from_utf8(pb._tempdir.encode('utf8')),
                   '-s', str(pb._sensitivity.get_value_as_int()) ]

            if config.data.os == 'win32':
                kw = { 'creationflags': win32process.CREATE_NO_WINDOW }
            else:
                kw = { 'preexec_fn': subprocess_setup }
            try:
                pb._shots=subprocess.Popen( argv,
                                            bufsize=0,
                                            shell=False,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            **kw )
            except OSError, e:
                do_cancel(None, pb)
                dialog.message_dialog(_("Could not run shotdetect: %s") % unicode(e), modal=False)
                return True

            do_gui_operation(pb.set_label_value,
                             _("Detecting shots from %s") % gobject.filename_display_name(movie),
                             0.01)
            while True:
                l=pb._shots.stderr.readline()
                if not l:
                    break
                ms=shot_re.findall(l)
                if ms:
                    ts=0
                    try:
                        ts=long(ms[0])
                    except ValueError:
                        m=exp_re.match(ms[0])
                        if m:
                            ts=long(float(m.group(1)) * 10 ** int(m.group(2)))

                    pb._datapoints.append(ts)
                    d=self.controller.cached_duration
                    if d > 0:
                        prg=1.0 * ts / d
                    else:
                        prg=None
                    do_gui_operation(pb.set_label_value,
                                     _("Detected shot #%(num)d at %(pos)s ") % {
                            'num': len(pb._datapoints),
                            'pos': helper.format_time_reference(ts)
                            },
                                     prg)

            # Detection is over. Import result
            do_gui_operation(on_shotdetect_end, pb)
            return False

        def do_detect(b, pb):
            b.set_sensitive(False)

            pb._tempdir=unicode(tempfile.mkdtemp('', 'shotdetect'), sys.getfilesystemencoding())
            #~ if config.data.os == 'win32' or self.controller.cached_duration <= 0:
                #~ # Async. reading from a pipe is a mess on win32. A
                #~ # proper fix should be found, but in the meantime,
                #~ # give a feedback to the user.  Do it also when the
                #~ # movie length is unknown, so that the user can know
                #~ # there is activity even if no shot is detected.
                #~ def progress():
                    #~ pb.pulse()
                    #~ return True
                #~ pb._source=gobject.timeout_add(500, progress)

            t=threading.Thread(target=execute_shotdetect, args= [ pb ])
            t.start()
            return True

        w=gtk.Window()
        w.set_title(_("Shot detection"))

        v=gtk.VBox()
        w.add(v)

        l=gtk.Label()
        l.set_markup(_("<b>Shot detection</b>\n\nAdvene will try to detect shots from the currently loaded movie. The threshold parameter is used to specify the sensitivity of the algorithm, and should typically be between 50 and 80. If too many shots are detected, try to augment its value."))
        l.set_line_wrap(True)
        v.pack_start(l, expand=False)

        progressbar=gtk.ProgressBar()

        def set_label_value(s, label='', value=None):
            s.set_text(label)
            if value is None:
                progressbar.pulse()
            else:
                progressbar.set_fraction(value)
            return False
        progressbar.set_label_value=set_label_value.__get__(progressbar)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Sensitivity")), expand=False)
        progressbar._sensitivity=gtk.SpinButton(gtk.Adjustment(60, 5, 95, 1, 5))
        hb.pack_start(progressbar._sensitivity)
        v.pack_start(hb, expand=False)
        v.pack_start(progressbar, expand=False)

        progressbar._window=w
        progressbar._datapoints=[]

        hb=gtk.HBox()

        b=gtk.Button(stock=gtk.STOCK_EXECUTE)
        b.connect('clicked', do_detect, progressbar)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect('clicked', do_cancel, progressbar, True)
        hb.pack_start(b, expand=False)

        v.pack_start(hb, expand=False)
        w.show_all()
        return True

if __name__ == '__main__':
    v = AdveneGUI ()
    try:
        v.main (config.data.args)
    except Exception, e:
        e, v, tb = sys.exc_info()
        print config.data.version_string
        print "Got exception %s. Stopping services..." % str(e)
        v.on_exit ()
        print "*** Exception ***"
        import code
        code.traceback.print_exception (e, v, tb)
