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
"""Transcription view.
"""
import logging
logger = logging.getLogger(__name__)

import sys
import re
import os
import operator

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango

try:
    from gi.repository import GtkSource
except ImportError:
    GtkSource=None

import urllib.request, urllib.parse, urllib.error

import advene.core.config as config

# Advene part
from advene.model.package import Package
from advene.model.schema import AnnotationType

import advene.util.importer

import advene.util.helper as helper

from gettext import gettext as _

from advene.gui.views import AdhocView
from advene.gui.util import dialog, get_pixmap_button, get_small_stock_button, name2color
from advene.gui.util import decode_drop_parameters
from advene.gui.edit.properties import EditWidget
from advene.gui.util.completer import Completer
from advene.gui.widget import TimestampRepresentation

name="Note-taking view plugin"

def register(controller):
    controller.register_viewclass(TranscriptionEdit)

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
    tooltip = _("Take notes on the fly as a timestamped transcription")
    def __init__ (self, controller=None, parameters=None, filename=None):
        super(TranscriptionEdit, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Save view"), self.save_view),
            (_("Save default options"), self.save_default_options),
            )

        self.controller=controller
        self.package=controller.package

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
            'snapshot-size': 32,
            'font-size': 0,
            'annotation-type-id': None,
            }

        self.colors = {
            'default': name2color('lightblue'),
            'ignore':  name2color('tomato'),
            'current': name2color('green'),
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
        self.update_font_size()
        if filename is not None:
            self.load_transcription(filename=filename)
        for n, v in arg:
            if n == 'text':
                self.load_transcription(buffer=v)

    def get_save_arguments(self):
        arguments = [ ('text', "".join(self.generate_transcription())) ]
        return self.options, arguments

    def edit_preferences(self, *p):
        cache=dict(self.options)

        ew=EditWidget(cache.__setitem__, cache.get)
        ew.set_name(_("Preferences"))
        ew.add_checkbox(_("Timestamp"), "timestamp", _("Click inserts timestamp marks"))
        ew.add_checkbox(_("Insert on single-click"), 'insert-on-single-click', _("A single click will insert the mark (else a double click is needed)"))
        ew.add_checkbox(_("Play on scroll"), "play-on-scroll", _("Play the new position upon timestamp modification"))
        ew.add_checkbox(_("Generate empty annotations"), "empty-annotations", _("If checked, generate annotations for empty text"))
        ew.add_spin(_("Reaction time"), "delay", _("Reaction time (substracted from current player time, except when paused.)"), -5000, 5000)
        ew.add_checkbox(_("Auto-insert"), "autoinsert", _("Automatic timestamp mark insertion"))
        ew.add_spin(_("Automatic insertion delay"), 'automatic-mark-insertion-delay', _("If autoinsert is active, timestamp marks will be automatically inserted when text is entered after no interaction since this delay (in ms).\n1000 is typically a good value."), 0, 100000)
        ew.add_spin(_("Font size"), "font-size", _("Font size for text (0 for standard size)"), 0, 48)

        res=ew.popup()
        if res:
            if cache['font-size'] != self.options['font-size']:
                # Font-size was changed. Update the textview.
                self.update_font_size(cache['font-size'])
            self.options.update(cache)
        return True

    def update_font_size(self, size=None):
        if size is None:
            size=self.options['font-size']
        if size == 0:
            # Get the default value from a temporary textview
            t=Gtk.TextView()
            size=int(t.get_pango_context().get_font_description().get_size() / Pango.SCALE)
            del t
        f=self.textview.get_pango_context().get_font_description()
        f.set_size(size * Pango.SCALE)
        self.textview.modify_font(f)

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
            res=begin.forward_search(searched, Gtk.TextSearchFlags.TEXT_ONLY)
            if not res:
                finished=True
            else:
                matchStart, matchEnd = res
                b.apply_tag_by_name("searched_string", matchStart, matchEnd)
                begin=matchEnd

    def textview_drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.get_data().decode('utf-8'))
            position=int(data['timestamp'])
            #(x, y) = self.textview.get_window()_to_buffer_coords(Gtk.TextWindowType.TEXT,
            #                                               int(x),
            #                                               int(y))
            it=self.textview.get_iter_at_location(x, y)
            if it is None:
                return False
            # Check that preceding mark.value is lower
            m, i=self.find_preceding_mark(it.iter)
            if m is not None and m.value > position:
                self.message(_("Invalid timestamp mark"))
                return False
            m, i=self.find_following_mark(it.iter)
            if m is not None and m.value < position:
                self.message(_("Invalid timestamp mark"))
                return False
            # Create the timestamp
            self.create_timestamp_mark(position, it.iter)

            # If the drag originated from our own widgets, remove it.
            source=Gtk.drag_get_source_widget(context)
            if source in self.marks:
                self.remove_timestamp_mark(source)
            return True
        return False

    def can_undo(self):
        try:
            return hasattr(self.textview.get_buffer(), 'can_undo')
        except AttributeError:
            return False

    def undo(self, *p):
        b=self.textview.get_buffer()
        if b.can_undo():
            b.undo()
        return True

    def build_widget(self):
        vbox = Gtk.VBox()

        if GtkSource is not None:
            self.textview=GtkSource.View()
            self.textview.set_buffer(GtkSource.Buffer())
        else:
            self.textview = Gtk.TextView()

        # We could make it editable and modify the annotation
        self.textview.set_editable(True)
        self.textview.set_wrap_mode (Gtk.WrapMode.WORD)

        hb=Gtk.HBox()
        vbox.pack_start(hb, False, True, 0)
        if self.controller.gui:
            self.player_toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(self.player_toolbar)
        hb.add(self.get_toolbar())

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.add (sw)


        # 0-mark at the beginning
        zero=self.create_timestamp_mark(0, self.textview.get_buffer().get_start_iter())
        self.current_mark=zero

        # Memorize the last keypress time
        self.last_keypress_time = 0

        self.textview.connect('button-press-event', self.button_press_event_cb)
        self.textview.connect('key-press-event', self.key_pressed_cb)
        self.textview.get_buffer().create_tag("past", background="#dddddd")
        self.textview.get_buffer().create_tag("ignored", strikethrough=True)

        self.textview.drag_dest_set(Gtk.DestDefaults.MOTION |
                                    Gtk.DestDefaults.HIGHLIGHT |
                                    Gtk.DestDefaults.ALL,
                                    config.data.get_target_types('timestamp'),
                                    Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        self.textview.connect('drag-data-received', self.textview_drag_received)

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

        self.searchbox=Gtk.HBox()

        def hide_searchbox(*p):
            # Clear the searched_string tags
            b=self.textview.get_buffer()
            b.remove_tag_by_name("searched_string", *b.get_bounds())
            self.searchbox.hide()
            return True

        close_button=get_pixmap_button('small_close.png', hide_searchbox)
        close_button.set_relief(Gtk.ReliefStyle.NONE)
        self.searchbox.pack_start(close_button, False, False, 0)

        def search_entry_cb(e):
            self.highlight_search_forward(e.get_text())
            return True

        def search_entry_key_press_cb(e, event):
            if event.keyval == Gdk.KEY_Escape:
                hide_searchbox()
                return True
            return False

        self.searchbox.entry=Gtk.Entry()
        self.searchbox.entry.connect('activate', search_entry_cb)
        self.searchbox.pack_start(self.searchbox.entry, False, False, 0)
        self.searchbox.entry.connect('key-press-event', search_entry_key_press_cb)

        b=get_small_stock_button(Gtk.STOCK_FIND)
        b.connect('clicked', lambda b: self.highlight_search_forward(self.searchbox.entry.get_text()))
        self.searchbox.pack_start(b, False, True, 0)

        fill=Gtk.HBox()
        self.searchbox.pack_start(fill, True, True, 0)
        self.searchbox.show_all()
        self.searchbox.hide()

        self.searchbox.set_no_show_all(True)
        vbox.pack_start(self.searchbox, False, True, 0)

        self.statusbar=Gtk.Statusbar()
        vbox.pack_start(self.statusbar, False, True, 0)
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
        p = self.controller.player
        if p.status == p.PauseStatus:
            t=p.current_position_value
        else:
            t=p.current_position_value - self.options['delay']
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
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            return False

        if self.options['insert-on-single-click']:
            t=Gdk.EventType.BUTTON_PRESS
        else:
            t=Gdk.EventType._2BUTTON_PRESS
        if not (event.button == 1 and event.type == t):
            return False
        textwin=textview.get_window(Gtk.TextWindowType.TEXT)

        if event.get_window() != textwin:
            logger.error("Event.get_window(): %s - Textwin: %s", str(event.get_window()), str(textwin))
            return False

        (x, y) = textview.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
                                                  int(event.x),
                                                  int(event.y))
        it=textview.get_iter_at_location(x, y)
        if it is None:
            logger.error("Error in get_iter_at_location")
            return False

        if self.controller.player.is_playing():
            self.insert_timestamp_mark(it=it)
            return True
        return False

    def buffer_is_empty(self):
        b=self.textview.get_buffer()
        return len(b.get_text(*b.get_bounds() + (False,))) == 0

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
            self.controller.update_status(status="seek", position=position)
            return True

        def popup_edit(i, button):
            v = self.controller.gui.input_time_dialog()
            if v is not None:
                button.value = v
            return True

        def popup_ignore(win, button):
            self.toggle_ignore(button)
            return True

        def popup_remove(win):
            self.remove_timestamp_mark(child)
            return True

        def popup_modify(win, t):
            timestamp=child.value + t
            child.set_tooltip_text("%s" % helper.format_time(timestamp))
            # FIXME: find a way to do this in the new Gtk.Tooltip API?
            #if self.tooltips.active_tips_data is None:
            #    button.emit('show-help', Gtk.WIDGET_HELP_TOOLTIP)
            child.value=timestamp
            if self.options['play-on-scroll']:
                popup_goto(child, timestamp)
            return True

        if event.button == 1 and event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # Set current video time
            popup_modify(None, self.controller.player.current_position_value - timestamp)
            return True

        if event.button != 3:
            return False

        # Create a popup menu for timestamp
        menu = Gtk.Menu()

        item = Gtk.MenuItem(_("Position %s") % helper.format_time(timestamp))
        menu.append(item)

        item = Gtk.SeparatorMenuItem()
        menu.append(item)

        item = Gtk.MenuItem(_("Go to..."))
        item.connect('activate', popup_goto, timestamp)
        menu.append(item)

        item = Gtk.MenuItem(_("Edit"))
        item.connect('activate', popup_edit, button)
        menu.append(item)

        item = Gtk.MenuItem(_("Ignore the following text (toggle)"))
        item.connect('activate', popup_ignore, button)
        menu.append(item)

        item = Gtk.MenuItem(_("Remove mark"))
        item.connect('activate', popup_remove)
        menu.append(item)

        item = Gtk.MenuItem(_("Reaction-time offset"))
        item.connect('activate', popup_modify, -self.options['delay'])
        menu.append(item)

        item = Gtk.MenuItem(_("-1 sec"))
        item.connect('activate', popup_modify, -1000)
        menu.append(item)
        item = Gtk.MenuItem(_("-0.5 sec"))
        item.connect('activate', popup_modify, -500)
        menu.append(item)
        item = Gtk.MenuItem(_("-0.1 sec"))
        item.connect('activate', popup_modify, -100)
        menu.append(item)

        item = Gtk.MenuItem(_("+1 sec"))
        item.connect('activate', popup_modify, 1000)
        menu.append(item)
        item = Gtk.MenuItem(_("+0.5 sec"))
        item.connect('activate', popup_modify, 500)
        menu.append(item)
        item = Gtk.MenuItem(_("+0.1 sec"))
        item.connect('activate', popup_modify, 100)
        menu.append(item)

        menu.show_all()

        menu.popup_at_pointer(None)
        return True

    def create_timestamp_mark(self, timestamp, it):
        def popup_goto (b):
            self.controller.update_status(status="seek", position=b.value)
            return True

        b=self.textview.get_buffer()
        b.begin_user_action()
        anchor=b.create_child_anchor(it)
        # Create the mark representation
        child=TimestampRepresentation(timestamp, None, self.controller, width=self.options['snapshot-size'], visible_label=False)
        child.anchor=anchor
        child.connect('clicked', popup_goto)
        child.popup_menu=None
        child.connect('button-press-event', self.mark_button_press_cb, anchor, child)
        b.end_user_action()

        def handle_scroll_event(button, event):
            if not (event.get_state() & Gdk.ModifierType.CONTROL_MASK):
                return False
            if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                i='second-scroll-increment'
            else:
                i='scroll-increment'

            if event.direction == Gdk.ScrollDirection.DOWN or event.direction == Gdk.ScrollDirection.RIGHT:
                button.value -= config.data.preferences[i]
            elif event.direction == Gdk.ScrollDirection.UP or event.direction == Gdk.ScrollDirection.LEFT:
                button.value += config.data.preferences[i]

                button.set_tooltip_text("%s" % helper.format_time(button.value))
            # FIXME: find a way to do this in the new Gtk.Tooltip API?
            #if self.tooltips.active_tips_data is None:
            #    button.emit('show-help', Gtk.WIDGET_HELP_TOOLTIP)
            self.timestamp_play = button.value
            button.grab_focus()
            return True

        def mark_key_release_cb(button, event, anchor=None, child=None):
            """Handler for key release on timestamp mark.
            """
            # Control key released. Goto the position if we were scrolling a mark
            if self.timestamp_play is not None and (event.get_state() & Gdk.ModifierType.CONTROL_MASK):
                # self.timestamp_play contains the new value, but child.timestamp
                # as well. So we can use popup_goto
                self.timestamp_play = None
                popup_goto(child)
                return True
            return False

        child.connect('scroll-event', handle_scroll_event)
        child.connect('key-release-event', mark_key_release_cb, anchor, child)
        child.set_tooltip_text("%s" % helper.format_time(timestamp))
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
            b.insert_at_cursor(str(a.content.data))
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
                c.update_status(status="seek", position=self.marks[0].value)
        else:
            i=self.marks.index(self.current_mark) - 1
            m=self.marks[i]
            c.update_status(status="seek", position=m.value)
        return True

    def goto_next_mark(self):
        if self.current_mark is None:
            if self.marks:
                self.controller.update_status(status="seek", position=self.marks[-1].value)
        else:
            i=(self.marks.index(self.current_mark) + 1) % len(self.marks)
            m=self.marks[i]
            self.controller.update_status(status="seek", position=m.value)
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
                        self.textview.scroll_to_iter(it, 0.3, False, 0, 0)
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
                    self.log(_('Invalid timestamp mark in conversion: %s') % helper.format_time_reference(timestamp))
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
                yield '[I%s]' % helper.format_time_reference(d['begin'])
                yield d['content']
                yield '[%s]' % helper.format_time_reference(d['end'])

            elif last != d['begin']:
                yield '[%s]' % helper.format_time_reference(d['begin'])
                yield d['content']
                yield '[%s]' % helper.format_time_reference(d['end'])
            else:
                yield d['content']
                yield '[%s]' % helper.format_time_reference(d['end'])
            last=d['end']

    def as_html(self):
        """Return a HTML representation of the view.
        """
        res=[]
        b=self.textview.get_buffer()
        begin=b.get_start_iter()
        end=begin.copy()

        ignore_next=False
        while end.forward_char():
            a=end.get_child_anchor()
            if a and a.get_widgets():
                # Found a TextAnchor
                child=a.get_widgets()[0]

                text=b.get_text(begin, end, include_hidden_chars=False).replace('\n', '<br />')
                if ignore_next:
                    res.extend( ('<strike>', text, '</strike>') )
                else:
                    res.append( text )
                res.append(child.as_html(with_timestamp=False))
                res.append('\n')
                ignore_next=child.ignore
                begin=end.copy()

        # End of buffer.
        text=b.get_text(begin, end, include_hidden_chars=False).replace('\n', '<br />')
        if ignore_next:
            res.extend( ('<strike>', text, '</strike>') )
        else:
            res.append( text )
        return ''.join(res)

    def save_as_cb(self, button=None):
        self.sourcefile=None
        self.save_transcription_cb()
        return True

    def save_transcription_cb(self, button=None):
        if self.sourcefile:
            fname=self.sourcefile
        else:
            # Use current movie filename as basename
            default_name='transcribe.txt'
            uri = self.controller.player.get_uri()
            if uri:
                default_name=os.path.splitext(os.path.basename(uri))[0] + ".txt"
            fname=dialog.get_filename(title= ("Save transcription to..."),
                                               action=Gtk.FileChooserAction.SAVE,
                                               button=Gtk.STOCK_SAVE,
                                               default_dir=config.data.path['data'],
                                               default_file=default_name
                                               )
        if fname is not None:
            self.save_transcription(filename=fname)
        return True

    def save_transcription(self, filename=None):
        if os.path.splitext(filename)[1] == '':
            # No extension was given. Add '.txt'
            filename=filename+'.txt'
        try:
            with open(filename, "w", encoding='utf-8') as f:
                f.writelines(self.generate_transcription())
        except IOError as e:
            dialog.message_dialog(
                _("Cannot save the file: %s") % str(e),
                icon=Gtk.MessageType.ERROR)
            return True
        self.message(_("Transcription saved to %s") % filename)
        self.sourcefile=filename
        return True

    def load_transcription_cb(self, button=None):
        if not self.buffer_is_empty():
            if not dialog.message_dialog(_("This will overwrite the current textual content. Are you sure?"),
                                                  icon=Gtk.MessageType.QUESTION):
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
                    fname=urllib.request.pathname2url(filename)
                else:
                    fname=filename
                f=urllib.request.urlopen(fname)
            except IOError as e:
                self.message(_("Cannot open %(filename)s: %(error)s") % {'filename': filename,
                                                                         'error': str(e) })
                return
            data="".join(f.readlines())
            f.close()
        else:
            data=buffer

        if isinstance(data, bytes):
            data = data.decode('utf-8')

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
                t=helper.parse_time(timestamp)
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
        at=self.controller.gui.ask_for_annotation_type(text=_("Select the annotation type to import"),
                                                       create=False,
                                                       default=self.controller.package.get_element_by_id(self.options['annotation-type-id']))
        if at is None:
            return True

        self.options['annotation-type-id'] = at.id

        if not at.annotations:
            dialog.message_dialog(_("There are no annotations of type %s") % self.controller.get_title(at))
            return True

        if not self.buffer_is_empty():
            if not dialog.message_dialog(_("This will overwrite the current textual content. Are you sure?"),
                                                  icon=Gtk.MessageType.QUESTION):
                return True

        b=self.textview.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)

        al=at.annotations
        al.sort(key=lambda a: a.fragment.begin)

        last_time=-1

        for a in al:
            if a.fragment.begin > last_time:
                it=b.get_iter_at_mark(b.get_insert())
                self.create_timestamp_mark(a.fragment.begin, it)
            b.insert_at_cursor(a.content.data)
            it=b.get_iter_at_mark(b.get_insert())
            self.create_timestamp_mark(a.fragment.end, it)
            last_time = a.fragment.end
        return True

    def convert_transcription_cb(self, button=None):
        if not self.controller.gui:
            self.message(_("Cannot convert the data: no associated package"))
            return True

        d = Gtk.Dialog(title=_("Converting transcription"),
                       parent=self.controller.gui.gui.win,
                       flags=Gtk.DialogFlags.DESTROY_WITH_PARENT,
                       buttons=( Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                 Gtk.STOCK_OK, Gtk.ResponseType.OK,
                                 ))
        l=Gtk.Label(label=_("Choose the annotation-type where to create annotations.\n"))
        l.set_line_wrap(True)
        l.show()
        d.vbox.pack_start(l, False, True, 0)

        # Anticipated declaration of some widgets, which need to be
        # updated in the handle_new_type_selection callback.
        new_type_dialog=Gtk.VBox()
        delete_existing_toggle=Gtk.CheckButton(_("Delete existing annotations in this type"))
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

        type_selection=dialog.list_selector_widget(members=[ (a, self.controller.get_title(a), self.controller.get_element_color(a)) for a in ats],
                                                   callback=handle_new_type_selection,
                                                   preselect=self.controller.package.get_element_by_id(self.options['annotation-type-id']))

        hb=Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Select type") + " "), False, False, 0)
        hb.pack_start(type_selection, False, True, 0)
        d.vbox.pack_start(hb, False, True, 0)

        l=Gtk.Label(label=_("You want to create a new type. Please specify its schema and title."))
        l.set_line_wrap(True)
        l.show()
        new_type_dialog.pack_start(l, False, True, 0)

        hb=Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Title") + " "), False, False, 0)
        new_title=Gtk.Entry()
        hb.pack_start(new_title, True, True, 0)
        new_type_dialog.pack_start(hb, False, True, 0)

        hb=Gtk.HBox()
        hb.pack_start(Gtk.Label(_("Containing schema") + " "), False, False, 0)
        schemas=list(self.controller.package.schemas)
        schema_selection=dialog.list_selector_widget(members=[ (s, self.controller.get_title(s)) for s in schemas])
        hb.pack_start(schema_selection, False, True, 0)
        new_type_dialog.pack_start(hb, False, True, 0)

        new_type_dialog.show_all()
        new_type_dialog.set_no_show_all(True)
        new_type_dialog.hide()

        d.vbox.pack_start(new_type_dialog, True, True, 0)

        l=Gtk.Label()
        l.set_markup("<b>" + _("Export options") + "</b>")
        d.vbox.pack_start(l, False, True, 0)

        d.vbox.pack_start(delete_existing_toggle, False, True, 0)

        empty_contents_toggle=Gtk.CheckButton(_("Generate annotations for empty contents"))
        empty_contents_toggle.set_active(self.options['empty-annotations'])
        d.vbox.pack_start(empty_contents_toggle, False, True, 0)

        d.connect('key-press-event', dialog.dialog_keypressed_cb)

        d.show_all()
        dialog.center_on_mouse(d)

        finished=None
        while not finished:
            res=d.run()
            if res == Gtk.ResponseType.OK:
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
                                icon=Gtk.MessageType.WARNING)
                            at=None
                            continue
                    # Creating a new type
                    s=schema_selection.get_current_element()
                    at=s.createAnnotationType(ident=id_)
                    at.author=config.data.userid
                    at.date=self.controller.get_timestamp()
                    at.title=new_type_title
                    at.mimetype='text/plain'
                    at.setMetaData(config.data.namespace, 'color', next(s.rootPackage._color_palette))
                    at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                    s.annotationTypes.append(at)
                    self.controller.notify('AnnotationTypeCreate', annotationtype=at)

                if delete_existing_toggle.get_active():
                    # Remove all annotations of at type
                    batch_id=object()
                    for a in at.annotations:
                        self.controller.delete_element(a, batch=batch_id)

                self.options['empty-annotations']=empty_contents_toggle.get_active()
                finished=True
            else:
                at=None
                finished=True
        d.destroy()

        if at is not None:
            self.options['annotation-type-id'] = at.id
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
        self.options['snapshot-size']=size
        for m in self.marks:
            m.set_width(size)

    def scale_snaphots_menu(self, i):
        def set_scale(i, s):
            self.set_snapshot_scale(s)
            return True

        m=Gtk.Menu()
        for size, label in (
            ( 8, _("Smallish")),
            (16, _("Small")),
            (32, _("Normal")),
            (48, _("Large")),
            (64, _("Larger")),
            (128, _("Huge")),
            ):
            i=Gtk.MenuItem(label)
            i.connect('activate', set_scale, size)
            m.append(i)
        m.show_all()
        m.popup(None, None, None, 0, Gtk.get_current_event_time())
        return True

    def get_toolbar(self):
        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        def center_on_current(*p):
            # Make sure that the current mark is visible
            if self.current_mark is not None:
                it=self.textview.get_buffer().get_iter_at_child_anchor(self.current_mark.anchor)
                if it:
                    self.textview.scroll_to_iter(it, 0.2, False, 0, 0)
            return True

        tb_list = (
            (_("Open"),    _("Open"), Gtk.STOCK_OPEN, self.load_transcription_cb),
            (_("Save"),    _("Save"), Gtk.STOCK_SAVE, self.save_transcription_cb),
            (_("Save As"), _("Save As"), Gtk.STOCK_SAVE_AS, self.save_as_cb),
            (_("Import"), _("Import from annotations"), Gtk.STOCK_EXECUTE, self.import_annotations_cb),
            (_("Convert"), _("Convert to annotations"), Gtk.STOCK_CONVERT, self.convert_transcription_cb),
            (_("Preferences"), _("Preferences"), Gtk.STOCK_PREFERENCES, self.edit_preferences),
            (_("Center"), _("Center on the current mark"), Gtk.STOCK_JUSTIFY_CENTER, center_on_current),
            (_("Find"), _("Search a string"), Gtk.STOCK_FIND, self.show_searchbox),
            (_("Scale"), _("Set the size of snaphots"), Gtk.STOCK_FULLSCREEN, self.scale_snaphots_menu),
            )

        for text, tooltip, icon, callback in tb_list:
            b=Gtk.ToolButton(label=text)
            b.set_stock_id(icon)
            b.set_tooltip_text(tooltip)
            b.connect('clicked', callback)
            tb.insert(b, -1)

        if self.can_undo():
            b=Gtk.ToolButton(Gtk.STOCK_UNDO)
            b.connect('clicked', lambda i: self.undo())
            b.set_tooltip_text(_("Undo"))
            tb.insert(b, -1)
            b.show()

        def handle_toggle(t, option_name):
            self.options[option_name]=t.get_active()
            return True

        b=Gtk.ToggleToolButton(Gtk.STOCK_JUMP_TO)
        b.set_active(self.options['autoscroll'])
        b.set_tooltip_text(_("Automatically scroll to the mark position when playing"))
        b.connect('toggled', handle_toggle, 'autoscroll')
        b.set_label(_("Autoscroll"))
        tb.insert(b, -1)

        i=Gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'clock.png') ))
        b=Gtk.ToggleToolButton()
        b.set_icon_widget(i)
        b.set_label(_("Autoinsert"))
        b.set_active(self.options['autoinsert'])
        b.set_tooltip_text(_("Automatically insert marks"))
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

        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_Return:
                # Insert current timestamp mark
                if p.is_playing():
                    if event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                        # If Shift is held, pause/resume the video
                        c.update_status("pause")
                    self.insert_timestamp_mark()
                return True
            elif event.keyval == Gdk.KEY_Page_Down:
                self.goto_next_mark()
                return True
            elif event.keyval == Gdk.KEY_Page_Up:
                self.goto_previous_mark()
                return True
            elif event.keyval == Gdk.KEY_c and event.get_state() & Gdk.ModifierType.SHIFT_MASK:
                self.convert_transcription_cb()
                return True
        elif self.options['autoinsert'] and self.options['automatic-mark-insertion-delay']:
            if (Gdk.keyval_to_unicode(event.keyval)
                and event.keyval != Gdk.KEY_space
                and (event.time - self.last_keypress_time >= self.options['automatic-mark-insertion-delay'])):
                # Insert a mark if the user pressed a character key, except space
                # Is there any text after the cursor ? If so, do not insert the mark
                b=self.textview.get_buffer()
                it=b.get_iter_at_mark(b.get_insert())
                if it.ends_line():
                    # Check that we are in a valid position
                    if p.status == p.PauseStatus:
                        t=p.current_position_value
                    else:
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
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) < 2:
        logger.error("Should provide a package name")
        sys.exit(1)

    class DummyController:
        def log(self, *p):
            logger.error(p)

        def notify(self, *p, **kw):
            logger.info("Notify %s %s", p, kw)


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

    window.connect('destroy', lambda e: Gtk.main_quit())

    Gtk.main ()

