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

import sys, time
import os
import socket
import StringIO

import advene.core.config as config

import gtk
import gtk.glade
import gobject

import gettext
import locale

print "Using localedir %s" % config.data.path['locale']

APP='advene'
# Locale initialisation
locale.setlocale(locale.LC_ALL, '')
gettext.bindtextdomain(APP, config.data.path['locale'])
gettext.textdomain(APP)
gettext.install(APP, localedir=config.data.path['locale'], unicode=True)
gtk.glade.bindtextdomain(APP, config.data.path['locale'])
gtk.glade.textdomain(APP)

import advene.core.controller

import advene.rules.elements
import advene.rules.ecaengine

from advene.model.view import View
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.query import Query
import advene.model.constants
import advene.model.tal.context

import advene.core.mediacontrol
import advene.util.vlclib as vlclib

import advene.util.importer

# GUI elements
import advene.gui.util
import advene.gui.plugins.actions
import advene.gui.plugins.contenthandlers
import advene.gui.views.tree
import advene.gui.views.timeline
import advene.gui.views.logwindow
from advene.gui.views.browser import Browser
from advene.gui.views.history import HistoryNavigation
from advene.gui.edit.rules import EditRuleSet
from advene.gui.edit.dvdselect import DVDSelect
from advene.gui.edit.elements import get_edit_popup
from advene.gui.edit.create import CreateElementPopup
import advene.gui.evaluator
from advene.gui.views.accumulatorpopup import AccumulatorPopup
import advene.gui.edit.imports
import advene.gui.edit.properties
from advene.gui.views.transcription import TranscriptionView
from advene.gui.edit.transcribe import TranscriptionEdit
from advene.gui.views.interactivequery import InteractiveQuery
from advene.gui.views.viewbook import ViewBook

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

    def create_dictionary_for_class (self, a_class, dict):
        """Create a (name, function) dictionary for the specified class."""
        bases = a_class.__bases__
        for iteration in bases:
            self.create_dictionary_for_class (iteration, dict)
        for iteration in dir(a_class):
            dict[iteration] = getattr(self, iteration)

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
    @ivar imagecache: the current imagecache
    @type imagecache: imagecache.ImageCache

    @ivar annotation: the currently edited annotation (or I{None})
    @type annotation: advene.model.Annotation

    @ivar last_slow_position: a cache to check whether a GUI update is necessary
    @type last_slow_position: int

    @ivar preferences: the current preferences
    @type preferences: dict
    """

    def __init__ (self, args=None):
        """Initializes the GUI and other attributes.
        """
        self.controller = advene.core.controller.AdveneController(args)
        self.controller.register_gui(self)
        
        gladefile=config.data.advenefile (config.data.gladefilename)
        # Glade init.
        self.gui = gtk.glade.XML(gladefile, domain=gettext.textdomain())
        self.connect (self.gui)

        # Resize the main window
        window=self.gui.get_widget('win')
        self.init_window_size(window, 'main')

        self.tooltips = gtk.Tooltips()
        
        # Frequently used GUI widgets
        self.gui.logmessages = self.gui.get_widget("logmessages")
        self.gui.slider = self.gui.get_widget ("slider")
        # slider holds the position in ms units
        self.slider_move = False
        # but we display it in ms
        self.gui.slider.connect ("format-value", self.format_slider_value)

        # About box
        self.gui.get_widget('about_web_button').set_label(config.data.version_string)

        # Define combobox cell renderers
        for n in ("stbv_combo", ):
            combobox=self.gui.get_widget(n)
            cell = gtk.CellRendererText()
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, 'text', 0)

	# Adhoc view toolbuttons signal handling
	def adhoc_view_drag_sent(widget, context, selection, targetType, eventTime, name):
	    if targetType == config.data.target_type['adhoc-view']:
		selection.set(selection.target, 8, name)
		return True
	    return False

	def adhoc_view_release(widget, event, name):
	    widget.set_state(gtk.STATE_NORMAL)
	    # This is all hackish: we can only catch button-release
	    # event (because of set_use_drag_window() ) but it gets
	    # triggered both for a click and for a drag.  So we must
	    # try to guess if we are inside the toolbar (then click)
	    # or outside (then drag)
	    (x, y, m) = widget.window.get_pointer()
	    alloc=widget.get_parent().get_allocation()
	    #print x, y, alloc.width, alloc.height
	    if (x >= 0 and x <= alloc.width
		and y >= 0 and y <= alloc.height):
		# Release was done in the toolbar, so emulate a click
		self.open_adhoc_view(name, popup=True)

	    return True

	def adhoc_view_press(widget, event, name):
	    widget.set_state(gtk.STATE_PRELIGHT)
	    return False

	for n in ('tb_treeview', 'tb_timeline', 'tb_transcription', 
		  'tb_browser', 'tb_webbrowser', 'tb_transcribe'):
	    b=self.gui.get_widget(n)
	    name=n.replace('tb_', '')
	    b.set_use_drag_window(True)
	    b.connect("drag_data_get", adhoc_view_drag_sent, name)
	    b.connect("button_release_event", adhoc_view_release, name)
	    b.connect("button_press_event", adhoc_view_press, name)
	    b.drag_source_set(gtk.gdk.BUTTON1_MASK,
			      config.data.drag_type['adhoc-view'], gtk.gdk.ACTION_COPY)

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

        # List of active annotation views (timeline, tree, ...)
        self.adhoc_views = []

        # Populate default STBV and type lists
        self.update_gui()

    def annotation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        annotation=context.evaluateValue('annotation')
        event=context.evaluateValue('event')
        for v in self.adhoc_views:
            try:
                v.update_annotation(annotation=annotation, event=event)
            except AttributeError:
                pass
        return True

    def relation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        relation=context.evaluateValue('relation')
        event=context.evaluateValue('event')
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
                self.controller.activate_stbv(view)
        return True

    def query_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        query=context.evaluateValue('query')
        event=context.evaluateValue('event')
        for v in self.adhoc_views:
            try:
                v.update_query(query=query, event=event)
            except AttributeError:
                pass
        return True

    def schema_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        schema=context.evaluateValue('schema')
        event=context.evaluateValue('event')
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
        for v in self.adhoc_views:
            try:
                v.update_annotationtype(annotationtype=at, event=event)
            except AttributeError:
                pass
        # Update the current type menu
        self.update_gui()
        return True

    def relationtype_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        rt=context.evaluateValue('relationtype')
        event=context.evaluateValue('event')
        for v in self.adhoc_views:
            try:
                v.update_relationtype(relationtype=rt, event=event)
            except AttributeError:
                pass
        return True

    def on_view_activation(self, context, parameters):
        """Handler used to update the STBV GUI.
        """
        combo = self.gui.get_widget("stbv_combo")
        store = combo.get_model()
        i = store.get_iter_first()
        while i is not None:
            if store.get_value(i, 1) == self.controller.current_stbv:
                combo.set_active_iter(i)
                return True
            i=store.iter_next(i)
        
        return True

    def updated_position_cb (self, context, parameters):
        position_before=context.evaluateValue('position_before')
        self.navigation_history.append(position_before)
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
                gtk.threads_init ()
            except RuntimeError:
                print _("*** WARNING*** : gtk.threads_init not available.\nThis may lead to unexpected behaviour.")

	# Register default GUI elements (actions, content_handlers, etc)
	# !! We cannot use controller.load_plugins, because it would make it impossible
	# to build one-file executables
	advene.gui.plugins.actions.register(self.controller)
	advene.gui.plugins.contenthandlers.register(self.controller)
	
        # FIXME: We have to register LogWindow actions before we load the ruleset
        # but we should have an introspection method to do this automatically
        self.logwindow=advene.gui.views.logwindow.LogWindow(controller=self.controller)
        self.register_view(self.logwindow)

        self.visualisationwidget=self.get_visualisation_widget()
        self.gui.get_widget("displayvbox").add(self.visualisationwidget)
        self.gui.get_widget("vpaned").set_position(-1)
  
        for events, method in ( 
            ("PackageLoad", self.manage_package_load),
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
            ( ('SchemaCreate', 'SchemaEditEnd', 'SchemaDelete'),
              self.schema_lifecycle),
            ( ('AnnotationTypeCreate', 'AnnotationTypeEditEnd', 
               'AnnotationTypeDelete'),
              self.annotationtype_lifecycle),
            ( ('RelationTypeCreate', 'RelationTypeEditEnd', 
               'RelationTypeDelete'),
              self.relationtype_lifecycle),
            ("PlayerSet", self.updated_position_cb),
            ("ViewActivation", self.on_view_activation) 
            ):
            if isinstance(events, basestring):
                self.controller.event_handler.internal_rule (event=events,
                                                             method=method)
            else:
                for e in events:
                    self.controller.event_handler.internal_rule (event=e,
                                                                 method=method)

        self.controller.init()

        self.visual_id = None
        # The player is initialized. We can register the drawable id
        try:
            if not config.data.player['embedded']:
                raise Exception()
            if config.data.os == 'win32':
                self.visual_id=self.drawable.window.handle
            else:
                self.visual_id=self.drawable.window.xid
            self.controller.player.set_visual(self.visual_id)
        except Exception, e:
            print "Cannot set visual: %s" % str(e)
            self.displayhbox.destroy()

            self.logwindow.embedded=False
            self.logwindow.widget=self.logwindow.build_widget()
            
            tree = advene.gui.views.tree.TreeWidget(self.controller.package,
                                                    controller=self.controller)
            tree.get_widget().show_all()
            self.register_view (tree)
            sw = gtk.ScrolledWindow ()
            sw.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            
            sw.add (tree.get_widget())
            self.gui.get_widget("displayvbox").add(sw)
            sw.show_all()

        if config.data.webserver['mode'] == 1:
	    if self.controller.server:
		self.log(_("Using Mainloop input handling for webserver..."))
		gobject.io_add_watch (self.controller.server,
				      gobject.IO_IN,
				      self.handle_http_request)
		if config.data.os == 'win32':
		    # Win32 workaround for the reactivity problem
		    def sleeper():
			time.sleep(.001)
			return True
		    gobject.timeout_add(400, sleeper)
	    else:
		self.log(_("No available webserver"))

        # Populate the file history menu
        for filename in config.data.preferences['history']:
            self.append_file_history_menu(filename)

        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        gobject.timeout_add (100, self.update_display)
        gtk.main ()
        self.controller.notify ("ApplicationEnd")

    def get_visualisation_widget(self):
        """Return the main visualisation widget.

        It consists in the embedded video window plus the various views.
        """
        vis=gtk.VPaned()

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
        self.drawable.set_size_request(320,200)
        self.drawable.add_events(gtk.gdk.BUTTON_PRESS)
        self.drawable.connect_object("button-press-event", self.debug_cb, self.drawable)

        self.displayhbox=gtk.HPaned()

	hpane=gtk.HPaned()
        self.displayhbox.pack1(self.drawable, shrink=False)
	self.displayhbox.add2(hpane)
	
        self.navigation_history=HistoryNavigation(controller=self.controller)
        # Navigation history is embedded. The menu item is useless :
        self.gui.get_widget('navigationhistory1').set_property('visible', False)

	f=gtk.Frame()
	f.set_label(_("History"))
	f.add(self.navigation_history.widget)
        hpane.add2(f)

        if config.data.preferences['embed-treeview']:
            tree = advene.gui.views.tree.TreeWidget(self.controller.package,
                                                    controller=self.controller)
            hpane.add1(tree.get_widget())
            self.register_view (tree)            
	else:
            hpane.add1(self.logwindow.widget)
            self.logwindow.embedded=True
            # URL stack is embedded. The menu item is useless :
            self.gui.get_widget('urlstack1').set_property('visible', False)            

	# We should be able to specify 80%/20% for instance, but the allocation
	# is not available here. We have to wait for the main GUI window to 
	# appear
        hpane.set_position (300)

        vis.add1(self.displayhbox)

	self.viewbook=ViewBook(controller=self.controller)
	
	vis.add2(self.viewbook.widget)

        self.popupwidget=AccumulatorPopup(controller=self.controller,
                                          autohide=False)
	
	self.viewbook.add_view(self.popupwidget, _("Popups"))
	
        vis.show_all()

	# Information message
	l=gtk.Label(_("You can drag and drop view icons\n(timeline, treeview, transcription...)\nin this notebook to embed\nvarious views."))
	self.popupwidget.display(l, timeout=5000, title=_("Information"))

        return vis

    def display_imagecache(self):
	"""Debug method.

	Not accessible through the GUI, use the Evaluator window:
	c.gui.display_imagecache()
	"""
        k=self.controller.imagecache.keys()
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
	    if event.keyval == gtk.keysyms.Right:
		c.move_position (config.data.player_preferences['time_increment'])
		return True
	    elif event.keyval == gtk.keysyms.Left:
		c.move_position (-config.data.player_preferences['time_increment'])
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
            (_("Rewind"), _("Rewind"), gtk.STOCK_MEDIA_REWIND, 
             self.on_b_rewind_clicked),
            (_("Play"), _("Play"), gtk.STOCK_MEDIA_PLAY,
             self.on_b_play_clicked),
            (_("Pause"), _("Pause"), gtk.STOCK_MEDIA_PAUSE,
             self.on_b_pause_clicked),
            (_("Stop"), _("Stop"), gtk.STOCK_MEDIA_STOP, 
             self.on_b_stop_clicked),
            (_("Forward"), _("Forward"), gtk.STOCK_MEDIA_FORWARD,
             self.on_b_forward_clicked),
            )

        for text, tooltip, stock, callback in tb_list:
            b=gtk.ToolButton(stock)
            b.set_tooltip(self.tooltips, tooltip)
            b.connect("clicked", callback)
            tb.insert(b, -1)
        tb.show_all()
        return tb
    
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
        return vlclib.format_time (val)

    def init_window_size(self, window, name):
        """Initialize window size according to stored values.
        """
        s=config.data.preferences['windowsize'].setdefault(name, (640,480))
        window.set_default_size (*s)
        window.connect ("size_allocate", self.resize_cb, name)
        return True
    
    def resize_cb (self, widget, allocation, name):
        """Memorize the new dimensions of the widget.
        """
        config.data.preferences['windowsize'][name] = (allocation.width,
                                                       allocation.height)
        #print "New size for %s: %s" %  (name, config.data.preferences['windowsize'][name])
        return False
    
    def on_edit_current_stbv_clicked(self, button):
        combo=self.gui.get_widget("stbv_combo")
        i=combo.get_active_iter()
        stbv=combo.get_model().get_value(i, 1)
        if stbv is None:
	    if not advene.gui.util.message_dialog(_("Do you want to create a new dynamic view?"),
					      icon=gtk.MESSAGE_QUESTION):
                return True
            cr = CreateElementPopup(type_=View,
                                    parent=self.controller.package,
                                    controller=self.controller)
            cr.popup()
            return True
        try:
            pop = get_edit_popup (stbv, self.controller)
        except TypeError, e:
            print _("Error: unable to find an edit popup for %s:\n%s") % (stbv, unicode(e))
        else:
            pop.edit ()
        return True

    def update_stbv_list (self):
        """Update the STBV list.
        """
        stbv_combo = self.gui.get_widget("stbv_combo")
        l=[ None ]
        l.extend(self.controller.get_stbv_list())
        st, i = advene.gui.util.generate_list_model([ (i, self.controller.get_title(i)) 
                                                      for i in l ],
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
            except Exception, e:
                self.log(_("Cannot load package %s:\n%s") % (fname, unicode(e)))
            return True

        # We cannot set the widget name to something more sensible (like
        # filemenu) because Glade resets names when editing the menu
        menu=self.gui.get_widget('menuitem1_menu')
        i=gtk.MenuItem(label=unicode(os.path.basename(filename)))
        i.connect('activate', open_history_file, filename)
        self.tooltips.set_tip(i, _("Open %s") % filename)
        
        i.show()
        menu.append(i)

    def build_utbv_menu(self):
        def open_utbv(button, u):
            self.controller.open_url (u)
            return True

        c=self.controller

        url=c.get_default_url(root=True)
        
        menu=gtk.Menu()

        if not self.controller.package:
            return menu

        # Add defaultview first if it exists
        defaultview=c.package.getMetaData(config.data.namespace,
                                          'default_utbv')
        if defaultview:
            i=gtk.MenuItem(label=_("Default view"))
            i.connect('activate', open_utbv, c.get_default_url())
            menu.append(i)
        
        for utbv in c.package.views:
            if (utbv.matchFilter['class'] == 'package'
                and utbv.content.mimetype == 'text/html'):
                i=gtk.MenuItem(label=c.get_title(utbv))
                i.connect('activate', open_utbv, "%s/view/%s" % (url,
                                                                 utbv.id))
                menu.append(i)
        menu.show_all()
        return menu

    def open_adhoc_view(self, name, popup=True, **kw):
	"""Open the given adhoc view.
	"""
	view=None
	if name == 'treeview' or name == 'tree':
	    view = advene.gui.views.tree.TreeWidget(self.controller.package,
						    controller=self.controller)
	elif name == 'timeline':
	    view = advene.gui.views.timeline.TimeLine (l=None,
						       controller=self.controller)
	elif name == 'transcription':
	    try:
		at=kw['annotation_type_id']
	    except KeyError:
		at=self.ask_for_annotation_type(text=_("Choose the annotation type to display as transcription."), 
						create=False)
	    if at is not None:
		view = TranscriptionView(controller=self.controller,
					 annotationtype=at)
	elif name == 'browser':
	    view = Browser(element=self.controller.package,
			   controller=self.controller)
	elif name == 'webbrowser':
	    if self.controller.package is not None:
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
	if view is not None and popup:
	    view.popup()
	return view

    def update_gui (self):
        """Update the GUI.

        This method should be called upon package loading, or when a
        new view or type is created, or when an existing one is
        modified, in order to reflect changes.
        """
        self.update_stbv_list()
        return

    def manage_package_save (self, context, parameters):
        """Event Handler executed after saving a package.

        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        self.log (_("Package %s saved: %s and %s.")
                  % (self.controller.package.uri,
                     vlclib.format_element_name('annotation',
                                                len(self.controller.package.annotations)),
                     vlclib.format_element_name('relation',
                                                len(self.controller.package.relations))
                     ))
        return True

    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.

        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        self.log (_("Package %s loaded: %s and %s.")
                  % (self.controller.package.uri,
                     vlclib.format_element_name('annotation',
                                                len(self.controller.package.annotations)),
                     vlclib.format_element_name('relation',
                                                len(self.controller.package.relations))
                     ))

        f=self.controller.package.uri
        h=config.data.preferences['history']
        if not f in h and not f.endswith('new_pkg'):
            h.append(f)
            self.append_file_history_menu(f)
            # Keep the 5 last elements
            config.data.preferences['history']=h[-config.data.preferences['history-size-limit']:]
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

        return True

    def update_window_title(self):
        # Update the main window title
        self.gui.get_widget ("win").set_title(" - ".join((_("Advene"),
                                                          self.controller.package.title or _("No title"))))
        return True
    
    def handle_http_request (self, source, condition):
        """Handle a HTTP request.

        This method is used if config.data.webserver['mode'] == 1.
        """
        # Make sure that all exceptions are catched, else the gtk mainloop
        # will not execute update_display.
        try:
            source.handle_request ()
        except socket.error, e:
            print _("Network exception: %s") % str(e)
        except Exception, e:
            import traceback
            s=StringIO.StringIO()
            traceback.print_exc (file = s)
            self.log(_("Got exception %s in web server.") % str(e), s.getvalue())
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

    def get_illustrated_text(self, text, position=None):
        """Return a HBox with the given text and a snapshot corresponding to position.
        """
        hbox=gtk.HBox()
        hbox.add(advene.gui.util.image_from_position(self.controller,
                                                     position=position,
                                                     height=40))
        hbox.add(gtk.Label(text))
        return hbox

    def register_view (self, view):
        """Register a view plugin.

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

        ev=advene.gui.evaluator.Window(globals_=globals(),
                                       locals_={'package': p,
                                                'p': p,
                                                'a': a,
                                                'c': self.controller,
                                                'self': self },
				       historyfile=config.data.advenefile('evaluator.log', 'settings')
				       )
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
            newat=vlclib.TitledElement(value=None,
                                       title=_("Create a new annotation type"))
            ats.append(newat)
            
        if len(ats) == 1:
            at=ats[0]
        elif len(ats) > 1:
            at=advene.gui.util.list_selector(title=_("Choose an annotation type"),
                                             text=text,
                                             members=ats,
                                             controller=self.controller)
        else:
	    advene.gui.util.message_dialog(_("No annotation type is defined."),
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
                try:
                    pop = get_edit_popup (at, self.controller)
                except TypeError, e:
                    print _("Error: unable to find an edit popup for %s:\n%s") % (at, unicode(e))
                else:
                    at=pop.edit (modal=True)
                
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
            newschema=vlclib.TitledElement(value=None,
                                           title=_("Create a new schema"))
            schemas.append(newschema)
            
        if len(schemas) == 1:
            schema=schemas[0]
        elif len(schemas) > 1:
            schema=advene.gui.util.list_selector(title=_("Choose a schema"),
                                                 text=text,
                                                 members=schemas,
                                                 controller=self.controller)
        else:
	    advene.gui.util.message_dialog(_("No schema is defined."),
					   icon=gtk.MESSAGE_ERROR)
	    return None

        if create and schema == newschema:
            cr = CreateElementPopup(type_=Schema,
                                    parent=self.controller.package,
                                    controller=self.controller)
            schema=cr.popup(modal=True)
            if schema:
                try:
                    pop = get_edit_popup (schema,
                                          self.controller)
                except TypeError, e:
                    print _("Error: unable to find an edit popup for %s:\n%s") % (schema,
                                                                                  unicode(e))
                else:
                    at=pop.edit (modal=True)
            
        return schema
        
    def on_stbv_combo_changed (self, combo=None):
        """Callback used to select the current stbv.
        """
        i=combo.get_active_iter()
        if i is None:
            return False
        stbv=combo.get_model().get_value(i, 1)
        self.controller.activate_stbv(stbv)
        return True

    def on_exit(self, source=None, event=None):
        """Generic exit callback."""
        if self.controller.modified:
            response=advene.gui.util.yes_no_cancel_popup(title=_("Package modified"),
                                                         text=_("Your package has been modified but not saved.\nSave it now?"))
            if response == gtk.RESPONSE_CANCEL:
                return True            
            if response == gtk.RESPONSE_YES:
                self.on_save1_activate()
                return False
            if response == gtk.RESPONSE_NO:
                self.controller.modified=False
            
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

	return False

    def on_new1_activate (self, button=None, data=None):
        """New package. Erase the current one."""
        if self.controller.modified:
	    if not advene.gui.util.message_dialog(
                _("Your package has been modified but not saved.\nCreate a new one anyway?"),
		icon=gtk.MESSAGE_QUESTION):
                return True
        self.controller.load_package ()
        return True

    def on_open1_activate (self, button=None, data=None):
        """Open a file selector to load a package."""
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None

        filename=advene.gui.util.get_filename(title=_("Load a package"),
                                              action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                              button=gtk.STOCK_OPEN,
                                              default_dir=d)
        if filename:
            try:
                self.controller.load_package (uri=filename)
            except Exception, e:
                self.log(_("Cannot load package %s:\n%s") % (fname, unicode(e)))
        return True

    def on_save1_activate (self, button=None, data=None):
        """Save the current package."""
        if (self.controller.package.uri == ""
            or self.controller.package.uri.endswith('new_pkg')):
            self.on_save_as1_activate (button, data)
        else:
            self.controller.save_package ()
        return True

    def on_save_as1_activate (self, button=None, data=None):
        """Save the package with a new name."""
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None
        filename=advene.gui.util.get_filename(title=_("Save the current package"),
                                              action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                              button=gtk.STOCK_SAVE,
                                              default_dir=d)
        if filename:
	    (p, ext) = os.path.splitext(filename)
	    if ext == '':
		# Add a pertinent extension
		if self.controller.package.resources:
		    # There are resources -> save as an .azp package
		    ext='.azp'
		else:
		    ext='.xml'
		filename = filename + ext

	    if self.controller.package.resources and ext.lower() != '.azp':
		ret=advene.gui.util.yes_no_cancel_popup(title=_("Invalid file extension"),
							text=_("Your package contains resources,\nthe filename (%s) should have a .azp extension.\nShould I put the correct extension?") % filename)
		if ret == gtk.RESPONSE_YES:
		    filename = p + '.azp'
		elif ret == gtk.RESPONSE_NO:
		    advene.gui.util.message_dialog(_("OK, the resources will be lost."))
		else:
		    self.log(_("Aborting package saving"))
		    return True
		
            self.controller.save_package(name=filename)
        return True

    def on_import_dvd_chapters1_activate (self, button=None, data=None):
        # FIXME: loosy test
        if (self.controller.get_default_media() is None
            or 'dvd' in self.controller.get_default_media()):
	    if not advene.gui.util.message_dialog(
                _("Do you confirm the creation of annotations matching the DVD chapters?"),
		icon=gtk.MESSAGE_QUESTION):
                return True
            i=advene.util.importer.get_importer('lsdvd', controller=self.controller)
            i.package=self.controller.package
            i.process_file('lsdvd')
            self.controller.modified=True
            self.controller.notify('PackageLoad')
        else:
	    advene.gui.util.message_dialog(_("The associated media is not a DVD."),
					   icon=gtk.MESSAGE_ERROR)
        return True
        
    def on_import_file1_activate (self, button=None, data=None):
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None
        filename=advene.gui.util.get_filename(title=_("Choose the file to import"),
                                              action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                              button=gtk.STOCK_OPEN,
					      default_dir=d)
        if not filename:
            return True
        filename_utf=unicode(filename, 'iso-8859-1').encode('utf-8')
        i=advene.util.importer.get_importer(filename, controller=self.controller)
        if i is None:
	    advene.gui.util.message_dialog(
                _("The format of the file\n%s\nis not recognized.") % filename_utf,
		icon=gtk.MESSAGE_ERROR)
        else:
            # FIXME: build a dialog to enter optional parameters
            # FIXME: handle the multiple possible importers case (for XML esp.)
	    if not advene.gui.util.message_dialog(
                _("Do you confirm the import of data from\n%s\nby the %s filter?") % (
		    filename_utf, i.name), icon=gtk.MESSAGE_QUESTION):
                return True
            i.package=self.controller.package
            i.process_file(filename)
            self.controller.modified=True
            self.controller.notify("PackageLoad", package=i.package)
            self.log(_('Converted from file %s :') % filename_utf)
            self.log(i.statistics_formatted())
        return True

    def on_quit1_activate (self, button=None, data=None):
        """Gtk callback to quit."""
        return self.on_exit (button, data)

    def on_find1_activate (self, button=None, data=None): 
        iq = InteractiveQuery(here=self.controller.package,
                              controller=self.controller)
        iq.popup()
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
        w.set_title(_("Default RuleSet"))
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

    def on_view_urlstack_activate (self, button=None, data=None):
        """Open the URL stack view plugin."""
        if not self.logwindow.embedded:
            self.logwindow.popup()
        return True

    def on_evaluator2_activate (self, button=None, data=None):
        self.popup_evaluator()
        return True

    def on_webserver_log1_activate (self, button=None, data=None):
        w=gtk.Window()

        def refresh(b, t):
            b=t.get_buffer()
            begin,end = b.get_bounds ()
            b.delete(begin, end)
	    if self.controller.server:
		b.set_text(self.controller.server.logstream.getvalue())
	    else:
		b.set_text(_("No available webserver"))
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
        h=advene.gui.views.history.HistoryNavigation(self.controller, self.navigation_history)
        h.popup()
        return True

    def on_view_mediainformation_activate (self, button=None, data=None):
        """View mediainformation."""
        self.controller.position_update ()
        self.log (_("**** Media information ****"))
        self.log (_("Cached duration   : %s") % vlclib.format_time(self.controller.cached_duration))
        if self.controller.player.is_active():
            self.log (_("Current playlist : %s") % str(self.controller.player.playlist_get_list ()))
            self.log (_("Current position : %s") % vlclib.format_time(self.controller.player.current_position_value))
            self.log (_("Duration         : %s") % vlclib.format_time(self.controller.player.stream_duration))
            self.log (_("Status           : %s") % self.statustext[self.controller.player.status])
        else:
            self.log (_("Player not active."))
        return True

    def on_about1_activate (self, button=None, data=None):
        """Activate the About window."""
        self.gui.get_widget("about").show ()
        return True

    def about_hide (self, button=None, data=None):
        """Hide the About window."""
        self.gui.get_widget("about").hide ()
        return True

    def on_b_rewind_clicked (self, button=None, data=None):
        if self.controller.player.status == self.controller.player.PlayingStatus:
            self.controller.move_position (-config.data.player_preferences['time_increment'])
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
            self.controller.move_position (config.data.player_preferences['time_increment'])
        return True

    def on_b_addfile_clicked (self, button=None, data=None):
        """Open a movie file"""
        if config.data.path['data']:
            d=config.data.path['data']
        else:
            d=None

        filename=advene.gui.util.get_filename(title=_("Select a movie file"),
                                              action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                              button=gtk.STOCK_OPEN,
					      default_dir=d)
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
	    'duration': str(self.controller.cached_duration),
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
                self.controller.cached_duration = long(cache['duration'])
            except ValueError:
                pass
        return True

    def on_preferences1_activate (self, button=None, data=None):
        cache={
            'osd': config.data.player_preferences['osdtext'],
            'history-limit': config.data.preferences['history-size-limit'],
            'embed-treeview': config.data.preferences['embed-treeview'],
	    'toolbarstyle': self.gui.get_widget("toolbar_control").get_style(),
	    'data': config.data.path['data'],
	    'plugins': config.data.path['plugins'],
	    'advene': config.data.path['advene'],
	    'imagecache': config.data.path['imagecache'],
	    'moviepath': config.data.path['moviepath'],
            }

        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Preferences"))
	ew.add_title(_("General"))
        ew.add_checkbox(_("OSD"), "osd", _("Display captions on the video"))
        ew.add_checkbox(_("Embed treeview"), "embed-treeview", _("Embed a treeview in the application window\nChange will apply on application restart."))
        ew.add_spin(_("History size"), "history-limit", _("History filelist size limit"),
                    -1, 20)
        ew.add_option(_("Toolbar style"), "toolbarstyle", _("Toolbar style"), 
		      { _('Icons only'): gtk.TOOLBAR_ICONS,
			_('Text only'): gtk.TOOLBAR_TEXT,
			_('Both'): gtk.TOOLBAR_BOTH, 
			}
		      )

	ew.add_title(_("Paths"))

        ew.add_dir_selector(_("Data"), "data", _("Default directory for data files"))
        ew.add_dir_selector(_("Movie path"), "moviepath", _("List of directories (separated by %s) to search for movie files (_ means package directory)") % os.path.pathsep)
        ew.add_dir_selector(_("Imagecache"), "imagecache", _("Directory for storing the snapshot cache"))
        ew.add_dir_selector(_("Player"), "plugins", _("Directory of the video player"))

        res=ew.popup()
        if res:
            config.data.player_preferences['osdtext']=cache['osd']
            config.data.preferences['history-size-limit']=cache['history-limit']
            config.data.preferences['embed-treeview']=cache['embed-treeview']
            for t in ('toolbar_control', 'toolbar_view', 'toolbar_fileop', 'toolbar_create'):
                self.gui.get_widget(t).set_style(cache['toolbarstyle'])
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
        for n in ('caption', 'osdfont', 'snapshot', 'vout'):
            cache[n] = config.data.player[n]

        ew=advene.gui.edit.properties.EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Player configuration"))
        ew.add_title(_("Captions"))
        ew.add_checkbox(_("Enable"), "caption", _("Enable video captions"))
        ew.add_file_selector(_("Font"), "osdfont", _("TrueType font for captions"))
        
        ew.add_title(_("Snapshots"))
        ew.add_checkbox(_("Enable"), "snapshot", _("Enable snapshots"))
        ew.add_spin(_("Width"), "width", _("Snapshot width"), 0, 1280)
        ew.add_spin(_("Height"), "height", _("Snapshot height"), 0, 1280)
        
        ew.add_title(_("Video"))
        options={_("Default"): 'default' }
        if config.data.os == 'win32':
            options[_("GDI")] = 'wingdi'
            options[_("Direct X")] = 'directx'
        else:
            options[_("X11")] = 'x11'
        ew.add_option(_("Output"), "vout", _("Video output module"), options)

        ew.add_title(_("Verbosity"))
        ew.add_spin(_("Level"), "level", _("Verbosity level. -1 for no messages."),
                    -1, 3)
        
        res=ew.popup()
        if res:
            for n in ('caption', 'osdfont', 'snapshot', 'vout'):
                config.data.player[n] = cache[n]
            config.data.player['snapshot-dimensions']    = (cache['width'] , 
                                                            cache['height'])
            if cache['level'] == -1:
                config.data.player['verbose'] = None
            else:
                config.data.player['verbose'] = cache['level']
            self.controller.restart_player ()
            if self.visual_id:
                self.controller.player.set_visual(self.visual_id)
        return True

    def on_save_imagecache1_activate (self, button=None, data=None):
	id_ = vlclib.mediafile2id (self.controller.get_default_media())
        d=self.controller.imagecache.save (id_)
	self.log(_("Imagecache saved to %s") % d)
        return True

    def on_restart_player1_activate (self, button=None, data=None):
        self.log (_("Restarting player..."))
        self.controller.restart_player ()
        if self.visual_id:
            self.controller.player.set_visual(self.visual_id)
        return True

    def on_slider_button_press_event (self, button=None, data=None):
        self.slider_move = True

    def on_slider_button_release_event (self, button=None, data=None):
        p = self.controller.create_position (value = long(self.gui.slider.get_value ()))
        self.controller.update_status('set', p)
        self.slider_move = False

    def on_help1_activate (self, button=None, data=None):
        helpfile=os.path.join( config.data.path['web'], 'user.html' )
        if os.access(helpfile, os.R_OK):
            self.controller.open_url (helpfile)
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

    def on_about_web_button_clicked(self, button=None, data=None):
        self.controller.open_url('http://liris.cnrs.fr/advene/')
        return True

if __name__ == '__main__':
    v = AdveneGUI ()
    try:
        v.main (sys.argv[1:])
    except Exception, e:
        e, v, tb = sys.exc_info()
	print config.data.version_string
        print _("Got exception %s. Stopping services...") % str(e)
        v.on_exit ()
        print _("*** Exception ***")
        import code
        code.traceback.print_exception (e, v, tb)
