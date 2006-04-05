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
"""Helper GUI classes and methods.

This module provides generic edit forms for the various Advene
elements (Annotation, Relation, AnnotationType, RelationType, Schema,
View, Package).

"""

import advene.core.config as config
import gettext
gettext.install('advene', unicode=True)

import gtk
import gobject
import pango
import sre
import os

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.view import View
from advene.model.resources import ResourceData
from advene.model.query import Query

from advene.gui.edit.timeadjustment import TimeAdjustment
from advene.gui.views.browser import Browser

import advene.util.vlclib as vlclib
import advene.gui.util

# FIXME: handle 'time' type, with hh:mm:ss.mmm display in attributes

# Common content MIME-types
common_content_mimetypes = [
    'text/plain',
    'application/x-advene-structured',
    'application/x-advene-zone',
    ]

common_view_mimetypes = [
    'text/html',
    'text/plain',
    'image/svg+xml',
    ]


_edit_popup_list = []

def get_edit_popup (el, controller=None):
    """Return the right edit popup for the given element."""
    for c in _edit_popup_list:
        if c.can_edit (el):
            return c(el, controller)
    raise TypeError(_("No edit popup available for element %s") % el)

class EditPopupClass (type):
  def __init__ (cls, *args):
    super (EditPopupClass, cls).__init__(*args)
    if hasattr (cls, 'can_edit'):
        _edit_popup_list.append(cls)

class EditElementPopup (object):
    """Abstract class for editing Advene elements.

    To create a specialized edit window, define the make_widget
    method, which returns the appropriate widget composed of EditAttributesForm
    and EditTextForm. The make_widget must register its forms via
    self.register_form().

    On validation, the registered forms are asked to update the values
    of their respective elements.
    """
    __metaclass__ = EditPopupClass

    def __init__ (self, el, controller=None):
        """Create an edit window for the given element."""
        self.element = el
        self.controller = controller
        self.window=None
        self.vbox = gtk.VBox ()
        self.vbox.connect ("key-press-event", self.key_pressed_cb)
        self.editable=True
        # List of defined forms in the window
        self.forms = []
        # Dictionary of callbacks according to keys
        self.key_cb = {}

    def register_form (self, f):
        self.forms.append(f)

    def can_edit (el):
        """Return True if the class can edit the given element.

        Warning: it is a static method (no self argument), but the
        staticmethod declaration is handled in the metaclass."""
        return False
    can_edit = staticmethod (can_edit)

    def make_widget (self, editable=True):
        """Create the editing widget (and return it)."""
        raise Exception ("This method should be defined in the subclasses.")

    def apply_cb (self, button=None, event=None, callback=None):
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

        if callback is not None:
            callback (element=self.element)
        return True

    def validate_cb (self, button=None, event=None, callback=None):
        """Method called when validating a form."""
        if self.apply_cb(button, event, callback):
            if self.window is not None:
                self.window.destroy ()
        return True

    def close_cb (self, button=None, data=None):
        """Method called when closing a form."""
        if self.window is not None:
            self.window.destroy ()
        return True

    def key_pressed_cb (self, button=None, event=None):
        if self.key_cb.has_key (event.keyval):
            return self.key_cb[event.keyval] (button, event)
        else:
            return False

    def get_title (self):
        """Return the element title."""
        c = self.element.viewableClass
        if hasattr (self.element, 'title') and self.element.title is not None:
            name=self.element.title
        elif hasattr (self.element, 'id') and self.element.id is not None:
            name=self.element.id
        else:
            name=str(self.element)
        return "%s %s" % (c, name)

    def framed (self, widget, label=""):
        fr = gtk.Frame ()
        fr.set_label (label)
        fr.add (widget)
        return fr

    def edit (self, callback=None, modal=False):
        """Display the edit window.
        """
        self.key_cb[gtk.keysyms.Return] = self.validate_cb
        self.key_cb[gtk.keysyms.Escape] = self.close_cb

        if hasattr(self.element, 'isImported') and self.element.isImported():
            self.editable=False
        elif hasattr(self.element, 'schema') and self.element.schema.isImported():
            self.editable=False

        w=self.make_widget (editable=self.editable)
        self.vbox.add (w)
        
        if self.editable:
            title=_("Edit %s") % self.get_title()
        else:
            title=_("View %s (read-only)") % self.get_title()

        if modal:
            d = gtk.Dialog(title=title,
                           parent=None,
                           flags=gtk.DIALOG_DESTROY_WITH_PARENT | gtk.DIALOG_MODAL,
                           buttons=( gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                                     gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT ))

            d.vbox.add(self.vbox)
            d.vbox.show_all()

            def keypressed_cb(widget=None, event=None):
                if event.keyval == gtk.keysyms.Return:
                    d.response(gtk.RESPONSE_ACCEPT)
                    return True
                elif event.keyval == gtk.keysyms.Escape:
                    d.response(gtk.RESPONSE_REJECT)
                    return True
                return False
            d.connect("key_press_event", keypressed_cb)

            while True:
                res=d.run()
                retval=False
                if res == gtk.RESPONSE_ACCEPT:
                    retval=self.apply_cb()
                elif res == gtk.RESPONSE_REJECT:
                    retval=True

                if retval:
                    d.destroy()
                    break

            return self.element
        else:
            # Non-modal case
            self.window = gtk.Window (gtk.WINDOW_TOPLEVEL)
            self.window.set_position(gtk.WIN_POS_MOUSE)
            self.window.set_title(title)

            # Button bar
            hbox = gtk.HButtonBox()

            b = gtk.Button (stock=gtk.STOCK_OK)
            b.connect ("clicked", self.validate_cb, callback)
            hbox.add (b)

            b = gtk.Button (stock=gtk.STOCK_APPLY)
            b.connect ("clicked", self.apply_cb, callback)
            hbox.add (b)

            b = gtk.Button (stock=gtk.STOCK_CANCEL)
            b.connect ("clicked", self.close_cb)
            hbox.add (b)

            self.vbox.pack_start (hbox, expand=False)

            self.window.add(self.vbox)

            if self.controller.gui:
                self.controller.gui.init_window_size(self.window, 'editpopup')
            self.window.show_all ()
            return self.element

    def display (self):
        """Display the display window (not editable)."""
        self.key_cb[gtk.keysyms.Return] = self.close_cb
        self.key_cb[gtk.keysyms.Escape] = self.close_cb

        self.vbox.add (self.make_widget (editable=False))
        # Button bar
        hbox = gtk.HButtonBox()

        b = gtk.Button (stock=gtk.STOCK_OK)
        b.connect ("clicked", lambda w: self.window.destroy ())
        hbox.add (b)

        self.vbox.pack_start (hbox, expand=False)

        self.window.set_title (_("Display %s") % self.get_title())
        if self.controller.gui:
            self.controller.gui.init_window_size(self.window, 'editpopup')
        self.window.show_all ()

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

    def make_widget (self, editable=True):
        vbox = gtk.VBox ()

        # Annotation data
        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'type',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'type':   _('Type'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (f.get_view (), expand=False)

        f = EditFragmentForm(element=self.element.fragment, controller=self.controller)
        self.register_form (f)
        vbox.pack_start (f.get_view (), expand=False)

        f = EditContentForm(self.element.content, controller=self.controller,
                            mimetypeeditable=False, annotation=self.element)
        f.set_editable(editable)
        t = f.get_view()
        self.register_form(f)
        vbox.pack_start(self.framed(t, _("Content")), expand=True)

        return vbox

class EditRelationPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Relation)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("RelationEditEnd", relation=element)
        return True

    def make_widget (self, editable=True):
        vbox = gtk.VBox ()

        # Annotation data
        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'type',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date'),
                                       labels={'id':     _('Id'),
                                               'type':   _('Type'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (f.get_view (), expand=False)

        def button_press_handler(widget, event, annotation):
            if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
                menu=advene.gui.popup.Menu(annotation, controller=self.controller)
                menu.popup()
                return True
            if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                try:
                    pop = advene.gui.edit.elements.get_edit_popup (annotation, self.controller)
                except TypeError, e:
                    print _("Error: unable to find an edit popup for %s:\n%s") % (annotation,
                                                                                  unicode(e))
                else:
                    pop.edit ()
                return True
            return False

        # FIXME: make it possible to edit the members list (drag and drop ?)
        hb = gtk.HButtonBox()
        hb.set_layout(gtk.BUTTONBOX_START)
        for a in self.element.members:
            b = gtk.Button(a.id)
            b.connect("button_press_event", button_press_handler, a)
            b.show()
            hb.add(b)

        vbox.pack_start(self.framed(hb, _("Members")), expand=True)

        # Relation content
        f = EditContentForm(self.element.content, controller=self.controller,
                            mimetypeeditable=False)
        f.set_editable(editable)
        t = f.get_view()
        self.register_form(f)
        vbox.pack_start(self.framed(t, _("Content")), expand=True)

        return vbox

class EditViewPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, View)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("ViewEditEnd", view=element)
        return True

    def make_widget (self, editable=True):
        vbox = gtk.VBox ()

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'title',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('title', 'author', 'date'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (f.get_view (), expand=False)

        # matchFilter
        f = self.make_registered_form (element=self.element.matchFilter,
                                       fields=('class', 'type'),
                                       editable=editable,
                                       editables=('class', 'type'),
                                       labels={'class': _('Class'),
                                               'type':  _('Type')}
                                       )
        vbox.pack_start (self.framed(f.get_view (), _("Match Filter")),
                         expand=False)

        # View content

        f = EditContentForm (self.element.content, controller=self.controller,
                             mimetypeeditable=editable)
        f.set_editable (editable)
        t = f.get_view ()
        self.register_form (f)
        vbox.pack_start (self.framed(t, _("Content")), expand=True)

        return vbox

class EditQueryPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Query)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("QueryEditEnd", query=element)
        return True

    def make_widget (self, editable=True):
        vbox = gtk.VBox ()

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'title',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('title', 'author', 'date'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.pack_start (f.get_view (), expand=False)

        f = EditContentForm (self.element.content, controller=self.controller,
                             mimetypeeditable=editable)
        f.set_editable (editable)
        t = f.get_view ()
        self.register_form (f)
        vbox.pack_start (self.framed(t, _("Content")), expand=True)

        return vbox

class EditPackagePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Package)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("PackageEditEnd", package=element)
        return True

    def make_widget (self, editable=False):
        vbox=gtk.VBox()
        f = self.make_registered_form (element=self.element,
                                       fields=('uri', 'title',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date', 'title'),
                                       labels={'uri':    _('URI'),
                                               'title':  _('Title'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )

        vbox.pack_start(f.get_view(), expand=False)

        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable)
        self.register_form(f)
        vbox.pack_start(f.get_view(), expand=False)

        f = EditMetaForm(title=_("Default dynamic view"),
                         element=self.element, name='default_stbv',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable)
        self.register_form(f)
        vbox.pack_start(f.get_view(), expand=False)

        f = EditMetaForm(title=_("Default static view"),
                         element=self.element, name='default_utbv',
                         namespaceid='advenetool', controller=self.controller,
                         editable=editable)
        self.register_form(f)
        vbox.pack_start(f.get_view(), expand=False)

        return vbox

class EditSchemaPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Schema)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("SchemaEditEnd", schema=element)
        return True

    def make_widget (self, editable=True):
        vbox=gtk.VBox()

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'title',
                                               'author', 'date'),
                                       editable=editable,
                                       editables=('author', 'date', 'title'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'title':  _('Title'),
                                               'author': _('Author'),
                                               'date':   _('Date')}
                                       )
        vbox.add(f.get_view())

        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable)
        self.register_form(f)

        vbox.pack_start(f.get_view(), expand=False)

        return vbox

class EditAnnotationTypePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, AnnotationType)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("AnnotationTypeEditEnd", annotationtype=element)
        return True

    def make_widget (self, editable=False):
        vbox = gtk.VBox()

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'title',
                                               'author', 'date', 'mimetype'),
                                       editable=editable,
                                       editables=('author', 'date', 'title',
                                                  'mimetype'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'title':  _('Title'),
                                               'author': _('Author'),
                                               'date':   _('Date'),
                                               'mimetype': _('MIME Type')}
                                       )
        vbox.add(f.get_view())

        # FIXME: should be in a hidable frame (gtk.Expander)
        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable)
        self.register_form(f)
        vbox.pack_start(f.get_view(), expand=False)

        f = EditMetaForm(title=_("Representation"),
                         element=self.element, name='representation',
                         controller=self.controller,
                         editable=editable)
        self.register_form(f)
        vbox.pack_start(f.get_view(), expand=False)

        return vbox

class EditRelationTypePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, RelationType)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("RelationTypeEditEnd", relationtype=element)
        return True

    def make_widget (self, editable=False):
        vbox=gtk.VBox()

        f = self.make_registered_form (element=self.element,
                                       fields=('id', 'uri', 'title',
                                               'author', 'date', 'mimetype'),
                                       editable=editable,
                                       editables=('author', 'date', 'title',
                                                  'mimetype'),
                                       labels={'id':     _('Id'),
                                               'uri':    _('URI'),
                                               'title':  _('Title'),
                                               'author': _('Author'),
                                               'date':   _('Date'),
                                               'mimetype': _('MIME Type')}
                                       )
        vbox.add(f.get_view ())

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
        vbox.pack_start(f.get_view(), expand=False)

        f = EditMetaForm(title=_("Description"),
                         element=self.element, name='description',
                         namespaceid='dc', controller=self.controller,
                         editable=editable)
        self.register_form(f)

        vbox.pack_start(f.get_view(), expand=False)

        return vbox

class EditResourcePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, ResourceData)
    can_edit = staticmethod (can_edit)

    def notify(self, element):
        self.controller.notify("ResourceEditEnd", resource=element)
        return True

    def make_widget (self, editable=True):
        vbox = gtk.VBox ()

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
        vbox.pack_start (f.get_view (), expand=False)

        f = EditContentForm(self.element, controller=self.controller,
                            mimetypeeditable=False)
        f.set_editable(editable)
        t = f.get_view()
        self.register_form(f)
        vbox.pack_start(self.framed(t, _("Content")), expand=True)

        return vbox

class EditForm(object):
    """Generic EditForm class.

    This class defines the method that an EditForm is expected to
    implement.
    """
    def check_validity(self):
        """Checks the validity of the data."""
        return True

    def update_element (self):
        """Update the element from the values in the form.

        This method is called upon form validation, to actually update
        the element with the values given in the form.
        """
        raise Exception ("This method should be implemented in subclasses.")

    def get_view (self):
        """Return the view (gtk Widget) for this form.
        """
        raise Exception ("This method should be implemented in subclasses.")

    def metadata_get_method(self, element, data, namespaceid='advenetool'):
        namespace = config.data.namespace_prefix[namespaceid]
        def get_method():
            expr=element.getMetaData(namespace, data)
            if expr is None:
                expr=""
            if sre.match('^\s*$', expr):
		# The field can contain just a newline, which will be then ignored
                try:
                    i=element.id
                except AttributeError:
                    i=str(element)
                print "Messed up metadata for %s (%s)" % (i, expr)
                expr=""
            return expr
        return get_method

    def metadata_set_method(self, element, data, namespaceid='advenetool'):
        namespace = config.data.namespace_prefix[namespaceid]
        def set_method(value):
            if value is None or value == "":
                value=""
            if sre.match('^\s+', value):
                try:
                    i=element.id
                except AttributeError:
                    i=str(element)
                print "Messed up value for %s" % element.id
                value=""
            element.setMetaData(namespace, data, unicode(value))
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
    def __init__ (self, element, controller=None, annotation=None,
                  editable=True, mimetypeeditable=True, **kw):
        # self.element is a Content object
        self.element = element
        self.controller=controller

        # Annotation context, sometimes needed
        self.annotation=annotation
        # self.contentform will be an appropriate EditForm
        # (EditTextForm,EditRuleSetForm,...)
        self.contentform = None
        # self.mimetype is a gtk.Entry
        self.mimetype = None

        # Allow the edition of mimetype for contents
        # but not for the special case of Ruleset/Query
        self.editable = editable

        self.mimetypeeditable = (mimetypeeditable
                                 and editable
                                 and not (self.element.mimetype in
                                          ('application/x-advene-ruleset',
                                           'application/x-advene-simplequery')))

    def set_editable (self, bool):
        self.editable = bool

    def check_validity(self):
	if self.contentform is None:
	    return True
	else:
	    return self.contentform.check_validity()

    def update_element (self):
        """Update the element fields according to the values in the view."""
	if self.contentform is None:
	    return True
        if self.mimetypeeditable:
            self.element.mimetype = self.mimetype.child.get_text()
        self.contentform.update_element()
        return True

    def get_view (self):
        """Generate a view widget for editing content."""
        vbox = gtk.VBox()

        hbox = gtk.HBox()
        l=gtk.Label(_("MIME Type"))
        hbox.pack_start(l, expand=False)

        self.mimetype=gtk.combo_box_entry_new_text()
	if self.mimetypeeditable:
	    for c in common_view_mimetypes:
		self.mimetype.append_text(c)

        self.mimetype.child.set_text(self.element.mimetype)
        self.mimetype.child.set_editable(self.mimetypeeditable)
        hbox.pack_start(self.mimetype)

        vbox.pack_start(hbox, expand=False)

        handler = config.data.get_content_handler(self.element.mimetype)
	if handler is None:
	    self.contentform=None
	    vbox.add(gtk.Label(_("Error: cannot find a content handler for %s")
			       % self.element.mimetype))
	else:
	    self.contentform=handler(self.element,
				     controller=self.controller,
				     annotation=self.annotation)

        self.contentform.set_editable(self.editable)
        vbox.add(self.contentform.get_view())
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

    def __init__ (self, element, controller=None, **kw):
        self.element = element
        self.controller=controller
        self.editable = True
        self.fname=None
        self.view = None
        self.tooltips=gtk.Tooltips()

    def set_editable (self, boolean):
        self.editable = boolean

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False
        buf = self.view.get_buffer()
        start_iter, end_iter = buf.get_bounds ()
        text = buf.get_text (start_iter, end_iter)
	self.element.data = text
        return True

    def key_pressed_cb (self, win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            if event.keyval == gtk.keysyms.s:
                self.content_save()
                return True
            elif event.keyval == gtk.keysyms.o:
                self.content_open()
                return True
            elif event.keyval == gtk.keysyms.r:
                self.content_reload()
                return True
            elif event.keyval == gtk.keysyms.i:
                self.browser_open()
                return True
        return False

    def browser_open(self, b=None):
        def callback(e):
            if e is not None:
                if e.startswith('string:'):
                    e=e.replace('string:', '')
                b=self.view.get_buffer()
                b.insert_at_cursor(unicode(e))
            return True
        browser = Browser(element=self.controller.package,
                          controller=self.controller,
			  callback=callback)
        browser.popup()
        return True

    def content_reload(self, b=None):
        self.content_open(fname=self.fname)
        return True

    def content_open(self, b=None, fname=None):
        if fname is None:
            fname=advene.gui.util.get_filename(default_file=self.fname)
        if fname is not None:
            try:
                f=open(fname, 'r')
            except IOError, e:
		advene.gui.util.message_dialog(
                    _("Cannot read the data:\n%s") % unicode(e),
		    icon=gtk.MESSAGE_ERROR)
                return True
            b=self.view.get_buffer()
            begin,end = b.get_bounds ()
            b.delete(begin, end)
            b.set_text("".join(f.readlines()))
            f.close()
            self.fname=fname
        return True

    def content_save(self, b=None, fname=None):
        if fname is None:
            fname=advene.gui.util.get_filename(title=_("Save content to..."),
                                               action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                               button=gtk.STOCK_SAVE,
                                               default_file=self.fname)
        if fname is not None:
            if os.path.exists(fname):
                os.rename(fname, fname + '~')
            try:
                f=open(fname, 'w')
            except IOError, e:
		advene.gui.util.message_dialog(
                    _("Cannot save the data:\n%s") % unicode(e),
		    icon=gtk.MESSAGE_ERROR)
                return True
            b=self.view.get_buffer()
            begin,end = b.get_bounds ()
            f.write(b.get_text(begin, end))
            f.close()
            self.fname=fname
        return True

    def get_view (self):
        """Generate a view widget for editing text attribute."""
        vbox=gtk.VBox()

        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        b=gtk.ToolButton()
        b.set_stock_id(gtk.STOCK_OPEN)
        b.set_tooltip(self.tooltips, _("Open a file (C-o)"))
        b.connect("clicked", self.content_open)
        tb.insert(b, -1)

        b=gtk.ToolButton()
        b.set_stock_id(gtk.STOCK_SAVE)
        b.set_tooltip(self.tooltips, _("Save to a file (C-s)"))
        b.connect("clicked", self.content_save)
        tb.insert(b, -1)

        b=gtk.ToolButton()
        b.set_stock_id(gtk.STOCK_REFRESH)
        b.set_tooltip(self.tooltips, _("Reload the file (C-r)"))
        b.connect("clicked", self.content_reload)
        tb.insert(b, -1)

        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ('pixmaps', 'browser.png') ))
        b=gtk.ToolButton(icon_widget=i)
        b.set_tooltip(self.tooltips, _("Insert a value from the browser (C-i)"))
        b.connect("clicked", self.browser_open)
        tb.insert(b, -1)

        tb.show_all()
        vbox.pack_start(tb, expand=False)

        textview = gtk.TextView ()
        textview.set_editable (self.editable)
        textview.set_wrap_mode (gtk.WRAP_CHAR)
        textview.get_buffer ().set_text (self.element.data)
        textview.connect ("key-press-event", self.key_pressed_cb)
        self.view = textview

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
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

    def __init__ (self, element, controller=None, **kw):
        self.element = element
        self.controller=controller
        self.editable = True
        self.fname=None
        self.view = None
        self.tooltips=gtk.Tooltips()

    def set_editable (self, boolean):
        self.editable = boolean

    def set_filename(self, fname):
        self.filename_entry.set_text(fname)
        self.fname = fname
        return fname

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False
        if self.fname:
            size=os.stat(self.fname).st_size
            f=open(self.fname, 'r')
            self.element.data = f.read(size + 2)
            f.close()
        return True

    def key_pressed_cb (self, win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            if event.keyval == gtk.keysyms.s:
                self.content_save()
                return True
            elif event.keyval == gtk.keysyms.o:
                self.content_open()
                return True
        return False

    def content_open(self, b=None, fname=None):
        if fname is None:
            fname=advene.gui.util.get_filename(default_file=self.fname)
        if fname is not None:
            try:
                f=open(fname, 'r')
            except IOError, e:
		advene.gui.util.message_dialog(
                    _("Cannot read the data:\n%s") % unicode(e),
		    icon=gtk.MESSAGE_ERROR)
                return True
            self.set_filename(fname)
        return True

    def content_save(self, b=None, fname=None):
        if fname is None:
            fname=advene.gui.util.get_filename(title=_("Save content to..."),
                                               action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                               button=gtk.STOCK_SAVE,
                                               default_file=self.fname)
        if fname is not None:
            if os.path.exists(fname):
                os.rename(fname, fname + '~')
            try:
                f=open(fname, 'w')
            except IOError, e:
		advene.gui.util.message_dialog(
                    _("Cannot save the data:\n%s") % unicode(e),
		    icon=gtk.MESSAGE_ERROR)
                return True
            self.set_filename(fname)
        return True

    def get_view (self):
        """Generate a view widget for editing text attribute."""
        vbox=gtk.VBox()

        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        b=gtk.ToolButton()
        b.set_stock_id(gtk.STOCK_OPEN)
        b.set_tooltip(self.tooltips, _("Open a file (C-o)"))
        b.connect("clicked", self.content_open)
        tb.insert(b, -1)

        b=gtk.ToolButton()
        b.set_stock_id(gtk.STOCK_SAVE)
        b.set_tooltip(self.tooltips, _("Save to a file (C-s)"))
        b.connect("clicked", self.content_save)
        tb.insert(b, -1)

        tb.show_all()
        vbox.pack_start(tb, expand=False)

        self.filename_entry = gtk.Entry()
        self.filename_entry.set_editable (self.editable)
        vbox.connect ("key-press-event", self.key_pressed_cb)

        vbox.pack_start(self.filename_entry, expand=False)
        return vbox
config.data.register_content_handler(GenericContentHandler)

class EditFragmentForm(EditForm):
    def __init__(self, element=None, controller=None, editable=True):
        self.begin=None
        self.end=None
        self.element = element
        self.controller = controller
        self.editable=editable

    def check_validity(self):
        if self.begin.value >= self.end.value:
	    advene.gui.util.message_dialog(_("Begin time is greater than end time"),
					   icon=gtk.MESSAGE_ERROR)
            return False
        else:
            return True

    def update_element(self):
        if not self.editable:
            return False
        if not self.check_validity():
            return False
        self.element.begin=self.begin.value
        self.element.end=self.end.value
        return True

    def get_view(self):
        hbox=gtk.HBox()

        self.begin=TimeAdjustment(value=self.element.begin,
                                  controller=self.controller,
                                  editable=self.editable)
        f=gtk.Frame()
        f.set_label(_("Begin"))
        f.add(self.begin.get_widget())
        hbox.add(f)

        self.end=TimeAdjustment(value=self.element.end,
                                controller=self.controller,
                                editable=self.editable)
        f=gtk.Frame()
        f.set_label(_("End"))
        f.add(self.end.get_widget())
        hbox.add(f)

        return hbox

class EditGenericForm(EditForm):
    def __init__(self, title=None, getter=None, setter=None, controller=None, editable=True):
        self.title=title
        self.getter=getter
        self.setter=setter
        self.controller=controller
        self.editable=editable
        self.entry=None
        self.view=None

    def get_view(self):
        hbox = gtk.HBox()

        l=gtk.Label(self.title)
        hbox.pack_start(l, expand=False)

        self.entry=gtk.Entry()
        v=self.getter()
        if v is None:
            v=""
        self.entry.set_text(v)
        self.entry.set_editable(self.editable)
        hbox.pack_start(self.entry)

        hbox.show_all()
        return hbox

    def update_element(self):
        if not self.editable:
            return False
        v=self.entry.get_text()
        self.setter(v)
        return True

class EditMetaForm(EditGenericForm):
    def __init__(self, title=None, element=None, name=None,
                 namespaceid='advenetool', controller=None,
                 editable=True):
        getter=self.metadata_get_method(element, name, namespaceid)
        setter=self.metadata_set_method(element, name, namespaceid)
        super(EditMetaForm, self).__init__(title=title,
                                           getter=getter,
                                           setter=setter,
                                           controller=controller,
                                           editable=editable)

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

    def set_editable (self, list):
        self.editable = list

    def set_labels (self, dic):
        self.labels = dic

    def set_types (self, dic):
        self.types = dic

    def attribute_type (self, at):
        typ = None
        if self.types.has_key (at):
            typ=self.types[at]
        else:
            # No specific type was given. Guess it...
            e=getattr(self.element, at)
            if isinstance (e, int) or isinstance (e, long):
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
                val = long(v)
            except ValueError:
                raise ValueError (_('Expecting an integer.'))
        else:
            val = v
        return val

    def value_to_repr (self, at, v):
        """Return the appropriate representation of value v for attribute at.

        Return None if the value could not be converted.
        """
        if v is not None:
            return str(v)
        else:
            return None

    def cell_edited(self, cell, path_string, text, (model, column)):
        iter = model.get_iter_from_string(path_string)
        if not iter:
            return
        at = model.get_value (iter, self.COLUMN_NAME)
        try:
            val = self.repr_to_value (at, text)
        except ValueError, e:
	    advene.gui.util.message_dialog(
                _("The %s attribute could not be updated:\n\n%s\n\nResetting to the original value.")
                % (at, str(e)),
		icon=gtk.MESSAGE_WARNING)
            # Invalid value -> we take the original value
            val = getattr(self.element, at)

        model.set_value(iter, column, self.value_to_repr (at, val))

    def check_validity(self):
        invalid=[]
        model = self.view.get_model ()
        iter = model.get_iter_first ()
        while iter is not None:
            at = model.get_value (iter, EditAttributesForm.COLUMN_NAME)
            #print "Updating value of %s.%s" % (str(self.element), at)
            if at in self.editable:
                text = model.get_value (iter, EditAttributesForm.COLUMN_VALUE)
                v = None
                try:
                    v = self.repr_to_value (at, text)
                except ValueError, e:
                    v = None
                    invalid.append((at, e))
            iter = model.iter_next(iter)
        # Display list of invalid attributes
        if invalid:
	    advene.gui.util.message_dialog(
                _("The following attributes cannot be updated:\n\n%s")
                % "\n".join ([ "%s: %s" % (at, str(e)) for (at, e) in invalid ]),
		icon=gtk.MESSAGE_ERROR)
            return False
        else:
            return True

    def update_element (self):
        """Update the element fields according to the values in the view."""
        invalid=[]
        model = self.view.get_model ()
        iter = model.get_iter_first ()
        while iter is not None:
            at = model.get_value (iter, EditAttributesForm.COLUMN_NAME)
            #print "Updating value of %s.%s" % (str(self.element), at)
            if at in self.editable:
                text = model.get_value (iter, EditAttributesForm.COLUMN_VALUE)
                v = None
                try:
                    v = self.repr_to_value (at, text)
                except ValueError, e:
                    v = None
                    invalid.append((at, e))

                if v is not None:
                    try:
                        #print "el.%s = %s (%s)" % (at, str(v), repr(type(v)))
                        setattr (self.element, at, v)
                    except ValueError, e:
                        invalid.append((at, e))
            iter = model.iter_next(iter)
        # Display list of invalid attributes
        if invalid:
	    advene.gui.util.message_dialog(
                _("The following attributes could not be updated:\n\n%s")
                % "\n".join ([ "%s: %s" % (at, str(e)) for (at, e) in invalid ]),
		icon=gtk.MESSAGE_ERROR)
        return True

    def get_view (self):
        """Generate a view widget for editing el attributes.

        Return the view widget.
        """
        model = gtk.ListStore (gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_STRING, gobject.TYPE_BOOLEAN, gobject.TYPE_INT)

        el = self.element

        treeview = gtk.TreeView(model)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Attribute'), renderer,
                                    text=self.COLUMN_LABEL,
                                    weight=self.COLUMN_WEIGHT)

        treeview.append_column(column)

        renderer = gtk.CellRendererText()
        renderer.connect('edited', self.cell_edited, (model, 1))
        column = gtk.TreeViewColumn(_('Value'), renderer,
                                    text=self.COLUMN_VALUE,
                                    editable=self.COLUMN_EDITABLE,
                                    weight=self.COLUMN_WEIGHT)
        column.set_clickable(False)
        treeview.append_column(column)

        weight = {False: pango.WEIGHT_BOLD,
                  True:  pango.WEIGHT_NORMAL}

        for at in self.attributes:
            editable = at in self.editable
            if self.labels.has_key (at):
                label=self.labels[at]
            else:
                label=at

            iter = model.append ()
            model.set(iter,
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
            if event.window is widget.get_bin_window():
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
        store=gtk.ListStore(
            gobject.TYPE_PYOBJECT,
            gobject.TYPE_STRING
            )
        for el in getattr(self.model, self.field):
            store.append( [ el,
			    self.get_representation(el) ] )
        return store

    def insert_new(self, button=None, treeview=None):
        element=advene.gui.util.list_selector(title=_("Insert an element"),
                                              text=_("Choose the element to insert."),
                                              members=self.members,
                                              controller=self.controller)
        if element is not None:
            treeview.get_model().append( [element,
					  self.get_representation(element) ])
        return True

    def delete_current(self, button=None, treeview=None):
        model, iter=treeview.get_selection().get_selected()
        if iter is not None:
            model.remove(iter)
        return True

    def get_view(self):
        vbox=gtk.VBox()
        self.store=self.create_store()

        treeview=gtk.TreeView(model=self.store)
        treeview.set_reorderable(True)
        treeview.connect("button_press_event", self.tree_view_button_cb)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(self.title, renderer,
                                    text=self.COLUMN_LABEL)
        treeview.append_column(column)

        vbox.add(treeview)

        hbox=gtk.HButtonBox()
        b=gtk.Button(stock=gtk.STOCK_ADD)
        b.connect("clicked", self.insert_new, treeview)
        hbox.add(b)

        b=gtk.Button(stock=gtk.STOCK_REMOVE)
        b.connect("clicked", self.delete_current, treeview)
        hbox.add(b)

        vbox.add(hbox)

        vbox.show_all()

        return vbox

    def update_element(self):
        if not self.editable:
            return False
        # Rebuild list from self.store
        elements=[ e[self.COLUMN_ELEMENT] for e in self.store ]
        setattr(self.model, self.field, elements)
        return True

if __name__ == "__main__":
    class Foo:
        def __init__ (self, name="Foo"):
            self.name = name
            self.test = 1
            self.parent = "toto"

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_default_size (320, 200)

    def key_pressed_cb (win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True

    def update_cb (win, form):
        form.update_element()
        win.get_toplevel().destroy()
        return True

    window.connect ("key_press_event", key_pressed_cb)
    window.connect ("destroy", lambda e: gtk.main_quit())
    window.set_title ("test")

    vbox = gtk.VBox ()
    window.add (vbox)

    f = Foo ('Bar')
    form = EditAttributesForm (f)
    form.set_attributes (('name', 'test', 'parent'))
    form.set_editable (('name', 'test'))
    form.set_labels ({'name':'Nom'})
    form.set_types ({'name':'string', 'test':'int'})


    vbox.add (form.get_view())

    b = gtk.Button (stock=gtk.STOCK_OK)
    b.connect ("clicked", update_cb, form)
    hbox = gtk.HButtonBox()
    vbox.pack_start (hbox, expand=False)
    hbox.add (b)

    window.show_all()
    gtk.main ()
    print """
    Element: %s
    Name: %s
    Test: %d
    Parent: %s
    """ % (f, f.name, f.test, f.parent)
