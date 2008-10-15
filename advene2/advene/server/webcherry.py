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

import sys
import os
import re
import urllib
import cgi
import imghdr
import inspect

from gettext import gettext as _

import cherrypy

if int(cherrypy.__version__.split('.')[0]) < 3:
    raise _("The webserver requires version 3.0 of CherryPy at least.")

from advene.model.core.package import Package
from advene.model.tales import AdveneContext
from simpletal.simpleTALES import PathNotFoundException
from simpletal.simpleTAL import TemplateParseException

DEBUG = True
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

    def get_valid_members (self, el):
        """Return a list of strings, valid members for the object el in TALES.

        This method is used to generate the contextual completion menu
        in the web interface and the browser view.

        @param el: the object to examine (often an Advene object)
        @type el: any

        @return: the list of elements which are members of the object,
                 in the TALES meaning.
        @rtype: list
        """
        # FIXME: try to sort items in a meaningful way

        # FIXME: return only simple items if not in expert mode
        l = []
        try:
            l.extend(el.ids())
        except AttributeError:
            try:
                l.extend(el.keys())
            except AttributeError:
                pass
        if l:
            l.insert(0, _('---- Elements ----'))

        pl=[e[0]
            for e in inspect.getmembers(type(el))
            if isinstance(e[1], property) and e[1].fget is not None]
        if pl:
            l.append(_('---- Attributes ----'))
            l.extend(pl)

        l.append(_('---- Methods ----'))
        # Global methods
        # l.extend (AdveneContext.defaultMethods ())
        # User-defined global methods
        #FIXME l.extend (config.data.global_methods)

        return l
        
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
            mode = self.controller.server.displaymode
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

        @param location: the URL to redirect to.
        @type location: string (URL)
        """
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

class Admin(Common):
    """Handles the X{/admin}  requests.

    The C{/admin} folder contains the following elements for the
    administration of the server:

      - C{/admin/list} : display the list of currently loaded packages
      - C{/admin/load} : load a new package
      - C{/admin/save/alias} : save a package
      - C{/admin/delete/alias} : remove a loaded package
      - C{/admin/status} : display current status
      - C{/admin/display} : display or set the default webserver display mode
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
        res=[ self.start_html (_("Server Administration"), duplicate_title=True) ]
        if self.controller.server.displaymode == 'raw':
            switch='navigation'
        else:
            switch='raw'
        mode_sw="""%(mode)s (<a href="/admin/display/%(switch)s">switch to %(switch)s</a>)""" % {
            'mode': self.controller.server.displaymode, 'switch': switch }

        res.append(_("""
        <p><a href="/admin/reset">Reset the server</a></p>
        <p><a href="/admin/halt">Halt the server</a></p>
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
        res=[ self.start_html (_("Available files"), duplicate_title=True) ]
        res.append ("<ul>")

        l=[ os.path.join(self.controller.server.packages_directory, n)
            for n in os.listdir(self.controller.server.packages_directory)
            if n.lower().endswith('.pdb') ]
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
                self.start_html (_("Package %s loaded") % alias, duplicate_title=True),
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
                self.start_html (_("Package %s deleted") % alias, duplicate_title=True),
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
                self.start_html (_("Package %s saved") % alias, duplicate_title=True),
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
        return self.start_html (_('Server reset'), duplicate_title=True)
    reset.exposed=True

    def halt(self):
        """Halt server.
        """
        self.controller.server.stop()
        raise SystemExit(0)
    halt.exposed=True

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
        res=[ self.start_html (_("Loaded package(s)")) ]

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
            """) % { 'alias':alias, 'uri':p.uri, 'size':len(list(p.own.annotations)) })
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
        except PathNotFoundException, e:
            self.start_html (_("Error"), duplicate_title=True)
            res.append (_("""The TALES expression %s is not valid.""") % tales)
            res.append (unicode(e.args).encode('utf-8'))
            return

        # FIXME:
        # Principe: si l'objet est un viewable, on appelle la
        # methode view pour en obtenir une vue par defaut.
        #if isinstance(objet, advene.model.viewable.Viewable):
        #    # It is a viewable, so display it using the default view
        #    objet.view(context=context)

        displaymode = self.controller.server.displaymode
        # Hack to automatically switch to an image view for image objects.
        if query.has_key('mode'):
            displaymode = query['mode']
            del (query['mode'])

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
            except PathNotFoundException, e:
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
            except PathNotFoundException, e:
                res.append(_("<h1>Error</h1>"))
                res.append(_("""<p>There was an error.</p>
                <pre>%s</pre>""") % cgi.escape(unicode(e.args[0]).encode('utf-8')))
            except TemplateParseException, e:
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
                                for c in self.get_valid_members (objet)
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
        except TemplateParseException, e:
            res=[ self.start_html(_("Error")) ]
            res.append(_("<h1>Error</h1>"))
            res.append(_("""<p>There was an error in the template code.</p>
            <p>Tag name: <strong>%(tagname)s</strong></p>
            <p>Error message: <em>%(message)s</em></p>""") % {
                        'tagname': cgi.escape(e.location),
                        'message': e.errorDescription })
        except PathNotFoundException, e:
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
        self.packages=Packages(controller)

    def index(self):
        """Display the server root document.
        """
        res=[ self.start_html (_("Advene webserver"), duplicate_title=True) ]
        res.append(_("""<p>Welcome on the <a href="http://liris.cnrs.fr/advene/">Advene</a> webserver run by %(userid)s on %(serveraddress)s.</p>""") %
                         {
                'userid': os.environ['USER'],
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
                mes=_("""the <a href="/packages/%s">loaded package's data</a>""") % alias
            res.append(_(""" <p>You can either access %s or the <a href="/admin">server administration page</a>.<p>""") % mes)

        #res.append(_("""<hr><p align="right"><em>Document generated by <a href="http://liris.cnrs.fr/advene/">Advene</a> v. %s.</em></p>""") % (advene.core.version.version))
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
                'log.access_file': '/tmp/advene-webserver.log',
                'log.error_file': '/tmp/advene-error.log',
                'server.reverse_dns': False,
                # For the moment, advene.model is not
                # other-thread-compatible, so do not use a threadPool
                'server.thread_pool': 0,
                'engine.autoreload_on': False,
                'server.environment': "development",
                #'server.environment': "production",
                },
            }
        cherrypy.config.update(settings)

        cherrypy.tree.mount(Root(controller), config={})

        self.displaymode='navigation'
        self.packages_directory='/tmp'

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

class BasicController:
    def __init__(self):
        self.packages={}
        self.aliases={}
        self.server=None

    def load_main_package(self, fname):
        p=Package(fname)
        self.packages['advene']=p
        self.aliases[p]='advene'
    
    def log(self, *p):
        print p

    def load_package(self,  uri=None, alias=None):
        print "FIXME"

    def save_package(self,  alias=None):
        print "FIXME"

    def unregister_package(self,  alias=None):
        print "FIXME"

    def reset(self):
        self.packages={}
        self.aliases={}

    def build_context(self, here=None, alias=None):
        c=AdveneContext()
        c.addGlobal('here', here)
        return c

    def queue_action(self, action, *p, **kw):
        action(*p, **kw)

if __name__ == '__main__':
    controller=BasicController()
    controller.load_main_package('file:' + sys.argv[1])
    controller.server=AdveneWebServer(controller)
    
    controller.server.start()
    cherrypy.engine.block()
