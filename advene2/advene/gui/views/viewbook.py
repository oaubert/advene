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
"""Notebook containing multiple views
"""

import advene.core.config as config

import gtk

from gettext import gettext as _
from advene.gui.views import AdhocView
import advene.util.helper as helper
from advene.gui.util import get_pixmap_button, dialog, decode_drop_parameters
import xml.etree.ElementTree as ET
from advene.gui.edit.elements import get_edit_popup

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
        v.set_label(name)
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
                    item.connect('activate', close_view, view)
                    menu.append(item)

                try:
                    for label, action in view.contextual_actions:
                        item = gtk.MenuItem(label, use_underline=False)
                        item.connect('activate', action, view)
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
                    view.set_label(lab)
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
        e.connect('button-press-event', popup_menu, v)

        if not permanent:
            e.connect('drag-data-get', label_drag_sent, v)
            # The widget can generate drags
            e.drag_source_set(gtk.gdk.BUTTON1_MASK,
                              config.data.drag_type['adhoc-view-instance'],
                              gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_LINK)
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
        def create_and_open_view(sources):
            v=self.controller.create_static_view(elements=sources)
            p=get_edit_popup(v, controller=self.controller)
            self.add_view(p, name=_("Edit %s") % self.controller.get_title(v))
            return True

        def edit_annotation(a):
            p=get_edit_popup(a, controller=self.controller)
            self.add_view(p, name=_("Edit %s") % self.controller.get_title(a))
            return True

        def edit_selection(sources):
            """Edit the selected elements in an edit accumulator.
            """
            v=self.controller.gui.open_adhoc_view('editaccumulator',
                                                  destination=self.location)
            if v is not None:
                for a in sources:
                    v.edit(a)
            return True

        if targetType == config.data.target_type['adhoc-view']:
            data=decode_drop_parameters(selection.data)
            label=None
            view=None
            if 'id' in data:
                # Saved parametered view. Get the view itself.
                ident=data['id']
                v=self.controller.package.get(ident)
                # Get the view_id
                if v is None:
                    self.log(_("Cannot find the view %s") % ident)
                    return True
                name=v
                label=v.title
                view=self.controller.gui.open_adhoc_view(name, label=label, destination=self.location)
            elif 'name' in data:
                name=data['name']
                def stbv_name(v):
                    f=v.content.as_file
                    n=ET.parse(f).getroot().attrib.get('id')
                    f.close()
                    return f                    
                saved=[ v
                        for v in self.controller.package.all.views
                        if v.content.mimetype == 'application/x-advene-adhoc-view'
                        and stbv_name(v) == name ]
                if name == 'transcription':
                    menu=gtk.Menu()
                    i=gtk.MenuItem(_("Open a new transcription for..."))
                    menu.append(i)
                    sm=gtk.Menu()
                    i.set_submenu(sm)
                    for at in self.controller.package.all.annotation_types:
                        title=self.controller.get_title(at)
                        i=gtk.MenuItem(title, use_underline=False)
                        i.connect('activate', lambda i, s, t: self.controller.gui.open_adhoc_view(name, source=s, label=t, destination=self.location), "here/all/annotation_types/%s/annotations/sorted" % at.id, title)
                        sm.append(i)
                elif saved:
                    menu=gtk.Menu()
                    i=gtk.MenuItem(_("Open a new view"))
                    i.connect('activate', lambda i: self.controller.gui.open_adhoc_view(name, label=label, destination=self.location))
                    menu.append(i)
                else:
                    menu=None

                if menu is not None:
                    if saved:
                        i=gtk.MenuItem(_("Open a saved view"))
                        menu.append(i)
                        sm=gtk.Menu()
                        i.set_submenu(sm)
                        for v in saved:
                            i=gtk.MenuItem(v.title, use_underline=False)
                            i.connect('activate', lambda i, vv: self.controller.gui.open_adhoc_view(vv, label=vv.title, destination=self.location), v)
                            sm.append(i)
                    menu.show_all()
                    menu.popup(None, None, None, 0, gtk.get_current_event_time())
                else:
                    view=self.controller.gui.open_adhoc_view(name, label=label, destination=self.location)
            else:
                # Bug
                self.log("Cannot happen")
                return True


            if 'master' in data and view is not None:
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
            at=self.controller.package.get(unicode(selection.data, 'utf8'))
            # Propose a menu to open various views for the annotation-type:
            menu=gtk.Menu()
            title=self.controller.get_title(at)
            i=gtk.MenuItem(_("Use annotation-type %s :") % title, use_underline=False)
            menu.append(i)
            for label, action in (
                (_("to create a new static view"), lambda i: create_and_open_view([ at ])),
                (_("as a transcription"), lambda i: self.controller.gui.open_adhoc_view('transcription', source='here/annotationTypes/%s/annotations/sorted' % at.id, destination=self.location, label=title)),
                (_("in a timeline"), lambda i: self.controller.gui.open_adhoc_view('timeline', elements=at.annotations, annotationtypes=[ at ], destination=self.location, label=title)),
                (_("as a montage"), lambda i: self.controller.gui.open_adhoc_view('montage', elements=at.annotations, destination=self.location, label=title)),
                (_("in a table"), lambda i: self.controller.gui.open_adhoc_view('table', elements=at.annotations, destination=self.location, label=title)),
                (_("in a query"), lambda i: self.controller.gui.open_adhoc_view('interactivequery', here=at, destination=self.location, label=_("Query %s") % title)),
                (_("in the TALES browser"), lambda i: self.controller.gui.open_adhoc_view('browser', element=at, destination=self.location, label=_("Browsing %s") % title)),
                ):
                i=gtk.MenuItem(label, use_underline=False)
                i.connect('activate', action)
                menu.append(i)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True
        elif targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.get(uri) for uri in unicode(selection.data, 'utf8').split('\n') ]
            # Propose a menu to open various views for the annotation:
            menu=gtk.Menu()
            
            if len(sources) == 1:
                a=sources[0]
                title=self.controller.get_title(a)
                i=gtk.MenuItem(_("Use annotation %s :") % title, use_underline=False)
                menu.append(i)
                for label, action in (
                    (_("to edit it"), lambda i: edit_annotation(a)),
                    (_("to create a new static view"), lambda i: create_and_open_view(sources)),
                    (_("in a query"), lambda i: self.controller.gui.open_adhoc_view('interactivequery', here=a, destination=self.location, label=_("Query %s") % title)),
                    (_("in the TALES browser"), lambda i: self.controller.gui.open_adhoc_view('browser', element=a, destination=self.location, label=_("Browse %s") % title)),
                    (_("to display its contents"), lambda i: self.controller.gui.open_adhoc_view('annotationdisplay', annotation=a, destination=self.location, label=_("%s") % title)) ,
                    (_("as a bookmark"), lambda i: self.controller.gui.open_adhoc_view('activebookmarks', elements=[ a.begin ], destination=self.location)),
                    ):
                    i=gtk.MenuItem(label, use_underline=False)
                    i.connect('activate', action)
                    menu.append(i)

                def apply_query(m, q):
                    ctx=self.controller.build_context(here=a)
                    res, qexpr=self.controller.evaluate_query(q, context=ctx)
                    self.controller.gui.open_adhoc_view('interactiveresult', query=q, result=res, destination=self.location)
                    return True

                if self.controller.package.all.queries:
                    sm=gtk.Menu()
                    for q in self.controller.package.all.queries:
                        i=gtk.MenuItem(self.controller.get_title(q))
                        i.connect('activate', apply_query, q)
                        sm.append(i)
                    i=gtk.MenuItem(_("as the context for the query..."), use_underline=False)
                    i.set_submenu(sm)
                    menu.append(i)
            else:
                title=_("Set of annotations")
                i=gtk.MenuItem(_("Use annotations:"), use_underline=False)
                menu.append(i)
                for label, action in (
                    (_("to edit them"), lambda i: edit_selection(sources)),
                    (_("to create a new static view"), lambda i: create_and_open_view(sources)),
                    (_("as bookmarks"), lambda i: self.controller.gui.open_adhoc_view('activebookmarks', elements=[ a.begin for a in sources ], destination=self.location)),
                    ):
                    i=gtk.MenuItem(label, use_underline=False)
                    i.connect('activate', action)
                    menu.append(i)
            menu.show_all()
            menu.popup(None, None, None, 0, gtk.get_current_event_time())
            return True
        elif targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.data)
            v=self.controller.gui.open_adhoc_view('activebookmarks', destination=self.location)
            v.append(long(data['timestamp']), comment=data.get('comment', ''))
            return True
        return False

    def build_widget(self):
        notebook=gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_TOP)
        notebook.popup_disable()
        notebook.set_scrollable(True)

        notebook.connect('drag-data-received', self.drag_received)
        notebook.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                               gtk.DEST_DEFAULT_HIGHLIGHT |
                               gtk.DEST_DEFAULT_DROP |
                               gtk.DEST_DEFAULT_ALL,
                               config.data.drag_type['adhoc-view'] +
                               config.data.drag_type['adhoc-view-instance'] +
                               config.data.drag_type['annotation-type'] +
                               config.data.drag_type['annotation'] +
                               config.data.drag_type['timestamp'],
                               gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_LINK)

        return notebook
