#! /usr/bin/env python

"""Helper GUI classes and methods.

This module provides generic edit forms for the various Advene
elements (Annotation, Relation, AnnotationType, RelationType, Schema,
View, Package).

"""

import advene.core.config as config

from gettext import gettext as _

import pygtk
pygtk.require ('2.0')
import gtk
import gobject
import pango

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

import advene.gui.edit.rules
import advene.rules.actions
import xml.dom
import StringIO

# FIXME: handle 'time' type, with hh:mm:ss.mmm display

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
        self.window = gtk.Window (gtk.WINDOW_TOPLEVEL)
        self.window.set_position(gtk.WIN_POS_MOUSE)
        self.vbox = gtk.VBox ()
        self.vbox.connect ("key-press-event", self.key_pressed_cb)
        self.window.add (self.vbox)
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
    
    def make_widget (self, editable=False):
        """Create the editing widget (and return it)."""
        raise Exception ("This method should be defined in the subclasses.")

    def validate_cb (self, button=None, event=None, callback=None):
        """Method called when validating a form."""
        for f in self.forms:
            f.update_element ()
        self.window.destroy ()

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

    def close_cb (self, button=None, data=None):
        """Method called when closing a form."""
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
            name=str(self)
        return "%s %s" % (c, name)

    def framed (self, widget, label=""):
        fr = gtk.Frame ()
        fr.set_label (label)
        fr.add (widget)
        return fr

    def edit (self, callback=None):
        """Display the edit window."""
        self.key_cb[gtk.keysyms.Return] = self.validate_cb
        self.key_cb[gtk.keysyms.Escape] = self.close_cb

        self.vbox.add (self.make_widget (editable=True))

        # Button bar
        hbox = gtk.HButtonBox()

        b = gtk.Button (stock=gtk.STOCK_OK)
        b.connect ("clicked", self.validate_cb, callback)
        hbox.add (b)

        b = gtk.Button (stock=gtk.STOCK_CANCEL)
        b.connect ("clicked", lambda w: self.window.destroy ())
        hbox.add (b)

        self.vbox.pack_start (hbox, expand=False)
        self.window.set_title (_("Edit %s") % self.get_title())
        self.window.show_all ()

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
        self.window.show_all ()

    def make_registered_form (self,
                              element=None,
                              fields=(),
                              editables=None,
                              editable=False, # Boolean
                              types=None,
                              labels=None):
        """Shortcut for creating an Attributes form and registering it."""
        f = EditAttributesForm (element)
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
    
    def make_widget (self, editable=False):
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

        # FIXME: maybe we should use here a specific plugin (from timeadjustment)
        # Fragment data
        f = self.make_registered_form (element=self.element.fragment,
                                       fields=('begin', 'end'),
                                       editable=editable,
                                       editables=('begin', 'end'),
                                       types={'begin':'int', 'end':'int'},
                                       labels={'begin': _('Begin'),
                                               'end': _('End')}
                                       )
        vbox.pack_start (f.get_view (), expand=False)

        # Annotation content
        f = EditTextForm (self.element.content, 'data')
        f.set_editable (editable)
        t = f.get_view ()
        self.register_form (f)
        vbox.pack_start(self.framed(t, _("Content")), expand=True)

        return vbox

class EditRelationPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Relation)
    can_edit = staticmethod (can_edit)
        
    def notify(self, element):
        self.controller.notify("RelationEditEnd", relation=element)
        return True
    
    def make_widget (self, editable=False):
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

        def edit_popup(button, element):
            try:
                pop = get_edit_popup (element, self.controller)
            except TypeError, e:
                print _("Error: unable to find an edit popup for %s:\n%s") % (element, str(e))
            else:
                pop.edit ()
            return True

        # FIXME: make it possible to edit the members list (drag and drop ?)
        hb = gtk.HButtonBox()
        hb.set_layout(gtk.BUTTONBOX_START)
        for a in self.element.members:
            b = gtk.Button(a.id)
            b.connect("clicked", edit_popup, a)
            b.show()
            hb.add(b)
            
        vbox.pack_start(self.framed(hb, _("Members")), expand=True)

        # Relation content
        f = EditTextForm (self.element.content, 'data')
        f.set_editable (editable)
        t = f.get_view ()
        self.register_form (f)
        vbox.pack_start(self.framed(t, _("Content")), expand=True)

        return vbox

class EditViewPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, View)
    can_edit = staticmethod (can_edit)
        
    def notify(self, element):
        self.controller.notify("ViewEditEnd", view=element)
        return True
    
    def make_widget (self, editable=False):
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
        # FIXME: we should use a generic mimetype plugin detection
        if self.element.content.mimetype == 'application/x-advene-ruleset':
            f = EditRuleSetForm (self.element.content, 'model')
        else:
            f = EditTextForm (self.element.content, 'data')

        f.set_editable (editable)
        t = f.get_view ()
        self.register_form (f)
        vbox.pack_start (self.framed(t, _("Content")), expand=True)

        return vbox

class EditPackagePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Package)
    can_edit = staticmethod (can_edit)
        
    def make_widget (self, editable=False):
        # Package data
        # Annotation data
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
        return f.get_view ()

class EditSchemaPopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, Schema)
    can_edit = staticmethod (can_edit)
        
    def notify(self, element):
        self.controller.notify("SchemaEditEnd", schema=element)
        return True
    
    def make_widget (self, editable=False):
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
        return f.get_view ()

class EditAnnotationTypePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, AnnotationType)
    can_edit = staticmethod (can_edit)
        
    def notify(self, element):
        self.controller.notify("AnnotationTypeEditEnd", annotationtype=element)
        return True
    
    def make_widget (self, editable=False):
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
        return f.get_view ()

class EditRelationTypePopup (EditElementPopup):
    def can_edit (el):
        return isinstance (el, RelationType)
    can_edit = staticmethod (can_edit)
        
    def notify(self, element):
        self.controller.notify("RelationTypeEditEnd", relationtype=element)
        return True
    
    def make_widget (self, editable=False):
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
        return f.get_view ()

class EditForm:
    """Generic EditForm class.

    This class defines the method that an EditForm is expected to
    implement.
    """
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

class EditTextForm (EditForm):
    """Create a textview edit form for the given element."""
    def __init__ (self, element, field):
        self.element = element
        self.field = field
        self.editable = False
        self.view = None

    def set_editable (self, bool):
        self.editable = bool

    def update_element (self):
        """Update the element fields according to the values in the view."""
        buf = self.view.get_buffer()
        start_iter, end_iter = buf.get_bounds ()
        text = buf.get_text (start_iter, end_iter)
        setattr (self.element, self.field, text)

    def get_view (self):
        """Generate a view widget for editing text attribute."""
        textview = gtk.TextView ()
        textview.set_editable (self.editable)
        textview.set_wrap_mode (gtk.WRAP_CHAR)
        textview.get_buffer ().insert_at_cursor (getattr(self.element, self.field))
        self.view = textview

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_win.add(textview)

        return scroll_win

class EditRuleSetForm (EditForm):
    """Create a RuleSet edit form for the given element (a view, presumably)."""
    def __init__ (self, element, field):
        # Element is a view.content, field should be "data" or "model" ?
        self.element = element
        self.field = field
        self.editable = False
        self.view = None

    def set_editable (self, boo):
        self.editable = boo

    def update_element (self):
        """Update the element fields according to the values in the view."""
        self.edit.update_value()

        # FIXME: this is not very clean (too many manipulations)
        # We should generate the XML tree directly
        di = xml.dom.DOMImplementation.DOMImplementation()
        # FIXME: hardcoded NS URI should move to config
        rulesetdom = di.createDocument("http://liris.cnrs.fr/advene/ruleset", "ruleset", None)
        self.edit.model.to_dom(rulesetdom)

        stream=StringIO.StringIO()
        xml.dom.ext.PrettyPrint(rulesetdom, stream)
        setattr(self.element, 'data', stream.getvalue())
        stream.close()

    def get_view (self):
        """Generate a view widget to edit the ruleset."""

        # FIXME: we generate a dummy catalog, but we should get the
        # controller.event_handler one instead. Maybe we should store
        # it in the config module.
        catalog=advene.rules.elements.ECACatalog()
        for a in advene.rules.actions.DefaultActionsRepository(controller=None).get_default_actions():
            catalog.register_action(a)

        rs=advene.rules.elements.RuleSet()
        rs.from_dom(catalog=catalog,
                    domelement=getattr(self.element, self.field))

        self.edit=advene.gui.edit.rules.EditRuleSet(rs, catalog=catalog)

        self.view = self.edit.get_packed_widget()

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll_win.add_with_viewport(self.view)

        return scroll_win


class EditAttributesForm (EditForm):
    """Creates an edit form for the given element."""
    COLUMN_LABEL=0
    COLUMN_VALUE=1
    COLUMN_NAME=2
    COLUMN_EDITABLE=3
    COLUMN_WEIGHT=4
    
    def __init__ (self, el):
        self.element = el
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
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_WARNING, gtk.BUTTONS_CLOSE,
                _("The %s attribute could not be updated:\n\n%s\n\nResetting to the original value.")
                % (at, str(e)))
            dialog.connect("response", lambda w, e: dialog.destroy())
            dialog.show()
            
            # Invalid value -> we take the original value
            val = getattr(self.element, at)
 
        model.set_value(iter, column, self.value_to_repr (at, val))

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
            dialog = gtk.MessageDialog(
                None, gtk.DIALOG_DESTROY_WITH_PARENT,
                gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE,
                _("The following attributes could not be updated:\n\n%s")
                % "\n".join ([ "%s: %s" % (at, str(e)) for (at, e) in invalid ]))
            dialog.connect("response", lambda w, e: dialog.destroy())
            dialog.show()

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

if __name__ == "__main__":
    class Foo:
        def __init__ (self, name="Foo"):
            self.name = name
            self.test = 1
            self.parent = "toto"

    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_size_request (320, 200)

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
