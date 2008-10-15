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
"""Autocomplete feature for gtk.TextView

This code is inspired and adapted from the Scribes project
(http://scribes.sf.net/) - GPLv2
"""

import gtk
import re

from advene.model.cam.annotation import Annotation
from advene.model.cam.tag import AnnotationType, RelationType
from advene.model.cam.query import Query
from advene.model.cam.view import View

class Completer:
    def __init__(self, textview=None, controller=None, element=None, indexer=None):
        self.textview=textview
        self.controller=controller
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
        if length > 1:
            self.hide_completion_window()
        else:
            self.check_completion()
        return False

    def hide_completion_window(self, *p):
        self.widget.hide_all()
        self.is_visible=False

    def show_completion_window(self, *p):
        width, height = self.widget.size_request()
        if width <= 200:
            width=200
        else:
            width += 28
        if height <= 200:
            height=200
        else:
            height += 28
        self.widget.resize(width, height)
        self.widget.set_property("width-request", width)
        self.widget.set_property("height-request", height)
        self.position_window(width, height)
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
        position = self.textview.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT, rectangle.x, rectangle.y)
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
        window = self.textview.get_window(gtk.TEXT_WINDOW_TEXT)
        rectangle = self.textview.get_visible_rect()
        window_x, window_y = window.get_origin()
        window_width, window_height = rectangle.width, rectangle.height

        # Determine where to position the completion window.
        position_x = window_x + cursor_x
        position_y = window_y + cursor_y + cursor_height

        # If the completion window extends past the text editor's buffer,
        # reposition the completion window inside the text editor's buffer area.
        if position_x + width > window_x + window_width:
            position_x = (window_x + window_width) - width
        if position_y + height > window_y + window_height:
            position_y = (window_y + cursor_y) - height
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
        return word_start.get_text(cursor_position)

    def insert_word_completion(self, path):
        """Insert item selected in the completion window into the text editor's
        buffer.

        @param path: The selected row in the completion window.
        @type path: A gtk.TreeRow object.
        """
        # Get the selected completion string.
        completion_string = self.model[path[0]][0].decode("utf8")

        word=self.get_word_before_cursor().encode('utf8')
        complete=completion_string.replace(word, '')
        b=self.textview.get_buffer()
        b.begin_user_action()
        b.insert_at_cursor(complete)
        b.end_user_action()
        return

    def check_completion(self):
        word = self.get_word_before_cursor()
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

        if event.keyval in (gtk.keysyms.Tab, gtk.keysyms.Right, gtk.keysyms.Left,
                            gtk.keysyms.Home, gtk.keysyms.End, gtk.keysyms.Insert,
                            gtk.keysyms.Delete,
                            gtk.keysyms.Page_Up, gtk.keysyms.Page_Down,
                            gtk.keysyms.Escape):
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
        if event.keyval == gtk.keysyms.Return:
            # Insert the selected item into the editor's buffer when the enter key
            # event is detected.
            self.treeview.row_activated(path, self.treeview.get_column(0))
        elif event.keyval == gtk.keysyms.Up:
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
        elif event.keyval == gtk.keysyms.Down:
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
        w=gtk.Window(gtk.WINDOW_POPUP)

        w.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_MENU)
        w.set_size_request(200, 200)

        self.treeview=gtk.TreeView()

        self.model = gtk.ListStore(str)
        renderer = gtk.CellRendererText()
        col=gtk.TreeViewColumn("", renderer, text=0)
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

        style = self.textview.get_style()
        color = style.base[gtk.STATE_SELECTED]
        self.treeview.modify_base(gtk.STATE_ACTIVE, color)

        scroll=gtk.ScrolledWindow()
        scroll.add(self.treeview)
        scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scroll.set_border_width(2)
        w.add(scroll)

        return w

class Indexer:
    """Indexer for Advene elements contents.
    """
    def __init__(self, controller=None, package=None):
        self.controller=controller
        self.package=package

        # Dictionary of sets. It has a 'views' key for view contents,
        # and annotation-type ids for the annotation contents
        self.index={
            'views': set(),
            }
        self.regexp=re.compile(r'[^\w\d_]+', re.UNICODE)
        self.size_limit=5

    def get_words(self, s):
        """Return the list of indexable words from the given string.
        """
        return [ w for w in self.regexp.split(s) if len(w) >= self.size_limit ]

    def initialize(self):
        """Initialize the indexer on package load.
        """
        s=self.index['views']
        for v in self.package.all.views:
            s.update(self.get_words(v.content_data))
        s.update([ at.id for at in self.package.all.annotation_types ])
        s.update([ rt.id for rt in self.package.all.relation_types ])
        s.update([ q.id for q in self.package.all.queries ])
        s.update([ v.id for v in self.package.all.views ])

        for at in self.package.all.annotation_types:
            s=self.index.get(at.id, set())
            for a in at.annotations:
                s.update(self.get_words(a.content_data))
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
            return True
        else:
            return True
        s.update(self.get_words(element.content.data))
        if atid:
            self.index[atid]=s
        return True

    def get_completions(self, prefix, context=None):
        """Return the list of possible completions.

        element is used as contextual information to refine the
        search. If it is an Annotation, completions will be searched
        in the annotation of the same type. If it is a view,
        completions will be searched for in other views.

        If element is a gtk.TextBuffer, completions will be searched
        in its content.
        """
        if isinstance(context, View):
            s=self.index['views']
            # FIXME: maybe add ids (annotation-types, relations-types, views)
        elif isinstance(context, Annotation):
            s=self.index.get(context.type.id, [])
        elif isinstance(context, gtk.TextBuffer):
            # The replace clause transforms the timestamp placeholders into spaces.
            s=set(self.get_words(unicode(context.get_slice(*context.get_bounds()).replace('\xef\xbf\xbc', ' '))))
            s.update(self.index['views'])
        else:
            s=self.index['views']

        res=[ w for w in s if w.startswith(prefix) and w != prefix ]
        return res

if __name__ == "__main__":
    import sys
    window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    window.set_default_size (600, 400)

    def key_pressed_cb (win, event):
        if event.state & gtk.gdk.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == gtk.keysyms.q:
                gtk.main_quit ()
                return True

    window.connect('key_press_event', key_pressed_cb)
    window.connect('destroy', lambda e: gtk.main_quit())
    window.set_title ('test')

    import gtksourceview
    t=gtksourceview.SourceView(gtksourceview.SourceBuffer())
    #t=gtk.TextView()
    if sys.argv[1:]:
        print "loading ", sys.argv[1]
        t.get_buffer().set_text(open(sys.argv[1]).read())

    i=Indexer()
    compl=Completer(textview=t,
                    controller=None,
                    element=t.get_buffer(),
                    indexer=i)

    window.add (t)
    window.show_all()
    gtk.main ()
