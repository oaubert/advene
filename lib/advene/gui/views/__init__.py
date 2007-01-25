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
import advene.core.config as config

import sre
import gtk
import StringIO

from gettext import gettext as _

import xml.dom.DOMImplementation

from advene.model.content import Content
from advene.model.view import View
import advene.gui.util
import advene.util.helper as helper

class AdhocView(object):
    """Implementation of the generic parts of AdhocViews.

    For details about the API of adhoc views, see gui.views.viewplugin.
    """
    def __init__(self, controller=None, parameters=None):
        self.view_name = "Generic adhoc view"
        self.view_id = 'generic'
        # List of couples (label, action) that are use to
        # generate contextual actions
        self.contextual_actions = ()

        # Dictionary of view-specific options.
        self.options = {}

        # If True, the view should be closed when loading a new package.
        # Else, it can respond to a package load and update
        # itself accordingly (through the update_model method).
        self.close_on_package_load = True

        self.controller = controller
        # If self.buttonbox exists, then the widget has already
        # defined its own buttonbox, and the generic popup method
        # can but the "Close" button in it:
        # self.buttonbox = gtk.HButtonBox()

        if parameters is not None:
            opt, arg = self.load_parameters(parameters)
            self.options.update(opt)

        self.widget=self.build_widget()

    def close(self):
        if self.controller and self.controller.gui:
            self.controller.gui.unregister_view (self)
        self.widget.destroy()
        return True

    def log(self, msg, level=None):
        m=": ".join( (self.view_name, msg) )
        if self.controller:
            self.controller.log(m, level)
        else:
            print m

    def load_parameters(self, content):
        """Load the parameters from a Content object.
 
        It will return a tuple (options, arguments) where options is a
        dictionary and arguments a list of tuples (name, value).

        In case of problem, it will simply return None, None.
        """
        opt, arg = {}, []
        try:
            m=content.mimetype
        except:
            return opt, arg
        if  m != 'application/x-advene-adhoc-view':
            return opt, arg

        p=AdhocViewParametersParser()
        p.parse_file(content.stream)
        
        if p.view_id != self.view_id:
            self.controller.log(_("Invalid view id"))
            return False

        for name, value in p.options.iteritems():
            # If there is a self.options dictionary, try to guess
            # value types from its content.
            try:
                op=self.options[name]
                if value == 'None':
                    value=None
                elif value == 'True':
                    value=True
                elif value == 'False':
                    value=False
                elif isinstance(op, int) or isinstance(op, long):
                    value=long(value)
                elif isinstance(op, float):
                    value=float(value)
            except (KeyError, AttributeError):
                pass
            opt[name]=value
        return opt, p.arguments

    def save_parameters(self, content, options=None, arguments=None):
        """Save the view parameters to a Content object.
        """
        if not isinstance(content, Content):
            raise Exception("save_parameters saves to a Content object")

        content.mimetype='application/x-advene-adhoc-view'

        di = xml.dom.DOMImplementation.DOMImplementation()
        dom = di.createDocument(config.data.namespace, "adhoc", None)
        node=dom._get_documentElement()
        node.setAttribute('id', self.view_id)

        if options:
            for n, v in options.iteritems():
                o=dom.createElement('option')
                o.setAttribute('name', n)
                o.setAttribute('value', unicode(v))
                node.appendChild(o)
        if arguments:
            for n, v in arguments:
                o=dom.createElement('argument')
                o.setAttribute('name', n)
                o.setAttribute('value', unicode(v))
                node.appendChild(o)
        stream=StringIO.StringIO()
        xml.dom.ext.PrettyPrint(dom, stream)
        content.setData(stream.getvalue())
        stream.close()
        xml.dom.ext.PrettyPrint(dom)

        return True

    def get_save_arguments(self):
        """Method called when saving a parametered view.
        
        It should return a tuple (options, arguments) where options is
        the options dictionary, and arguments is a list of (name,
        value) tuples).

        If it returns None, None, it means that the view saving is cancelled.
        """
        return self.options, []

    def save_view(self, *p):
        ident=advene.gui.util.entry_dialog(title=_("%s saving" % self.view_name),
                                           text=_("Enter a view name to save this parametered view"),
                                           default=self.controller.package._idgenerator.get_id(View))
        if ident is not None:
            if not sre.match(r'^[a-zA-Z0-9_]+$', ident):
                advene.gui.util.message_dialog(_("Error: the identifier %s contains invalid characters.") % ident)
                return True

            options, arguments = self.get_save_arguments()
            if options is None and arguments is None:
                # Cancel view saving
                return True

            v=helper.get_id(self.controller.package.views, ident)
            if v is None:
                create=True
                v=self.controller.package.createView(ident=ident, clazz='package')
                v.title=ident
            else:
                # Existing view. Check that it is already an adhoc-view
                if v.content.mimetype != 'application/x-advene-adhoc-view':
                    advene.gui.util.message_dialog(_("Error: the view %s is not an adhoc view.") % ident)
                    return True
                create=False
            v.author=config.data.userid
            v.date=self.controller.get_timestamp()

            self.save_parameters(v.content, options, arguments)
            if create:
                self.controller.package.views.append(v)
                self.controller.notify("ViewCreate", view=v)
            else:
                self.controller.notify("ViewEditEnd", view=v)
        return True

    def get_widget (self):
        """Return the widget."""
        return self.widget

    def build_widget(self):
        return gtk.Label(self.view_name)

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title (self.view_name)

        w=self.get_widget()

        def close_popup(*p):
            window.destroy()
            return True

        # Close the popup window when the widget is destroyed
        w.connect("destroy", close_popup)

        # If the widget defines a buttonbox, we can use it and do not
        # have to define a enclosing VBox (which also solves a problem
        # with the timeline view not being embedable inside a VBox()
        if hasattr(w, 'buttonbox') and w.buttonbox is not None:
            window.add(w)
            window.buttonbox = w.buttonbox
        else:
            vbox = gtk.VBox()
            window.add (vbox)
            vbox.add (w)
            window.buttonbox = gtk.HButtonBox()
            vbox.pack_start(window.buttonbox, expand=False)

        # Insert contextual_actions in buttonbox
        try:
            for label, action in self.contextual_actions:
                b=gtk.Button(label)
                b.connect("clicked", action)
                window.buttonbox.pack_start(b, expand=False)
        except AttributeError:
            pass

        b = gtk.Button(stock=gtk.STOCK_CLOSE)

        if self.controller and self.controller.gui:
            b.connect ("clicked", self.controller.gui.close_view_cb, window, self)
        else:
            b.connect ("clicked", lambda w: window.destroy())
        window.buttonbox.pack_start (b, expand=False)

        window.show_all()

        if self.controller and self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb, window, self)
            self.controller.gui.init_window_size(window, self.view_id)

        return window

class AdhocViewParametersParser(xml.sax.handler.ContentHandler):
    """Parse an AdhocView parameters content.
    """
    def __init__(self):
        self.view_id=None
        self.options={}
        # self.arguments will contain (name, value) tuples, in order
        # to preserve order.
        self.arguments=[]
 
    def startElement(self, name, attributes):
        if name == 'adhoc':
            self.view_id=attributes['id']
        elif name == "option":
            name=attributes['name']
            value=attributes['value']
            self.options[name]=value
        elif name == 'argument':
            name=attributes['name']
            value=attributes['value']
            self.arguments.append( (name, value) )
        else:
            print "Unknown tag %s in AdhocViewParametersParser" % name

    def parse_file(self, name):
        p=xml.sax.make_parser()
        p.setFeature(xml.sax.handler.feature_namespaces, False)
        p.setContentHandler(self)
        p.parse(name)
        return self
