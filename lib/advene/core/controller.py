#!/usr/bin/env python

"""Advene controller.

The L{AdveneEventHandler} is used by the application to handle events
notifications and actions triggering.
"""

import sys, time

import advene.core.config as config

from gettext import gettext as _

# For CORBA
import ORBit, CORBA
ORBit.load_typelib (config.data.typelib)
import VLC

import advene.rules.elements
import advene.rules.ecaengine

from advene.model.package import Package 
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment
import advene.model.constants
import advene.model.tal.context

import advene.core.mediacontrol

from advene.core.imagecache import ImageCache

import advene.util.vlclib as vlclib

if config.data.launch_http_server:
    import advene.core.webserver
import threading

class AdveneController:
    """AdveneController class.

    The main attributes for this class are:
      - L{package} : the currently loaded package
      - L{imagecache} : the associated imagecache
      - L{active_annotations} : the currently active annotations
      - L{player} : the player (X{advene.core.mediacontrol.Player} instance)
      - L{event_handler} : the event handler
      - L{server} : the embedded web server

    Some entry points in the methods:
      - L{__init__} : controller initialization
      - L{update_status} : use this method to interact with the player
      
    @ivar imagecache: the current imagecache
    @type imagecache: imagecache.ImageCache

    @ivar active_annotations: the currently active annotations.
    @type active_annotations: list
    @ivar future_begins: the annotations that should be activated next (sorted)
    @type future_begins: list
    @ivar future_ends: the annotations that should be desactivated next (sorted)
    @type future_ends: list

    @ivar last_position: a cache to check whether an update is necessary
    @type last_position: int
    
    @ivar package: the package currently loaded
    @type package: advene.model.Package

    @ivar preferences: the current preferences
    @type preferences: dict

    @ivar player: a reference to the player
    @type player: advene.core.mediacontrol.Player

    @ivar event_handler: the event handler instance
    @type event_handler: AdveneEventHandler

    @ivar server: the embedded web server
    @type server: webserver.AdveneWebServer

    """
    
    def __init__ (self):
        """Initializes CORBA and other attributes.
        """
        # Image Cache
        self.imagecache = ImageCache ()
        
        # List of active annotations
        self.active_annotations = []
        self.future_begins = None
        self.future_ends = None
        self.last_position = -1
        
        self.package = None

        self.preferences = config.data.preferences
        
        self.player = advene.core.mediacontrol.Player ()
        self.player.get_default_media = self.get_default_media
        self.player_restarted = 0
        
        # Event handler initialization
        self.event_handler = advene.rules.ecaengine.ECAEngine (controller=self)
        # Used in update_status to emit appropriate notifications
        self.status2eventname = {
            'pause':  'PlayerPause',
            'resume': 'PlayerResume',
            'start':  'PlayerStart',
            'stop':   'PlayerStop',
            'set':    'PlayerSet',
            }

    def init(self, args=None):
        """Mainloop : CORBA initalization
        """
        if args is None:
            args=[]
        self.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="Message",
            method=self.message_log,
            description=_("Display a message"),
            parameters={'message': _("String to display.")}
            ))

        # Read the default rules
        self.event_handler.read_ruleset_from_file(config.data.advenefile('default_rules.xml'),
                                                  type_='default')

        self.event_handler.internal_rule (event="PackageLoad",
                                          method=self.manage_package_load)
        
        if config.data.launch_http_server:
            self.server = advene.core.webserver.AdveneWebServer(player=self.player,
                                                                master=self)
            # If == 1, it is the responbility of the Gtk app to set the input loop
            if config.data.launch_http_server == 2:
                self.serverthread = threading.Thread (target=self.server.serve_forawhile)
                self.serverthread.start ()

        # FIXME: check the return value (media file to play)
        self.parse_command_line (args)

        # If no package is defined yet, load the template
        if self.package is None:
            self.load_package ()
        return True
    
    def create_position (self, value=0, key=VLC.MediaTime,
                         origin=VLC.AbsolutePosition):
        """Create a VLC Position.
        
        Returns a VLC.Position object initialized to the right value, by
        default using a MediaTime in AbsolutePosition.

        @param value: the value
        @type value: int
        @param key: the Position key
        @type key: VLC.Key
        @param origin: the Position origin
        @type origin: VLC.Origin
        @return: a position
        @rtype: VLC.Position
        """
        p = VLC.Position ()
        p.origin = origin
        p.key = key
        p.value = value
        return p

    def update_snapshot (self, position):
        """Event handler used to take a snapshot for the given position (current).

        @return: a boolean (~desactivation)
        """
        if not self.imagecache.is_initialized (position):
            # FIXME: only 0-relative position for the moment
            try:
                i = self.player.snapshot (self.player.relative_position)
            except VLC.InternalException, e:
                print "Exception in snapshot: %s" % e.message
                return False
            if i.height != 0:
                self.imagecache[position] = vlclib.snapshot2png (i)
        else:
            # FIXME: do something useful (warning) ?                
            pass
        return True    
        
    def parse_command_line (self, args):
        """Parse command line options.

        We recognize the .mpg and .avi extension, as well as the dvd
        keyword, to specify the media file.

        An .xml file is considered as an annotation package.

        @param args: the argument list
        @type args: list
        @return: the file to add add to playlist if one was specified
        @rtype: string
        """
        file_to_play = None
        for s in args:
            if s.startswith ('-'):
                print _("Unknown option: %s") % s
            else:
                if s == "dvd":
                    file_to_play = "dvd:///dev/dvd"
                elif s.endswith('.xml'):
                    # It should be an annotation file. Load it.
                    self.load_package (uri=s)
                elif s.endswith('.mpg') or s.endswith('.avi'):
                    file_to_play = s
        return file_to_play

    def get_default_media (self):
        mediafile = self.package.getMetaData (config.data.namespace,
                                              "mediafile")
        return mediafile

    def restart_player (self):
        """Restart the media player."""
        self.player.restart_player ()
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            self.player.playlist_add_item (mediafile)

    def goto_next_snapshot (self, annotation=None, **kw):
        """Event handler called after having made a snapshot.

        It will go just before the next position for which we need to
        take a snapshot.
        """
        # FIXME: this is completely out of date wrt. ECA framework
        missing = self.imagecache.missing_snapshots ()
        missing.sort ()
        #print "Goto next snapshot : %s" % missing
        bar = self.gui.get_widget ("snapshots-progressbar")
        bar.set_fraction (1 - (len(missing) + .0) / len(self.imagecache))
        if not missing:
            # No more missing snapshots : we can stop
            self.log(_("All snapshots are up-to-date."))
            self.on_update_snapshots_stop_clicked()
            # Return False to desactivate the callback
            return False
        
        if self.player.status != VLC.PlayingStatus:
            # End of stream
            self.log(_("End of stream (%s). Quitting")
                     % repr(self.player.status))
            self.on_update_snapshots_stop_clicked()
            return False

        # offset is the offset to next point : missing position minus
        # current position
        next = missing[0]
        #print "Next Offset: %d" % (next - self.player.current_position_value)
        if (next - self.player.current_position_value > 1000
            or next < self.player.current_position_value):
            # We move only if the next position if further than 1 second,
            # or negative
            pos = next - 1000
            if pos < 0:
                pos = 0
            #print "Set position %d" % pos
            self.player.update_status ("set", self.create_position (pos))
        return True

    def load_package (self, uri=None, alias="advene"):
        """Load a package.

        This method is esp. used as a callback for webserver. If called
        with no argument, or an empty string, it will create a new
        empty package.

        @param uri: the URI of the package
        @type uri: string
        @param alias: the name of the package (ignored in the GUI, always "advene")
        @type alias: string
        """
        if uri is None or uri == "":
            self.package = Package (uri="new_pkg",
                                    source=config.data.advenefile(config.data.templatefilename))
            self.package.author = config.data.userid
        else:
            self.package = Package (uri=uri)
        self.event_handler.notify ("PackageLoad")
    
    def save_package (self, as=None):
        """Save a package.

        @param as: the URI of the package
        @type uri: string
        """
        if as is None:
            as=self.package.uri
        self.package.save(as=as)
        self.event_handler.notify ("PackageSave")
    
    def manage_package_load (self, context, parameters):
        """Event Handler executed after loading a package.
        
        self.package should be defined.

        @return: a boolean (~desactivation)
        """

        # Check that all fragments are Millisecond fragments.
        l = [a.id for a in self.package.annotations
             if not isinstance (a.fragment, MillisecondFragment)]
        if l:
            self.package = None
            self.log (_("Cannot load package: the following annotations do not have Millisecond fragments:"))
            self.log (", ".join(l))
            return True
            
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            if self.player.is_active():
                if mediafile not in self.player.playlist_get_list ():
                    # Update the player playlist
                    self.player.playlist_add_item (mediafile)
                    
            # Load the imagecache
            id = vlclib.mediafile2id (mediafile)
            self.imagecache.clear ()
            self.imagecache.load (id)
            # Populate the missing keys
            for a in self.package.annotations:
                self.imagecache.init_value (a.fragment.begin)
                self.imagecache.init_value (a.fragment.end)
                
        # Update the webserver
        if config.data.launch_http_server:
            self.server.register_package (alias='advene',
                                          package=self.package,
                                          imagecache=self.imagecache)
        return True

    def get_stbv_list(self):
        return [ v
                 for v in self.package.views
                 if v.content.mimetype == 'application/x-advene-ruleset' ]

    def activate_stbv(self, view=None):
        """Activates a given STBV.

        If view is None, then reset the user STBV.
        """
        if view is None:
            self.event_handler.clear_ruleset(type_='user')
            return
        rs=advene.rules.elements.RuleSet()
        rs.from_dom(catalog=self.event_handler.catalog,
                    domelement=view.content.model,
                    origin=view.uri)
        self.event_handler.set_ruleset(rs, type_='user')
        self.event_handler.notify("ViewActivation", view=view)
        return
        
    def handle_http_request (self, source, condition):
        """Handle a HTTP request.

        This method is used if config.data.launch_http_server == 1.  
        """
        source.handle_request ()
        return True
        
    def log (self, msg):
        """Add a new log message.

        Should be overriden by the application (GUI for instance)

        @param msg: the message
        @type msg: string
        """
        print msg
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

    def on_exit (self, source=None, event=None):
        """General exit callback."""
        # Terminate the web server
        try:
            self.server.stop_serving ()
        except:
            pass
        
        # Terminate the VLC server
        try:
            self.player.exit()
        except:
            pass

    def move_position (self, value, relative=True):
        """Helper method : fast forward or rewind by value milliseconds.

        @param value: the offset in milliseconds
        @type value: int
        """
        if relative:
            self.update_status ("set", self.create_position (value=value,
                                                             key=VLC.MediaTime,
                                                             origin=VLC.RelativePosition))
        else:
            self.update_status ("set", self.create_position (value=value,
                                                             key=VLC.MediaTime,
                                                             origin=VLC.AbsolutePosition))

    def update_corba (self, orb):
        """Manage CORBA calls (in corba-server mode)."""
        if self.orb.work_pending ():
            self.orb.perform_work ()
        return True

    def generate_sorted_lists (self, position):        
        """Return two sorted lists valid for a given position.
        
        (i.e. all annotations beginning or ending after the
        position). The lists are sorted according to the begin and end
        position respectively.

        The elements of the list are (annotation, begin, end).
        
        The update_display method only has to check the first element
        of each list. If there is a match, it should trigger the
        events and pop the element.

        If there is a seek operation, we should regenerate the lists.

        @param position: the current position
        @type position: int
        @return: a tuple of two lists containing triplets
        @rtype: tuple
        """
        l = [ (a, a.fragment.begin, a.fragment.end)
              for a in self.package.annotations
              if a.fragment.begin >= position or a.fragment.end >= position ]
        future_begins = list(l)
        future_ends = l
        future_begins.sort(lambda a, b: cmp(a[1], b[1]))
        future_ends.sort(lambda a, b: cmp(a[2], b[2]))

        #print "Begins: %s\nEnds: %s" % (future_begins, future_ends)
        return future_begins, future_ends

    def reset_annotation_lists (self):
        """Reset the future annotations lists."""
        self.future_begins = None
        self.future_ends = None
        self.active_annotations = []

    def update_status (self, status=None, position=None):
        """Update the player status.

        Wrapper for the player.update_status method, used to notify the
        AdveneEventHandler.

        @param status: the status (cf advene.core.mediacontrol.Player)
        @type status: string
        @param position: an optional position
        @type position: VLC.Position
        """
        self.player.update_status (status, position)
        if self.status2eventname.has_key (status):
            self.event_handler.notify (self.status2eventname[status], position=position)
        return
    
    def position_update (self):
        """Updates the current_position_value.

        This method, regularly called, restarts the player in case of
        a communication failure.

        It updates the slider range if necessary.

        @return: the current position in ms
        @rtype: a long
        """
        try:
            self.player.position_update ()
        except CORBA.COMM_FAILURE:
            # The server is down. Restart it.
            print _("Restarting player...")
            self.player_restarted += 1
            if self.player_restarted > 5:
                raise Exception (_("Unable to start the player."))
            self.restart_player ()

        return self.player.current_position_value

    def update (self):
        """Update the information.

        This method is regularly called by the upper application (for
        instance a Gtk mainloop).

        Hence, it is a critical execution path and care should be
        taken with the code used here.
        """
        pos=self.position_update ()
        #print "--------------------- %d / %d" % (pos, self.player.stream_duration)
        if pos < self.last_position:
            # We did a seek compared to the last time, so we 
            # invalidate the future_begins and future_ends lists
            # as well as the active_annotations
            self.future_begins = None
            self.future_ends = None
            self.active_annotations = []

        self.last_position = pos
        
        if self.future_begins is None or self.future_ends is None:
            self.future_begins, self.future_ends = self.generate_sorted_lists (pos)

        if self.future_begins:
            a, b, e = self.future_begins[0]
            while b <= pos:
                # Ignore if we were after the annotation end
                if e > pos:
                    self.event_handler.notify ("AnnotationBegin",
                                               annotation=a)                            
                    self.active_annotations.append(a)
                self.future_begins.pop(0)
                if self.future_begins:
                    a, b, e = self.future_begins[0]
                else:
                    break
                    
        if self.future_ends:
            a, b, e = self.future_ends[0]
            while e <= pos:
                #print "Comparing %d < %d for %s" % (e, pos, a.content.data)
                try:
                    self.active_annotations.remove(a)
                except ValueError:
                    pass
                self.event_handler.notify ("AnnotationEnd",
                                           annotation=a)
                self.future_ends.pop(0)
                if self.future_ends:
                    a, b, e = self.future_ends[0]
                else:
                    break
                
        return pos
    
if __name__ == '__main__':
    c = AdveneController()
    try:
        c.main ()
    except Exception, e:
        print _("Got exception %s. Stopping services...") % str(e)
        c.on_exit ()
        print _("*** Exception ***")
        import code
        e, v, tb = sys.exc_info()
        code.traceback.print_exception (e, v, tb)
