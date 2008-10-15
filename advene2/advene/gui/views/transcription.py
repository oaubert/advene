#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
"""Transcription view.
"""

import sys
import re
import sets

import gtk

import advene.core.config as config

# Advene part
from advene.model.cam.package import Package
from advene.gui.edit.properties import EditWidget

import advene.util.helper as helper

from gettext import gettext as _

from advene.gui.views import AdhocView
from advene.gui.util import dialog, get_small_stock_button, get_pixmap_button
import advene.gui.popup

parsed_representation = re.compile(r'^here/content/parsed/([\w\d_\.]+)$')
empty_representation = re.compile(r'^\s*$')

name="Transcription view plugin"

def register(controller):
    controller.register_viewclass(TranscriptionView)

class TranscriptionView(AdhocView):
    view_name = _("Transcription")
    view_id = 'transcription'
    tooltip = _("Representation of a set of annotation as a transcription")

    def __init__ (self, controller=None, source=None, elements=None, parameters=None):
        super(TranscriptionView, self).__init__(controller=controller)
        self.close_on_package_load = True
        self.contextual_actions = (
            (_("Save view"), self.save_view),
            (_("Save default options"), self.save_default_options),
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
            'autoscroll': True,
            }

        self.package=controller.package

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        a=dict(arg)
        if source is None and a.has_key('source'):
            source=a['source']

        if source is None and elements is None:
            # Use whole package
            source="here/annotations"

        # source is a TALES expression, which is evaluated in the
        # package context. It must return a list of annotations.
        self.source = source
        # elements is a list of annotations (typically the output of
        # an interactivequery). It is taken into account only if
        # source is None
        self.elements = elements

        self.model=[]
        self.regenerate_model()

        # Annotation where the cursor is set
        self.currentannotation=None

        # Used when batch-updating modified annotations when closing
        # the window
        self.ignore_updates = False

        self.modified=False

        self.quick_options=helper.CircularList( (
            # (separator, display_time)
            (" ", False),
            ("\n", False),
            ("\n", True),
            (" ", True),
            ) )

        # Try to determine a default representation
        try:
            t=sets.Set([ a.type for a in self.model ])
        except:
            t=[]
        if len(t) == 1:
            # Unique type, the model is homogeneous. Use the
            # annotation-type representation
            at=self.model[0].type
            rep=at.representation
            if rep is not None and not re.match(r'^\s*$', rep):
                # There is a standard representation for the type.
                # But if the current value is != '', then it has been
                # updated by the parameters, so keep it.
                if self.options['representation'] == '':
                    self.options['representation'] = rep
        self.widget=self.build_widget()

    def get_save_arguments(self):
        if self.source is not None:
            arguments = [ ('source', self.source) ]
        else:
            arguments = []
        return self.options, arguments

    def regenerate_model(self):
        if self.source is None:
            self.model=self.elements[:]
            return
        c=self.controller.build_context()
        try:
            self.model=c.evaluate(self.source)
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
        old_representation=cache['representation']
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
            if old_representation != cache['representation']:
                # The user-defined representation was changed. In most
                # cases, this means that the user wants to use it
                # instead of the default representation, so force
                # default-representation to False
                cache['default-representation']=False
            if cache['separator'] == user_defined:
                # User-defined has been selected. Use the user-separator value
                cache['separator']=cache['user-separator']
            self.options.update(cache)
            # Process special characters
            for c in ('representation', 'separator'):
                self.options[c]=self.options[c].replace('\\n', '\n').replace('\\t', '\t')
            self.generate_buffer_content()
        return True

    def close(self, *p):
        l=self.check_modified()
        if l:
            if self.options['representation'] and not parsed_representation.match(self.options['representation']):
                def close_cb():
                    AdhocView.close(self)
                    return True

                dialog.message_dialog(label=_("%d annotation(s) were modified\nbut we cannot propagate the modifications\nsince the representation parameter is used.") % len(l), callback=close_cb)
            else:
                def handle_modified():
                    self.log(_("Updating modified annotations"))
                    self.ignore_updates = True
                    self.update_modified(l)
                    AdhocView.close(self)
                    return True
                dialog.message_dialog(label=_("%d annotations were modified.\nDo you want to update their content?") % len(l),
                                      icon=gtk.MESSAGE_QUESTION,
                                      callback=handle_modified)
        else:
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
                rep=a.type.representation
            else:
                rep=self.options['representation']
            m=parsed_representation.match(rep)
            if m:
                # We have a simple representation (here/content/parsed/name)
                # so we can update the name field.
                name=m.group(1)
                reg = re.compile('^' + name + '=(.+?)$', re.MULTILINE)
                a.content.data = reg.sub(name + '=' + text, a.content.data)
            else:
                m=empty_representation.match(rep)
                if m:
                    a.content.data = text
                else:
                    return False
            return True

        b=self.textview.get_buffer()
        impossible=[]
        batch_id=object()
        for a in l:
            beginiter=b.get_iter_at_mark(b.get_mark("b_%s" % a.id))
            enditer  =b.get_iter_at_mark(b.get_mark("e_%s" % a.id))
            self.controller.notify('ElementEditBegin', element=a, immediate=True)
            if update(a, b.get_text(beginiter, enditer)):
                self.controller.notify("AnnotationEditEnd", annotation=a, batch=batch_id)
            else:
                impossible.append(a)
            self.controller.notify('ElementEditCancel', element=a)
        if impossible:
            dialog.message_dialog(label=_("Cannot convert the following annotations,\nthe representation pattern is too complex.\n%s") % ",".join( [ a.id for a in impossible ] ))
        return True

    def refresh(self, *p):
        self.update_model()
        return True

    def validate(self, *p):
        l=self.check_modified()
        if l:
            if self.options['representation'] and not parsed_representation.match(self.options['representation']):
                dialog.message_dialog(label=_("Cannot validate the update.\nThe representation pattern is too complex."))
                return True
            self.ignore_updates = True
            self.update_modified(l)
            self.ignore_updates = False
        return True

    def show_searchbox(self, *p):
        self.searchbox.show_all()
        self.searchbox.entry.grab_focus()
        return True

    def quick_options_toggle(self, *p):
        """Quickly toggle between different presentation options.
        """
        self.options['separator'], self.options['display-time']=self.quick_options.next()
        self.refresh()
        return True

    def build_widget(self):
        mainbox = gtk.VBox()

        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        for icon, action, tip in (
            (gtk.STOCK_SAVE, self.save_transcription, _("Save transcription to a text file")),
            (gtk.STOCK_APPLY, self.validate, _("Apply the modifications")),
            (gtk.STOCK_FIND, self.show_searchbox, _("Find text")),
            (gtk.STOCK_REDO, self.quick_options_toggle, _("Quickly switch display options")),
            (gtk.STOCK_REFRESH, self.refresh, _("Refresh the transcription")),
            (gtk.STOCK_PREFERENCES, self.edit_options, _("Edit preferences")),
            ):
            b=gtk.ToolButton(stock_id=icon)
            b.set_tooltip(self.controller.gui.tooltips, tip)
            b.connect('clicked', action)
            tb.insert(b, -1)
        mainbox.pack_start(tb, expand=False)

        #if self.controller.gui:
        #    self.player_toolbar=self.controller.gui.get_player_control_toolbar()
        #    mainbox.pack_start(self.player_toolbar, expand=False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_resize_mode(gtk.RESIZE_PARENT)
        mainbox.add (sw)

        self.textview = gtk.TextView()
        # We could make it editable and modify the annotation
        self.textview.set_editable(True)
        self.textview.set_wrap_mode (gtk.WRAP_WORD)
        b=self.textview.get_buffer()

        # Create useful tags
        b.create_tag("activated", background="skyblue")
        b.create_tag("current", background="lightblue")
        b.create_tag("searched_string", background="green")

        self.generate_buffer_content()

        self.textview.connect('button-press-event', self.button_press_event_cb)
        self.textview.connect_after('move-cursor', self.move_cursor_cb)
        self.textview.connect('populate-popup', self.populate_popup_cb)

        self.update_current_annotation(self.textview, None)

        sw.add(self.textview)

        self.searchbox=gtk.HBox()

        def hide_searchbox(*p):
            # Clear the searched_string tags
            b=self.textview.get_buffer()
            b.remove_tag_by_name("searched_string", *b.get_bounds())
            self.searchbox.hide()
            return True

        close_button=get_pixmap_button('small_close.png', hide_searchbox)
        close_button.set_relief(gtk.RELIEF_NONE)
        self.searchbox.pack_start(close_button, expand=False, fill=False)

        def search_entry_cb(e):
            self.highlight_search_forward(e.get_text())
            return True

        def search_entry_key_press_cb(e, event):
            if event.keyval == gtk.keysyms.Escape:
                hide_searchbox()
                return True
            return False

        self.searchbox.entry=gtk.Entry()
        self.searchbox.entry.connect('activate', search_entry_cb)
        self.searchbox.pack_start(self.searchbox.entry, expand=False, fill=False)
        self.searchbox.entry.connect('key-press-event', search_entry_key_press_cb)

#        def find_next(b):
#            # FIXME
#            return True
#
#        b=get_small_stock_button(gtk.STOCK_GO_FORWARD, find_next)
#        b.set_relief(gtk.RELIEF_NONE)
#        self.controller.gui.tooltips.set_tip(b, _("Find next occurrence"))
#        self.searchbox.pack_start(b, expand=False, fill=False)

        fill=gtk.HBox()
        self.searchbox.pack_start(fill, expand=True, fill=True)

        mainbox.pack_start(self.searchbox, expand=False)

        self.statusbar=gtk.Statusbar()
        self.statusbar.set_has_resize_grip(False)
        mainbox.pack_start(self.statusbar, expand=False)

        mainbox.show_all()

        hide_searchbox()

        # Ignore show_all method to keep the searchbar hidden, and
        # we already did it anyway.
        mainbox.set_no_show_all(True)

        mainbox.connect('key-press-event', self.key_press_event_cb)

        return mainbox

    def representation(self, a):
        if self.options['default-representation']:
            rep=self.controller.get_title(a)
        elif self.options['representation']:
            rep=self.controller.get_title(a,
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
        for a in l:
            if self.options['display-time']:
                b.insert_at_cursor("[%s]" % helper.format_time(a.begin))

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
                b.insert_at_cursor("[%s]" % helper.format_time(a.end))

            b.insert_at_cursor(self.options['separator'])
        return

    def highlight_search_forward(self, searched):
        """Highlight with the searched_string tag the given string.
        """
        b=self.textview.get_buffer()
        begin, end=b.get_bounds()
        # Remove searched_string tag occurences that may be left from
        # a previous invocation
        b.remove_tag_by_name("searched_string", begin, end)

        finished=False

        while not finished:
            res=begin.forward_search(searched, gtk.TEXT_SEARCH_TEXT_ONLY)
            if not res:
                finished=True
            else:
                matchStart, matchEnd = res
                b.apply_tag_by_name("searched_string", matchStart, matchEnd)
                begin=matchEnd

    def play_annotation(self, a):
        c=self.controller
        pos = c.create_position (value=a.begin,
                                 key=c.player.MediaTime,
                                 origin=c.player.AbsolutePosition)
        c.update_status (status="set", position=pos)
        c.gui.set_current_annotation(a)
        return True

    def populate_popup_cb(self, textview, menu):
        if self.currentannotation is None:
            return False

        item=gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)

        item = gtk.MenuItem(_("Annotation %s") % self.currentannotation.id, use_underline=False)
        menuc=advene.gui.popup.Menu(self.currentannotation,
                                    controller=self.controller)
        item.set_submenu(menuc.menu)
        item.show()
        menu.append(item)

        def play_annotation(i, a):
            self.play_annotation(a)
            return True

        item = gtk.MenuItem(_("Play"))
        item.connect('activate', play_annotation, self.currentannotation)
        item.show()
        menu.append(item)

        return False

    def key_press_event_cb (self, textview, event):
        if event.keyval == gtk.keysyms.F3:
            self.searchbox.show_all()
            return True
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
        if self.currentannotation is not None and event.type == gtk.gdk._2BUTTON_PRESS:
            # Double click -> goto annotation
            self.play_annotation(self.currentannotation)
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
            a=self.package.get(annotationid)
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

    def position_reset(self):
        # The position was reset. Deactivate active annotations.
        b=self.textview.get_buffer()
        b.remove_tag_by_name('activated', *b.get_bounds())
        return True

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
            beginmark=b.get_mark("b_%s" % annotation.id)
            endmark=b.get_mark("e_%s" % annotation.id)
            if beginmark is None or endmark is None:
                return True
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
        if self.options['autoscroll']:
            # Make sure that the annotation is visible
            m=self.textview.get_buffer().get_mark("b_%s" % a.id)
            if m:
                self.textview.scroll_to_mark(m, 0.2)

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
        annotation=context.evaluate('annotation')
        if annotation is not None and annotation in self.model:
            self.activate_annotation (annotation)
        return True

    def desactivate_annotation_handler (self, context, parameters):
        annotation=context.evaluate('annotation')
        if annotation is not None and annotation in self.model:
            self.desactivate_annotation (annotation)
        return True

    def save_transcription(self, button=None):
        fname=dialog.get_filename(title= ("Save transcription to..."),
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
            self.message(_("Cannot write to %(filename)s: %(error)s:") %
                     {'filename': filename,
                      'error': unicode(e)})
            return True
        f.write(out)
        f.close()
        self.message(_("Transcription saved to %s") % filename)
        return True
