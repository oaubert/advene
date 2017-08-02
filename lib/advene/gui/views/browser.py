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

# Advene browser, a la NeXT's workspace manager
# FIXME: implement set_path to directly display a given path
import logging
logger = logging.getLogger(__name__)

# Advene part
import advene.core.config as config
from advene.gui.views import AdhocView
import advene.util.helper as helper
from advene.model.exception import AdveneException

from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import Gtk

name="TALES browser view plugin"

TREEPATH_FIRST=Gtk.TreePath.new_first()

def register(controller):
    controller.register_viewclass(Browser)

class BrowserColumn:
    def __init__(self, element=None, name="", callback=None, parent=None):
        self.model=element
        self.name=name
        self.callback=callback
        self.next_column=None
        self.previous=parent
        self.widget=self.build_widget()
        self.widget.connect('key-press-event', self.key_pressed_cb)

    def key_pressed_cb(self, col, event):
        if event.keyval == Gdk.KEY_Right:
            # Next column
            if self.next_column is not None:
                self.next_column.get_focus()
            return True
        elif event.keyval == Gdk.KEY_Left:
            # Previous column
            if self.previous is not None:
                self.previous.get_focus()
            return True
        return False

    def get_focus(self):
        self.listview.grab_focus()
        cursor=self.listview.get_cursor().path
        if cursor == TREEPATH_FIRST:
            # Initial selection. Directly put the cursor on the second element.
            cursor.next()
            self.listview.set_cursor(cursor)
        return True

    def get_widget(self):
        return self.widget

    def get_liststore(self):
        ls=Gtk.ListStore(str)
        if self.model is None:
            return ls
        for att in helper.get_valid_members(self.model):
            ls.append([att])
        return ls

    def update(self, element=None, name=""):
        self.model=element
        self.liststore.clear()
        for att in helper.get_valid_members(element):
            self.liststore.append([att])
        self.name=name
        self.label.set_label(name)
        # Destroy all following columns
        self.next_column=None
        return True

    def row_activated(self, widget, treepath, treecolumn):
        att=widget.get_model()[treepath[0]][0]
        if att.startswith('----'):
            return True
        if self.callback:
            self.callback(self, att)
        return True

    def on_column_activation(self, widget):
        if self.callback:
            self.callback(self.previous, self.name)
        return True

    def on_button_press(self, widget, event):
        att=None
        if event.button == 1:
            selection = widget.get_selection()
            if selection is not None:
                store, it = selection.get_selected()
                if it is not None:
                    att = widget.get_model().get_value (it, 0)
        if att and att.startswith('----'):
            return True
        if att and self.callback:
            self.callback(self, att)
            return True
        return False

    def on_changed_selection(self, selection, model):
        att=None
        if selection is not None:
            store, it = selection.get_selected()
            if it is not None:
                att = model.get_value (it, 0)
        if att and att.startswith('----'):
            return True
        if att and self.callback:
            self.callback(self, att)
            return True
        return False

    def build_widget(self):
        vbox=Gtk.VBox()

        self.label=Gtk.Button(self.name, use_underline=False)
        self.label.connect('clicked', self.on_column_activation)
        vbox.pack_start(self.label, False, True, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        vbox.add (sw)

        self.liststore = self.get_liststore()
        self.listview = Gtk.TreeView(self.liststore)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Attributes", renderer, text=0)
        column.set_widget(Gtk.Label())
        self.listview.append_column(column)
        self.listview.connect('key-press-event', self.key_pressed_cb)

        selection = self.listview.get_selection()
        selection.unselect_all()
        selection.connect('changed', self.on_changed_selection, self.liststore)
        #self.listview.connect('row-activated', self.row_activated)
        #self.listview.connect('button-press-event', self.on_button_press)

        sw.add(self.listview)

        vbox.show_all()
        return vbox

class Browser(AdhocView):
    view_name = _("TALES browser")
    view_id = 'browser'
    tooltip=_("TALES browser")
    def __init__(self, controller=None, parameters=None, callback=None, element=None):
        super(Browser, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = [
                    (_("Display result in table"), self.display_result),
                    ]

        if element is None:
            element=controller.package
        self.element=element
        self.controller=controller
        self.callback = callback

        if self.callback:
            def validate_path(*p):
                if self.callback:
                    p=self.pathlabel.get_text()
                    self.close()
                    self.callback(p)
                return True

            def validate_value(*p):
                if self.callback:
                    v="string:%s" % self.valuelabel.get_text()
                    self.close()
                    self.callback(v)
                return True
            self.contextual_actions.append( (_("Insert path"), validate_path) )
            self.contextual_actions.append( (_("Insert value"),  validate_value) )

        self.path=[element]
        # 640 / 4
        self.column_width=160
        self.rootcolumn=None
        self.current_value=None
        self.widget=self.build_widget()

    def update_model(self, package=None):
        if package is None:
            package = self.controller.package

        # Reset to the rootcolumn
        cb=self.rootcolumn.next_column
        while cb is not None:
            cb.widget.destroy()
            cb=cb.next_column
        self.rootcolumn.next_column=None

        # Update the rootcolumn element
        self.rootcolumn.update(element=package, name="here")
        self._update_view('here', package)
        # The clicked_callback must use the new package
        self.element = package
        return True

    def clicked_callback(self, columnbrowser, attribute):
        # We could use here=columnbrowser.model, but then the traversal
        # of path is not done and absolute_url does not work
        context = self.controller.build_context(here=self.element)

        # Rebuild path
        path=['here']
        if columnbrowser is not None:
            col=self.rootcolumn
            while (col is not columnbrowser) and (col is not None):
                col=col.next_column
                if col is not None:
                    path.append(col.name)
            path.append(attribute)

        try:
            el=context.evaluateValue("/".join(path))
        except (AdveneException, TypeError) as e:
            # Delete all next columns
            if columnbrowser is None:
                cb=self.rootcolumn.next_column
            else:
                cb=columnbrowser.next_column
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next_column
            if columnbrowser is not None:
                columnbrowser.next_column=None
                self._update_view(path, Exception(_("Expression returned None (there was an exception)")))
                if config.data.preferences['expert-mode']:
                    self.log("Exception when evaluating %s :\n%s" % ("/".join(path),
                                                                      str(e)))
            return True

        self._update_view(path, el)

        if columnbrowser is None:
            # We selected  the rootcolumn. Delete the next ones
            cb=self.rootcolumn.next_column
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next_column
            self.rootcolumn.next_column=None
        elif columnbrowser.next_column is None:
            # Create a new columnbrowser
            col=BrowserColumn(element=el, name=attribute, callback=self.clicked_callback,
                              parent=columnbrowser)
            col.widget.set_property("width-request", self.column_width)
            self.hbox.pack_start(col.get_widget(), False, False, 0)
            columnbrowser.next_column=col
        else:
            # Delete all next+1 columns (we reuse the next one)
            cb=columnbrowser.next_column.next_column
            while cb is not None:
                cb.widget.destroy()
                cb=cb.next_column
            columnbrowser.next_column.update(element=el, name=attribute)

        # Scroll the columns
        adj=self.sw.get_hadjustment()
        adj.set_value(adj.get_upper() - .1)
        return True

    def _update_view(self, path, element):
        self.pathlabel.set_text("/".join(path))
        self.typelabel.set_text(str(type(element)))
        try:
            val=str(element)
        except UnicodeDecodeError:
            val=str(repr(element))
        if '\n' in val:
            val=val[:val.index('\n')]+'...'
        if len(val) > 80:
            val=val[:77]+'...'
        self.valuelabel.set_text(val)
        self.current_value=element

    def display_result(self, *p):
        """Display the results as annotations in a table
        """
        if not hasattr(self.current_value, '__iter__'):
            self.log(_("Result is not a list"))
            return True

        self.controller.gui.open_adhoc_view('interactiveresult', result=self.current_value)
        return True

    def scroll_event(self, widget=None, event=None):
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            a=widget.get_hadjustment()
            if event.direction == Gdk.ScrollDirection.DOWN or event.direction == Gdk.ScrollDirection.RIGHT:
                val = helper.clamp(a.get_value() + a.get_step_increment(),
                                   a.get_lower(),
                                   a.get_upper() - a.get_page_size())
                if val != a.get_value():
                    a.set_value(val)
                    a.value_changed ()
                return True
            elif event.direction == Gdk.ScrollDirection.UP or event.direction == Gdk.ScrollDirection.LEFT:
                val = helper.clamp(a.get_value() - a.get_step_increment(),
                                   a.get_lower(),
                                   a.get_upper() - a.get_page_size())
                if val != a.get_value():
                    a.set_value(val)
                    a.value_changed ()
                return True
        return False

    def build_widget(self):
        vbox=Gtk.VBox()

        self.sw=Gtk.ScrolledWindow()
        self.sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.sw.connect('scroll-event', self.scroll_event)
        vbox.add(self.sw)

        self.hbox = Gtk.HBox()

        self.rootcolumn=BrowserColumn(element=self.element, name='here',
                                      callback=self.clicked_callback,
                                      parent=None)
        self.rootcolumn.widget.set_property("width-request", self.column_width)
        self.hbox.pack_start(self.rootcolumn.get_widget(), False, False, 0)

        self.sw.add_with_viewport(self.hbox)

        def name_label(name, label):
            hb=Gtk.HBox()
            l=Gtk.Label()
            l.set_markup("<b>%s :</b> " % name)
            hb.pack_start(l, False, True, 0)
            hb.pack_start(label, False, True, 0)
            return hb

        # Display the type/value of the current element
        self.pathlabel = Gtk.Label(label="here")
        self.pathlabel.set_selectable(True)
        vbox.pack_start(name_label(_("Path"), self.pathlabel), False, False, 0)

        self.typelabel = Gtk.Label(label=str(type(self.element)))
        vbox.pack_start(name_label(_("Type"), self.typelabel), False, False, 0)

        self.valuelabel = Gtk.Label(label="here")
        self.valuelabel.set_selectable(True)
        vbox.pack_start(name_label(_("Value"), self.valuelabel), False, False, 0)

        vbox.show_all()
        def debug(*p):
            logger.warn("browser debug %s", str(p), exc_info=True)
            return True

        #vbox.connect('destroy', debug)
        return vbox
