#!/usr/bin/env python

"""Advene controller.

The L{AdveneEventHandler} is used by the application to handle events
notifications and actions triggering.
"""

import sys, time
import os
import socket

import advene.core.config as config

from gettext import gettext as _

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

if config.data.webserver['mode']:
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
      - L{update} : regularly called method used to update information about the current stream
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

    @ivar modified: indicates if the data has been modified
    @type modified: boolean
    
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
        self.cached_duration = 0

        # STBV
        self.current_stbv = None
        
        self.package = None
        self.modified = False
        
        self.preferences = config.data.preferences

        playerfactory=advene.core.mediacontrol.PlayerFactory()
        self.player = playerfactory.get_player()
        self.player.get_default_media = self.get_default_media
        self.player_restarted = 0
        # FIXME: should be removed (CORBA dependent)
        try:
            os.unlink(config.data.iorfile)
        except OSError:
            pass
        
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
        self.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name="Message",
            method=self.message_log,
            description=_("Display a message"),
            parameters={'message': _("String to display.")}
            ))

    def busy_port_info(self):
        """Display the processes using the webserver port.
        """
        processes=[]
        pat=':%d' % config.data.webserver['port']
        f=os.popen('netstat -atlnp 2> /dev/null', 'r')
        for l in f.readlines():
            if pat not in l:
                continue
            pid=l.rstrip().split()[-1]
            processes.append(pid)
        f.close()
        # FIXME: make that a popup window
        print "+-------------------------------------------------------"
        print "|The following processes seem to use the %s port:" % pat
        print "| %s |" % processes
        print "+-------------------------------------------------------"        
    
    def init(self, args=None):
        """Mainloop : CORBA initalization
        """
        if args is None:
            args=[]

        # Read the default rules
        self.event_handler.read_ruleset_from_file(config.data.advenefile('default_rules.xml'),
                                                  type_='default')

        self.event_handler.internal_rule (event="PackageLoad",
                                          method=self.manage_package_load)
        
        if config.data.webserver['mode']:
            try:
                self.server = advene.core.webserver.AdveneWebServer(controller=self,
                                                                    port=config.data.webserver['port'])
            except socket.error:
                print _("Cannot start the webserver.\nAnother application is using the port.\nCheck that no VLC player is still running in the background.")
                if config.data.os != 'win32':
                    self.busy_port_info()
                sys.exit(0)
            
            # If == 1, it is the responbility of the Gtk app to set the input loop
            if config.data.webserver['mode'] == 2:
                self.serverthread = threading.Thread (target=self.server.serve_forawhile)
                self.serverthread.start ()

        # FIXME: check the return value (media file to play) or better,
        # rewrite parse_command_line
        file_to_play=self.parse_command_line (args)

        # If no package is defined yet, load the template
        if self.package is None:
            self.load_package ()

        if file_to_play:
            self.set_default_media(file_to_play)

        self.player.check_player()
        
        return True
    
    def create_position (self, value=0, key=None, origin=None):
        return self.player.create_position(value=value, key=key, origin=origin)
    
    def notify (self, event_name, *param, **kw):
        return self.event_handler.notify(event_name, *param, **kw)

    def update_snapshot (self, position):
        """Event handler used to take a snapshot for the given position (current).

        @return: a boolean (~desactivation)
        """
        if not self.imagecache.is_initialized (position):
            # FIXME: only 0-relative position for the moment
            print "Update snapshot for %d" % position
            try:
                i = self.player.snapshot (self.player.relative_position)
            except self.player.InternalException, e:
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
                elif os.path.splitext(s)[1] in ('.xml', '.advene', '.adv'):
                    # It should be an annotation file. Load it.
                    self.load_package (uri=s)
                else:
                    file_to_play = s
        return file_to_play

    def get_default_media (self):
        mediafile = self.package.getMetaData (config.data.namespace,
                                              "mediafile")
        return mediafile

    def set_default_media (self, uri):
        if isinstance(uri, unicode):
            uri=uri.encode('utf8')
        self.package.setMetaData (config.data.namespace, "mediafile", uri)
        self.player.playlist_clear()
        self.player.playlist_add_item (uri)

    def restart_player (self):
        """Restart the media player."""
        self.player.restart_player ()
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            if isinstance(mediafile, unicode):
                mediafile=mediafile.encode('utf8')
            self.player.playlist_add_item (mediafile)

    def start_update_snapshots(self, progress_callback=None, stop_callback=None):
        """Automatic snapshot update.

        The progress_callback method will be called with.
        """
        if not config.data.player['snapshot']:
            self.log (_("Error: the player is not run with the snapshot functionality. Configure it and try again."))
            return True
        
        def take_snapshot(context, parameters):
            if not config.data.player['snapshot']:
                return False
            print "Take snapshot %d" % self.player.current_position_value
            self.update_snapshot(position=self.player.current_position_value)
            return True

        # We define goto_next_snapshot local to start_update_snapshots, so
        # that we have access to progress_callback
        def goto_next_snapshot (context, parameters):
            """Event handler called after having made a snapshot.

            It will go just before the next position for which we need to
            take a snapshot.
            """
            missing = self.imagecache.missing_snapshots ()
            missing.sort ()

            if progress_callback:
                progress_callback(1 - (len(missing) + .0) / len(self.imagecache))

            if not missing:
                # No more missing snapshots : we can stop
                self.log(_("All snapshots are up-to-date."))
                self.stop_update_snapshots()
                # Return False to desactivate the callback
                return False

            if self.player.status != self.player.PlayingStatus:
                # End of stream
                self.log(_("End of stream (%s). Quitting")
                         % repr(self.player.status))
                self.stop_update_snapshots()
                return False

            # offset is the offset to next point : missing position minus
            # current position
            next = missing[0]
            print "%d / %s" % (self.player.current_position_value, str(missing))
            if (next - self.player.current_position_value > 2000
                or next < self.player.current_position_value):
                # We move only if the next position if further than 2 seconds,
                # or negative
                pos = next - 2000
                if pos < 0:
                    pos = 0
                print "Set position %d" % pos
                self.move_position(pos, relative=False)
            return True

        self.oldstate = self.event_handler.get_state ()
        self.event_handler.clear_state ()
        self.event_handler.internal_rule (event="AnnotationBegin", method=take_snapshot)
        self.event_handler.internal_rule (event="AnnotationEnd", method=take_snapshot)
        self.event_handler.internal_rule (event="AnnotationEnd", method=goto_next_snapshot)
        if stop_callback:
            self.event_handler.internal_rule(event="PlayerStop", method=stop_callback)
                                             
        # Populate the imagecache keys
        for a in self.package.annotations:
            self.imagecache.init_value (a.fragment.begin)
            self.imagecache.init_value (a.fragment.end)

        if progress_callback:
            missing = self.imagecache.missing_snapshots ()
            progress_callback(1 - (len(missing) + .0) / len(self.imagecache))
            
        # Start the player (without event notification)
        self.player.update_status ("start")

        # FIXME: we should wait for the PlayingStatus instead
        time.sleep (2)
        self.position_update()
        # Goto the first unavailable annotation
        goto_next_snapshot (None, None)
        
        return True
    
    def stop_update_snapshots(self):
        if hasattr (self, 'oldstate'):
            #self.gui.get_widget ("update-snapshots-stop").set_sensitive (False)
            #self.gui.get_widget ("update-snapshots-execute").set_sensitive (True)
            self.update_status ("stop")
            self.event_handler.set_state (self.oldstate)
            del (self.oldstate)
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
        # Check if we know the stream duration. If so, save it as
        # package metadata
        if self.cached_duration > 0:
            self.package.setMetaData (config.data.namespace,
                                      "duration",
                                      unicode(self.cached_duration))
        # Set if necessary the mediafile metadata
        if self.get_default_media() is None:
            pl = self.player.playlist_get_list()
            if pl:
                self.package.set_default_media(pl[0])
        self.package.save(as=as)
        self.modified=False
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

        self.modified=False
        # Get the cached duration
        duration = self.package.getMetaData (config.data.namespace, "duration")
        if duration is not None:
            self.cached_duration = long(duration)
        else:
            self.cached_duration = 0
            
        mediafile = self.get_default_media()
        if mediafile is not None and mediafile != "":
            if self.player.is_active():
                if mediafile not in self.player.playlist_get_list ():
                    # Update the player playlist
                    if isinstance(mediafile, unicode):
                        mediafile=mediafile.encode('utf8')
                    self.player.playlist_add_item (mediafile)
                     
            # Load the imagecache
            id_ = vlclib.mediafile2id (mediafile)
            self.imagecache.clear ()
            self.imagecache.load (id_)
            # Populate the missing keys
            for a in self.package.annotations:
                self.imagecache.init_value (a.fragment.begin)
                self.imagecache.init_value (a.fragment.end)
                
        # Update the webserver
        if config.data.webserver['mode']:
            self.server.register_package (alias='advene',
                                          package=self.package,
                                          imagecache=self.imagecache)
        return True

    def get_stbv_list(self):
        if self.package:
            return [ v
                     for v in self.package.views
                     if v.content.mimetype == 'application/x-advene-ruleset' ]
        else:
            return []

    def activate_stbv(self, view=None):
        """Activates a given STBV.

        If view is None, then reset the user STBV.
        """
        self.current_stbv=view
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

        This method is used if config.data.webserver['mode'] == 1.  
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
        
        return True

    def move_position (self, value, relative=True):
        """Helper method : fast forward or rewind by value milliseconds.

        @param value: the offset in milliseconds
        @type value: int
        """
        if relative:
            self.update_status ("set", self.create_position (value=value,
                                                             key=self.player.MediaTime,
                                                             origin=self.player.RelativePosition))
        else:
            self.update_status ("set", self.create_position (value=value,
                                                             key=self.player.MediaTime,
                                                             origin=self.player.AbsolutePosition))

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
        @type position: Position
        """
        position_before=self.player.current_position_value
        try:
            if hasattr(position, 'value'):
                print "update_status %s %i" % (status, position.value)
            else:
                print "update_status %s %s" % (status, position)
            self.player.update_status (status, position)
        except Exception, e:
            # FIXME: we should catch more specific exceptions and
            # devise a better feedback than a simple print
            print _("Raised exception in update_status: %s") % str(e)
            import code
            e, v, tb = sys.exc_info()
            code.traceback.print_exception (e, v, tb)
        else:
            if self.status2eventname.has_key (status):
                self.event_handler.notify (self.status2eventname[status],
                                           position=position,
                                           position_before=position_before)
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
        except self.player.InternalException:
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

        # Update the cached duration if necessary
        if self.cached_duration <= 0 and self.player.stream_duration > 0:
            print "updating cached duration"
            self.cached_duration = self.player.stream_duration

        return pos

    def delete_annotation(self, annotation):
        """Remove the annotation from the package."""
        self.package.annotations.remove(annotation)
        self.notify('AnnotationDelete', annotation=annotation)
        return True
    
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
