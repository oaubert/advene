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
from sets import Set
import re
import cgi

import advene.core.config as config

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

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.query import Query
import advene.model.constants
import advene.model.tal.context

import advene.core.mediacontrol
import advene.util.helper as helper
import advene.util.ElementTree as ET

import advene.util.importer
from advene.gui.util.completer import Indexer

# GUI elements
from advene.gui.util import get_small_stock_button, image_from_position, dialog
import advene.gui.plugins.actions
import advene.gui.plugins.contenthandlers
import advene.gui.views.tree
from advene.gui.views import AdhocViewParametersParser
import advene.gui.views.timeline
import advene.gui.views.table
import advene.gui.views.logwindow
import advene.gui.views.interactivequery
from advene.gui.views.history import HistoryNavigation
from advene.gui.edit.rules import EditRuleSet
from advene.gui.edit.dvdselect import DVDSelect
from advene.gui.edit.elements import get_edit_popup
from advene.gui.edit.create import CreateElementPopup
from advene.gui.edit.merge import Merger
from advene.gui.edit.importer import ExternalImporter
from advene.gui.evaluator import Evaluator
from advene.gui.views.accumulatorpopup import AccumulatorPopup
import advene.gui.edit.imports
import advene.gui.edit.properties
import advene.gui.edit.montage
from advene.gui.views.transcription import TranscriptionView
from advene.gui.edit.transcribe import TranscriptionEdit
from advene.gui.views.viewbook import ViewBook
from advene.gui.views.html import HTMLView
from advene.gui.views.scroller import ScrollerView
from advene.gui.views.caption import CaptionView
from advene.gui.views.editaccumulator import EditAccumulator
from advene.gui.views.tagbag import TagBag
import advene.gui.views.annotationdisplay

class Connect:
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

    def connect (self, gui):
        """Connect the class methods with the UI."""
        gui.signal_autoconnect(self.create_dictionary ())

    def gtk_widget_hide (self, widget):
        """Generic hide() method."""
        widget.hide ()
        return True

class AdveneGUI (Connect):
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
        self.connect (self.gui)

        # Resize the main window
        window=self.gui.get_widget('win')
        self.init_window_size(window, 'main')
        window.set_icon_list(*[ gtk.gdk.pixbuf_new_from_file(config.data.advenefile( ( 'pixmaps', 'icon_advene%d.png' % size ) ))
                                for size in (16, 32, 48, 64, 128) ])
        
        self.tooltips = gtk.Tooltips()

        # Last auto-save time (in ms)
        self.last_auto_save=time.time()*1000

        # Frequently used GUI widgets
        self.gui.logmessages = self.gui.get_widget("logmessages")
        self.slider_move = False
        # Will be initialized in get_visualisation_widget
        self.gui.stbv_combo = None

        # Adhoc view toolbuttons signal handling
        def adhoc_view_drag_sent(widget, context, selection, targetType, eventTime, name):
            if targetType == config.data.target_type['adhoc-view']:
                selection.set(selection.target, 8,
                              cgi.urllib.urlencode( {
                            'name': name,
                            } ))
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
            ('browser', _('Package browser'), 'browser.png'),
            ('webbrowser', _('Web browser'), 'web.png'),
            ('transcribe', _('Note-taking editor'), 'transcribe.png'),
            ('editaccumulator', _('Edit window placeholder (annotation and relation edit windows will be put here)'), 'editaccumulator.png'),
            ('history', _('Entry points'), 'history.png'),
            ('tagbag', _("Bag of tags"), 'tagbag.png'),
            ('montage', _("Dynamic montage"), 'montage.png'),
            ):
            b=gtk.Button()
            i=gtk.Image()
            i.set_from_file(config.data.advenefile( ( 'pixmaps', pixmap) ))
            b.add(i)
            self.tooltips.set_tip(b, tip)
            b.connect("drag_data_get", adhoc_view_drag_sent, name)
            b.connect("clicked", open_view_menu, name)
            b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)
            hb.pack_start(b, expand=False)
        hb.show_all()

        self.quicksearch_button=get_small_stock_button(gtk.STOCK_FIND, self.do_quicksearch)

        def modify_source(i, expr, label):
            """Modify the quicksearch source, and update the tooltip accordingly.
            """
            config.data.preferences['quicksearch-source']=expr
            self.tooltips.set_tip(self.quicksearch_button, _("Searching on %s.\nLeft click to launch the search, right-click to set the quicksearch options") % label)
            return True

        def quicksearch_options(button, event, method):
            """Generate the quicksearch options menu.
            """
            if event.button != 3 or event.type != gtk.gdk.BUTTON_PRESS:
                return False
            menu=gtk.Menu()
            item=gtk.CheckMenuItem(_("Ignore case"))
            item.set_active(config.data.preferences['quicksearch-ignore-case'])
            item.connect('toggled', lambda i: config.data.preferences.__setitem__('quicksearch-ignore-case', i.get_active()))
            menu.append(item)
            
            item=gtk.MenuItem(_("Searched elements"))
            submenu=gtk.Menu()
            l=[ (_("All annotations"), 
                 None) ] + [
                (_("Annotations of type %s") % self.controller.get_title(at),
                 'here/annotationTypes/%s/annotations' % at.id) for at in self.controller.package.annotationTypes ] + [ (_("Views"), 'here/views') ]
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
        self.quicksearch_button.connect('button-press-event', quicksearch_options, modify_source)
        hb.pack_start(self.quicksearch_button, expand=False, fill=False)
        hb.show_all()

        # Player status
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
        self.gui.player_status = self.gui.get_widget ("player_status")
        self.oldstatus = "NotStarted"

        self.last_slow_position = 0
        
        self.current_annotation = None

        # Dictionary of registered adhoc views
        self.registered_adhoc_views={}

        # List of active annotation views (timeline, tree, ...)
        self.adhoc_views = []
        # List of active element edit popups
        self.edit_popups = []
        
        self.edit_accumulator = None

        # Populate default STBV and type lists
        self.update_gui()

    def annotation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        annotation=context.evaluateValue('annotation')
        event=context.evaluateValue('event')
        if annotation.ownerPackage != self.controller.package:
            return True
        for v in self.adhoc_views:
            try:
                v.update_annotation(annotation=annotation, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('EditEnd'):
            self.controller.package._indexer.element_update(annotation)
        return True

    def relation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        relation=context.evaluateValue('relation')
        event=context.evaluateValue('event')
        if relation.ownerPackage != self.controller.package:
            return True
        for v in self.adhoc_views:
            try:
                v.update_relation(relation=relation, event=event)
            except AttributeError:
                pass
        return True

    def view_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        view=context.evaluateValue('view')
        event=context.evaluateValue('event')
        if view.ownerPackage != self.controller.package:
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

        return True

    def query_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        query=context.evaluateValue('query')
        event=context.evaluateValue('event')
        if query.ownerPackage != self.controller.package:
            return True
        for v in self.adhoc_views:
            try:
                v.update_query(query=query, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('Create'):
            self.controller.package._indexer.element_update(query)
        return True

    def resource_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        resource=context.evaluateValue('resource')
        event=context.evaluateValue('event')
        if resource.ownerPackage != self.controller.package:
            return True

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
        for v in self.adhoc_views:
            try:
                v.update_relationtype(relationtype=rt, event=event)
            except AttributeError:
                pass
        # Update the content indexer
        if event.endswith('Create'):
            self.controller.package._indexer.element_update(rt)
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
        w=[ e for e in self.edit_popups if e.element == element ]
        if w:
            for e in w:
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
                print _("*** WARNING*** : gtk.threads_init not available.\nThis may lead to unexpected behaviour.")

        # Register default GUI elements (actions, content_handlers, etc)
        # !! We cannot use controller.load_plugins, because it would make it impossible
        # to build one-file executables
        for m in (advene.gui.plugins.actions,
                  advene.gui.plugins.contenthandlers,
                  advene.gui.views.timeline,
                  advene.gui.views.browser,
                  advene.gui.views.interactivequery,
                  advene.gui.views.table,
                  advene.gui.views.history,
                  advene.gui.views.tree,
                  advene.gui.edit.montage,
                  advene.gui.views.annotationdisplay,
                  ):
            m.register(self.controller)

        # FIXME: We have to register LogWindow actions before we load the ruleset
        # but we should have an introspection method to do this automatically
        self.logwindow=advene.gui.views.logwindow.LogWindow(controller=self.controller)
        self.register_view(self.logwindow)

        self.visualisationwidget=self.get_visualisation_widget()
        self.gui.get_widget("displayvbox").add(self.visualisationwidget)
        self.gui.get_widget("vpaned").set_position(-1)

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
            
        defaults=config.data.advenefile( ('defaults', 'workspace.xml'), 'settings')
        if os.path.exists(defaults):
            # a default workspace has been saved. Load it and
            # ignore the default adhoc view specification.
            stream=open(defaults)
            tree=ET.parse(stream)
            stream.close()
            self.workspace_restore(tree.getroot())
        else:
            # Open the default adhoc popup views
            for dest in ('popup', 'west', 'east', 'south', 'fareast'):
                for n in config.data.preferences['adhoc-%s' % dest].split(':'):
                    try:
                        v=self.open_adhoc_view(n, destination=dest)
                    except Exception, e:
                        self.log(_("Cannot open adhoc view %(viewname)s in %(destination)s: %(error)s") % {
                                'viewname': n,
                                'destination': dest,
                                'error': unicode(e)})

        # Use small toolbar button everywhere
        gtk.settings_get_default().set_property('gtk_toolbar_icon_size', gtk.ICON_SIZE_SMALL_TOOLBAR)

        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        gobject.timeout_add (100, self.update_display)
        gobject.timeout_add (1000, self.slow_update_display)
        gtk.main ()
        self.controller.notify ("ApplicationEnd")

    def update_color(self, element):
        """Update the color for the given element.

        element may be AnnotationType, RelationType or Schema
        """
        try:
            c=self.controller.build_context(here=element)
            colname=c.evaluateValue(element.getMetaData(config.data.namespace, 'color'))
            gtk_color=gtk.gdk.color_parse(colname)
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
            self.drawable.connect("delete-event", lambda w, e: True)
        else:
            self.drawable=gtk.Socket()
            def handle_remove(socket):
                # Do not kill the widget if the application exits
                return True
            self.drawable.connect("plug-removed", handle_remove)

        black=gtk.gdk.Color(0, 0, 0)
        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            self.drawable.modify_bg (state, black)

        self.drawable.set_size_request(320, 200)
        self.drawable.add_events(gtk.gdk.BUTTON_PRESS)
        self.drawable.connect_object("button-press-event", self.debug_cb, self.drawable)

        self.player_toolbar=self.get_player_control_toolbar()

        # Dynamic view selection
        hb=gtk.HBox()
        #hb.pack_start(gtk.Label(_('D.view')), expand=False)
        self.gui.stbv_combo = gtk.ComboBox()
        cell = gtk.CellRendererText()
        self.gui.stbv_combo.pack_start(cell, True)
        self.gui.stbv_combo.add_attribute(cell, 'text', 0)
        hb.pack_start(self.gui.stbv_combo, expand=True)

        def on_edit_current_stbv_clicked(button):
            """Handle current stbv edition.
            """
            combo=self.gui.stbv_combo
            i=combo.get_active_iter()
            stbv=combo.get_model().get_value(i, 1)
            if stbv is None:
                if not dialog.message_dialog(_("Do you want to create a new dynamic view?"),
                                             icon=gtk.MESSAGE_QUESTION):
                    return True
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
                    # If we are already in the current annotation, do not goto
                    goto=not (self.controller.player.current_position_value in self.current_annotation.fragment)
                    self.loop_on_annotation_gui(self.current_annotation, goto=goto)
                else:
                    # No annotation was previously defined, deactivate the button
                    b.set_active(False)
            return True

        self.loop_toggle_button=gtk.ToggleToolButton(stock_id=gtk.STOCK_REFRESH)
        self.update_loop_button()
        self.loop_toggle_button.connect("toggled", loop_toggle_cb)
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
        self.gui.slider.set_draw_value(True)
        self.gui.slider.set_value_pos(gtk.POS_LEFT)
        self.gui.slider.connect ("format-value", self.format_slider_value)
        self.gui.slider.connect ("button-press-event", self.on_slider_button_press_event)
        self.gui.slider.connect ("button-release-event", self.on_slider_button_release_event)

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
        v.pack_start(self.gui.slider, expand=False)
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
        self.navigation_history=HistoryNavigation(controller=self.controller, closable=True)
        # Navigation history is embedded. The menu item is useless :
        self.gui.get_widget('navigationhistory1').set_property('visible', False)
        self.viewbook['west'].add_view(self.navigation_history, name=_("History"), permanent=True)
        # Make the history snapshots + border visible
        self.pane['west'].set_position (self.navigation_history.options['snapshot_width'] + 20)

        # Popup widget
        self.popupwidget=AccumulatorPopup(controller=self.controller,
                                          autohide=False)
        self.viewbook['east'].add_view(self.popupwidget, _("Popups"), permanent=True)

        self.pane['fareast'].show_all()

        # Information message
        l=gtk.Label(textwrap.fill(_("You can drag and drop view icons (timeline, treeview, transcription...) in this notebook to embed various views."), 50))
        self.popupwidget.display(l, timeout=10000, title=_("Information"))

        return self.pane['fareast']

    def display_imagecache(self):
        """Debug method.

        Not accessible through the GUI, use the Evaluator window:
        c.gui.display_imagecache()
        """
        k=self.controller.package.imagecache.keys()
        k.sort()
        hn=HistoryNavigation(controller=self.controller,
                             history=k,
                             vertical=True)
        w=hn.popup()
        return hn, w

    def process_player_shortcuts(self, win, event):
        """Generic player control shortcuts.

        Tab: pause/play
        Control-right/-left: move in the stream
        Control-home/-end: start/end of the stream
        """
        c=self.controller
        p=self.controller.player
        if event.keyval == gtk.keysyms.Tab:
            if p.status == p.PlayingStatus:
                c.update_status("pause")
            elif p.status == p.PauseStatus:
                c.update_status("resume")
            else:
                c.update_status("start")
            return True
        elif event.state & gtk.gdk.CONTROL_MASK:
            if event.keyval == gtk.keysyms.Up:
                c.move_position (1000/25, notify=False)
                return True
            elif event.keyval == gtk.keysyms.Down:
                c.move_position (-1000/25, notify=False)
                return True
            elif event.keyval == gtk.keysyms.Right:
                c.move_position (config.data.player_preferences['time_increment'], notify=False)
                return True
            elif event.keyval == gtk.keysyms.Left:
                c.move_position (-config.data.player_preferences['time_increment'], notify=False)
                return True
            elif event.keyval == gtk.keysyms.Home:
                c.update_status ("set", self.controller.create_position (0))
                return True
            elif event.keyval == gtk.keysyms.End:
                pos = c.create_position (value = -config.data.player_preferences['time_increment'],
                                         key = c.player.MediaTime,
                                         origin = c.player.ModuloPosition)
                c.update_status ("set", pos)
                return True
            elif event.keyval == gtk.keysyms.Page_Down:
                # FIXME: Next chapter
                return True
            elif event.keyval == gtk.keysyms.Page_Up:
                # FIXME: Previous chapter
                return True
        return False

    def get_player_control_toolbar(self):
        """Return a player control toolbar
        """
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        tb_list = (
            (_("Rewind"), gtk.STOCK_MEDIA_REWIND,
             self.on_b_rewind_clicked),
            (_("Play"), gtk.STOCK_MEDIA_PLAY,
             self.on_b_play_clicked),
            (_("Pause"), gtk.STOCK_MEDIA_PAUSE,
             self.on_b_pause_clicked),
            (_("Stop"), gtk.STOCK_MEDIA_STOP,
             self.on_b_stop_clicked),
            (_("Forward"), gtk.STOCK_MEDIA_FORWARD,
             self.on_b_forward_clicked),
            )

        for text, stock, callback in tb_list:
            b=gtk.ToolButton(stock)
            b.set_tooltip(self.tooltips, text)
            b.connect("clicked", callback)
            tb.insert(b, -1)

        tb.show_all()
        
        return tb

    def loop_on_annotation_gui(self, a, goto=False):
        """GUI version of controller.loop_on_annotation

        If "goto" is True, then go to the beginning of the annotation
        In addition to the standard "Loop on annotation", it updates a
        checkbox to activate/deactivate looping.
        """
        self.set_current_annotation(a)
        self.loop_toggle_button.set_active(True)
        def action_loop(controller, position):
            if self.loop_toggle_button.get_active():
                # Reactivate the loop.
                self.loop_on_annotation_gui(a, goto=True)
            return True
        # Note: the goto action has to be done *before* registering the videotime action, since 
        # setting a position resets the action queue.
        def reg():
            if goto:
                self.controller.update_status('set', a.fragment.begin, notify=False)
            self.controller.register_videotime_action(a.fragment.end, action_loop)
            return True
        self.controller.queue_action(reg)
        return True
    
    def debug_cb(self, window, event, *p):
        print "Got event %s (%d, %d) in window %s" % (str(event),
                                                      event.x,
                                                      event.y,
                                                      str(window))
        return False

    def format_slider_value (self, slider=None, val=0):
        """Formats a value (in milliseconds) into a time string.

        @param slider: a slider widget
        @param val: the value
        @type val: int
        @return: the formatted string
        @rtype: string
        """
        return helper.format_time (val)

    def init_window_size(self, window, name):
        """Initialize window size according to stored values.
        """
        if config.data.preferences['remember-window-size']:
            s=config.data.preferences['windowsize'].setdefault(name, (640,480))
            window.resize(*s)
            window.connect ("size_allocate", self.resize_cb, name)
        return True

    def resize_cb (self, widget, allocation, name):
        """Memorize the new dimensions of the widget.
        """
        config.data.preferences['windowsize'][name] = (allocation.width,
                                                       allocation.height)
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
            print _("Error: unable to find an edit popup for %(element)s:\n%(error)s") % {
                'element': element, 
                'error': unicode(e)}
        else:
                
            pop.edit (modal)
        return True

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

    def update_stbv_list (self):
        """Update the STBV list.
        """
        stbv_combo = self.gui.stbv_combo
        if stbv_combo is None:
            return True
        l=[ helper.TitledElement(value=None, title=_("No active dynamic view")) ]
        l.extend( [ helper.TitledElement(value=i, title=u'\u25b8 %s \u25b8' % self.controller.get_title(i))
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
                tree=ET.parse(name.content.stream)
                d={}
                d['clear']=True
                d['resize']=True
                ew=advene.gui.edit.properties.EditWidget(d.__setitem__, d.get)
                ew.set_name(_("Restoring workspace..."))
                ew.add_label(_("Do you wish to restore the %s workspace ?") % name.title)
                ew.add_checkbox(_("Clear current workspace"), "clear", _("Clear the current workspace"))
                ew.add_checkbox(_("Restore layout"), "resize", _("Restore the layout that was saved with the workspace"))
                res=ew.popup()
                if res:
                    if d['clear']:
                        self.workspace_clear()
                    self.workspace_restore(tree.getroot(), preserve_layout=not d['resize'])
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

        if name == 'tagbag':
            tags=Set()
            if not parameters:
                # Populate with annotations and relations tags
                for l in self.controller.package.annotations, self.controller.package.relations:
                    for e in l:
                        tags.update(e.tags)
            view=TagBag(self.controller, parameters=parameters, tags=list(tags))
        elif name == 'transcription':
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

            view = TranscriptionView(**kwargs)
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
            view=TranscriptionEdit(controller=self.controller, filename=filename)
        elif name == 'edit':
            try:
                element=kw['element']
            except KeyError:
                element=None
            if element is None:
                return None
            view=get_edit_popup(element, self.controller)
        elif name == 'editaccumulator':
            if not self.edit_accumulator:
                self.edit_accumulator=EditAccumulator(controller=self.controller, scrollable=True)
                view=self.edit_accumulator
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
        view._label=label or view.view_name
        if destination == 'popup':
            view.popup(label=label)
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
                                                          len(self.controller.package.annotations)),
                'relations': helper.format_element_name('relation',
                                                        len(self.controller.package.relations))
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
        p=context.evaluateValue('package')
        self.log (_("Package %(uri)s loaded: %(annotations)s and %(relations)s.")
                  % {
                'uri': p.uri,
                'annotations': helper.format_element_name('annotation',
                                                          len(p.annotations)),
                'relations': helper.format_element_name('relation',
                                                        len(p.relations))
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
        return True

    def update_window_title(self):
        # Update the main window title
        self.gui.get_widget ("win").set_title(" - ".join((_("Advene"),
                                                          self.controller.get_title(self.controller.package))))
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

    def get_illustrated_text(self, text, position=None, vertical=False):
        """Return a HBox with the given text and a snapshot corresponding to position.
        """
        if vertical:
            box=gtk.VBox()
        else:
            box=gtk.HBox()
        box.add(image_from_position(self.controller,
                                    position=position,
                                    height=40))
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
            a=p.annotations[-1]
        except IndexError:
            a=None

        ev=Evaluator(globals_=globals(),
                     locals_={'package': p,
                              'p': p,
                              'a': a,
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
        b=gtk.Button(stock=gtk.STOCK_CLOSE)

        def close_evaluator(*p):
            ev.save_history()
            w.destroy()
            return True

        b.connect("clicked", close_evaluator)
        b.show()
        ev.hbox.add(b)

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
            print _("Internal error on video player")
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
            # Update the display
            d = self.controller.cached_duration
            if d > 0 and d != self.gui.slider.get_adjustment ().upper:
                self.gui.slider.set_range (0, d)
                self.gui.slider.set_increments (d / 100, d / 10)

            if self.gui.slider.get_value() != pos:
                self.gui.slider.set_value(pos)

            if self.controller.player.status != self.oldstatus:
                self.oldstatus = self.controller.player.status
                self.gui.player_status.set_text (self.statustext[self.controller.player.status])

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
            if self.controller.player.status != self.oldstatus:
                self.oldstatus = self.controller.player.status
                self.gui.player_status.set_text (self.statustext[self.controller.player.status])
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

        # Update the loop toggle button, if the bookmark has been
        # reset by user interaction            
        if not self.controller.videotime_bookmarks and self.loop_toggle_button.get_active():
            self.loop_toggle_button.set_active(False)

        def do_save(aliases):
            for alias in aliases:
                print "Saving ", alias
                #self.controller.queue_action(self.controller.save_package, None, alias)
                self.controller.save_package(alias=alias)
            return True

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

    def do_quicksearch(self, *p):
        s=self.quicksearch_entry.get_text()
        if not s:
            self.log(_("Empty quicksearch string"))
            return True
        expr=config.data.preferences['quicksearch-source']
        if expr is None:
            source=self.controller.package.annotations
        else:
            c=self.controller.build_context()
            source=c.evaluateValue(expr)
        if config.data.preferences['quicksearch-ignore-case']:
            s=s.lower()        
            res=[ a for a in source if s in a.content.data.lower() ]
        else:
            res=[ a for a in source if s in a.content.data ]
            
        label=_("'%s'") % s
        self.open_adhoc_view('interactiveresult', destination='east', result=res, label=label, query=s)
        return True

    def ask_for_annotation_type(self, text=None, create=False):
        """Display a popup asking to choose an annotation type.

        If create then offer the possibility to create a new one.

        Return: the AnnotationType, or None if the action was cancelled.
        """
        at=None

        if text is None:
            text=_("Choose an annotation type.")

        ats=list(self.controller.package.annotationTypes)

        if create:
            newat=helper.TitledElement(value=None,
                                       title=_("Create a new annotation type"))
            ats.append(newat)

        if len(ats) == 1:
            at=ats[0]
        elif len(ats) > 1:
            at=dialog.list_selector(title=_("Choose an annotation type"),
                             text=text,
                             members=[ (a, self.controller.get_title(a)) for a in ats],
                             controller=self.controller)
        else:
            dialog.message_dialog(_("No annotation type is defined."),
                                  icon=gtk.MESSAGE_ERROR)
            return None

        if create and at == newat:
            # Create a new annotation type
            sc=self.ask_for_schema(text=_("Select the schema where you want to\ncreate the new annotation type."), create=True)
            if sc is None:
                return None

            cr=CreateElementPopup(type_=AnnotationType,
                                  parent=sc,
                                  controller=self.controller)
            at=cr.popup(modal=True)
            if at:
                self.edit_element(at, modal=True)
        return at

    def ask_for_schema(self, text=None, create=False):
        """Display a popup asking to choose a schema.

        If create then offer the possibility to create a new one.

        Return: the Schema, or None if the action was cancelled.
        """
        schema=None

        if text is None:
            text=_("Choose a schema.")

        schemas=list(self.controller.package.schemas)

        if create:
            newschema=helper.TitledElement(value=None,
                                           title=_("Create a new schema"))
            schemas.append(newschema)

        if len(schemas) == 1:
            schema=schemas[0]
        elif len(schemas) > 1:
            schema=dialog.list_selector(title=_("Choose a schema"),
                                                 text=text,
                                                 members=[ (s, self.controller.get_title(s)) for s in schemas],
                                                 controller=self.controller)
        else:
            dialog.message_dialog(_("No schema is defined."),
                           icon=gtk.MESSAGE_ERROR)
            return None

        if create and schema == newschema:
            cr = CreateElementPopup(type_=Schema,
                                    parent=self.controller.package,
                                    controller=self.controller)
            schema=cr.popup(modal=True)
            if schema:
                self.edit_element(schema, modal=True)

        return schema

    def popup_edit_accumulator(self, *p):
        self.open_adhoc_view('editaccumulator')
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
                        p.imagecache.save (helper.mediafile2id (media))
                    elif response == gtk.RESPONSE_NO:
                        p.imagecache._modified=False
                        pass
                elif config.data.preferences['imagecache-save-on-exit'] == 'always':
                    media=self.controller.get_default_media(package=p)
                    p.imagecache.save (helper.mediafile2id (media))
                    
        if self.controller.on_exit():
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
            if event.keyval == gtk.keysyms.q:
                # Quit
                return self.on_exit (win, None)
            elif event.keyval == gtk.keysyms.o:
                # Open an annotation file
                self.on_open1_activate (win, None)
                return True
            elif event.keyval == gtk.keysyms.e:
                # Popup the evaluator window
                self.popup_evaluator()
                return True
            elif event.keyval == gtk.keysyms.s:
                # Save the current annotation file
                self.on_save1_activate (win, None)
                return True
            elif event.keyval == gtk.keysyms.a:
                # EditAccumulator popup
                self.popup_edit_accumulator()
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
                                         text=_("Your package has been modified but not saved.\nSave it now?"))
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
                if package.resources and package.resources.children():
                    # There are resources -> save as an .azp package
                    ext='.azp'
                else:
                    ext='.xml'
                filename = filename + ext

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
        if (self.controller.get_default_media() is None
            or 'dvd' in self.controller.get_default_media()):
            if not dialog.message_dialog(
                _("Do you confirm the creation of annotations matching the DVD chapters?"),
                icon=gtk.MESSAGE_QUESTION):
                return True
            i=advene.util.importer.get_importer('lsdvd', controller=self.controller)
            i.package=self.controller.package
            i.process_file('lsdvd')
            self.controller.package._modified = True
            self.controller.notify('PackageLoad', package=self.controller.package)
        else:
            dialog.message_dialog(_("The associated media is not a DVD."),
                                           icon=gtk.MESSAGE_ERROR)
        return True

    def on_import_file1_activate (self, button=None, data=None):
        v=ExternalImporter(controller=self.controller)
        w=v.popup()
        dialog.center_on_mouse(w)
        return False

    def on_quit1_activate (self, button=None, data=None):
        """Gtk callback to quit."""
        return self.on_exit (button, data)

    def on_find1_activate (self, button=None, data=None):
        self.open_adhoc_view('interactivequery', destination='east')
        return True

    def on_cut1_activate (self, button=None, data=None):
        print "Cut: Not implemented yet."
        return True

    def on_copy1_activate (self, button=None, data=None):
        print "Copy: Not implemented yet."
        return True

    def on_paste1_activate (self, button=None, data=None):
        print "Paste: Not implemented yet."
        return True

    def on_delete1_activate (self, button=None, data=None):
        print "Delete: Not implemented yet (cf popup menu)."
        return True

    def on_edit_ruleset1_activate (self, button=None, data=None):
        """Default ruleset editing."""
        w=gtk.Window(gtk.WINDOW_TOPLEVEL)
        w.set_title(_("Standard RuleSet"))
        w.connect ("destroy", lambda e: w.destroy())

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
        b.connect("clicked", edit.add_rule_cb)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.connect("clicked", edit.remove_rule_cb)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_SAVE)
        b.connect("clicked", save_ruleset, 'default')
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect("clicked", validate_ruleset, 'default')
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect("clicked", lambda e: w.destroy())
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
        b.connect("clicked", close, w)
        hbox.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_REFRESH)
        b.connect("clicked", refresh, t)
        hbox.pack_start(b, expand=False)

        vbox.pack_start(hbox, expand=False)

        w.add(vbox)
        refresh(None, t)

        if self.controller.gui:
            self.controller.gui.init_window_size(w, 'weblogview')

        w.show_all()

        return True

    def on_navigationhistory1_activate (self, button=None, data=None):
        h=advene.gui.views.history.HistoryNavigation(self.controller, self.navigation_history, closable=False)
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
        d.set_copyright("Copyright 2002,2003,2004,2005,2006,2007 Olivier Aubert, Pierre-Antoine Champin")
        d.set_license(_('GNU General Public License\nSee http://www.gnu.org/copyleft/gpl.html for more details'))
        d.set_website('http://liris.cnrs.fr/advene/')
        d.set_website_label('Visit the Advene web site for examples and documentation.')
        d.set_authors( [ 'Olivier Aubert', 'Pierre-Antoine Champin', 'Yannick Prie', 'Bertrand Richard', 'Frank Wagner' ] )
        d.set_logo(gtk.gdk.pixbuf_new_from_file(config.data.advenefile( ( 'pixmaps', 'logo_advene.png') )))
        d.connect('response', lambda w, r: w.destroy())
        d.run()

        return True

    def on_b_rewind_clicked (self, button=None, data=None):
        if self.controller.player.status == self.controller.player.PlayingStatus:
            self.controller.move_position (-config.data.player_preferences['time_increment'],
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
            self.controller.move_position (config.data.player_preferences['time_increment'],
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

        window.connect ("destroy", lambda e: window.destroy())

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
        b.connect("clicked", validate, sel, window)
        hbox.add(b)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect("clicked", cancel, window)
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
                dialog.message_dialog(_("Successfully extracted the video stream address from the given url"))
                stream=s
            self.controller.set_default_media(stream)
        return True
    
    def on_b_exit_clicked (self, button=None, data=None):
        return self.on_exit (button, data)

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
        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Package properties"))
        ew.add_entry(_("Author"), "author", _("Author name"))
        ew.add_entry(_("Date"), "date", _("Package creation date"))
        ew.add_entry(_("Title"), "title", _("Package title"))
        ew.add_file_selector(_("Associated media"), 'media', _("Select a movie file"))
        ew.add_entry(_("Duration"), "duration", _("Media duration in ms"))

        res=ew.popup()

        if res:
            self.controller.package.author = cache['author']
            self.controller.package.date = cache['date']
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
        direct_options=('history-size-limit', 'scroll-increment',
                        'adhoc-south', 'adhoc-west', 'adhoc-east', 'adhoc-fareast', 'adhoc-popup',
                        'display-scroller', 'display-caption', 'imagecache-save-on-exit', 
                        'remember-window-size', 'expert-mode',
                        'package-auto-save', 'package-auto-save-interval')
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
        ew.add_title(_("General"))
        ew.add_spin(_("Scroll increment"), "scroll-increment", _("On most annotations, control+scrollwheel will increment/decrement their bounds by this value (in ms)."), 10, 2000)
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

        ew.add_title(_("GUI"))
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

        ew.add_title(_("Standard adhoc views"))
        ew.add_label(_("""List of adhoc views to open on application startup.
Multiple views can be separated by :
Available views: timeline, tree, browser, transcribe"""))

        ew.add_entry(_("South"), 'adhoc-south', _("Embedded below the video"))
        ew.add_entry(_("West"), 'adhoc-west', _("Embedded at the left of the video"))
        ew.add_entry(_("East"), 'adhoc-east', _("Embedded at the right of the video"))
        ew.add_entry(_("Right"), 'adhoc-fareast', _("Embedded at the right of the window"))
        ew.add_entry(_("Popup"), 'adhoc-popup', _("In their own window"))

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
            try:
                self.controller.player.set_widget(self.drawable)
            except AttributeError:
                if self.visual_id:
                    self.controller.player.set_visual(self.visual_id)
        return True

    def on_save_imagecache1_activate (self, button=None, data=None):
        id_ = helper.mediafile2id (self.controller.get_default_media())
        d=self.controller.package.imagecache.save (id_)
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

    def on_slider_button_release_event (self, button=None, data=None):
        if self.controller.player.playlist_get_list():
            p = self.controller.create_position (value = long(self.gui.slider.get_value ()))
            self.controller.update_status('set', p)
        self.slider_move = False
        return False

    def on_help1_activate (self, button=None, data=None):
        helpfile=os.path.join( config.data.path['web'], 'user.html' )
        if os.access(helpfile, os.R_OK):
            self.controller.open_url ('file:///' + helpfile)
        else:
            self.log(_("Unable to find the help file at %s") % helpfile)
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
        return True

    def on_create_annotation_type_activate (self, button=None, data=None):
        sc=self.ask_for_schema(text=_("Select the schema where you want to\ncreate the new annotation type."), create=True)
        if sc is None:
            return None
        cr=CreateElementPopup(type_=AnnotationType,
                              parent=sc,
                              controller=self.controller)
        cr.popup()
        return True

    def on_create_relation_type_activate (self, button=None, data=None):
        sc=self.ask_for_schema(text=_("Select the schema where you want to\ncreate the new relation type."), create=True)
        if sc is None:
            return None
        cr=CreateElementPopup(type_=RelationType,
                              parent=sc,
                              controller=self.controller)
        cr.popup()
        return True

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

        v=helper.get_id(self.controller.package.views, ident)
        if v is None:
            create=True
            v=self.controller.package.createView(ident=ident, clazz='package')
            v.content.mimetype='application/x-advene-workspace-view'
        else:
            # Existing view. Check that it is already an workspace-view
            if v.content.mimetype != 'application/x-advene-workspace-view':
                dialog.message_dialog(_("Error: the view %s exists and is not a workspace view.") % ident)
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

if __name__ == '__main__':
    v = AdveneGUI ()
    try:
        v.main (config.data.args)
    except Exception, e:
        e, v, tb = sys.exc_info()
        print config.data.version_string
        print _("Got exception %s. Stopping services...") % str(e)
        v.on_exit ()
        print _("*** Exception ***")
        import code
        code.traceback.print_exception (e, v, tb)
