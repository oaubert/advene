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
"""Advene http server.

This module defines a number of classes that describe the structure of
the Advene webserver. The L{AdveneWebServer} class is the main server
class.

URL syntax
==========

  The URL syntax is described in each decription class.

  The server can run standalone or embedded in another application
  (typically the C{advene} GUI).  In all cases, Webserver depends on
  AdveneController.
"""

import advene.core.config as config
import advene.core.version

import sys
import os
import re
import urllib
import cgi
import socket
import imghdr

from gettext import gettext as _

import cherrypy

if int(cherrypy.__version__.split('.')[0]) < 3:
    raise _("The webserver requires version 3.0 of CherryPy at least.")

from advene.model.fragment import MillisecondFragment
from advene.model.annotation import Annotation, Relation
from advene.model.view import View
from advene.model.resources import Resources

from advene.model.exception import AdveneException

import simpletal.simpleTAL
import simpletal.simpleTALES as simpleTALES

import advene.util.helper as helper

DEBUG=True
class Common:
    """Common functionalities for all cherrypy nodes.
    """
    def __init__(self, controller=None):
        self.controller=controller

    def _cpOnError(self):
        """Error message handling.
        """
        err = sys.exc_info()
        if DEBUG:
            print "Error handling"
            import traceback, StringIO
            bodyFile = StringIO.StringIO()
            traceback.print_exc(file = bodyFile)
            cherrypy.response.status=500
            cherrypy.response.headers['Content-type']='text/html'
            cherrypy.response.body = ["""<html><head><title>Advene - Error</title></head><body>Sorry, an error occured. <pre>%s</pre></body></html>""" % bodyFile.getvalue() ]
            bodyFile.close()

        else:
            # Do something else here.
            cherrypy.response.body = ['Error: ' + str(err[0])]

    def location_bar (self):
        """Returns a string representing the active location bar.

        This method will use the current URL path, and return an HTML string
        where the different components of the path are linked to their URL.

        @return: a HTML string
        @rtype: string
        """
        s = urllib.splittag(
            urllib.splitquery(cherrypy.request.path_info)[0]
            )[0]
        path = s.split('/')[1:]
        return """<a href="/">/</a>""" + "/".join(
            ["""<a href="%s">%s</a>"""
             % (uri, name)
             for (name, uri) in zip(path,
                                    ["/"+"/".join(path[:i+1])
                                     for i in range(len(path))])]
            )

    def no_cache (self):
        """Write the cache-control headers in the response.

        This method sends cache-control headers to ensure that the
        browser does not cache the response, as it may vary from one
        call to another.

        @return: nothing
        """
        cherrypy.response.headers['Pragma']='no-cache'
        cherrypy.response.headers['Cache-Control']='max-age=0'

    def start_html (self, title="", headers=None, head_section=None, body_attributes="",
                    mode=None, mimetype=None, duplicate_title=False, cache=False):
        """Starts writing a HTML response (header + common body start).

        @param title: Title of the HTML document (default : "")
        @type title: string
        @param headers: additional headers to add
        @type headers: a list of tuples (keyword, value)
        @param head_section: additional HTML code to add in the <head></head> section
        @type head_section: string
        @param body_attributes: attributes added to the body tag
        @type body_attributes: string

        @param mode: presentation mode (navigation, raw). Default: navigation
        @type mode: string
        @param duplicate_title: duplicate title as HTML header (h1)
        @type duplicate_title: boolean
        @param cache: make the document cacheable. Default: False
        @type cache: boolean
        @return: nothing
        """
        if mode is None:
            mode = config.data.webserver['displaymode']
        cherrypy.response.status=200
        if mode == 'navigation' or mimetype is None or mimetype == 'text/html':
            mimetype='text/html; charset=utf-8'
        # Enforce utf-8 encoding on all text resources
        if mimetype.startswith('text/') and 'charset' not in mimetype:
            mimetype += '; charset=utf-8'
        cherrypy.response.headers['Content-type']=mimetype
        if headers is not None:
            for h in headers:
                cherrypy.request.headers[h[0]]=h[1]
        if not cache:
            self.no_cache ()

        res=[]
        if mode == "navigation":
            res.append("""<html><head><title>%s</title><link rel="stylesheet" type="text/css" href="/data/advene.css" />""" % title)
            if head_section is not None:
                res.append(head_section)

            res.append("</head><body %s>" % body_attributes)

            res.append(_("""
            <p>
            <a href="/admin">Server administration</a> |
            <a href="/media">Media control</a> |
            <a href="%(path)s?mode=raw">Raw view</a>
            </p>
            Location: %(locationbar)s
            <hr>
            """) % { 'locationbar': self.location_bar (),
                     'path': cherrypy.request.path_info } )

        if duplicate_title and mode == 'navigation':
            res.append("<h1>%s</h1>\n" % title)

        return "".join(res)

    def send_no_content(self):
        """Sends a No Content (204) response.

        Mainly used in /media handling.
        """
        cherrypy.response.status=204
        self.no_cache ()
        return ""

    def send_redirect (self, location):
        """Sends a redirect response.

        As this method generates headers, it must be called before other
        headers or content.

        If the value of C{location} is C{no_content}, then a 204
        response (No Content) will be sent. This can be useful in
        cases where we want to keep on the same origin document.

        @param location: the URL to redirect to.
        @type location: string (URL)
        """
        #cherrypy.response.string=301
        #self.no_cache ()
        #cherrypy.response.headers["Location"]=location
        #cherrypy.response.headers['Content-type']='text/html; charset=utf-8'
        #
        #return _("""
        #<html><head><title>Redirect to %(location)s</title>
        #</head><body>
        #<p>You should be redirected to %(location)s</p>
        #</body></html>
        #""") % {'location':location}
        if location == 'no_content':
            return self.send_no_content()
        raise cherrypy.HTTPRedirect(location)

    def send_error (self, status=404, message=None):
        """Sends an error response.

        @param message: the error message
        @type message: string
        """
        if message is None:
            message=_("Unspecified Error")
        raise cherrypy.HTTPError(status, _("""
        <h1>Error</h1>
        <p>An error occurred:</p>
        %s
        """) % message)

    def image_type (self, o):
        """Return the image type (mime) of the object.

        This method examines the content of the given object, and
        returns either a mime-type if it is an image, I{None} if it is
        not.

        @param o: an object
        @type o: any
        @return: the content-type if o is an image, else None
        @rtype: string
        """
        res=imghdr.what (None, str(o))
        if res is not None:
            return "image/%s" % res
        else:
            return None

    def display_media_status (self):
        """Display current media status.

        This method is called from another embedding method (which
        will generate the appropriate headers). It displays the current
        status of the media player.
        """
        res=[]
        if self.controller.player == None:
            res.append(_("""<h1>No available mediaplayer</h1>"""))
        else:
            l = self.controller.player.playlist_get_list ()
            self.controller.update_status ()
            res.append(_("""
            <h1>Current STBV: %(currentstbv)s</h1>

            <h1>Player status</h1>
            <table border="1">
            <tr>
            <td>Current position</td><td>%(position)s</td>
            <td>Duration</td><td>%(duration)s</td>
            <td>Player status</td><td>%(status)s</td>
            </tr>
            </table>
            """) % {
                    'currentstbv': str(self.controller.current_stbv),
                    'position': helper.format_time(self.controller.player.current_position_value),
                    'duration': helper.format_time(self.controller.player.stream_duration),
                    'status': repr(self.controller.player.status)
                    })

            if len(l) == 0:
                res.append (_("""<h1>No playlist</h1>"""))
            else:
                res.append (_("""<h1>Current playlist</h1>
                <ul>%s</ul>""") % ("\n<li>".join ([ str(i) for i in l ])))
                res.append (_("""
                <form action="/media/play" method="GET">
                Starting pos: <input type="text" name="position" value="0">
                <input type="submit" value="Play">
                </form>
                <a href="/media/stop">Stop</a> | <a href="/media/pause">Pause</a><br>
                """))
            res.append (_("""<hr />
            <form action="/media/load" method="GET">
            Add a new file (<em>dvd</em> to play a DVD):
            <input type="text" name="filename">
            <input type="submit" value="Add">
            </form>"""))
        res.append (_("""<h3><a href="/media/snapshot">Access to current packages snapshots</h3>"""))
        return "".join(res)

    def activate_stbvid(self, stbvid):
        """Activate the given stbv id.
        """
        if stbvid is not None:
            stbv=helper.get_id(self.controller.package.views, stbvid)
            if stbv is None:
                raise cherrypy.HTTPError(400, _('Unknown STBV identifier: %s') % stbvid)
        else:
            stbv=None
        self.controller.queue_action(self.controller.activate_stbv, view=stbv)

class Media(Common):
    """Handles X{/media} access requests.

     Tree organization
     =================

     The C{/media} folder gives the ability to acces the mediaplayer.

     The elements available in this folder are :

       - C{/media/load}
       - C{/media/snapshot}
       - C{/media/play}
       - C{/media/pause}
       - C{/media/stop}
       - C{/media/current}

     Accessing the folder itself will display the media status.

     The X{/media/load} element
     --------------------------

       The C{load} element takes a C{filename} option, which specifies
       the media file that should be loaded into the player.

       The C{dvd} filename is a shortcut for loading the DVD media.

     The X{/media/snapshot} element
     ------------------------------

       The C{snapshot} element is itself a folder, whose elements
       are folders, named from the loaded packages'
       aliases. Accessing the C{snapshot} folder itself will
       display the available sub-folders.

       Each C{snapshot} sub-folder gives access to the content
       of the imagecache matching the name (package alias).

       The path C{/media/snapshot/package_alias} displays the list
       of available snapshots (i.e. the keys in the imagecache),
       indicating wether the image is really available (I{Done}) or
       waiting to be captured (I{Pending}). It the option
       C{mode=inline} is given, the images will be displayed
       inline. In no option is given, only the keys are displayed,
       with a link to the snapshot itself.

       Accessing a specific snapshot is done by suffixing the URL with
       the snapshot index : C{/media/snapshot/package_alias/12321}

     The X{/media/play} element
     --------------------------

       The C{/media/play} starts the media player. It can take three
       optional arguments (in the form of URL-options):

         - C{filename=...} : if specified, the media player will load the
           given file before starting the player.
         - C{position=...} : if specified, the player will start at the
           given position (in ms). Else, it will start
           at the beginning.
         - C{stbv=...} : the id of a STBV to activate

     The X{/media/stop} and X{/media/pause} elements
     -----------------------------------------------

       These elements control the player, and take no argument.
     """
    def index(self):
        """Display media status"""
        return "".join( (
            self.start_html (_('Media information'), mode='navigation'),
            self.display_media_status () ) )
    index.exposed=True

    def load(self, **params):
        """Load a media file.
        """
        if params.has_key ('filename'):
            name = params['filename']
            res=[]
            if name == 'dvd':
                name=self.controller.player.dvd_uri(1, 1)
            self.controller.queue_action(self.controller.set_media, name)
            res.append(_("File added"))
            res.append(_("""<p><strong>%s has been added to the playlist</strong></p>""") % name)
            res.append(self.display_media_status ())
        return "".join(res)
    load.exposed=True

    def snapshot(self, *args, **params):
        """Return the snapshot for the given position.
        """
        # snapshot syntax: /media/snapshot/package_alias/NNNN
        res=[]
        if not args:
            res.append(self.start_html (_("Access to packages snapshots"), duplicate_title=True, mode='navigation'))
            res.append ("<ul>")
            for alias in self.controller.packages.keys ():
                res.append ("""<li><a href="/media/snapshot/%s">%s</a></li>""" % (alias, alias))
            res.append("</ul>")
            return "".join(res)
        alias = args[0]
        try:
            i = self.controller.packages[alias].imagecache
        except KeyError:
            return self.send_error(400, _("Unknown package alias"))

        try:
            position=long(args[1])
        except IndexError:
            # No position was given. Display all available snapshots
            res.append(self.start_html (_("Available snapshots for %s") % alias, duplicate_title=True, mode='navigation'))
            if (params.has_key('mode') and params['mode'] == 'inline'):
                template="""<li><a href="/media/snapshot/%(alias)s/%(position)d"><img src="/media/snapshot/%(alias)s/%(position)d" /></a></li>"""
                res.append ("""<p><a href="/media/snapshot/%s">Display with no inline images</a></p>""" % alias)
            else:
                template="""<li><a href="/media/snapshot/%(alias)s/%(position)d">%(position)d</a> (%(status)s)</li>"""
                res.append (_("""<p><a href="/media/snapshot/%s?mode=inline">Display with inline images</a></p>""") % alias)
            res.append ("<ul>")

            k = i.keys ()
            k.sort ()
            for position in k:
                if i.is_initialized (position):
                    m = _("Done")
                else:
                    m = _("Pending")
                res.append (template % { 'alias': alias,
                                         'position': position,
                                         'status': m })
            res.append ("</ul>")
            return "".join(res)

        if not i.is_initialized (position):
            self.no_cache ()
        snapshot=i[position]
        cherrypy.response.headers['Content-type']=snapshot.contenttype
        res.append (str(snapshot))
        return res
    snapshot.exposed=True

    def play(self, position=None, **params):
        """Play the movie.
        """
        c=self.controller
        if params.has_key('stbv'):
            self.activate_stbvid(params['stbv'])
        if params.has_key ('filename'):
            c.queue_action(c.set_media, params['filename'])

        if not c.player.playlist_get_list():
            return self.send_no_content()

        if position is None:
            try:
                position=params['position']
            except KeyError:
                position=0
        pos=c.create_position (value=long(position),
                               key=c.player.MediaTime,
                               origin=c.player.AbsolutePosition)
        c.queue_action( c.update_status, "set", pos )
        return self.send_no_content()
    play.exposed=True

    def pause(self, **params):
        """Pause the movie.
        """
        if params.has_key('stbv'):
            self.activate_stbvid(params['stbv'])
        self.controller.queue_action(self.controller.update_status, 'pause')
        return self.send_no_content()
    pause.exposed=True

    def stop(self, **params):
        """Stop the movie.
        """
        if params.has_key('stbv'):
            self.activate_stbvid(params['stbv'])
        self.controller.queue_action(self.controller.update_status, 'stop')
        return self.send_no_content()
    stop.exposed=True

    def resume(self, **params):
        """Resume the movie.
        """
        if params.has_key('stbv'):
            self.activate_stbvid(params['stbv'])
        self.controller.queue_action(self.controller.update_status, 'resume')
        return self.send_no_content()
    resume.exposed=True

    def current(self):
        """Return the currently playing movie file.
        """
        cherrypy.response.headers['Content-type']='text/plain'
        l=self.controller.player.playlist_get_list()
        if l:
            return l[0]
        else:
            return 'N/C'
    current.exposed=True

    def stbv(self, *args, **query):
        """Activate the given stbv.
        """
        if not args and not query.has_key('id'):
            cherrypy.response.headers['Content-Type']='text/plain'
            return self.controller.current_stbv.id or 'None'
        else:
            if args:
                stbvid=args[0]
            else:
                stbvid=query['id']
            if stbvid == 'None':
                stbvid=None
            try:
                self.activate_stbvid(stbvid)
            except Exception, e:
                return self.send_error(400, _("Cannot activate stbvid %(stbvid)s: %(error)s") % { 'stbvid': stbvid,
                                                                                           'error': unicode(e) })
            return self.send_redirect("/application/")

    stbv.exposed=True

class Application(Common):
    """Handles X{/application} access requests.

    Tree organization
    =================

    The C{/application} folder gives the ability to acces the application (GUI).

    The elements available in this folder are :

      - C{/application/stbv}
      - C{/application/adhoc}
      - C{/application/config}

    Accessing the folder itself will display the application status.

    The X{/application/stbv} element
    --------------------------------

      C{/application/stbv} activates the given STBV. It takes the STBV id as
      next element in the path, or as C{id=...} parameter. Note that it only
      activates the STBV. To activate the STBV and start the player, use the
      C{/application/play?stbv=...} URI.

    The X{/application/adhoc} element
    ---------------------------------

      C{/application/adhoc} opens the given ad-hoc view. It takes
      the view name as next element in the path. Accessible views
      are: C{tree}, C{timeline}, C{transcription}, C{transcribe},
      C{edit}, C{bookmarks}, C{browser}.

      The transcription view can take an optional C{type}
      parameter, either as next element in the URI or as a
      C{type=...} parameter. To open the transcription view on the
      annotation-type simple_text, you can simply use:
      C{/application/adhoc/transcription/simple_text}

      The transcribe view takes a mandatory C{url} parameter.

      The edit view takes a mandatory C{id} parameter, which is
      the id of the element to be edited.

    The X{/application/config} element
    ----------------------------------

      C{/application/config} gives access to configuration information
      as stored in the C{config.data.web} dictionary.

      Using the C{GET} method returns the value of the
      information. Using the C{PUT} method updates the configuration
      information.
    """
    def current_adhoc(self):
        """Display currently opened adhoc views.
        """
        res=[]
        c=self.controller
        if not c.gui:
            res.append(_("""<p>No GUI is available."""))
        else:
            res.append(_("""<p>Opened adhoc views: %s</p>""") % ", ".join([ v.view_name for v in c.gui.adhoc_views]))
            res.append(_("""<p>Available adhoc views:</p><ul>"""))
            l=c.gui.registered_adhoc_views.keys()
            l.sort()
            for name in l:
                view=c.gui.registered_adhoc_views[name]
                try:
                    description=": " + view.tooltip
                except AttributeError:
                    description=""
                res.append("""<li><a href="/application/adhoc/%(id)s">%(name)s</a>%(description)s</li>""" %
                           { 'id': name,
                             'name': view.view_name,
                             'description': description })
            res.append("</ul>")
        return "".join(res)

    def current_stbv(self):
        """Display currently active STBV.
        """
        res=[]
        c=self.controller
        res.append(_("""<p>Current stbv: %s</p>""") % c.get_title(c.current_stbv))
        res.append(_("""<p>You can activate the following STBV:</p><ul>%s</ul>""")
                         % "\n".join( [ """<li><a href="/application/stbv/%s">%s</a> (<a href="/media/play/0?stbv=%s">%s</a>)</li>""" %
                                        (s.id, c.get_title(s), s.id, _("Activate and play"))
                                        for s in c.get_stbv_list() ] ) )
        return "".join(res)

    def index(self):
        return "".join( (
            self.start_html (_('Application information'), mode='navigation'),
            self.current_stbv(),
            self.current_adhoc() )
            )
    index.exposed=True

    def stbv(self, *args, **query):
        """Activate the given stbv.
        """
        if not args:
            cherrypy.response.headers['Content-Type']='text/plain'
            return self.controller.current_stbv.id or 'None'
        else:
            stbvid=args[0]
            if stbvid == 'None':
                stbvid=None
            try:
                self.activate_stbvid(stbvid)
                return self.send_redirect("/application/")
            except Exception, e:
                self.send_error(400, _("Cannot activate stbvid %(stbvid)s: %(error)s") % { 'stbvid': stbvid,
                                                                                           'error': unicode(e) })
    stbv.exposed=True

    def adhoc(self, view=None, arg=None, **query):
        """Open the given adhoc view.
        """
        c=self.controller
        if view is None or c.gui is None:
            return self.current_adhoc()

        try:
            destination=query['destination']
        except KeyError:
            destination='popup'

        if view == 'transcription':
            atid=arg
            if atid is None:
                try:
                    atid=query['type']
                except KeyError:
                    atid=None

            if atid is not None:
                source="here/annotationTypes/%s/annotations/sorted" % atid
            else:
                # Maybe there was a source parameter ?
                try:
                    source=query['source']
                except KeyError:
                    # No provided source. Use the whole package
                    source="here/annotations/sorted"
            c.queue_action(c.gui.open_adhoc_view, view, source=source, destination=destination)
            return self.send_no_content()

        if view == 'transcribe':
            try:
                url=query['url']
            except KeyError:
                url=None
            c.queue_action(c.gui.open_adhoc_view, view, filename=url, destination=destination)
            return self.send_no_content()

        if view == 'edit':
            elid=arg
            if elid is None:
                try:
                    elid=query['id']
                except KeyError:
                    return self.send_error(400, _("Missing element id parameter"))

            el=c.package.get_element_by_id(elid)
            if el is None:
                return self.send_error(400, _("No existing element with id %s") % elid)

            c.queue_action(c.gui.open_adhoc_view, view, element=el)
            return self.send_no_content()

        if view in c.gui.registered_adhoc_views:
            c.queue_action(c.gui.open_adhoc_view, view, destination=destination)
            return self.send_no_content()

        return self.send_error(400, _("""<p>The GUI view %s does not exist.</p>""") % view)
    adhoc.exposed=True

    def config(self, *args, **query):
        """Set config variable value.
        """
        if not args:
            return self.send_error(500, _("Invalid request"))
        name=args[0]
        try:
            v=config.data.web[name]
        except KeyError:
            return self.send_error(500, _("Invalid configuration variable name"))

        if cherrypy.request.method == 'GET':
            cherrypy.response.headers['Content-Type']='text/plain'
            return str(v)
        elif cherrypy.request.method == 'PUT':
            data=cherrypy.request.rfile.read()
            # Convert the type.
            if isinstance(v, int) or isinstance(v, long):
                try:
                    data=long(data)
                except ValueError:
                    return self.send_error(500, _("Invalid value"))
            config.data.web[name]=data
            return self.send_no_content()
        else:
            return self.send_error(500, _("Unsupported method %s") % cherrypy.request.method)
    config.exposed=True



class Access(Common):
    """Displays the access control menu.

    Access Control
    ==============

    Access control is available in the AdveneServer through the
    path X{/admin/access}. By default, only the localhost (IP
    address 127.0.0.1) is allowed to access the server. The user
    can add or delete hosts from the access list, but the
    localhost can never be removed from the access list.

    The addition or removal of a computer is done through URLs:
    X{/admin/access/add/hostname} and X{/admin/access/delete/hostname}

    If no options are given, the current access control list is
    displayed.
    """
    def display_access_list(self):
        """Display the current access list.
        """
        return _("""
        <h1>Authorized hosts</h1>
        <table border="1">
        <tr><th>Host</th><th>IP Addr</th><th>Action</th></tr>
        %s
        </table>
        <form method="GET">
        Add a new hostname to the list :<br>
        <input type="text" name="hostname"><input type="submit" value="Add">
        </form>
        """) % "\n".join(["""<tr><td>%(name)s</td><td>%(ip)s</td><td><a href="/admin/access/delete/%(name)s">Remove</a></td></tr>""" % { 'ip': ip, 'name': name }
                          for (name, ip) in self.controller.server.authorized_hosts.items()])

    def index(self):
        return "".join( ( self.start_html(_('Access control'), duplicate_title=True, mode='navigation'),
                          self.display_access_list()) )
    index.exposed=True

    def add(self, hostname):
        res=[self.start_html(_('Access control - add a hostname'), duplicate_title=True, mode='navigation')]
        ip=None
        if hostname == '*':
            ip='*'
        else:
            try:
                ip = socket.gethostbyname (hostname)
            except socket.error:
                res.append (_("""<strong>Error: %s is an invalid hostname.</strong>""") % hostname)
        if ip is not None:
            self.controller.server.authorized_hosts[ip] = hostname
            res.append (_("""<p>Added %s to authorized hosts list.</p>""") % hostname)
        res.append(self.display_access_list())
        return "".join(res)
    add.exposed=True

    def delete(self, hostname):
        res=[self.start_html(_('Access control - delete a hostname'), duplicate_title=True, mode='navigation')]
        ip=None
        try:
            ip = socket.gethostbyname (hostname)
        except socket.error:
            res.append (_("""<strong>Error: %s is an invalid hostname.</strong>""") % hostname)

        if ip == '127.0.0.1':
            res.append(_("""<strong>Cannot remove the localhost access.</strong>"""))
        elif ip is not None:
            # Remove the hostname
            if ip in self.controller.server.authorized_hosts:
                del self.controller.server.authorized_hosts[ip]
                res.append (_("""<p>Removed %s from authorized hosts list.</p>""") % hostname)
            else:
                res.append (_("""<p>%s is not in authorized hosts list.</p>""") % hostname)
        res.append(self.display_access_list())
        return "".join(res)
    delete.exposed=True

class Admin(Common):
    """Handles the X{/admin}  requests.

    The C{/admin} folder contains the following elements for the
    administration of the server:

      - C{/admin/list} : display the list of currently loaded packages
      - C{/admin/load} : load a new package
      - C{/admin/save/alias} : save a package
      - C{/admin/delete/alias} : remove a loaded package
      - C{/admin/access} : display access control list
      - C{/admin/status} : display current status
      - C{/admin/display} : display or set the default webserver display mode
      - C{/admin/methods} : list the available global methods
      - C{/admin/halt} : halt the webserver

    Accessing the C{/admin} folder itself displays the summary
    (equivalent to the root document).

    Loading, saving or deleting packages is done by specifying the
    C{alias} parameter. In the case of the C{/admin/load} action,
    the C{uri} parameter must provide the appropriate URI.

    Setting the X{display mode}
    ===========================

    Accessing the C{/admin/display} element updates the server
    display mode. The data should be available as a parameter
    named C{mode}, which is either C{default} or C{raw}, or as
    last element in the URI, for instance
    C{/admin/display/navigation}

    @param l: the access path as a list of elements,
              with the initial one (C{access}) omitted
    @type l: list
    @param query: the options given in the URL
    @type query: dict
    """
    def index(self):
        """Display the main administration page.

        This method displays the administration page of the server, which
        should link to all functionalities.
        """
        res=[ self.start_html (_("Server Administration"), duplicate_title=True, mode='navigation') ]
        if self.controller.server.displaymode == 'raw':
            switch='navigation'
        else:
            switch='raw'
        mode_sw="""%(mode)s (<a href="/admin/display/%(switch)s">switch to %(switch)s</a>)""" % {
            'mode': self.controller.server.displaymode, 'switch': switch }

        res.append(_("""
        <p><a href="/admin/access">Update the access list</a></p>
        <p><a href="/admin/methods">List available TALES methods</a></p>
        <p><a href="/action">List available actions</a></p>
        <p><a href="/admin/reset">Reset the server</a></p>
        <p><a href="/media">Media control</a></p>
        <p><a href="/application">Display GUI status</a></p>
        <p><a href="/admin/list">List available files</a></p>
        <p><a href="/packages">List loaded packages</a> (%(packagelist)s)</p>
        <p>Display mode : %(displaymode)s</p>
        <hr>
        <p>Load a package :
        <form action="/admin/load" method="GET">
        Alias: <input type="text" name="alias" /><br>
        URI:   <input type="text" name="uri" /><br>
        <input type="submit" value="Load" />
        </form>
        </body></html>
        """) % { 'packagelist': " | ".join( ['<a href="/packages/%s">%s</a>' % (alias, alias)
                                             for alias in self.controller.packages.keys() ] ),
                 'displaymode': mode_sw })
        return "".join(res)
    index.exposed=True

    def list(self):
        """Display available Advene files.

        This method displays the data files in the data directory.
        Maybe it should be removed when the server runs embedded.
        """
        res=[ self.start_html (_("Available files"), duplicate_title=True, mode='navigation') ]
        res.append ("<ul>")

        l=[ os.path.join(config.data.path['data'], n)
            for n in os.listdir(config.data.path['data'])
            if n.lower().endswith('.xml') or n.lower().endswith('.azp') ]
        l.sort(lambda a, b: cmp(a.lower(), b.lower()))
        for uri in l:
            name, ext = os.path.splitext(uri)
            alias = re.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))
            res.append ("""
            <li><a href="/admin/load?alias=%(alias)s&uri=%(uri)s">%(uri)s</a></li>
            """ % {'alias':alias, 'uri':uri})
        res.append ("""
        </ul>
        """)
        return "".join(res)
    list.exposed=True

    def load(self, *args, **query):
        """Load the specified URI with the given alias.
        """
        try:
            alias = query['alias']
        except KeyError:
            return self.send_error (501,
                                    _("""You should specify an alias"""))
        try:
            uri = query['uri']
        except KeyError:
            return self.send_error (501,
                                    _("""You should specify an uri"""))
        try:
            # FIXME: potential problem: this method executes in the webserver thread, which may
            # cause problems with the GUI
            self.controller.load_package (uri=uri, alias=alias)
            return "".join( (
                self.start_html (_("Package %s loaded") % alias, duplicate_title=True, mode='navigation'),
                _("""<p>Go to the <a href="/packages/%(alias)s">%(alias)s</a> package, or to the <a href="/packages">package list</a>.""") % { 'alias': alias }
                ))
        except Exception, e:
            return self.send_error(501, _("""<p>Cannot load package %(alias)s : %(error)s</p>""" % {
                        'alias': alias,
                        'error': str(e) }))
    load.exposed=True

    def delete(self, alias):
        """Unload a package.
        """
        try:
            self.controller.unregister_package (alias)
            return "".join((
                self.start_html (_("Package %s deleted") % alias, duplicate_title=True, mode='navigation'),
                _("""<p>Go to the <a href="/packages">package list</a>.""")
                ))
        except Exception, e:
            return self.send_error(501, _("""<p>Cannot delete package %(alias)s : %(error)s</p>""" % {
                        'alias': alias,
                        'error': str(e) }
                                          ))
    delete.exposed = True

    def save(self, alias=None):
        """Save a package.
        """
        try:
            if alias is not None:
                # Save a specific package
                self.controller.save_package(alias=alias)
            else:
                self.controller.save_package()
                alias='default'
            return "".join((
                self.start_html (_("Package %s saved") % alias, duplicate_title=True, mode='navigation'),
                _("""<p>Go to the <a href="/packages/%(alias)s">%(alias)s</a> package, or to the <a href="/packages">package list</a>.""") % { 'alias': alias }
                ))
        except Exception, e:
            return self.send_error(501, _("""<p>Cannot save package %(alias)s : %(error)s</p>""" % {
                        'alias': alias,
                        'error': str(e) }
                                          ))
    save.exposed=True

    def reset(self):
        """Reset packages list.
        """
        self.controller.reset()
        return self.start_html (_('Server reset'), duplicate_title=True, mode='navigation')
    reset.exposed=True

    def methods(self):
        """Display available TALES methods.
        """
        res=[ self.start_html (_('Available TALES methods'), duplicate_title=True, mode='navigation') ]
        res.append('<ul>')
        c=self.controller.build_context(here=None)
        k=c.methods.keys()
        k.sort()
        for name in k:
            descr=c.methods[name].__doc__
            if descr:
                descr=descr.split('\n')[0]
            res.append("<li><strong>%s</strong>: %s</li>\n" % (name, descr))
        res.append("</ul>")
        return "".join(res)
    methods.exposed=True

    def display(self, mode=None):
        """Set display mode.
        """
        if mode:
            # Set default display mode
            if mode in ('raw', 'navigation'):
                self.controller.server.displaymode=mode
            ref=cherrypy.request.headers.get('Referer', "/")
            return self.send_redirect(ref)
        else:
            # Display status
            cherrypy.response.status=200
            cherrypy.response.headers['Content-type']='text/plain'
            self.no_cache ()
            return self.controller.server.displaymode
    display.exposed=True

class Packages(Common):
    """Node for packages access.
    """
    def index(self):
        """Display currently available (loaded) packages.

        This method displays the list of currently loaded
        packages. The generated list provides links for accessing,
        reloading, saving or removing the package.
        """
        res=[ self.start_html (_("Loaded package(s)"), mode='navigation') ]

        res.append (_("""
        <h1>Loaded package(s)</h1>
        <table border="1" width="50%">
        <tr>
        <th>Alias</th>
        <th>Action</th>
        <th>URI</th>
        <th>Annotations</th>
        </tr>
        """))
        for alias in self.controller.packages.keys():
            p = self.controller.packages[alias]
            res.append (_("""<tr>
            <td><a href="/packages/%(alias)s">%(alias)s</a></td>
            <td align="center"><a href="/admin/load?alias=%(alias)s&uri=%(uri)s">Reload</a>|<a href="/admin/delete?alias=%(alias)s">Drop</a>|<a href="/admin/save?alias=%(alias)s">Save</a></td>
            <td>%(uri)s</td>
            <td>%(size)d</td>
            </tr>
            """) % { 'alias':alias, 'uri':p.uri, 'size':len(p.annotations) })
        res.append ("""
        </ul>
        """)
        return "".join(res)
    index.exposed=True

    def display_package_element (self, p, tales, query=None):
        """Display a view for a TALES expression.

        This method displays the view for the element defined by the
        expression C{tales} wrt to package C{p}, with facultative
        parameters in C{query}. It handles the X{/packages} folder.

        The query can hold an optional parameter, named C{mode}, which
        indicates a specific display mode for the resulting
        object. Valid modes are:

          - C{image} : the object is an image, and we generate the
                       correct headers.
          - C{raw} : do not display the navigation interface, but only the
                     object's view
          - C{content} : return the content data of an object, with
                         its specific mime-type
          - C{default} : default mode, with navigation interface

        The C{display mode} has a default value at the server level,
        wich can be set through the C{/admin} folder.

        An autodetect feature will force the display mode to C{image}
        if the object is an image (depending on the return value of
        L{image_type}).

        All other other parameters given on the URL path are kepts in
        the C{query} dictionary, which is available in TALES
        expressions through the C{request/} root element.

        @param p: the package in which the expression should be evaluated
        @type p: advene.model.Package
        @param tales: a TALES expression
        @type tales: string
        @param query: options used in TAL/TALES processing
        @type query: dict
        """
        res=[]
        alias = self.controller.aliases[p]

        if query is None:
            query={}

        if tales == "":
            expr = "here"
        elif tales.startswith ('options'):
            expr = tales
        else:
            expr = "here/%s" % tales

        context = self.controller.build_context (here=p, alias=alias)
        context.pushLocals()
        context.setLocal('request', query)
        # FIXME: the following line is a hack for having qname-keys work
        #        It is a hack because obviously, p is not a "view"
        context.setLocal (u'view', p)

        try:
            objet = context.evaluate(expr)
        except AdveneException, e:
            self.start_html (_("Error"), duplicate_title=True, mode='navigation')
            res.append (_("""The TALES expression %s is not valid.""") % tales)
            res.append (unicode(e.args[0]).encode('utf-8'))
            return

        # FIXME:
        # Principe: si l'objet est un viewable, on appelle la
        # methode view pour en obtenir une vue par defaut.
        #if isinstance(objet, advene.model.viewable.Viewable):
        #    # It is a viewable, so display it using the default view
        #    objet.view(context=context)

        displaymode = self.controller.server.displaymode
        # Hack to automatically switch to an image view for image objects.
        # FIXME: we should find a clean solution (for instance a new object
        # with a content-type method : if it is HTML, we return it normally ;
        # if it is some other thing, we return it with the correct content-type
        # header).
        if query.has_key('mode'):
            displaymode = query['mode']
            del (query['mode'])
        if isinstance(objet, str) and self.image_type (objet) is not None:
            displaymode = 'image'

        if displaymode == 'image':
            # Return an image, so build the correct headers
            cherrypy.response.status=200
            cherrypy.response.headers['Content-type']=self.image_type(str(objet))
            self.no_cache ()

            res.append (str(objet))
            return "".join(res)
        elif displaymode == 'content':
            if hasattr(objet, 'mimetype'):
                cherrypy.response.status=200
                cherrypy.response.headers['Content-type']=objet.mimetype
                self.no_cache ()
                res.append (objet.data)
                return "".join(res)
            elif hasattr(objet, 'contenttype'):
                cherrypy.response.status=200
                cherrypy.response.headers['Content-type']=objet.contenttype
                self.no_cache ()
                res.append (objet)
                return "".join(res)
            else:
                return self.send_error (404, _("Content mode not available on non-content data"))

        # Last case: default or raw

        if displaymode != "raw":
            displaymode = "navigation"

        # Display content
        if hasattr (objet, 'view') and callable (objet.view):

            context = self.controller.build_context(here=objet, alias=alias)
            context.pushLocals()
            context.setLocal('request', query)
            # FIXME: should be default view
            context.setLocal(u'view', objet)
            try:
                v=objet.view (context=context)
                res.append( self.start_html(mimetype=v.contenttype) )
                if v.contenttype.startswith('text'):
                    res.append (unicode(v).encode('utf-8'))
                else:
                    res.append(v)
            except simpletal.simpleTAL.TemplateParseException, e:
                res.append( self.start_html(_("Error")) )
                res.append(_("<h1>Error</h1>"))
                res.append(_("""<p>There was an error in the template code.</p>
                <p>Tag name: <strong>%(tagname)s</strong></p>
                <p>Error message: <em>%(message)s</em></p>""") % {
                        'tagname': cgi.escape(e.location),
                        'message': e.errorDescription} )
                return "".join(res)
            except simpleTALES.ContextContentException, e:
                res.append( self.start_html(_("Error")) )
                res.append(_("<h1>Error</h1>"))
                res.append(_("""<p>An invalid character is in the Context:</p>
                <p>Error message: <em>%(error)s</em></p><pre>%(message)s</pre>""")
                                 % {'error': e.errorDescription,
                                    'message': unicode(e.args[0]).encode('utf-8')})
                return "".join(res)
            except AdveneException, e:
                res.append( self.start_html(_("Error")) )
                res.append(_("<h1>Error</h1>"))
                res.append(_("""<p>There was an error in the TALES expression.</p>
                <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
                return "".join(res)
        else:
            mimetype=None
            try:
                mimetype = objet.mimetype
            except AttributeError:
                try:
                    mimetype = objet.contenttype
                except AttributeError:
                    pass
            try:
                res.append( self.start_html(mimetype=mimetype) )
                if mimetype and mimetype.startswith('text'):
                    res.append (unicode(objet).encode('utf-8'))
                else:
                    res.append(str(objet))
            except AdveneException, e:
                res.append(_("<h1>Error</h1>"))
                res.append(_("""<p>There was an error.</p>
                <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
            except simpletal.simpleTAL.TemplateParseException, e:
                res.append(_("<h1>Error</h1>"))
                res.append(_("""<p>There was an error in the template code.</p>
                <p>Tag name: <strong>%(tagname)s</strong></p>
                <p>Error message: <em>%(message)s</em></p>""") % {
                            'tagname': cgi.escape(e.location),
                            'message': e.errorDescription})

        # Generating navigation footer
        if displaymode == 'navigation' and 'html' in cherrypy.response.headers['Content-type']:
            uri=cherrypy.request.path_info
            levelup = uri[:uri.rindex("/")]
            auto_components = [ c
                                for c in helper.get_valid_members (objet)
                                if not c.startswith('----') ]
            auto_components.sort()
            try:
                auto_views = objet.validViews
                auto_views.sort()
            except AttributeError:
                auto_views = []

            res.append (_("""
            <hr>
            <p>
            Location: %(location)s<br>
            <form name="navigation" method="GET">
            <a href="%(levelup)s">Up one level</a> |
            Next level :
            <select name="path" onchange="submit()">
            """) % {
                    'location': self.location_bar (),
                    'levelup': levelup})

            if hasattr (objet, 'view'):
                res.append ("<option selected>view</option>")

            res.append ("\n".join(
                ["""<option>%s</option>""" % c for c in auto_components]))

            res.append (_("""
            </select> View: <select name="view" onchange="submit()">
            <option selected></option>
            """))

            res.append ("\n".join(
                ["""<option value="%s">%s</option>""" %
                 ("/".join((cherrypy.url(), "view", c)), c)
                 for c in auto_views]))

            res.append ("""
            </select>
            <input type="submit" value="go">
            </form>
            <form name="entry" method="GET">
            <input size="50" type="text" name="path" accesskey="p">
            <input type="submit" value="go"></form>
            """)
            res.append (_("""<hr>
            <p>Evaluating expression "<strong>%(expression)s</strong>" on package %(uri)s returns %(value)s</p>
            """) % {
                    'expression': tales ,
                    'uri': p.uri,
                    'value': cgi.escape(str(type(objet)))})
        return "".join(res)

    def default(self, *args, **query):
        """Access a specific package.

        URL handling
        ============

        The URL is first split in components, and some parameters may
        modify the interpretation of the path.

        The C{path} parameter is used to interactively modifying the
        path (through a form).

        Else, the C{path} value will be appended to the current path
        of the URL, and the browser is redirected to this new location.

        The C{view} parameter is a shortcut for rapidly accessing an
        element view. Its value is in fact the URL displaying the
        correct view, and the browser is redirected.

        """
        if not args:
            return self.index()

        pkgid = args[0]

        try:
            p = self.controller.packages[pkgid]
        except KeyError:
            return self.send_error (501, _("<p>Package <strong>%s</strong> not loaded</p>")
                                    % pkgid)

        # Handle form parameters (from the navigation interface)
        if query.has_key('view'):
            if query['view'] != '':
                # The 'view' parameter is in fact the new path
                # that we should redirect to
                return self.send_redirect (query['view'])
            else:
                # If the submit was done automatically on "path" modification,
                # the view field will exist but be empty, so delete it
                del(query['view'])

        if query.has_key('path'):
            # Append the given path to the current URL
            p="/".join( (cherrypy.url(), query['path']) )
            if query['path'].find ('..') != -1:
                p = os.path.normpath (p)
            del(query['path'])
            if len(query) == 0:
                location = p
            else:
                location = "%s?%s" % (p,
                                      "&".join (["%s=%s" % (k,urllib.quote(query[k]))
                                                 for k in query.keys()]))
            return self.send_redirect (location)

        tales = "/".join (args[1:])

        if cherrypy.request.method == 'PUT':
            return self.handle_put_request(*args, **query)
        elif cherrypy.request.method == 'POST':
            return self.handle_post_request(*args, **query)
        elif cherrypy.request.method != 'GET':
            return self.send_error(400, 'Unknown method: %s' % cherrypy.request.method)

        try:
            return self.display_package_element (p , tales, query)
        except simpletal.simpleTAL.TemplateParseException, e:
            res=[ self.start_html(_("Error")) ]
            res.append(_("<h1>Error</h1>"))
            res.append(_("""<p>There was an error in the template code.</p>
            <p>Tag name: <strong>%(tagname)s</strong></p>
            <p>Error message: <em>%(message)s</em></p>""") % {
                        'tagname': cgi.escape(e.location),
                        'message': e.errorDescription })
        except AdveneException, e:
            res=[ self.start_html(_("Error")) ]
            res.append(_("<h1>Error</h1>"))
            res.append(_("""<p>There was an error in the expression.</p>
            <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
        except:
            # FIXME: should use standard Cherrypy error handling.
            t, v, tr = sys.exc_info()
            import code
            res=[ self.start_html(_("Error")) ]
            res.append(_("<h1>Error</h1>"))
            res.append(_("""<p>Cannot resolve TALES expression %(expr)s on package %(package)s<p><pre>
            %(type)s
            %(value)s
            %(traceback)s</pre>""") % {
                    'expr': tales,
                    'package': pkgid,
                    'type': unicode(tales),
                    'value': unicode(v),
                    'traceback': "\n".join(code.traceback.format_tb (tr)) })

        return "".join(res)
    default.exposed=True

    def handle_put_request(self, *args, **query):
        """Handle PUT requests (update or create).

        A PUT request done on an Advene element will try to update it
        with the given content.

        Data transmission
        =================

        Data can be transmitted either as a textual content (from a
        <textarea> or an <input> field), or as a file upload.

        To transmit the content of a textarea, use C{data} as field
        name.

        To transmit the content from a file upload, use C{datafile} as
        field name.

        Generic information
        ===================

        The PUT method requests that the enclosed entity be stored
        under the supplied Request-URI. If the Request-URI refers to
        an already existing resource, the enclosed entity SHOULD be
        considered as a modified version of the one residing on the
        origin server. If the Request-URI does not point to an
        existing resource, and that URI is capable of being defined as
        a new resource by the requesting user agent, the origin server
        can create the resource with that URI.

        If a new resource is created, the origin server MUST inform
        the user agent via the 201 (Created) response.

        If an existing resource is modified, either the 200 (OK) or
        204 (No Content) response codes SHOULD be sent to indicate
        successful completion of the request.

        If the resource could not be created or modified with the
        Request-URI, an appropriate error response SHOULD be given
        that reflects the nature of the problem. The recipient of the
        entity MUST NOT ignore any Content-* (e.g. Content-Range)
        headers that it does not understand or implement and MUST
        return a 501 (Not Implemented) response in such cases.
        """
        if len(args) < 2:
            return self.send_error(501, _("<h1>Error</h1>") +
                            _("<p>Cannot set the value : invalid path</p>"))

        alias=args[0]

        # Get the TALES expression of the element, and its attribute name
        tales = "/".join (args[1:-1])
        attribute = args[-1]

        if tales == "":
            expr = "here"
        else:
            expr = "here/%s" % tales

        context = self.controller.build_context(here=self.controller.packages[alias],
                                                alias=alias)
        context.pushLocals()
        context.setLocal('request', query)

        # Handle the various ways to transmit data
        if 'datafile' in query:
            # File upload.
            data=query['datafile'].value
        elif 'datapath' in query:
            # A file path was specified. This will put the
            # content of the path specified by 'datapath',
            # from the server filesystem. This is a
            # temporary and convenience hack to manage the
            # uploading of resource files from the WYSIWYG
            # editor.
            # FIXME FIXME FIXME
            # However it is a serious security issue, since:
            # - in the non-embedded case, users may get
            #   the content of any file from the server.
            # - in the embedded case (GUI embedding
            #   server), other users may access the files
            #   owned by the user running the application
            # This should be addressed at some time...
            data=open(query['datapath'], 'rb').read()
        else:
            data=query['data']

        if tales.startswith('resources'):
            # Resource creation
            path=tales.split('/')[1:]
            parent=self.controller.package.resources
            if path:
                # The resource is in a folder. Let's create the
                # hierarchy first.
                for i in range(1, len(path)+1):
                    subpath=path[:i]
                    try:
                        r = context.evaluate("here/resources/%s" % "/".join(subpath))
                    except AdveneException:
                        # The resource folder does not exist. Create it.
                        parent[subpath[-1]] = parent.DIRECTORY_TYPE
                        el=parent[subpath[-1]]
                        self.controller.notify('ResourceCreate',
                                               resource=el)
                        r=el
                    if isinstance(r, Resources):
                        parent=r
                    else:
                        return self.send_error(501, (_("<h1>Error</h1><p>When creating resource %(path)s, the resource folder %(folder)s could not be created.</p>") % {
                                    'path': '/'.join(path),
                                    'folder': subpath[-1] }).encode('utf-8'))
            # We can create the resource in the parent ResourceFolder
            parent[attribute]=data
            el=parent[attribute]
            self.controller.notify('ResourceCreate',
                                   resource=el)
            cherrypy.response.status=200
            return _("Resource successfuly created/updated")

        try:
            objet = context.evaluate(expr)
        except Exception, e:
            return self.send_error(501, _("<h1>Error</h1>") + unicode(e.args[0]).encode('utf-8'))
        try:
            objet.__setattr__(attribute, data)
            cherrypy.response.status=200
            return _("Value successfuly updated")
        except Exception, e:
            return self.send_error(501, _("Unable to update the attribute %(attribute)s for element %(element)s: %(error)s." ) % { 'attribute': attribute, 'element': objet, 'error': e })

    def handle_post_request(self, *args, **query):
        """Handle POST requests (update, create or delete).

        The C{POST} requests are used to update or create elements in
        a package. Only a limited set of elements are accessible in
        this way.

        Manipulating package data
        =========================

        The package data can be manipulated in this way. The
        appropriate action is specified through the C{action}
        parameter, which can be either C{update}, C{create} or
        C{delete}.

        Data transmission
        =================

        Data can be transmitted either as a textual content (from a
        <textarea> or an <input> field), or as a file upload.

        To transmit the content of a textarea, use C{data} as field
        name.

        To transmit the content from a file upload, use C{datafile} as
        field name.

        Moreover, if a C{redirect} field is present, it should contain
        a URL which will be redirected to upon successful creation or
        update.

        Updating data
        =============

        The update of an element of the object addressed by the POSTed
        URL is done by giving the URL of the element to update.

        If an additional C{object} parameter is given, it indicates
        that the object is a list, and that we should access one of
        its elements named by C{object}.

        For instance, the update of the content of the view C{foo} in
        the package C{bar} can be done through the following form::

          <form method="POST" action="/packages/bar/views/foo/content/data">
          <textarea name="data">Contents</textarea>
          <input type="hidden" name="action" value="update">
          <input type="submit" value="Submit" />
          <input name="redirect" type="hidden" value="http://foo/bar" /><br />
          </form>

        Creating new data
        =================

        The creation of new elements in a package is done by
        specifying the C{action=create} parameter. The TALES path must
        be the path of the package (C{/packages/pkgid}), except for
        resources where the TALES path is the path of the resource to
        be created.

        The type of the created object is given through the C{type}
        parameter. For the moment, C{view}, C{annotationtype},
        C{relationtype} and C{resource} are valid.

        A view is created with the following data, specified with parameters:

          - C{id} : the identifier of the view. Should not be already used.
          - C{class} : the class that this view should apply on.
          - C{data} : the content data of the view (the TAL template).

        An annotation is created with the following data:
          - C{id}: the identifier (optional, is generated if empty)
          - C{type}: the annotation-type id
          - C{begin}, C{end}: the begin and end time in ms
          - C{data}: the content data (optional)

        The following HTML code gives an example of relation creation::

           <form method="POST" action="http://localhost:1234/packages/advene">
             <input type="hidden" name="action" value="create" />
             <input type="hidden" name="type" value="annotation" />
           AnnotationType:  <input name="annotationtype" value="annotation"/><br />
           Begin (in  ms): <input name="begin" value="1" /><br />
           End (in ms): <input name="end" value="5000" /><br />
           Content: <input name="data" value="Empty Annotation" /><br />
           Redirect: <input name="redirect" value="" /><br />
           <input type="submit" name="submit" />
           </form>

        An relation is created with the following data:
          - C{id}: the identifier (optional, is generated if empty)
          - C{type}: the relation-type id
          - C{member1}, C{member2}: the ids of the members of the relation
          - C{data}: the content data (optional)

        The following HTML code gives an example of relation creation::

           <form method="POST" action="http://localhost:1234/packages/advene">
             <input type="hidden" name="action" value="create" />
             <input type="hidden" name="type" value="relation" />
           RelationType:  <input name="relationtype" value="basic-relation"/><br />
           Member1:  <input name="member1" value="a1" /><br />
           Member2  <input name="member2" value="a2" /><br />
           Content: <input name="data" value="Empty Relation" /><br />
           Redirect: <input name="redirect" value="" /><br />
           <input type="submit" name="submit" />
           </form>
        """
        if not 'action' in query or not ('data' in query or 'datapath' in query or 'datafile' in query):
            return self.send_error(500, _("<p>Invalid request</p>."))

        if not args:
            return self.send_error(501, _("<h1>Error</h1>") +
                            _("<p>Cannot set the value : invalid path</p>"))

        alias=args[0]

        # Get the TALES expression of the element, and its attribute name
        tales = "/".join (args[1:-1])
        if len(alias) > 1:
            attribute = args[-1]
        else:
            attribute = ''

        if tales == "":
            expr = "here"
        else:
            expr = "here/%s" % tales

        package=self.controller.packages[alias]
        context = self.controller.build_context(here=package, alias=alias)
        context.pushLocals()
        context.setLocal('request', query)

        # Handle the various ways to transmit data
        if 'datafile' in query:
            # File upload.
            data=query['datafile'].value
        elif 'datapath' in query:
            # A file path was specified. This will put the
            # content of the path specified by 'datapath',
            # from the server filesystem. This is a
            # temporary and convenience hack to manage the
            # uploading of resource files from the WYSIWYG
            # editor.
            # FIXME FIXME FIXME
            # However it is a serious security issue, since:
            # - in the non-embedded case, users may get
            #   the content of any file from the server.
            # - in the embedded case (GUI embedding
            #   server), other users may access the files
            #   owned by the user running the application
            # This should be addressed at some time...
            data=open(query['datapath'], 'rb').read()
        else:
            data=query['data']

        # Different actions : update, create, delete
        if query['action'] == 'update':
            try:
                objet = context.evaluate(expr)
            except Exception, e:
                return self.send_error(501, _("<h1>Error</h1>") + unicode(e.args[0]).encode('utf-8'))
            if hasattr(objet, attribute):
                objet.__setattr__(attribute, data)
                if 'redirect' in query and query['redirect']:
                    return self.send_redirect(query['redirect'])
                if expr.endswith('/content'):
                    # We have updated the content.data of an element
                    element = context.evaluate(expr[:-8])
                    if isinstance(element, View) and element.matchFilter['class'] in ('*', 'package'):
                        return self.send_redirect('/packages/advene/view/' + element.id)
                    else:
                        res=[ self.start_html(_("Value updated")) ]
                        res.append (_("""
                <h1>Value updated</h1>
                The value of %(path)s has been updated to
                <pre>
                %(value)s
                </pre>
                """) % { 'path': "/".join([tales, attribute]),
                         'value': cgi.escape(data) })
                        return "".join(res)
            else:
                # Fallback mode : maybe we were in a dict, and
                # attribute is the id of the object in the dict
                try:
                    objet[attribute]=data
                    if 'redirect' in query and query['redirect']:
                        return self.send_redirect(query['redirect'])
                    res=[ self.start_html(_("Value updated")) ]
                    res.append (_("""
                    <h1>Value updated</h1>
                    The value of %(path)s has been updated to
                    <pre>
                    %(value)s
                    </pre>
                    """) % { 'path': "%s[%s]" % (tales, attribute),
                             'value': cgi.escape(data) })
                    return "".join(res)
                except TypeError:
                    # Not a dict...
                    return self.send_error(500, _("Malformed request: cannot update the value of %(attribute)s in %(tales)s.") % locals())

        elif query['action'] == 'create':
            # Creating an element. If it is a resource, its id is
            # specified by its TALES path. For other types of elements
            # (annotation, view, relation...), the TALES path must
            # point to the package.
            if query['type'] == 'resource':
                if tales.startswith('resources'):
                    # Resource creation
                    path=tales.split('/')[1:]
                    parent=package.resources
                    if path:
                        # The resource is in a folder. Let's create the
                        # hierarchy first.
                        for i in range(1, len(path)+1):
                            subpath=path[:i]
                            try:
                                r = context.evaluate("here/resources/%s" % "/".join(subpath))
                            except AdveneException:
                                # The resource folder does not exist. Create it.
                                parent[subpath[-1]] = parent.DIRECTORY_TYPE
                                el=parent[subpath[-1]]
                                self.controller.notify('ResourceCreate',
                                                       resource=el)
                                r=el
                            if isinstance(r, Resources):
                                parent=r
                            else:
                                return self.send_error(501, (_("<h1>Error</h1><p>When creating resource %(path)s, the resource folder %(folder)s could not be created.</p>") % {
                                            'path': '/'.join(path),
                                            'folder': subpath[-1] }).encode('utf-8'))
                    parent[attribute]=data
                    el=parent[attribute]
                    self.controller.notify('ResourceCreate',
                                           resource=el)
                    cherrypy.response.status=200
                    if 'redirect' in query and query['redirect']:
                        return self.send_redirect(query['redirect'])
                    return _("Resource successfuly created/updated")

            # A TALES path was specified. We cannot handle this case.
            if expr:
                return self.send_error(500, _("Cannot create an element in something else than a package."))
            objet=package

            # Keyword parameters for each create* method
            kw={}
            def update_arg(formname, argname, default):
                try:
                    kw[argname]=query[formname]
                except KeyError:
                    kw[argname]=default

            if query['type'] == 'view':
                update_arg('id', 'ident', None)
                if kw['ident'] is None:
                    kw['ident']=objet._idgenerator.get_id(View)
                    objet._idgenerator.add(kw['ident'])
                elif objet._idgenerator.exists(kw['ident']):
                    return self.send_error(500, _("The identifier %s already exists.") % kw['ident'])

                update_arg('mimetype', 'content_mimetype', 'text/html')
                update_arg('class', 'clazz', 'package')
                update_arg('author', 'author', config.data.userid)
                kw['content_data']=data
                kw['date']=self.controller.get_timestamp()
                try:
                    v = objet.createView(**kw)
                    objet.views.append(v)
                except Exception, e:
                    return self.send_error(500,
                                           _("<p>Error while creating view %(id)s</p><pre>%(error)s</pre>") % {
                            'id': kw['ident'],
                            'error': unicode(e).encode('utf-8') })

                if 'redirect' in query and query['redirect']:
                    return self.send_redirect(query['redirect'])
                return "".join( ( self.start_html(_("View created")),
                                  _("""
                 <h1>View <em>%(id)s</em> created</h1>
                 <p>The view <a href="%(url)s">%(id)s</a> was successfully created.</p>
                 """) % { 'id': v.id,
                          'url': "/packages/%s/views/%s" % (self.controller.aliases[objet],
                                                            v.id) }) )

            elif query['type'] == 'relation':
                # Takes as parameters:
                # id = identifier (optional)
                # relationtype = relation type identifier
                # member1 = first member (annotation id)
                # member2 = second member (annotation id)
                # data = content data (optional)
                for k in ('relationtype', 'member1', 'member2'):
                    if not query.has_key(k):
                        return self.send_error(500, _("Missing %s parameter") % k)
                rt = context.evaluate("here/relationTypes/%s" % query['relationtype'])
                if rt is None:
                    return self.send_error(500, _("Relation type %s does not exist") % query['relationtype'])
                try:
                    id_ = query['id']
                except KeyError:
                    id_ = objet._idgenerator.get_id(Relation)
                m1 = context.evaluate('package/annotations/%s' % query['member1'])
                if m1 is None:
                    return self.send_error(500, _("Annotation %s does not exist") % query['member1'])
                m2 = context.evaluate('package/annotations/%s' % query['member2'])
                if m2 is None:
                    return self.send_error(500, _("Annotation %s does not exist") % query['member2'])

                if rt not in helper.matching_relationtypes(objet, m1.type, m2.type):
                    return self.send_error(500, _("<p>Cannot create relation between %(member1)s and %(member2)s: invalid type</p>") % query)

                try:
                    relation=objet.createRelation(ident=id_,
                                                    members=(m1, m2),
                                                    type=rt)
                    objet._idgenerator.add(id_)
                    relation.content.data=data
                    objet.relations.append(relation)
                    self.controller.notify("RelationCreate", relation=relation)
                except Exception, e:
                    query['error']=unicode(e).encode('utf-8')
                    return self.send_error(500, _("<p>Error while creating relation between %(member1)s and %(member2)s :</p><pre>%(error)s</pre>") % query)
                if 'redirect' in query and query['redirect']:
                    return self.send_redirect(query['redirect'])
                return "".join( ( self.start_html(_("Relation created")),
                                  _("""<h1>Relation <em>%s</em> created</h1>""") % (relation.id)) )

            elif query['type'] == 'annotation':
                # Takes as parameters:
                # id = identifier (optional)
                # annotationtype = relation type identifier
                # begin, end = begin and end time (in ms)
                # data = content data (optional)
                at = context.evaluate("here/annotationTypes/%s" % query['annotationtype'])
                if at is None:
                    return self.send_error(500, _("Annotation type %s does not exist") % query['annotationtype'])
                try:
                    id_ = query['id']
                except KeyError:
                    id_ = objet._idgenerator.get_id(Annotation)
                try:
                    begin=long(query['begin'])
                    end=long(query['end'])
                    fragment=MillisecondFragment(begin=begin, end=end)
                    a=objet.createAnnotation(ident=id_, type=at, fragment=fragment)
                    objet._idgenerator.add(id_)
                    a.content.data = data
                    objet.annotations.append(a)
                    self.controller.notify("AnnotationCreate", annotation=a)
                except Exception, e:
                    t, v, tr = sys.exc_info()
                    import code
                    return self.send_error(500, _("""<p>Error while creating annotation of type %(type)s :<pre>
                    %(errortype)s
                    %(value)s
                    %(traceback)s</pre>""") % {
                            'type': query['annotationtype'],
                            'errortype': unicode(t),
                            'value': unicode(v),
                            'traceback': "\n".join(code.traceback.format_tb (tr))
                            })

                if 'redirect' in query and query['redirect']:
                    return self.send_redirect(query['redirect'])
                return self.start_html(_("Annotation %s created") % a.id)
            else:
                return self.send_error(500, _("Error: Cannot create an object of type %s.") % (query['type']))

        else:
            return self.send_error(500, _("Error: Cannot perform the action <em>%(action)s</em> on <code>%(object)s</code></p>") % { 'action': query['action'], 'object': cgi.escape(unicode(objet)) })

class Action(Common):
    """Handles the X{/action}  requests.

    The C{/action} folder allows to invoke the actions defined in
    the ECA framework (i.e. the same actions as the dynamic rules).

    Accessing the C{/action} folder itself displays the summary of
    available actions.
    """
    def index(self):
        catalog=self.controller.event_handler.catalog
        res=[ self.start_html(_("Available actions"), duplicate_title=True, mode='navigation') ]
        res.append("<ul>")
        d=dict(catalog.get_described_actions(expert=True).iteritems())
        k=d.keys()
        k.sort()
        for name in k:
            a=catalog.get_action(name)
            if a.parameters:
                # There are parameters. Display a link to the form.
                res.append(_("""<li>%(name)s: %(value)s""")
                                 % {'name': name,
                                    'value': d[name]})
                res.append(a.as_html("/action/%s" % name))
            else:
                # No parameter, we can directly link the action
                res.append("""<li><a href="%s">%s</a>: %s"""
                                 % ("/action/%s" % name,
                                    name,
                                    d[name]))
            res.append("</li>\n")
        res.append("</ul>")
        return "".join(res)
    index.exposed=True

    def default(self, *args, **query):
        action=args[0]
        catalog=self.controller.event_handler.catalog
        try:
            ra=catalog.get_action(action)
        except KeyError:
            return "".join((
                    self.start_html (_('Error'), duplicate_title=True),
                    _("""<p>Unknown action</p><pre>Action: %s</pre>""") % action
                    ))

        # Check for missing parameters
        missing=[]
        invalid=[]
        for p in ra.parameters:
            if not p in query:
                missing.append(p)
            elif not helper.is_valid_tales(query[p]):
                invalid.append(p)

        if missing:
            res=[ self.start_html (_('Error'), duplicate_title=True) ]
            res.append (_('Missing parameter(s) :<ul>'))
            for p in missing:
                res.append('<li>%s: %s</li>' % (p, ra.parameters[p]))
            return "".join(res)
        if invalid:
            res=[ self.start_html (_('Error'), duplicate_title=True) ]
            res.append (_('<p>Invalid parameter(s), they do not look like TALES expressions:</p><ul>'))
            for p in invalid:
                res.append('<li>%s (%s): %s</li>' % (p, ra.parameters[p], query[p]))
            return "".join(res)
        self.controller.queue_registered_action(ra, query)
        return self.send_no_content()
    default.exposed=True

class Root(Common):
    """Common methods for all web resources.

    URL syntax
    ==========

    The virtual tree served by this server has the following entry points :

      - C{/admin} : administrate the webserver
      - C{/packages} : access to packages
      - C{/media} : control the player
      - C{/action} : list and invoke Advene actions
      - C{/application} : control the application
    """
    def __init__(self, controller=None):
        self.controller=controller
        self.admin=Admin(controller)
        self.admin.access=Access(controller)
        self.action=Action(controller)
        self.application=Application(controller)
        self.media=Media(controller)
        self.packages=Packages(controller)

    def data(self, *p):
        """Placeholder for data static dir resource.

        data is handled by cherrypy.staticdir tool.
        """
        return _("Advene web resources")
    data.exposed=True

    def index(self):
        """Display the server root document.
        """
        res=[ self.start_html (_("Advene webserver"), duplicate_title=True, mode='navigation') ]
        res.append(_("""<p>Welcome on the <a href="http://liris.cnrs.fr/advene/">Advene</a> webserver run by %(userid)s on %(serveraddress)s.</p>""") %
                         {
                'userid': config.data.userid,
                'serveraddress': cherrypy.request.base,
                })

        if len(self.controller.packages) == 0:
            res.append(_(""" <p>No package is loaded. You can access the <a href="/admin">server administration page</a>.<p>"""))
        else:
            # It must be 2, since we always have a 'advene' key.  but
            # there could be some strange case where the advene key is
            # not present?
            if len(self.controller.packages) <= 2:
                alias='advene'
                p=self.controller.packages['advene']
                defaultview=p.getMetaData(config.data.namespace, 'default_utbv')
                if defaultview:
                    mes=_("""the <a href="/packages/%(alias)s/view/%(view)s">loaded package's default view</a>""") % {'alias': alias, 'view': defaultview}
                else:
                    mes=_("""the <a href="/packages/%s">loaded package's data</a>""") % alias
            else:
                mes=_("""the <a href="/packages">loaded packages' data</a>""")
            res.append(_(""" <p>You can either access %s or the <a href="/admin">server administration page</a>.<p>""") % mes)

        res.append(_("""<hr><p align="right"><em>Document generated by <a href="http://liris.cnrs.fr/advene/">Advene</a> v. %s.</em></p>""") % (advene.core.version.version))
        return "".join(res)
    index.exposed=True

class AdveneWebServer:
    """Embedded HTTP server for the Advene framework.

    This is an embedded HTTP Server dedicated to serving Advene
    packages content, and interacting with a media player.

    @ivar controller: the controller
    @type controller: advene.core.controller.Controller

    @ivar urlbase: the base URL for this server
    @type urlbase: string
    @ivar displaymode: the default display-mode
    @type displaymode: string
    @ivar authorized_hosts: the list of authorized hosts
    @type authorized_hosts: dict
    """
    def __init__(self, controller=None, port=1234):
        """HTTP Server initialization.

        When running embedded, the server should be provided a
        C{controller} parameter, responsible for handling package
        loading and player interaction.

        @param controller: the controller
        @type controller: advene.core.controller.Controller
        @param port: the port number the server should bind to
        @type port: int
        """
        self.controller=controller
        settings = {
            'global': {
                'server.socket_port' : port,
                #'server.socket_queue_size': 5,
                #'server.protocol_version': "HTTP/1.0",
                'log.screen': False,
                'log.access_file': config.data.advenefile('webserver.log', 'settings'),
                'log.error_file': config.data.advenefile('webserver-error.log', 'settings'),
                'server.reverse_dns': False,
                'server.thread_pool': 10,
                'engine.autoreload_on': False,
                #'server.environment': "development",
                'server.environment': "production",
                },
            #    '/admin': {
            #        'session_authenticate_filter.on' :True
            #        },
            }
        cherrypy.config.update(settings)

        self.displaymode = config.data.webserver['displaymode']

        # Not used for the moment.
        self.authorized_hosts = {'127.0.0.1': 'localhost'}

        self.urlbase = u"http://localhost:%d/" % port

        app_config={
            '/favicon.ico': {
                'tools.staticfile.on': True,
                'tools.staticfile.filename': config.data.advenefile( ( 'pixmaps', 'advene.ico' ) ),
                },
            '/data': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': config.data.path['web'],
                },
            }
        cherrypy.tree.mount(Root(controller), config=app_config)

        try:
            # server.quickstart *must* be started from the main thread.
            cherrypy.server.quickstart()
        except Exception, e:
            self.controller.log(_("Cannot start HTTP server: %s") % unicode(e))

    def start(self):
        """Start the webserver.
        """
        self.controller.queue_action(cherrypy.engine.start, False)
        return True

    def stop(self):
        """Stop the webserver.
        """
        cherrypy.engine.stop()
        cherrypy.server.stop()
