"""Advene http server.

This module is composed of two classes : L{AdveneWebServer} is the
main server class, L{AdveneRequestHandler} is dedicated to request
handling.

URL syntax
==========

  The URL syntax is described in L{AdveneRequestHandler}.

Embedding AdveneServer
======================

  The server can run standalone or embedded in another application (typically
  the GUI C{advenetool}).

  To embed the server in another application, it must be instanciated
  with the following parameters : C{controller}. See the
  L{AdveneWebServer.__init__} documentation for more details.

Running AdveneServer standalone
===============================

  The AdveneServer can be run indepently. In this case, it can maintain
  and give access to a number of different packages.  
"""

import advene.core.config as config
import advene.core.version

from gettext import gettext as _

from advene.model.package import Package
from advene.model.view import View
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment
from advene.model.exception import AdveneException
from advene.model.content import Content

import advene.model.tal.context
import simpletal.simpleTAL

import sys
import os
import posixpath
import urlparse
import urllib
import cgi
import socket
import select
import inspect
import mimetypes
import logging

import imghdr

import advene.util.vlclib as vlclib
import advene.core.imagecache as imagecache

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
                    mode="navigation", mimetype=None, duplicate_title=False, cache=False):
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
#         if epoz:
#             self.wfile.write(
#                 """<script src="/data/epoz/dom2_events.js" type="text/javascript"></script>
#                 <script src="/data/epoz/sarissa.js" type="text/javascript"></script>
#                 <script src="/data/epoz/epozeditor.js" type="text/javascript"></script>
#                 <link href="/data/epoz/epozstyles.css" type="text/css" rel="stylesheet">
#                 <link href="/data/epoz/epozcustom.css" type="text/css" rel="stylesheet">
#                 </head>
#                 <body onload="epoz = initEpoz(document.getElementById('epoz-editor'));
#                 epozui = epoz.getTool('ui');">
#                 """)
#         else:
#             self.wfile.write("</head><body>")

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
        res = {}
        if q == "":
            return res
        for t in q.split("&"):
            k,v = t.split("=", 1)
            res[urllib.unquote_plus(k)] = urllib.unquote_plus(v)
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
            self.server.controller.player.update_status ()
            self.wfile.write (_("""
            <h1>Current STBV: %s</h1>

            <h1>Player status</h1>
            <table border="1">
            <tr>
            <td>Current position</td><td>%d</td>
            <td>Input size</td><td>%d</td>
            <td>Player status</td><td>%s</td>
            </tr>
            </table>
            """) % (
                str(self.server.controller.current_stbv),
                self.server.controller.player.current_position_value,
                self.server.controller.player.stream_duration,
                repr(self.server.controller.player.status)))
                
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
          - C{/media/stbv}

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

          The C{/media/play} starts the media player. It can take two
          optional arguments (in the form of URL-options):

            - C{filename=...} : if specified, the media player will load the
              given file before starting the player.
            - C{position=...} : if specified, the player will start at the
              given position (in ms). Else, it will start
              at the beginning.

        The X{/media/stop} and X{/media/pause} elements
        -----------------------------------------------

          These elements control the player, and take no argument.

        @param l: the access path as a list of elements,
                  with the initial one (C{media}) omitted
        @type l: list
        @param query: the options given in the URL
        @type query: dict

        The X{/media/stbv} element
        --------------------------

          The C{/media/stbv} element activates a new stbv. It takes one
          argument (in the form of URL-option):

            - C{id=...} : the STBV id

          If no argument is given, its deactivates the STBV


        """
        if len(l) == 0:
            # Display media information
            self.start_html (_('Media information'))
            self.display_media_status ()
        else:
            command = l[0]
            param = l[1:]
            if command == 'load':
                if query.has_key ('filename'):
                    name = urllib.unquote(query['filename'])
                    if name == 'dvd':
                        name = "dvd:///dev/dvd"
                    try:
                        if isinstance(name, unicode):
                            name=name.encode('utf8')
                        self.server.controller.player.playlist_add_item (name)
                        
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
                    for alias in self.server.packages.keys ():
                        self.wfile.write ("""<li><a href="/media/snapshot/%s">%s</a></li>""" % (alias, alias))
                    self.wfile.write("</ul>")
                    return
                alias = param[0]
                i = self.server.imagecaches[alias]

                if not query.has_key ('position') and len(param) < 2:
                    self.start_html (_("Available snapshots for %s") % alias, duplicate_title=True)
                    self.wfile.write ("<ul>")
                    if (query.has_key('mode') and query['mode'] == 'inline'):
                        template="""<li><a href="/media/snapshot/%(alias)s/%(position)d"><img src="/media/snapshot/%(alias)s?position=%(position)d" /></a></li>"""
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
                    self.server.controller.player.playlist_add_item (f)
                if len(param) != 0:
                    # First parameter is the position
                    position = param[0]                    
                elif query.has_key ('position'):
                    position = query['position']
                else:
                    self.send_redirect ("/media")
                self.server.controller.update_status ("set", long(position))
                self.send_no_content()
            elif command == 'pause':
                self.server.controller.update_status ("pause")
                ref=self.headers.get('Referer', "/media")
                self.send_no_content()
            elif command == 'stop':
                self.server.controller.update_status ("stop")
                ref=self.headers.get('Referer', "/media")
                self.send_no_content()
            elif command == 'stbv':
                if len(param) != 0:
                    stbvid=param[0]
                elif query.has_key ('id'):
                    stbvid=query['id']
                else:
                    self.send_error (404, _('Malformed request'))
                    return
                
                stbvlist=[ v
                           for v in self.server.controller.package.views
                           if v.id == stbvid ]
                if len(stbvlist) != 1:
                    self.send_error(404, _('Unknown STBV identifier: %s') % stbvid)
                    return
                else:
                    stbv=stbvlist[0]

                self.server.controller.activate_stbv(view=stbv)
                #self.server.controller.update_status("play", 0)                
                self.send_no_content()
                    
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
        self.wfile.write(_("""
        <p><a href="/admin/status">Display the server status</a></p>
        <p><a href="/admin/access">Update the access list</a></p>
        <p><a href="/admin/reset">Reset the server</a></p>
        <p><a href="/media">Media control</a></p>
        <p><a href="/admin/list">List available files</a></p>
        <p><a href="/packages">List loaded packages</a> (%s)</p> 
        <form action="/admin/display" method="POST">
        <p>Display mode: <select name="mode">
        <option value="default" selected>Default (with navigation interface)</option>
        <option value="raw">Raw (only the views)</option>
        </select>
        <input type="submit" value="Set">
        <hr>
        <p>Load a package :
        <form action="/admin/load" method="GET">
        Alias: <input type="text" name="alias" /><br>
        URI:   <input type="text" name="uri" /><br>
        <input type="submit" value="Load" />
        </form>
        </body></html>
        """) % " | ".join( ['<a href="/packages/%s">%s</a>' % (alias, alias)
                            for alias in self.server.packages.keys() ] ))

    def display_packages_list (self):
        """Display available Advene files.

        This method displays the data files in the data directory.
        Maybe it should be removed when the server runs embedded.
        """
        self.start_html (_("Available files"), duplicate_title=True)
        self.wfile.write ("<ul>")
        import glob
        for i in glob.glob (os.sep.join ((config.data.path['data'], '*.xml'))):
            name = i.replace (".xml", "")
            self.wfile.write ("""
            <li><a href="/admin/load?alias=%(alias)s&uri=%(uri)s">%(uri)s</a></li>
            """ % {'alias':name, 'uri':i})
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
        for alias in self.server.packages.keys():
            p = self.server.packages[alias]
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

    def default_options(self, alias):
        return {
            u'package_url': u"/packages/%s" % alias,
            u'snapshot': self.server.imagecaches[alias],
            u'namespace_prefix': config.data.namespace_prefix,
            u'config': config.data.web,
            }
        
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
                
            context = advene.model.tal.context.AdveneContext (here=self.server.packages[alias],
                                                              options=self.default_options(alias))
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

        Setting the X{display mode}
        ===========================
        
        Accessing the C{/admin/display} element updates the server
        display mode. The data should be available as a parameter
        named C{mode}, which is either C{default} or C{raw}

        Manipulating package data
        -------------------------

        The package data can be manipulated in this way. The
        appropriate action is specified through the C{action}
        parameter, which can be either C{update}, C{create} or
        C{delete}.

        Updating data
        -------------

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
        -----------------

        The creation of new elements in a package is done by
        specifying the C{action=create} parameter.

        The type of the created object is given through the C{type}
        parameter. For the moment, only C{view} is valid.

        A view is created with the following data, specified with parameters:

          - C{id} : the identifier of the view. Should not be already used.
          - C{class} : the class that this view should apply on.
          - C{data} : the content data of the view (the TAL template).
        
        """

        self.start_html (_("Setting value"))

        (scheme,
         netloc,
         stringpath,
         params,
         stringquery,
         fragment) = urlparse.urlparse (self.path)
        
        stringpath = stringpath.replace ('%3A', ':')

        # A trailing / would give an empty last value in the path
        path = stringpath.split('/')[1:]
        
        if path[-1] == '':
            del (path[-1])

        if len(path) < 2:
            self.wfile.write (_("<h1>Error</h1>"))
            self.wfile.write(_("<p>Cannot set the value : invalid path</p>"))
            return

        if path[0] == 'admin':
            if path[1] == 'display':
                query = self.query2dict(self.rfile.read (long(self.headers['content-length'])))
                if not query.has_key('mode'):
                    self.server.displaymode = 'default'
                else:
                    self.server.displaymode = query['mode']
                self.wfile.write (_("""
                <h1>Display mode</h1>
                <p>Display mode is now <code>%s</code></p>
                """) % self.server.displaymode)
                return
        elif path[0] == 'packages':
            alias = path[1]
            query = self.query2dict(self.rfile.read (long(self.headers['content-length'])))
            tales = "/".join (path[2:])
            if tales == "":
                expr = "here"
            else:
                expr = "here/%s" % tales
                
            context = advene.model.tal.context.AdveneContext (here=self.server.packages[alias],
                                                        options=self.default_options(alias))
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
            
            # Different actions : update, create, delete
            if query['action'] == 'update':
                if hasattr(objet, query['key']):
                    objet.__setattr__(query['key'], query['data'])
                    self.wfile.write (_("""
                    <h1>Value updated</h1>
                    The value of %s has been updated to
                    <pre>
                    %s
                    </pre>
                    """) % ("/".join([tales, query['key']]),
                           cgi.escape(query['data'])))
                else:
                    # Fallback mode : maybe we were in a list, and
                    # query['object'] has the id of the object in the list
                    try:
                        o = objet[query['object']]
                        if hasattr(o, query['key']):
                            o.__setattr__(query['key'], query['data'])
                            self.wfile.write (_("""
                            <h1>Value updated</h1>
                            The value of %s has been updated to
                            <pre>
                            %s
                            </pre>
                            """) % ("/".join([tales,
                                             query['object'],
                                             query['key']]),
                                   cgi.escape(query['data'])))
                            return
                    except:
                        pass
                    self.wfile.write ("""
                    <h1>Error</h1>
                    <p>The object %s has no key %s.</p>
                    """ % (tales, query['key']))
            elif query['action'] == 'create':
                 # Create a new element. For the moment, only
                 # View is supported
                 if not isinstance (objet, Package):
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
                         self.wfile.write (_("<h1>Error</h1>"))
                         self.wfile.write (_("<p>Error while creating view %s</p>")
                                           % query['id'])
                         self.wfile.write("""
                         <pre>
                         %s
                         </pre>
                         """ % (unicode(e)))
                         return
                     
                     self.wfile.write (_("""
                     <h1>View <em>%s</em> created</h1>
                     <p>The view <a href="%s">%s</a> was successfully created.</p>
                     """) % (v.id,
                            "/packages/%s/views/%s" % (self.server.aliases[objet],
                                                      v.id),
                            v.id))
                 else:
                     self.wfile.write (_("<h1>Error</h1>"))
                     self.wfile.write (_("<p>Cannot create an object of type %s.</p>") % (query['type']))
            else:
                self.wfile.write (_("<h1>Error</h1>"))
                self.wfile.write (_("<p>Cannot perform the action <em>%s</em> on <code>%s</code></p>")
                                  % (query['action'], cgi.escape(unicode(objet))))
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
                self.wfile.write (_("<p>Cannot perform the action <em>%s</em> on <code>%s</code></p>")
                                  % (query['action'], cgi.escape(unicode(objet))))

                
    def do_GET(self):
        """Handle GET requests.

        This method dispatches GET requests to the corresponding methods :

          - L{do_GET_element} for C{/package} elements access
          - L{do_GET_admin} for C{/admin} folder access
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
        #self.do_GET_debug ()a
        #return
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
        elif command == 'media':
            self.handle_media (parameters, query)
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
            p = self.server.packages[pkgid]
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
            <p>Tag name: <strong>%s</strong></p>
            <p>Error message: <em>%s</em></p>""" % (cgi.escape(e.location),
                                                    e.errorDescription)))
        except AdveneException, e:
            self.wfile.write(_("<h1>Error</h1>"))
            self.wfile.write(_("""<p>There was an error in the expression.</p>
            <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
        except:
            t, v, tr = sys.exc_info()
            import code
            self.wfile.write(_("<h1>Error</h1>"))
            self.wfile.write(_("""<p>Cannot resolve TALES expression %s on package %s<p><pre>
            %s
            %s
            %s</pre>""") % (t, pkgid, unicode(t), unicode(v), "\n".join(code.traceback.format_tb (tr))))
                
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

        Accessing the C{/admin} folder itself displays the summary
        (equivalent to the root document).

        Loading, saving or deleting packages is done by specifying the
        C{alias} parameter. In the case of the C{/admin/load} action,
        the C{uri} parameter must provide the appropriate URI.

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

        if command == 'list':
            self.display_packages_list ()
        elif command == 'load':
            # Loads the specified URI
            try:
                alias = query['alias']
            except:
                self.send_error (501,
                                 _("""You should specify an alias"""))
            try:
                uri = query['uri']
            except:
                self.send_error (501,
                                 _("""You should specify an uri"""))
            try:
                self.server.controller.load_package (uri=uri, alias=alias)
                self.start_html (_("Package %s loaded") % alias, duplicate_title=True)
                self.display_loaded_packages (embedded=True)                
            except:
                self.send_error(501,
                                _("""<p>Cannot load package %s</p>""")
                                % uri)
            self.send_redirect('/packages')
        elif command == 'delete':
            alias = query['alias']
            self.server.unregister_package (alias)
            self.start_html (_("Package %s deleted") % alias, duplicate_title=True)
            self.display_loaded_packages (embedded=True)
        elif command == 'save':
            alias = query['alias']
            p = self.server.packages[alias]
            p.save (as=p.uri)
            self.start_html (_("Package %s saved") % alias, duplicate_title=True)
            self.display_loaded_packages (embedded=True)
        elif command == 'reset':
            # Reset packages list
            self.server.packages = {}
            self.server.aliases = {}
            self.server.imagecaches = {}
            self.start_html (_('Server reset'), duplicate_title=True)
            self.display_loaded_packages (embedded=True)
        elif command == 'status':
            self.start_html (_('Server status'), duplicate_title=True)
            self.wfile.write (_("""
            <p>%d package(s) loaded.</p>
            """) % len(self.server.packages))
            if len(self.server.packages) > 0:
                self.display_loaded_packages (embedded=True)
            else:
                self.wfile.write (_("<p>No package loaded</p>"))
        elif command == 'access':
            self.handle_access (l, query)
        else:
            self.start_html (_('Error'), duplicate_title=True)
            self.wfile.write (_("""<p>Unknown admin command</p><pre>Command: %s</pre>""") % command)

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
        file_=os.sep.join((datadir, os.sep.join(parameters)))

        if (os.path.isdir(file_)):
            parameters.append('index.html')
            file_=os.sep.join((datadir, os.sep.join(parameters)))
            
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
        self.wfile.write(_("""<p>Welcome on the <a href="http://liris.cnrs.fr/advene/">Advene</a> webserver run by %s on %s:%d.</p>""") %
                         (config.data.userid, self.server.server_name, self.server.server_port))

        if len(self.server.aliases) == 1:
            self.wfile.write(_(""" <p>You can either access the <a href="/packages/%s">loaded package's data</a> or the <a href="/admin">server administration page</a>.<p>""") % self.server.packages.keys()[0])
        elif len(self.server.aliases) == 0:
            self.wfile.write(_(""" <p>No package is loaded. You can access the <a href="/admin">server administration page</a>.<p>"""))
        else:
            self.wfile.write(_(""" <p>You can either access the <a href="/packages">loaded package's data</a> or the <a href="/admin">server administration page</a>.<p>"""))
            
        
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
        
        @param p: the package in which the expression should be evaluated
        @type p: advene.model.Package
        @param tales: a TALES expression
        @type tales: string
        @param query: options used in TAL/TALES processing
        @type query: dict
        """

        alias = self.server.aliases[p]

        if query is None:
            query={}
        query.update(self.default_options(alias))

        if tales == "":
            expr = "here"
        elif tales.startswith ('options'):
            expr = tales
        else:
            expr = "here/%s" % tales

        context = advene.model.tal.context.AdveneContext (here=p, options=query)
        # FIXME: the following line is a hack for having qname-keys work
        #        It is a hack because obviously, p is not a "view"
        context.addGlobal (u'view', p)
        if 'epoz' in tales:
            context.addGlobal (u"epozmacros", self.server.epoz_macros)

        try:
            objet = context.evaluateValue (expr)
        except AdveneException, e:
            self.start_html (_("Error"), duplicate_title=True)
            self.wfile.write (_("""The TALES expression %s is not valid.""") % tales)
            #print "Exc %s" % type(repr(e))
            #print "a %s" % unicode(e.args)
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
        if hasattr(objet, 'contenttype') and objet.contenttype not in ('text/plain',
                                                                       'text/html'):
            displaymode = 'content'

        if displaymode == 'image':
            # Return an image, so build the correct headers
            self.send_response (200)
            self.send_header ('Content-type', self.image_type(str(objet)))
            self.no_cache ()
            self.end_headers ()
            self.wfile.write (str(objet))
            return
        elif displaymode == 'content':
            if isinstance (objet, Content):
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
        # FIXME: epoz support is kind of a hack for now. 
        # FIXME: we should return a meaningful title

        if displaymode != "raw":
            displaymode = "navigation"
            
        if 'epoz' in tales:
            self.start_html(title=_("TALES evaluation - %s") % tales,
                            head_section=self.server.epoz_head,
                            body_attributes=self.server.epoz_body_attributes,
                            mode=displaymode)
        else:
            self.start_html(title=_("TALES evaluation - %s") % tales,
                            mode=displaymode)

        # Display content
        if hasattr (objet, 'view') and callable (objet.view):
            
            context = advene.model.tal.context.AdveneContext (here=objet,
                                                              options=query)
            # FIXME: maybe add more elements to context (view, ?)
            #context.log = advene.model.tal.context.DebugLogger ()
            try:
                self.wfile.write (objet.view (context=context).encode('utf-8'))
            except simpletal.simpleTAL.TemplateParseException, e:
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error in the template code.</p>
                <p>Tag name: <strong>%s</strong></p>
                <p>Error message: <em>%s</em></p>""") % (cgi.escape(e.location),
                                                         e.errorDescription))
            except AdveneException, e:
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error in the TALES expression.</p>
                <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
        else:
            try:
                self.wfile.write (unicode(objet).encode('utf-8'))
            except AdveneException, e:
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error.</p>
                <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
            except simpletal.simpleTAL.TemplateParseException, e:
                self.wfile.write(_("<h1>Error</h1>"))
                self.wfile.write(_("""<p>There was an error in the template code.</p>
                <p>Tag name: <strong>%s</strong></p>
                <p>Error message: <em>%s</em></p>""" % (cgi.escape(e.location),
                                                        e.errorDescription)))
        
        # Generating navigation footer
        if displaymode != "raw":
            levelup = self.path[:self.path.rindex("/")]
            auto_components = [ c
                                for c in vlclib.get_valid_members (objet)
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
            Location: %s<br>
            <form name="navigation" method="GET">
            <a href="%s">Up one level</a> |
            Next level :
            <select name="path" onchange="submit()">
            """) % (self.location_bar (),
                   levelup))

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
            <p>Evaluating expression "<strong>%s</strong>" on package %s returns %s</p>
            """) % (tales , p.uri, cgi.escape(str(type(objet)))))            
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

class AdveneWebServer(SocketServer.ThreadingMixIn,
                       BaseHTTPServer.HTTPServer):
    """Specialized HTTP server for the Advene framework.
    
    This is a specialized HTTP Server dedicated to serving Advene
    packages content, and interacting with a media player.

    @ivar packages: a dictionary of (alias, package)
    @type packages: dict
    @ivar aliases: a dictionary of (package, alias)
    @type aliases: dict
    @ivar imagecaches: a dictionary of (alias, imagecache)
    @type imagecaches: dict
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
        loading and player interaction. When running standalone, the
        server will its own controller.

        @param controller: the controller
        @type controller: any, should provide some methods (C{load_package}, C{update_status}, ...)
        @param port: the port number the server should bind to
        @type port: int
        """
        self.packages = {}     # Key: alias,  value: package
        self.aliases = {}      # Key: package, value: alias
        self.imagecaches = {}  # Key: alias, value: imagecache
        self.shouldrun = True  # Set to False to indicate the end of the
                               # server_forawhile method

        self.logger = logging.getLogger('webserver')
        handler=logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.logger.addHandler(handler)
        # set the level to logging.DEBUG to get more messages
        self.logger.setLevel(logging.INFO)
        
        if controller is None:
            # If "controller" is not specified, adveneserver will handle
            # itself package loading
            controller = self

        self.controller=controller
        self.urlbase = "http://localhost:%d/" % port
        self.displaymode = config.data.webserver['displaymode']
        self.authorized_hosts = {'127.0.0.1':'localhost'}

        # Compile EPOZ template file
        fname=os.sep.join((config.data.path['web'], 'epoz', 'epozmacros.html'))
        templateFile = open (fname, 'r')
        self.epoz_macros = simpletal.simpleTAL.compileHTMLTemplate (templateFile)        
        templateFile.close()
        self.epoz_head = """<script src="/data/epoz/dom2_events.js" type="text/javascript"></script>
        <script src="/data/epoz/sarissa.js" type="text/javascript"></script>
        <script src="/data/epoz/epozeditor.js" type="text/javascript"></script>
        <link href="/data/epoz/epozstyles.css" type="text/css" rel="stylesheet">
        <link href="/data/epoz/epozcustom.css" type="text/css" rel="stylesheet">
        """
        self.epoz_body_attributes="""onload="epoz = initEpoz(document.getElementById('epoz-editor')); epozui = epoz.getTool('ui');" """
        
        
        BaseHTTPServer.HTTPServer.__init__(self, ('', port),
                                           AdveneRequestHandler)

    def get_url_for_alias (self, alias=None):
        if alias is not None:
            return urllib.basejoin(self.urlbase, "/packages/" + alias)
        else:
            return None

    # Controller methods
    def load_package (self, uri=None, alias="advene"):
        """Loads a package.

        This method is provided in order to make the server able to
        run standalone, and be its own controller.

        @param uri: the URI of the package. Create a new package if it is I{None} or C{""}
        @type uri: string
        @param alias: the alias of the loaded package
        @type alias: string
        """

        if uri is None or uri == "":
            p = Package (uri="",
                         source=config.data.advenefile(config.data.templatefile))
            p.author = config.data.userid
        else:
            p = Package (uri=uri)
            
        mediafile = p.getMetaData (config.data.namespace,
                                   "mediafile")
        if mediafile is not None and mediafile != "":
            id_ = vlclib.mediafile2id (mediafile)
            
        self.register_package (alias=alias,
                               package=p,
                               imagecache=imagecache.ImageCache (id_))

    def update_status(self, status, position):
        if self.controller.player is not None:
            self.controller.player.update_status(status, position)
        return True

    # End of controller methods
    
    def register_package (self, alias, package, imagecache):
        """Register a package in the server loaded packages lists.

        @param alias: the package's alias
        @type alias: string
        @param package: the package itself
        @type package: advene.model.Package
        @param imagecache: the imagecache associated to the package
        @type imagecache: advene.core.ImageCache
        """
        self.packages[alias] = package
        self.aliases[package] = alias
        self.imagecaches[alias] = imagecache
        if self.controller.player is not None and self.controller.player.is_active():
            mediafile = package.getMetaData (config.data.namespace, "mediafile")
            if (mediafile is not None and mediafile != "" and
                mediafile not in self.controller.player.playlist_get_list()):
                if isinstance(mediafile, unicode):
                    mediafile=mediafile.encode('utf8')
                self.controller.player.playlist_add_item (mediafile)

    def unregister_package (self, alias):
        """Remove a package from the loaded packages lists.

        @param alias: the  package alias
        @type alias: string
        """
        p = self.packages[alias]
        del (self.aliases[p])
        del (self.packages[alias])
        del (self.imagecaches[alias])
        
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
                self.controller.player.stop ()
        except:
            pass
        
    def serve_forawhile (self):
        """Handle one request at a time until C{shouldrun} is False.
        
        Loop waiting for events on the input socket, with timeout handling
        and quitting variable.
        """
        while self.shouldrun:
            r, w, x = select.select ([ self.socket ], [], [], 1)
            if len(r) != 0:
                self.handle_request()

if __name__ == "__main__":
    import atexit
    import advene.core.mediacontrol as mediacontrol
    
    server = AdveneWebServer(controller=None)
    f=mediacontrol.PlayerFactory()
    server.player=f.get_player()
    atexit.register (server.stop_player)

    if len(sys.argv) > 1:
        for uri in sys.argv[1:]:
            alias = posixpath.basename(posixpath.splitext(uri)[0])
            server.load_package (uri=uri, alias=alias)
    print _("Server ready to serve requests.")
    server.serve_forever ()
