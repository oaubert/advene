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
import sre
import sets

import gtk

import advene.core.config as config

# Advene part
from advene.model.package import Package
from advene.gui.edit.properties import EditWidget

import advene.util.helper as helper

from gettext import gettext as _

from advene.gui.views import AdhocView
import advene.gui.util
import advene.gui.popup

parsed_representation = sre.compile(r'^here/content/parsed/([\w\d_\.]+)$')
empty_representation = sre.compile(r'^\s*$')

class TranscriptionView(AdhocView):
    def __init__ (self, controller=None, source=None, parameters=None):
        self.view_name = _("Transcription")
        self.view_id = 'transcriptionview'
        self.close_on_package_load = True
        self.contextual_actions = (
            (_("Refresh"), self.refresh),
            (_("Validate"), self.validate),
            (_("Save view"), self.save_view),
            )
        self.controller=controller
        self.options = {
            'display-bounds': False,
            'display-time': False,
            'separator': ' ',
            # Use the default representation parameter for annotations
            'default-representation': True,
            # If representation is not empty, it is used as a TALES
            # expression to generate the representation of the
            # transcripted annotation. Useful with structured annotations
            'representation': '',
            }

        self.package=controller.package
        
        if parameters:
            opt, arg = self.load_parameters(parameters)
            self.options.update(opt)
            a=dict(arg)
            if source is None and a.has_key('source'):
                source=a['source']

        if source is None:
            # Use whole package
            source="here/annotations"

        # source is a TALES expression, which is evaluated in the
        # package context. It must return a list of annotations.
        self.source = source
        self.model=[]
        self.regenerate_model()
        
        # Annotation where the cursor is set
        self.currentannotation=None

        # Used when batch-updating modified annotations when closing
        # the window
        self.ignore_updates = False

        self.modified=False

        # Try to determine a default representation
        try:
            t=sets.Set([ a.type for a in self.model ])
        except:
            t=[]
        if len(t) == 1:
            # Unique type, the model is homogeneous. Use the
            # annotation-type representation
            at=self.model[0].type
            repr=at.getMetaData(config.data.namespace, 'representation')
            if repr is not None and not sre.match(r'^\s*$', repr):
                # There is a standard representation for the type.
                # But if the current value is != '', then it has been
                # updated by the parameters, so keep it.
                if self.options['representation'] == '':
                    self.options['representation'] = repr
        self.widget=self.build_widget()

    def get_save_arguments(self):
        arguments = [ ('source', self.source) ]
        return self.options, arguments

    def regenerate_model(self):
        c=self.controller.build_context()
        try:
            self.model=c.evaluateValue(self.source)
        except Exception, e:
            self.log(_("Error in source evaluation %(source)s: %(error)s") % {
                    'source': self.source,
                    'error': unicode(e) })
            self.model=[]
        return

    def edit_options(self, button):
        user_defined=object()
        cache=dict(self.options)
        for c in ('representation', 'separator'):
            cache[c] = cache[c].replace('\n', '\\n').replace('\t', '\\t')
        cache['user-separator']=cache['separator']
        if cache['separator'] not in (' ', '\\n', '\\t', ' - '):
            cache['separator']=user_defined

        ew=EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Transcription options"))
        ew.add_checkbox(_("Default representation"), "default-representation", _("Use the default representation for annotations"))
        ew.add_entry(_("Representation"), "representation", _("If default representation is unchecked,\nthis TALES expression that will be used to format the annotations."))
        ew.add_option(_("Separator"), "separator", 
                      _("This separator will be inserted between the annotations."),
                      { _('Whitespace'): ' ',
                        _('Newline'): "\\n",
                        _('Tabulation'): "\\t",
                        _('Dash'): " - ",
                        _('User defined'): user_defined,
                        })
        ew.add_entry(_("User-defined separator"), "user-separator", _("Separator used if user-defined is selected.Use \\n for a newline and \\t for a tabulation."))
        ew.add_checkbox(_("Display timestamps"), "display-time", _("Insert timestsamp values"))
        ew.add_checkbox(_("Display annotation bounds"), 'display-bounds', _("Display annotation bounds"))
        res=ew.popup()

        if res:
            if cache['separator'] == user_defined:
                # User-defined has been selected. Use the user-separator value
                cache['separator']=cache['user-separator']
            self.options.update(cache)
            # Process special characters
            for c in ('representation', 'separator'):
                self.options[c]=self.options[c].replace('\\n', '\n').replace('\\t', '\t')
            self.generate_buffer_content()
        return True

    def close(self):
        l=self.check_modified()
        if l:
            if self.options['representation'] and not parsed_representation.match(self.options['representation']):
                advene.gui.util.message_dialog(label=_("%d annotation(s) were modified\nbut we cannot propagate the modifications\nsince the representation parameter is used.") % len(l))
            else:
                if advene.gui.util.message_dialog(label=_("%d annotations were modified.\nDo you want to update their content?") % len(l),
                                                  icon=gtk.MESSAGE_QUESTION):
                    self.ignore_updates = True
                    self.update_modified(l)
        AdhocView.close(self)
        return True

    def check_modified(self):
        b=self.textview.get_buffer()
        modified = []
        # Update the model to be sure.
        self.regenerate_model()
        for a in self.model:
            try:
                beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % a.id))
                enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % a.id))
                if b.get_text(beginiter, enditer) != self.representation(a):
                    modified.append(a)
            except TypeError:
                # Some missing annotations
                modified.append(a)
        return modified

    def update_modified(self, l):
        def update(a, text):
            """Update an annotation content according to its representation.

            If the update is not possible (too complex representation), return False.
            """
            if self.options['default-representation']:
                repr=a.type.getMetaData(config.data.namespace, 'representation')
            else:
                repr=self.options['representation']
            m=parsed_representation.match(repr)
            if m:
                # We have a simple representation (here/content/parsed/name)
                # so we can update the name field.
                name=m.group(1)
                reg = sre.compile('^' + name + '=(.+?)$', sre.MULTILINE)
                a.content.data = reg.sub(name + '=' + text, a.content.data)
            else:
                m=empty_representation.match(repr)
                if m:
                    a.content.data = text
                else:
                    return False
            return True

        b=self.textview.get_buffer()
        impossible=[]
        for a in l:
            beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % a.id))
            enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % a.id))
            if update(a, b.get_text(beginiter, enditer)):
                self.controller.notify("AnnotationEditEnd", annotation=a)
            else:
                impossible.append(a)
        if impossible:
                advene.gui.util.message_dialog(label=_("Cannot convert the following annotations,\nthe representation pattern is too complex.\n%s") % ",".join( [ a.id for a in impossible ] ))
        return True

    def refresh(self, *p):
        self.update_model()
        return True

    def validate(self, *p):
        l=self.check_modified()
        if l:
            if self.options['representation'] and not parsed_representation.match(self.options['representation']):
                advene.gui.util.message_dialog(label=_("Cannot validate the update.\nThe representation pattern is too complex."))
                return True
            self.ignore_updates = True
            self.update_modified(l)
            self.ignore_updates = False
        return True

    def build_widget(self):
        mainbox = gtk.VBox()

        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            mainbox.pack_start(self.player_toolbar, expand=False)

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

    def representation(self, a):
        if self.options['default-representation']:
            rep=helper.get_title(self.controller, a)
        elif self.options['representation']:
            rep=helper.get_title(self.controller, a,
                                 representation=self.options['representation'])
        else:
            rep=a.content.data
        return rep

    def generate_buffer_content(self):
        b=self.textview.get_buffer()
        # Clear the buffer
        begin,end=b.get_bounds()
        b.delete(begin, end)

        l=list(self.model)
        #l.sort(lambda a,b: cmp(a.fragment.begin, b.fragment.begin))
        for a in l:
            if self.options['display-time']:
                b.insert_at_cursor("[%s]" % helper.format_time(a.fragment.begin))

            mark = b.create_mark("b_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            mark.set_visible(self.options['display-bounds'])

            b.insert_at_cursor(unicode(self.representation(a)))
            mark = b.create_mark("e_%s" % a.id,
                                 b.get_iter_at_mark(b.get_insert()),
                                 left_gravity=True)
            mark.set_visible(self.options['display-bounds'])

            if self.options['display-time']:
                b.insert_at_cursor("[%s]" % helper.format_time(a.fragment.end))

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
        return False

    def move_cursor_cb(self, textview, step_size, count, extend_selection):
        self.update_current_annotation()
        return False

    def update_model(self, package=None):
        self.regenerate_model()
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
        if self.ignore_updates:
            return True

        # Update the model value
        self.regenerate_model()

        if event == 'AnnotationActivate':
            self.activate_annotation(annotation)
            return True
        if event == 'AnnotationDeactivate':
            self.desactivate_annotation(annotation)
            return True
        if event == 'AnnotationCreate':
            # If it does not exist yet, we should create it if it is now in self.model
            if annotation in self.model:
                # Update the whole model.
                self.update_model()
            return True

        if event == 'AnnotationEditEnd':
            if not annotation in self.model:
                return True
            b=self.textview.get_buffer()
            beginmark=b.get_mark("b_%s" % annotation.id)
            endmark=b.get_mark("e_%s" % annotation.id)

            beginiter=b.get_iter_at_mark(beginmark)
            enditer  =b.get_iter_at_mark(endmark)

            b.delete(beginiter, enditer)
            b.insert(beginiter, unicode(self.representation(annotation)))
            # After insert, beginiter is updated to point to the end
            # of the invalidated text.
            b.move_mark(endmark, beginiter)
        elif event == 'AnnotationDelete':
            b=self.textview.get_buffer()
            # FIXME: handle the case where the annotation was not in
            # this transcription (i.e. beginmark does not exist)
            beginmark=b.get_mark("b_%s" % annotation.id)
            endmark=b.get_mark("e_%s" % annotation.id)
            beginiter=b.get_iter_at_mark(beginmark)
            enditer  =b.get_iter_at_mark(endmark)
            b.delete(beginiter, enditer)
            b.delete_mark(beginmark)
            b.delete_mark(endmark)
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
        if annotation is not None and annotation in self.model:
            self.activate_annotation (annotation)
        return True

    def desactivate_annotation_handler (self, context, parameters):
        annotation=context.evaluateValue('annotation')
        if annotation is not None and annotation in self.model:
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
            self.log(_("Cannot write to %(filename)s: %(error)s:") %
                     {'filename': filename, 
                      'error': unicode(e)})
            return True
        f.write(out)
        f.close()
        self.log(_("Transcription saved to %s") % filename)
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

