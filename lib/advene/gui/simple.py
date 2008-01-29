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
"""Advene simple GUI.

Simplified Advene GUI.
"""

from advene.gui.main import AdveneGUI

import time
import os

import advene.core.config as config
from advene.gui.views.viewbook import ViewBook

import gtk
import gtk.glade
import gobject

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

import advene.model.constants
import advene.model.tal.context

import advene.core.mediacontrol
import advene.util.helper as helper

import advene.util.importer

# GUI elements
from advene.gui.util import get_small_stock_button
import advene.gui.plugins.actions
import advene.gui.plugins.contenthandlers
import advene.gui.views.tree
import advene.gui.views.timeline
import advene.gui.views.table
import advene.gui.views.logwindow
import advene.gui.views.interactivequery
import advene.gui.views.finder
import advene.gui.edit.imports
import advene.gui.edit.properties
import advene.gui.edit.montage
import advene.gui.views.annotationdisplay

class SimpleAdveneGUI(AdveneGUI):
    def __init__ (self):
        """Initializes the simple GUI and other attributes.
        """
        self.controller = advene.core.controller.AdveneController()
        self.controller.register_gui(self)

        gladefile=config.data.advenefile ('simple.glade')
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
                 'here/annotationTypes/%s/annotations' % at.id) for at in self.controller.package.annotationTypes ] + [ (_("Views"), 'here/views'), (_("Tags"), 'tags') ]
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
        # Internal rule used for annotation loop
        self.annotation_loop_rule=None

        # Dictionary of registered adhoc views
        self.registered_adhoc_views={}

        # List of active annotation views (timeline, tree, ...)
        self.adhoc_views = []
        # List of active element edit popups
        self.edit_popups = []
        
        self.edit_accumulator = None

        # Populate default STBV and type lists
        self.update_gui()

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

        try:
            self.gui_plugins=self.controller.load_plugins(os.path.join(
                    os.path.dirname(advene.__file__), 'gui', 'plugins'),
                                                          prefix="advene_gui_plugins")
        except OSError:
            pass
        
        # Register default GUI elements (actions, content_handlers, etc)
        for m in (advene.gui.views.timeline,
                  advene.gui.views.browser,
                  advene.gui.views.finder,
                  advene.gui.views.interactivequery,
                  advene.gui.views.table,
                  advene.gui.views.bookmarks,
                  advene.gui.views.tree,
                  advene.gui.edit.montage,
                  advene.gui.views.annotationdisplay,
                  ):
            m.register(self.controller)

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
            
        # Open default views
        self.open_adhoc_view('timeline', destination='south')
        # FIXME: transcribe cannot be included if no package is loaded. Fix this.
        #self.open_adhoc_view('transcribe', destination='east')

        # Use small toolbar button everywhere
        gtk.settings_get_default().set_property('gtk_toolbar_icon_size', gtk.ICON_SIZE_SMALL_TOOLBAR)

        # Everything is ready. We can notify the ApplicationStart
        self.controller.notify ("ApplicationStart")
        self.event_source_update_display=gobject.timeout_add (100, self.update_display)
        self.event_source_slow_update_display=gobject.timeout_add (1000, self.slow_update_display)
        gtk.main ()
        self.controller.notify ("ApplicationEnd")

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
        self.gui.slider.set_draw_value(False)
        self.gui.slider.connect ("button-press-event", self.on_slider_button_press_event)
        self.gui.slider.connect ("button-release-event", self.on_slider_button_release_event)

        # Stack the video components
        v=gtk.VBox()
        v.pack_start(self.drawable, expand=True)
        self.captionview=None

        h=gtk.HBox()
        self.time_label=gtk.Label()
        self.time_label.set_text(helper.format_time(None))
        h.pack_start(self.time_label, expand=False)
        h.pack_start(self.gui.slider, expand=True)
        v.pack_start(h, expand=False)

        v.pack_start(self.player_toolbar, expand=False)

        # create the viewbooks
        for pos in ('east', 'south'):
            self.viewbook[pos]=ViewBook(controller=self.controller, location=pos)
        self.viewbook['fareast']=self.viewbook['east']
        self.viewbook['west']=self.viewbook['east']

        self.pane['east']=gtk.HPaned()
        self.pane['south']=gtk.VPaned()
        self.pane['main']=self.gui.get_widget('vpaned')

        # pack all together
        self.pane['east'].pack1(v, shrink=False)
        self.pane['east'].add2(self.viewbook['east'].widget)

        self.pane['south'].add1(self.pane['east'])
        self.pane['south'].add2(self.viewbook['south'].widget)

        # Open default views:
        self.pane['south'].show_all()

        return self.pane['south']
    
    def update_package_list (self):
        pass

    def append_file_history_menu(self, filename):
        pass

    def updated_position_cb (self, context, parameters):
        """Method called upon video player position change.
        """
        position_before=context.evaluateValue('position_before')
        # Notify views that the position has been reset.
        for v in self.adhoc_views:
            try:
                v.position_reset ()
            except AttributeError:
                pass
        return True

