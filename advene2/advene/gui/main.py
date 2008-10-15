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
"""Advene GUI.

This module defines the GUI classes. The main one is L{AdveneGUI},
which is instantiated with a GLADE XML file. It defines the important
methods and the various GUI callbacks (generally all methods with the
C{on_} prefix).

It also defines GUI-specific actions (DisplayPopup, etc).
"""

import sys
import time
import os
import StringIO
import textwrap
import re
import urllib2
import socket
import operator

import advene.core.config as config
import advene.core.version

import gtk
import gtk.glade
import gobject
import pprint

import gettext
import locale

print "Using localedir %s" % config.data.path['locale']

APP='advene'
# Locale initialisation
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    print "Error in locale initialization. Interface translation may be incorrect."
    pass
gettext.bindtextdomain(APP, config.data.path['locale'])
gettext.textdomain(APP)
gettext.install(APP, localedir=config.data.path['locale'], unicode=True)
gtk.glade.bindtextdomain(APP, config.data.path['locale'])
gtk.glade.textdomain(APP)
# The following line is useless, since gettext.install defines _ as a
# builtin. However, code checking applications need to be explicitly
# told that _ is imported.
from gettext import gettext as _

import advene.core.controller

import advene.rules.elements
import advene.rules.ecaengine

from advene.model.cam.package import Package
from advene.model.cam.annotation import Annotation
from advene.model.cam.relation import Relation
from advene.model.cam.view import View
from advene.model.cam.list import Schema
from advene.model.cam.tag import AnnotationType, RelationType
from advene.model.cam.query import Query
import advene.model.consts
import advene.model.tales

import advene.core.mediacontrol
import advene.util.helper as helper
import xml.etree.ElementTree as ET

#import advene.util.importer
from advene.gui.util.completer import Indexer

# GUI elements
from advene.gui.util import get_small_stock_button, image_from_position, dialog, encode_drop_parameters

#import advene.gui.plugins.actions
#import advene.gui.plugins.contenthandlers
#import advene.gui.views.tree
from advene.gui.views import AdhocViewParametersParser
import advene.gui.views.timeline
#import advene.gui.views.activebookmarks
#from advene.gui.edit.rules import EditRuleSet
#from advene.gui.edit.dvdselect import DVDSelect
from advene.gui.edit.elements import get_edit_popup
from advene.gui.edit.create import CreateElementPopup
#from advene.gui.edit.merge import Merger
#from advene.gui.edit.importer import ExternalImporter
from advene.gui.evaluator import Evaluator
from advene.gui.views.accumulatorpopup import AccumulatorPopup
from advene.gui.views.logwindow import LogWindow
#import advene.gui.edit.imports
#import advene.gui.edit.properties
#import advene.gui.edit.montage
#from advene.gui.edit.timeadjustment import TimeAdjustment
from advene.gui.views.viewbook import ViewBook
from advene.gui.views.html import HTMLView
#from advene.gui.views.scroller import ScrollerView
#from advene.gui.views.caption import CaptionView
#import advene.gui.views.annotationdisplay
from simpletal import simpleTAL

class Connect(object):
    """Glade XML interconnection with python class.

    Abstract class defining helper functions to interconnect
    glade XML files and methods of a python class.
    """
    def create_dictionary (self):
        """Create a (name, function) dictionary for the current class."""
        d = {}
        self.create_dictionary_for_class (self.__class__, d)
        return d

    def create_dictionary_for_class (self, a_class, dic):
        """Create a (name, function) dictionary for the specified class."""
        bases = a_class.__bases__
        for iteration in bases:
            self.create_dictionary_for_class (iteration, dic)
        for iteration in dir(a_class):
            dic[iteration] = getattr(self, iteration)

    def connect(self, gui):
        """Connect the class methods with the UI."""
        gui.signal_autoconnect(self.create_dictionary ())

    def gtk_widget_hide (self, widget):
        """Generic hide() method."""
        widget.hide ()
        return True

class AdveneGUI(Connect):
    """Main GUI class.

    Some entry points in the methods:
      - L{__init__} and L{main} : GUI initialization
      - L{update_display} : method regularly called to refresh the display
      - L{on_win_key_press_event} : key press handling

    @ivar gui: the GUI model from libglade
    @ivar gui.logmessages: the logmessages window
    @ivar gui.slider: the slider widget
    @ivar gui.player_status: the player_status widget

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
        self.controller = advene.core.controller.AdveneController()
        self.controller.register_gui(self)

        gladefile=config.data.advenefile (config.data.gladefilename)
        # Glade init.
        self.gui = gtk.glade.XML(gladefile, domain=gettext.textdomain())
        self.connect(self.gui)

        # Resize the main window
        window=self.gui.get_widget('win')
        self.init_window_size(window, 'main')
        window.set_icon_list(*self.get_icon_list())
        self.tooltips = gtk.Tooltips()

        # Last auto-save time (in ms)
        self.last_auto_save=time.time()*1000

        # Frequently used GUI widgets
        self.gui.logmessages = self.gui.get_widget("logmessages")
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

        # Adhoc view toolbuttons signal handling
        def adhoc_view_drag_sent(widget, context, selection, targetType, eventTime, name):
            if targetType == config.data.target_type['adhoc-view']:
                selection.set(selection.target, 8, encode_drop_parameters(name=name))
                return True
            return False

        def open_view(widget, name, destination='popup'):
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
                (_("Open this view..."), 'popup'),
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

        # Generate the adhoc view buttons
        hb=self.gui.get_widget('adhoc_hbox')
        for name, tip, pixmap in (
            ('tree', _('Tree view'), 'treeview.png'),
            ('timeline', _('Timeline'), 'timeline.png'),
            ('transcription', _('Transcription of annotations'), 'transcription.png'),
            ('browser', _('TALES explorer'), 'browser.png'),
            ('finder', _('Package finder'), 'finder.png'),
            ('webbrowser', _('Web browser'), 'web.png'),
            ('transcribe', _('Note-taking editor'), 'transcribe.png'),
            ('editaccumulator', _('Edit window placeholder (annotation and relation edit windows will be put here)'), 'editaccumulator.png'),
            ('bookmarks', _('Bookmarks'), 'bookmarks.png'),
            ('activebookmarks', _('Active bookmarks'), 'activebookmarks.png'),
            ('tagbag', _("Bag of tags"), 'tagbag.png'),
            ('montage', _("Dynamic montage"), 'montage.png'),
            ('schemaeditor', _("Schema editor"), 'schemaeditor.png'),
            ):
            if name in ('browser', 'schemaeditor') and not config.data.preferences['expert-mode']:
                continue
            if name != 'webbrowser' and not name in self.registered_adhoc_views:
                self.log("Missing basic adhoc view %s" % name)
                continue
            b=gtk.Button()
            i=gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            b.add(i)
            self.tooltips.set_tip(b, tip)
            b.connect('drag-data-get', adhoc_view_drag_sent, name)
            b.connect('clicked', open_view_menu, name)
            b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)
            hb.pack_start(b, expand=False)
        hb.show_all()

        self.quicksearch_button=get_small_stock_button(gtk.STOCK_FIND)

        def modify_source(i, expr, label):
            """Modify the quicksearch source, and update the tooltip accordingly.
            """
            config.data.preferences['quicksearch-source']=expr
            self.tooltips.set_tip(self.quicksearch_button, _("Searching on %s.\nLeft click to launch the search, right-click to set the quicksearch options") % label)
            return True

        def quicksearch_options(button, event, method):
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
            submenu=gtk.Menu()
            l=[ (_("All annotations"),
                 None) ] + [
                (_("Annotations of type %s") % self.controller.get_title(at),
                 # FIXME: invalid expression here. We should use iter_elements(p)
                 'here/all/annotation_types/%s/annotations' % at.id) for at in self.controller.package.all.annotation_types ] + [ (_("Views"), 'here/views'), (_("Tags"), 'tags') ]
            for (label, expression) in l:
                i=gtk.CheckMenuItem(label)
                i.set_active(expression == config.data.preferences['quicksearch-source'])
                i.connect('activate', method, expression, label)
                submenu.append(i)
            item.set_submenu(submenu)
            menu.append(item)

            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True

        if config.data.preferences['quicksearch-source'] is None:
            modify_source(None, None, _("All annotations"))
        hb=self.gui.get_widget('search_hbox')
        self.quicksearch_entry=gtk.Entry()
        self.tooltips.set_tip(self.quicksearch_entry, _('String to search'))
        self.quicksearch_entry.connect('activate', self.do_quicksearch)
        hb.pack_start(self.quicksearch_entry, expand=False)
        def modify_source_and_search(i, expr, label):
            """Modify the search source and launch the search.
            """
            modify_source(i, expr, label)
            self.do_quicksearch()
            return True
        self.quicksearch_button.connect('button-press-event', quicksearch_options, modify_source_and_search)
        hb.pack_start(self.quicksearch_button, expand=False, fill=False)
        hb.show_all()

        # Player status
        p=self.controller.player
        self.update_player_labels()
        self.gui.player_status = self.gui.get_widget ("player_status")
        self.oldstatus = "NotStarted"

        self.last_slow_position = 0

        self.current_annotation = None
        # Internal rule used for annotation loop
        self.annotation_loop_rule=None

        # List of active annotation views (timeline, tree, ...)
        self.adhoc_views = []
        # List of active element edit popups
        self.edit_popups = []

        self.edit_accumulator = None

        # Populate default STBV and type lists
        self.update_gui()

    def get_icon_list(self):
        """Return the list of icon pixbuf appropriate for Window.set_icon_list.
        """
        if not hasattr(self, '_icon_list'):
            self._icon_list=[ gtk.gdk.pixbuf_new_from_file(config.data.advenefile(
                        ( 'pixmaps', 'icon_advene%d.png' % size ) ))
                              for size in (16, 32, 48, 64, 128) ]
        return self._icon_list

    def update_player_labels(self):
        """Update the representation of player status.

        They may change when another player is selected.
        """
        p=self.controller.player
        self.active_player_status=(p.PlayingStatus, p.PauseStatus,
                                   p.ForwardStatus, p.BackwardStatus)
        self.statustext={
            p.PlayingStatus  : _("Playing"),
            p.PauseStatus    : _("Pause"),
            p.ForwardStatus  : _("Forward"),
            p.BackwardStatus : _("Backward"),
            p.InitStatus     : _("Init"),
            p.EndStatus      : _("End"),
            p.UndefinedStatus: _("Undefined"),
            }

    def annotation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        annotation=context.evaluate('annotation')
        event=context.evaluate('event')
        if annotation.owner != self.controller.package:
            return True
        for v in self.adhoc_views:
            try:
                v.update_annotation(annotation=annotation, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('EditEnd') or event.endswith('Create'):
            self.controller.package._indexer.element_update(annotation)
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == annotation
                       or e.element in annotation.relations ]:
                # FIXME: annotation.relations does not exist anymore.
                e.refresh()
            # Update the type fieldnames
            if annotation.content.mimetype.endswith('/x-advene-structured'):
                annotation.owner._fieldnames[annotation.type.id].update(helper.common_fieldnames([ annotation ]))

        # Refresh the edit popup for the associated relations
        for e in [ e for e in self.edit_popups if e.element in annotation.relations ]:
            e.refresh()
        return True

    def relation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        relation=context.evaluate('relation')
        event=context.evaluate('event')
        if relation.owner != self.controller.package:
            return True
        for v in self.adhoc_views:
            try:
                v.update_relation(relation=relation, event=event)
            except AttributeError:
                pass
        # Refresh the edit popup for the relation or its members
        for e in [ e for e in self.edit_popups if e.element == relation or e.element in relation ]:
            e.refresh()
        # Refresh the edit popup for the members
        for e in [ e for e in self.edit_popups if e.element in relation ]:
            e.refresh()
        return True

    def view_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        view=context.evaluate('view')
        event=context.evaluate('event')
        if view.owner != self.controller.package:
            return True
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

        # Update the content indexer
        if event.endswith('EditEnd'):
            self.controller.package._indexer.element_update(view)
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == view ]:
                e.refresh()

        return True

    def query_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        query=context.evaluate('query')
        event=context.evaluate('event')
        if query.owner != self.controller.package:
            return True
        for v in self.adhoc_views:
            try:
                v.update_query(query=query, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('EditEnd'):
            self.controller.package._indexer.element_update(query)
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == query ]:
                e.refresh()
        return True

    def resource_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        resource=context.evaluate('resource')
        event=context.evaluate('event')
        if resource.owner != self.controller.package:
            return True

        for v in self.adhoc_views:
            try:
                v.update_resource(resource=resource, event=event)
            except AttributeError:
                pass
        if event.endswith('EditEnd'):
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == resource ]:
                e.refresh()
        return True

    def schema_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        schema=context.evaluate('schema')
        event=context.evaluate('event')
        if schema.owner != self.controller.package:
            return True

        for v in self.adhoc_views:
            try:
                v.update_schema(schema=schema, event=event)
            except AttributeError:
                pass
        if event.endswith('EditEnd'):
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == schema ]:
                e.refresh()
        return True

    def annotationtype_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        at=context.evaluate('annotationtype')
        event=context.evaluate('event')
        if at.owner != self.controller.package:
            return True
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
        if event.endswith('EditEnd'):
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == at ]:
                e.refresh()
        return True

    def relationtype_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        rt=context.evaluate('relationtype')
        event=context.evaluate('event')
        if rt.owner != self.controller.package:
            return True
        for v in self.adhoc_views:
            try:
                v.update_relationtype(relationtype=rt, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('Create'):
            self.controller.package._indexer.element_update(rt)
        if event.endswith('EditEnd'):
            # Refresh the edit popup
            for e in [ e for e in self.edit_popups if e.element == rt ]:
                e.refresh()

        return True

    def handle_element_delete(self, context, parameters):
        """Handle element deletion.

        It notably closes all edit windows for the element.
        """
        event=context.evaluate('event')
        if not event.endswith('Delete'):
            return True
        el=event.replace('Delete', '').lower()
        element=context.evaluate(el)
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
        position_before=context.evaluate('position_before')
        #self.navigation_history.append(position_before)
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

    @property
    def imagecache(self):
        """Return the imagecache for the current media, or None.
        """
        if self.controller.current_media:
            return self.controller.package.imagecache[self.controller.current_media.id]
        else:
            return 

    def main (self, args=None):
        """Mainloop : Gtk mainloop setup.

        @param args: list of arguments
        @type args: list
        """
        if args is None:
            args=[]
        if config.data.os != 'win32':
            try:
                gtk.gdk.threads_init ()
            except RuntimeError:
                print "*** WARNING*** : gtk.threads_init not available.\nThis may lead to unexpected behaviour."

        # FIXME: We have to register LogWindow actions before we load the ruleset
        # but we should have an introspection method to do this automatically
        self.logwindow=LogWindow(controller=self.controller)
        self.register_view(self.logwindow)

        self.visualisationwidget=self.get_visualisation_widget()
        self.gui.get_widget("displayvbox").add(self.visualisationwidget)
        self.gui.get_widget("vpaned").set_position(-1)

        def media_changed(context, parameters):
            if config.data.preferences['expert-mode']:
                return True
            uri=context.globals['uri']
            if not uri:
                msg=_("No media association is defined in the package. Please use the 'File/Select a video file' menuitem to associate a media file.")
            elif not os.path.exists(unicode(uri).encode(sys.getfilesystemencoding(), 'ignore')) and not uri.startswith('http:') and not uri.startswith('dvd'):
                msg=_("The associated media %s could not be found. Please use the 'File/Select a video file' menuitem to associate a media file.") % uri
            else:
                msg=_("You are now working with the following video:\n%s") % uri
            self.controller.queue_action(dialog.message_dialog, msg, modal=False)
            return True

        for events, method in (
            ("PackageLoad", self.manage_package_load),
            ("PackageActivate", self.manage_package_activate),
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
        # The player is initialized. We can register the drawable id
        try:
            if not config.data.player['embedded']:
                raise Exception()
            try:
                self.controller.player.set_widget(self.drawable)
            except AttributeError:
                if config.data.os == 'win32':
                    self.visual_id=self.drawable.window.handle
                else:
                    self.visual_id=self.drawable.window.xid
                self.controller.player.set_visual(self.visual_id)
        except Exception, e:
            self.log("Cannot set visual: %s" % unicode(e))

        # Populate the file history menu
        for filename in config.data.preferences['history']:
            self.append_file_history_menu(filename)

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
                i=gtk.MenuItem(ident)
                i.connect('activate', select_player, p)
                menu.append(i)
                i.show()
                if self.controller.player.player_id == ident:
                    i.set_sensitive(False)
            return True

        menu=gtk.Menu()
        self.gui.get_widget('select_player1').set_submenu(menu)
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
            and time.time() - config.data.preferences['last-update'] >= 24 * 60 * 60):
            config.data.preferences['last-update']=time.time()
            self.check_for_update()
        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        gtk.main ()
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
        data=u.read()
        u.close()
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
        colname=self.controller.get_element_color(element)
        try:
            gtk_color=gtk.gdk.color_parse(colname)
        except:
            gtk_color=None
        d=gtk.ColorSelectionDialog(_("Choose a color"))
        if gtk_color:
            d.colorsel.set_current_color(gtk_color)
        res=d.run()
        if res == gtk.RESPONSE_OK:
            col=d.colorsel.get_current_color()
            element.color=u"string:#%04x%04x%04x" % (col.red,
                                                     col.green,
                                                     col.blue)
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
        b=self.loop_toggle_button
        if self.current_annotation is None:
            mes=_("Select an annotation to loop on it")
        else:
            mes=_("Looping on %s") % self.controller.get_title(self.current_annotation)
        b.set_tooltip(self.tooltips, mes)
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

        if config.data.os == 'win32':
            # gtk.Socket is available on win32 only from gtk >= 2.8
            self.drawable=gtk.DrawingArea()
            # Ignore the delete event, which is sent when the
            # embedded vout dies (i.e. on movie stop)
            self.drawable.connect('delete-event', lambda w, e: True)
        else:
            self.drawable=gtk.Socket()
            def handle_remove(socket):
                # Do not kill the widget if the application exits
                return True
            self.drawable.connect('plug-removed', handle_remove)

        black=gtk.gdk.Color(0, 0, 0)
        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            self.drawable.modify_bg (state, black)

        self.drawable.set_size_request(320, 200)
        self.drawable.add_events(gtk.gdk.BUTTON_PRESS)
        self.drawable.connect_object('button-press-event', self.debug_cb, self.drawable)

        self.player_toolbar=self.get_player_control_toolbar()

        # Dynamic view selection
        hb=gtk.HBox()
        #hb.pack_start(gtk.Label(_('D.view')), expand=False)
        self.gui.stbv_combo = gtk.ComboBox()
        cell = gtk.CellRendererText()
        self.gui.stbv_combo.pack_start(cell, True)
        self.gui.stbv_combo.add_attribute(cell, 'text', 0)
        hb.pack_start(self.gui.stbv_combo, expand=True)

        def new_stbv(*p):
            cr = CreateElementPopup(type_=View,
                                    parent=self.controller.package,
                                    controller=self.controller)
            cr.popup()
            return True
        b=get_small_stock_button(gtk.STOCK_ADD, new_stbv)
        self.tooltips.set_tip(b, _("Create a new dynamic view."))
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
        hb.pack_start(edit_stbv_button, expand=False)

        def on_stbv_combo_changed (combo=None):
            """Callback used to select the current stbv.
            """
            i=combo.get_active_iter()
            if i is None:
                return False
            stbv=combo.get_model().get_value(i, 1)
            if stbv is None:
                self.tooltips.set_tip(edit_stbv_button, _("Create a new dynamic view."))
            else:
                self.tooltips.set_tip(edit_stbv_button, _("Edit the current dynamic view."))
            self.controller.activate_stbv(stbv)
            return True
        self.gui.stbv_combo.connect('changed', on_stbv_combo_changed)
        self.update_stbv_list()

        # Append the volume control to the toolbar
        self.audio_mute=gtk.ToggleToolButton()
        audio_on=gtk.Image()
        audio_on.set_from_file(config.data.advenefile( ( 'pixmaps', 'silk-sound.png') ))
        audio_on.show()
        audio_off=gtk.Image()
        audio_off.set_from_file(config.data.advenefile( ( 'pixmaps', 'silk-sound-mute.png') ))
        audio_off.show()

        def toggle_audio_mute(b):
            """Toggle audio mute status.
            """
            # Set the correct image
            if b.get_active():
                self.controller.player.sound_mute()
                b.set_icon_widget(audio_off)
            else:
                self.controller.player.sound_unmute()
                b.set_icon_widget(audio_on)
            return False

        self.audio_mute.set_icon_widget(audio_on)
        self.audio_mute.connect('toggled', toggle_audio_mute)
        self.audio_mute.set_active(self.controller.player.sound_is_muted())
        self.audio_mute.set_tooltip(self.tooltips, _("Mute/unmute"))
        self.player_toolbar.insert(self.audio_mute, -1)

        # Append the loop checkitem to the toolbar
        def loop_toggle_cb(b):
            """Handle loop button action.
            """
            if b.get_active():
                if self.current_annotation:
                    def action_loop(context, target):
                        if (self.loop_toggle_button.get_active()
                            and context.globals['annotation'] == self.current_annotation):
                            self.controller.update_status('set', self.current_annotation.begin)
                        return True

                    def reg():
                        # If we are already in the current annotation, do not goto it
                        v=self.controller.player.current_position_value
                        if v < self.current_annotation.begin or v > self.current_annotation.end:
                            self.controller.update_status('set', self.current_annotation.begin)
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

        self.loop_toggle_button=gtk.ToggleToolButton(stock_id=gtk.STOCK_REFRESH)
        self.update_loop_button()
        self.loop_toggle_button.connect('toggled', loop_toggle_cb)
        self.player_toolbar.insert(self.loop_toggle_button, -1)

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
        def update_timelabel(s):
            self.time_label.set_text(helper.format_time(s.get_value()))
            return False
        self.gui.slider.connect('value-changed', update_timelabel)

        # Stack the video components
        v=gtk.VBox()
        v.pack_start(hb, expand=False)
        v.pack_start(self.drawable, expand=True)
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
        self.time_label=gtk.Label()
        self.time_label.set_text(helper.format_time(None))
        eb.add(self.time_label)

        def time_pressed(w, event):
            if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                d = gtk.Dialog(title=_("Enter the new time value"),
                               parent=None,
                               flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                               buttons=( gtk.STOCK_OK, gtk.RESPONSE_OK,
                                         gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))

                ta=TimeAdjustment(value=self.gui.slider.get_value(), controller=self.controller, videosync=False, editable=True, compact=False)
                d.vbox.pack_start(ta.widget, expand=False)
                d.show_all()
                dialog.center_on_mouse(d)
                res=d.run()
                retval=None
                if res == gtk.RESPONSE_OK:
                    t=ta.get_value()
                    self.controller.update_status ("set", self.controller.create_position (t))
                d.destroy()
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
        self.pane['main']=self.gui.get_widget('vpaned')

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
        # URL stack is embedded, the menu item is useless :
        self.gui.get_widget('urlstack1').set_property('visible', False)

        # Navigation history
        #self.navigation_history=Bookmarks(controller=self.controller, closable=True, display_comments=False)
        # Navigation history is embedded. The menu item is useless :
        #self.gui.get_widget('navigationhistory1').set_property('visible', False)
        #self.viewbook['west'].add_view(self.navigation_history, name=_("History"), permanent=True)
        # Make the history snapshots + border visible
        self.pane['west'].set_position (config.data.preferences['bookmark-snapshot-width'] + 20)

        # Popup widget
        self.popupwidget=AccumulatorPopup(controller=self.controller,
                                          autohide=False)
        self.viewbook['east'].add_view(self.popupwidget, _("Popups"), permanent=True)

        self.pane['fareast'].show_all()

        self.popupwidget.display_message(_("You can drag and drop view icons (timeline, treeview, transcription...) in this notebook to embed various views."), timeout=10000, title=_("Information"))

        return self.pane['fareast']

    def find_bookmark_view(self):
        l=[ w for w in self.adhoc_views if w.view_id == 'activebookmarks' ]
        if l:
            # There is at least one open view. Use the latest.
            a=l[-1]
        else:
            # No existing view. Create one.
            a=self.open_adhoc_view('activebookmarks', destination='fareast')
            # Make the fareast view visible if needed
            p=self.pane['fareast']
            w=p.get_allocation().width
            if abs(w - p.get_position()) < 30:
                # Less than 50 visible pixels. Enlarge.
                p.set_position(w - 256)
        return a

    def create_bookmark(self, position, insert_after_current=False):
        # Capture a screenshot
        self.controller.update_snapshot(position)
        # Insert an active bookmark
        a=self.find_bookmark_view()

        if a is not None:
            b=a.append(position, after_current=insert_after_current)
            b.grab_focus()
            # We can scroll to the bookmark only after it has
            # been allocated a space (and thus the
            # scroll_to_bookmark method can know its position
            # inside its parent).
            b.widget.connect('size-allocate', lambda w, e: a.scroll_to_bookmark(b) and False)
        return True

    def update_control_toolbar(self, tb=None):
        if tb is None:
            tb=self.player_toolbar
        p=self.controller.player

        buttons=dict( (b.get_stock_id(), b) 
                      for b in tb.get_children()
                      if hasattr(b, 'get_stock_id') )

        if gtk.STOCK_MEDIA_PLAY in buttons and 'record' in p.player_capabilities:
            buttons[gtk.STOCK_MEDIA_PLAY].set_stock_id(gtk.STOCK_MEDIA_RECORD)
        elif gtk.STOCK_MEDIA_RECORD in buttons:
            buttons[gtk.STOCK_MEDIA_RECORD].set_stock_id(gtk.STOCK_MEDIA_PLAY)
        # else: should not happen.

        if 'frame-by-frame' in p.player_capabilities:
            buttons[gtk.STOCK_MEDIA_PREVIOUS].show()
            buttons[gtk.STOCK_MEDIA_NEXT].show()
        else:
            buttons[gtk.STOCK_MEDIA_PREVIOUS].hide()
            buttons[gtk.STOCK_MEDIA_NEXT].hide()
        if hasattr(p, 'fullscreen'):
            buttons[gtk.STOCK_FULLSCREEN].show()
        else:
            buttons[gtk.STOCK_FULLSCREEN].hide()

    def updated_player_cb(self, context, parameter):
        self.update_player_labels()
        p=self.controller.player
        # The player is initialized. We can register the drawable id
        try:
            p.set_widget(self.drawable)
        except AttributeError:
            if config.data.os == 'win32':
                self.visual_id=self.drawable.window.handle
            else:
                self.visual_id=self.drawable.window.xid
            p.set_visual(self.visual_id)
        self.update_control_toolbar(self.player_toolbar)
        # Hook the player control keypress.
        self.controller.player.fullscreen_key_handler = self.process_player_shortcuts

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
        self.controller.move_frame(+1)

    def player_rewind_frame(self, event):
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
        }

    def process_player_shortcuts(self, win, event):
        """Generic player control shortcuts.

        Tab: pause/play
        Control-right/-left: move in the stream
        Control-home/-end: start/end of the stream
        """
        c=self.controller
        p=self.controller.player
        if event.state & gtk.gdk.MOD1_MASK and event.keyval == gtk.keysyms.space:
            self.player_create_bookmark(event)
            return True
        elif event.keyval in self.key_shortcuts:
            self.key_shortcuts[event.keyval](self, event)
            return True
        elif event.state & gtk.gdk.CONTROL_MASK and event.keyval in self.control_key_shortcuts:
            self.control_key_shortcuts[event.keyval](self, event)
            return True
        return False

    def get_player_control_toolbar(self):
        """Return a player control toolbar
        """
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)


        
        # Note: beware, the order of buttons is significant here since
        # they can be updated by the updated_player_cb method. In case
        # of modification, ensure that both methods are still
        # consistent.
        tb_list = [
            (_("Play [Control-Tab / Control-Space]"), gtk.STOCK_MEDIA_PLAY,
             self.on_b_play_clicked),
            (_("Pause [Control-Tab / Control-Space]"), gtk.STOCK_MEDIA_PAUSE,
             self.on_b_pause_clicked),
            (_("Stop"), gtk.STOCK_MEDIA_STOP,
             self.on_b_stop_clicked),
            (_("Rewind (%.02f s) [Control-Left]") % (config.data.preferences['time-increment'] / 1000.0), gtk.STOCK_MEDIA_REWIND,
             self.on_b_rewind_clicked),
            (_("Forward (%.02f s) [Control-Right]" % (config.data.preferences['time-increment'] / 1000.0)), gtk.STOCK_MEDIA_FORWARD,
             self.on_b_forward_clicked),
            (_("Previous frame [Control-Down]"), gtk.STOCK_MEDIA_PREVIOUS, lambda i: self.controller.move_frame(-1)),
            (_("Next frame [Control-Up]"), gtk.STOCK_MEDIA_NEXT, lambda i: self.controller.move_frame(+1)),
            ( (_("Fullscreen"), gtk.STOCK_FULLSCREEN, lambda i: self.controller.player.fullscreen()) )
            ]


        for text, stock, callback in tb_list:
            b=gtk.ToolButton(stock)
            b.set_tooltip(self.tooltips, text)
            b.connect('clicked', callback)
            tb.insert(b, -1)

        tb.show_all()

        # Call update_control_toolbar()
        self.update_control_toolbar(tb)
        return tb

    def loop_on_annotation_gui(self, a, goto=False):
        """Loop over an annotation

        If "goto" is True, then go to the beginning of the annotation
        In addition to the standard "Loop on annotation", it updates a
        checkbox to activate/deactivate looping.
        """
        self.set_current_annotation(a)
        self.loop_toggle_button.set_active(True)
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

    def edit_element(self, element, modal=False):
        """Edit the element.
        """
        if self.edit_accumulator and (
            isinstance(element, Annotation) or isinstance(element, Relation)):
            self.edit_accumulator.edit(element)
            return True

        try:
            pop = get_edit_popup (element, self.controller)
        except TypeError, e:
            print (_(u"Error: unable to find an edit popup for %(element)s:\n%(error)s") % {
                'element': unicode(element),
                'error': unicode(e)}).encode('latin1')
            pop=None
        else:

            pop.edit (modal=modal)
        return pop

    def update_package_list (self):
        """Update the list of loaded packages.
        """
        menu=self.gui.get_widget('package_list_menu')

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
            self.tooltips.set_tip(i, _("Activate %s") % self.controller.get_title(p))
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
                    for i in self.controller.stbv_list ] )
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

    def append_file_history_menu(self, filename):
        """Add the filename at the end of the filemenu Glade widget.
        """
        def open_history_file(button, fname):
            try:
                self.controller.load_package (uri=fname)
            except (OSError, IOError), e:
                dialog.message_dialog(_("Cannot load package %(filename)s:\n%(error)s") % {
                        'filename': fname,
                        'error': unicode(e)}, gtk.MESSAGE_ERROR)
            return True

        # We cannot set the widget name to something more sensible (like
        # filemenu) because Glade resets names when editing the menu
        menu=self.gui.get_widget('menuitem1_menu')
        i=gtk.MenuItem(label=unicode(os.path.basename(filename)), use_underline=False)
        i.connect('activate', open_history_file, filename)
        self.tooltips.set_tip(i, _("Open %s") % filename)

        i.show()
        menu.append(i)

    def build_utbv_menu(self, action=None):
        if action is None:
            action = self.controller.open_url

        def open_utbv(button, u):
            action (u)
            return True

        menu=gtk.Menu()
        for title, url in self.controller.utbv_list:
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
        w=self.gui.get_widget('win')
        d={}
        d['x'], d['y']=w.get_position()
        d['width'], d['height']=w.get_size()
        for k, v in d.iteritems():
            d[k]=unicode(v)
        layout=ET.SubElement(workspace, 'layout', d)
        for n in ('west', 'east', 'fareast', 'south', 'main'):
            ET.SubElement(layout, 'pane', id=n, position=unicode(self.pane[n].get_position()))
        # Now save adhoc views
        for v in self.adhoc_views:
            if not hasattr(v, '_destination'):
                continue
            # Do not save permanent widgets
            if v in self.viewbook[v._destination].permanent_widgets:
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
        if layout and not preserve_layout:
            w=self.gui.get_widget('win')
            w.move(long(layout.attrib['x']), long(layout.attrib['y']))
            w.resize(long(layout.attrib['width']), long(layout.attrib['height']))
            for pane in layout:
                if pane.tag == 'pane':
                    self.pane[pane.attrib['id']].set_position(long(pane.attrib['position']))

    def workspace_save(self, viewid=None):
        """Save the workspace in the given viewid.
        """
        title=_("Saved workspace")
        v=self.controller.package.get(viewid)
        if v is None:
            create=True
            v=self.controller.package.create_view(id=viewid, mimetype='application/x-advene-workspace-view')
        else:
            # Existing view. Overwrite it.
            create=False
        v.title=title

        workspace=self.workspace_serialize()
        helper.indent(workspace)

        stream=StringIO.StringIO()
        ET.ElementTree(workspace).write(stream, encoding='utf-8')
        v.content_data=stream.getvalue()
        stream.close()

        if create:
            self.controller.notify("ViewCreate", view=v)
        else:
            self.controller.notify("ViewEditEnd", view=v)
        return True

    def open_adhoc_view(self, name, label=None, destination='popup', parameters=None, **kw):
        """Open the given adhoc view.

        Destination can be: 'popup', 'south', 'west', 'east', 'fareast' or None.

        In the last case (None), the view is returned initialized, but not
        added to its destination, it is the responsibility of the
        caller to display it and set the _destinaton attribute to the
        correct value.

        If name is a 'view' object, then try to interpret it as a
        application/x-advene-adhoc-view or
        application/x-advene-adhoc-view and open the appropriate view
        with the given parameters.
        """
        view=None
        if isinstance(name, View):
            if name.content.mimetype == 'application/x-advene-workspace-view':
                f=name.content.as_file
                tree=ET.parse(f)
                f.close()

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
            f=name.content.as_file
            p=AdhocViewParametersParser(f)
            f.close()
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
                    kwargs['source']="here/all/annotation_types/%s/annotations/sorted" % at.id
                    if label is None:
                        label=self.controller.get_title(at)
            view = self.registered_adhoc_views[name](**kwargs)
        elif name == 'webbrowser' or name == 'htmlview':
            if destination != 'popup' and HTMLView._engine is not None:
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
            view=get_edit_popup(element, self.controller)
        elif name == 'editaccumulator':
            view=self.registered_adhoc_views[name](controller=self.controller, scrollable=True)
            if not self.edit_accumulator:
                # The first opened accumulator becomes the default one.
                self.edit_accumulator=view
                def handle_accumulator_close(w):
                    self.edit_accumulator = None
                    return False
                self.edit_accumulator.widget.connect('destroy', handle_accumulator_close)
        elif name in self.registered_adhoc_views:
            view=self.registered_adhoc_views[name](controller=self.controller,
                                                   parameters=parameters, **kw)

        if view is None:
            return view
        # Store destination and label, used when moving the view
        view._destination=destination
        view.set_label(label or view.view_name)
        if destination == 'popup':
            w=view.popup(label=label)
            if isinstance(w, gtk.Window):
                dialog.center_on_mouse(w)
        elif destination in ('south', 'east', 'west', 'fareast'):
            self.viewbook[destination].add_view(view, name=label)
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
                                                          len(self.controller.package.all.annotations)),
                'relations': helper.format_element_name('relation',
                                                        len(self.controller.package.all.relations))
                })
        return True

    def manage_package_activate (self, context, parameters):
        self.log(_("Activating package %s") % self.controller.get_title(self.controller.package))
        self.update_gui()

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
        config.data.preferences['quicksearch-source']=None
        pass

    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.

        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        p=context.evaluate('package')
        self.log (_("Package %(uri)s loaded: %(annotations)s and %(relations)s.")
                  % {
                'uri': p.uri,
                'annotations': helper.format_element_name('annotation',
                                                          len(p.all.annotations)),
                'relations': helper.format_element_name('relation',
                                                        len(p.all.relations))
                })

        h=config.data.preferences['history']
        if not p.uri in h and not p.uri.endswith('new_pkg'):
            h.append(p.uri)
            self.append_file_history_menu(p.uri)
            # Keep the 5 last elements
            config.data.preferences['history']=h[-config.data.preferences['history-size-limit']:]

        # Create the content indexer
        p._indexer=Indexer(controller=self.controller,
                           package=p)
        p._indexer.initialize()

        self.controller.queue_action(self.check_for_default_adhoc_view, p)
        return True

    def check_for_default_adhoc_view(self, package):
        # Open the default adhoc view (which is commonly the _default_workspace)
        default_adhoc = package.meta.get( "/".join((config.data.namespace, "default_adhoc") ))
        if default_adhoc is None:
            return False
        view=package.get(default_adhoc)
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
        t=" - ".join((_("Advene"), self.controller.get_title(self.controller.package)))
        if self.controller.package._modified:
            t += " (*)"
        self.gui.get_widget ("win").set_title(t)
        return True

    def log (self, msg, level=None):
        """Add a new log message to the logmessage window.

        @param msg: the message
        @type msg: string
        @param level: the error level
        @type level: int
        """
        buf = self.gui.logmessages.get_buffer ()
        mes = "".join((time.strftime("%H:%M:%S"), " - ", str(msg), "\n"))
        # FIXME: handle level (bold?)
        buf.place_cursor(buf.get_end_iter ())
        buf.insert_at_cursor (mes)
        endmark = buf.create_mark ("end", buf.get_end_iter (), True)
        self.gui.logmessages.scroll_mark_onscreen (endmark)
        return

    def get_illustrated_text(self, text, position=None, vertical=False, height=40):
        """Return a HBox with the given text and a snapshot corresponding to position.
        """
        if vertical:
            box=gtk.VBox()
        else:
            box=gtk.HBox()
        box.add(image_from_position(self.controller,
                                    position=position,
                                    height=height))
        box.add(gtk.Label(text))
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
            try:
                view.register_callback (controller=self.controller)
            except AttributeError:
                pass
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

    def popup_evaluator(self, *p, **kw):
        p=self.controller.package
        try:
            a=p.all.annotations[-1]
        except IndexError:
            a=None
        try:
            at=p.all.annotation_types[-1]
        except IndexError:
            at=None

        ev=Evaluator(globals_=globals(),
                     locals_={'package': p,
                              'p': p,
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
        w=ev.popup()
        self.init_window_size(w, 'evaluator')

        return True

    def update_display (self):
        """Update the interface.

        This method is regularly called by the Gtk mainloop, and
        continually checks whether the interface should be updated.

        Hence, it is a critical execution path and care should be
        taken with the code used here.
        """
        # Synopsis:
        # Ask the controller to update its status
        # If we are moving the slider, don't update the display
        #gtk.threads_enter()
        try:
            pos=self.controller.update()
        except self.controller.player.InternalException:
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
        elif self.controller.player.status in self.active_player_status:
            self.time_label.set_text(helper.format_time(pos))
            # Update the display
            d = self.controller.cached_duration
            if d > 0 and d != self.gui.slider.get_adjustment ().upper:
                self.gui.slider.set_range (0, d)
                self.gui.slider.set_increments (d / 100, d / 10)

            if self.gui.slider.get_value() != pos:
                self.gui.slider.set_value(pos)

            if self.controller.player.status != self.oldstatus:
                self.oldstatus = self.controller.player.status
                self.gui.player_status.set_text(self.statustext.get(self.controller.player.status, _("Unknown")))

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
            self.time_label.set_text(helper.format_time(None))
            if self.controller.player.status != self.oldstatus:
                self.oldstatus = self.controller.player.status
                self.gui.player_status.set_text(self.statustext.get(self.controller.player.status, _("Unknown")))
            # New position_update call to handle the starting case (the first
            # returned status is None)
            self.controller.position_update ()

        return True

    def slow_update_display (self):
        """Update the interface (slow version)

        This method is regularly called by the Gtk mainloop, and
        updates elements with a slower rate than update_display
        """
        mute=self.controller.player.sound_is_muted()
        if self.audio_mute.get_active() != mute:
            self.audio_mute.set_active(mute)

        def do_save(aliases):
            for alias in aliases:
                print "Saving ", alias
                #self.controller.queue_action(self.controller.save_package, None, alias)
                self.controller.save_package(alias=alias)
            return True

        if self.gui.get_widget ("win").get_title().endswith('(*)') ^ self.controller.package._modified:
            self.update_window_title()

        # Check auto-save
        if config.data.preferences['package-auto-save'] != 'never':
            t=time.time() * 1000
            if t - self.last_auto_save > config.data.preferences['package-auto-save-interval']:
                # Need to save
                l=[ alias for (alias, p) in self.controller.packages.iteritems() if p._modified and alias != 'advene' ]
                if l:
                    if config.data.preferences['package-auto-save'] == 'always':
                        self.controller.queue_action(do_save, l)
                    else:
                        # Ask before saving. Use the non-modal dialog
                        # to avoid locking the interface
                        dialog.message_dialog(label=_("""The package(s) %s are modified.\nSave them now?""") % ", ".join(l),
                                              icon=gtk.MESSAGE_QUESTION,
                                              callback=lambda: do_save(l))
                self.last_auto_save=t

        # Fix the webserver reaction time on win32
        if config.data.os == 'win32':
            if self.controller.player.status in self.active_player_status:
                i=config.data.play_interval
            else:
                i=config.data.noplay_interval
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
                                             source=config.data.preferences['quicksearch-source'],
                                             case_sensitive=not config.data.preferences['quicksearch-ignore-case'])

    def do_quicksearch(self, *p):
        s=self.quicksearch_entry.get_text()
        if not s:
            self.log(_("Empty quicksearch string"))
            return True
        res=self.search_string(unicode(s))
        label=_("'%s'") % s
        self.open_adhoc_view('interactiveresult', destination='east', result=res, label=label, query=s)
        return True

    def ask_for_annotation_type(self, text=None, create=False, force_create=False):
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
            ats=list(self.controller.package.all.annotation_types)
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
                preselect=None
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
            self.tooltips.set_tip(new_type_title_dialog.title_entry, _("Title of the new type"))
            self.tooltips.set_tip(new_type_title_dialog.id_entry, _("Id of the new type. It is generated from the title, but you may change it if necessary."))
            new_type_dialog.pack_start(new_type_title_dialog, expand=False)
            # Mimetype
            type_list=(
                ('text/plain', _("Plain text content")),
                ('application/x-advene-structured', _("Simple-structured content")),
                ('application/x-advene-zone', _("Rectangular zone content")),
                ('image/svg+xml', _("SVG graphics content")),
                )

            mimetype_selector = dialog.list_selector_widget(members=type_list, entry=True)
            self.tooltips.set_tip(mimetype_selector, _("Specify the content-type for the annotation type"))

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
            self.tooltips.set_tip(schema_selector, _("Choose an existing schema for the new type, or create a new one"))
            new_type_title_dialog.attach(schema_selector, 1, 2, 3, 4)
            new_type_title_dialog.attach(new_schema_dialog, 1, 2, 4, 5)
            new_schema_dialog.pack_start(gtk.Label(_("Specify the schema title")), expand=False)
            ident=self.controller.package._idgenerator.get_id(Schema)
            new_schema_title_dialog=dialog.title_id_widget(element_title=ident,
                                                           element_id=ident)
            self.tooltips.set_tip(new_schema_title_dialog.title_entry, _("Title of the new schema"))
            self.tooltips.set_tip(new_schema_title_dialog.id_entry, _("Id of the new schema. It is generated from the title, but you may change it if necessary."))
            new_schema_dialog.pack_start(new_schema_title_dialog, expand=False)

        d.vbox.show_all()
        if force_create:
            new_type_title_dialog.title_entry.grab_focus()
            type_selector.hide()
        else:
            new_type_dialog.hide()
        new_schema_dialog.hide()

        d.show()
        dialog.center_on_mouse(d)
        res=d.run()
        if res == gtk.RESPONSE_OK:
            at=type_selector.get_current_element()
            if at == newat:
                # Creation of a new type.
                attitle=new_type_title_dialog.title_entry.get_text()
                atid=new_type_title_dialog.id_entry.get_text()
                at=self.controller.package.get(atid)
                if at is not None:
                    dialog.message_dialog(_("You specified a annotation-type identifier that already exists. Aborting."))
                    d.destroy()
                    return None
                sc=schema_selector.get_current_element()
                if sc == newschema:
                    sctitle=new_schema_title_dialog.title_entry.get_text()
                    scid=new_schema_title_dialog.id_entry.get_text()
                    sc=self.controller.package.get(scid)
                    if sc is None:
                        # Create the schema
                        sc=self.controller.package.create_schema(id=scid)
                        sc.title=sctitle
                        self.controller.notify('SchemaCreate', schema=sc)
                    elif isinstance(sc, Schema):
                        # Warn the user that he is reusing an existing one
                        dialog.message_dialog(_("You specified a existing schema identifier. Using the existing schema."))
                    else:
                        dialog.message_dialog(_("You specified an existing identifier that does not reference a schema. Aborting."))
                        d.destroy()
                        return None
                # Create the type
                at=sc.create_annotation_type(id=atid)
                at.title=attitle
                at.mimetype=mimetype_selector.get_current_element()
                at.color=self.controller.package._color_palette.next()
                at.element_color='here/tag_color'
                self.controller.notify('AnnotationTypeCreate', annotationtype=at)
                self.edit_element(at, modal=True)
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
                sctitle=new_schema_title_dialog.title_entry.get_text()
                scid=new_schema_title_dialog.id_entry.get_text()
                sc=self.controller.package.get(scid)
                if sc is None:
                    # Create the schema
                    sc=self.controller.package.create_schema(id=scid)
                    sc.title=sctitle
                    self.controller.notify('SchemaCreate', schema=sc)
                    self.edit_element(sc, modal=True)
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
        # Make the fareast view visible if needed
        p=self.pane['fareast']
        w=p.get_allocation().width
        if abs(w - p.get_position()) < 30:
            # Less than 50 visible pixels. Enlarge.
            p.set_position(w - 256)
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

            ic=self.imagecache
            if ic and ic._modified and config.data.preferences['imagecache-save-on-exit'] != 'never':
                if config.data.preferences['imagecache-save-on-exit'] == 'ask':
                    media=self.controller.get_current_mediafile(package=p)
                    response=dialog.yes_no_cancel_popup(title=_("%s snapshots") % media,
                                                             text=_("Do you want to save the snapshots for media %s?") % media)
                    if response == gtk.RESPONSE_CANCEL:
                        return True
                    elif response == gtk.RESPONSE_YES:
                        try:
                            ic.save (helper.mediafile2id (media))
                        except OSError, e:
                            self.log(_("Cannot save imagecache for %(media)s: %(e)s") % locals())
                    elif response == gtk.RESPONSE_NO:
                        ic._modified=False
                        pass
                elif config.data.preferences['imagecache-save-on-exit'] == 'always':
                    media=self.controller.get_current_mediafile(package=p)
                    try:
                        ic.save (helper.mediafile2id (media))
                    except OSError, e:
                        self.log(_("Cannot save imagecache for %(media)s: %(e)s") % locals())

        if self.controller.on_exit():
            # Memorize application window size/position
            self.resize_cb(self.gui.get_widget('win'), None, 'main')
            gtk.main_quit()
            return False
        else:
            return True

    # Callbacks function. Skeletons can be generated by glade2py

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
            elif event.keyval == gtk.keysyms.a:
                # EditAccumulator popup
                self.popup_edit_accumulator()
                return True
            elif event.keyval == gtk.keysyms.k:
                # Get the cursor in the quicksearch entry
                self.quicksearch_entry.grab_focus()
                self.quicksearch_entry.select_region(0, -1)
                return True
            elif event.keyval == gtk.keysyms.z:
                try:
                    self.controller.undomanager.undo()
                except AttributeError:
                    pass
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
            if not ext in ('.xml', '.apl', '.czp'):
                # Does not look like a valid package
                if not dialog.message_dialog(_("The file %s does not look like a valid Advene package. It should have a .czp or .xml extension. Try to open anyway?") % filename,
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
                self.controller.load_package (uri=filename, alias=alias)
            except (OSError, IOError), e:
                dialog.message_dialog(_("Cannot load package %(filename)s:\n%(error)s") % {
                        'filename': filename,
                        'error': unicode(e)}, gtk.MESSAGE_ERROR)
        return True

    def on_save1_activate (self, button=None, package=None):
        """Save the current package."""
        if package is None:
            package=self.controller.package
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
                default = package.meta.get( "/".join( (config.data.namespace, "default_adhoc") ) )
                if not default:
                    self.controller.package.setMetaData (config.data.namespace, "default_adhoc", '_default_workspace')
            alias=self.controller.aliases[package]
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
                filename = filename + '.czp'

            if os.path.exists(filename):
                if dialog.message_dialog(_("The file %s already exists. Overwrite it?") % filename,
                                         icon=gtk.MESSAGE_QUESTION):
                    os.remove(filename)
                else:
                    self.log(_("Cancelled package saving."))
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
                default = package.meta.get( "/".join((config.data.namespace, "default_adhoc") ))
                if not default:
                    self.controller.package.setMetaData (config.data.namespace, "default_adhoc", '_default_workspace')
            alias=self.controller.aliases[package]
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
        if (self.controller.get_current_mediafile() is None
            or 'dvd' in self.controller.get_current_mediafile()):
            if not dialog.message_dialog(
                _("Do you confirm the creation of annotations matching the DVD chapters?"),
                icon=gtk.MESSAGE_QUESTION):
                return True
#            try:
#                i=advene.util.importer.get_importer('lsdvd', controller=self.controller)
#            except Exception:
#                dialog.message_dialog(_("Cannot import DVD chapters. Did you install the lsdvd software?"),
#                                        icon=gtk.MESSAGE_ERROR)
            # FIXME: reimplement
            dialog.message_dialog(_("Cannot import DVD chapters. Did you install the lsdvd software?"),
                                  icon=gtk.MESSAGE_ERROR)
            
            #i.package=self.controller.package
            #i.process_file('lsdvd')
            #self.controller.package._modified = True
            #self.controller.notify('PackageLoad', package=self.controller.package)
        else:
            dialog.message_dialog(_("The associated media is not a DVD."),
                                           icon=gtk.MESSAGE_ERROR)
        return True

    def on_import_file1_activate (self, button=None, data=None):
        v=ExternalImporter(controller=self.controller)
        w=v.popup()
        dialog.center_on_mouse(w)
        return False

    def on_undo1_activate (self, button=None, data=None):
        try:
            self.controller.undomanager.undo()
        except AttributeError:
            pass
        return True

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

        vbox=gtk.VBox()
        vbox.set_homogeneous (False)
        w.add(vbox)

        rs = self.controller.event_handler.get_ruleset('default')
        edit=EditRuleSet(rs,
                         catalog=self.controller.event_handler.catalog,
                         controller=self.controller)
        vbox.add(edit.get_widget())
        edit.get_widget().show()

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

        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect('clicked', edit.add_rule_cb)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.connect('clicked', edit.remove_rule_cb)
        hb.pack_start(b, expand=False)

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
        w=gtk.Window()

        def refresh(b, t):
            b=t.get_buffer()
            b.delete(*b.get_bounds ())
            f=open(config.data.advenefile('webserver.log', 'settings'), 'r')
            b.set_text("".join(f.readlines()))
            f.close()
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

        if self.controller.gui:
            self.controller.gui.init_window_size(w, 'weblogview')

        w.show_all()

        return True

    def on_navigationhistory1_activate (self, button=None, data=None):
        #FIXME
        #h=Bookmarks(self.controller, self.navigation_history, closable=False)
        h.popup()
        return True

    def on_view_mediainformation_activate (self, button=None, data=None):
        """View mediainformation."""
        self.controller.position_update ()
        self.log (_("**** Media information ****"))
        self.log (_("Cached duration   : %(time)s (%(ms)d ms)") % {
                'time': helper.format_time(self.controller.cached_duration),
                'ms': self.controller.cached_duration })
        if self.controller.player.is_active():
            self.log (_("Current playlist : %s") % str(self.controller.player.playlist_get_list ()))
            self.log (_("Current position : %(time)s (%(ms)d ms)") % {
                    'time': helper.format_time(self.controller.player.current_position_value),
                    'ms': self.controller.player.current_position_value})
            self.log (_("Duration         : %(time)s (%(ms)d ms)") % {
                    'time': helper.format_time(self.controller.player.stream_duration),
                    'ms': self.controller.player.stream_duration })
            self.log (_("Status           : %s") % self.statustext[self.controller.player.status])
        else:
            self.log (_("Player not active."))
        return True

    def on_about1_activate (self, button=None, data=None):
        """Activate the About window."""
        gtk.about_dialog_set_url_hook(lambda dialog, link: self.controller.open_url(link))
        d=gtk.AboutDialog()
        d.set_name('Advene')
        d.set_version(config.data.version_string.replace('Advene ', ''))
        d.set_copyright("Copyright 2002-2008 Olivier Aubert, Pierre-Antoine Champin")
        d.set_license(_('GNU General Public License\nSee http://www.gnu.org/copyleft/gpl.html for more details'))
        d.set_website('http://liris.cnrs.fr/advene/')
        d.set_website_label(_('Visit the Advene web site for examples and documentation.'))
        d.set_authors( [ 'Olivier Aubert', 'Pierre-Antoine Champin', 'Yannick Prie', 'Bertrand Richard', 'Frank Wagner' ] )
        d.set_logo(gtk.gdk.pixbuf_new_from_file(config.data.advenefile( ( 'pixmaps', 'logo_advene.png') )))
        d.connect('response', lambda w, r: w.destroy())
        d.run()

        return True

    def on_b_rewind_clicked (self, button=None, data=None):
        if self.controller.player.status == self.controller.player.PlayingStatus:
            self.controller.move_position (-config.data.preferences['time-increment'],
                                            notify=False)
        return True

    def on_b_play_clicked (self, button=None, data=None):
        if self.controller.player.status == self.controller.player.PauseStatus:
            self.controller.update_status ("resume")
        elif self.controller.player.status != self.controller.player.PlayingStatus:
            self.controller.update_status ("start")
        return True

    def on_b_pause_clicked (self, button=None, data=None):
        self.controller.update_status ("pause")
        return True

    def on_b_stop_clicked (self, button=None, data=None):
        self.controller.update_status ("stop")
        return True

    def on_b_forward_clicked (self, button=None, data=None):
        if self.controller.player.status == self.controller.player.PlayingStatus:
            self.controller.move_position (config.data.preferences['time-increment'],
                                           notify=False)
        return True

    def on_b_addfile_clicked (self, button=None, data=None):
        """Open a movie file"""
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None

        filename=dialog.get_filename(title=_("Select a movie file"),
                                     action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                     button=gtk.STOCK_OPEN,
                                     default_dir=d,
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
                      current=self.controller.get_current_mediafile())
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
            'creator': self.controller.package.creator,
            'created': self.controller.package.created,
            'contributor': self.controller.package.contributor,
            'modified': self.controller.package.modified,
            'media': self.controller.get_current_mediafile() or "",
            'duration': str(self.controller.package.cached_duration),
            'title': self.controller.package.title or ""
            }
        def reset_duration(b, entry):
            # FIXME
            v=long(self.controller.player.stream_duration)
            entry.set_text(str(v))
            return True

        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Package properties"))
        ew.add_entry(_("Creator"), "creator", _("Author name"))
        ew.add_entry(_("Created"), "created", _("Package creation date"))
        ew.add_entry(_("Contributor"), "contributor", _("Contributor name"))
        ew.add_entry(_("Contributed"), "modified", _("Package modification date"))
        ew.add_entry(_("Title"), "title", _("Package title"))
        # FIXME: allow to manipulate Media instances
        ew.add_file_selector(_("Associated media"), 'media', _("Select a movie file"))
        ew.add_entry_button(_("Duration"), "duration", _("Media duration in ms"), _("Reset"), reset_duration)

        res=ew.popup()

        if res:
            self.controller.package.creator = cache['creator']
            self.controller.package.created = cache['created']
            self.controller.package.contributor = cache['contributor']
            self.controller.package.contributed = cache['contributed']
            self.controller.package.title = cache['title']
            self.update_window_title()
            self.controller.set_default_media(cache['media'])
            try:
                self.controller.package.cached_duration = long(cache['duration'])
            except ValueError, e:
                print "Cannot convert duration", str(e)
                pass
        return True

    def on_preferences1_activate (self, button=None, data=None):
        direct_options=('history-size-limit', 'scroll-increment', 'second-scroll-increment',
                        'time-increment', 'second-time-increment', 'language',
                        'display-scroller', 'display-caption', 'imagecache-save-on-exit',
                        'remember-window-size', 'expert-mode', 'update-check',
                        'package-auto-save', 'package-auto-save-interval',
                        'bookmark-snapshot-width', 'bookmark-snapshot-precision',
                        'save-default-workspace', 'restore-default-workspace',
                        'tts-language', )
        cache={
            'toolbarstyle': self.gui.get_widget("toolbar_fileop").get_style(),
            'data': config.data.path['data'],
            'plugins': config.data.path['plugins'],
            'advene': config.data.path['advene'],
            'imagecache': config.data.path['imagecache'],
            'moviepath': config.data.path['moviepath'],
            'font-size': config.data.preferences['timeline']['font-size'],
            'button-height': config.data.preferences['timeline']['button-height'],
            'interline-height': config.data.preferences['timeline']['interline-height'],
            }
        for k in direct_options:
            cache[k] = config.data.preferences[k]
        ew=advene.gui.edit.properties.EditNotebook(cache.__setitem__, cache.get)
        ew.set_name(_("Preferences"))

        ew.add_title(_("GUI"))
        ew.add_option(_("Interface language (after restart)"), 'language', _("Language used for the interface (necessitates to restart the application)"),
                      {
                "English": 'C',
                "Francais": 'fr_FR',
                _("System default"): '',
                })
        ew.add_spin(_("History size"), "history-size-limit", _("History filelist size limit"),
                    -1, 20)
        ew.add_checkbox(_("Remember window size"), "remember-window-size", _("Remember the size of opened windows"))
        ew.add_option(_("Toolbar style"), "toolbarstyle", _("Toolbar style"),
                      { _('Icons only'): gtk.TOOLBAR_ICONS,
                        _('Text only'): gtk.TOOLBAR_TEXT,
                        _('Both'): gtk.TOOLBAR_BOTH,
                        }
                     )
        ew.add_checkbox(_("Expert mode"), "expert-mode", _("Offer advanced possibilities"))
        ew.add_spin(_("Bookmark snapshot width"), 'bookmark-snapshot-width', _("Width of the snapshots representing bookmarks"), 50, 400)
        ew.add_spin(_("Bookmark snapshot precision"), 'bookmark-snapshot-precision', _("Precision (in ms) of the displayed bookmark snapshots."), 25, 500)

        ew.add_title(_("Time-related"))
        ew.add_spin(_("Time increment"), "time-increment", _("Skip duration, when using control-left/right or forward/rewind buttons (in ms)."), 100, 30000)
        ew.add_spin(_("Second time increment"), "second-time-increment", _("Skip duration, when using control-shift-left/right (in ms)."), 100, 30000)
        ew.add_spin(_("Scroll increment"), "scroll-increment", _("On most annotations, control+scrollwheel will increment/decrement their bounds by this value (in ms)."), 10, 10000)
        ew.add_spin(_("Second scroll increment"), "second-scroll-increment", _("On most annotations, control+shift+scrollwheel will increment/decrement their bounds by this value (in ms)."), 10, 10000)

        ew.add_title(_("General"))
        ew.add_checkbox(_("Daily update check"), 'update-check', _("Daily check for updates on the Advene website"))
        ew.add_option(_("On exit,"), 'imagecache-save-on-exit',
                      _("How to handle screenshots on exit"),
                      {
                _("never save screenshots"): 'never',
                _("always save screenshots"): 'always',
                _("ask before saving screenshots"): 'ask',
                })
        ew.add_option(_("Auto-save"), 'package-auto-save',
                      _("Data auto-save functionality"),
                      {
                _("is desactivated"): 'never',
                _("is done automatically"): 'always',
                _("is done after confirmation"): 'ask',
                })
        ew.add_spin(_("Auto-save interval"), 'package-auto-save-interval', _("Interval (in ms) between package auto-saves"), 1000, 60 * 60 * 1000)

        ew.add_title(_("Standard views"))

        ew.add_option(_("On package saving,"), 'save-default-workspace',
                      _("Do you wish to save the default workspace with the package?"),
                      {
                _("never save the current workspace"): 'never',
                _("always save the current workspace"): 'always',
                _("ask before saving the current workspace"): 'ask',
                })

        ew.add_option(_("On package load,"), 'restore-default-workspace',
                      _("Do you wish to load the workspace saved with the package?"),
                      {
                _("never load the saved workspace"): 'never',
                _("always load the saved workspace"): 'always',
                _("ask before loading the saved workspace"): 'ask',
                })

        ew.add_checkbox(_("Scroller"), 'display-scroller', _("Embed the caption scroller below the video"))
        ew.add_checkbox(_("Caption"), 'display-caption', _("Embed the caption view below the video"))

        ew.add_title(_("Paths"))

        ew.add_dir_selector(_("Data"), "data", _("Standard directory for data files"))
        ew.add_dir_selector(_("Movie path"), "moviepath", _("List of directories (separated by %s) to search for movie files (_ means package directory)") % os.path.pathsep)
        ew.add_dir_selector(_("Imagecache"), "imagecache", _("Directory for storing the snapshot cache"))
        ew.add_dir_selector(_("Player"), "plugins", _("Directory of the video player"))

        ew.add_title(_("Timeline parameters"))
        ew.add_spin(_("Font size"), 'font-size', _("Font size for annotation widgets"), 4, 20)
        ew.add_spin(_("Button height"), 'button-height', _("Height of annotation widgets"), 10, 50)
        ew.add_spin(_("Interline height"), 'interline-height', _("Height of interlines"), 0, 40)

        ew.add_title(_("Text-To-Speech"))
        ew.add_option(_("TTS language"), 'tts-language',
                      _("What language settings should be used for text-to-speech"),
                      {
                _("French"): 'fr',
                _("English"): 'en',
                _("Esperanto"): 'eo',
                _("Spanish"): 'es',
                })

        res=ew.popup()
        if res:
            for k in direct_options:
                config.data.preferences[k] = cache[k]
            self.gui.get_widget('toolbar_fileop').set_style(cache['toolbarstyle'])
            for k in ('font-size', 'button-height', 'interline-height'):
                config.data.preferences['timeline'][k] = cache[k]
            for k in ('data', 'moviepath', 'plugins', 'imagecache', 'advene'):
                if cache[k] != config.data.path[k]:
                    config.data.path[k]=cache[k]
                    # Store in auto-saved preferences
                    config.data.preferences['path'][k]=cache[k]
                    if k == 'plugins':
                        self.controller.restart_player()
            # Save preferences
            config.data.save_preferences()

        return True

    def on_configure_player1_activate (self, button=None, data=None):
        cache={
            'width': config.data.player['snapshot-dimensions'][0],
            'height': config.data.player['snapshot-dimensions'][1],
            'level': config.data.player['verbose'] or -1,
            }
        items=('caption', 'osdfont', 'snapshot', 'vout', 'svg', 'dvd-device')
        for n in items:
            cache[n] = config.data.player[n]

        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Player configuration"))
        ew.add_title(_("Captions"))
        ew.add_checkbox(_("Enable"), "caption", _("Enable video captions"))
        ew.add_file_selector(_("Font"), "osdfont", _("TrueType font for captions"))
        ew.add_checkbox(_("Enable SVG"), "svg", _("Enable SVG captions"))

        ew.add_title(_("Snapshots"))
        ew.add_checkbox(_("Enable"), "snapshot", _("Enable snapshots"))
        ew.add_spin(_("Width"), "width", _("Snapshot width"), 0, 1280)
        ew.add_spin(_("Height"), "height", _("Snapshot height"), 0, 1280)

        ew.add_title(_("Video"))
        options={_("Standard"): 'default' }
        if config.data.os == 'win32':
            ew.add_entry(_("DVD drive"), 'dvd-device', _("Drive letter for the DVD"))
            options[_("GDI")] = 'wingdi'
            options[_("Direct X")] = 'directx'
        else:
            ew.add_entry(_("DVD device"), 'dvd-device', _("Device for the DVD"))
            options[_("X11")] = 'x11'
            options[_("XVideo")] = 'xvideo'
        ew.add_option(_("Output"), "vout", _("Video output module"), options)

        ew.add_title(_("Verbosity"))
        ew.add_spin(_("Level"), "level", _("Verbosity level. -1 for no messages."),
                    -1, 3)

        res=ew.popup()
        if res:
            for n in items:
                config.data.player[n] = cache[n]
            config.data.player['snapshot-dimensions']    = (cache['width'] ,
                                                            cache['height'])
            if cache['level'] == -1:
                config.data.player['verbose'] = None
            else:
                config.data.player['verbose'] = cache['level']
            self.controller.restart_player ()
        return True

    def on_save_imagecache1_activate (self, button=None, data=None):
        media = self.controller.current_media
        d=self.controller.package.imagecache[media].save (helper.mediafile2id(media.id))
        self.log(_("Imagecache saved to %s") % d)
        return True

    def on_restart_player1_activate (self, button=None, data=None):
        self.log (_("Restarting player..."))
        self.controller.restart_player ()
        try:
            self.controller.player.set_widget(self.drawable)
        except AttributeError:
            if self.visual_id:
                self.controller.player.set_visual(self.visual_id)
        return True

    def on_slider_button_press_event (self, button=None, data=None):
        self.slider_move = True
        return False

    def on_slider_button_release_event (self, button=None, data=None):
        if self.controller.player.playlist_get_list():
            p = self.controller.create_position (value = long(self.gui.slider.get_value ()))
            self.controller.update_status('set', p)
        self.slider_move = False
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
            self.log(_("Unable to find the help file at %s") % helpfile)
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
        self.edit_element(at, modal=True)
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
            self.log("Cannot load %s file: %s" % (filename, unicode(e)))
            return True
        m=Merger(self.controller, sourcepackage=source, destpackage=self.controller.package)
        m.popup()
        return True

    def on_save_workspace_as_package_view1_activate (self, button=None, data=None):
        name=self.controller.package._idgenerator.get_id(View)+'_'+'workspace'
        title, ident=dialog.get_title_id(title=_("Saving workspace"),
                                  element_title=name,
                                  element_id=name,
                                  text=_("Enter a view name to save the workspace"))
        if ident is None:
            return True

        if not re.match(r'^[a-zA-Z0-9_]+$', ident):
            dialog.message_dialog(_("Error: the identifier %s contains invalid characters.") % ident)
            return True

        v=self.controller.package.get(ident)
        if v is None:
            create=True
            v=self.controller.package.create_view(ident=ident, mimetype='application/x-advene-workspace-view')
        else:
            # Existing view. Check that it is already an workspace-view
            if v.content.mimetype != 'application/x-advene-workspace-view':
                dialog.message_dialog(_("Error: the view %s exists and is not a workspace view.") % ident)
                return True
            create=False
        v.title=title

        workspace=self.workspace_serialize()
        stream=StringIO.StringIO()
        helper.indent(workspace)
        ET.ElementTree(workspace).write(stream, encoding='utf-8')
        v.content.data=stream.getvalue()
        stream.close()

        if create:
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

    def on_export_activate (self, button=None, data=None):
        importer_package=Package(url=config.data.advenefile('exporters.xml'))

        def generate_default_filename(filter, filename=None):
            """Generate a filename for the given filter.
            """
            if filename is None:
                # Get the current package title.
                filename=self.controller.package.title
                if filename == 'Template package':
                    # Use a better name
                    filename=os.path.splitext(os.path.basename(self.controller.package.uri))[0]
                filename=helper.title2id(filename)
            else:
                # A filename was provided. Strip the extension.
                filename=os.path.splitext(filename)[0]
            # Add a pertinent extension
            if filter is None:
                return filename
            ext=filter.meta.get("/".join( (config.data.namespace, 'extension') ) )
            if not ext:
                ext = helper.title2id(filter.id)
            return '.'.join( (filename, ext) )

        fs = gtk.FileChooserDialog(title=_("Export package data"),
                                   parent=self.gui.get_widget('win'),
                                   action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                   buttons=( gtk.STOCK_CONVERT, gtk.RESPONSE_OK,
                                             gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL ))
        def update_extension(sel):
            filter=sel.get_current_element()
            f=generate_default_filename(filter, os.path.basename(fs.get_filename()))
            fs.set_current_name(f)
            return True
        exporters=dialog.list_selector_widget(sorted(( ( v, v.title )
                                                       for v in importer_package.views
                                                       if v.id != 'index' ), key=operator.itemgetter(1)),
                                              callback=update_extension)
        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Export format")), expand=False)
        hb.pack_start(exporters)
        fs.set_extra_widget(hb)

        fs.show_all()
        fs.set_current_name(generate_default_filename(exporters.get_current_element()))
        self.fs=fs
        res=fs.run()

        if res == gtk.RESPONSE_OK:
            filter=exporters.get_current_element()
            filename=fs.get_filename()
            ctx=self.controller.build_context()

            try:
                stream=open(filename, 'wb')
            except Exception, e:
                self.log(_("Cannot export to %(filename)s: %(e)s") % locals())
                return True

            kw = {}
            f=filter.content.as_file            
            if filter.content.mimetype is None or filter.content.mimetype.startswith('text/'):
                compiler = simpleTAL.HTMLTemplateCompiler()
                compiler.parseTemplate(f, 'utf-8')
                compiler.getTemplate().expand (context=ctx, outputFile=stream, outputEncoding='utf-8')
            else:
                compiler = simpleTAL.XMLTemplateCompiler ()
                compiler.parseTemplate(f)
                compiler.getTemplate().expand (context=ctx, outputFile=stream, outputEncoding='utf-8', suppressXMLDeclaration=True)
            f.close()
            stream.close()
            self.log(_("Data exported to %s") % filename)
        fs.destroy()
        return True

    def generate_screenshots(self, *p):
        """Generate screenshots.
        """
        c=self.controller
        p=c.player
        ic=self.imagecache
        if ic is None:
            self.log("No media defined")
            return True

        def do_cancel(b, pb):
            if pb.event_source_generate is not None:
                gobject.source_remove(pb.event_source_generate)
            
            ic.autosync=pb.old_autosync

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
                ic[p.current_position_value] = helper.snapshot2png (i)
                prg=1.0 * p.current_position_value / p.stream_duration
                pb.set_fraction(prg)
                pb.set_text(helper.format_time(p.current_position_value))
                if prg > .999:
                    do_cancel(None, pb)
            return True

        def do_generate(b, pb):
            b.set_sensitive(False)
            # Deactivate the GUI update method
            gobject.source_remove(self.event_source_update_display)
            gobject.source_remove(self.event_source_slow_update_display)

            # Make the imagecache directly store data on disk
            pb.old_autosync=ic.autosync
            ic.autosync=True
            if ic.name is None:
                ic.name=helper.mediafile2id(c.get_current_mediafile())

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
        progressbar.old_autosync=ic.autosync
        hb=gtk.HBox()

        b=gtk.Button(stock=gtk.STOCK_MEDIA_RECORD)
        b.connect('clicked', do_generate, progressbar)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect('clicked', do_cancel, progressbar)
        hb.pack_start(b, expand=False)

        v.pack_start(hb, expand=False)
        print "Showing window"
        w.show_all()
        w.set_modal(True)

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
