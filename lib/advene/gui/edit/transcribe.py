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
import os
import operator

import gtk

import urllib

import advene.core.config as config

# Advene part
from advene.model.package import Package
from advene.model.schema import AnnotationType

import advene.util.importer

import advene.util.helper as helper

from gettext import gettext as _

from advene.gui.views import AdhocView
from advene.gui.util import dialog, get_pixmap_button, get_small_stock_button
from advene.gui.util import encode_drop_parameters, decode_drop_parameters
from advene.gui.edit.properties import EditWidget
from advene.gui.util.completer import Completer
from advene.gui.widget import TimestampRepresentation

class TranscriptionImporter(advene.util.importer.GenericImporter):
    """Transcription importer.
    """
    def __init__(self, transcription_edit=None, **kw):
        super(TranscriptionImporter, self).__init__(**kw)
        self.transcription_edit=transcription_edit
        self.name = _("Transcription importer")

    def process_file(self, filename):
        if filename != 'transcription':
            return None
        if self.package is None:
            self.init_package()
        self.convert(self.transcription_edit.parse_transcription())
        return self.package

class TranscriptionEdit(AdhocView):
    view_name = _("Note taking")
    view_id = 'transcribe'
    tooltips = _("Note taking facility")
    def __init__ (self, controller=None, parameters=None, filename=None):
        super(TranscriptionEdit, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Save view"), self.save_view),
            (_("Save default options"), self.save_default_options),
            )

        self.controller=controller
        self.package=controller.package
        self.tooltips=gtk.Tooltips()

        self.sourcefile=None
        self.empty_re = re.compile('^\s*$')

        self.options = {
            'timestamp': True, # _("If checked, click inserts timestamp marks"))
            'play-on-scroll': False,
            'empty-annotations': True, # _("Do not generate annotations for empty text"))
            'delay': config.data.reaction_time,
            # Marks will be automatically inserted it no keypress occurred in the 3 previous seconds.
            'automatic-mark-insertion-delay': 1500,
            'insert-on-single-click': False,
            'autoscroll': True,
            'autoinsert': True,
            }

        self.colors = {
            'default': gtk.gdk.color_parse ('lightblue'),
            'ignore':  gtk.gdk.color_parse ('tomato'),
            'current': gtk.gdk.color_parse ('green'),
            }

        self.marks = []

        self.current_mark = None

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)

        self.button_height=20

        # When modifying an offset with Control+Scroll, store the last value.
        # If play-on-scroll, then set the destination upon Control release
        self.timestamp_play = None

        self.widget=self.build_widget()
        if filename is not None:
            self.load_transcription(filename=filename)
        for n, v in arg:
            if n == 'text':
                self.load_transcription(buffer=urllib.unquote(v))

    def get_save_arguments(self):
        b=self.textview.get_buffer()
        arguments = [ ('text', urllib.quote_plus("".join(self.generate_transcription()))) ]
        return self.options, arguments

    def edit_preferences(self, *p):
        cache=dict(self.options)

        ew=EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Preferences"))
        ew.add_checkbox(_("Timestamp"), "timestamp", _("Click inserts timestamp marks"))
        ew.add_checkbox(_("Insert on single-click"), 'insert-on-single-click', _("A single click will insert the mark (else a double click is needed)"))
        ew.add_checkbox(_("Play on scroll"), "play-on-scroll", _("Play the new position upon timestamp modification"))
        ew.add_checkbox(_("Generate empty annotations"), "empty-annotations", _("If checked, generate annotations for empty text"))
        ew.add_spin(_("Reaction time"), "delay", _("Reaction time (substracted from current player time)"), -5000, 5000)
        ew.add_checkbox(_("Auto-insert"), "autoinsert", _("Automatic timestamp mark insertion"))
        ew.add_spin(_("Automatic insertion delay"), 'automatic-mark-insertion-delay', _("If autoinsert is active, timestamp marks will be automatically inserted when text is entered after no interaction since this delay (in ms).\n1000 is typically a good value."), 0, 100000)

        res=ew.popup()
        if res:
            self.options.update(cache)
        return True

    def show_searchbox(self, *p):
        self.searchbox.show()
        self.searchbox.entry.grab_focus()
        return True

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

    def textview_drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.data)
            position=long(data['timestamp'])
            #(x, y) = self.textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
            #                                               int(x),
            #                                               int(y))
            it=self.textview.get_iter_at_location(x, y)
            if it is None:
                return False
            # Check that preceding mark.value is lower
            m, i=self.find_preceding_mark(it)
            if m is not None and m.value > position:
                self.message(_("Invalid timestamp mark"))
                return False
            m, i=self.find_following_mark(it)
            if m is not None and m.value < position:
                self.message(_("Invalid timestamp mark"))
                return False
            # Create the timestamp
            self.create_timestamp_mark(position, it)

            # If the drag originated from our own widgets, remove it.
            source=context.get_source_widget()
            if source in self.marks:
                self.remove_timestamp_mark(source)
            return True
        return False

    def build_widget(self):
        vbox = gtk.VBox()

        hb=gtk.HBox()
        vbox.pack_start(hb, expand=False)
        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(self.player_toolbar)
        hb.add(self.get_toolbar())

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add (sw)

        self.textview = gtk.TextView()
        # We could make it editable and modify the annotation
        self.textview.set_editable(True)
        self.textview.set_wrap_mode (gtk.WRAP_WORD)

        # 0-mark at the beginning
        zero=self.create_timestamp_mark(0, self.textview.get_buffer().get_start_iter())
        self.current_mark=zero

        # Memorize the last keypress time
        self.last_keypress_time = 0

        self.textview.connect("button-press-event", self.button_press_event_cb)
        self.textview.connect("key-press-event", self.key_pressed_cb)
        self.textview.get_buffer().create_tag("past", background="#dddddd")
        self.textview.get_buffer().create_tag("ignored", strikethrough=True)

        self.textview.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                    gtk.DEST_DEFAULT_HIGHLIGHT |
                                    gtk.DEST_DEFAULT_ALL,
                                    config.data.drag_type['timestamp']
                                    ,
                                    gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.textview.connect("drag_data_received", self.textview_drag_received)
        
        # Hook the completer component
        completer=Completer(textview=self.textview,
                            controller=self.controller,
                            element=self.textview.get_buffer(),
                            indexer=self.controller.package._indexer)

        sw.add(self.textview)

        # Search box
        b=self.textview.get_buffer()

        # Create useful tags
        b.create_tag("activated", background="skyblue")
        b.create_tag("current", background="lightblue")
        b.create_tag("searched_string", background="green")

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

        b=get_small_stock_button(gtk.STOCK_FIND)
        b.connect('clicked', lambda b: self.highlight_search_forward(self.searchbox.entry.get_text()))
        self.searchbox.pack_start(b, expand=False)

        fill=gtk.HBox()
        self.searchbox.pack_start(fill, expand=True, fill=True)
        self.searchbox.show_all()
        self.searchbox.hide()

        self.searchbox.set_no_show_all(True)
        vbox.pack_start(self.searchbox, expand=False)

        self.statusbar=gtk.Statusbar()
        self.statusbar.set_has_resize_grip(False)
        vbox.pack_start(self.statusbar, expand=False)
        vbox.show_all()

        return vbox

    def remove_timestamp_mark(self, mark):
        b=self.textview.get_buffer()
        self.marks.remove(mark)
        begin=b.get_iter_at_child_anchor(mark.anchor)
        end=begin.copy()
        end.forward_char()
        b.delete_interactive(begin, end, True)
        mark.destroy()
        return True

    def insert_timestamp_mark(self, it=None):
        """Insert a timestamp mark with the current player position.
        
        If iter is not specified, insert at the current cursor position.
        """
        t=self.controller.player.current_position_value - self.options['delay']
        self.controller.update_snapshot(t)

        if it is None:
            b=self.textview.get_buffer()
            it=b.get_iter_at_mark(b.get_insert())

        m, i=self.find_preceding_mark(it)
        if m is not None and m.value >= t:
            self.message(_("Invalid timestamp mark"))
            return False
        m, i=self.find_following_mark(it)
        if m is not None and m.value <= t:
            self.message(_("Invalid timestamp mark"))
            return False

        self.create_timestamp_mark(t, it)

    def button_press_event_cb(self, textview, event):
        if not self.options['timestamp']:
            return False
        if event.state & gtk.gdk.CONTROL_MASK:
            return False

        if self.options['insert-on-single-click']:
            t=gtk.gdk.BUTTON_PRESS
        else:
            t=gtk.gdk._2BUTTON_PRESS
        if not (event.button == 1 and event.type == t):
            return False
        textwin=textview.get_window(gtk.TEXT_WINDOW_TEXT)

        if event.window != textwin:
            print "Event.window: %s" % str(event.window)
            print "Textwin: %s" % str(textwin)
            return False

        (x, y) = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
                                                  int(event.x),
                                                  int(event.y))
        it=textview.get_iter_at_location(x, y)
        if it is None:
            print "Error in get_iter_at_location"
            return False

        p=self.controller.player
        if (p.status == p.PlayingStatus or p.status == p.PauseStatus):
            self.insert_timestamp_mark(it=it)
            return True
        return False

    def buffer_is_empty(self):
        b=self.textview.get_buffer()
        return len(b.get_text(*b.get_bounds())) == 0

    def toggle_ignore(self, button):
        button.ignore = not button.ignore
        self.update_mark(button)
        b=self.textview.get_buffer()
        it=b.get_iter_at_child_anchor(button.anchor)
        if it is None:
            return button
        next_anchor, next_it=self.find_following_mark(it)
        if next_it is None:
            next_it=b.get_bounds()[1]
        if button.ignore:
            b.apply_tag_by_name('ignored', it, next_it)
        else:
            b.remove_tag_by_name('ignored', it, next_it)
        return button

    def update_mark(self, button):
        if button.ignore:
            button.set_color(self.colors['ignore'])
        else:
            button.set_color(self.colors['default'])
        return

    def mark_button_press_cb(self, button, event, anchor=None, child=None):
        """Handler for right-button click on timestamp mark.
        """
        timestamp=button.value
        def popup_goto (win, position):
            c=self.controller
            pos = c.create_position (value=position,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            return True

        def popup_ignore(win, button):
            self.toggle_ignore(button)
            return True

        def popup_remove(win):
            self.remove_timestamp_mark(child)
            return True

        def popup_modify(win, t):
            timestamp=child.value + t
            self.tooltips.set_tip(child, "%s" % helper.format_time(timestamp))
            if self.tooltips.active_tips_data is None:
                button.emit('show-help', gtk.WIDGET_HELP_TOOLTIP)
            child.value=timestamp
            if self.options['play-on-scroll']:
                popup_goto(child, timestamp)
            return True

        if event.button == 1 and event.state & gtk.gdk.CONTROL_MASK:
            # Set current video time
            popup_modify(None, self.controller.player.current_position_value - timestamp)
            return True

        if event.button != 3:
            return False

        # Create a popup menu for timestamp
        menu = gtk.Menu()

        item = gtk.MenuItem(_("Position %s") % helper.format_time(timestamp))
        menu.append(item)

        item = gtk.SeparatorMenuItem()
        menu.append(item)

        item = gtk.MenuItem(_("Go to..."))
        item.connect("activate", popup_goto, timestamp)
        menu.append(item)

        item = gtk.MenuItem(_("Ignore the following text (toggle)"))
        item.connect("activate", popup_ignore, button)
        menu.append(item)

        item = gtk.MenuItem(_("Remove mark"))
        item.connect("activate", popup_remove)
        menu.append(item)

        item = gtk.MenuItem(_("Reaction-time offset"))
        item.connect("activate", popup_modify, -self.options['delay'])
        menu.append(item)

        item = gtk.MenuItem(_("-1 sec"))
        item.connect("activate", popup_modify, -1000)
        menu.append(item)
        item = gtk.MenuItem(_("-0.5 sec"))
        item.connect("activate", popup_modify, -500)
        menu.append(item)
        item = gtk.MenuItem(_("-0.1 sec"))
        item.connect("activate", popup_modify, -100)
        menu.append(item)

        item = gtk.MenuItem(_("+1 sec"))
        item.connect("activate", popup_modify, 1000)
        menu.append(item)
        item = gtk.MenuItem(_("+0.5 sec"))
        item.connect("activate", popup_modify, 500)
        menu.append(item)
        item = gtk.MenuItem(_("+0.1 sec"))
        item.connect("activate", popup_modify, 100)
        menu.append(item)

        menu.show_all()

        menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def create_timestamp_mark(self, timestamp, it):
        def popup_goto (b):
            c=self.controller
            pos = c.create_position (value=b.value,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            return True

        b=self.textview.get_buffer()
        anchor=b.create_child_anchor(it)
        # Create the mark representation
        child=TimestampRepresentation(timestamp, self.controller, width=50)
        child.anchor=anchor
        child.connect('clicked', popup_goto)
        child.popup_menu=None
        child.connect("button-press-event", self.mark_button_press_cb, anchor, child)

        def handle_scroll_event(button, event):
            if not (event.state & gtk.gdk.CONTROL_MASK):
                return True
            if event.direction == gtk.gdk.SCROLL_DOWN:
                button.value += config.data.preferences['scroll-increment']
            elif event.direction == gtk.gdk.SCROLL_UP:
                button.value -= config.data.preferences['scroll-increment']
            self.tooltips.set_tip(button, "%s" % helper.format_time(button.value))
            if self.tooltips.active_tips_data is None:
                button.emit('show-help', gtk.WIDGET_HELP_TOOLTIP)
            self.timestamp_play = button.value
            button.grab_focus()
            return True

        def mark_key_release_cb(button, event, anchor=None, child=None):
            """Handler for key release on timestamp mark.
            """
            # Control key released. Goto the position if we were scrolling a mark
            if self.timestamp_play is not None and (event.state & gtk.gdk.CONTROL_MASK):
                # self.timestamp_play contains the new value, but child.timestamp
                # as well. So we can use popup_goto
                self.timestamp_play = None
                popup_goto(child)
                return True
            return False

        child.connect("scroll-event", handle_scroll_event)
        child.connect("key-release-event", mark_key_release_cb, anchor, child)
        self.tooltips.set_tip(child, "%s" % helper.format_time(timestamp))
        child.value=timestamp
        child.ignore=False
        self.update_mark(child)
        child.show_all()
        child.label.set_no_show_all(True)
        child.label.hide()
        self.textview.add_child_at_anchor(child, anchor)

        self.marks.append(child)
        self.marks.sort(key=lambda a: a.value)
        return child

    def populate(self, annotations):
        """Populate the buffer with data taken from the given annotations.
        """
        b=self.textview.get_buffer()
        # Clear the buffer
        begin,end=b.get_bounds()
        b.delete(begin, end)
        # FIXME: check for conflicting bounds
        l=[ (a.fragment.begin, a.fragment.end, a)
            for a in annotations ]
        l.sort(key=operator.itemgetter(0))
        last_end=-1
        for (begin, end, a) in l:
            if begin < last_end or end < last_end:
                self.log(_("Invalid timestamp"))
                pass
            it=b.get_iter_at_mark(b.get_insert())
            self.create_timestamp_mark(begin, it)
            b.insert_at_cursor(unicode(a.content.data))
            it=b.get_iter_at_mark(b.get_insert())
            self.create_timestamp_mark(end, it)
            last_end=end
        return

    def find_preceding_mark(self, i):
        """Find the mark preceding the iterator.

        Return mark, it if found
        Returns None, None if no mark exists.
        """
        it=i.copy()
        while it.backward_char():
            a=it.get_child_anchor()
            if a and a.get_widgets():
                # Found a TextAnchor
                return a.get_widgets()[0], it.copy()
        return None, None

    def find_following_mark(self, i):
        """Find the mark following the iterator.

        Return mark, it if found
        Returns None, None if no mark exists.
        """
        it=i.copy()
        while it.forward_char():
            a=it.get_child_anchor()
            if a and a.get_widgets():
                # Found a TextAnchor
                return a.get_widgets()[0], it.copy()
        return None, None

    def goto_previous_mark(self):
        c=self.controller
        if self.current_mark is None:
            if self.marks:
                pos = c.create_position (value=self.marks[0].value,
                                         key=c.player.MediaTime,
                                         origin=c.player.AbsolutePosition)
                c.update_status (status="set", position=pos)
        else:
            i=self.marks.index(self.current_mark) - 1
            m=self.marks[i]
            pos = c.create_position (value=m.value,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
        return True

    def goto_next_mark(self):
        c=self.controller
        if self.current_mark is None:
            if self.marks:
                pos = c.create_position (value=self.marks[-1].value,
                                         key=c.player.MediaTime,
                                         origin=c.player.AbsolutePosition)
                c.update_status (status="set", position=pos)
        else:
            i=(self.marks.index(self.current_mark) + 1) % len(self.marks)
            m=self.marks[i]
            pos = c.create_position (value=m.value,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
        return True

    def update_position(self, pos):
        l=[ m for m in self.marks if m.value <= pos and not m.anchor.get_deleted() ]
        if l:
            cm=l[-1]
            if cm != self.current_mark:
                # Restore the properties of the previous current mark
                if self.current_mark is not None:
                    self.update_mark(self.current_mark)
                cm.set_color(self.colors['current'])
                b=self.textview.get_buffer()
                begin, end = b.get_bounds()
                b.remove_tag_by_name('past', begin, end)
                it=b.get_iter_at_child_anchor(cm.anchor)
                if it is not None:
                    b.apply_tag_by_name('past', begin, it)
                    if self.options['autoscroll']:
                        self.textview.scroll_to_iter(it, 0.3)
                self.current_mark = cm
        else:
            if self.current_mark is not None:
                self.update_mark(self.current_mark)
            self.current_mark=None
        return True

    def parse_transcription(self, show_ignored=False, strip_blank=True):
        """Parse the transcription text.

        If show_ignored, then generate a 'ignored' key for ignored
        texts.

        If strip_blank, then strip leading and trailing whitespace and
        newline for each annotation.

        Return : a iterator on a dict with keys
        'begin', 'end', 'content'
        (compatible with advene.util.importer)
        """

        b=self.textview.get_buffer()
        begin=b.get_start_iter()
        end=begin.copy()

        # Special case for the first mark: if the first item in the
        # buffer is a mark, use its time. Else, initialize the time at 0
        a=begin.get_child_anchor()
        if a and a.get_widgets():
            # Found a TextAnchor
            child=a.get_widgets()[0]
            t=child.value
        else:
            t=0

        ignore_next=False
        while end.forward_char():
            a=end.get_child_anchor()
            if a and a.get_widgets():
                # Found a TextAnchor
                child=a.get_widgets()[0]
                timestamp=child.value
                if timestamp < t:
                    # Invalid timestamp mark.
                    self.log(_('Invalid timestamp mark in conversion: %s') % helper.format_time(timestamp))
                    t=timestamp
                    continue
                text=b.get_text(begin, end, include_hidden_chars=False)
                if strip_blank:
                    text=text.rstrip().lstrip()
                if self.empty_re.match(text) and not self.options['empty-annotations']:
                    pass
                elif ignore_next:
                    if show_ignored:
                        yield { 'begin': t,
                                'end':   timestamp,
                                'content': text,
                                'ignored': True }
                else:
                    yield { 'begin': t,
                            'end':   timestamp,
                            'content': text,
                            'ignored': False }
                ignore_next=child.ignore
                t=timestamp
                begin=end.copy()
        # End of buffer. Create the last annotation
        timestamp=self.controller.cached_duration
        text=b.get_text(begin, end, include_hidden_chars=False)
        if self.empty_re.match(text) or ignore_next:
            # Last timestsamp mark
            pass
        else:
            yield { 'begin': t,
                    'end': timestamp,
                    'content': text,
                    'ignored': False }

    def generate_transcription(self):
        last=None
        for d in self.parse_transcription(show_ignored=True,
                                          strip_blank=False):
            if d['ignored']:
                yield '[I%s]' % helper.format_time(d['begin'])
                yield d['content']
                yield '[%s]' % helper.format_time(d['end'])

            elif last != d['begin']:
                yield '[%s]' % helper.format_time(d['begin'])
                yield d['content']
                yield '[%s]' % helper.format_time(d['end'])
            else:
                yield d['content']
                yield '[%s]' % helper.format_time(d['end'])
            last=d['end']

    def save_as_cb(self, button=None):
        self.sourcefile=None
        self.save_transcription_cb()
        return True

    def save_transcription_cb(self, button=None):
        if self.sourcefile:
            fname=self.sourcefile
        else:
            fname=dialog.get_filename(title= ("Save transcription to..."),
                                               action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                               button=gtk.STOCK_SAVE,
                                               default_dir=config.data.path['data'])
        if fname is not None:
            self.save_transcription(filename=fname)
        return True

    def save_transcription(self, filename=None):
        if os.path.splitext(filename)[1] == '':
            # No extension was given. Add '.txt'
            filename=filename+'.txt'
        try:
            f=open(filename, "w")
        except IOError, e:
            dialog.message_dialog(
                _("Cannot save the file: %s") % unicode(e),
                icon=gtk.MESSAGE_ERROR)
            return True
        f.writelines(self.generate_transcription())
        f.close()
        self.message(_("Transcription saved to %s") % filename)
        self.sourcefile=filename
        return True

    def load_transcription_cb(self, button=None):
        if not self.buffer_is_empty():
            if not dialog.message_dialog(_("This will overwrite the current textual content. Are you sure?"),
                                                  icon=gtk.MESSAGE_QUESTION):
                return True
        fname=dialog.get_filename(title=_("Select transcription file to load"),
                                           default_dir=config.data.path['data'])
        if fname is not None:
            self.load_transcription(filename=fname)
        return True

    def load_transcription(self, filename=None, buffer=None):
        if buffer is None:
            try:
                if re.match('[a-zA-Z]:', filename):
                    # Windows drive: notation. Convert it to
                    # a more URI-compatible syntax
                    fname=urllib.pathname2url(filename)
                else:
                    fname=filename
                f=urllib.urlopen(fname)
            except IOError, e:
                self.message(_("Cannot open %(filename)s: %(error)s") % {'filename': filename,
                                                                         'error': unicode(e) })
                return
            lines="".join(f.readlines())
            f.close()
        else:
            lines=buffer

        try:
            data=unicode(lines, 'utf8')
        except UnicodeDecodeError:
            # Try UTF-16, which is used in quicktime text format
            try:
                data=unicode(lines, 'utf16')
            except UnicodeDecodeError:
                # Fallback on latin1, which is very common, but may
                # sometimes fail
                data=unicode(lines, 'latin1')

        b=self.textview.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)

        mark_re=re.compile('\[(I?)(\d+:\d+:\d+.?\d*)\]([^\[]*)')

        # 0-mark at the beginning
        self.create_timestamp_mark(0, begin)
        last_time=0

        m=mark_re.search(data)
        if m:
            # Handle the start case: there may be some text before the
            # first mark
            b.insert_at_cursor(data[:m.start()])
            for m in mark_re.finditer(data):
                # We set the sourcefile if it was already a timestamped
                # transcription: we do not want to overwrite a plain
                # transcription by mistake
                self.sourcefile=filename
                ignore, timestamp, text = m.group(1, 2, 3)
                t=helper.convert_time(timestamp)
                if last_time != t or ignore:
                    it=b.get_iter_at_mark(b.get_insert())
                    mark=self.create_timestamp_mark(t, it)
                    if ignore:
                        mark.ignore=True
                        self.update_mark(mark)
                    last_time = t
                b.insert_at_cursor(text)
        else:
            b.insert_at_cursor(data)
        return

    def import_annotations_cb(self, button=None):
        if not self.controller.gui:
            self.message(_("Cannot import annotations: no existing interface"))
            return True
        at=self.controller.gui.ask_for_annotation_type(text=_("Select the annotation type to import"), create=False)
        if at is None:
            return True

        if not self.buffer_is_empty():
            if not dialog.message_dialog(_("This will overwrite the current textual content. Are you sure?"),
                                                  icon=gtk.MESSAGE_QUESTION):
                return True

        b=self.textview.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)

        al=at.annotations
        al.sort(key=lambda a: a.fragment.begin)

        last_time=None

        for a in al:
            if a.fragment.begin > last_time:
                it=b.get_iter_at_mark(b.get_insert())
                mark=self.create_timestamp_mark(a.fragment.begin, it)
            b.insert_at_cursor(a.content.data)
            it=b.get_iter_at_mark(b.get_insert())
            mark=self.create_timestamp_mark(a.fragment.end, it)
            last_time = a.fragment.end
        return True

    def convert_transcription_cb(self, button=None):
        if not self.controller.gui:
            self.message(_("Cannot convert the data: no associated package"))
            return True

        d = gtk.Dialog(title=_("Converting transcription"),
                       parent=None,
                       flags=gtk.DIALOG_DESTROY_WITH_PARENT,
                       buttons=( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                 gtk.STOCK_OK, gtk.RESPONSE_OK,
                                 ))
        l=gtk.Label(_("Choose the annotation-type where to create annotations.\n"))
        l.set_line_wrap(True)
        l.show()
        d.vbox.pack_start(l, expand=False)

        # Anticipated declaration of some widgets, which need to be
        # updated in the handle_new_type_selection callback.
        new_type_dialog=gtk.VBox()
        delete_existing_toggle=gtk.CheckButton(_("Delete existing annotations in this type"))
        delete_existing_toggle.set_active(False)

        ats=list(self.controller.package.annotationTypes)
        newat=helper.TitledElement(value=None,
                                   title=_("Create a new annotation type"))
        ats.append(newat)

        def handle_new_type_selection(combo):
            el=combo.get_current_element()
            if el == newat:
                new_type_dialog.show()
                delete_existing_toggle.set_sensitive(False)
            else:
                new_type_dialog.hide()
                delete_existing_toggle.set_sensitive(True)
            return True

        type_selection=dialog.list_selector_widget(members=[ (a, self.controller.get_title(a)) for a in ats],
                                                   callback=handle_new_type_selection)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Select type") + " "), expand=False)
        hb.pack_start(type_selection, expand=False)
        d.vbox.pack_start(hb, expand=False)

        l=gtk.Label(_("You want to create a new type. Please specify its schema and title."))
        l.set_line_wrap(True)
        l.show()
        new_type_dialog.pack_start(l, expand=False)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Title") + " "), expand=False)
        new_title=gtk.Entry()
        hb.pack_start(new_title)
        new_type_dialog.pack_start(hb, expand=False)

        hb=gtk.HBox()
        hb.pack_start(gtk.Label(_("Containing schema") + " "), expand=False)
        schemas=list(self.controller.package.schemas)
        schema_selection=dialog.list_selector_widget(members=[ (s, self.controller.get_title(s)) for s in schemas])
        hb.pack_start(schema_selection, expand=False)
        new_type_dialog.pack_start(hb, expand=False)

        new_type_dialog.show_all()
        new_type_dialog.set_no_show_all(True)
        new_type_dialog.hide()

        d.vbox.pack_start(new_type_dialog)

        l=gtk.Label()
        l.set_markup("<b>" + _("Export options") + "</b>")
        d.vbox.pack_start(l, expand=False)

        d.vbox.pack_start(delete_existing_toggle, expand=False)

        empty_contents_toggle=gtk.CheckButton(_("Generate annotations for empty contents"))
        empty_contents_toggle.set_active(self.options['empty-annotations'])
        d.vbox.pack_start(empty_contents_toggle, expand=False)

        d.connect("key_press_event", dialog.dialog_keypressed_cb)

        d.show_all()
        dialog.center_on_mouse(d)

        finished=None
        while not finished:
            res=d.run()
            if res == gtk.RESPONSE_OK:
                at=type_selection.get_current_element()
                if at == newat:
                    new_type_title=new_title.get_text()
                    if new_type_title == '':
                        # Empty title. Generate one.
                        id_=self.controller.package._idgenerator.get_id(AnnotationType)
                        new_type_title=id_
                    else:
                        id_=helper.title2id(new_type_title)
                        # Check that the id is available
                        if self.controller.package._idgenerator.exists(id_):
                            dialog.message_dialog(
                                _("The %s identifier already exists. Choose another one.") % id_,
                                icon=gtk.MESSAGE_WARNING)
                            at=None
                            continue
                    # Creating a new type
                    s=schema_selection.get_current_element()
                    at=s.createAnnotationType(ident=id_)
                    at.author=config.data.userid
                    at.date=self.controller.get_timestamp()
                    at.title=new_type_title
                    at.mimetype='text/plain'
                    at.setMetaData(config.data.namespace, 'color', s.rootPackage._color_palette.next())
                    at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                    s.annotationTypes.append(at)
                    self.controller.notify('AnnotationTypeCreate', annotationtype=at)

                if delete_existing_toggle.get_active():
                    # Remove all annotations of at type
                    for a in at.annotations:
                        self.controller.delete_annotation(a)

                self.options['empty-annotations']=empty_contents_toggle.get_active()
                finished=True
            else:
                at=None
                finished=True
        d.destroy()

        if at is not None:
            ti=TranscriptionImporter(package=self.controller.package,
                                     controller=self.controller,
                                     defaulttype=at,
                                     transcription_edit=self)
            ti.process_file('transcription')

            self.controller.package._modified=True
            self.controller.notify("PackageActivate", package=ti.package)
            self.message(_('Notes converted'))
            self.log(ti.statistics_formatted())
            # Feedback
            dialog.message_dialog(
                _("Conversion completed.\n%s annotations generated.") % ti.statistics['annotation'])

        return True

    def set_snapshot_scale(self, size):
        for m in self.marks:
            m.width=size
            m.refresh()
            
    def scale_snaphots_menu(self, i):
        def set_scale(i, s):
            self.set_snapshot_scale(s)
            return True

        m=gtk.Menu()
        for size, label in (
            ( 8, _("Smallish")),
            (16, _("Small")),
            (32, _("Normal")),
            (48, _("Large")),
            (64, _("Larger")),
            (128, _("Huge")),
            ):
            i=gtk.MenuItem(label)
            i.connect("activate", set_scale, size)
            m.append(i)
        m.show_all()
        m.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def get_toolbar(self):
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        def center_on_current(*p):
            # Make sure that the current mark is visible
            if self.current_mark is not None:
                it=self.textview.get_buffer().get_iter_at_child_anchor(self.current_mark.anchor)
                if it:
                    self.textview.scroll_to_iter(it, 0.2)
            return True

        tb_list = (
            (_("Open"),    _("Open"), gtk.STOCK_OPEN, self.load_transcription_cb),
            (_("Save"),    _("Save"), gtk.STOCK_SAVE, self.save_transcription_cb),
            (_("Save As"), _("Save As"), gtk.STOCK_SAVE_AS, self.save_as_cb),
            (_("Import"), _("Import from annotations"), gtk.STOCK_EXECUTE, self.import_annotations_cb),
            (_("Convert"), _("Convert to annotations"), gtk.STOCK_CONVERT, self.convert_transcription_cb),
            (_("Preferences"), _("Preferences"), gtk.STOCK_PREFERENCES, self.edit_preferences),
            (_("Center"), _("Center on the current mark"), gtk.STOCK_JUSTIFY_CENTER, center_on_current),
            (_("Find"), _("Search a string"), gtk.STOCK_FIND, self.show_searchbox),
            (_("Scale"), _("Set the size of snaphots"), gtk.STOCK_FULLSCREEN, self.scale_snaphots_menu),
            )

        for text, tooltip, icon, callback in tb_list:
            b=gtk.ToolButton(label=text)
            b.set_stock_id(icon)
            b.set_tooltip(self.tooltips, tooltip)
            b.connect("clicked", callback)
            tb.insert(b, -1)

        def handle_toggle(t, option_name):
            self.options[option_name]=t.get_active()
            return True

        b=gtk.ToggleToolButton(stock_id=gtk.STOCK_JUMP_TO)
        b.set_active(self.options['autoscroll'])
        b.set_tooltip(self.tooltips, _("Automatically scroll to the mark position when playing"))
        b.connect('toggled', handle_toggle, 'autoscroll')
        b.set_label(_("Autoscroll"))
        tb.insert(b, -1)

        b=gtk.ToggleToolButton()
        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'clock.png') ))
        b.set_icon_widget(i)
        b.set_label(_("Autoinsert"))
        b.set_active(self.options['autoinsert'])
        b.set_tooltip(self.tooltips, _("Automatically insert marks"))
        b.connect('toggled', handle_toggle, 'autoinsert')
        tb.insert(b, -1)


        tb.show_all()
        return tb

    def key_pressed_cb (self, win, event):
        c=self.controller
        p=c.player

        # Process player shortcuts
        if c.gui and c.gui.process_player_shortcuts(win, event):
            return True

        if event.state & gtk.gdk.CONTROL_MASK:
            if event.keyval == gtk.keysyms.s:
                # Save file
                self.save_transcription_cb()
                return True
            elif event.keyval == gtk.keysyms.Return:
                # Insert current timestamp mark
                if p.status == p.PlayingStatus or p.status == p.PauseStatus:
                    self.insert_timestamp_mark()
                return True
            elif event.keyval == gtk.keysyms.space:
                # Pause and insert current timestamp mark
                if p.status == p.PlayingStatus or p.status == p.PauseStatus:
                    c.update_status("pause")
                    self.insert_timestamp_mark()
                return True
            elif event.keyval == gtk.keysyms.Page_Down:
                self.goto_next_mark()
                return True
            elif event.keyval == gtk.keysyms.Page_Up:
                self.goto_previous_mark()
                return True
        elif self.options['autoinsert'] and self.options['automatic-mark-insertion-delay']:
            if (gtk.gdk.keyval_to_unicode(event.keyval)
                and event.keyval != gtk.keysyms.space
                and (event.time - self.last_keypress_time >= self.options['automatic-mark-insertion-delay'])):
                # Insert a mark if the user pressed a character key, except space
                # Is there any text after the cursor ? If so, do not insert the mark
                b=self.textview.get_buffer()
                it=b.get_iter_at_mark(b.get_insert())
                if it.ends_line():
                    # Check that we are in a valid position
                    t=p.current_position_value - self.options['delay']
                    m, i=self.find_preceding_mark(it)
                    if m is not None and m.value >= t:
                        pass
                    else:
                        m, i=self.find_following_mark(it)
                        if m is not None and m.value <= t:
                            pass
                        else:
                            self.insert_timestamp_mark()
            self.last_keypress_time = event.time
            return False

        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Should provide a package name"
        sys.exit(1)

    class DummyController:
        def log(self, *p):
            print p

        def notify(self, *p, **kw):
            print "Notify %s %s" % (p, kw)


    controller=DummyController()
    controller.gui=None

    import advene.player.dummy
    player=advene.player.dummy.Player()
    controller.player=player
    controller.player.status=controller.player.PlayingStatus

    #controller.package = Package (uri=sys.argv[1])
    config.data.path['resources']='/usr/local/src/advene-project/share'
    controller.package = Package (uri="new_pkg",
                            source=config.data.advenefile(config.data.templatefilename))

    transcription = TranscriptionEdit(controller=controller)

    window = transcription.popup()

    window.connect ("destroy", lambda e: gtk.main_quit())

    gtk.main ()

