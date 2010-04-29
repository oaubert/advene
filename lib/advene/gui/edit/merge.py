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
"""GUI to merge packages.
"""
import gtk
import gobject
import difflib
import pango

from gettext import gettext as _

import advene.gui.popup
import advene.util.helper as helper
from advene.util.merger import Differ

labels = {
 'new': _("Create element"),
 'new_annotation': _("Create annotation (duplicate id)"),
 'new_relation': _("Create relation (duplicate id)"),
 'update_meta_color': _("Update the color"),
 'update_meta_representation': _("Update the representation"),
 'update_meta_description': _("Update the description"),
 'update_title': _("Update the title"),
 'update_mimetype': _("Update the mimetype"),
 'update_begin': _("Update the begin time"),
 'update_end': _("Update the end time"),
 'update_content': _("Update the content"),
 'update_matchfilter': _("Update the matchFilter"),
 'update_member_types': _("Update the member types"),
 'update_tags': _("Update tags"),
 }

class TreeViewMerger:
    COLUMN_ELEMENT=0
    COLUMN_ACTION=1
    COLUMN_ELEMENT_NAME=2
    COLUMN_APPLY=3

    def __init__(self, controller=None, differ=None):
        self.controller=controller
        self.differ=differ
        self.store=self.build_liststore()
        self.widget=self.build_widget()

    def build_liststore(self):
        # Store reference to the element, string representation (title and id)
        # and boolean indicating wether it is imported or not
        store=gtk.ListStore(
            gobject.TYPE_PYOBJECT,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_BOOLEAN,
            )

        for l in self.differ.diff():
            name, s, d, action=l
            # Note: s and d are normally Advene elements, except for
            # resources for which we have the path.
            store.append(row=[ l,
                               labels.setdefault(name, name),
                               "%s %s (%s)" % (helper.get_type(s),
                                               self.controller.get_title(s),
                                               getattr(s, 'id', unicode(s))),
                               True ])
        return store

    def build_widget(self):
        def show_diff(item, l):
            name, s, d, action = l

            diff=difflib.Differ()

            w=gtk.Window()
            w.set_title(_("Difference between original and merged elements"))

            v=gtk.VBox()

            sw = gtk.ScrolledWindow()
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
            v.add(sw)

            tv=gtk.TextView()
            f=pango.FontDescription("courier 12")
            tv.modify_font(f)

            b=tv.get_buffer()


            minustag=b.create_tag("minus", background="lightsalmon")
            plustag=b.create_tag("plus", background="palegreen1")

            for l in diff.compare(d.content.data.splitlines(1),
                                  s.content.data.splitlines(1)):
                if l.startswith('-'):
                    b.insert_with_tags(b.get_iter_at_mark(b.get_insert()), l, minustag)
                elif l.startswith('+'):
                    b.insert_with_tags(b.get_iter_at_mark(b.get_insert()), l, plustag)
                else:
                    b.insert_at_cursor(l)
            sw.add(tv)

            hb=gtk.HButtonBox()
            b=gtk.Button(stock=gtk.STOCK_CLOSE)
            b.connect('clicked', lambda b: w.destroy())
            hb.add(b)

            v.pack_start(hb, expand=False)
            w.add(v)

            w.show_all()
            w.resize(800, 600)
            return True

        def build_popup_menu(l):
            menu=gtk.Menu()

            name, s, d, action = l

            if name != 'new':
                i=gtk.MenuItem(_("Current element"))
                m = advene.gui.popup.Menu(d, controller=self.controller, readonly=False)
                i.set_submenu(m.menu)
                menu.append(i)

            i=gtk.MenuItem(_("Updated element"))
            m = advene.gui.popup.Menu(s, controller=self.controller, readonly=True)
            i.set_submenu(m.menu)
            menu.append(i)

            if name == 'update_content':
                i=gtk.MenuItem(_("Show diff"))
                i.connect('activate', show_diff, l)
                menu.append(i)

            menu.show_all()
            return menu

        def tree_view_button_cb(widget=None, event=None):
            retval = False
            button = event.button
            x = int(event.x)
            y = int(event.y)

            if button == 3:
                if event.window is widget.get_bin_window():
                    model = widget.get_model()
                    t = widget.get_path_at_pos(x, y)
                    if t is not None:
                        path, col, cx, cy = t
                        it = model.get_iter(path)
                        node = model.get_value(it, self.COLUMN_ELEMENT)
                        widget.get_selection().select_path (path)
                        menu=build_popup_menu(node)
                        menu.popup(None, None, None, 0, gtk.get_current_event_time())
                        retval = True
            return retval


        treeview=gtk.TreeView(model=self.store)
        treeview.connect('button-press-event', tree_view_button_cb)

        renderer = gtk.CellRendererToggle()
        renderer.set_property('activatable', True)
        column = gtk.TreeViewColumn(_('Merge?'), renderer,
                                    active=self.COLUMN_APPLY)

        def toggled_cb(renderer, path, model, column):
            model[path][column] = not model[path][column]
            return True
        renderer.connect('toggled', toggled_cb, self.store, self.COLUMN_APPLY)

        treeview.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Action'), renderer,
                                    text=self.COLUMN_ACTION)
        column.set_resizable(True)
        treeview.append_column(column)

        renderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(_('Element'), renderer,
                                    text=self.COLUMN_ELEMENT_NAME)
        column.set_resizable(True)
        treeview.append_column(column)

        return treeview

class Merger:
    def __init__(self, controller=None, sourcepackage=None, destpackage=None):
        self.controller=controller
        self.sourcepackage=sourcepackage
        self.destpackage=destpackage
        self.differ=Differ(sourcepackage, destpackage, self.controller)
        self.widget=self.build_widget()

    def build_widget(self):
        vbox=gtk.VBox()

        vbox.pack_start(gtk.Label("Merge elements from %s into %s" % (self.sourcepackage.uri,
                                                                     self.destpackage.uri)),
                                  expand=False)

        scroll_win = gtk.ScrolledWindow ()
        scroll_win.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.add(scroll_win)

        self.mergerview=TreeViewMerger(controller=self.controller, differ=self.differ)
        scroll_win.add(self.mergerview.widget)

        return vbox

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title (_("Package %s") % (self.destpackage.title or _("No title")))

        vbox = gtk.VBox()
        window.add (vbox)

        vbox.add (self.widget)
        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'merge')
            window.set_icon_list(*self.controller.gui.get_icon_list())

        self.buttonbox = gtk.HButtonBox()

        def validate(b):
            print "Validate"
            m=self.mergerview.store
            for l in m:
                if l[self.mergerview.COLUMN_APPLY]:
                    name, s, d, action = l[self.mergerview.COLUMN_ELEMENT]
                    action(s, d)
            self.destpackage._modified = True
            self.controller.notify('PackageActivate', package=self.destpackage)
            window.destroy()
            return True

        def select_all(b):
            model=self.mergerview.store
            for l in model:
                l[self.mergerview.COLUMN_APPLY] = True
            return True

        def unselect_all(b):
            model=self.mergerview.store
            for l in model:
                l[self.mergerview.COLUMN_APPLY] = False
            return True


        b = gtk.Button(_("All"))
        b.connect('clicked', select_all)
        self.buttonbox.add (b)


        b = gtk.Button(_('None'))
        b.connect('clicked', unselect_all)
        self.buttonbox.add (b)

        b = gtk.Button(stock=gtk.STOCK_OK)
        b.connect('clicked', validate)
        self.buttonbox.add (b)

        b = gtk.Button(stock=gtk.STOCK_CANCEL)
        b.connect('clicked', lambda b: window.destroy())
        self.buttonbox.add (b)

        vbox.pack_start(self.buttonbox, expand=False)

        window.show_all()

        return window
