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
"""GUI to merge packages.
"""
import sys

import gtk
import gobject

from gettext import gettext as _

import advene.core.config as config

import advene.gui.popup
import advene.gui.util
import advene.util.helper as helper
from advene.util.merger import Differ

labels = {
 'new': _("Create element"),
 'update_meta_color': _("Update the color"),
 'update_meta_representation': _("Update the representation"),
 'update_meta_description': _("Update the description"),
 'update_title': _("Update the title"),
 'update_mimetype': _("Update the mimetype"),
 'update_begin': _("Update the begin time"),
 'update_end': _("Update the end time"),
 'update_content': _("Update the content"),
 'update_matchfilter': _("Update the matchFilter"),
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
            store.append(row=[ l,
                               labels.setdefault(name, name),
                               "%s %s" % (helper.get_type(s),
                                          self.controller.get_title(s)),
                               True ])
        return store

    def build_widget(self):
        vbox=gtk.VBox()

        treeview=gtk.TreeView(model=self.store)

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

        vbox.add(treeview)
        vbox.show_all()

        return vbox

class Merger:
    def __init__(self, controller=None, sourcepackage=None, destpackage=None):
        self.controller=controller
        self.sourcepackage=sourcepackage
        self.destpackage=destpackage
        self.differ=Differ(sourcepackage, destpackage)
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
        scroll_win.add_with_viewport(self.mergerview.widget)

        return vbox

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title (_("Package %s") % (self.destpackage.title or _("No title")))

        vbox = gtk.VBox()
        window.add (vbox)

        vbox.add (self.widget)
        if self.controller.gui:
            self.controller.gui.register_view (self)
            window.connect ("destroy", self.controller.gui.close_view_cb, window, self)

        if self.controller.gui:
            self.controller.gui.init_window_size(window, 'merge')

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

        b = gtk.Button(stock=gtk.STOCK_OK)
        b.connect("clicked", validate)
        self.buttonbox.add (b)

        vbox.pack_start(self.buttonbox, expand=False)

        window.show_all()

        return window
