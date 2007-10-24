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
"""Notebook containing multiple views
"""

import advene.core.config as config

import gtk
import cgi

from gettext import gettext as _
from advene.gui.views import AdhocView
import advene.util.helper as helper
from advene.gui.util import get_pixmap_button, dialog

class ViewBook(AdhocView):
    """Notebook containing multiple views
    """
    view_name = _("ViewBook")
    view_id = 'viewbook'
    def __init__ (self, controller=None, views=None, location=None):
        super(ViewBook, self).__init__(controller=controller)
        self.controller=controller
        if views is None:
            views = []
        self.views=[]

        # Record the viewbook location (south, west, east, fareast)
        self.location=location

        # List of widgets that cannot be removed
        self.permanent_widgets = []

        self.widget=self.build_widget()
        for v in views:
            self.add_view(v, v.view_name)

    def remove_view(self, view):
        if view in self.permanent_widgets:
            self.log(_("Cannot remove this widget, it is essential."))
            return False
        view.close()
        return True

    def detach_view(self, view):
        if view in self.permanent_widgets:
            self.log(_("Cannot remove this widget, it is essential."))
            return False
        self.views.remove(view)
        view.widget.get_parent().remove(view.widget)
        return True

    def clear(self):
        """Clear the viewbook.
        """
        for v in self.views:
            if not v in self.permanent_widgets:
                self.remove_view(v)

    def add_view(self, v, name=None, permanent=False):
        """Add a new view to the notebook.

        Each view is an Advene view, and must have a .widget attribute
        """
        if name is None:
            try:
                name=v.view_name
            except AttributeError:
                name="FIXME"
        self.controller.gui.register_view (v)
        self.views.append(v)
        v._destination=self.location
        v._label=name
        if permanent:
            self.permanent_widgets.append(v)

        def close_view(item, view):
            self.remove_view(view)
            return True

        def detach_view(item, view):
            self.detach_view(view)
            return True

        def popup_menu(button, event, view):

            def relocate_view(item, v, d):
                # Reference the widget so that it is not destroyed
                wid=v.widget
                if not self.detach_view(v):
                    return True
                if d == 'popup':
                    v.popup(label=v._label)
                elif d in ('south', 'east', 'west', 'fareast'):
                    v._destination=d
                    self.controller.gui.viewbook[d].add_view(v, name=v._label)
                return True

            if event.button == 3:
                menu = gtk.Menu()
                if not permanent:
                    # Relocation submenu
                    submenu=gtk.Menu()

                    for (label, destination) in (
                        (_("...in its own window"), 'popup'),
                        (_("...embedded east of the video"), 'east'),
                        (_("...embedded west of the video"), 'west'),
                        (_("...embedded south of the video"), 'south'),
                        (_("...embedded at the right of the window"), 'fareast')):
                        if destination == self.location:
                            continue
                        item = gtk.MenuItem(label)
                        item.connect('activate', relocate_view,  view, destination)
                        submenu.append(item)

                    item=gtk.MenuItem(_("Detach"))
                    item.set_submenu(submenu)
                    menu.append(item)

                    item = gtk.MenuItem(_("Close"))
                    item.connect("activate", close_view, view)
                    menu.append(item)

                try:
                    for label, action in view.contextual_actions:
                        item = gtk.MenuItem(label)
                        item.connect("activate", action, view)
                        menu.append(item)
                except AttributeError:
                    pass

                menu.show_all()
                menu.popup(None, None, None, 0, gtk.get_current_event_time())
                return True
            elif event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                # Double click: propose to rename the view
                label_widget=button.get_children()[0]
                lab=dialog.entry_dialog(title=_("Rename the view"),
                                        text=_("Please enter the new name of the view"),
                                        default=view._label)
                if lab is not None:
                    label_widget.set_text(lab)
                    view._label=lab
                return True
            return False

        def label_drag_sent(widget, context, selection, targetType, eventTime, v):
            if targetType == config.data.target_type['adhoc-view-instance']:
                # This is not very robust, but allows to transmit a view instance reference
                selection.set(selection.target, 8, self.controller.gui.get_adhoc_view_instance_id(v))
                self.detach_view(v)
                return True
            return False

        e=gtk.EventBox()
        if len(name) > 13:
            shortname=unicode(name[:12]) + u'\u2026'
        else:
            shortname=name
        l=gtk.Label(shortname)
        if self.controller.gui:
            self.controller.gui.tooltips.set_tip(e, name)
        e.add(l)
        e.connect("button_press_event", popup_menu, v)

        if not permanent:
            e.connect("drag_data_get", label_drag_sent, v)
            # The widget can generate drags
            e.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['adhoc-view-instance'],
                              gtk.gdk.ACTION_LINK)
        hb=gtk.HBox()
        hb.pack_start(e, expand=False, fill=False)

        if not permanent:
            b=get_pixmap_button('small_close.png')
            b.set_relief(gtk.RELIEF_NONE)
            b.connect('clicked', close_view, v)
            hb.pack_start(b, expand=False, fill=False)
        hb.show_all()

        self.widget.append_page(v.widget, hb)
        v.widget.show_all()
        # Hide the player toolbar when the view is embedded
        try:
            v.player_toolbar.hide()
        except AttributeError:
            pass

        num=self.widget.page_num(v.widget)
        self.widget.set_current_page(num)

        return True

    def drag_received(self, widget, context, x, y, selection, targetType, time):
        if targetType == config.data.target_type['adhoc-view']:
            data=dict(cgi.parse_qsl(selection.data))
            label=None
            if 'id' in data:
                # Saved parametered view. Get the view itself.
                ident=data['id']
                v=helper.get_id(self.controller.package.views, ident)
                # Get the view_id
                if v is None:
                    self.log(_("Cannot find the view %s") % ident)
                    return True
                name=v
                label=v.title
            elif 'name' in data:
                name=data['name']
            else:
                # Bug
                self.log("Cannot happen")
                return True

            if self.controller.gui:
                view=self.controller.gui.open_adhoc_view(name, label=label, destination=self.location)
                if 'master' in data:
                    # A master view has been specified. Connect it to
                    # the created view.
                    master=self.controller.gui.get_adhoc_view_instance_from_id(data['master'])
                    view.set_master_view(master)
            return True
        elif targetType == config.data.target_type['adhoc-view-instance']:
            v=self.controller.gui.get_adhoc_view_instance_from_id(selection.data)
            if v is not None:
                wid=v.widget
                self.add_view(v, name=v._label)
            else:
                print "Cannot find view ", selection.data
            return True
        elif targetType == config.data.target_type['annotation-type']:
            at=self.controller.package.annotationTypes.get(selection.data)
            # Propose a menu to open various views for the annotation-type:
            menu=gtk.Menu()
            i=gtk.MenuItem(_("Use annotation-type %s :") % self.controller.get_title(at))
            menu.append(i)
            for label, action in (
                (_("as a transcription"), lambda i: self.controller.gui.open_adhoc_view('transcription', source='here/annotationTypes/%s/annotations/sorted' % at.id, destination=self.location)),
                (_("in a timeline"), lambda i: self.controller.gui.open_adhoc_view('timeline', elements=at.annotations, annotationtypes=[ at ], destination=self.location)),
                (_("as a montage"), lambda i: self.controller.gui.open_adhoc_view('montage', elements=at.annotations, destination=self.location)),
                (_("in a table"), lambda i: self.controller.gui.open_adhoc_view('table', elements=at.annotations, destination=self.location)),
                (_("in a query"), lambda i: self.controller.gui.open_adhoc_view('interactivequery', here=at, destination=self.location)),
                (_("in the package browser"), lambda i: self.controller.gui.open_adhoc_view('browser', element=at, destination=self.location)),
                ):
                i=gtk.MenuItem(label)
                i.connect('activate', action)
                menu.append(i)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True
        elif targetType == config.data.target_type['annotation']:
            a=self.controller.package.annotations.get(selection.data)
            # Propose a menu to open various views for the annotation:
            menu=gtk.Menu()
            i=gtk.MenuItem(_("Use annotation %s :") % self.controller.get_title(a))
            menu.append(i)
            for label, action in (
                (_("in a query"), lambda i: self.controller.gui.open_adhoc_view('interactivequery', here=a, destination=self.location)),
                (_("in the package browser"), lambda i: self.controller.gui.open_adhoc_view('browser', element=a, destination=self.location)),
                (_("to display its contents"), lambda i: self.controller.gui.open_adhoc_view('annotationdisplay', annotation=a, destination=self.location)),
                ):
                i=gtk.MenuItem(label)
                i.connect('activate', action)
                menu.append(i)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True
        return False

    def build_widget(self):
        notebook=gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_TOP)
        notebook.popup_disable()
        notebook.set_scrollable(True)

        notebook.connect("drag_data_received", self.drag_received)
        notebook.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                               gtk.DEST_DEFAULT_HIGHLIGHT |
                               gtk.DEST_DEFAULT_DROP |
                               gtk.DEST_DEFAULT_ALL,
                               config.data.drag_type['adhoc-view'] +
                               config.data.drag_type['adhoc-view-instance'] +
                               config.data.drag_type['annotation-type'] +
                               config.data.drag_type['annotation'],
                               gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK)

        return notebook
