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
"""Autocomplete feature for Gtk.TextView

This code is inspired and adapted from the Scribes project
(http://scribes.sf.net/) - GPLv2
"""
import logging
logger = logging.getLogger(__name__)

from gi.repository import Gtk
from gi.repository import Gdk
import re

import advene.core.config as config

from advene.model.annotation import Annotation
from advene.model.schema import AnnotationType, RelationType
from advene.model.query import Query
from advene.model.view import View

class Completer:
    def __init__(self, textview=None, controller=None, element=None, indexer=None):
        self.textview=textview
        self.controller=controller
        if indexer is None:
            indexer = Indexer()
        self.indexer=indexer
        # If defined, element is the element being edited, which
        # allows to do a more precise completion search
        self.element=element


        self.is_visible=False
        self.word_list=None

        self.widget=self.build_widget()
        self.connect()

    def connect(self):
        """Register the various callbacks for completion.
        """
        self.textview.connect('key-press-event', self.key_press_event_cb)
        self.textview.connect('focus-out-event', self.hide_completion_window)
        self.textview.get_buffer().connect('delete-range', self.hide_completion_window)
        self.textview.get_buffer().connect_after('insert-text', self.insert_text_cb)
        self.textview.connect('paste-clipboard', self.hide_completion_window)
        self.textview.connect_after('paste-clipboard', self.hide_completion_window)
        #self.textview.connect('button-press-event', self.__button_press_event_cb)
        return True

    def insert_text_cb(self, textbuffer, iterator, text, length):
        """Handles callback when the "insert-text" signal is emitted.
        """
        if config.data.preferences['abbreviation-mode'] and text == ' ':
            # Find previous word
            w, begin, end = self.get_word_before_cursor()
            w = w.strip()
            repl = self.indexer.abbreviations.get(w, None)
            if repl is not None:
                textbuffer.delete(begin, end)
                textbuffer.insert(begin, repl + " ")
            return False
        if not config.data.preferences['completion-mode']:
            return False
        if length > 1:
            self.hide_completion_window()
        else:
            self.check_completion()
        return False

    def hide_completion_window(self, *p):
        self.widget.hide()
        self.is_visible=False

    def show_completion_window(self, *p):
        req = self.treeview.size_request()
        width, height = req.width, req.height
        width += 24
        height += 24
        self.widget.resize(width, height)
        self.widget.set_property("width-request", width)
        self.widget.set_property("height-request", height)
        self.position_window(width, height)

        self.widget.set_size_request(width, height)

        self.widget.show_all()
        self.position_window(width, height)
        self.is_visible=True

    def get_cursor_rectangle(self):
        b=self.textview.get_buffer()
        cursor_iterator=b.get_iter_at_mark(b.get_insert())
        rectangle = self.textview.get_iter_location(cursor_iterator)
        return rectangle

    def get_cursor_textview_coordinates(self):
        rectangle=self.get_cursor_rectangle()
        # Get the cursor's window coordinates.
        position = self.textview.buffer_to_window_coords(Gtk.TextWindowType.TEXT, rectangle.x, rectangle.y)
        cursor_x = position[0]
        cursor_y = position[1]
        return cursor_x, cursor_y

    def get_cursor_size(self):
        """Get the cursor's size.
        """
        rectangle=self.get_cursor_rectangle()
        return rectangle.width, rectangle.height

    def position_window(self, width, height):
        """Position the completion window in the text editor's buffer.

        @param width: The completion window's width.
        @type width: An Integer object.

        @param height: The completion window's height.
        @type height: An Integer object.
        """
        # Get the cursor's coordinate and size.
        cursor_x, cursor_y = self.get_cursor_textview_coordinates()
        cursor_height = self.get_cursor_size()[1]
        # Get the text editor's textview coordinate and size.
        window = self.textview.get_window(Gtk.TextWindowType.TEXT)
        origin = window.get_origin()
        # Note: do not use origin.x/origin.y since it does not work on win32
        window_x, window_y = origin[1], origin[2]

        # Determine where to position the completion window.
        position_x = window_x + cursor_x
        position_y = window_y + cursor_y + cursor_height

        if position_x + width > Gdk.Screen.width():
            position_x = window_x + cursor_x - width
        if position_y + height > Gdk.Screen.height():
            position_y = window_y + cursor_y - height

        #if not_(self.__signals_are_blocked):
        x, y = self.widget.get_position()

        if position_y != y:
            position_x = x

        if position_x != x or position_y != y:
            # Set the window's new position.
            self.widget.move(position_x, position_y)

    def populate_model(self, completion_list):
        """Populate the view's data model.

        @param self: Reference to the CompletionTreeView instance.
        @type self: A CompletionTreeView object.
        """
        if completion_list != self.word_list:
            self.word_list = completion_list
            self.model.clear()
            for word in self.word_list:
                self.model.append([word])
                self.treeview.columns_autosize()
            self.treeview.get_selection().select_path(0)

    def get_word_before_cursor(self):
        b=self.textview.get_buffer()
        cursor_position=b.get_iter_at_mark(b.get_insert())
        word_start=cursor_position.copy()
        word_start.backward_word_start()
        return word_start.get_text(cursor_position), word_start, cursor_position

    def insert_word_completion(self, path):
        """Insert item selected in the completion window into the text editor's
        buffer.

        @param path: The selected row in the completion window.
        @type path: A Gtk.TreeRow object.
        """
        # Get the selected completion string.
        completion_string = self.model[path[0]][0]

        word, begin, end=self.get_word_before_cursor()
        complete=completion_string.replace(word.encode('utf8'), '')
        b=self.textview.get_buffer()
        b.begin_user_action()
        b.insert_at_cursor(complete)
        b.end_user_action()
        return

    def check_completion(self):
        word, begin, end = self.get_word_before_cursor()
        if word:
            if len(word) < 2:
                return False
            matches=sorted(self.indexer.get_completions(word, context=self.element),
                           key=len)
            if matches:
                self.populate_model(matches)
                self.show_completion_window()
            else:
                # Hide the window
                self.hide_completion_window()
        else:
            self.hide_completion_window()
        return False

    def key_press_event_cb(self, widget, event):
        """Handles "key-press-event" for the treeview and textview.

        This function allows the "Up" and "Down" arrow keys to work in
        the word completion window.
        """
        if not self.is_visible:
            return False

        if event.keyval in (Gdk.KEY_Tab, Gdk.KEY_Right, Gdk.KEY_Left,
                            Gdk.KEY_Home, Gdk.KEY_End, Gdk.KEY_Insert,
                            Gdk.KEY_Delete,
                            Gdk.KEY_Page_Up, Gdk.KEY_Page_Down,
                            Gdk.KEY_Escape):
            self.hide_completion_window()
            return True

        # Get the selected item on the completion window.
        selection = self.treeview.get_selection()
        # Get the model and iterator of the selected item.
        model, iterator = selection.get_selected()
        # If for whatever reason the selection is lost, select the first row
        # automatically when the up or down arrow key is pressed.
        if not iterator:
            selection.select_path((0,))
            model, iterator = selection.get_selected()
        path = model.get_path(iterator)
        if event.keyval == Gdk.KEY_Return:
            # Insert the selected item into the editor's buffer when the enter key
            # event is detected.
            self.treeview.row_activated(path, self.treeview.get_column(0))
        elif event.keyval == Gdk.KEY_Up:
            # If the up key is pressed check to see if the first row is selected.
            # If it is, select the last row. Otherwise, get the path to the row
            # above and select it.
            if not path[0]:
                number_of_rows = len(model)
                selection.select_path(number_of_rows - 1)
                self.treeview.scroll_to_cell(number_of_rows - 1)
            else:
                selection.select_path((path[0] - 1, ))
                self.treeview.scroll_to_cell((path[0] - 1, ))
        elif event.keyval == Gdk.KEY_Down:
            # Get the iterator of the next row.
            next_iterator = model.iter_next(iterator)
            # If the next row exists, select it, if not select the first row.
            if next_iterator:
                selection.select_iter(next_iterator)
                path = model.get_path(next_iterator)
                self.treeview.scroll_to_cell(path)
            else:
                selection.select_path(0)
                self.treeview.scroll_to_cell(0)
        else:
            return False
        return True

    def build_widget(self):
        w=Gtk.Window(Gtk.WindowType.POPUP)

        w.set_type_hint(Gdk.WindowTypeHint.MENU)
        #w.set_size_request(200, 200)

        self.treeview=Gtk.TreeView()

        self.model = Gtk.ListStore(str)
        renderer = Gtk.CellRendererText()
        col=Gtk.TreeViewColumn("", renderer, text=0)
        col.set_expand(False)

        self.treeview.append_column(col)
        self.treeview.set_headers_visible(False)
        self.treeview.set_rules_hint(True)
        self.treeview.set_hover_selection(True)
        self.treeview.set_model(self.model)

        def treeview_row_activated_cb(treeview, path, column):
            """Handles "row-activated" in the treeview.
            """
            self.insert_word_completion(path)
            self.hide_completion_window()
            return True
        self.treeview.connect('row-activated', treeview_row_activated_cb)

        scroll=Gtk.ScrolledWindow()
        scroll.add(self.treeview)
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_border_width(2)
        w.add(scroll)

        return w

class Indexer:
    """Indexer for Advene elements contents.
    """
    def __init__(self, controller=None, package=None, abbreviations=None):
        self.controller=controller
        self.package=package

        if abbreviations is None:
            abbreviations = {}
        self.abbreviations = abbreviations

        # Dictionary of sets. It has a 'views' key for view contents,
        # and annotation-type ids for the annotation contents
        self.index={
            'views': set(),
            }
        self.regexp=re.compile(r'[^\w\d_]+', re.UNICODE)
        self.alt_regexp = re.compile(r'\s*,\s*', re.UNICODE)
        self.size_limit = 4

    def get_words(self, s):
        """Return the list of indexable words from the given string.
        """
        if ',' in s:
            regexp = self.alt_regexp
        else:
            regexp = self.regexp
        return [ w for w in regexp.split(s) if len(w) >= self.size_limit ]

    def initialize(self):
        """Initialize the indexer on package load.
        """
        s=self.index['views']
        for v in self.package.views:
            s.update(self.get_words(v.content.data))
        s.update([ at.id for at in self.package.annotationTypes ])
        s.update([ rt.id for rt in self.package.relationTypes ])
        s.update([ q.id for q in self.package.queries ])
        s.update([ v.id for v in self.package.views ])

        for at in self.package.annotationTypes:
            s=self.index.get(at.id, set())

            words=at.getMetaData(config.data.namespace, "completions")
            if words is not None:
                s.update(self.get_words(words.strip()))

            for a in at.annotations:
                s.update(self.get_words(a.content.data))

            self.index[at.id]=s
        return True

    def element_update(self, element):
        """Update the collection on element modification.
        """
        if isinstance(element, View):
            s=self.index['views']
            atid=None
            s.add(element.id)
        elif isinstance(element, Annotation):
            atid=element.type.id
            s=self.index.get(atid, set())
        elif isinstance(element, (AnnotationType, RelationType, Query)):
            self.index['views'].add(element.id)
            words=element.getMetaData(config.data.namespace, "completions")
            if words is not None:
                self.index.get(element.id, set()).update(self.get_words(words.strip()))
            return True
        else:
            return True
        s.update(self.get_words(element.content.data))
        if atid:
            self.index[atid]=s
        return True

    def get_completions(self, prefix, context=None, predefined_only=False):
        """Return the list of possible completions.

        element is used as contextual information to refine the
        search. If it is an Annotation, completions will be searched
        in the annotation of the same type. If it is a view,
        completions will be searched for in other views.

        If element is a Gtk.TextBuffer, completions will be searched
        in its content.
        """
        if isinstance(context, View):
            s=self.index['views']
            # FIXME: maybe add ids (annotation-types, relations-types, views)
        elif isinstance(context, Annotation):
            s = []
            if predefined_only or config.data.preferences['completion-predefined-only']:
                terms = context.type.getMetaData(config.data.namespace, "completions")
                if terms:
                    s = self.get_words(terms)
            if not s:
                # No predefined completion anyway
                s = self.index.get(context.type.id, [])
        elif isinstance(context, Gtk.TextBuffer):
            # The replace clause transforms the timestamp placeholders into spaces.
            args = context.get_bounds() + (False, )
            s=set(self.get_words(str(context.get_slice(*args).replace('\xef\xbf\xbc', ' '))))
            s.update(self.index['views'])
        else:
            s=self.index['views']

        res=[ w for w in s if w.startswith(prefix) and w != prefix ]
        return res

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
    window.set_default_size (600, 400)

    def key_pressed_cb (win, event):
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == Gdk.KEY_q:
                Gtk.main_quit ()
                return True

    window.connect('key_press_event', key_pressed_cb)
    window.connect('destroy', lambda e: Gtk.main_quit())
    window.set_title ('test')

    from gi.repository import GtkSource
    t=GtkSource.View(GtkSource.Buffer())
    #t=Gtk.TextView()
    if sys.argv[1:]:
        logger.info("loading %s", sys.argv[1])
        t.get_buffer().set_text(open(sys.argv[1], encoding='utf-8').read())

    i=Indexer()
    compl=Completer(textview=t,
                    controller=None,
                    element=t.get_buffer(),
                    indexer=i)

    window.add (t)
    window.show_all()
    Gtk.main ()
