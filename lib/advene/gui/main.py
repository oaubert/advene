"""Advene GUI.

This module defines the GUI classes. The main one is L{AdveneGUI},
which is instantiated with a GLADE XML file. It defines the important
methods and the various GUI callbacks (generally all methods with the
C{on_} prefix).
"""

import sys, time
import cStringIO
import os

import advene.core.config as config
import advene.core.version

import gettext
gettext.install('advene', unicode=True)
#gettext.install('advene', localedir=config.data.path['locale'], unicode=True)
gettext.textdomain('advene')
from gettext import gettext as _

# For gtk/glade
import pygtk
#pygtk.require ('2.0')
import gtk
import gtk.glade
gtk.glade.bindtextdomain('advene')

import webbrowser
import textwrap

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

import advene.util.importer

# GUI elements
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
import advene.gui.evaluator
import advene.gui.views.singletonpopup
import advene.gui.edit.imports
from advene.gui.views.transcription import TranscriptionView
import advene.gui.edit.transcribe

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
        """
        self.controller = advene.core.controller.AdveneController()
        self.controller.register_gui(self)
        
        gladefile=config.data.advenefile (config.data.gladefilename)
        # Glade init.
        gtk.glade.bindtextdomain(gettext.textdomain())
        gtk.glade.textdomain(gettext.textdomain())
        self.gui = gtk.glade.XML(gladefile, domain=gettext.textdomain())
        self.connect (self.gui)

        # Resize the main window
        window=self.gui.get_widget('win')
        self.init_window_size(window, 'main')
        
        # Frequently used GUI widgets
        self.gui.logmessages = self.gui.get_widget("logmessages")
        self.gui.slider = self.gui.get_widget ("slider")
        # slider holds the position in ms units
        self.slider_move = False
        # but we display it in ms
        self.gui.slider.connect ("format-value", self.format_slider_value)

        # About box
        self.gui.get_widget('about_web_button').set_label("Advene %s"
                                                          % advene.core.version.version)

        # Define combobox cell renderers
        for n in ("stbv_combo", "current_type_combo"):
            combobox=self.gui.get_widget(n)
            cell = gtk.CellRendererText()
            combobox.pack_start(cell, True)
            combobox.add_attribute(cell, 'text', 0)
            
        self.current_type=None

        self.gui.current_annotation = self.gui.get_widget ("current_annotation")
        self.gui.current_annotation.set_text ('['+_('None')+']')

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

        self.webbrowser = webbrowser.get ()

        # Current Annotation (when defining a new one)
        self.annotation = None

        self.navigation_history=[]

        self.last_slow_position = 0

        # List of active annotation views (timeline, tree, ...)
        self.annotation_views = []

        # Populate default STBV and type lists
        self.update_gui()

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
            # Update the combo box
            self.update_stbv_list()
            # Not ideal (we could edit the non-activated view) but it is
            # better for the general case (use of the Edit button)
            if event in ('ViewCreate', 'ViewEditEnd'):
                self.controller.activate_stbv(view)

        return True

    def query_lifecycle(self, context, parameters):
        """Method used to update the active views.

        It will propagate the event.
        """
        query=context.evaluateValue('query')
        event=context.evaluateValue('event')
        for v in self.annotation_views:
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

    def on_view_activation(self, context, parameters):
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
        # Note: it works for the moment only because we take an
        # immediate snapshot but there is some delay between the
        # position update and the player reaction.
        # If it is corrected, it should always work because of the
        # snapshot cache in the player. To be tested...
        # FIXME: notify the History view
        self.controller.update_snapshot(long(position_before))
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

        # FIXME: We have to register LogWindow actions before we load the ruleset
        # but we should have an introspection method to do this automatically
        self.logwindow=advene.gui.views.logwindow.LogWindow(controller=self.controller)
        self.register_view(self.logwindow)

        # Update the Message action (GUI version)
        self.controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="Message",
            method=self.action_message_log,
            description=_("Display a message"),
            parameters={'message': _("String to display.")},
            category='gui',
            ))

        self.controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="Popup",
            method=self.action_popup,
            description=_("Display a popup"),
            parameters={'message': _("String to display."),
                        'duration': _("Display duration in ms. Ignored if empty.")},
            category='gui',            
            ))

        self.controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="PopupGoto",
            method=self.action_popup_goto,
            description=_("Display a popup to go to another position"),
            parameters={'description': _("General description"),
                        'message': _("String to display."),
                        'position': _("New position"),
                        'duration': _("Display duration in ms. Ignored if empty.")},
            category='gui',
            ))

        self.controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="OpenView",
            method=self.action_open_view,
            description=_("Open a GUI view"),
            parameters={'guiview': _("View name (timeline or tree)"),
                        },
            category='gui',
            ))

        self.controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="PopupGoto2",
            method=self.generate_action_popup_goton(2),
            description=_("Display a popup with 2 options"),
            parameters={'description': _("General description"),
                        'message1': _("First option description"),
                        'position1': _("First position"),
                        'message2': _("Second option description"),
                        'position2': _("Second position"),
                        'duration': _("Display duration in ms. Ignored if empty.")
                        },
            category='gui',
            ))
        self.controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="PopupGoto3",
            method=self.generate_action_popup_goton(3),
            description=_("Display a popup with 3 options"),
            parameters={'description': _("General description"),
                        'message1': _("First option description"),
                        'position1': _("First position"),
                        'message2': _("Second option description"),
                        'position2': _("Second position"),
                        'message3': _("Third option description"),
                        'position3': _("Third position"),
                        'duration': _("Display duration in ms. Ignored if empty.")
                        },
            category='gui',
            ))

        # Create the SingletonPopup instance
        self.singletonpopup=advene.gui.views.singletonpopup.SingletonPopup(controller=self.controller,
                                            autohide=False)

        # We add a Treeview in the main app window
        tree = advene.gui.views.tree.TreeWidget(self.controller.package,
                                                controller=self.controller)
        self.gui.get_widget("html_scrollwindow").add (tree.get_widget())
        tree.get_widget().show_all()
        self.register_view (tree)

        self.controller.event_handler.internal_rule (event="PackageLoad",
                                                     method=self.manage_package_load)
        self.controller.event_handler.internal_rule (event="PackageSave",
                                                     method=self.manage_package_save)
        # Annotation lifecycle
        for e in ('AnnotationCreate', 'AnnotationEditEnd', 'AnnotationDelete',
                  'AnnotationActivate', 'AnnotationDeactivate'):
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
        # View lifecycle
        for e in ('QueryCreate', 'QueryEditEnd', 'QueryDelete'):
            self.controller.event_handler.internal_rule (event=e,
                                                         method=self.query_lifecycle)
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

        self.controller.event_handler.internal_rule (event="ViewActivation",
                                                     method=self.on_view_activation)

        self.controller.init(args)

        if config.data.webserver['mode'] == 1:
            self.log(_("Using Mainloop input handling for webserver..."))
            gtk.input_add (self.controller.server,
                           gtk.gdk.INPUT_READ,
                           self.handle_http_request)
            if config.data.os == 'win32':
                # Win32 workaround for the reactivity problem
                def sleeper():
                    time.sleep(.001)
                    return True
                gtk.timeout_add(400, sleeper)

        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        gtk.timeout_add (100, self.update_display)
        print "Running GUI"
        gtk.main ()
        self.controller.notify ("ApplicationEnd")

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
        s=config.data.preferences['windowsize'].setdefault(name, (640,480))
        window.set_default_size (*s)
        window.connect ("size_allocate", self.resize_cb, name)
        return True
    
    def resize_cb (self, widget, allocation, name):
        """Memorize the new dimensions of the widget."""
        config.data.preferences['windowsize'][name] = (allocation.width,
                                                       allocation.height)
        #print "New size for %s: %s" %  (name, config.data.preferences['windowsize'][name])
        return False
    
    def set_current_type (self, t):
        """Set the current annotation type.

        t can be None.
        
        @param t: annotation type
        @type t: AnnotationType
        """
        self.current_type = t
        type_combo=self.gui.get_widget ("current_type_combo")
        store = self.gui.get_widget("current_type_combo").get_model()
        i=store.get_iter_first()
        while i is not None:
            if store.get_value(i, 1) == t:
                type_combo.set_active_iter(i)
                return True
            i=store.iter_next(i)
        print "Strange bug in set_current_type: %s" % str(t)
        return True
    
    def on_edit_current_stbv_clicked(self, button):
        combo=self.gui.get_widget("stbv_combo")
        i=combo.get_active_iter()
        stbv=combo.get_model().get_value(i, 1)
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

    def update_stbv_list (self):
        """Update the STBV list.
        """
        stbv_combo = self.gui.get_widget("stbv_combo")
        l=[ None ]
        l.extend(self.controller.get_stbv_list())
        st, i = advene.gui.util.generate_list_model(l,
                                                    controller=self.controller,
                                                    active_element=self.controller.current_stbv)
        stbv_combo.set_model(st)
        if i is None:
            i=st.get_iter_first()
        # To ensure that the display is updated
        stbv_combo.set_active(-1)
        stbv_combo.set_active_iter(i)
        stbv_combo.show_all()
        return True

    def update_type_list (self):
        """Update the annotation type list.
        """
        type_combo=self.gui.get_widget ("current_type_combo")
        if self.controller.package:
            l=list(self.controller.package.annotationTypes)
            l.sort(lambda a,b: cmp(a.title, b.title))
        else:
            l=[ None ]
        if self.current_type is None and l:
            self.current_type=l[0]
        st, i = advene.gui.util.generate_list_model(l,
                                                    controller=self.controller,
                                                    active_element=self.current_type)
        type_combo.set_model(st)
        if i is None:
            i=st.get_iter_first()
        # To ensure that the display is updated
        type_combo.set_active(-1)
        if i is not None:
            type_combo.set_active_iter(i)
        type_combo.show_all()
        return True

    def update_gui (self):
        """Update the GUI.

        This method should be called upon package loading, or when a
        new view or type is created, or when an existing one is
        modified, in order to reflect changes.
        """
        self.update_type_list()
        self.update_stbv_list()
        return

    def manage_package_save (self, context, parameters):
        """Event Handler executed after saving a package.

        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        self.log (_("Package %s saved. %d annotations.") % (self.controller.package.uri,
                                                            len(self.controller.package.annotations)))
        return True

    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.

        self.controller.package should be defined.

        @return: a boolean (~desactivation)
        """
        self.log (_("Package %s loaded. %d annotations.") % (self.controller.package.uri,
                                                             len(self.controller.package.annotations)))
        self.update_gui()

        self.update_window_title()
        for v in self.annotation_views:
            try:
                v.update_model(self.controller.package)
            except AttributeError:
                pass

        return True

    def update_window_title(self):
        # Update the main window title
        self.gui.get_widget ("win").set_title(" - ".join((_("Advene"),
                                                          self.controller.package.title or _("No title"))))
        
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
        buf.insert_at_cursor (mes)
        endmark = buf.create_mark ("end", buf.get_end_iter (), True)
        self.gui.logmessages.scroll_mark_onscreen (endmark)
        return

    def parse_parameter(self, context, parameters, name, default_value):
        if parameters.has_key(name):
            try:
                result=context.evaluateValue(parameters[name])
            except advene.model.tal.context.AdveneTalesException, e:
                try:
                    rulename=context.evaluateValue('rule')
                except advene.model.tal.context.AdveneTalesException:
                    rulename=_("Unknown rule")
                self.controller.log(_("Rule %s: Error in the evaluation of the parameter %s:" % (rulename, name)))
                self.controller.log(str(e)[:160])
                result=default_value
        else:
            result=default_value
        return result


    def action_message_log (self, context, parameters):
        """Event Handler for the message action.

        Essentialy a wrapper for the X{log} method.

        The parameters should have a 'message' key.
        """
        message=self.parse_parameter(context, parameters, 'message', _("No message..."))
        message=message.replace('\\n', '\n')
        self.log (message)
        return True

    def action_open_view (self, context, parameters):
        """Event Handler for the OpenView action.

        The parameters should have a 'guiview' key.
        """
        view=self.parse_parameter(context, parameters, 'guiview', None)
        if view is None:
            return True
        match={
            'timeline': self.on_timeline1_activate,
            'tree': self.on_view_annotations_activate,
            }
        if match.has_key(view):
            match[view]()
        else:
            self.log(_("Error: undefined GUI view %s") % view)
        return True

    def action_popup (self, context, parameters):
        message=self.parse_parameter(context, parameters, 'message', _("No message..."))
        message=message.replace('\\n', '\n')
        message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

        duration=self.parse_parameter(context, parameters, 'duration', None)
        if duration == "" or duration == 0:
            duration = None
        l = gtk.Label(message)
        self.singletonpopup.display(widget=l, timeout=duration)
        return True

    def action_popup_goto (self, context, parameters):
        def handle_response(button, position):
            self.controller.update_status("set", position)
            self.singletonpopup.undisplay()
            return True

        description=self.parse_parameter(context, parameters, 'description', _("Make a choice"))
        description=description.replace('\\n', '\n')
        description=textwrap.fill(description, config.data.preferences['gui']['popup-textwidth'])
        
        message=self.parse_parameter(context, parameters, 'message', _("Click to go to another position"))
        message=message.replace('\\n', '\n')
        message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

        position=self.parse_parameter(context, parameters, 'position', 0)
        duration=self.parse_parameter(context, parameters, 'duration', None)
        if duration == "" or duration == 0:
            duration = None
        b=gtk.Button(message)
        b.connect("clicked", handle_response, position)

        vbox=gtk.VBox()
        l=gtk.Label(description)
        vbox.pack_start(l, expand=False)
        vbox.pack_start(b, expand=False)
        vbox.show_all()
        
        self.singletonpopup.display(widget=vbox, timeout=duration)
        return True

    def generate_action_popup_goton(self, size):
        def generate (context, parameters):
            """Display a popup with 'size' choices."""
            def handle_response(button, position):
                self.controller.update_status("set", long(position))
                self.singletonpopup.undisplay()
                return True

            vbox=gtk.VBox()

            description=self.parse_parameter(context,
                                             parameters, 'description', _("Make a choice"))
            description=description.replace('\\n', '\n')
            description=textwrap.fill(description,
                                      config.data.preferences['gui']['popup-textwidth'])
            vbox.add(gtk.Label(description))

            for i in range(1, size+1):
                message=self.parse_parameter(context, parameters,
                                             'message%d' % i, _("Choice %d") % i)
                message=message.replace('\\n', '\n')
                message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

                position=self.parse_parameter(context, parameters, 'position%d' % i, 0)
                b=gtk.Button(message)
                b.connect("clicked", handle_response, position)
                vbox.add(b)

            duration=self.parse_parameter(context, parameters, 'duration', None)
            if duration == "" or duration == 0:
                duration = None
            self.singletonpopup.display(widget=vbox, timeout=duration)
            return True
        return generate

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
                                                'c': self.controller })
        w=ev.popup()
        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect("clicked", lambda b: w.destroy())
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
        try:
            pos=self.controller.update()
        except self.controller.player.InternalException:
            # FIXME: something sensible to do here ?
            print _("Internal error on video player")
            return True
        except Exception, e:
            # Catch-all exception, in order to keep the mainloop
            # runnning
            print _("Got exception %s. Trying to continue.") % str(e)
            import code
            e, v, tb = sys.exc_info()
            code.traceback.print_exception (e, v, tb)
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
                self.gui.player_status.set_text (self.statustext[self.controller.player.status])

            if (self.annotation is not None
                and self.annotation.content.data != self.gui.current_annotation.get_text()):
                self.gui.current_annotation.set_text (self.annotation.content.data)

            # Update the position mark in the registered views
            # Note: beware when implementing update_position in views:
            # it is a critical execution path
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
        # FIXME: handle create==True case
        at=None
        
        if text is None:
            text=_("Choose an annotation type.")

        ats=self.controller.package.annotationTypes
        if len(ats) == 1:
            at=ats[0]
        elif len(ats) > 1:
            at=advene.gui.util.list_selector(title=_("Choose an annotation type"),
                                             text=text,
                                             members=self.controller.package.annotationTypes,
                                             controller=self.controller)
        else:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                _("No annotation type is defined."))
            response=dialog.run()
            dialog.destroy()
            return None

        return at
        
        
    def on_current_type_combo_changed (self, combo=None):
        """Callback used to select the current type of the edited annotation.
        """
        i=combo.get_active_iter()
        if i is None:
            return False
        t=combo.get_model().get_value(i, 1)
        self.set_current_type(t)
        #print "Current type changed to " + str(t)
        return True

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
            
        if self.controller.on_exit():
            gtk.main_quit()
            return False
        else:
            return True

    # Callbacks function. Skeletons can be generated by glade2py

    def on_win_key_press_event (self, win=None, event=None):
        """Keypress handling."""
        # Control-shortcuts
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                # Quit
                return self.on_exit (win, None)
            elif event.keyval == gtk.keysyms.o:
                # Open an annotation file
                self.on_open1_activate (win, None)
            elif event.keyval == gtk.keysyms.e:
                # Popup the evaluator window
                self.popup_evaluator()
            elif event.keyval == gtk.keysyms.s:
                # Save the current annotation file
                self.on_save1_activate (win, None)
            elif event.keyval == gtk.keysyms.Return:
                # We do something special on C-return, so
                # go to the following test (Return)
                pass
            else:
                return False

        if event.keyval == gtk.keysyms.Return:
            # Non-pausing annotation mode
            c=self.controller
            c.position_update ()
            if self.annotation is None:
                # Start a new annotation
                if self.current_type is None:
                    # FIXME: should display a warning
                    return True
                f = MillisecondFragment (begin=c.player.current_position_value-config.data.reaction_time,
                                         duration=30000)
                self.annotation = c.package.createAnnotation(type = self.current_type,
                                                             fragment=f)
                self.log (_("Defining a new annotation..."))
                self.controller.notify ("AnnotationCreate", annotation=self.annotation)
            else:
                # End the annotation. Store it in the annotation list
                self.annotation.fragment.end = c.player.current_position_value-config.data.reaction_time
                f=self.annotation.fragment
                if f.end < f.begin:
                    f.begin, f.end = f.end, f.begin
                c.package.annotations.append (self.annotation)
                self.log (_("New annotation: %s") % self.annotation)
                self.gui.current_annotation.set_text ('['+_('None')+']')
                c.notify ("AnnotationEditEnd", annotation=self.annotation)
                self.annotation = None
                if event.state & gtk.gdk.CONTROL_MASK:
                    # Continuous editing mode: we immediately start a new annotation
                    if self.current_type is None:
                        return True
                    f = MillisecondFragment (begin=c.player.current_position_value-config.data.reaction_time,
                                             duration=30000)
                    self.annotation = c.package.createAnnotation(type = self.current_type,
                                                                 fragment=f)
                    self.log (_("Defining a new annotation..."))
                    self.controller.notify ("AnnotationCreate", annotation=self.annotation)
                if c.player.status == c.player.PauseStatus:
                    c.update_status ("resume")
            return True
        elif event.keyval == gtk.keysyms.space:
            # Pausing annotation mode
            if self.annotation is None:
                # Not defining any annotation yet. Pause the stream
                if self.controller.player.status != self.controller.player.PauseStatus:
                    self.controller.update_status ("pause")
                self.controller.position_update ()
                if self.current_type is None:
                    return True
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
            self.controller.move_position (config.data.player_preferences['time_increment'])
            return True
        elif event.keyval == gtk.keysyms.Left:
            self.controller.move_position (-config.data.player_preferences['time_increment'])
            return True
        elif event.keyval == gtk.keysyms.Home:
            self.controller.update_status ("set", self.controller.create_position (0))
            return True
        elif event.keyval == gtk.keysyms.End:
            c=self.controller
            pos = c.create_position (value = -config.data.player_preferences['time_increment'],
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
        if self.controller.modified:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                _("Your package has been modified but not saved.\nCreate a new one anyway?"))
            response=dialog.run()
            dialog.destroy()
            if response != gtk.RESPONSE_YES:
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
            self.controller.load_package (uri=filename)
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
            self.controller.save_package(as=filename)
	return True

    def on_import_dvd_chapters1_activate (self, button=None, data=None):
        # FIXME: loosy test
        if (self.controller.get_default_media() is None
            or 'dvd' in self.controller.get_default_media()):
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                _("Do you confirm the creation of annotations matching the DVD chapters?"))
            response=dialog.run()
            dialog.destroy()
            if response != gtk.RESPONSE_YES:
                return True
            i=advene.util.importer.get_importer('lsdvd')
            i.package=self.controller.package
            i.process_file('lsdvd')
            self.controller.modified=True
            self.controller.notify('PackageLoad')
        else:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                _("The associated media is not a DVD."))
            response=dialog.run()
            dialog.destroy()
            
        return True
        
    def on_import_file1_activate (self, button=None, data=None):
        filename=advene.gui.util.get_filename(title=_("Choose the file to import"),
                                              action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                              button=gtk.STOCK_OPEN)
        if not filename:
            return True
        i=advene.util.importer.get_importer(filename)
        if i is None:
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                _("The format of the file\n%s\nis not recognized.") % file_)
            response=dialog.run()
            dialog.destroy()
        else:
            # FIXME: build a dialog to enter optional parameters
            # FIXME: handle the multiple possibilities case (for XML esp.)
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
                _("Do you confirm the import of data from\n%s\nby the %s filter?") % (
                filename, i.name))
            response=dialog.run()
            dialog.destroy()
            if response != gtk.RESPONSE_YES:
                return True
            i.package=self.controller.package
            i.process_file(filename)
            self.controller.modified=True
            self.controller.notify("PackageLoad", package=i.package)
            self.log('Converted from file %s :' % filename)
            self.log(i.statistics_formatted())
        return True

    def on_import_transcription1_activate (self, button=None, data=None):
        te=advene.gui.edit.transcribe.TranscriptionEdit(controller=self.controller)
        window = te.popup()
        window.connect ("destroy", lambda w: w.destroy())
        return True

    def on_quit1_activate (self, button=None, data=None):
        """Gtk callback to quit."""
        return self.on_exit (button, data)

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
        duration = self.controller.cached_duration
        if duration <= 0:
            if self.controller.package.annotations:
                duration = max([a.fragment.end for a in self.controller.package.annotations])
            else:
                duration = 0

        t = advene.gui.views.timeline.TimeLine (self.controller.package.annotations,
                                                minimum=0,
                                                maximum=duration,
                                                controller=self.controller)
        window=t.popup()
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

    def on_view_logwindow_activate (self, button=None, data=None):
        """Open logwindow view plugin."""
        self.logwindow.popup()
        return True

    def on_view_annotations_activate (self, button=None, data=None):
        """Open treeview view plugin."""
        tree = advene.gui.views.tree.TreeWidget(self.controller.package,
                                                controller=self.controller)
        tree.popup()
        return True

    def on_transcription1_activate (self, button=None, data=None):
        """Open transcription view."""
        at=self.ask_for_annotation_type(text=_("Choose the annotation type to display as transcription."), create=False)
        if at is not None:
            transcription = TranscriptionView(controller=self.controller,
                                              annotationtype=at)
            transcription.popup()
        return True
    
    def on_browser1_activate (self, button=None, data=None):
        browser = advene.gui.views.browser.Browser(element=self.controller.package,
                                                   controller=self.controller)
        popup=browser.popup()
        return True

    def on_evaluator2_activate (self, button=None, data=None):
        self.popup_evaluator()
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
        filename=advene.gui.util.get_filename(title=_("Select a movie file"),
                                              action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                              button=gtk.STOCK_OPEN)
        if filename:
            self.controller.set_default_media(filename)
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
            sel.get_widget().destroy()
            self.controller.set_default_media(url)
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
        return self.on_exit (button, data)

    def on_package_imports1_activate (self, button=None, data=None):
        """Edit imported elements from other packages."""
        imp=advene.gui.edit.imports.Importer(controller=self.controller)
        imp.popup()
        return True

    def on_package_properties1_activate (self, button=None, data=None):
        self.gui.get_widget ("prop_author_id").set_text (self.controller.package.author)
        self.gui.get_widget ("prop_date").set_text (self.controller.package.date)
        self.gui.get_widget ("prop_media").set_text (self.controller.get_default_media() or "")
        self.gui.get_widget ("prop_title").set_text (self.controller.package.title or "")

        self.gui.get_widget ("properties").show ()
        return True

    def on_preferences1_activate (self, button=None, data=None):
        self.gui.get_widget ("osdtext_toggle").set_active (config.data.player_preferences['osdtext'])
        self.gui.get_widget ("preferences").show ()
        return True

    def on_preferences_ok_clicked (self, button=None, data=None):
        config.data.player_preferences['osdtext'] = self.gui.get_widget ("osdtext_toggle").get_active ()
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
        self.controller.set_default_media(mediafile)
        #id_ = vlclib.mediafile2id (mediafile)
        #self.controller.imagecache.save (id_)

        self.controller.package.title = self.gui.get_widget ("prop_title").get_text ()
        self.update_window_title()
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
        self.controller.restart_player ()
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
        p = self.controller.create_position (value = long(self.gui.slider.get_value ()))
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

    def on_help1_activate (self, button=None, data=None):
        # FIXME: display user help.
        help=os.sep.join( (config.data.path['web'], 'user.html') )
        if os.access(help, os.R_OK):
            self.webbrowser.open (help)
        # FIXME: display a warning if not found
        return True

    def on_toolbar_style1_activate (self, button=None, data=None):
        st={ _('Icons only'): gtk.TOOLBAR_ICONS,
             _('Text only'): gtk.TOOLBAR_TEXT,
             _('Both'): gtk.TOOLBAR_BOTH }

        style=self.gui.get_widget("toolbar_control").get_style()
        preselect=None
        for k, v in st.iteritems():
            if style == v:
                preselect=k
                break
                
        s=advene.gui.util.list_selector(title=_("Choose the toolbar style."),
                                        text=_("Choose the toolbar style."),
                                        members=st,
                                        controller=self.controller,
                                        preselect=preselect)
        if s is not None:
            for t in ("toolbar_control", "toolbar_view", "toolbar_fileop"):
                self.gui.get_widget(t).set_style(st[s])
        return True

    def on_about_web_button_clicked(self, button=None, data=None):
        self.webbrowser.open('http://liris.cnrs.fr/advene/')
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
