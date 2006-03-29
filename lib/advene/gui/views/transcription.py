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
"""Transcription view.
"""

import sys

import gtk

# Advene part
from advene.model.package import Package
from advene.gui.edit.properties import EditWidget

import advene.util.vlclib as vlclib

from gettext import gettext as _

from advene.gui.views import AdhocView
import advene.gui.popup

class TranscriptionView(AdhocView):
    def __init__ (self, controller=None, annotationtype=None, separator="  "):
        self.view_name = _("Transcription")
	self.view_id = 'transcriptionview'
	self.close_on_package_load = True

        self.controller=controller
        self.package=controller.package
        self.model = annotationtype
        # Annotation where the cursor is set
        self.currentannotation=None

        self.modified=False

        self.options = {
	    'display-bounds': False,
	    'display-time': False,
	    'separator': ' ',
	    # If representation is not None, it is used as a TALES
	    # expression to generate the representation of the
	    # transcripted annotation. Useful with structured annotations
	    'representation': '',
	    }

        self.widget=self.build_widget()

    def edit_options(self, button):
	cache=dict(self.options)

        ew=EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Transcription options"))
        ew.add_entry(_("Representation"), "representation", _("If not empty, this TALES expression that will be used to format the annotations."))
        ew.add_entry(_("Separator"), "separator", _("This separator will be inserted between the annotations."))
        ew.add_checkbox(_("Display timestamps"), "display-time", _("Insert timestsamp values"))
        ew.add_checkbox(_("Display annotation bounds"), 'display-bounds', _("Display annotation bounds"))
        res=ew.popup()

        if res:
	    # Process special characters
	    for c in ('representation', 'separator'):
		self.options[c]=cache[c].replace('\\n', '\n').replace('\\t', '\t')
	    for c in ('display-time', 'display-bounds'):
		self.options[c]=cache[c]
	    self.generate_buffer_content()
	return True

    def build_widget(self):
        mainbox = gtk.VBox()

        if self.controller.gui:
            toolbar=self.controller.gui.get_player_control_toolbar()
            mainbox.pack_start(toolbar, expand=False)
            
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
	sw.set_resize_mode(gtk.RESIZE_PARENT)
        mainbox.add (sw)

        self.textview = gtk.TextView()
        # We could make it editable and modify the annotation
        self.textview.set_editable(True)
        self.textview.set_wrap_mode (gtk.WRAP_CHAR)
        b=self.textview.get_buffer()

        activated_tag = b.create_tag("activated")
        #activated_tag.set_property("weight", pango.WEIGHT_BOLD)
        activated_tag.set_property("background", "skyblue")
        # activated_tag.set_property("foreground", "white")

        currenttag = b.create_tag("current")
        currenttag.set_property("background", "lightblue")


        self.generate_buffer_content()

        self.textview.connect("button-press-event", self.button_press_event_cb)
        self.textview.connect_after("move-cursor", self.move_cursor_cb)
        self.textview.connect("insert-at-cursor", self.insert_at_cursor_cb)
        self.textview.connect("populate-popup", self.populate_popup_cb)

        self.update_current_annotation(self.textview, None)

        sw.add_with_viewport (self.textview)


        hb=gtk.HButtonBox()
        hb.set_homogeneous(False)

        b=gtk.Button(stock=gtk.STOCK_PREFERENCES)
        b.connect("clicked", self.edit_options)
        hb.pack_start(b, expand=False)

        b=gtk.Button(stock=gtk.STOCK_SAVE)
        b.connect ("clicked", self.save_transcription)
        hb.pack_start(b, expand=False)

        mainbox.pack_start(hb, expand=False)

	mainbox.buttonbox = hb

        mainbox.show_all()

        return mainbox

    def generate_buffer_content(self):
        b=self.textview.get_buffer()
        # Clear the buffer
        begin,end=b.get_bounds()
        b.delete(begin, end)

        l=self.model.annotations[:]
        l.sort(lambda a,b: cmp(a.fragment.begin, b.fragment.begin))
        for a in l:
            if self.options['display-time']:
                b.insert_at_cursor("[%s]" % vlclib.format_time(a.fragment.begin))

            mark = b.create_mark("b_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            mark.set_visible(self.options['display-bounds'])

            if self.options['representation']:
                rep=vlclib.get_title(self.controller, a, 
				     representation=self.options['representation'])
            else:
                rep=a.content.data

            b.insert_at_cursor(unicode(rep))
            mark = b.create_mark("e_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            mark.set_visible(self.options['display-bounds'])

            if self.options['display-time']:
                b.insert_at_cursor("[%s]" % vlclib.format_time(a.fragment.end))

            b.insert_at_cursor(self.options['separator'])
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
        self.modified=True
        b=self.textview.get_buffer()
        b.insert_at_cursor(s)
        # Update the annotation's content
        beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % self.currentannotation.id))
        enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % self.currentannotation.id))
        self.currentannotation.content.data = b.get_text(beginiter, enditer)
        print "Updated value to %s" % self.currentannotation.content.data
        return True

    def button_press_event_cb(self, textview, event):
        if event.button != 1:
            return False
        textwin=textview.get_window(gtk.TEXT_WINDOW_TEXT)
        if event.window != textwin:
            return False

        (x, y) = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                                  int(event.x),
                                                  int(event.y))
        it=textview.get_iter_at_location(x, y)
        if it is None:
            print "Error in get_iter_at_location"
            return False
        textview.get_buffer().move_mark_by_name('insert', it)
        textview.get_buffer().move_mark_by_name('selection_bound', it)
        self.update_current_annotation()
        return True

    def move_cursor_cb(self, textview, step_size, count, extend_selection):
        self.update_current_annotation()
        return False

    def update_model(self, package):
	self.generate_buffer_content()
	return True

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
            while i.backward_char():
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

    def save_transcription(self, button=None):
	fname=advene.gui.util.get_filename(title= ("Save transcription to..."),
					   action=gtk.FILE_CHOOSER_ACTION_SAVE,
					   button=gtk.STOCK_SAVE)
	if fname is not None:
	    self.save_output(filename=fname)
            return True
        return True

    def save_output(self, filename=None):
        b=self.textview.get_buffer()
        begin,end=b.get_bounds()
        out=b.get_text(begin, end)
	try:
	    f=open(filename, "w")
	except Exception, e:
	    self.controller.log(_("Cannot write to %s: %s:") %
				  (filename, unicode(e)))
	    return True
        f.write(out)
        f.close()
        self.controller.log(_("Transcription saved to %s") % filename)
        return True

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

