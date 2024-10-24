#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
import logging
logger = logging.getLogger(__name__)

import advene.core.config as config

import re
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GObject
import io
import os
import urllib.request, urllib.parse, urllib.error

from gettext import gettext as _

from advene.model.content import Content
from advene.gui.util import dialog, get_pixmap_button
import advene.util.helper as helper

import xml.etree.ElementTree as ET

class AdhocView:
    """Implementation of the generic parts of AdhocViews.

    For details about the API of adhoc views, see gui.views.viewplugin.
    """
    view_name = "Generic adhoc view"
    view_id = 'generic'
    tooltip = "This view is a generic abstract view that should be derived by real views."

    def __init__(self, controller=None, parameters=None):
        """
        """
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
        # self.buttonbox = Gtk.HButtonBox()

        self._label=self.view_name

        # List of slave views (to be closed on master view close)
        self._slave_views=[]
        self.master_view=None

        # List of couples (object, signal handler id)
        self._signal_ids=[]

        #if parameters is not None:
        #    opt, arg = self.load_parameters(parameters)
        #    self.options.update(opt)
        #
        #self.widget=self.build_widget()

    def register_slave_view(self, v):
        self._slave_views.append(v)
        v.master_view=self

    def unregister_slave_view(self, v):
        try:
            self._slave_views.remove(v)
        except ValueError:
            pass

    def safe_connect(self, obj, *p):
        """Connect a signal handler to a GObject.

        It memorizes the handler id so that it is properly
        disconnected upon view closing.
        """
        i=obj.connect(*p)
        self._signal_ids.append(( obj, i ))
        return i

    def close(self, *p):
        if self.controller and self.controller.gui:
            self.controller.gui.unregister_view (self)
        if self.master_view is not None:
            self.master_view.unregister_slave_view(self)
        for v in self._slave_views:
            v.close()
        for o, i in self._signal_ids:
            o.disconnect(i)
        self.widget.destroy()
        return True

    def message(self, m):
        """Display a message in the statusbar, if present.
        """
        self.log(m)
        if hasattr(self, 'statusbar'):
            context_id = self.statusbar.get_context_id('error')
            message_id = self.statusbar.push(context_id, m)
            # Display the message only 1.5 second
            def undisplay():
                self.statusbar.pop(context_id)
                return False
            GObject.timeout_add(1500, undisplay)

    def log(self, msg, level=None):
        m = ": ".join( (self.view_name, msg) )
        if self.controller:
            self.controller.log(m, level)
        else:
            logger.warning(m)

    def set_label(self, label):
        self._label=label
        p=self.widget.get_parent()
        if isinstance(p, Gtk.Notebook):
            # We are in a notebook.
            label = p.get_tab_label(self.widget)
            if label is not None:
                if isinstance(label, Gtk.Label):
                    label.set_text(label)
                elif isinstance(label, Gtk.HBox):
                    # It may be a HBox with multiple elements. Find the label.
                    # Normally (cf gui.viewbook), the label is in an EventBox
                    label = label.get_children()[1].get_children()[0]
                    label.set_text(label)
        elif isinstance(p, Gtk.VBox):
            # It is a popup window. Set its title.
            p.get_toplevel().set_title(label)

    def load_parameters(self, param):
        """Parse the parameters from a Content object, a tuple or an ElementTree.Element

        It will return a tuple (options, arguments) where options is a
        dictionary and arguments a list of tuples (name, value).

        If param is None, then try to load default options, if they
        exist. They should be stored in
        config.data.advenefile( ('defaults', self.view_id + '.xml'), 'settings')

        In case of problem, it will simply return None, None.
        """
        opt, arg = {}, []

        if param is None:
            # Load default options
            n=config.data.advenefile( ('defaults', self.view_id + '.xml'), 'settings')
            if os.path.exists(n):
                stream=open(n, encoding='utf-8')
                p=AdhocViewParametersParser(stream)
                stream.close()
            else:
                # No default options. Return empty values.
                return opt, arg
        elif isinstance(param, tuple):
            # It is an already parsed tuple. Return it.
            # FIXME: should we post-process it ?
            return param
        elif isinstance(param, Content):
            try:
                m=param.mimetype
            except AttributeError:
                return opt, arg
            if  m != 'application/x-advene-adhoc-view':
                return opt, arg
            p=AdhocViewParametersParser(param.stream)
        elif ET.iselement(param):
            p=AdhocViewParametersParser(param)
        else:
            raise Exception("Unknown parameter type " + str(param))

        if p.view_id != self.view_id:
            self.controller.log(_("Invalid view id"))
            return False

        # Post-processing of options
        for name, value in p.options.items():
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
                elif isinstance(op, int):
                    value=int(value)
                elif isinstance(op, float):
                    value=float(value)
            except (KeyError, AttributeError):
                pass
            opt[name]=value
        return opt, p.arguments

    def parameters_to_element(self, options=None, arguments=None):
        """Generate an ET.Element representing the view and its parameters.
        """
        root=ET.Element(ET.QName(config.data.namespace, 'adhoc'), id=self.view_id)

        if options:
            for n, v in options.items():
                ET.SubElement(root, ET.QName(config.data.namespace, 'option'), name=n, value=urllib.parse.quote(str(v)))
        if arguments:
            for n, v in arguments:
                ET.SubElement(root, ET.QName(config.data.namespace, 'argument'), name=n, value=urllib.parse.quote(str(v)))
        return root

    def save_default_options(self, *p):
        """Save the default options.
        """
        d=config.data.advenefile('defaults', 'settings')
        if not os.path.isdir(d):
            # Create it
            try:
                helper.recursive_mkdir(d)
            except OSError as e:
                self.controller.log(_("Cannot save default options: %s") % str(e))
                return True
        defaults=config.data.advenefile( ('defaults', self.view_id + '.xml'), 'settings')

        options, args=self.get_save_arguments()
        # Do not save package-specific arguments.
        root=self.parameters_to_element(options, [])
        stream=open(defaults, 'w', encoding='utf-8')
        helper.indent(root)
        ET.ElementTree(root).write(stream, encoding='unicode')
        stream.close()
        self.controller.log(_("Default options saved for view %s") % self.view_name)
        return True

    def save_parameters(self, content, options=None, arguments=None):
        """Save the view parameters to a Content object.
        """
        if not isinstance(content, Content):
            raise Exception("save_parameters saves to a Content object")

        content.mimetype='application/x-advene-adhoc-view'

        root=self.parameters_to_element(options, arguments)
        stream=io.StringIO()
        helper.indent(root)
        ET.ElementTree(root).write(stream, encoding='unicode')
        content.setData(stream.getvalue())
        stream.close()
        return True

    def get_elements_from_source(self, source):
        if source == 'global_annotations':
            elements = self.controller.global_package.annotations
        else:
            c = self.controller.build_context()
            try:
                elements = c.evaluateValue(source)
                self.source = source
            except Exception:
                logger.error(_("Error in source evaluation %s"), source, exc_info=True)
                elements = []
        return elements

    def get_save_arguments(self):
        """Method called when saving a parametered view.

        It should return a tuple (options, arguments) where options is
        the options dictionary, and arguments is a list of (name,
        value) tuples).

        If it returns None, None, it means that the view saving is cancelled.
        """
        return self.options, []

    def save_view(self, *p):
        title, ident=self.controller.package._idgenerator.new_from_title(self._label)
        title, ident=dialog.get_title_id(title=_("Saving %s" % self.view_name),
                                         element_title=title,
                                         element_id=ident,
                                         text=_("Enter a view name to save this parametered view"))
        if ident is not None:
            if not re.match(r'^[a-zA-Z0-9_]+$', ident):
                dialog.message_dialog(_("Error: the identifier %s contains invalid characters.") % ident)
                return True

            options, arguments = self.get_save_arguments()
            if options is None and arguments is None:
                # Cancel view saving
                return True

            v=helper.get_id(self.controller.package.views, ident)
            if v is None:
                create=True
                v=self.controller.package.createView(ident=ident, clazz='package')
            else:
                # Existing view. Check that it is already an adhoc-view
                if v.content.mimetype != 'application/x-advene-adhoc-view':
                    dialog.message_dialog(_("Error: the view %s is not an adhoc view.") % ident)
                    return True
                create=False
                self.controller.notify('EditSessionStart', element=v, immediate=True)
            v.title=title
            v.author=config.data.userid
            v.date=helper.get_timestamp()

            self.save_parameters(v.content, options, arguments)
            if create:
                self.controller.package.views.append(v)
                self.controller.notify("ViewCreate", view=v)
            else:
                self.controller.notify("ViewEditEnd", view=v)
                self.controller.notify('EditSessionEnd', element=v)
        return True

    def export_as_static_view(self, ident=None):
        """Propose to export the view as a static view.

        The as_html() method must be implemented.
        """
        title=None
        if ident is None:
            title, ident=self.controller.package._idgenerator.new_from_title("export " + self._label)
            title, ident=dialog.get_title_id(title=_("HTML export"),
                                             text=_("Specify a name for the export view"),
                                             element_title=title,
                                             element_id=ident)
            if ident is None:
                return True
        if title is None:
            title=ident
        # Create the view
        v=self.controller.package.createView(
            ident=ident,
            author=config.data.userid,
            date=helper.get_timestamp(),
            clazz='*',
            content_mimetype="text/html",
            )
        v.title=title
        v.content.data=self.as_html()
        self.controller.package.views.append(v)
        self.controller.notify('ViewCreate', view=v)
        d=dialog.message_dialog(_("View successfully exported as %s.\nOpen it in the web browser ?") % v.title, icon=Gtk.MessageType.QUESTION)
        if d:
            c=self.controller.build_context(here=v)
            self.controller.open_url(c.evaluateValue('package/view/%s/absolute_url' % ident))
        return True

    def get_widget (self):
        """Return the widget."""
        return self.widget

    def build_widget(self):
        return Gtk.Label(label=self.view_name)

    def attach_view(self, menuitem, window):
        def relocate_view(item, v, d):
            # Reference the widget so that it is not destroyed
            if hasattr(v, 'reparent_prepare'):
                v.reparent_prepare()
            wid=v.widget
            wid.hide()
            wid.get_parent().remove(wid)
            if d in ('south', 'east', 'west', 'fareast'):
                v._destination=d
                self.controller.gui.viewbook[d].add_view(v, name=v._label)
                window.disconnect(window.cleanup_id)
                window.destroy()
            wid.show()
            if hasattr(v, 'reparent_done'):
                v.reparent_done()
            return True

        menu=Gtk.Menu()
        for (label, destination) in (
                (_("...embedded east of the video"), 'east'),
                (_("...embedded west of the video"), 'west'),
                (_("...embedded south of the video"), 'south'),
                (_("...embedded at the right of the window"), 'fareast')):
            item = Gtk.MenuItem(label, use_underline=False)
            item.connect('activate', relocate_view, self, destination)
            menu.append(item)

        menu.show_all()
        menu.popup_at_pointer(None)
        return True

    def popup(self, label=None):
        if label is None:
            label=self.view_name
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        window.set_title (label)

        def close_popup(*p):
            window.destroy()
            return True

        # Close the popup window when the widget is destroyed
        self.widget.connect('destroy', close_popup)

        # Buttons specific to the window, that should be removed from
        # the buttonbox on window close (esp. when reparenting to the
        # application)
        window.own_buttons=[]

        # If the widget defines a buttonbox, we can use it and do not
        # have to define a enclosing VBox (which also solves a problem
        # with the timeline view not being embedable inside a VBox()
        if hasattr(self.widget, 'buttonbox') and self.widget.buttonbox is not None:
            window.add(self.widget)
            window.buttonbox = self.widget.buttonbox
        else:
            vbox = Gtk.VBox()
            window.add(vbox)
            window.buttonbox = Gtk.HBox()
            vbox.pack_start(window.buttonbox, False, True, 0)
            vbox.add (self.widget)

        # Insert contextual_actions in buttonbox
        if hasattr(self, 'contextual_actions') and self.contextual_actions:
            menubar=Gtk.MenuBar()
            root=Gtk.MenuItem(_("Actions"))
            menubar.append(root)
            menu=Gtk.Menu()
            root.set_submenu(menu)
            for label, action in self.contextual_actions:
                b=Gtk.MenuItem(label, use_underline=False)
                b.connect('activate', lambda w: action())
                menu.append(b)
            window.buttonbox.pack_start(menubar, False, True, 0)
            window.own_buttons.append(menubar)

        def drag_sent(widget_, context, selection, targetType, eventTime ):
            if targetType == config.data.target_type['adhoc-view-instance']:
                # This is not very robust, but allows to transmit a view instance reference
                selection.set(selection.get_target(), 8, repr(self).encode('utf8'))
                if hasattr(self, 'reparent_prepare'):
                    self.reparent_prepare()
                self.widget.get_parent().remove(self.widget)
                # Do not trigger the close_view_cb handler
                window.disconnect(window.cleanup_id)
                window.destroy()
                return True
            return False

        b=get_pixmap_button('small_attach.png', self.attach_view, window)
        b.set_tooltip_text(_("Click or drag-and-drop to reattach view"))
        b.connect('drag-data-get', drag_sent)
        # The widget can generate drags
        b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                          config.data.get_target_types('adhoc-view-instance'),
                          Gdk.DragAction.LINK)

        window.own_buttons.append(b)
        window.buttonbox.pack_start(b, False, True, 0)

        b=get_pixmap_button('small_close.png')
        if self.controller and self.controller.gui:
            b.connect('clicked', self.controller.gui.close_view_cb, window, self)
        else:
            b.connect('clicked', lambda w: window.destroy())
        window.own_buttons.append(b)
        window.buttonbox.pack_start(b, False, False, 0)

        def remove_own_buttons(w):
            for b in window.own_buttons:
                b.destroy()
            return False

        window.connect('destroy', remove_own_buttons)

        window.buttonbox.show_all()
        window.show_all()

        if hasattr(self, 'reparent_done'):
            self.reparent_done()

        if self.controller and self.controller.gui:
            self.controller.gui.register_view (self)
            window.cleanup_id = window.connect('destroy', self.controller.gui.close_view_cb, window, self)
            self.controller.gui.init_window_size(window, self.view_id)
            window.set_icon_list(self.controller.gui.get_icon_list())

        return window

class AdhocViewParametersParser:
    """Parse an AdhocView parameters content.

    It can be a advene.model.Content or a elementtree.Element
    """
    def __init__(self, source=None):
        self.view_id=None
        self.options={}
        # self.arguments will contain (name, value) tuples, in order
        # to preserve order.
        self.arguments=[]
        if ET.iselement(source):
            self.parse_element(source)
        elif hasattr(source, 'read'):
            # File-like object
            self.parse_file(source)
        else:
            logger.warning("Do not know what to do with %s", source)

    def parse_file(self, fd):
        tree=ET.parse(fd)
        self.parse_element(tree.getroot())

    def parse_element(self, root):
        """Parse an ElementTree Element.
        """
        if root.tag != ET.QName(config.data.namespace, 'adhoc'):
            raise Exception("Invalid adhoc view definition" + root.tag)
        self.view_id=root.attrib['id']

        for e in root:
            if e.tag == ET.QName(config.data.namespace, 'option'):
                name=e.attrib['name']
                value=urllib.parse.unquote(e.attrib['value'])
                self.options[name]=value
            elif e.tag == ET.QName(config.data.namespace, 'argument'):
                name=e.attrib['name']
                value=urllib.parse.unquote(e.attrib['value'])
                self.arguments.append( (name, value) )
            else:
                logger.warning("Unknown tag %s in AdhocViewParametersParser", e.tag)
