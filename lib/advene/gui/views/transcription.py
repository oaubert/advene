"""Transcription view.
"""

import sys

import pygtk
#pygtk.require ('2.0')
import gtk
import gobject
import pango

# Advene part
from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View

import advene.util.vlclib as vlclib

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.edit.create
import advene.gui.popup

class TranscriptionView:
    def __init__ (self, controller=None, annotationtype=None, separator="  "):
        self.controller=controller
        self.package=controller.package
        self.model = annotationtype
        self.separator = separator
        self.displaytime=False
        # Annotation where the cursor is set
        self.currentannotation=None

        # If representation is not None, it is used as a TALES
        # expression to generate the representation of the
        # transcripted annotation. Useful with structured annotations
        self.representation=None

        # Various option toggles
        self.display_bounds_toggle=gtk.CheckButton(_("Display annotation bounds"))
        self.display_bounds_toggle.set_active(False)
        self.display_bounds_toggle.connect("toggled", self.display_toggle)
        self.display_time_toggle=gtk.CheckButton(_("Display times"))
        self.display_time_toggle.set_active(False)
        self.display_time_toggle.connect("toggled", self.display_toggle)

        self.widget=self.build_widget()

    def display_toggle(self, button):
        self.generate_buffer_content()
        return True

    def build_widget(self):
        vbox = gtk.VBox()
        self.textview = gtk.TextView()
        # We could make it editable and modify the annotation
        self.textview.set_editable(True)
        self.textview.set_wrap_mode (gtk.WRAP_CHAR)
        b=self.textview.get_buffer()

        activated_tag = b.create_tag("activated")
        activated_tag.set_property("weight", pango.WEIGHT_BOLD)

        currenttag = b.create_tag("current")
        currenttag.set_property("background", "lightblue")


        self.generate_buffer_content()

        self.textview.connect("button-press-event", self.button_press_event_cb)
        self.textview.connect_after("move-cursor", self.move_cursor_cb)
        self.textview.connect("insert-at-cursor", self.insert_at_cursor_cb)
        self.textview.connect("populate-popup", self.populate_popup_cb)

        self.update_current_annotation(self.textview, None)
        vbox.add(self.textview)
        vbox.show_all()
        return vbox

    def generate_buffer_content(self):
        b=self.textview.get_buffer()
        # Clear the buffer
        begin,end=b.get_bounds()
        b.delete(begin, end)
        t_toggle=self.display_time_toggle.get_active()
        m_toggle=self.display_bounds_toggle.get_active()

        for a in self.model.annotations:
            if t_toggle:
                b.insert_at_cursor("[%s]" % vlclib.format_time(a.fragment.begin))

            mark = b.create_mark("b_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            mark.set_visible(m_toggle)

            if self.representation:
                rep=vlclib.get_title(self.controller, a, representation=self.representation)
            else:
                rep=a.content.data

            b.insert_at_cursor(unicode(rep))
            mark = b.create_mark("e_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            mark.set_visible(m_toggle)

            if t_toggle:
                b.insert_at_cursor("[%s]" % vlclib.format_time(a.fragment.end))

            #print "inserted from %d to %d" % (b_a, e_a)
            b.insert_at_cursor(self.separator)
        return

    def populate_popup_cb(self, textview, menu):
        if self.currentannotation is None:
            return False

        item = gtk.MenuItem(_("Annotation %s") % self.currentannotation.id)
        menuc=advene.gui.popup.Menu(self.currentannotation,
                                    controller=self.controller)
        item.set_submenu(menuc.menu)
        item.show_all()
        menu.append(item)

        return False

    def insert_at_cursor_cb(self, textview, s):
        if self.currentannotation is None:
            return False

        b=self.textview.get_buffer()
        b.insert_at_cursor(s)
        # Update the annotation's content
        beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % self.currentannotation.id))
        enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % self.currentannotation.id))
        self.currentannotation.content.data = b.get_text(beginiter, enditer)
        print "Updated value to %s" % self.currentannotation.content.data
        return True

    def button_press_event_cb(self, textview, event):
        self.update_current_annotation()
        return False

    def move_cursor_cb(self, textview, step_size, count, extend_selection):
        self.update_current_annotation()
        return False

    def update_current_annotation(self, *p, **kw):
        b=self.textview.get_buffer()
        i=b.get_iter_at_mark(b.get_insert())

        annotationid=None

        # Are we on an annotation bound ?
        marknames = [ m.get_name()
                      for m in i.get_marks() ]
        beginmarks= [ n
                      for n in marknames
                      if n and n.startswith('b_') ]
        endmarks= [ n
                    for n in marknames
                    if n and n.startswith('e_') ]
        if beginmarks or endmarks:
            # Do not activate on annotation boundary
            # (it causes problems when editing)
            annotationid=None
        else:
            # Look backwards for the first mark that we find
            while not i.is_start():
                marknames = [ m.get_name()
                              for m in i.get_marks() ]
                beginmarks= [ n
                              for n in marknames
                              if n and n.startswith('b_') ]
                endmarks= [ n
                            for n in marknames
                            if n and n.startswith('e_') ]
                if beginmarks:
                    break
                if endmarks:
                    break
                i.backward_char()

            if beginmarks:
                annotationid=beginmarks[0].replace('b_', '')

        if annotationid is not None:
            a=self.package.annotations['#'.join( (self.package.uri,
                                                  annotationid) )]
            if a != self.currentannotation:
                if self.currentannotation is not None:
                    self.untag_annotation(self.currentannotation, "current")
                self.currentannotation=a
                self.tag_annotation(a, "current")
        else:
            if self.currentannotation is not None:
                self.untag_annotation(self.currentannotation, "current")
                self.currentannotation=None
        return False

    def update_annotation (self, annotation=None, event=None):
        """Update an annotation's representation."""
        if event == 'AnnotationActivate':
            self.activate_annotation(annotation)
            return True
        if event == 'AnnotationDeactivate':
            self.desactivate_annotation(annotation)
            return True
        if event == 'AnnotationCreate':
            # If it does not exist yet, we should create it if it is now in self.list
            if annotation in self.model.annotationTypes:
                # FIXME
                print "Not implemented yet."
                pass
            return True

        if event == 'AnnotationEditEnd':
            # FIXME
            print "Update representation"
        elif event == 'AnnotationDelete':
            # FIXME
            print "Remove representation"
        else:
            print "Unknown event %s" % event
        return True

    def tag_annotation(self, a, tagname):
        b=self.textview.get_buffer()
        beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % a.id))
        enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % a.id))
        b.apply_tag_by_name(tagname, beginiter, enditer)

    def untag_annotation(self, a, tagname):
        b=self.textview.get_buffer()
        beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % a.id))
        enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % a.id))
        b.remove_tag_by_name(tagname, beginiter, enditer)

    def activate_annotation(self, a):
        self.tag_annotation(a, "activated")
        return True

    def desactivate_annotation(self, a):
        self.untag_annotation(a, "activated")
        return True

    def register_callback (self, controller=None):
        """Add the activate handler for annotations."""
        self.beginrule=controller.event_handler.internal_rule (event="AnnotationBegin",
                                                method=self.activate_annotation_handler)
        self.endrule=controller.event_handler.internal_rule (event="AnnotationEnd",
                                                method=self.desactivate_annotation_handler)

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.beginrule, type_="internal")
        controller.event_handler.remove_rule(self.endrule, type_="internal")

    def activate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None and annotation.type == self.model:
            self.activate_annotation (annotation)
        return True

    def desactivate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None and annotation.type == self.model:
            self.desactivate_annotation (annotation)
        return True

    def select_separator(self, button=None):
        """Select a new separator."""
        sep=advene.gui.util.entry_dialog(title=_('Enter the new separator'),
                                         text=_("Specify the separator that will be inserted\nbetween the annotations."),
                                         default=self.separator)
        if sep is None:
            # The user canceled the action
            return True

        # Process special characters
        sep=sep.replace('\\n', '\n')
        sep=sep.replace('\\t', '\t')

        self.separator=sep
        self.generate_buffer_content()

        return True

    def select_representation(self, button=None):
        """Select a new representation."""
        rep=advene.gui.util.entry_dialog(title=_('Enter a TALES expression'),
                                         text=_("Specify the TALES expression that will be used\nto format the annotations."),
                                         default=self.representation)
        if rep is None:
            # The user canceled the action
            return True

        # Process special characters
        rep=rep.replace('\\n', '\n')
        rep=rep.replace('\\t', '\t')

        self.representation=rep
        self.generate_buffer_content()

        return True

    def save_transcription(self, button=None):
        fs = gtk.FileSelection ("Save transcription to...")

        def close_and_save(button, fs):
            self.save_output(filename=fs.get_filename())
            fs.destroy()
            return True

        fs.ok_button.connect_after ("clicked", close_and_save, fs)
        fs.cancel_button.connect ("clicked", lambda win: fs.destroy ())

        fs.show ()
        return True

    def save_output(self, filename=None):
        b=self.textview.get_buffer()
        begin,end=b.get_bounds()
        out=b.get_text(begin, end)
        f=open(filename, "w")
        f.write(out)
        f.close()
        self.controller.log(_("Transcription saved to %s") % filename)
        return True
    
    def get_widget (self):
        """Return the TreeView widget."""
        return self.widget

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'transcriptionview')

        window.set_title (_("Transcription for %s") % (self.model.title
                                                       or self.model.id))

        vbox = gtk.VBox()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add (sw)
        sw.add_with_viewport (self.get_widget())
        if self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb,
                            window, self)

        hb=gtk.HButtonBox()
        hb.set_homogeneous(False)

        hb.pack_start(self.display_time_toggle, expand=False)
        hb.pack_start(self.display_bounds_toggle, expand=False)

        b=gtk.Button(_("Separator"))
        b.connect("clicked", self.select_separator)
        hb.pack_start(b, expand=False)

        b=gtk.Button(_("Representation"))
        b.connect("clicked", self.select_representation)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_SAVE)
        b.connect ("clicked", self.save_transcription)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect ("clicked", lambda w: window.destroy ())
        hb.pack_start(b, expand=False)

        vbox.pack_start(hb, expand=False)

        window.add(vbox)

        window.show_all()
        return window

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    class DummyController:
        def notify(self, *p, **kw):
            print "Notify %s %s" % (p, kw)

    controller=DummyController()

    controller.package = Package (uri=sys.argv[1])

    transcription = TranscriptionView(controller=controller,
                                      annotationtype=controller.package.annotationTypes[0])

    window = transcription.popup()

    i = 0
    def key_pressed_cb (win, event):
        global i
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True
            elif event.keyval == gtk.keysyms.space:
                if i > 0:
                    b = controller.package.annotationTypes[0].annotations[i-1]
                    transcription.desactivate_annotation(b)
                a = controller.package.annotationTypes[0].annotations[i]
                print "Activating %s" % a.content.data
                transcription.activate_annotation(a)
                i += 1
        return False

    window.connect ("key-press-event", key_pressed_cb)
    window.connect ("destroy", lambda e: gtk.main_quit())

    gtk.main ()

