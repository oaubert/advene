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
"""Helper GUI classes and methods.

This module provides generic edit forms for the various Advene
elements (Annotation, Relation, AnnotationType, RelationType, Schema,
View, Package).

"""

import advene.core.config as config
from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango

import operator
import os
import re
import struct

try:
    import gi
    gi.require_version('GtkSource', '3.0')
    from gi.repository import GtkSource
except ImportError:
    GtkSource = None

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.view import View
from advene.model.resources import ResourceData
from advene.model.query import Query

from advene.gui.edit.timeadjustment import TimeAdjustment
from advene.gui.views.browser import Browser
from advene.gui.views.tagbag import TagBag
from advene.gui.util import dialog, get_pixmap_toolbutton, name2color, predefined_content_mimetypes
from advene.gui.util.completer import Completer
import advene.gui.popup
from advene.gui.widget import AnnotationRepresentation, RelationRepresentation
from advene.gui.views import AdhocView

import advene.util.helper as helper

# FIXME: handle 'time' type, with hh:mm:ss.mmm display in attributes
_edit_popup_list = []

def get_edit_popup (el, controller=None, editable=True):
    """Return the right edit popup for the given element."""
    if controller and controller.gui:
        for p in controller.gui.edit_popups:
            if p.element == el and p._widget:
                # The edit popup is already open.
                return p
    for c in _edit_popup_list:
        if c.can_edit (el):
            controller.notify('EditSessionStart', element=el, immediate=True)
            return c(el, controller, editable)
    raise TypeError(_("No edit popup available for element %s") % el)

class EditPopupClass (type):
    def __init__ (cls, *args):
        super (EditPopupClass, cls).__init__(*args)
        if hasattr (cls, 'can_edit'):
            _edit_popup_list.append(cls)

class EditElementPopup (AdhocView, metaclass=EditPopupClass):
    """Abstract class for editing Advene elements.

    To create a specialized edit window, define the make_widget
    method, which returns the appropriate widget composed of EditAttributesForm
    and EditTextForm. The make_widget must register its forms via
    self.register_form().

    On validation, the registered forms are asked to update the values
    of their respective elements.
    """

    view_name = _("Edit Window")
    view_id = 'editwindow'

    def __init__ (self, el, controller=None, editable=True):
        """Create an edit window for the given element."""
        super(EditElementPopup, self).__init__(controller=controller)
        self.element = el
        # Override the class property with the element type, so that
        # init_window_size can discriminate against different types
        if isinstance(el, View):
            t=helper.get_view_type(el)
        else:
            t=el.__class__.__name__
        self.view_id="-".join( (EditElementPopup.view_id, t) )
        self.vbox = Gtk.VBox ()
        self.vbox.connect('key-press-event', self.key_pressed_cb)
        self.editable=editable
        # List of defined forms in the window
        self.forms = []
        if controller and controller.gui:
            controller.gui.register_edit_popup(self)
        # Dictionary of callbacks according to keys
        self.key_cb = {}
        self._widget=None
        # callback method invoked upon modification/validation.
        self.callback=None

    @property
    def widget(self):
        """Compatibility property to integrate in the AdhocView framework.
        """
        if self._widget is None:
            vbox=Gtk.VBox()

            tb=Gtk.Toolbar()
            tb.set_style(Gtk.ToolbarStyle.ICONS)

            b=Gtk.ToolButton(Gtk.STOCK_OK)
            b.connect('clicked', self.validate_cb)
            b.set_tooltip_text(_("Apply changes and close the edit window"))
            tb.insert(b, -1)

            b=Gtk.ToolButton (Gtk.STOCK_APPLY)
            b.connect('clicked', self.apply_cb)
            b.set_tooltip_text(_("Apply changes"))
            tb.insert(b, -1)

            self.extend_toolbar(tb)

            vbox.pack_start(tb, False, True, 0)
            vbox.pack_start(self.make_widget(editable=self.editable), True, True, 0)

            def destroy_cb(*p):
                if self.controller and self.controller.gui:
                    self.controller.gui.unregister_edit_popup(self)
                return True
            vbox.connect('destroy', destroy_cb)

            def initial_focus(w, event):
                for f in self.forms:
                    try:
                        if f.get_focus():
                            break
                    except:
                        continue
                vbox.disconnect(self.sig)
                del self.sig
                return False
            self.sig = vbox.connect('draw', initial_focus)

            self._widget=vbox

        return self._widget

    def reparent_done(self):
        if self._widget.get_toplevel() != self.controller.gui.gui.win:
            # In a popup window. Define appropriate shortcuts.
            #self.key_cb[Gdk.KEY_Return] = self.validate_cb
            self.key_cb[Gdk.KEY_Escape] = self.close_cb
            self._widget.get_toplevel().connect('key-press-event', self.key_pressed_cb)
        return True

    def extend_toolbar(self, tb):
        """Extend the widget toolbar.

        Child classes can add their own items to the toolbar.
        """
        return True

    def register_form (self, f):
        self.forms.append(f)

    def refresh(self):
        """Refresh the display if the element has changed.
        """
        for f in self.forms:
            f.refresh()

    def close(self, *p):
        for f in self.forms:
            c=getattr(f, 'close', None)
            if callable(c):
                c()
        return super(EditElementPopup, self).close(*p)

    def can_edit (el):
        """Return True if the class can edit the given element.

        Warning: it is a static method (no self argument), but the
        staticmethod declaration is handled in the metaclass."""
        return False
    can_edit = staticmethod (can_edit)

    def make_widget (self, editable=True, compact=False):
        """Create the editing widget (and return it)."""
        raise Exception ("This method should be defined in the subclasses.")

    def apply_cb (self, button=None, event=None):
        """Method called when applying a form."""
        if not self.editable:
            return True

        for f in self.forms:
            if not f.check_validity():
                return False

        for f in self.forms:
            f.update_element ()

        # The children classes can define a notify method, which will
        # be called upon modification of the element, in order to
        # notify the system of the modification
        try:
            self.notify(self.element)
        except AttributeError:
            pass

        if self.callback is not None:
            self.callback (element=self.element)
        return True

    def validate_cb (self, button=None, event=None):
        """Method called when validating a form."""
        if self.apply_cb(button, event):
            self.controller.notify("ElementEditEnd", element=self.element, comment="Window closed")
            self.close()
        return True

    def apply_and_open(self, b, *p):
        self.apply_cb(b, None)
        # Open in web browser
        ctx=self.controller.build_context()
        url=ctx.evaluateValue('here/absolute_url')
        self.controller.open_url('/'.join( (url, 'view', self.element.id) ))
        return True

    def apply_and_activate(self, b, *p):
        self.apply_cb(b, None)
        self.controller.activate_stbv(self.element)
        p=self.controller.player
        if p.status == p.PauseStatus:
            self.controller.update_status('resume')
        elif p.status == p.PlayingStatus:
            pass
        else:
            self.controller.update_status('start')
        return True

    def get_modified(self):
        return [ f for f in self.forms if f.get_modified() ]

    def set_modified(self, m):
        for f in self.forms:
            self.set_modified(False)

    def close_cb (self, button=None, data=None):
        """Method called when closing a form."""
        if self.get_modified():
            if not dialog.message_dialog(_("Content has been modified. Close anyway and lose data?"), icon=Gtk.MessageType.QUESTION,
                                         modal=True):
                return False
        self.controller.notify("EditSessionEnd", element=self.element, comment="Window closed")
        self.close()
        return True

    def key_pressed_cb (self, widget=None, event=None):
        # Process player shortcuts
        if config.data.preferences['player-shortcuts-in-edit-windows'] and self.controller.gui and self.controller.gui.process_player_shortcuts(widget, event):
            return True

        if event.keyval in self.key_cb:
            return self.key_cb[event.keyval] (widget, event)
        else:
            return False

    def get_title (self):
        """Return the element title."""
        t="%s %s" % (self.element.viewableClass,
                     self.controller.get_title(self.element))
        try:
            t += " [%s]" % self.element.id
        except:
            pass
        return t

    def framed (self, widget, label=""):
        fr = Gtk.Frame ()
        fr.set_label (label)
        fr.add (widget)
        return fr

    def expandable (self, widget, label="", expanded=False):
        fr = Gtk.Expander ()
        fr.set_label (label)
        fr.add(widget)
        fr.set_expanded(expanded)
        return fr

    def edit (self, callback=None, modal=False, label=None):
        """Display the edit window.
        """
        if self.widget.get_parent():
            # The widget is already displayed.
            w=self.widget.get_toplevel()
            w.set_urgency_hint(True)
            return self.element
        self.callback=callback
        self.key_cb[Gdk.KEY_Return] = self.validate_cb
        self.key_cb[Gdk.KEY_Escape] = self.close_cb

        if hasattr(self.element, 'isImported') and self.element.isImported():
            self.editable=False
        elif hasattr(self.element, 'schema') and self.element.schema.isImported():
            self.editable=False

        if self.editable:
            title=_("Edit %s") % self.get_title()
        else:
            title=_("View %s (read-only)") % self.get_title()

        if modal:
            d = Gtk.Dialog(title=title,
                           parent=self.controller.gui.gui.win,
                           flags=Gtk.DialogFlags.DESTROY_WITH_PARENT | Gtk.DialogFlags.MODAL,
                           buttons=( Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                     Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL ))

            d.vbox.add(self.widget)
            d.vbox.show_all()

            d.connect('key-press-event', dialog.dialog_keypressed_cb)

            while True:
                d.show()
                dialog.center_on_mouse(d)
                res=d.run()
                retval=False
                if res == Gtk.ResponseType.OK:
                    retval=self.apply_cb()
                elif res == Gtk.ResponseType.CANCEL:
                    retval=True

                if retval:
                    d.destroy()
                    if self.controller and self.controller.gui:
                        self.controller.gui.unregister_edit_popup(self)
                    break
        else:
            self.popup(label=title)

        return self.element

    def display (self):
        """Display the display window (not editable)."""
        self.popup(label=_("Display %s") % self.get_title())

    def compact(self, callback=None):
        """Display the compact edit window.
        """
        self.key_cb[Gdk.KEY_Return] = self.validate_cb
        self.key_cb[Gdk.KEY_Escape] = self.close_cb

        self.callback=callback
        if hasattr(self.element, 'isImported') and self.element.isImported():
            self.editable=False
        elif hasattr(self.element, 'schema') and self.element.schema.isImported():
            self.editable=False

        tb=Gtk.Toolbar()
        self.extend_toolbar(tb)
        if tb.get_children():
            # There are some items. Display them
            tb.props.icon_size=Gtk.IconSize.SMALL_TOOLBAR
            tb.set_style(Gtk.ToolbarStyle.ICONS)
            self.vbox.pack_start(tb, False, True, 0)
        else:
            tb.destroy()
        w=self.make_widget (editable=self.editable, compact=True)
        self.vbox.add (w)
        self._widget = self.vbox

        def handle_destroy(*p):
            if self.controller and self.controller.gui:
                self.controller.gui.unregister_edit_popup(self)
            return True

        self.vbox.connect('destroy', handle_destroy)

        return self.vbox

    def make_registered_form (self,
                              element=None,
                              fields=(),
                              editables=None,
                              editable=False, # Boolean
                              types=None,
                              labels=None):
        """Shortcut for creating an Attributes form and registering it."""
        f = EditAttributesForm (element, controller=self.controller)
        f.set_attributes (fields)
        if editable and editables is not None:
            f.set_editable (editables)
        if types is not None:
            f.set_types (types)
        if labels is not None:
            f.set_labels (labels)
        self.register_form (f)
        return f

class EditAnnotationPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Annotation)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("AnnotationEditEnd", annotation=element)
        return True

    def goto(self, button=None, direction=1):
        if direction > 0:
            compare = operator.gt
        else:
            compare = operator.lt
        l=[a
           for a in self.element.type.annotations
           if compare(a.fragment.begin, self.element.fragment.begin) ]
        l.sort(key=lambda a: a.fragment.begin, reverse=(direction == -1))
        if l:
            a=l[0]
            self.controller.gui.edit_element(a, destination=getattr(self, '_destination', 'default'))
            # Validate the current one
            self.validate_cb()
        return True

    def extend_toolbar(self, tb):
        if tb.get_children():
            tb.insert(Gtk.SeparatorToolItem(), -1)

        b=get_pixmap_toolbutton(Gtk.STOCK_GO_BACK, self.goto, -1)
        b.set_tooltip_text(_("Apply changes and edit previous annotation of same type"))
        tb.insert(b, -1)

        b=get_pixmap_toolbutton(Gtk.STOCK_GO_FORWARD, self.goto, +1)
        b.set_tooltip_text(_("Apply changes and edit next annotation of same type"))
        tb.insert(b, -1)

        def toggle_highlight(b, ann):
            if b.highlight:
                event="AnnotationActivate"
                label= _("Unhighlight annotation")
                b.highlight=False
            else:
                event="AnnotationDeactivate"
                label=_("Highlight annotation")
                b.highlight=True
                b.set_tooltip_text(label)
            self.controller.notify(event, annotation=ann)
            return True

        b=get_pixmap_toolbutton('highlight.png', toggle_highlight, self.element)
        b.highlight=True
        tb.insert(b, -1)
        return True

    def make_widget (self, editable=True, compact=False):
        vbox = Gtk.VBox ()

        nb=Gtk.Notebook()
        vbox.pack_start(nb, False, True, 0)

        def small_label(t):
            l=Gtk.Label()
            l.set_markup('<span size="x-small">%s</span>' % t)
            return l

        def begin_callback(t):
            for c in self.forms:
                if hasattr(c, 'contentform') and hasattr(c.contentform, 'set_begin'):
                    c.contentform.set_begin(t)
            return True

        f = EditFragmentForm(element=self.element.fragment, controller=self.controller,
                             begin_callback=begin_callback)
        self.register_form (f)
        nb.append_page(f.get_view(compact=compact), small_label(_("Fragment")))

        # Annotation data
        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'type',
                                               'author', 'date'),
                                       types={ 'type': 'advene' },
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'type':   _('Type'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        nb.append_page(f.get_view(), small_label(_("Metadata")))

        f = EditRelationsForm(element=self.element, controller=self.controller)
        self.register_form(f)
        nb.append_page(f.get_view(compact=compact), small_label(_("Relations")))

        f = EditTagForm(element=self.element, controller=self.controller, editable=editable)
        self.register_form(f)
        nb.append_page(f.get_view(compact=compact), small_label(_("Tags")))

        f = EditContentForm(self.element.content, controller=self.controller,
                            mimetypeeditable=False, parent=self.element)
        f.set_editable(editable)
        t = f.get_view(compact=compact)
        self.register_form(f)
        vbox.pack_start(t, True, True, 0)


        def select_default(widget):
            widget.set_current_page(0)
            return False
        nb.connect_after('realize', select_default)

        return vbox

class EditRelationPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Relation)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("RelationEditEnd", relation=element)
        return True

    def make_widget (self, editable=True, compact=False):
        vbox = Gtk.VBox ()

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'type',
                                               'author', 'date'),
                                       types={ 'type': 'advene' },
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'type':   _('Type'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        ex=self.expandable(f.get_view(), _("Metadata"), expanded=False)
        vbox.pack_start(ex, False, True, 0)

        def button_press_handler(widget, event, annotation):
            if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
                menu=advene.gui.popup.Menu(annotation, controller=self.controller)
                menu.popup()
                return True
            if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                self.controller.gui.edit_element(annotation)
                return True
            return False

        # FIXME: make it possible to edit the members list (drag and drop ?)
        hb = Gtk.HBox()
        for a in self.element.members:
            b = AnnotationRepresentation(a, controller=self.controller)
            b.set_alignment(0, 0)
            hb.pack_start(b, False, True, 0)
        hb.show_all()
        vbox.pack_start(self.framed(hb, _("Members")), False, False, 0)

        # Tags
        f = EditTagForm(element=self.element, controller=self.controller, editable=editable)
        self.register_form(f)
        vbox.pack_start (f.get_view(), False, False, 0)

        # Relation content
        f = EditContentForm(self.element.content, controller=self.controller,
                            mimetypeeditable=False, parent=self.element)
        f.set_editable(editable)
        t = f.get_view()
        self.register_form(f)
        # If there is content, expand the content widget
        if self.element.content.data:
            exp=True
        else:
            exp=False
        vbox.pack_start(self.expandable(t, _("Content"), expanded=exp), True, True, 0)

        return vbox

class EditViewPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, View)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("ViewEditEnd", view=element)
        return True

    def extend_toolbar(self, tb):
        t = helper.get_view_type(self.element)
        if t == 'static' and self.element.matchFilter['class'] in ('package', '*'):
            b = get_pixmap_toolbutton( 'web.png', self.apply_and_open)
            b.set_tooltip_text(_("Apply changes and visualise in web browser"))
            tb.insert(b, -1)
            self.key_cb[Gdk.KEY_F5] = self.apply_and_open
        elif t == 'dynamic':
            b = get_pixmap_toolbutton( Gtk.STOCK_MEDIA_PLAY, self.apply_and_activate)
            b.set_tooltip_text(_("Apply changes and activate the view"))
            tb.insert(b, -1)
            self.key_cb[Gdk.KEY_F5] = self.apply_and_activate
        return True

    def make_widget (self, editable=True, compact=False):
        vbox = Gtk.VBox ()

        f = EditAttributeForm(title=_("Title (name)"),
                              element=self.element, name='title',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("Name of the view"))
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri',
                                               'author', 'date'),
                                       types={ 'type': 'advene' },
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (self.expandable(f.get_view (), _("Metadata"),
                                         expanded=False), False, False, 0)

        if config.data.preferences['expert-mode']:
            # matchFilter
            f = self.make_registered_form (element=self.element.matchFilter,
                                           fields=('class', 'type'),
                                           editable=editable,
                                           editables=('class', 'type'),
                                           labels={'class': _('Class'),
                                                   'type':  _('Type')}
                                           )
            vbox.pack_start (self.expandable(f.get_view (), _("Match Filter"), expanded=False),
                             False, False, 0)

        # Tags (not tags in view)
        #f = EditTagForm(element=self.element, controller=self.controller, editable=editable)
        #self.register_form(f)
        #ex=self.expandable(f.get_view(), _("Tags"), expanded=not compact)
        #vbox.pack_start (ex, False, False, 0)

        # View content

        f = EditContentForm (self.element.content, controller=self.controller,
                             mimetypeeditable=editable, parent=self.element)
        f.set_editable (editable)
        t = f.get_view ()
        self.register_form (f)
        vbox.pack_start (self.framed(t, _("Content")), True, True, 0)

        return vbox

class EditQueryPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Query)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("QueryEditEnd", query=element)
        return True

    def apply_and_execute(self, b):
        self.apply_cb(b, None)
        try:
            res, q = self.controller.evaluate_query(self.element)
            self.controller.gui.open_adhoc_view('interactiveresult',
                                                query=self.element,
                                                result=res,
                                                destination='east')
        except Exception as e:
            self.controller.log(_('Exception in query: %s') % str(e))
        return True

    def extend_toolbar(self, tb):
        b = get_pixmap_toolbutton( 'gtk-execute', self.apply_and_execute)
        b.set_tooltip_text(_("Validate and run query on package"))
        tb.insert(b, -1)
        return True

    def make_widget (self, editable=True, compact=False):
        vbox = Gtk.VBox ()

        f = EditAttributeForm(title=_("Title (name)"),
                              element=self.element, name='title',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("Name of the query"))
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (self.expandable(f.get_view (),  _("Metadata"), expanded=False),
                         False, False, 0)

        f = EditContentForm (self.element.content, controller=self.controller,
                             mimetypeeditable=editable, parent=self.element)
        f.set_editable (editable)
        t = f.get_view ()
        self.register_form (f)
        vbox.pack_start (self.framed(t, _("Content")), True, True, 0)

        return vbox

class EditPackagePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Package)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        # Side effect of the notify method: we use it to update the
        # appropriate attributes of the package.
        self.controller.set_default_media(element.media,
                                          package=element)
        d=element.getMetaData (config.data.namespace, "duration")
        if d:
            try:
                d=int(d)
            except ValueError:
                d=0
            element.cached_duration = d
        else:
            element.cached_duration = 0
        self.controller.notify("PackageEditEnd", package=element)
        return True

    def make_widget (self, editable=False, compact=False):
        vbox=Gtk.VBox()

        sg=Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        f = EditAttributeForm(title=_("Title (name)"),
                              element=self.element, name='title',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("Name of the package"),
                              sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = self.make_registered_form (element=self.element,
                                       fields=('uri',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date',),
                                       labels={'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )

        vbox.pack_start (self.expandable(f.get_view (),  _("Metadata"), expanded=False),
                         False, False, 0)

        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable,
                         tooltip=_("Textual description of the package"),
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Default dynamic view"),
                         element=self.element, name='default_stbv',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("Dynamic view to activate on package load"),
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Default static view"),
                         element=self.element, name='default_utbv',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("Static view to open on package load"),
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Default adhoc view"),
                         element=self.element, name='default_adhoc',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("Adhoc view to open on package load"),
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Cached duration"),
                         element=self.element, name='duration',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("Cached duration in ms"),
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Mediafile"),
                         element=self.element, name='mediafile',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("Location of associated media file"),
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        return vbox

class EditSchemaPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Schema)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("SchemaEditEnd", schema=element)
        return True

    def make_widget (self, editable=True, compact=False):
        vbox=Gtk.VBox()

        sg=Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        f = EditAttributeForm(title=_("Title (name)"),
                              element=self.element, name='title',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("Name of the schema"),
                              sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (self.expandable(f.get_view (),  _("Metadata"), expanded=False),
                         False, False, 0)

        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable,
                         tooltip=_("Textual description of the package"),
                         focus=True,
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Color"),
                         element=self.element, name='color',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("TALES expression returning a color for the element"),
                         type='color',
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        if config.data.preferences['expert-mode']:
            f = EditMetaForm(title=_("Item color"),
                             element=self.element, name='item_color',
                             namespaceid='advenetool', controller=self.controller,
                             editable=editable,
                             tooltip=_("TALES expression returning a color for the items contained by the element"),
                             type='color',
                             sizegroup=sg)
            self.register_form(f)
            vbox.pack_start(f.get_view(), False, False, 0)

        return vbox

class EditAnnotationTypePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, AnnotationType)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("AnnotationTypeEditEnd", annotationtype=element)
        return True

    def make_widget (self, editable=False, compact=False):
        vbox = Gtk.VBox()

        sg=Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        f = EditAttributeForm(title=_("Title (name)"),
                              element=self.element, name='title',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("Name of the type"),
                              sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date'),
                                               }
                                       )
        vbox.pack_start(self.expandable(f.get_view(),  _("Metadata"), expanded=False), False, False, 0)

        f = EditAttributeForm(title=_("MIME Type"),
                              element=self.element, name='mimetype',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("MIMEType of the content"),
                              type='mimetype',
                              sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable,
                         tooltip=_("Textual description of the package"),
                         focus=True,
                         sizegroup=sg)

        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Color"),
                         element=self.element, name='color',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("TALES expression returning a color for the element"),
                         type='color',
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        abox=Gtk.VBox()
        f = EditMetaForm(title=_("Representation"),
                         element=self.element, name='representation',
                         controller=self.controller,
                         editable=editable,
                         tooltip=_("TALES expression used to get a compact representation of the annotations"),
                         elements=[ ("here/content/parsed/%s" % name, _("Display %s key") % name)
                                    for name in getattr(self.element, '_fieldnames', []) ],
                         sizegroup=sg)
        self.register_form(f)
        abox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Item color"),
                         element=self.element, name='item_color',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("TALES expression returning a color for the items contained by the element"),
                         type='color',
                         sizegroup=sg)
        self.register_form(f)
        abox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Completions"),
                         element=self.element, name='completions',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable,
                         tooltip=_("Space-separated list of words used for content completion"),
                         sizegroup=sg)
        self.register_form(f)
        abox.pack_start(f.get_view(), False, False, 0)


        vbox.pack_start(self.expandable(abox, label=_("Advanced"), expanded=False), False, False, 0)

        return vbox

class EditRelationTypePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, RelationType)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("RelationTypeEditEnd", relationtype=element)
        return True

    def make_widget (self, editable=False, compact=False):
        vbox=Gtk.VBox()

        sg=Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        f = EditAttributeForm(title=_("Title (name)"),
                              element=self.element, name='title',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("Name of the type"),
                              sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditAttributeForm(title=_("MIME Type"),
                              element=self.element, name='mimetype',
                              controller=self.controller,
                              editable=editable,
                              tooltip=_("MIMEType of the content"),
                              type='mimetype',
                              sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date', 'title'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date'),
                                               }
                                       )
        vbox.add(self.expandable(f.get_view(),  _("Metadata"), expanded=False))

        members=[ ('#'+at.id, self.controller.get_title(at)) for at in self.controller.package.annotationTypes ]
        members.append( ('', _("Any annotation type")) )
        f = EditElementListForm(
            title=_("Members"),
            element=self.element,
            field='hackedMemberTypes',
            members=members,
            controller=self.controller,
            editable=editable)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable,
                         tooltip=_("Textual description of the package"),
                         focus=True,
                         sizegroup=sg)

        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        f = EditMetaForm(title=_("Color"),
                         element=self.element, name='color',
                         controller=self.controller,
                         editable=editable,
                         tooltip=_("TALES expression specifying a color"),
                         type='color',
                         sizegroup=sg)
        self.register_form(f)
        vbox.pack_start(f.get_view(), False, False, 0)

        return vbox

class EditResourcePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, ResourceData)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("ResourceEditEnd", resource=element)
        return True

    def make_widget (self, editable=True, compact=False):
        vbox = Gtk.VBox ()

        # Resource data
        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'mimetype'),
                                       #'author', 'date'),
                                       editable=editable,
                                       editables=(),
                                       labels={'id':     _('Id'),
                                               'mimetype':   _('MIMEType'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (f.get_view (), False, False, 0)

        f = EditContentForm(self.element, controller=self.controller,
                            mimetypeeditable=False, parent=self.element)
        f.set_editable(editable)
        t = f.get_view()
        self.register_form(f)
        vbox.pack_start(self.framed(t, _("Content")), True, True, 0)

        return vbox

class EditForm(object):
    """Generic EditForm class.

    This class defines the method that an EditForm is expected to
    implement.
    """
    def close(self):
        return True

    def check_validity(self):
        """Checks the validity of the data."""
        return True

    def update_element (self):
        """Update the element from the values in the form.

        This method is called upon form validation, to actually update
        the element with the values given in the form.
        """
        raise Exception ("This method should be implemented in subclasses.")

    def get_modified(self):
        """Checks wether the content is different from its original value.

        Not all EditForms can implement this. But it is tested
        in the close_cb callback: if an EditForm is_modified(), then
        we should ask for confirmation before closing.
        """
        return False

    def set_modified(self, is_modified):
        return is_modified

    def refresh(self):
        """Update the representation wrt. the element value.
        """
        pass

    def get_view (self, compact=False):
        """Return the view (gtk Widget) for this form.
        """
        raise Exception ("This method should be implemented in subclasses.")

    def metadata_get_method(self, element, data, namespaceid='advenetool'):
        namespace = config.data.namespace_prefix[namespaceid]
        def get_method():
            expr=element.getMetaData(namespace, data)
            if expr is None:
                expr=""
            if re.match('^\s+$', expr):
                # The field can contain just a newline or whitespaces, which will be then ignored
                #try:
                #    i=element.id
                #except AttributeError:
                #    i=str(element)
                #print "Messed up metadata for %s (%s)" % (i, expr)
                expr=""
            return expr
        return get_method

    def metadata_set_method(self, element, data, namespaceid='advenetool'):
        namespace = config.data.namespace_prefix[namespaceid]
        def set_method(value):
            if value is None or value == "":
                value=""
            if re.match('^\s+', value):
                #try:
                #    i=element.id
                #except AttributeError:
                #    i=str(element)
                #print "Messed up value for %s" % element.id
                value=""
            element.setMetaData(namespace, data, str(value))
            return True
        return set_method

class ContentHandler(EditForm):
    """Content Handler form.

    It is an EditForm with a specialized constructor (see __init__
    below), and a can_handle static method.

    can_handle returns an integer between 0 and 100. 0 means that it
    cannot handle the content. 100 means that it must absolutely
    handle the content.

    Specialized builtin content handlers generally return 80, which
    leaves space for user-defined handlers.

    Generic content handlers return 50.
    """
    def can_handle(mimetype):
        return 0
    can_handle=staticmethod(can_handle)

    def __init__ (self, content, controller=None, **kw):
        self.element=content
        self.controller=controller

class EditContentForm(EditForm):
    """Create an edit form for the given content.
    """
    def __init__ (self, element, controller=None, parent=None,
                  editable=True, mimetypeeditable=True, **kw):
        # self.element is a Content object
        self.element = element
        self.controller=controller

        # Parent context, sometimes needed
        self.parent=parent
        # self.contentform will be an appropriate EditForm
        # (EditTextForm,EditRuleSetForm,...)
        self.contentform = None
        # self.mimetype is a Gtk.Entry
        self.mimetype = None

        # Allow the edition of mimetype for contents
        # but not for the special case of Ruleset/Query
        self.editable = editable

        self.mimetypeeditable = (mimetypeeditable
                                 and editable
                                 and not (self.element.mimetype in
                                          ('application/x-advene-ruleset',
                                           'application/x-advene-simplequery')))

    def close(self):
        self.contentform.close()
        return True

    def set_editable (self, bool):
        self.editable = bool

    def get_focus(self):
        try:
            return self.contentform.get_focus()
        except:
            return False

    def check_validity(self):
        if self.contentform is None:
            return True
        else:
            return self.contentform.check_validity()

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if self.contentform is None:
            return True
        if self.mimetypeeditable and not hasattr(self, 'mimetype'):
            self.element.mimetype = self.mimetype.get_current_element()
        self.contentform.update_element()
        return True

    def get_modified(self):
        # FIXME: more complete tests should be done, but this one
        # covers the main case.
        return self.contentform.get_modified()

    def set_modified(self, b):
        self.contentform.set_modified(b)

    def refresh(self):
        if self.mimetype is not None:
            self.mimetype.set_current_element(self.element.mimetype)
        self.contentform.refresh()

    def get_view (self, compact=False):
        """Generate a view widget for editing content."""
        vbox = Gtk.VBox()

        if self.element.mimetype == 'application/x-advene-ruleset':
            compact=True

        if not compact and config.data.preferences['expert-mode']:
            hbox = Gtk.HBox()
            l=Gtk.Label(label=_("MIME Type"))
            hbox.pack_start(l, False, True, 0)

            mt=self.element.mimetype
            # Is the current value in the predefined list?
            data=[ tupl
                   for tupl in predefined_content_mimetypes
                   if tupl[0] == mt ]
            if not data:
                # Not yet predefined. Add its raw value.
                current=(mt, mt)
                predefined_content_mimetypes.append(current)
            else:
                current=data[0]

            if self.mimetypeeditable:
                l=predefined_content_mimetypes
            else:
                l=[ current ]

            self.mimetype=dialog.list_selector_widget(members=l,
                                                      preselect=mt,
                                                      entry=self.mimetypeeditable)

            hbox.pack_start(self.mimetype, True, True, 0)

            vbox.pack_start(hbox, False, True, 0)
        else:
            self.mimetype=None

        handler = config.data.get_content_handler(self.element.mimetype)
        if handler is None:
            self.contentform=None
            vbox.add(Gtk.Label(label=_("Error: cannot find a content handler for %s")
                               % self.element.mimetype))
        else:
            self.contentform=handler(self.element,
                                     controller=self.controller,
                                     parent=self.parent)

        self.contentform.set_editable(self.editable)
        self.content_handler_widget = self.contentform.get_view(compact=compact)
        vbox.add(self.content_handler_widget)
        self.content_handler_widget.grab_focus()
        return vbox

class TextContentHandler (ContentHandler):
    """Create a textview edit form for the given element.
    """
    def can_handle(mimetype):
        res=0
        if 'text' in mimetype:
            res=70
        if 'xml' in mimetype:
            res=60
        if mimetype == 'text/plain' or mimetype in config.data.text_mimetypes:
            res=80
        return res
    can_handle=staticmethod(can_handle)

    def __init__ (self, element, controller=None, parent=None, **kw):
        self.element = element
        self.controller=controller
        self.parent=parent
        self.editable = True
        self.fname=None
        self.view = None

    def get_focus(self):
        self.view.grab_focus()
        return True

    def set_editable (self, boolean):
        self.editable = boolean

    def refresh(self):
        self.view.get_buffer().set_text(self.element.data)
        self.set_modified(False)

    def get_modified(self):
        return self.view.get_buffer().get_modified()

    def set_modified(self, b):
        self.view.get_buffer().set_modified(b)

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False
        buf = self.view.get_buffer()
        start_iter, end_iter = buf.get_bounds ()
        text = buf.get_text(start_iter, end_iter, False)
        self.element.data = text
        self.set_modified(False)
        return True

    def key_pressed_cb (self, win, event):
        # Process player shortcuts
        # Desactivated, since control+arrows navigation and tab
        # insertion is common in text editing.
        #if self.controller.gui and self.controller.gui.process_player_shortcuts(win, event):
        #    return True
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_s:
                self.content_save()
                return True
            elif event.keyval == Gdk.KEY_o:
                self.content_open()
                return True
            elif event.keyval == Gdk.KEY_r:
                self.content_reload()
                return True
            elif event.keyval == Gdk.KEY_i:
                self.browser_open()
                return True
        return False

    def browser_open(self, b=None):
        def callback(e):
            if e is not None:
                if e.startswith('string:'):
                    e=e.replace('string:', '')
                b=self.view.get_buffer()
                b.insert_at_cursor(str(e))
            return True
        browser = Browser(element=self.element,
                          controller=self.controller,
                          callback=callback)
        browser.popup()
        return True

    def content_set(self, c):
        b=self.view.get_buffer()
        b.delete(*b.get_bounds ())
        b.set_text(c)
        return True

    def content_reload(self, b=None):
        self.content_open(fname=self.fname)
        return True

    def content_open(self, b=None, fname=None):
        if fname is None:
            fname=dialog.get_filename(default_file=self.fname)
        if fname is not None:
            try:
                with open(fname, 'r', encoding='utf-8') as f:
                    lines="".join(f.readlines())
                    self.content_set(data)
                    self.fname=fname
            except IOError as e:
                dialog.message_dialog(
                    _("Cannot read the data:\n%s") % str(e),
                    icon=Gtk.MessageType.ERROR)
                return True
        return True

    def content_save(self, b=None, fname=None):
        if fname is None:
            default=None
            if self.parent is not None:
                try:
                    default=self.parent.id + '.txt'
                except AttributeError:
                    pass
            fname=dialog.get_filename(title=_("Save content to..."),
                                               action=Gtk.FileChooserAction.SAVE,
                                               button=Gtk.STOCK_SAVE,
                                               default_file=default)
        if fname is not None:
            if os.path.exists(fname):
                os.rename(fname, fname + '~')
            try:
                b=self.view.get_buffer()
                with open(fname, 'w', encoding='utf-8') as f:
                    f.write(b.get_text(*b.get_bounds() + ( False, )))
                self.fname=fname
            except IOError as e:
                dialog.message_dialog(
                    _("Cannot save the data:\n%s") % str(e),
                    icon=Gtk.MessageType.ERROR)
                return True
        return True

    def get_view (self, compact=False):
        """Generate a view widget for editing text attribute."""
        vbox=Gtk.VBox()

        if not compact:
            tb = self.toolbar = Gtk.Toolbar()
            vbox.toolbar=tb
            tb.set_style(Gtk.ToolbarStyle.ICONS)

            b=Gtk.ToolButton(Gtk.STOCK_OPEN)
            b.set_tooltip_text(_("Open a file (C-o)"))
            b.connect('clicked', self.content_open)
            tb.insert(b, -1)

            b=Gtk.ToolButton(Gtk.STOCK_SAVE)
            b.set_tooltip_text(_("Save to a file (C-s)"))
            b.connect('clicked', self.content_save)
            tb.insert(b, -1)

            b=Gtk.ToolButton(Gtk.STOCK_REFRESH)
            b.set_tooltip_text(_("Reload the file (C-r)"))
            b.connect('clicked', self.content_reload)
            tb.insert(b, -1)

            if config.data.preferences['expert-mode']:
                b=get_pixmap_toolbutton('browser.png', self.browser_open)
                b.set_tooltip_text(_("Insert a value from the browser (C-i)"))
                tb.insert(b, -1)

            vbox.pack_start(tb, False, True, 0)

        if GtkSource is not None:
            textview=GtkSource.View.new_with_buffer(GtkSource.Buffer())
            b=textview.get_buffer()
            m=GtkSource.LanguageManager.get_default()
            if m:
                b.set_language(m.guess_language(content_type=self.element.mimetype))
                b.set_highlight_syntax(True)
            textview.set_editable (self.editable)
            textview.set_wrap_mode (Gtk.WrapMode.CHAR)
            textview.set_auto_indent(True)
            b.begin_not_undoable_action()
            b.set_text(self.element.data)
            b.end_not_undoable_action()
            textview.connect('key-press-event', self.key_pressed_cb)

            if not compact:
                b_undo = Gtk.ToolButton(Gtk.STOCK_UNDO)
                tb.insert(b_undo, -1)

                b_redo = Gtk.ToolButton(Gtk.STOCK_REDO)
                tb.insert(b_redo, -1)

                def undo_cb(buf):
                    b_undo.set_sensitive(buf.can_undo())
                    b_redo.set_sensitive(buf.can_redo())
                    return True

                def undo(b):
                    b=textview.get_buffer()
                    if b.can_undo():
                        b.undo()
                    undo_cb(b)
                    return True

                def redo(b):
                    b=textview.get_buffer()
                    if b.can_redo():
                        b.redo()
                    undo_cb(b)
                    return True

                textview.get_buffer().connect('changed', undo_cb)
                b_undo.connect('clicked', undo)
                b_redo.connect('clicked', redo)
                undo_cb(textview.get_buffer())
        else:
            textview = Gtk.TextView ()
            textview.set_editable (self.editable)
            textview.set_wrap_mode (Gtk.WrapMode.CHAR)
            textview.get_buffer().set_text(self.element.data)
            textview.connect('key-press-event', self.key_pressed_cb)
        self.view = textview
        self.set_modified(False)

        col=self.controller.get_element_color(self.parent)
        if col is not None:
            color=name2color(col)
            self.view.modify_base(Gtk.StateType.NORMAL, color)

        # Hook the completer component
        if hasattr(self.parent.rootPackage, '_indexer'):
            completer=Completer(textview=self.view,
                                controller=self.controller,
                                element=self.parent,
                                indexer=self.parent.rootPackage._indexer)

        scroll_win = Gtk.ScrolledWindow ()
        scroll_win.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll_win.add(textview)

        vbox.add(scroll_win)
        return vbox
config.data.register_content_handler(TextContentHandler)

class GenericContentHandler (ContentHandler):
    """Generic content handler form.

    It allows to load/save the content to/from a file.
    """
    def can_handle(mimetype):
        res=50
        return res
    can_handle=staticmethod(can_handle)

    def __init__ (self, element, controller=None, parent=None, **kw):
        self.element = element
        self.controller=controller
        self.editable = True
        self.fname=None
        self.view = None
        self.parent=None
        self.data=self.element.data

    def set_editable (self, boolean):
        self.editable = boolean

    def set_filename(self, fname):
        self.filename_entry.set_text(fname)
        self.fname = fname
        return fname

    def update_preview(self):
        self.preview.foreach(self.preview.remove)
        if self.element.mimetype.startswith('image/'):
            i=Gtk.Image()
            if self.fname is None:
                # Load the element content
                loader = GdkPixbuf.PixbufLoader()
                try:
                    loader.write (self.data)
                    loader.close ()
                    pixbuf = loader.get_pixbuf ()
                except GObject.GError:
                    # The PNG data was invalid.
                    pixbuf=GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))
            else:
                pixbuf=GdkPixbuf.Pixbuf.new_from_file(self.fname)
            i.set_from_pixbuf(pixbuf)
            self.preview.add(i)
            i.show()
        return True

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False
        self.element.data=self.data
        return True

    def key_pressed_cb (self, win, event):
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_s:
                self.content_save()
                return True
            elif event.keyval == Gdk.KEY_o:
                self.content_open()
                return True
            elif event.keyval == Gdk.KEY_r:
                self.content_reload()
                return True
        return False

    def content_open(self, b=None, fname=None):
        if fname is None:
            fname=dialog.get_filename(default_file=self.fname)
        if fname is not None:
            try:
                f=open(fname, 'rb')
            except IOError as e:
                dialog.message_dialog(
                    _("Cannot read the data:\n%s") % str(e),
                    icon=Gtk.MessageType.ERROR)
                return True
            self.set_filename(fname)

            size=os.stat(self.fname).st_size
            self.data = f.read(size + 2)
            f.close()

            self.update_preview()
        return True

    def content_reload(self, b=None):
        self.content_open(fname=self.fname)
        self.update_preview()
        return True

    def content_save(self, b=None, fname=None):
        if fname is None:
            default=None
            if self.parent is not None:
                try:
                    default=self.parent.id + '.txt'
                except AttributeError:
                    pass
            fname=dialog.get_filename(title=_("Save content to..."),
                                               action=Gtk.FileChooserAction.SAVE,
                                               button=Gtk.STOCK_SAVE,
                                               default_file=default)
        if fname is not None:
            if os.path.exists(fname):
                os.rename(fname, fname + '~')
            try:
                f=open(fname, 'wb')
                f.write(self.data)
                f.close()
            except IOError as e:
                dialog.message_dialog(
                    _("Cannot save the data:\n%s") % str(e),
                    icon=Gtk.MessageType.ERROR)
                return True
            self.set_filename(fname)
        return True

    def get_view (self, compact=False):
        """Generate a view widget for editing any content (by saving/loading to/from a file)."""
        vbox=Gtk.VBox()

        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        b=Gtk.ToolButton(Gtk.STOCK_OPEN)
        b.set_tooltip_text(_("Open a file (C-o)"))
        b.connect('clicked', self.content_open)
        tb.insert(b, -1)

        b=Gtk.ToolButton(Gtk.STOCK_SAVE)
        b.set_tooltip_text(_('Save to a file (C-s)'))
        b.connect('clicked', self.content_save)
        tb.insert(b, -1)

        b=Gtk.ToolButton(Gtk.STOCK_REFRESH)
        b.set_tooltip_text(_('Reload the file (C-r)'))
        b.connect('clicked', self.content_reload)
        tb.insert(b, -1)

        tb.show_all()
        vbox.pack_start(tb, False, True, 0)

        self.filename_entry = Gtk.Entry()
        self.filename_entry.set_editable (self.editable)
        vbox.connect('key-press-event', self.key_pressed_cb)

        vbox.pack_start(self.filename_entry, False, True, 0)
        self.preview=Gtk.VBox()
        vbox.pack_start(self.preview, True, True, 0)
        self.update_preview()
        return vbox
config.data.register_content_handler(GenericContentHandler)

class EditFragmentForm(EditForm):
    def __init__(self, element=None, controller=None, editable=True, begin_callback=None):
        self.begin=None
        self.end=None
        self.element = element
        self.controller = controller
        self.editable=editable
        self.begin_callback=begin_callback

    def check_validity(self):
        if self.begin.value >= self.end.value:
            dialog.message_dialog(_("Begin time is greater than end time"),
                                           icon=Gtk.MessageType.ERROR)
            return False
        else:
            return True

    def refresh(self):
        self.begin.value=self.element.begin
        self.begin.update_display()
        self.end.value=self.element.end
        self.end.update_display()

    def update_element(self):
        if not self.editable:
            return False
        if not self.check_validity():
            return False
        self.element.begin=self.begin.value
        self.element.end=self.end.value
        return True

    def get_view(self, compact=False):
        hbox=Gtk.HBox()

        self.begin=TimeAdjustment(value=self.element.begin,
                                  controller=self.controller,
                                  editable=self.editable,
                                  compact=compact,
                                  callback=self.begin_callback)
        f=Gtk.Frame()
        f.set_label(_("Begin"))
        f.add(self.begin.get_widget())
        hbox.pack_start(f, False, True, 0)

        self.end=TimeAdjustment(value=self.element.end,
                                controller=self.controller,
                                editable=self.editable,
                                compact=compact)
        f=Gtk.Frame()
        f.set_label(_("End"))
        f.add(self.end.get_widget())
        hbox.pack_start(f, False, True, 0)

        return hbox

class EditGenericForm(EditForm):
    def __init__(self, title=None, getter=None, setter=None,
                 controller=None, editable=True, tooltip=None, type=None, elements=None,
                 focus=False, sizegroup=None):
        self.title=title
        self.getter=getter
        self.setter=setter
        self.controller=controller
        self.editable=editable
        self.entry=None
        self.view=None
        self.sizegroup=sizegroup
        self.tooltip=tooltip
        self.type=type
        # List of (value, label) items
        self.elements=elements
        self.focus=focus

    def get_focus(self):
        if self.focus:
            self.entry.grab_focus()
            return True
        else:
            return False

    def get_view(self, compact=False):
        hbox = Gtk.HBox()

        l=Gtk.Label(label=self.title)
        hbox.pack_start(l, False, True, 0)
        if self.sizegroup is not None:
            self.sizegroup.add_widget(l)

        v=self.getter()
        if v is None:
            v=""
        if self.type == 'mimetype':
            # Is the current value in the predefined list?
            data=[ tupl
                   for tupl in predefined_content_mimetypes
                   if tupl[0] == v ]
            if not data:
                # Not yet predefined. Add its raw value.
                current=(v, v)
                predefined_content_mimetypes.append(current)
            else:
                current=data[0]

            if self.editable:
                l=predefined_content_mimetypes
            else:
                l=[ current ]
            self.entry=dialog.list_selector_widget(members=l,
                                                   preselect=v,
                                                   entry=self.editable)
        elif self.elements:
            self.entry=dialog.list_selector_widget(members=self.elements,
                                                   preselect=v,
                                                   entry=self.editable)
        else:
            self.entry=Gtk.Entry()
            self.entry.set_text(v)
            self.entry.set_editable(self.editable)

        if self.tooltip:
            self.entry.set_tooltip_text(self.tooltip)

        hbox.pack_start(self.entry, True, True, 0)

        if self.type == 'color':
            if not config.data.preferences['expert-mode'] and (not v or v.startswith('string:')):
                # Hide the text entry if not in expert-mode and if the
                # current color is statically defined or empty
                self.entry.hide()
                self.entry.set_no_show_all(True)
            b=Gtk.ColorButton()
            b.set_use_alpha(False)

            if v:
                c=self.controller.build_context()
                try:
                    color=c.evaluateValue(v)
                    gtk_color=Gdk.color_parse(color)
                    b.set_color(gtk_color)
                except:
                    pass

            def handle_color(button):
                col=button.get_color()
                self.entry.set_text("string:#%04x%04x%04x" % (col.red, col.green, col.blue))
                return True

            b.connect('color-set', handle_color)
            hbox.pack_start(b, False, True, 0)

            def drag_received(widget, context, x, y, selection, targetType, time):
                """Handle the drop of a color.
                """
                if targetType == config.data.target_type['color']:
                    # The structure consists in 4 unsigned shorts: r, g, b, opacity
                    (r, g, b, opacity)=struct.unpack('HHHH', selection.get_data())
                    self.entry.set_text("string:#%04x%04x%04x" % (r, g, b))
                return False

            # Allow the entry to get drops of type application/x-color
            self.entry.connect('drag-data-received', drag_received)
            self.entry.drag_dest_set(Gtk.DestDefaults.MOTION |
                                     Gtk.DestDefaults.HIGHLIGHT |
                                     Gtk.DestDefaults.ALL,
                                     config.data.get_target_types('color'),
                                     Gdk.DragAction.COPY)


        hbox.show_all()
        return hbox

    def refresh(self):
        v=self.getter()
        if v is None:
            v=""
        if hasattr(self.entry, 'set_current_element'):
            self.entry.set_current_element(v)
        else:
            self.entry.set_text(v)

    def update_element(self):
        if not self.editable:
            return False
        if hasattr(self.entry, 'get_current_element'):
            v=self.entry.get_current_element()
        else:
            v=self.entry.get_text()
        self.setter(v)
        return True

class EditMetaForm(EditGenericForm):
    def __init__(self, title=None, element=None, name=None,
                 namespaceid='advenetool', controller=None,
                 editable=True, tooltip=None, type=None,
                 elements=None,
                 focus=False, sizegroup=None):
        getter=self.metadata_get_method(element, name, namespaceid)
        setter=self.metadata_set_method(element, name, namespaceid)
        super(EditMetaForm, self).__init__(title=title,
                                           getter=getter,
                                           setter=setter,
                                           controller=controller,
                                           editable=editable,
                                           tooltip=tooltip,
                                           type=type,
                                           elements=elements,
                                           focus=focus,
                                           sizegroup=sizegroup)

class EditAttributeForm(EditGenericForm):
    def __init__(self, title=None, element=None, name=None,
                 controller=None,
                 editable=True, tooltip=None, type=None, elements=None,
                 focus=False, sizegroup=None):
        getter=lambda: getattr(element, name)
        setter=lambda v: setattr(element, name, v)
        super(EditAttributeForm, self).__init__(title=title,
                                                getter=getter,
                                                setter=setter,
                                                controller=controller,
                                                editable=editable,
                                                tooltip=tooltip,
                                                type=type,
                                                elements=elements,
                                                focus=focus,
                                                sizegroup=sizegroup)

class EditAttributesForm (EditForm):
    """Creates an edit form for the given element."""
    COLUMN_LABEL=0
    COLUMN_VALUE=1
    COLUMN_NAME=2
    COLUMN_EDITABLE=3
    COLUMN_WEIGHT=4

    def __init__ (self, el, controller=None):
        self.element = el
        self.controller=controller
        self.attributes = ()  # Visible attributes
        self.editable = ()    # Editable attributes
        self.labels = {}      # Specific labels for attributes
        self.types = {}       # Specific types for attributes
        self.view = None

    def set_attributes (self, attlist):
        self.attributes = attlist

    def set_editable (self, attlist):
        self.editable = attlist

    def set_labels (self, dic):
        self.labels = dic

    def set_types (self, dic):
        self.types = dic

    def attribute_type (self, at):
        """Return the type of the attribute.

        Current values: 'int', 'advene' (advene element)
        """
        typ = None
        if at in self.types:
            typ=self.types[at]
        else:
            # No specific type was given. Guess it...
            e=getattr(self.element, at)
            if isinstance (e, int):
                typ='int'
        return typ

    def repr_to_value (self, at, v):
        """Convert the value of v into the appropriate value for attribute at.

        Raises an exception (ValueError) if the value could not be converted.
        """
        val = None
        typ = self.attribute_type (at)
        if typ == 'int':
            try:
                val = int(v)
            except ValueError:
                raise ValueError (_('Expecting an integer.')) from None
        elif typ == 'advene':
            # We should not have writable Advene elements in attributes anyway
            pass
        elif isinstance(v, str):
            val = str(v)
        else:
            val=v
        return val

    def value_to_repr (self, at, v):
        """Return the appropriate representation of value v for attribute at.

        Return None if the value could not be converted.
        """
        typ = self.attribute_type (at)
        if typ == 'advene':
            return self.controller.get_title(v)
        elif v is not None:
            return str(v)
        else:
            return None

    def cell_edited(self, cell, path_string, text, model, column):
        it = model.get_iter_from_string(path_string)
        if not it:
            return
        at = model.get_value (it, self.COLUMN_NAME)
        try:
            val = self.repr_to_value (at, text)
        except ValueError as e:
            dialog.message_dialog(
                _("The %(attribute)s attribute could not be updated:\n\n%(error)s\n\nResetting to the original value.")
                % {'attribute': at, 'error': str(e)},
                icon=Gtk.MessageType.WARNING)
            # Invalid value -> we take the original value
            val = getattr(self.element, at)

        model.set_value(it, column, self.value_to_repr (at, val))

    def check_validity(self):
        invalid=[]
        model = self.view.get_model ()
        it = model.get_iter_first ()
        while it is not None:
            at = model.get_value (it, EditAttributesForm.COLUMN_NAME)
            if at in self.editable:
                text = model.get_value (it, EditAttributesForm.COLUMN_VALUE)
                v = None
                try:
                    v = self.repr_to_value (at, text)
                except ValueError as e:
                    v = None
                    invalid.append((at, e))
            it = model.iter_next(it)
        # Display list of invalid attributes
        if invalid:
            dialog.message_dialog(
                _("The following attributes cannot be updated:\n\n%s")
                % "\n".join ([ "%s: %s" % (attr, str(err)) for (attr, err) in invalid ]),
                icon=Gtk.MessageType.ERROR)
            return False
        else:
            return True

    def refresh(self):
        model=self.view.get_model()
        for row in model:
            at=row[self.COLUMN_NAME]
            row[self.COLUMN_VALUE]=self.value_to_repr(at, getattr (self.element, at))

    def update_element (self):
        """Update the element fields according to the values in the view."""
        invalid=[]
        model = self.view.get_model ()
        it = model.get_iter_first ()
        while it is not None:
            at = model.get_value (it, EditAttributesForm.COLUMN_NAME)
            if at in self.editable:
                text = model.get_value (it, EditAttributesForm.COLUMN_VALUE)
                v = None
                try:
                    v = self.repr_to_value (at, text)
                except ValueError as e:
                    v = None
                    invalid.append((at, e))

                if v is not None:
                    try:
                        setattr (self.element, at, v)
                    except ValueError as e:
                        invalid.append((at, e))
            it = model.iter_next(it)
        # Display list of invalid attributes
        if invalid:
            dialog.message_dialog(
                _("The following attributes could not be updated:\n\n%s")
                % "\n".join ([ "%s: %s" % (attr, str(err)) for (attr, err) in invalid ]),
                icon=Gtk.MessageType.ERROR)
        return True

    def get_view (self, compact=False):
        """Generate a view widget for editing el attributes.

        Return the view widget.
        """
        model = Gtk.ListStore (GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_BOOLEAN, GObject.TYPE_INT)

        el = self.element

        treeview = Gtk.TreeView(model)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(_('Attribute'), renderer,
                                    text=self.COLUMN_LABEL,
                                    weight=self.COLUMN_WEIGHT)

        treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        renderer.connect('edited', self.cell_edited, model, 1)
        column = Gtk.TreeViewColumn(_('Value'), renderer,
                                    text=self.COLUMN_VALUE,
                                    editable=self.COLUMN_EDITABLE,
                                    weight=self.COLUMN_WEIGHT)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_resizable(True)
        column.set_clickable(False)
        treeview.append_column(column)

        weight = {False: Pango.Weight.BOLD,
                  True:  Pango.Weight.NORMAL}

        for at in self.attributes:
            editable = at in self.editable
            if at in self.labels:
                label=self.labels[at]
            else:
                label=at

            it = model.append ()
            model.set(it,
                      self.COLUMN_LABEL, label,
                      self.COLUMN_VALUE, self.value_to_repr(at, getattr (el, at)),
                      self.COLUMN_NAME, at,
                      self.COLUMN_EDITABLE, editable,
                      self.COLUMN_WEIGHT, weight[editable])

        # Tweak the display:
        treeview.set_headers_visible (False)
        treeview.set_border_width (1)
        self.view = treeview
        return treeview

class EditElementListForm(EditForm):
    COLUMN_ELEMENT=0
    COLUMN_LABEL=1

    def __init__(self, title=None, element=None, field=None,
                 members=None, controller=None, editable=True):
        """Edit an element list.

        The field attribute of element contains a list of elements.
        Valid elements are specified in members, which is a list of couples
        (element, label)
        """
        self.title=title
        self.model=element
        self.field=field
        self.members=members
        self.controller=controller
        self.editable=editable
        self.view=None

    def tree_view_button_cb(self, widget=None, event=None):
        retval = False
        button = event.button
        x = int(event.x)
        y = int(event.y)

        if button == 3:
            if event.get_window() is widget.get_bin_window():
                model = widget.get_model()
                t = widget.get_path_at_pos(x, y)
                if t is not None:
                    path, col, cx, cy = t
                    node=model[path][self.COLUMN_ELEMENT]
                    widget.get_selection().select_path (path)
                    menu = advene.gui.popup.Menu(node, controller=self.controller)
                    menu.popup()
                    retval = True
        return retval

    def get_representation(self, v):
        r='???'
        for el, label in self.members:
            if el == v:
                r = label
                break
        return r

    def create_store(self):
        store=Gtk.ListStore(
            GObject.TYPE_PYOBJECT,
            GObject.TYPE_STRING
            )
        for el in getattr(self.model, self.field):
            store.append( [ el,
                            self.get_representation(el) ] )
        return store

    def insert_new(self, button=None, treeview=None):
        element=dialog.list_selector(title=_("Insert an element"),
                                              text=_("Choose the element to insert."),
                                              members=self.members,
                                              controller=self.controller)
        if element is not None:
            treeview.get_model().append( [element,
                                          self.get_representation(element) ])
        return True

    def delete_current(self, button=None, treeview=None):
        model, it=treeview.get_selection().get_selected()
        if it is not None:
            model.remove(it)
        return True

    def get_view(self, compact=False):
        vbox=Gtk.VBox()
        self.store=self.create_store()

        treeview=Gtk.TreeView(model=self.store)
        treeview.set_reorderable(True)
        treeview.connect('button-press-event', self.tree_view_button_cb)
        self.treeview=treeview

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(self.title, renderer,
                                    text=self.COLUMN_LABEL)
        treeview.append_column(column)

        vbox.add(treeview)

        hbox=Gtk.HButtonBox()
        b=Gtk.Button(stock=Gtk.STOCK_ADD)
        b.connect('clicked', self.insert_new, treeview)
        hbox.add(b)

        b=Gtk.Button(stock=Gtk.STOCK_REMOVE)
        b.connect('clicked', self.delete_current, treeview)
        hbox.add(b)

        vbox.add(hbox)

        vbox.show_all()

        return vbox

    def refresh(self):
        self.store=self.create_store()
        self.treeview.set_model(self.store)

    def update_element(self):
        if not self.editable:
            return False
        # Rebuild list from self.store
        elements=[ e[self.COLUMN_ELEMENT] for e in self.store ]
        setattr(self.model, self.field, elements)
        return True

class EditTagForm(EditForm):
    """Edit form to tags
    """
    def __init__(self, element=None, controller=None, editable=True):
        self.element = element
        self.controller = controller
        self.view=None
        self.editable=editable

    def check_validity(self):
        invalid=[ t for t in self.get_current_tags()
                  if not re.match('^[\w\d_]+$', t) ]
        if invalid:
            dialog.message_dialog(_("Some tags contain invalid characters: %s") % ", ".join(invalid),
                                           icon=Gtk.MessageType.ERROR)
            return False
        else:
            return True

    def get_current_tags(self):
        return self.view.tags

    def refresh(self):
        self.view.tag=self.element.tags
        self.view.refresh()

    def update_element(self):
        if not self.editable:
            return False
        if not self.check_validity():
            return False
        self.element.setTags( self.get_current_tags() )
        return True

    def get_view(self, compact=False):
        hb=Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Tags:") + " "), False, False, 0)
        self.view=TagBag(controller=self.controller, tags=self.element.tags, vertical=False)
        self.view.register_callback(controller=self.controller)
        self.view.widget.connect('destroy', lambda w: self.view.unregister_callback(self.controller))
        hb.add(self.view.widget)
        return hb

class EditRelationsForm(EditForm):
    """Edit form for relations.
    """
    def __init__(self, element=None, controller=None, editable=True):
        self.element = element
        self.controller = controller
        self.view=None
        self.editable=editable

    def check_validity(self):
        # FIXME
        invalid=[]
        if invalid:
            dialog.message_dialog(_("Some tags contain invalid characters: %s") % ", ".join(invalid),
                                           icon=Gtk.MessageType.ERROR)
            return False
        else:
            return True

    def refresh(self):
        self.view.foreach(self.view.remove)
        col1=Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        col2=Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        for i, r in enumerate(self.element.relations):
            # Determine the direction
            if r.members[0] == self.element:
                direction="to"
                other=r.members[1]
            else:
                direction="from"
                other=r.members[0]
            hb=Gtk.HBox()

            b=RelationRepresentation(r, controller=self.controller, direction=direction)
            b.set_alignment(0, 0)
            col1.add_widget(b)
            hb.pack_start(b, False, True, 0)

            a=AnnotationRepresentation(other, controller=self.controller)
            a.set_alignment(0, 0)
            col2.add_widget(a)
            hb.pack_start(a, False, True, 0)

            self.view.pack_start(hb, False, True, 0)
        self.view.show_all()
        return

    def update_element(self):
        if not self.editable:
            return False
        if not self.check_validity():
            return False
        #FIXME self.element.setTags( self.get_current_tags() )
        return True

    def get_view(self, compact=False):
        self.view=Gtk.VBox()
        self.refresh()
        return self.view
