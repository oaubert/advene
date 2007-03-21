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
"""Advene http server.

This module is composed of two classes : L{AdveneWebServer} is the
main server class, L{AdveneRequestHandler} is dedicated to request
handling.

URL syntax
==========

  The URL syntax is described in L{AdveneRequestHandler}.

  The server can run standalone or embedded in another application
  (typically the C{advene} GUI).  In all cases, Webserver depends on
  AdveneController.

  It is the responsibility of the embedding application to handle
  incoming requests to server.fileno() (typically through a
  gobject.io_input_add()). See the L{AdveneWebServer.__init__}
  documentation for more details.
"""

import advene.core.config as config
import advene.core.version

from gettext import gettext as _

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.fragment import MillisecondFragment
from advene.model.exception import AdveneException

import advene.model.tal.context
import simpletal.simpleTAL
import simpletal.simpleTALES as simpleTALES

import sys
import os
import sre
import urlparse
import urllib
import cgi
import socket
import select
import mimetypes
import logging

import imghdr

import advene.util.helper as helper

import SocketServer
import BaseHTTPServer

class AdveneRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    """RequestHandler for the AdveneServer.

    URL syntax
    ==========

    The virtual tree served by this server has the following entry points :

      - C{/admin} : the administration folder
      - C{/debug} : the debug path
      - C{/packages} : the packages folder
      - C{/media} : the I{media} control folder


    The requests are handled through this class. The main methods are:

      - L{do_GET} : handles C{GET} requests.
      - L{do_POST} : handles C{POST} requests.
      - L{do_PROPFIND} : handles C{PROPFIND} requests (to be implemented correctly...)

    More specific methods are then called :

      - L{do_GET_admin} : handles requests for the C{/admin} folder.
      - L{do_GET_element} : handles requests for the C{/packages} folder.
    """

    def location_bar (self):
        """Returns a string representing the active location bar.

        This method will use the current URL path, and return an HTML string
        where the different components of the path are linked to their URL.

        @return: a HTML string
        @rtype: string
        """
        s = urllib.splittag(
            urllib.splitquery(self.path)[0]
            )[0]
        path = s.split('/')[1:]
        return """<a href="/">/</a>""" + "/".join(
            ["""<a href="%s">%s</a>"""
             % (uri, name)
             for (name, uri) in zip(path,
                                    ["/"+"/".join(path[:i+1])
                                     for i in range(len(path))])]
            )

    def log_message(self, format, *args):
        self.server.logger.info("%s %s" % (self.address_string(), format % args))

    def no_cache (self):
        """Write the cache-control headers in the response.

        This method sends cache-control headers to ensure that the
        browser does not cache the response, as it may vary from one
        call to another.

        @return: nothing
        """
        self.send_header ('Pragma', 'no-cache')
        self.send_header ('Cache-Control', 'max-age=0')

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
        self.send_response (200)
        if mode == 'navigation':
            mimetype='text/html'
        if mimetype is None or mimetype == 'text/html':
            mimetype='text/html; charset=utf-8'
        self.send_header ('Content-type', mimetype)
        if headers is not None:
            for h in headers:
                self.send_header(h[0], h[1])
        if not cache:
            self.no_cache ()
        self.end_headers ()

        if mode == "navigation":
            self.wfile.write("<html><head><title>%s</title>" % title)
            if head_section is not None:
                self.wfile.write(head_section)

            self.wfile.write("</head><body %s>" % body_attributes)

            self.wfile.write (_("""
            <p>
            <a href="/admin">Server administration</a> |
            <a href="/admin/status">Server status</a> |
            <a href="/media">Media control</a> |
            <a href="%(path)s?mode=raw">Raw view</a>
            </p>
            Location: %(locationbar)s
            <hr>
            """) % { 'locationbar': self.location_bar (),
                     'path': self.path})

        if duplicate_title and mode == 'navigation':
            self.wfile.write("<h1>%s</h1>\n" % title)

    def send_no_content(self):
        """Sends a No Content (204) response.

        Mainly used in /media handling.
        """
        self.send_response (204)
        self.no_cache ()
        self.end_headers ()

    def send_redirect (self, location):
        """Sends a redirect response.

        As this method generates headers, it must be called before other
        headers or content.

        @param location: the URL to redirect to.
        @type location: string (URL)
        """
        self.send_response (301)
        self.no_cache ()
        self.send_header ("Location", location)
        self.send_header ('Content-type', 'text/html; charset=utf-8')
        self.end_headers ()
        self.wfile.write (_("""
        <html><head><title>Redirect to %(location)s</title>
        </head><body>
        <p>You should be redirected to %(location)s</p>
        </body></html>
        """) % {'location':location})

    def query2dict (self, q):
        """Converts a query string to a dictionary.

        This method converts a query string (C{attr1=val1&attr2=val2...}) into
        a dictionary with keys and values unquoted.

        @param q: the query string
        @type q: string
        @return: a dictionary with (keys, values) taken from C{q}
        @rtype: dictionary
        """
        if q == "":
            return {}
	res={}
	for k, v in cgi.parse_qsl(q):
	    # Implicit conversion of parameters. We try utf-8 first.
	    # That will work only if it is ascii or utf-8.
	    # If it fails, the most frequent case is latin1
	    try:
		v=unicode(v, 'utf-8')
	    except UnicodeDecodeError:
		v=unicode(v, 'latin1')
	    res[k]=v
	return res

    def display_media_status (self):
        """Display current media status.

        This method is called from another embedding method (which
        will generate the appropriate headers). It displays the current
        status of the media player.
        """
        if self.server.controller.player == None:
            self.wfile.write (_("""<h1>No available mediaplayer</h1>"""))
        else:
            l = self.server.controller.player.playlist_get_list ()
            self.server.controller.update_status ()
            self.wfile.write (_("""
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
                    'currentstbv': str(self.server.controller.current_stbv),
                    'position': helper.format_time(self.server.controller.player.current_position_value),
                    'duration': helper.format_time(self.server.controller.player.stream_duration),
                    'status': repr(self.server.controller.player.status)
                    })

            if len(l) == 0:
                self.wfile.write (_("""<h1>No playlist</h1>"""))
            else:
                self.wfile.write (_("""<h1>Current playlist</h1>
                <ul>%s</ul>""") % ("\n<li>".join (l)))
                self.wfile.write (_("""
                <form action="/media/play" method="GET">
                Starting pos: <input type="text" name="position" value="0">
                <input type="submit" value="Play">
                </form>
                <a href="/media/stop">Stop</a> | <a href="/media/pause">Pause</a><br>
                """))
            self.wfile.write (_("""<hr />
            <form action="/media/load" method="GET">
            Add a new file (<em>dvd</em> to play a DVD):
            <input type="text" name="filename">
            <input type="submit" value="Add">
            </form>"""))
        self.wfile.write (_("""<h3><a href="/media/snapshot">Access to current packages snapshots</h3>"""))

    def activate_stbvid(self, stbvid):
        stbv=helper.get_id(self.server.controller.package.views, stbvid)
        if stbv is None:
            self.send_error(404, _('Unknown STBV identifier: %s') % stbvid)
            return
        self.server.controller.activate_stbv(view=stbv)
        return

    def handle_media (self, l, query):
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

          Accessing a specific snapshot can be done in two ways:
            - Suffixing the URL with the snapshot index
            - Providing the snapshot index as the option C{position}

          The following paths are thus equivalent::

            /media/snapshot/package_alias/12321
            /media/snapshot/package_alias?position=12321


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

        @param l: the access path as a list of elements,
                  with the initial one (C{media}) omitted
        @type l: list
        @param query: the options given in the URL
        @type query: dict

        """
        if len(l) == 0:
            # Display media information
            self.start_html (_('Media information'))
            self.display_media_status ()
        else:
            command = l[0]
            param = l[1:]
            if query.has_key('stbv'):
                self.activate_stbvid(query['stbv'])
            if command == 'load':
                if query.has_key ('filename'):
                    name = urllib.unquote(query['filename'])
                    if name == 'dvd':
                        name = self.server.controller.player.dvd_uri(1,1)
                    try:
                        if isinstance(name, unicode):
                            name=name.encode('utf8')
                        self.server.controller.queue_action(self.server.controller.player.playlist_add_item, name)
                        self.server.controller.notify("MediaChange", uri=name)

                        self.start_html (_("File added"))
                        self.wfile.write (_("""<p><strong>%s has been added to the playlist</strong></p>""") % name)
                        self.display_media_status ()
                    except:
                        self.wfile.write (_("""<p><strong>Error: cannot add %s to the playlist.</strong></p>""") % name)
                else:
                    self.display_media_status ()
            elif command == 'snapshot':
                # snapshot syntax:
                # /media/snapshot/package_alias?position=#
                # or
                # /media/snapshot/package_alias/#
                if len(param) == 0:
                    self.start_html (_("Access to packages snapshots"), duplicate_title=True)
                    self.wfile.write ("<ul>")
                    for alias in self.server.controller.packages.keys ():
                        self.wfile.write ("""<li><a href="/media/snapshot/%s">%s</a></li>""" % (alias, alias))
                    self.wfile.write("</ul>")
                    return
                alias = param[0]
                i = self.server.controller.packages[alias].imagecache

                if not query.has_key ('position') and len(param) < 2:
                    self.start_html (_("Available snapshots for %s") % alias, duplicate_title=True)
                    self.wfile.write ("<ul>")
                    if (query.has_key('mode') and query['mode'] == 'inline'):
                        template="""<li><a href="/media/snapshot/%(alias)s/%(position)d"><img src="/media/snapshot/%(alias)s/%(position)d" /></a></li>"""
                        self.wfile.write ("""<p><a href="/media/snapshot/%s">Display with no inline images</a></p>""" % alias)
                    else:
                        template="""<li><a href="/media/snapshot/%(alias)s/%(position)d">%(position)d</a> (%(status)s)</li>"""
                        self.wfile.write (_("""<p><a href="/media/snapshot/%s?mode=inline">Display with inline images</a></p>""") % alias)

                    k = i.keys ()
                    k.sort ()
                    for position in k:
                        if i.is_initialized (position):
                            m = _("Done")
                        else:
                            m = _("Pending")
                        self.wfile.write (template % { 'alias': alias,
                                                       'position': position,
                                                       'status': m })
                    self.wfile.write ("</ul>")
                    return
                else:
                    if query.has_key ('position'):
                        position = long(query['position'])
                    else:
                        position = long(param[1])
                self.send_response (200)
                if not i.is_initialized (position):
                    self.no_cache ()
                self.send_header ('Content-type', 'image/png')
                self.end_headers ()
                self.wfile.write (i[position])
            elif command == 'play':
                if query.has_key ('filename'):
                    f=query['filename']
                    if isinstance(f, unicode):
                        f=f.encode('utf8')
		    self.server.controller.queue_action(self.server.controller.player.playlist_clear, f)
		    self.server.controller.queue_action(self.server.controller.player.playlist_add_item, f)
		    self.server.controller.notify("MediaChange", uri=f)

                if len(param) != 0:
                    # First parameter is the position
                    position = param[0]
                elif query.has_key ('position'):
                    position = query['position']
                else:
                    position = 0

		if not self.server.controller.player.playlist_get_list():
		    self.send_no_content()
		    return
                if self.server.controller.player.status != self.server.controller.player.PlayingStatus:
		    self.server.controller.queue_action( self.server.controller.update_status, "start", long(position) )
		else:
		    self.server.controller.queue_action( self.server.controller.update_status, "set", long(position) )
                self.send_no_content()
            elif command in ('pause', 'stop', 'resume'):
                self.server.controller.update_status (command)
                self.send_no_content()
            elif command == 'current':
                self.send_response (200)
                self.send_header ('Content-type', 'text/plain')                
                self.end_headers ()
                l=self.server.controller.player.playlist_get_list()
                if l:
                    self.wfile.write (l[0])
                else:
                    self.wfile.write('N/C')
            elif command == 'stbv':
                if len(param) != 0:
                    stbvid=param[0]
                elif query.has_key ('id'):
                    stbvid=query['id']
                else:
                    self.send_error (404, _('Malformed request'))
                    return
                self.activate_stbvid(stbvid)
                #self.server.controller.update_status("play", 0)
                self.send_no_content()

    def handle_application (self, l, query):
        """Handles X{/application} access requests.

        Tree organization
        =================

        The C{/application} folder gives the ability to acces the application (GUI).

        The elements available in this folder are :

          - C{/application/stbv}
          - C{/application/adhoc}

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
          C{edit}.

          The transcription view can take an optional C{type}
          parameter, either as next element in the URI or as a
          C{type=...} parameter. To open the transcription view on the
          annotation-type simple_text, you can simply use:
          C{/application/adhoc/transcription/simple_text}

          The transcribe view takes a mandatory C{url} parameter.

          The edit view takes a mandatory C{id} parameter, which is
          the id of the element to be edited.
        """
        def current_adhoc():
            if not c.gui:
                self.wfile.write(_("""<p>No GUI is available."""))
            else:
                self.wfile.write(_("""<p>Current adhoc views: %s</p>""") % ", ".join([ v.view_name for v in c.gui.adhoc_views]))
                self.wfile.write(_("""<p>You can open a new <a href="/application/adhoc/tree">tree view</a>, a new <a href="/application/adhoc/timeline">timeline</a> or a new <a href="/application/adhoc/transcription">transcription</a>.</p>"""))

        def current_stbv():
            self.wfile.write(_("""<p>Current stbv: %s</p>""") % c.get_title(c.current_stbv))
            self.wfile.write(_("""<p>You can activate the following STBV:</p><ul>%s</ul>""")
                             % "\n".join( [ """<li><a href="/application/stbv/%s">%s</a> (<a href="/media/play/0?stbv=%s">Activate and play</a>)</li>""" %
                                            (s.id, c.get_title(s), s.id)
                                            for s in c.get_stbv_list() ] ) )

        c=self.server.controller
        if len(l) == 0:
            # Display media information
            self.start_html (_('Application information'))
            current_stbv()
            current_adhoc()
            return
        else:
            command = l[0]
            param = l[1:]
            if command == 'stbv':
                if len(param) != 0:
                    stbvid=param[0]
                elif query.has_key ('id'):
                    stbvid=query['id']
                else:
                    self.start_html (_('Application information'))
                    current_stbv()
                    return
                self.activate_stbvid(stbvid)
                #self.server.controller.update_status("play", 0)
                self.send_redirect("/application/stbv")
            elif command == 'adhoc':
                view=None
                if len(param) != 0:
                    view=param[0]
                if view is None or c.gui is None:
                    current_adhoc()
                    return
                if view in ('tree', 'timeline', 'browser'):
                    c.queue_action(c.gui.open_adhoc_view, view)
                    self.send_no_content()
                elif view == 'transcription':
                    atid=None
                    if len(param) > 1:
                        atid=param[1]
                    elif query.has_key('type'):
                        atid=query['type']

                    if atid is not None:
                        source="here/annotationTypes/%s/annotations/sorted" % atid
                    else:
                        # Maybe there was a source parameter ?
                        try:
                            source=query['source']
                        except:
                            # No provided source. Use the whole package
                            source="here/annotations/sorted"
                    c.queue_action(c.gui.open_adhoc_view, view, source=source)
                    self.send_no_content()
                elif view == 'transcribe':
                    url=None
                    if query.has_key('url'):
                        url=query['url']
                    c.queue_action(c.gui.open_adhoc_view, view, filename=url)
                    self.send_no_content()
                elif view == 'edit':
                    elid=None
                    if len(param) > 1:
                        elid=param[1]
                    elif query.has_key('id'):
                        elid=query['id']

                    if elid is None:
                        self.send_error(404, _("Missing element id parameter"))
                        return
                    el=c.package.get_element_by_id(elid)
                    if el is None:
                        self.send_error(404, _("No existing element with id %s") % elid)
                        return
                    c.queue_action(c.gui.open_adhoc_view, view, element=el)
                    self.send_no_content()
                else:
                    self.start_html (_('Error'))
                    self.wfile.write(_("""<p>The GUI view %s does not exist.</p>""") % view)
        return

    def handle_access (self, l, query):
        """Displays the access control menu.

        Access Control
        ==============

        Access control is available in the AdveneServer through the
        path X{/admin/access}. By default, only the localhost (IP
        address 127.0.0.1) is allowed to access the server. The user
        can add or delete hosts from the access list, but the
        localhost can never be removed from the access list.

        The addition or removal of a computer is done by providing the
        C{hostname} and C{action} options :

          - C{hostname} specifies the hostname that should be added or
            removed
          - C{action} is either C{add} or C{del}

        If no options are given, the current access control list is
        displayed.

        @param l: the access path as a list of elements,
                  with the initial one (C{access}) omitted
        @type l: list
        @param query: the options given in the URL
        @type query: dict
        """
        self.start_html (_('Access control'), duplicate_title=True)

        ip=None
        if query.has_key('hostname'):
            if query['hostname'] == '*':
                ip='*'
            else:
                try:
                    ip = socket.gethostbyname (query['hostname'])
                except:
                    self.wfile.write (_("""<strong>Error: %s is an invalid hostname.</strong>""") % query['hostname'])
            if ip is not None:
                if query.has_key("action") and query['action'] == 'del':
                    # Remove the hostname
                    if ip in self.server.authorized_hosts:
                        del self.server.authorized_hosts[ip]
                        self.wfile.write (_("""<p>Removed %s from authorized hosts list.</p>""") % query['hostname'])
                    else:
                        self.wfile.write (_("""<p>Cannot remove %s from authorized hosts list.</p>""") % query['hostname'])
                else:
                    # Add it to the ACL
                    self.server.authorized_hosts[ip] = query['hostname']
                    self.wfile.write (_("""<p>Added %s to authorized hosts list.</p>""") % query['hostname'])

        self.wfile.write (_("""
        <h1>Authorized hosts</h1>
        <table border="1">
        <tr><th>Host</th><th>IP Addr</th><th>Action</th></tr>
        %s
        </table>
        <form method="GET">
        Add a new hostname to the list :<br>
        <input type="text" name="hostname"><input type="submit" value="Add">
        </form>
        """) % "\n".join(["""<tr><td>%s</td><td>%s</td><td><a href="/admin/access?hostname=%s&action=del">Remove</a></td></tr>""" % (ip, name, name)
                         for (name, ip) in self.server.authorized_hosts.items()]))
        return

    def display_summary (self):
        """Display the main administration page.

        This method displays the root document of the server, which
        should link to all functionalities."""

        self.start_html (_("Server Administration"), duplicate_title=True)
        if self.server.displaymode == 'raw':
            switch='navigation'
        else:
            switch='raw'
        mode_sw="""%s (<a href="/admin/display/%s">switch to %s</a>)""" % (
            self.server.displaymode, switch, switch)

        self.wfile.write(_("""
        <p><a href="/admin/status">Display the server status</a></p>
        <p><a href="/admin/access">Update the access list</a></p>
        <p><a href="/admin/methods">List available TALES methods</a></p>
        <p><a href="/action">List available actions</a></p>
        <p><a href="/admin/reset">Reset the server</a></p>
        <p><a href="/admin/halt">Halt the server</a></p>
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
                                             for alias in self.server.controller.packages.keys() ] ),
                 'displaymode': mode_sw })

    def display_packages_list (self):
        """Display available Advene files.

        This method displays the data files in the data directory.
        Maybe it should be removed when the server runs embedded.
        """
        self.start_html (_("Available files"), duplicate_title=True)
        self.wfile.write ("<ul>")

        l=[ os.path.join(config.data.path['data'], n)
            for n in os.listdir(config.data.path['data'])
            if n.lower().endswith('.xml') or n.lower().endswith('.azp') ]
        for uri in l:
            name, ext = os.path.splitext(uri)
            alias = sre.sub('[^a-zA-Z0-9_]', '_', os.path.basename(name))
            self.wfile.write ("""
            <li><a href="/admin/load?alias=%(alias)s&uri=%(uri)s">%(uri)s</a></li>
            """ % {'alias':alias, 'uri':uri})
        self.wfile.write ("""
        </ul>
        """)

    def display_loaded_packages (self, embedded=False):
        """Display currently available (loaded) packages.

        This method displays the list of currently loaded
        packages. The generated list provides links for accessing,
        reloading, saving or removing the package.

        @param embedded: Specify wether the list is embedded in
                         another document or not. In the latter case,
                         the headers will be generated.
        @type embedded: boolean
        """
        if not embedded:
            self.start_html (_("Loaded package(s)"))

        self.wfile.write (_("""
        <h1>Loaded package(s)</h1>
        <table border="1" width="50%">
        <tr>
        <th>Alias</th>
        <th>Action</th>
        <th>URI</th>
        <th>Annotations</th>
        </tr>
        """))
        for alias in self.server.controller.packages.keys():
            p = self.server.controller.packages[alias]
            self.wfile.write (_("""<tr>
            <td><a href="/packages/%(alias)s">%(alias)s</a></td>
            <td align="center"><a href="/admin/load?alias=%(alias)s&uri=%(uri)s">Reload</a>|<a href="/admin/delete?alias=%(alias)s">Drop</a>|<a href="/admin/save?alias=%(alias)s">Save</a></td>
            <td>%(uri)s</td>
            <td>%(size)d</td>
            </tr>
            """) % { 'alias':alias, 'uri':p.uri, 'size':len(p.annotations) })
        self.wfile.write ("""
        </ul>
        """)

    def do_PUT(self):
        """Handle PUT requests (update or create).

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
        (scheme,
         netloc,
         stringpath,
         params,
         stringquery,
         fragment) = urlparse.urlparse (self.path)

        stringpath = stringpath.replace ('%3A', ':')
        query = self.query2dict (stringquery)

        print "Handling PUT request for %s" % stringpath

        # A trailing / would give an empty last value in the path
        path = stringpath.split('/')[1:]

        if path[-1] == '':
            del (path[-1])

        if len(path) < 2:
            self.send_error(501, _("<h1>Error</h1>") +
                            _("<p>Cannot set the value : invalid path</p>"))
            return
        elif path[0] == 'packages':
            alias = path[1]
            # FIXME: we could try to resolve to the -2 element only, and use
            # the -1 as attribute name, which should be more flexible
            tales = "/".join (path[2:])
            if tales == "":
                expr = "here"
            else:
                expr = "here/%s" % tales

            context = self.server.controller.build_context(here=self.server.controller.packages[alias],
                                                           alias=alias)
            context.pushLocals()
            context.setLocal('request', query)

            try:
                objet = context.evaluateValue (expr)
            except AdveneException, e:
                self.send_error(501, _("<h1>Error</h1>") + unicode(e.args[0]).encode('utf-8'))
                return

            # We can update only data attributes
            if hasattr(objet, 'data'):
                objet.__setattr__('data', self.rfile.read (long(self.headers['content-length'])))
                self.send_response(200, _("Value successfuly updated"))
                self.end_headers()
                return
            else:
                self.send_response(501, _("Unable to update this value."))
                self.end_headers()
                return
        else:
            self.send_response(501, _("Unable to update this value."))
            self.end_headers()
            return

    def do_POST(self):
        """Handles POST requests (update or create).

        The C{POST} requests are used to update or create elements in
        a package. Only a limited set of elements are accessible in
        this way.

        Manipulating package data
        =========================

        The package data can be manipulated in this way. The
        appropriate action is specified through the C{action}
        parameter, which can be either C{update}, C{create} or
        C{delete}.

        Updating data
        =============

        The update of an element of the object addressed by the POSTed
        URL is done by giving the name of the object attribute that we
        want to update, as the value of the C{key} parameter.

        If an additional C{object} parameter is given, it indicates
        that the object is a list, and that we should access one of
        its elements named by C{object}.

        For instance, the update of the content of the view C{foo} in
        the package C{bar} can be done through the following form::

          <form method="POST" action="/packages/bar/views/foo">
          <textarea name="data">Contents</textarea>
          <input type="hidden" name="key" value="contentData">
          <input type="hidden" name="action" value="update">
          <input type="submit" value="Submit" />
          </form>

        Creating new data
        =================

        The creation of new elements in a package is done by
        specifying the C{action=create} parameter.

        The type of the created object is given through the C{type}
        parameter. For the moment, C{view}, C{annotationtype} and
        C{relationtype} are valid.

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

        #self.start_html (_("Setting value"))

        (scheme,
         netloc,
         stringpath,
         params,
         stringquery,
         fragment) = urlparse.urlparse (self.path)

        stringpath = stringpath.replace ('%3A', ':')
        pathquery = self.query2dict (stringquery)

        # A trailing / would give an empty last value in the path
        path = stringpath.split('/')[1:]

        if path[-1] == '':
            del (path[-1])

        if len(path) < 2:
            self.wfile.write (_("<h1>Error</h1>"))
            self.wfile.write(_("<p>Cannot set the value : invalid path</p>"))
            return

        if path[0] == 'packages':
            alias = path[1]
            query = self.query2dict(self.rfile.read (long(self.headers['content-length'])))
            tales = "/".join (path[2:])
            if tales == "":
                expr = "here"
            else:
                expr = "here/%s" % tales

            package = self.server.controller.packages[alias]
            context = self.server.controller.build_context(here=package,
                                                           alias=alias)
            context.pushLocals()
            context.setLocal('request', query)

            try:
                objet = context.evaluateValue (expr)
            except AdveneException, e:
                self.start_html (_("Error"), duplicate_title=True)
                self.wfile.write (unicode(e.args[0]).encode('utf-8'))
                return

            if not query.has_key('action') or not query.has_key('data'):
                self.start_html (_("Error"), duplicate_title=True)
                self.wfile.write (_("<p>Invalid request</p>."))
                return

            def answer(message):
                if query.has_key('redirect') and query['redirect']:
                    self.send_redirect(query['redirect'])
                    self.wfile.write("<html><head><title>%s</title></head><body>" % message)
                else:
                    self.start_html(message)

            # Different actions : update, create, delete
            if query['action'] == 'update':
                if hasattr(objet, query['key']):
                    objet.__setattr__(query['key'], query['data'])
                    answer(_("Value updated"))
                    self.wfile.write (_("""
                    <h1>Value updated</h1>
                    The value of %(path)s has been updated to
                    <pre>
                    %(value)s
                    </pre>
                    """) % { 'path': "/".join([tales, query['key']]),
                             'value': cgi.escape(query['data']) })
                else:
                    # Fallback mode : maybe we were in a list, and
                    # query['object'] has the id of the object in the list
                    try:
                        o = objet[query['object']]
                        if hasattr(o, query['key']):
                            o.__setattr__(query['key'], query['data'])
                            answer(_("Value updated"))
                            self.wfile.write (_("""
                            <h1>Value updated</h1>
                            The value of %(path)s has been updated to
                            <pre>
                            %(value)s
                            </pre>
                            """) % { 'path': "/".join([tales,
                                                       query['object'],
                                                       query['key']]),
                                     'value': cgi.escape(query['data']) })
                            return
                    except:
                        pass
                    self.wfile.write ("""
                    <h1>Error</h1>
                    <p>The object %s has no key %s.</p>
                    """ % (tales, query['key']))
            elif query['action'] == 'create':
                 # Create a new element. For the moment, only
                 # View, Relation, Annotation is supported
                 if not isinstance (objet, Package):
                     answer(_("Error"))
                     self.wfile.write (_("""
                     <h1>Error</h1>
                     <p>Cannot create an element in something else than a package.</p>
                     """))
                 elif query['type'] == 'view':
                     try:
                         v = objet.createView (ident=query['id'],
                                               clazz=query['class'],
                                               content_data=query['data'])
                         objet.views.append(v)
                     except Exception, e:
                         answer(_("<h1>Error</h1>"))
                         self.wfile.write (_("<p>Error while creating view %s</p>")
                                           % query['id'])
                         self.wfile.write("""
                         <pre>
                         %s
                         </pre>
                         """ % (unicode(e)))
                         return

                     answer(_("View created"))
                     self.wfile.write (_("""
                     <h1>View <em>%(id)s</em> created</h1>
                     <p>The view <a href="%(url)s">%(id)s</a> was successfully created.</p>
                     """) % { 'id': v.id,
                              'url': "/packages/%s/views/%s" % (self.server.controller.aliases[objet],
                                                                v.id) })
                 elif query['type'] == 'relation':
                     # Takes as parameters:
                     # id = identifier (optional)
                     # relationtype = relation type identifier
                     # member1 = first member (annotation id)
                     # member2 = second member (annotation id)
                     # data = content data (optional)
                     rt = context.evaluateValue("package/relationTypes/%s" % query['relationtype'])
                     try:
                         id_ = query['id']
                     except KeyError:
                         id_ = package._idgenerator.get_id(Relation)
                     m1 = context.evaluateValue('package/annotations/%s' % query['member1'])
                     m2 = context.evaluateValue('package/annotations/%s' % query['member2'])

                     relationtypes=helper.matching_relationtypes(package, m1, m2)
                     if rt not in relationtypes:
                         answer(_("Error"))
                         self.wfile.write (_("<h1>Error</h1>"))
                         self.wfile.write (_("<p>Cannot create relation between %(member1)s and %(member2)s: invalid type</p>") % query)
                         return
                     try:
                         relation=package.createRelation(ident=id_,
                                                         members=(m1, m2),
                                                         type=rt)
                         package._idgenerator.add(id_)
                         package.relations.append(relation)
                         self.server.controller.notify("RelationCreate", relation=relation)
                     except Exception, e:
                         answer(_("Error"))
                         self.wfile.write (_("<h1>Error</h1>"))
                         query['error']=unicode(e)
                         self.wfile.write (_("<p>Error while creating relation between %(member1)s and %(member2)s :</p><pre>%(error)s</pre>") % query)
                         return
                     answer(_("Relation created"))
                     self.wfile.write (_("""
                     <h1>Relation <em>%s</em> created</h1>
                     """) % (relation.id))
                 elif query['type'] == 'annotation':
                     # Takes as parameters:
                     # id = identifier (optional)
                     # annotationtype = relation type identifier
                     # begin, end = begin and end time (in ms)
                     # data = content data (optional)
                     at = context.evaluateValue("package/annotationTypes/%s" % query['annotationtype'])
                     try:
                         id_ = query['id']
                     except KeyError:
                         id_ = package._idgenerator.get_id(Annotation)
                     try:
                         begin=long(query['begin'])
                         end=long(query['end'])
                         fragment=MillisecondFragment(begin=begin,
                                                      end=end)
                         a=package.createAnnotation(ident=id_,
                                                    type=at,
                                                    fragment=fragment)
                         package._idgenerator.add(id_)
                         try:
                             a.content.data = query['data']
                         except KeyError:
                             a.content.data = "Annotation %s" % id_
                         package.annotations.append(a)
                         self.server.controller.notify("AnnotationCreate", annotation=a)
                     except Exception, e:
                         t, v, tr = sys.exc_info()
                         answer(_("Error"))
                         self.wfile.write (_("<h1>Error</h1>"))
                         self.wfile.write (_("<p>Error while creating annotation of type %s :") % query['annotationtype'])
                         import code
                         self.wfile.write(_("""<pre>
                         %(type)s
                         %(value)s
                         %(traceback)s</pre>""") % {
                                 'type': unicode(t), 
                                 'value': unicode(v), 
                                 'traceback': "\n".join(code.traceback.format_tb (tr))
                                 })
                         return

                     answer(_("Annotation created"))
                     self.wfile.write (_("""
                     <h1>Annotation <em>%s</em> created</h1>
                     """) % (a.id))
                 else:
                     answer(_("Error"))
                     self.wfile.write (_("<h1>Error</h1>"))
                     self.wfile.write (_("<p>Cannot create an object of type %s.</p>") % (query['type']))
            else:
                answer(_("Error"))
                self.wfile.write (_("<h1>Error</h1>"))
                self.wfile.write (_("<p>Cannot perform the action <em>%(action)s</em> on <code>%(object)s</code></p>")
                                  % { 'action': query['action'], 
                                      'object': cgi.escape(unicode(objet)) })
        elif path[0] == 'config':
            if len(path) == 2:
                # We have a config value to set
                query = self.query2dict(self.rfile.read (long(self.headers['content-length'])))
                name=path[1]
                config.data.web[name]=query['data']
                self.send_response(200, _("Value of %s successfuly updated") % name)
                self.end_headers()
                return
            else:
                self.wfile.write (_("<h1>Error</h1>"))
                self.wfile.write (_("<p>Cannot perform the action <em>%(action)s</em> on <code>%(object)s</code></p>")
                                  % { 'action': query['action'], 
                                      'object': cgi.escape(unicode(objet)) } )


    def do_GET(self):
        """Handle GET requests.

        This method dispatches GET requests to the corresponding methods :

          - L{do_GET_element} for C{/package} elements access
          - L{do_GET_admin} for C{/admin} folder access
          - L{do_GET_action} for C{/action} folder access
          - L{do_GET_debug} for C{/debug} access
          - L{handle_media} for C{/media} access

        URL handling
        ============

        The URL is first split in components, and some parameters may
        modify the interpretation of the path.

        The C{path} parameter is used to interactively modifying the
        path (through a form).

        If the C{path} parameters starts with the string C{eval:}, it
        will be considered as a python expression to be evaluated, and all
        other URL components will be ignored. The evaluation is done in the
        L{do_eval} method.

        Else, the C{path} value will be appended to the current path
        of the URL, and the browser is redirected to this new location.

        The C{view} parameter is a shortcut for rapidly accessing an
        element view. Its value is in fact the URL displaying the
        correct view, and the browser is redirected.
        """
        (scheme, netloc, stringpath, params, stringquery, fragment) = urlparse.urlparse (self.path)
        stringpath = stringpath.replace ('%3A', ':')
        # Strip trailing /
        if stringpath.endswith('/'):
            stringpath=stringpath[:-1]
        path = stringpath.split('/')[1:]
        query = self.query2dict (stringquery)

        # The eval: syntax has precedence over all other invocations
        # FIXME: it is for debug only and should be used with caution
        # Syntax: http://localhost:1234/?path=eval:dir()
        if query.has_key('path') and query['path'].startswith ('eval:'):
            q=query['path'][5:]
            self.do_eval (q)
            return

        # If the submit was done automatically on "path" modification,
        # the view field will exist but be empty, so delete it
        if query.has_key('view') and query['view'] == '':
            del(query['view'])

        if query.has_key('view'):
            # If we specify a view, we do not want to take the
            # 'path' parameter into account
            try:
                del query['path']
                # And anyway, the 'view' parameter is in fact the new path
                # that we should be redirected to
                self.send_redirect (query['view'])
            except:
                pass

        if query.has_key('path'):
            stringpath = stringpath + "/" + query['path']
            if query['path'].find ('..') != -1:
                stringpath = os.path.normpath (stringpath)
            del(query['path'])
            if len(query) == 0:
                location = stringpath
            else:
                location = "%s?%s" % (stringpath,
                                      "&".join (["%s=%s" % (k,query[k])
                                                 for k in query.keys()]))
            self.send_redirect (location)
            return

        if not path:
            self.display_server_root()
            return

        command = path[0]
        parameters = path[1:]

        if command == '':
            self.display_server_root ()
        elif command == 'packages':
            self.do_GET_element(parameters, query)
        elif command == 'admin':
            self.do_GET_admin (parameters, query)
        elif command == 'action':
            self.do_GET_action (parameters, query)
        elif command == 'media':
            self.handle_media (parameters, query)
        elif command == 'application':
            self.handle_application (parameters, query)
        elif command == 'data':
            self.do_GET_data(parameters, query)
        elif command == 'debug':
            self.do_GET_debug ()
        elif command == 'favicon.ico':
            self.do_GET_favicon()
        else:
            self.send_error(404,
                            _("""<p>Unknown request: %s</p>""")
                            % self.path)

    def do_GET_element (self, parameters, query):
        if len(parameters) == 0:
            self.display_loaded_packages ()
            return
        else:
            pkgid = parameters[0]
        try:
            p = self.server.controller.packages[pkgid]
        except:
            self.send_error (501, _("<p>Package <strong>%s</strong> not loaded</p>")
                             % pkgid)
            return

        try:
            t = "/".join (parameters[1:])
            self.display_package_element (p , t, query)
        except simpletal.simpleTAL.TemplateParseException, e:
            self.wfile.write(_("<h1>Error</h1>"))
            self.wfile.write(_("""<p>There was an error in the template code.</p>
            <p>Tag name: <strong>%(tagname)s</strong></p>
            <p>Error message: <em>%(message)s</em></p>""") % {
                        'tagname': cgi.escape(e.location),
                        'message': e.errorDescription })
        except AdveneException, e:
            self.wfile.write(_("<h1>Error</h1>"))
            self.wfile.write(_("""<p>There was an error in the expression.</p>
            <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
        except:
            t, v, tr = sys.exc_info()
            import code
            self.wfile.write(_("<h1>Error</h1>"))
            self.wfile.write(_("""<p>Cannot resolve TALES expression %(expr)s on package %(package)s<p><pre>
            %(type)s
            %(value)s
            %(traceback)s</pre>""") % {
                    'expr': t, 
                    'package': pkgid, 
                    'type': unicode(t), 
                    'value': unicode(v), 
                    'traceback': "\n".join(code.traceback.format_tb (tr)) })

    def do_GET_admin (self, l, query):
        """Handles the X{/admin}  requests.

        The C{/admin} folder contains the following elements for the
        administration of the server:

          - C{/admin/list} : display the list of currently loaded packages
          - C{/admin/load} : load a new package
          - C{/admin/save} : save a package
          - C{/admin/delete} : remove a loaded package
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
        if len(l) == 0 or l[0] == '':
            self.display_summary ()
            return

        command = l[0]
        del l[0]

        if command == 'list':
            self.display_packages_list ()
        elif command == 'load':
            # Loads the specified URI
            try:
                alias = query['alias']
            except:
                self.send_error (501,
                                 _("""You should specify an alias"""))
                return
            try:
                uri = query['uri']
            except:
                self.send_error (501,
                                 _("""You should specify an uri"""))
                return
            try:
                self.server.controller.load_package (uri=uri, alias=alias)
                self.start_html (_("Package %s loaded") % alias, duplicate_title=True)
                self.display_loaded_packages (embedded=True)
                return
            except:
                self.send_error(501,
                                _("""<p>Cannot load package %s</p>""")
                                % uri)
                return
        elif command == 'delete':
            alias = query['alias']
            self.server.controller.sunregister_package (alias)
            self.start_html (_("Package %s deleted") % alias, duplicate_title=True)
            self.display_loaded_packages (embedded=True)
        elif command == 'save':
            alias=None
            try:
                alias = query['alias']
            except:
                pass
            if alias is not None:
                # Save a specific package
                self.server.controller.save_package(alias=alias)
            else:
                self.server.controller.save_package()
                alias='default'
            self.start_html (_("Package %s saved") % alias, duplicate_title=True)
            self.display_loaded_packages (embedded=True)
        elif command == 'reset':
            # Reset packages list
            self.server.controller.reset()
            self.start_html (_('Server reset'), duplicate_title=True)
            self.display_loaded_packages (embedded=True)
        elif command == 'status':
            self.start_html (_('Server status'), duplicate_title=True)
            self.wfile.write (_("""
            <p>%d package(s) loaded.</p>
            """) % len(self.server.controller.packages))
            if len(self.server.controller.packages) > 0:
                self.display_loaded_packages (embedded=True)
            else:
                self.wfile.write (_("<p>No package loaded</p>"))
        elif command == 'access':
            self.handle_access (l, query)
        elif command == 'methods':
            self.start_html (_('Available TALES methods'), duplicate_title=True)
            self.wfile.write('<ul>')
            c=self.server.controller.build_context(here=None)
            k=c.methods.keys()
            k.sort()
            for name in k:
                descr=c.methods[name].__doc__
                if descr:
                    descr=descr.split('\n')[0]
                self.wfile.write("<li><strong>%s</strong>: %s</li>\n" % (name, descr))
            self.wfile.write("</ul>")
        elif command == 'display':
            if l:
                # Set default display mode
                if l[0] in ('raw', 'navigation'):
                    self.server.displaymode=l[0]
                    ref=self.headers.get('Referer', "/")
                    self.send_redirect(ref)
                return
            else:
                # Display status
                self.start_html(_("Default display mode"))
                self.wfile.write(self.server.displaymode)
        elif command == 'halt':
            self.server.stop_serving ()
        else:
            self.start_html (_('Error'), duplicate_title=True)
            self.wfile.write (_("""<p>Unknown admin command</p><pre>Command: %s</pre>""") % command)

    def do_GET_action (self, l, query):
        """Handles the X{/action}  requests.

        The C{/action} folder allows to invoke the actions defined in
        the ECA framework (i.e. the same actions as the dynamic rules).

        Accessing the C{/action} folder itself displays the summary of
        available actions.

        @param l: the access path as a list of elements,
                  with the initial one (C{access}) omitted
        @type l: list
        @param query: the options given in the URL
        @type query: dict
        """
        catalog=self.server.controller.event_handler.catalog

        def display_action_summary():
            self.start_html(_("Available actions"), duplicate_title=True)
            self.wfile.write("<ul>")
            d=dict(catalog.get_described_actions(expert=True).iteritems())
            k=d.keys()
            k.sort()
            for name in k:
                a=catalog.get_action(name)
                if a.parameters:
                    # There are parameters. Display a link to the form.
                    self.wfile.write(_("""<li>%(name)s: %(value)s""")
                                     % {'name': name,
                                        'value': d[name]})
                    self.wfile.write(a.as_html("/action/%s" % name))
                else:
                    # No parameter, we can directly link the action
                    self.wfile.write("""<li><a href="%s">%s</a>: %s"""
                                     % ("/action/%s" % name,
                                        name,
                                        d[name]))
                self.wfile.write("</li>\n")
            self.wfile.write("</ul>")

        if len(l) == 0 or l[0] == '':
            display_action_summary ()
            return

        action = l[0]
        del l[0]

        try:
            ra=catalog.get_action(action)
        except KeyError:
            self.start_html (_('Error'), duplicate_title=True)
            self.wfile.write (_("""<p>Unknown action</p><pre>Action: %s</pre>""") % action)

        # Check for missing parameters
        missing=[]
        invalid=[]
        for p in ra.parameters:
            if not p in query:
                missing.append(p)
            elif not helper.is_valid_tales(query[p]):
                invalid.append(p)

        if missing:
            self.start_html (_('Error'), duplicate_title=True)
            self.wfile.write (_('Missing parameter(s) :<ul>'))
            for p in missing:
                self.wfile.write('<li>%s: %s</li>' % (p, ra.parameters[p]))
            return
        if invalid:
            self.start_html (_('Error'), duplicate_title=True)
            self.wfile.write (_('<p>Invalid parameter(s), they do not look like TALES expressions:</p><ul>'))
            for p in invalid:
                self.wfile.write('<li>%s (%s): %s</li>' % (p, ra.parameters[p], query[p]))
            return

        self.server.controller.queue_registered_action(ra, query)

        self.send_no_content()

    def do_GET_favicon(self):
        ico=config.data.advenefile( ( 'pixmaps', 'dvd.ico' ) )

        try:
            f=open(ico, 'rb')
        except IOError:
            self.send_error(404, _("No favicon"))
            return
        self.send_response (200)
        self.send_header ('Content-type', 'image/x-icon')
        self.send_header ('Cache-Control', 'max-age=6000')
        self.end_headers ()
        self.wfile.write(f.read())
        f.close()
        return True

    def do_GET_data (self, parameters, query):
        datadir=config.data.path['web']
        if '..' in parameters:
            # FIXME: we should do more effective security tests
            # against various attacks. But maybe we can just trust
            # the caller ?
            self.send_error(501,
                            _("""<p>Invalid data request %s</p>""")
                            % "/".join(parameters))
            return
        file_=os.path.join(datadir, *parameters)

        if (os.path.isdir(file_)):
            parameters.append('index.html')
            file_=os.path.join(datadir, *parameters)

        (mimetype, encoding) = mimetypes.guess_type(file_)
        if mimetype is None:
            mimetype = "text/plain"
        if encoding is None:
            encoding = ""
        else:
            encoding = "; charset=%s" % encoding

        try:
            f=open(file_, 'rb')
        except IOError:
            self.send_error(404,
                            _("""<p>%s not found.</p>""") % "/".join(parameters))
            return
        self.send_response (200)
        self.send_header ('Content-type', "%s%s" % (mimetype, encoding))
        self.send_header ('Cache-Control', 'max-age=600')
        self.end_headers ()
        self.wfile.write(f.read())
        f.close()
        return

    def display_server_root(self):
        """Display the server root document."""
        self.start_html (_("Advene webserver"), duplicate_title=True)
        self.wfile.write(_("""<p>Welcome on the <a href="http://liris.cnrs.fr/advene/">Advene</a> webserver run by %(userid)s on %(servername)s:%(serverport)d.</p>""") %
                         {
                'userid': config.data.userid, 
                'servername': self.server.server_name, 
                'serverport': self.server.server_port })

        if len(self.server.controller.packages) == 0:
            self.wfile.write(_(""" <p>No package is loaded. You can access the <a href="/admin">server administration page</a>.<p>"""))
        else:
            # It must be 2, since we always have a 'advene' key.  but
            # there could be some strange case where the advene key is
            # not present?
            if len(self.server.controller.packages) <= 2:
                alias='advene'
                p=self.server.controller.packages['advene']
                defaultview=p.getMetaData(config.data.namespace, 'default_utbv')
                if defaultview:
                    mes=_("""the <a href="/packages/%(alias)s/view/%(view)s">loaded package's default view</a>""") % {'alias': alias, 'view': defaultview}
                else:
                    mes=_("""the <a href="/packages/%s">loaded package's data</a>""") % alias
            else:
                mes=_("""the <a href="/packages">loaded packages' data</a>""")
            self.wfile.write(_(""" <p>You can either access %s or the <a href="/admin">server administration page</a>.<p>""") % mes)

        self.wfile.write(_("""<hr><p align="right"><em>Document generated by <a href="http://liris.cnrs.fr/advene/">Advene</a> v. %s.</em></p>""") % (advene.core.version.version))
        return

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

        alias = self.server.controller.aliases[p]

        if query is None:
            query={}

        if tales == "":
            expr = "here"
        elif tales.startswith ('options'):
            expr = tales
        else:
            expr = "here/%s" % tales

        context = self.server.controller.build_context (here=p, alias=alias)
        context.pushLocals()
        context.setLocal('request', query)
        # FIXME: the following line is a hack for having qname-keys work
        #        It is a hack because obviously, p is not a "view"
        context.setLocal (u'view', p)

        try:
            objet = context.evaluateValue (expr)
        except AdveneException, e:
            self.start_html (_("Error"), duplicate_title=True)
            self.wfile.write (_("""The TALES expression %s is not valid.""") % tales)
            self.wfile.write (unicode(e.args[0]).encode('utf-8'))
            return

        # FIXME:
        # Principe: si l'objet est un viewable, on appelle la
        # methode view pour en obtenir une vue par defaut.
        #if isinstance(objet, advene.model.viewable.Viewable):
        #    # It is a viewable, so display it using the default view
        #    objet.view(context=context)

        displaymode = self.server.displaymode
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
            self.send_response (200)
            self.send_header ('Content-type', self.image_type(str(objet)))
            self.no_cache ()
            self.end_headers ()
            self.wfile.write (str(objet))
            return
        elif displaymode == 'content':
            if hasattr(objet, 'mimetype'):
                self.send_response (200)
                self.send_header ('Content-type', objet.mimetype)
                self.no_cache ()
                self.end_headers ()
                self.wfile.write (objet.data)
                return
            elif hasattr(objet, 'contenttype'):
                self.send_response (200)
                self.send_header ('Content-type', objet.contenttype)
                self.no_cache ()
                self.end_headers ()
                self.wfile.write (objet)
                return
            else:
                self.send_error (404, _("Content mode not available on non-content data"))
                return

        # Last case: default or raw

        # FIXME: we should return a meaningful title

        if displaymode != "raw":
            displaymode = "navigation"

        # Display content
        if hasattr (objet, 'view') and callable (objet.view):

            context = self.server.controller.build_context(here=objet, alias=alias)
            context.pushLocals()
            context.setLocal('request', query)
            # FIXME: should be default view
            context.setLocal(u'view', objet)
            try:
                res=objet.view (context=context)
		self.start_html(mimetype=res.contenttype)
                if res.contenttype.startswith('text'):
                    self.wfile.write (res.encode('utf-8'))
                else:
                    self.wfile.write(res)
            except simpletal.simpleTAL.TemplateParseException, e:
                self.start_html(_("Error"))
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error in the template code.</p>
                <p>Tag name: <strong>%(tagname)s</strong></p>
                <p>Error message: <em>%(message)s</em></p>""") % {
                        'tagname': cgi.escape(e.location),
                        'message': e.errorDescription} )
            except simpleTALES.ContextContentException, e:
                self.start_html(_("Error"))
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>An invalid character is in the Context:</p>
                <p>Error message: <em>%(error)s</em></p><pre>%(message)s</pre>""")
                                 % {'error': e.errorDescription, 
                                    'message': unicode(e.args[0]).encode('utf-8')})
            except AdveneException, e:
                self.start_html(_("Error"))
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error in the TALES expression.</p>
                <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
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
		self.start_html(mimetype=mimetype)
                self.wfile.write (unicode(objet).encode('utf-8'))
            except AdveneException, e:
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error.</p>
                <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
            except simpletal.simpleTAL.TemplateParseException, e:
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error in the template code.</p>
                <p>Tag name: <strong>%(tagname)s</strong></p>
                <p>Error message: <em>%(message)s</em></p>""") % {
                            'tagname': cgi.escape(e.location),
                            'message': e.errorDescription})

        # Generating navigation footer
        if displaymode != "raw":
            levelup = self.path[:self.path.rindex("/")]
            auto_components = [ c
                                for c in helper.get_valid_members (objet)
                                if not c.startswith('----') ]
            auto_components.sort()
            try:
                auto_views = objet.validViews
                auto_views.sort()
            except:
                auto_views = []

            self.wfile.write (_("""
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
                self.wfile.write ("<option selected>view</option>")

            self.wfile.write ("\n".join(
                ["""<option>%s</option>""" % c for c in auto_components]))

            alias = self.path.split("/")[2]
            self.wfile.write (_("""
            </select> View: <select name="view" onchange="submit()">
            <option selected></option>
            """))

            self.wfile.write ("\n".join(
                ["""<option value="%s">%s</option>""" %
                 ("/".join((self.path, "view", c)), c)
                 for c in auto_views]))

            self.wfile.write ("""
            </select>
            <input type="submit" value="go">
            </form>
            <form name="entry" method="GET">
            <input size="50" type="text" name="path" accesskey="p">
            <input type="submit" value="go"></form>
            """)
            self.wfile.write (_("""<hr>
            <p>Evaluating expression "<strong>%(expression)s</strong>" on package %(uri)s returns %(value)s</p>
            """) % {
                    'expression': tales , 
                    'uri': p.uri, 
                    'value': cgi.escape(str(type(objet)))})
        return

    def do_eval (self, q):
        """Evaluates a python expression.

        This method is used as a debug shortcut, and should disappear in
        released versions of the software.

        It is called when a C{GET} method is invoked with a C{path}
        parameter beginning with C{eval:}.

        @param q: the expression to evaluated
        @type q: string
        """
        if 'pprint' not in dir():
            import pprint
        self.send_response (200)
        self.send_header ('Content-type', 'text/html; charset=utf-8')
        self.no_cache ()
        self.end_headers ()

        try:
            r = eval(q)
        except:
            t, v, tr = sys.exc_info()
            import code
            r = code.traceback.format_exception (t, v, tr)

        self.wfile.write ("""
        <html><head><title>Python evaluation</title>
        </head><body onLoad="document.entry.path.focus();">
        <p>
        <a href="/admin">Administrate server</a> |
        <a href="/admin/status">Server status</a>
        </p>
        Location: %s
        <hr>
        <h1>Python evaluation</h1>
        <p>Evaluating <strong>%s</strong> :</p>
        <pre>
        %s
        </pre>
        <form name="entry" method="GET"><input size="100" type="text" name="path" value="eval:%s" />
        <input type="submit" value="go" /></form>
        """ % (self.location_bar(),
               cgi.escape (q),
               cgi.escape(pprint.pformat(r)),
               cgi.escape (q, True)))

    def do_GET_debug (self):
        """Debug method.

        This method is called when accessing the C{/debug} folder.
        """
        self.start_html ("URLParse output")
        self.wfile.write("""
        <h1>URLParse output</h1>
        <p>Decomposing %s :</p>
        """ % self.path)
        self.wfile.write("""
        <pre>
        Scheme   : %s
        Netloc   : %s
        Path     : %s
        Params   : %s
        Query    : %s
        Fragment : %s
        </pre>
        </body></html>
        """ % urlparse.urlparse (self.path))
        return

    def do_PROPFIND (self):
        """PROPFIND method handler.

        The PROPFIND method seems to be more and more used by modern
        navigators.

        This method is here only to satisfy them, but does not return
        any sensible information for the moment.
        """

        return

class AdveneWebServer(
    SocketServer.ThreadingMixIn,
    BaseHTTPServer.HTTPServer,
):
    """Specialized HTTP server for the Advene framework.

    This is a specialized HTTP Server dedicated to serving Advene
    packages content, and interacting with a media player.

    @ivar controller: the controller
    @type controller: advene.core.controller.Controller

    @ivar shouldrun: indicates whether the server should stop listening
    @type shouldrun: boolean
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
        self.shouldrun = True  # Set to False to indicate the end of the
                               # server_forawhile method

        self.logger = logging.getLogger('webserver')
        # set the level to logging.DEBUG to get more messages
        self.logger.setLevel(logging.INFO)
        
        # Write webserver log to ~/.advene/webserver.log
        logfile=config.data.advenefile('webserver.log', 'settings')
        dp=os.path.dirname(logfile)
        if not os.path.isdir(dp):
            try:
                os.mkdir(dp)
            except OSError, e:
                print "Error: ", str(e)
                logfile="/tmp/webserver.log"
                print "Using %s as logfile" % logfile

        f=open(logfile, 'w')
        handler=logging.StreamHandler(f)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.logger.addHandler(handler)

        self.is_embedded = True

        self.controller=controller
        self.urlbase = u"http://localhost:%d/" % port
        self.displaymode = config.data.webserver['displaymode']
        self.authorized_hosts = {'127.0.0.1': 'localhost'}

        BaseHTTPServer.HTTPServer.__init__(self, ('', port),
                                           AdveneRequestHandler)

    def verify_request (self, request, client_address):
        """Access control method.

        This method returns C{True} if the client is allowed to send
        this request. We use the L{authorized_hosts} list to check.

        @param request: the incoming request
        @type request: Request
        @param client_address: the client address as a tuple (host, port)
        @type client_address: tuple
        @return: a boolean indicating whether the client is authorized or not
        @rtype: boolean
        """
        (host, port) = client_address
        #print "ACL for (%s, %d)" % (host, port)
        # FIXME: access control is desactivated for the moment.
        return True
        if '*' in self.authorized_hosts:
            return True
        if host not in self.authorized_hosts:
            return False
        return True

    def stop_serving (self):
        """Stop the web server.

        This method should be called to indicate that the web server should
        stop waiting for connections.
        """
        self.shouldrun = False
        self.socket.close ()

    def stop_player (self):
        """Stop the media player."""
        try:
            if self.controller.player.is_active ():
                self.controller.queue_action(self.controller.player.stop)
        except:
            pass

    def serve_forawhile (self):
        """Handle one request at a time until C{shouldrun} is False.

        Loop waiting for events on the input socket, with timeout handling
        and quitting variable.
        """
        while self.shouldrun:
	    try:
		r, w, x = select.select ([ self.socket ], [], [], 1)
	    except select.error:
		continue
            if r:
                self.handle_request()

    def start(self):
        """Stops the web server.

        New API.
        """
        self.serve_forawhile()

    def stop(self):
        """Stops the web server.

        New API.
        """
        self.stop_serving()
        
if __name__ == "__main__":
    from advene.core.controller  import AdveneController
    from advene.model.zippackage import ZipPackage

    controller=AdveneController()
    controller.init(config.data.args)

    if config.data.webserver['mode'] == 1:
        # Warning: in this case, the controller.update() method
        # will not be called, so dynamic views will not work.
        # Cf bin/advene-webserver for a correct example.
        print _("Server ready to serve requests.")
        controller.server.serve_forawhile ()

    # Cleanup the ZipPackage directories
    ZipPackage.cleanup()
