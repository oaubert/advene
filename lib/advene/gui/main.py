"""Advene GUI.

This module defines the GUI classes. The main one is L{AdveneGUI},
which is instantiated with a GLADE XML file. It defines the important
methods and the various GUI callbacks (generally all methods with the
C{on_} prefix).
"""

import sys, time
import cStringIO

import advene.core.config as config

import gettext
gettext.install('advene', unicode=True)
gettext.textdomain('advene')

# For gtk/glade
import pygtk
pygtk.require ('2.0')
import gtk
import gtk.glade
gtk.glade.bindtextdomain('advene')

import webbrowser

import advene.core.controller

import advene.rules.elements
import advene.rules.ecaengine

from advene.model.package import Package 
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.fragment import MillisecondFragment
import advene.model.constants
import advene.model.tal.context

import advene.core.mediacontrol

from advene.core.imagecache import ImageCache
import advene.util.vlclib as vlclib
import advene.gui.util
import advene.gui.views.tree
import advene.gui.views.timeline
import advene.gui.views.logwindow
import advene.gui.views.browser
import advene.gui.views.history
import advene.gui.edit.rules
import advene.gui.edit.dvdselect
import advene.gui.edit.elements
import advene.gui.edit.create

from advene.gui.edit.annotation import AnnotationEdit
from advene.gui.edit.timeadjustment import TimeAdjustment

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
      
    @ivar current_type: the edited annotations will be created with this type
    @type current_type: advene.model.AnnotationType
    @ivar gui: the GUI model from libglade
    @ivar gui.logmessages: the logmessages window
    @ivar gui.slider: the slider widget
    @ivar gui.fs: the fileselector widget
    @ivar gui.current_annotation: the current annotation text widget
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

    @ivar webbrowser: the web browser
    @type webbrowser: webbrowser

    """
    
    def __init__ (self):
        """Initializes the GUI and other attributes.

        @param gladefile: the name of the GLADE XML file containing the interface definition
        @type gladefile: string
        """
        self.controller = advene.core.controller.AdveneController()
        gladefile=config.data.advenefile (config.data.gladefilename)
        # Glade init.
        gtk.glade.bindtextdomain(gettext.textdomain())
        gtk.glade.textdomain(gettext.textdomain())
        self.gui = gtk.glade.XML(gladefile, domain=gettext.textdomain())
        self.connect (self.gui)
        
        # Frequently used GUI widgets
        self.gui.logmessages = self.gui.get_widget("logmessages")
        self.gui.slider = self.gui.get_widget ("slider")
        # slider holds the position in ms units
        self.slider_move = False
        # but we display it in ms
        self.gui.slider.connect ("format-value", self.format_slider_value)

        # Combo box
        type_combo=self.gui.get_widget ("current_type_combo")
        type_combo.list.connect ("selection-changed", self.on_current_type_changed)

        # Populate default STBV menu
        self.update_stbv_menu()
        
        # Declaration of the fileselector
        self.gui.fs = gtk.FileSelection ("Select a file")
        self.gui.fs.ok_button.connect_after ("clicked", lambda win: self.gui.fs.hide ())
        self.gui.fs.cancel_button.connect ("clicked", lambda win: self.gui.fs.destroy ())
        if config.data.path['data']:
            self.gui.fs.set_filename (config.data.path['data'])

        self.gui.current_annotation = self.gui.get_widget ("current_annotation")
        self.gui.current_annotation.set_text ('['+_('None')+']')

        # Player status
        p=self.controller.player
        self.active_player_status=(p.PlayingStatus, p.PauseStatus,
                                   p.ForwardStatus, p.BackwardStatus)
        self.gui.player_status = self.gui.get_widget ("player_status")
        self.oldstatus = "NotStarted"

        self.webbrowser = webbrowser.get ()
        
        # Current Annotation (when defining a new one)
        self.annotation = None

        self.navigation_history=[]
        
        self.last_slow_position = 0
        
        # List of active annotation views (timeline, tree, ...)
        self.annotation_views = []

    def update_stbv (self, widget, view):
        """Callback for the STBV option menu.

        @param widget: the calling widget
        @type widget: a Gtk widget (OptionMenu)
        @param view: the selected view
        @type view: advene.model.view
        """
        self.controller.activate_stbv(view)
        return True
       
    def annotation_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        annotation=context.evaluateValue('annotation')
        event=context.evaluateValue('event')
        for v in self.annotation_views:
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
        for v in self.annotation_views:
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
        for v in self.annotation_views:
            try:
                v.update_view(view=view, event=event)
            except AttributeError:
                pass

        if view.content.mimetype == 'application/x-advene-ruleset':
            self.update_stbv_menu()
            
        return True
    
    def schema_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        schema=context.evaluateValue('schema')
        event=context.evaluateValue('event')
        for v in self.annotation_views:
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
        for v in self.annotation_views:
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
        for v in self.annotation_views:
            try:
                v.update_relationtype(relationtype=rt, event=event)
            except AttributeError:
                pass
        return True
    
    def updated_position_cb (self, context, parameters):
        position_before=context.evaluateValue('position_before')
        # Note: it works for the moment only because we take an
        # immediate snapshot but there is some delay between the
        # position update and the player reaction.
        # If it is corrected, it should always work because of the
        # snapshot cache in the player. To be tested...
        # FIXME: notify the History view
        self.controller.update_snapshot(long(position_before))
        self.navigation_history.append(position_before)
        print "New navigation history: %s" % self.navigation_history
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

        # FIXME: We have to register LogWindow actions before we load the ruleset
        # but we should have an introspection method to do this automatically
        self.logwindow=advene.gui.views.logwindow.LogWindow()
        self.register_view(self.logwindow)

        # Update the Message action (GUI version)
        self.controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="Message",
            method=self.message_log,
            description=_("Display a message"),
            parameters={'message': _("String to display.")}
            ))

        # We add a Treeview in the main app window
        tree = advene.gui.views.tree.TreeWidget(self.controller.package,
                                                controller=self.controller)
        self.gui.get_widget("html_scrollwindow").add (tree.get_widget())
        tree.get_widget().show_all()
        self.register_view (tree)

        self.controller.event_handler.internal_rule (event="PackageLoad",
                                                     method=self.manage_package_load)
        # Annotation lifecycle
        for e in ('AnnotationCreate', 'AnnotationEditEnd', 'AnnotationDelete'):
            self.controller.event_handler.internal_rule (event=e,
                                                         method=self.annotation_lifecycle)
        # Relation lifecycle
        for e in ('RelationCreate', 'RelationEditEnd', 'RelationDelete'):
            self.controller.event_handler.internal_rule (event=e,
                                                         method=self.relation_lifecycle)
        # View lifecycle
        for e in ('ViewCreate', 'ViewEditEnd', 'ViewDelete'):
            self.controller.event_handler.internal_rule (event=e,
                                                         method=self.view_lifecycle)
        # Schema lifecycle
        for e in ('SchemaCreate', 'SchemaEditEnd', 'SchemaDelete'):
            self.controller.event_handler.internal_rule (event=e,
                                                         method=self.schema_lifecycle)
        # AnnotationType lifecycle
        for e in ('AnnotationTypeCreate', 'AnnotationTypeEditEnd', 'AnnotationTypeDelete'):
            self.controller.event_handler.internal_rule (event=e,
                                                         method=self.annotationtype_lifecycle)
        # RelationType lifecycle
        for e in ('RelationTypeCreate', 'RelationTypeEditEnd', 'RelationTypeDelete'):
            self.controller.event_handler.internal_rule (event=e,
                                                         method=self.relationtype_lifecycle)

        self.controller.event_handler.internal_rule (event="PlayerSet",
                                                     method=self.updated_position_cb)

        self.controller.init(args)
        
        if config.data.webserver['mode'] == 1:
            self.log(_("Using Mainloop input handling for webserver..."))
            gtk.input_add (self.controller.server,
                           gtk.gdk.INPUT_READ,
                           self.handle_http_request)

        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        gtk.timeout_add (100, self.update_display)
        gtk.main ()
        self.controller.notify ("ApplicationEnd")

    def format_time (self, val=0):
        """Formats a value (in milliseconds) into a time string.

        @param val: the value
        @type val: int
        @return: the formatted string
        @rtype: string
        """ 
        (s, ms) = divmod(long(val), 1000)
        # Format: HH:MM:SS.mmm
        return "%s.%03d" % (time.strftime("%H:%M:%S", time.gmtime(s)), ms)
       
    def format_slider_value (self, slider=None, val=0):
        """Formats a value (in milliseconds) into a time string.

        @param slider: a slider widget
        @param val: the value
        @type val: int
        @return: the formatted string
        @rtype: string
        """
        return self.format_time (val)

    def set_current_type (self, t):
        """Set the current annotation type.

        @param name: annotation type
        @type name: string
        """
        self.current_type = t
        type_combo=self.gui.get_widget ("current_type_combo")
        type_combo.entry.set_text (t.title)

    def on_edit_current_stbv_clicked(self, button):
        widget = self.gui.get_widget("stbv_combo").get_menu().get_active()
        stbv=widget.get_data("stbv")
        if stbv is None:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                _("Do you want to create a new dynamic view?"))
            response=dialog.run()
            dialog.destroy()
            if response != gtk.RESPONSE_YES:
                return True
            cr = advene.gui.edit.create.CreateElementPopup(type_=View,
                                                           parent=self.controller.package,
                                                           controller=self.controller)
            cr.popup()
            return True
        try:
            pop = advene.gui.edit.elements.get_edit_popup (stbv, self.controller)
        except TypeError, e:
            print _("Error: unable to find an edit popup for %s:\n%s") % (stbv, unicode(e))
        else:
            pop.edit ()
        return True
    
    def update_stbv_menu (self):
        """Update the STBV menu."""
        stbv_menu = self.gui.get_widget("stbv_combo").get_menu()
        if stbv_menu is None:
            # Application initialization
            stbv_menu = gtk.Menu()
            self.gui.get_widget("stbv_combo").set_menu(stbv_menu)

        for c in stbv_menu.get_children():
            stbv_menu.remove(c)
        
        default_item = gtk.MenuItem(_("None"))
        default_item.set_data("stbv", None)
        default_item.connect("activate", self.update_stbv, None)
        default_item.show()
        stbv_menu.append(default_item)

        for v in self.controller.get_stbv_list():
            i = gtk.MenuItem(v.title or v.id)
            i.set_data("stbv", v)
            i.connect("activate", self.update_stbv, v)
            i.show()
            stbv_menu.append(i)

        stbv_menu.set_active(0)
        stbv_menu.reposition()
        stbv_menu.show()
        return True

    def update_gui (self):
        """Update the GUI.

        This method should be called upon package loading, or when a
        new view or type is created, or when an existing one is
        modified, in order to reflect changes.
        """
        
        # Update the available types list
        available_types = self.controller.package.annotationTypes
        # Update the combo box
        type_combo=self.gui.get_widget ("current_type_combo")
        type_combo.list.clear_items(0, -1)
        labels=[]
        for t in available_types:
            i = gtk.ListItem()
            l = gtk.Label(t.title)
            l.set_alignment (0, 0)
            i.add (l)
            i.set_data ('type', t)
            type_combo.set_item_string(i, t.title)
            labels.append(i)
        # This sort is suboptimal (many calls to get_data()) but it is
        # not critical , so we do not try to optimize it
        labels.sort(lambda a,b: cmp(a.get_data('type').title,
                                    b.get_data('type').title))
        type_combo.list.append_items(labels)
        type_combo.list.show_all()
        self.set_current_type (available_types[0])

        self.update_stbv_menu()
        return
        
    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.
        
        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        self.log (_("Package %s loaded. %d annotations.") % (self.controller.package.uri,
                                                             len(self.controller.package.annotations)))
        self.update_gui()
        # Update the main window title
        self.gui.get_widget ("win").set_title(" - ".join((_("Advene"),
                                                          self.controller.package.title or "No title")))
        for v in self.annotation_views:
            try:
                v.update_model(self.controller.package)
            except AttributeError:
                pass
        
        return True
    
    def handle_http_request (self, source, condition):
        """Handle a HTTP request.

        This method is used if config.data.webserver['mode'] == 1.  
        """
        # Make sure that all exceptions are catched, else the gtk mainloop
        # will not execute update_display.
        try:
            source.handle_request ()
        except Exception, e:
            print _("Got exception %s in web server") % str(e)
            import code
            e, v, tb = sys.exc_info()
            code.traceback.print_exception (e, v, tb)
        return True
        
    def log (self, msg):
        """Add a new log message to the logmessage window.

        @param msg: the message
        @type msg: string
        """
        buf = self.gui.logmessages.get_buffer ()
        mes = str(msg) + "\n"
        buf.insert_at_cursor (mes)
        endmark = buf.create_mark ("end", buf.get_end_iter (), True)
        self.gui.logmessages.scroll_mark_onscreen (endmark)
        return

    def message_log (self, context, parameters):
        """Event Handler for the message action.

        Essentialy a wrapper for the X{log} method.

        @param message: the message to display
        @type message: string
        """
        if parameters.has_key('message'):
            message=context.evaluateValue(parameters['message'])
        else:
            message="No message..."
        self.log (message)
        return True
            
    def file_selector (self, callback=None, label="Select a file",
                       default=""):
        """Display the generic file selector.

        Callbacks are X{file_selected_cb}, X{annotations_load_cb},
        X{annotations_save_cb}.

        @param callback: method to be called on validation
        @type callback: method
        @param label: label of the fileselector window
        @type label: string
        @param default: default filename
        @type default: string
        """
        self.gui.fs.set_property ("title", label)
        self.gui.fs.set_property ("filename", default)
        self.gui.fs.set_property ("select-multiple", False)
        self.gui.fs.set_property ("show-fileops", False)

        if callback:
            # Disconnecting the old callback
            try:
                self.gui.fs.ok_button.disconnect (self.gui.fs.connect_id)
            except:
                pass
            # Connecting the new one
            self.gui.fs.connect_id = self.gui.fs.ok_button.connect ("clicked", callback, self.gui.fs)
        self.gui.fs.show ()
	return True

    def file_selected_cb (self, button, fs):
        """Open and play the selected movie file.

        Callback used by file_selector.
        """
        file_ = fs.get_property ("filename")
        if isinstance(file_, unicode):
            file_=file_.encode('utf8')
        self.controller.player.playlist_add_item (file_)
        self.controller.update_status ("start")
        return True

    def annotations_load_cb (self, button, fs):
        """Load a package."""
        file_ = fs.get_property ("filename")
        self.controller.load_package (uri=file_)
        return True

    def annotations_save_cb (self, button, fs):
        """Save the current package."""
        file_ = fs.get_property ("filename")
        self.controller.save_package(as=file_)
        return True

    def register_view (self, view):
        """Register a view plugin.

        @param view: the view to register
        @type view: a view plugin (cf advene.gui.views)
        """
        if view not in self.annotation_views:
            self.annotation_views.append (view)
            try:
                view.register_callback (controller=self.controller)
            except AttributeError:
                pass
        return True

    def unregister_view (self, view):
        """Unregister a view plugin
        """
        if view in self.annotation_views:
            self.annotation_views.remove (view)
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

        try:
            pos=self.controller.update()
        except self.controller.player.InternalException:
            # FIXME: something sensible to do here ?
            print _("Internal error on video player")
            return True
        
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
                self.gui.player_status.set_text (repr(self.controller.player.status)[:-6])

            if (self.annotation is not None
                and self.annotation.content.data != self.gui.current_annotation.get_text()):
                self.gui.current_annotation.set_text (self.annotation.content.data)
                
            # Update the position mark in the registered views
            if (abs(self.last_slow_position - pos) > config.data.slow_update_delay
                or pos < self.last_slow_position):
                self.last_slow_position = pos
                for v in self.annotation_views:
                    try:
                        v.update_position (pos)
                    except AttributeError:
                        pass
                
        else:
            self.gui.slider.set_value (0)
            if self.controller.player.status != self.oldstatus:
                self.oldstatus = self.controller.player.status
                self.gui.player_status.set_text (repr(self.controller.player.status)[:-6])
            # New position_update call to handle the starting case (the first
            # returned status is None)
            self.controller.position_update ()

        return True

    def on_current_type_changed (self, win=None):
        """Callback used to select the current type of the edited annotation.
        """
        sel = win.get_selection()
        if sel:
            t = sel[0].get_data('type')
            self.set_current_type (t)
            return True
        else:
            return False

    def on_exit(self, source=None, event=None):
        """Generic exit callback."""
        self.controller.on_exit()

        if self.controller.modified:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                _("Your package has been modified but not saved.\nQuit anyway?"))
            response=dialog.run()
            dialog.destroy()
            if response != gtk.RESPONSE_YES:
                return False
            
        gtk.main_quit()
        return True

    # Callbacks function. Skeletons can be generated by glade2py
    
    def on_win_key_press_event (self, win=None, event=None):
        """Keypress handling."""
        # Control-shortcuts
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                # Quit
                self.on_exit (win, None)
            elif event.keyval == gtk.keysyms.o:
                # Open an annotation file
                self.on_open1_activate (win, None)
            elif event.keyval == gtk.keysyms.m:
                # Open a video file
                self.on_b_addfile_clicked (win, None)
            elif event.keyval == gtk.keysyms.s:
                # Save the current annotation file
                self.on_save1_activate (win, None)
            else:
                return False
            
        if event.keyval == gtk.keysyms.Return:
            # Non-pausing annotation mode
            self.controller.position_update ()
            if self.annotation is None:
                # Start a new annotation
                self.annotation = self.controller.package.createAnnotation(type = self.current_type,
                                                                           fragment = MillisecondFragment (begin=self.controller.player.current_position_value, duration=30000))
                self.log (_("Defining a new annotation..."))
                self.controller.notify ("AnnotationCreate", annotation=self.annotation)
            else:
                # End the annotation. Store it in the annotation list
                self.annotation.fragment.end = self.controller.player.current_position_value
                self.controller.package.annotations.append (self.annotation)
                self.log (_("New annotation: %s") % self.annotation)
                self.gui.current_annotation.set_text ('['+_('None')+']')
                self.controller.notify ("AnnotationEditEnd", annotation=self.annotation)
                if self.controller.player.status == self.controller.player.PauseStatus:
                    self.controller.update_status ("resume")
                self.annotation = None
            return True
        elif event.keyval == gtk.keysyms.space:
            # Pausing annotation mode
            if self.annotation is None:
                # Not defining any annotation yet. Pause the stream
                if self.controller.player.status != self.controller.player.PauseStatus:
                    self.controller.update_status ("pause")
                self.controller.position_update ()
                self.annotation = self.controller.package.createAnnotation (type = self.current_type,
                                                                            fragment = MillisecondFragment (begin=self.controller.player.current_position_value, duration=30000))
                self.controller.notify ("AnnotationCreate", annotation=self.annotation)
                self.log (_("Defining a new annotation (Tab to resume the play)"))
            else:
                self.annotation.content.data += " "
            self.update_display ()
            return True
        elif event.keyval == gtk.keysyms.BackSpace:
            if self.annotation != None:
                self.annotation.content.data = self.annotation.content.data[:-1]
                self.update_display ()
                return True
            else:
                return False
        # Navigation keys
        elif event.keyval == gtk.keysyms.Tab:
            self.controller.update_status ("pause")
            return True
        elif event.keyval == gtk.keysyms.Right:
            self.controller.move_position (config.data.preferences['time_increment'])
            return True
        elif event.keyval == gtk.keysyms.Left:
            self.controller.move_position (-config.data.preferences['time_increment'])
            return True
        elif event.keyval == gtk.keysyms.Home:            
            self.controller.update_status ("set", self.controller.create_position (0))
            return True
        elif event.keyval == gtk.keysyms.End:
            c=self.controller
            pos = c.create_position (value = -config.data.preferences['time_increment'],
                                     key = c.player.MediaTime,
                                     origin = c.player.ModuloPosition)
            self.controller.update_status ("set", pos)
            return True
        elif event.keyval == gtk.keysyms.Page_Down:
            # Next chapter
            return True
        elif event.keyval == gtk.keysyms.Page_Up:
            # Previous chapter
            return True
        elif event.keyval > 32 and event.keyval < 256:
            k = chr(event.keyval)
            if self.annotation:
                self.annotation.content.data += k
                self.update_display ()
                return True
        return True

    def on_new1_activate (self, button=None, data=None):
        """New package. Erase the current one."""
        self.load_package ()
	return True

    def on_open1_activate (self, button=None, data=None):
        """Open a file selector to load a package."""
        self.file_selector (callback=self.annotations_load_cb,
                            label=_("Load a package"))
	return True

    def on_save1_activate (self, button=None, data=None):
        """Save the current package."""
        if self.controller.package.uri == "":
            self.on_save_as1_activate (button, data)
        else:
            self.controller.save_package ()
	return True

    def on_save_as1_activate (self, button=None, data=None):
        """Save the annotation list with a new name."""
        self.file_selector (callback=self.annotations_save_cb,
                            label=_("Save the current package"))
	return True

    def on_quit1_activate (self, button=None, data=None):
        """Gtk callback to quit."""
        self.on_exit (button, data)
        return True

    def on_cut1_activate (self, button=None, data=None):
        print "Not implemented yet."
	return True

    def on_copy1_activate (self, button=None, data=None):
        print "Not implemented yet."
	return True

    def on_paste1_activate (self, button=None, data=None):
        print "Not implemented yet."
	return True

    def on_delete1_activate (self, button=None, data=None):
        print "Not implemented yet."
	return True

    def on_timeline1_activate (self, button=None, data=None):
        """Timeline View of loaded defined annotations."""
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        def key_pressed_cb (win, event):
            if event.state & gtk.gdk.CONTROL_MASK:
                # The Control-key is held. Special actions :
                if event.keyval == gtk.keysyms.q:
                    win.emit('destroy')
                return True
            if event.keyval == gtk.keysyms.Escape:
                win.emit('destroy')
                return True
            return False

        window.connect ("key-press-event", key_pressed_cb)

        window.set_title (self.controller.package.title or "???")

        vbox = gtk.VBox()
        
        window.add (vbox)

        duration = self.controller.cached_duration
        if duration <= 0:
            if self.controller.package.annotations:
                duration = max([a.fragment.end for a in self.controller.package.annotations ])
            else:
                duration = 0
            
        t = advene.gui.views.timeline.TimeLine (self.controller.package.annotations,
                                                minimum=0,
                                                maximum=duration,
                                                controller=self.controller)
        window.timeline = t
        timeline_widget = t.get_packed_widget()
        vbox.add (timeline_widget)

        hbox = gtk.HButtonBox()
        vbox.pack_start (hbox, expand=False)

        fraction_adj = gtk.Adjustment (value=0.1,
                                       lower=0.01,
                                       upper=1.0,
                                       step_incr=.01,
                                       page_incr=.02)

        def zoom_event (win=None, timel=None, adj=None):
            timel.display_fraction_event (widget=win, fraction=adj.value)
            return True

        s = gtk.HScale (fraction_adj)
        s.set_digits(2)
        s.connect ("value-changed", zoom_event, t, fraction_adj)
        hbox.add (s)

        hbox.add (t.highlight_activated_toggle)
        hbox.add (t.scroll_to_activated_toggle)
        
        b = gtk.Button (stock=gtk.STOCK_OK)
        b.connect ("clicked", self.close_view_cb, window, t)
        hbox.add (b)
        
        vbox.set_homogeneous (False)
        
        window.connect ("destroy", self.close_view_cb, window, t)

        self.register_view (t)

        height=max(window.timeline.layer_position.values() or (1,)) + 3 * window.timeline.button_height
        window.set_default_size (640, height)
        window.show_all()

        # Make sure that the timeline display is in sync with the
        # fraction widget value
        t.display_fraction_event (window,
                                  fraction=fraction_adj.value)
                
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
        edit=advene.gui.edit.rules.EditRuleSet(rs,
                                               catalog=self.controller.event_handler.catalog)
        vbox.add(edit.get_widget())
        edit.get_widget().show()

        hb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", edit.add_rule)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.connect("clicked", edit.remove_rule)
        hb.pack_start(b, expand=False)

        def save_ruleset(button, type_):
            edit.update_value()
            # edit.model has been edited
            self.controller.event_handler.set_ruleset(edit.model, type_=type_)
            w.destroy()
            return True

        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect("clicked", save_ruleset, 'default')
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect("clicked", lambda e: w.destroy())
        hb.pack_end(b, expand=False)

        hb.show_all()

        vbox.pack_start(hb, expand=False)

        vbox.show()

        w.show()
        return True

    def on_view_logwindow_activate (self, button=None, data=None):
        """Open logwindow view plugin."""
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        window.set_title (_("Log Window"))
        window.add (self.logwindow.get_widget())

        window.connect ("destroy", self.close_view_cb, window, self.logwindow)
        window.show_all()
        return True
        
    def on_view_annotations_activate (self, button=None, data=None):
        """Open treeview view plugin."""
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_size_request (640, 480)

        window.set_title (_("Package %s") % (self.controller.package.title or _("No title")))
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        window.add (sw)
        tree = advene.gui.views.tree.TreeWidget(self.controller.package,
                                                controller=self.controller)
        sw.add (tree.get_widget())
        self.register_view (tree)

        window.connect ("destroy", self.close_view_cb, window, tree)
        window.show_all()
        return True

    def on_browser1_activate (self, button=None, data=None):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_size_request (320, 200)

        window.connect ("destroy", lambda e: window.destroy())
        window.set_title (self.controller.package.title or _("No package title"))

        vbox = gtk.VBox()

        window.add (vbox)

        browser = advene.gui.views.browser.Browser(self.controller.package)
        vbox.add (browser.get_widget())

        hbox = gtk.HButtonBox()
        vbox.pack_start (hbox, expand=False)

        b = gtk.Button (stock=gtk.STOCK_CLOSE)
        b.connect ("clicked", lambda w: window.destroy ())
        hbox.add (b)

        vbox.set_homogeneous (gtk.FALSE)

        window.show_all()
        
        return True

    def on_navigationhistory1_activate (self, button=None, data=None):
        h=advene.gui.views.history.HistoryNavigation(self.controller, self.navigation_history)
        h.popup()
        return True

    def on_view_mediainformation_activate (self, button=None, data=None):
        """View mediainformation."""
        self.controller.position_update ()
        self.log (_("**** Media information ****"))
        self.log (_("Cached duration   : %d") % self.controller.cached_duration)
        if self.controller.player.is_active():
            self.log (_("Current playlist : %s") % str(self.controller.player.playlist_get_list ()))
            self.log (_("Current position : %d") % self.controller.player.current_position_value)
            self.log (_("Duration         : %d") % self.controller.player.stream_duration)
            self.log (_("Status           : %s") % repr(self.controller.player.status))
        else:
            self.log (_("Player not active."))
        return True

    def on_start_web_browser_activate (self, button=None, data=None):
        """Open a browser on current package's root."""
        url = self.controller.server.get_url_for_alias('advene')
        if url is not None:
            self.webbrowser.open (url)
        else:
            self.log (("No current package"))
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
            self.controller.move_position (-config.data.preferences['time_increment'])
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
            self.controller.move_position (config.data.preferences['time_increment'])
	return True

    def on_b_addfile_clicked (self, button=None, data=None):
        self.file_selector (callback=self.file_selected_cb,
                            label=_("Select a movie file"))
	return True

    def on_b_selectdvd_clicked (self, button=None, data=None):
        """Play a DVD."""
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title(_("Title/Chapter selection"))
        
        window.connect ("destroy", lambda e: window.destroy())

        vbox=gtk.VBox()
        
        sel=advene.gui.edit.dvdselect.DVDSelect(controller=self.controller,
                                                current=self.controller.get_default_media())
        vbox.add(sel.get_widget())

        hbox=gtk.HButtonBox()

        def validate(button=None, sel=None, window=None):
            self.controller.update_status("stop")
            url=sel.get_url()
            self.controller.set_default_media(url)
            sel.get_widget().destroy()
            self.controller.player.playlist_clear()
            if isinstance(url, unicode):
                url=url.encode('utf8')
            self.controller.player.playlist_add_item (url)
            self.controller.update_status ("start")
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
        self.on_exit (button, data)
	return True

    def on_package_properties1_activate (self, button=None, data=None):
        self.gui.get_widget ("prop_author_id").set_text (self.controller.package.author)
        self.gui.get_widget ("prop_date").set_text (self.controller.package.date)        
        self.gui.get_widget ("prop_media").set_text (self.controller.get_default_media() or "")
        self.gui.get_widget ("prop_title").set_text (self.controller.package.title or "")

        self.gui.get_widget ("properties").show ()
        return True

    def on_preferences1_activate (self, button=None, data=None):
        self.gui.get_widget ("osdtext_toggle").set_active (self.preferences['osdtext'])
        self.gui.get_widget ("preferences").show ()
        return True

    def on_preferences_ok_clicked (self, button=None, data=None):
        self.preferences['osdtext'] = self.gui.get_widget ("osdtext_toggle").get_active ()
        self.gui.get_widget ("preferences").hide ()
        self.update_view ()
        return True

    def on_preferences_cancel_clicked (self, button=None, data=None):
        self.gui.get_widget ("preferences").hide ()
        return True

    def on_prop_ok_clicked (self, button=None, data=None):
        self.controller.package.author = self.gui.get_widget ("prop_author_id").get_text ()
        self.controller.package.date = self.gui.get_widget ("prop_date").get_text ()

        mediafile = self.gui.get_widget ("prop_media").get_text ()
        self.controller.package.setMetaData (config.data.namespace,
                                  "mediafile",
                                  mediafile)
        id_ = vlclib.mediafile2id (mediafile)
        self.controller.imagecache.save (id_)

        self.controller.package.title = self.gui.get_widget ("prop_title").get_text ()

        self.gui.get_widget ("properties").hide ()
        return True

    def on_prop_cancel_clicked (self, button=None, data=None):
        self.gui.get_widget ("properties").hide ()
        return True

    def on_configure_player1_activate (self, button=None, data=None):
        self.gui.get_widget ("player_caption_button").set_active (config.data.player['caption'])
        self.gui.get_widget ("player_osd_font").set_text (config.data.player['osdfont'])
        self.gui.get_widget ("player_snapshot_button").set_active (config.data.player['snapshot'])
        dim = config.data.player['snapshot-dimensions']
        self.gui.get_widget ("player_snapshot_width").set_value (dim[0])
        self.gui.get_widget ("player_snapshot_height").set_value (dim[1])

        if config.data.player['verbose'] is None:
            self.gui.get_widget ("player_verbose_button").set_active (False)
        else:
            self.gui.get_widget ("player_verbose_button").set_active (True)
            self.gui.get_widget ("player_debut_level").set_value(config.data.player['verbose'])
        self.gui.get_widget ("playerproperties").show ()
        return True

    def on_player_properties_apply_clicked (self, button=None, data=None):
        config.data.player['caption'] = self.gui.get_widget ("player_caption_button").get_active ()
        config.data.player['osdfont'] = self.gui.get_widget ("player_osd_font").get_text ()
        config.data.player['snapshot'] = self.gui.get_widget ("player_snapshot_button").get_active ()
        w = self.gui.get_widget ("player_snapshot_width").get_value_as_int ()
        h = self.gui.get_widget ("player_snapshot_height").get_value_as_int ()
        config.data.player['snapshot-dimensions'] = (w, h)
        if self.gui.get_widget ("player_verbose_button").get_active ():
            config.data.player['verbose'] = self.gui.get_widget ("player_debug_level").get_value_as_int ()
        else:
            config.data.player['verbose'] = None
        self.restart_player ()
        return True
    
    def on_player_properties_ok_clicked (self, button=None, data=None):
        self.on_player_properties_apply_clicked ()
        self.gui.get_widget ("playerproperties").hide ()
        return True

    def on_player_properties_cancel_clicked (self, button=None, data=None):
        self.gui.get_widget ("playerproperties").hide ()
        return True

    def on_save_imagecache1_activate (self, button=None, data=None):
        name = vlclib.package2id (self.controller.package)
        self.controller.imagecache.save (name)
        return True

    def on_restart_player1_activate (self, button=None, data=None):
        self.log (_("Restarting player..."))
        self.controller.restart_player ()
        return True

    def on_slider_button_press_event (self, button=None, data=None):
        self.slider_move = True

    def on_slider_button_release_event (self, button=None, data=None):
        p = self.controller.create_position (value = self.gui.slider.get_value ())
        self.controller.update_status('set', p)
        self.slider_move = False

    def on_update_snapshots1_activate (self, button=None, data=None):
        self.gui.get_widget ("update-snapshots").show ()
        return True

    def on_update_snapshots_execute_clicked (self, button=None, data=None):
        # Activate the Stop button
        self.gui.get_widget ("update-snapshots-stop").set_sensitive (True)
        self.gui.get_widget ("update-snapshots-execute").set_sensitive (False)

        def update_progress_callback(value=0):
            bar = self.gui.get_widget ("snapshots-progressbar")
            bar.set_fraction (value)
            return True

        def stop_callback(context, parameters):
            print "Stop callback"
            self.gui.get_widget ("update-snapshots-stop").set_sensitive (False)
            self.gui.get_widget ("update-snapshots-execute").set_sensitive (True)
            return True

        self.controller.start_update_snapshots(progress_callback=update_progress_callback,
                                               stop_callback=stop_callback)
        return True
    
    def on_update_snapshots_stop_clicked (self, button=None, data=None):
        self.controller.stop_update_snapshots()
        return True
    
    def on_update_snapshots_ok_clicked (self, button=None, data=None):
        self.controller.stop_update_snapshots()
        self.gui.get_widget ("update-snapshots").hide ()
        return True
    
if __name__ == '__main__':
    v = AdveneGUI ()
    try:
        v.main (sys.argv[1:])
    except Exception, e:
        print _("Got exception %s. Stopping services...") % str(e)
        v.on_exit ()
        print _("*** Exception ***")
        import code
        e, v, tb = sys.exc_info()
        code.traceback.print_exception (e, v, tb)
