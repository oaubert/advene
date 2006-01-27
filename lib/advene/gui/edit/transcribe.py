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

#import pygtk
import gtk
import gobject

import urllib

import advene.core.config as config

# Advene part
from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType

import advene.util.importer

import advene.util.vlclib as vlclib

from gettext import gettext as _

import advene.gui.edit.elements
import advene.gui.edit.create
import advene.gui.popup
import advene.gui.util

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

class TranscriptionEdit:
    def __init__ (self, controller=None, filename=None):
        self.controller=controller
        self.package=controller.package
        self.tooltips=gtk.Tooltips()

        self.sourcefile=None
        self.empty_re = sre.compile('^\s*$')

        self.timestamp_mode_toggle=gtk.ToggleToolButton()
        self.timestamp_mode_toggle.set_label(_("Timestamps"))
        self.timestamp_mode_toggle.set_stock_id(gtk.STOCK_INDEX)
        self.timestamp_mode_toggle.set_active (True)
        self.timestamp_mode_toggle.set_tooltip(self.tooltips,
                                               _("If unchecked, allows to edit text"))

        # Discontinuous is True by default
        self.discontinuous_toggle=gtk.ToggleToolButton()
        self.discontinuous_toggle.set_label(_("Discontinuous"))
        self.discontinuous_toggle.set_active (True)
        self.discontinuous_toggle.set_stock_id(gtk.STOCK_REMOVE)
        self.discontinuous_toggle.set_tooltip(self.tooltips,
                                              _("Do not generate annotations for empty text"))

        self.delay=gtk.Adjustment(value=-config.data.reaction_time,
                                  lower=-5000,
                                  upper=5000,
                                  step_incr=10,
                                  page_incr=100)

        self.colors = {
            'default': gtk.gdk.color_parse ('lightblue'),
            'ignore':  gtk.gdk.color_parse ('tomato'),
            'current': gtk.gdk.color_parse ('green'),
            }

        self.marks = []

        self.current_mark = None

        self.widget=self.build_widget()
        if filename is not None:
            self.load_transcription(filename)

    def build_widget(self):
        vbox = gtk.VBox()

        self.textview = gtk.TextView()
        # We could make it editable and modify the annotation
        self.textview.set_editable(True)
        self.textview.set_wrap_mode (gtk.WRAP_CHAR)

        # 0-mark at the beginning
        zero=self.create_timestamp_mark(0, self.textview.get_buffer().get_start_iter())
        self.current_mark=zero

        self.textview.connect("button-press-event", self.button_press_event_cb)

        vbox.add(self.textview)
        vbox.show_all()
        return vbox

    def remove_timestamp_mark(self, button, anchor, child):
        b=self.textview.get_buffer()
        self.marks.remove(child)
        begin=b.get_iter_at_child_anchor(anchor)
        end=begin.copy()
        end.forward_char()
        b.delete_interactive(begin, end, True)
        button.destroy()
        return True

    def button_press_event_cb(self, textview, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            return False
        if event.button != 1:
            return False
        if not self.timestamp_mode_toggle.get_active():
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
        if (p.status == p.PlayingStatus or p.status == p.PlayingStatus):
            # Check that preceding mark.timestamp is lower
            t=p.current_position_value + self.delay.value
            m, i=self.find_preceding_mark(it)
            if m is not None and m.timestamp >= t:
                self.controller.log(_("Invalid timestamp mark"))
                return False
            m, i=self.find_following_mark(it)
            if m is not None and m.timestamp <= t:
                self.controller.log(_("Invalid timestamp mark"))
                return False
            # Make a snapshot
            self.controller.update_snapshot(t)
            # Create the timestamp
            self.create_timestamp_mark(t, it)
        return False

    def set_color(self, button, color):
        for style in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            button.modify_bg (style, color)

    def toggle_ignore(self, button):
        button.ignore = not button.ignore
        self.update_mark(button)
        return button

    def update_mark(self, button):
        if button.ignore:
            self.set_color(button, self.colors['ignore'])
        else:
            self.set_color(button, self.colors['default'])
        return

    def mark_button_press_cb(self, button, event, anchor=None, child=None):
        """Handler for right-button click on timestamp mark.
        """
        if event.button != 3:
            return False
        timestamp=button.timestamp
        # Create a popup menu for timestamp
        menu = gtk.Menu()

        def popup_goto (win, position):
            c=self.controller
            pos = c.create_position (value=position,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            return True

        def popup_modify(win, t):
            timestamp=child.timestamp + t
            self.tooltips.set_tip(child, "%s" % vlclib.format_time(timestamp))
            child.timestamp=timestamp
            return True

        def popup_ignore(win, button):
            self.toggle_ignore(button)
            return True

        def popup_remove(win):
            self.remove_timestamp_mark(button, anchor, child)
            return True

        item = gtk.MenuItem(_("Position %s") % vlclib.format_time(timestamp))
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
        item.connect("activate", popup_modify, self.delay.value)
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

        item = gtk.MenuItem()
        item.add(advene.gui.util.image_from_position(self.controller,
                                                     position=timestamp,
                                                     height=60))
        item.connect("activate", popup_goto, timestamp)
        menu.append(item)

        menu.show_all()

        menu.popup(None, None, None, 0, gtk.get_current_event_time())
        return True

    def create_timestamp_mark(self, timestamp, it):
        def popup_goto (b):
            c=self.controller
            pos = c.create_position (value=b.timestamp,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
            return True

        b=self.textview.get_buffer()
        anchor=b.create_child_anchor(it)
        # Create the mark representation
        child=gtk.Button("")
        child.connect("clicked", popup_goto)
        child.connect("button-press-event", self.mark_button_press_cb, anchor, child)
        self.tooltips.set_tip(child, "%s" % vlclib.format_time(timestamp))
        child.timestamp=timestamp
        child.ignore=False
        self.update_mark(child)
        child.show()
        self.textview.add_child_at_anchor(child, anchor)

        self.marks.append(child)
        self.marks.sort(lambda a,b: cmp(a.timestamp, b.timestamp))
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
        l.sort(lambda a,b: cmp(a[0], b[0]))
        last_end=-1
        for (begin, end, a) in l:
            if begin < last_end or end < last_end:
                self.controller.log(_("Invalid timestamp"))
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
                pos = c.create_position (value=self.marks[0].timestamp,
                                         key=c.player.MediaTime,
                                         origin=c.player.AbsolutePosition)
                c.update_status (status="set", position=pos)
        else:
            i=self.marks.index(self.current_mark) - 1
            m=self.marks[i]
            pos = c.create_position (value=m.timestamp,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
        return True

    def goto_next_mark(self):
        c=self.controller
        if self.current_mark is None:
            if self.marks:
                pos = c.create_position (value=self.marks[-1].timestamp,
                                         key=c.player.MediaTime,
                                         origin=c.player.AbsolutePosition)
                c.update_status (status="set", position=pos)
        else:
            i=(self.marks.index(self.current_mark) + 1) % len(self.marks)
            m=self.marks[i]
            pos = c.create_position (value=m.timestamp,
                                     key=c.player.MediaTime,
                                     origin=c.player.AbsolutePosition)
            c.update_status (status="set", position=pos)
        return True

    def update_position(self, pos):
        l=[ m for m in self.marks if m.timestamp <= pos ]
        if l:
            cm=l[-1]
            if cm != self.current_mark:
                # Restore the properties of the previous current mark
                if self.current_mark is not None:
                    self.update_mark(self.current_mark)
                self.set_color(cm, self.colors['current'])
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

        t=0
        b=self.textview.get_buffer()
        begin=b.get_start_iter()
        end=begin.copy()
        ignore_next=False
        while end.forward_char():
            a=end.get_child_anchor()
            if a and a.get_widgets():
                # Found a TextAnchor
                child=a.get_widgets()[0]
                timestamp=child.timestamp
                text=b.get_text(begin, end, include_hidden_chars=False)
                if strip_blank:
                    text=text.rstrip().lstrip()
                if (self.discontinuous_toggle.get_active() and
                    self.empty_re.match(text)):
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
        timestamp=self.controller.player.stream_duration
        text=b.get_text(begin, end, include_hidden_chars=False)
        if (self.discontinuous_toggle.get_active() and
            self.empty_re.match(text)):
            pass
        elif ignore_next:
            if show_ignored:
                yield { 'begin': t,
                        'end':   timestamp,
                        'content': text,
                        'ignored': True }
        else:
            yield { 'begin': t,
                    'end': timestamp,
                    'content': text,
                    'ignored': False }

    def save_as_cb(self, button=None):
        self.sourcefile=None
        self.save_transcription_cb()
        return True

    def save_transcription_cb(self, button=None):
        if self.sourcefile:
            fname=self.sourcefile
        else:
            fname=advene.gui.util.get_filename(title= ("Save transcription to..."),
                                               action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                               button=gtk.STOCK_SAVE)
        if fname is not None:
            self.save_transcription(filename=fname)
        return True

    def save_transcription(self, filename=None):
        try:
            f=open(filename, "w")
        except IOError, e:
            advene.gui.util.message_dialog(
                _("Cannot save the file: %s") % unicode(e),
                icon=gtk.MESSAGE_ERROR)
            return True
        last=None
        for d in self.parse_transcription(show_ignored=True,
                                          strip_blank=False):
            if d['ignored']:
                f.writelines( ( '[I%s]' % vlclib.format_time(d['begin']),
                                d['content'],
                                '[%s]' % vlclib.format_time(d['end']) ) )

            elif last != d['begin']:
                f.writelines( ( '[%s]' % vlclib.format_time(d['begin']),
                                d['content'],
                                '[%s]' % vlclib.format_time(d['end']) ) )
            else:
                f.writelines( ( d['content'],
                                '[%s]' % vlclib.format_time(d['end']) ) )
            last=d['end']
        f.close()
        self.controller.log(_("Transcription saved to %s") % filename)
        self.sourcefile=filename
        return True

    def load_transcription_cb(self, button=None):
        fname=advene.gui.util.get_filename(title=_("Select transcription file to load"))
        if fname is not None:
            self.load_transcription(filename=fname)
        return True

    def load_transcription(self, filename=None):
        if sre.match('[a-zA-Z]:', filename):
            # Windows drive: notation. Convert it to
            # a more URI-compatible syntax
            filename=urllib.pathname2url(filename)
        try:
            f=urllib.urlopen(filename)
        except IOError, e:
            self.controller.log(_("Cannot open %s: %s") % (filename, str(e)))
            return
        data=unicode("".join(f.readlines()))

        b=self.textview.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)

        mark_re=sre.compile('\[(I?)(\d+:\d+:\d+.?\d*)\]([^\[]*)')

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
                t=vlclib.convert_time(timestamp)
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

    def convert_transcription_cb(self, button=None):
        if not self.controller.gui:
            self.controller.log(_("Cannot convert the data : no associated package"))
            return True

        at=self.controller.gui.ask_for_annotation_type(text=_("Select the annotation type to generate"), create=True)

        if at is None:
            self.controller.log(_("Conversion cancelled"))
            return True

        ti=TranscriptionImporter(package=self.controller.package,
                                 controller=self.controller,
                                 defaulttype=at,
                                 transcription_edit=self)
        ti.process_file('transcription')

        self.controller.modified=True
        self.controller.notify("PackageLoad", package=ti.package)
        self.controller.log(_('Converted from file %s :') % self.sourcefile)
        self.controller.log(ti.statistics_formatted())
        # Feedback
        advene.gui.util.message_dialog(
            _("Conversion completed.\n%s annotations generated.") % ti.statistics['annotation'])
        return True

    def get_widget (self):
        """Return the TreeView widget."""
        return self.widget

    def get_toolbar(self, close_cb=None):
        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        tb_list = (
            (_("Open"),    _("Open"), gtk.STOCK_OPEN, self.load_transcription_cb),
            (_("Save"),    _("Save"), gtk.STOCK_SAVE, self.save_transcription_cb),
            (_("Save As"), _("Save As"), gtk.STOCK_SAVE_AS, self.save_as_cb),
            (_("Convert"), _("Convert"), gtk.STOCK_CONVERT, self.convert_transcription_cb),
            (_("Close"),   _("Close"), gtk.STOCK_CLOSE, close_cb)
            )

        for text, tooltip, icon, callback in tb_list:
            b=gtk.ToolButton(label=text)
            b.set_stock_id(icon)
            b.set_tooltip(self.tooltips, tooltip)
            b.connect("clicked", callback)
            tb.insert(b, -1)

        tb.insert(self.timestamp_mode_toggle, -1)
        tb.insert(self.discontinuous_toggle, -1)

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
                    b=self.textview.get_buffer()
                    it=b.get_iter_at_mark(b.get_insert())
                    self.create_timestamp_mark(p.current_position_value,
                                               it)
                return True
            elif event.keyval == gtk.keysyms.space:
                # Pause and insert current timestamp mark
                if p.status == p.PlayingStatus or p.status == p.PauseStatus:
                    c.update_status("pause")
                    b=self.textview.get_buffer()
                    it=b.get_iter_at_mark(b.get_insert())
                    self.create_timestamp_mark(p.current_position_value,
                                               it)
                return True
            elif event.keyval == gtk.keysyms.Page_Down:
                self.goto_next_mark()
                return True
            elif event.keyval == gtk.keysyms.Page_Up:
                self.goto_previous_mark()
                return True

        return False

    def get_packed_widget(self, close_cb=None):
        vbox = gtk.VBox()

        hb=gtk.HBox()
        vbox.pack_start(hb, expand=False)
        if self.controller.gui:
            toolbar=self.controller.gui.get_player_control_toolbar()
            hb.add(toolbar)
        hb.add(self.get_toolbar(close_cb))

        # Spinbutton for reaction time
        l=gtk.Label(_("Reaction time"))
        hb.pack_start(l, expand=False)
        sp=gtk.SpinButton(self.delay)
        hb.pack_start(sp, expand=False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add (sw)
        sw.add_with_viewport (self.get_widget())
        return vbox

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'transcribeview')

        window.set_title (_("Transcription alignment"))
        window.connect ("key-press-event", self.key_pressed_cb)

        vbox = self.get_packed_widget(close_cb=lambda w: window.destroy())
        window.add(vbox)

        if self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb,
                            window, self)


        window.show_all()
        return window

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

