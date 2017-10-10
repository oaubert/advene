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
"""Notebook containing multiple views
"""
import logging
logger = logging.getLogger(__name__)

import advene.core.config as config

from gi.repository import Gdk
from gi.repository import Gtk

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
    def __init__ (self, controller=None, parameters=None, views=None, location=None, ):
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
        if hasattr(view, 'reparent_prepare'):
            view.reparent_prepare()
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

        def relocate_view(item, v, d):
            # Reference the widget so that it is not destroyed
            if not self.detach_view(v):
                return True
            if d == 'popup':
                v.popup(label=v._label)
            elif d in ('south', 'east', 'west', 'fareast'):
                v._destination=d
                self.controller.gui.viewbook[d].add_view(v, name=v._label)
            return True

        def handle_contextual_action(menuitem, action):
            action()
            return True

        def popup_menu(button, event, view):
            if event.button == 3:
                menu = Gtk.Menu()
                if not permanent:
                    # Relocation submenu
                    submenu=Gtk.Menu()

                    for (label, destination) in (
                        (_("...in its own window"), 'popup'),
                        (_("...embedded east of the video"), 'east'),
                        (_("...embedded west of the video"), 'west'),
                        (_("...embedded south of the video"), 'south'),
                        (_("...embedded at the right of the window"), 'fareast')):
                        if destination == self.location:
                            continue
                        item = Gtk.MenuItem(label)
                        item.connect('activate', relocate_view,  view, destination)
                        submenu.append(item)

                    item=Gtk.MenuItem(_("Detach"))
                    item.set_submenu(submenu)
                    menu.append(item)

                    item = Gtk.MenuItem(_("Close"))
                    item.connect('activate', close_view, view)
                    menu.append(item)

                try:
                    for label, action in view.contextual_actions:
                        item = Gtk.MenuItem(label, use_underline=False)
                        item.connect('activate', handle_contextual_action, action)
                        menu.append(item)
                except AttributeError:
                    pass

                menu.show_all()
                menu.popup_at_pointer(None)
                return True
            elif event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                # Double click: propose to rename the view
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
                selection.set(selection.get_target(), 8, self.controller.gui.get_adhoc_view_instance_id(v).encode('utf-8'))
                self.detach_view(v)
                return True
            return False

        e=Gtk.EventBox()
        e.set_visible_window(False)
        e.set_above_child(True)
        if len(name) > 13:
            shortname=str(name)[:12] + helper.chars.ellipsis
        else:
            shortname=name
        l=Gtk.Label()
        l.set_markup("<small>%s</small>" % shortname)
        if self.controller.gui:
            e.set_tooltip_text(name)
        e.add(l)
        e.connect('button-press-event', popup_menu, v)

        if not permanent:
            e.connect('drag-data-get', label_drag_sent, v)
            # The widget can generate drags
            e.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                              config.data.get_target_types('adhoc-view-instance'),
                              Gdk.DragAction.COPY | Gdk.DragAction.LINK)
        hb=Gtk.HBox()

        if not permanent:
            b=get_pixmap_button('small_detach.png')
            b.set_tooltip_text(_("Detach view in its own window, or drag-and-drop to another zone"))
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.connect('clicked', relocate_view, v, 'popup')
            b.connect('drag-data-get', label_drag_sent, v)
            # The widget can generate drags
            b.drag_source_set(Gdk.ModifierType.BUTTON1_MASK,
                              config.data.get_target_types('adhoc-view-instance'),
                              Gdk.DragAction.COPY | Gdk.DragAction.LINK)
            hb.pack_start(b, False, False, 0)

        hb.pack_start(e, False, False, 0)

        if not permanent:
            b=get_pixmap_button('small_close.png')
            b.set_tooltip_text(_("Close view"))
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.connect('clicked', close_view, v)
            hb.pack_start(b, False, False, 0)
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
            self.add_view(p, name=_("Edit %s") % self.controller.get_title(v, max_size=40))
            # FIXME: put focus on edit window
            return True

        def edit_annotation(a):
            p=get_edit_popup(a, controller=self.controller)
            self.add_view(p, name=_("Edit %s") % self.controller.get_title(a, max_size=40))
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
            data=decode_drop_parameters(selection.get_data())
            label=None
            view=None
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
                view=self.controller.gui.open_adhoc_view(name, label=label, destination=None)
                if view is not None:
                    self.add_view(view, name=view.view_name)
            elif 'name' in data:
                name=data['name']
                if name == 'comment':
                    saved=[ v
                            for v in self.controller.package.views
                            if helper.get_view_type(v) == 'static'
                            and v.matchFilter['class'] == 'package'
                            and not v.id.startswith('_') ]
                else:
                    saved=[ v
                            for v in self.controller.package.views
                            if v.content.mimetype == 'application/x-advene-adhoc-view'
                            and ET.parse(v.content.stream).getroot().attrib['id'] == name ]

                if name == 'transcription' or name == 'table':
                    menu=Gtk.Menu()
                    i=Gtk.MenuItem(_("Open a new %s for...") % _(name))
                    menu.append(i)
                    sm=Gtk.Menu()
                    i.set_submenu(sm)
                    for at in self.controller.package.annotationTypes:
                        title=self.controller.get_title(at, max_size=40)
                        i=Gtk.MenuItem(title, use_underline=False)
                        i.connect('activate', lambda i, s, t: self.controller.gui.open_adhoc_view(name, source=s, label=t, destination=self.location), "here/annotationTypes/%s/annotations/sorted" % at.id, title)
                        sm.append(i)
                elif saved:
                    menu=Gtk.Menu()
                    if name == 'comment':
                        i=Gtk.MenuItem(_("Create a new comment view"))
                    else:
                        i=Gtk.MenuItem(_("Open a new view"))
                    i.connect('activate', lambda i: self.controller.gui.open_adhoc_view(name, label=label, destination=self.location))
                    menu.append(i)
                else:
                    menu=None

                if menu is not None:
                    if saved:
                        i=Gtk.MenuItem(_("Open a saved view"))
                        menu.append(i)
                        sm=Gtk.Menu()
                        i.set_submenu(sm)
                        for v in saved:
                            i=Gtk.MenuItem(v.title, use_underline=False)
                            if name == 'comment':
                                i.connect('activate', lambda i, vv: self.controller.gui.open_adhoc_view('edit', element=vv, destination=self.location), v)
                            else:
                                i.connect('activate', lambda i, vv: self.controller.gui.open_adhoc_view(vv, label=vv.title, destination=self.location), v)
                            sm.append(i)
                    menu.show_all()
                    menu.popup_at_pointer(None)
                else:
                    view=self.controller.gui.open_adhoc_view(name, label=label, destination=None)
                    if view is not None:
                        self.add_view(view, name=view.view_name)
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
            v=self.controller.gui.get_adhoc_view_instance_from_id(selection.get_data().decode('utf-8'))
            if v is not None:
                self.add_view(v, name=v._label)
                if hasattr(v, 'reparent_done'):
                    v.reparent_done()
            else:
                logger.error("Cannot find view %s", selection.get_data())
            return True
        elif targetType == config.data.target_type['view']:
            v=self.controller.package.views.get(str(selection.get_data(), 'utf8'))
            if helper.get_view_type(v) in ('static', 'dynamic'):
                # Edit the view.
                self.controller.gui.open_adhoc_view('edit', element=v, destination=self.location)
            else:
                logger.error("Unhandled case in viewbook (targetType=view) for %s", v.id)
            return True
        elif targetType == config.data.target_type['query']:
            v=self.controller.package.queries.get(str(selection.get_data(), 'utf8'))
            if v is not None:
                self.controller.gui.open_adhoc_view('edit', element=v, destination=self.location)
            else:
                logger.error("Unhandled case in viewbook (targetType=query) for %s", v.id)
            return True
        elif targetType == config.data.target_type['schema']:
            v=self.controller.package.schemas.get(str(selection.get_data(), 'utf8'))
            if v is not None:
                self.controller.gui.open_adhoc_view('edit', element=v, destination=self.location)
            else:
                logger.error("Unhandled case in viewbook (targetType=schema) for %s", v.id)
            return True
        elif targetType == config.data.target_type['relation']:
            v=self.controller.package.relations.get(str(selection.get_data(), 'utf8'))
            if v is not None:
                self.controller.gui.open_adhoc_view('edit', element=v, destination=self.location)
            else:
                logger.error("Unhandled case in viewbook (targetType=relation) for %s", v.id)
            return True
        elif targetType == config.data.target_type['annotation-type']:
            at=self.controller.package.annotationTypes.get(str(selection.get_data(), 'utf8'))
            if at is None:
                logger.error("Unhandled case in viewbook (targetType=relation) for %s", v.id)
                return True
            # Propose a menu to open various views for the annotation-type:
            menu=Gtk.Menu()
            title=self.controller.get_title(at, max_size=40)
            i=Gtk.MenuItem(_("Use annotation-type %s :") % title, use_underline=False)
            talespath = 'here/annotationTypes/%s' % at.id
            menu.append(i)
            for label, action in (
                (_("to edit it"), lambda i :self.controller.gui.open_adhoc_view('edit', element=at, destination=self.location)),
                (_("to create a new static view"), lambda i: create_and_open_view([ at ])),
                (_("as a transcription"), lambda i: self.controller.gui.open_adhoc_view('transcription', source='%s/annotations/sorted' % talespath, destination=self.location, label=title)),
                (_("in a timeline"), lambda i: self.controller.gui.open_adhoc_view('timeline', elements=at.annotations, annotationtypes=[ at ], destination=self.location, label=title)),
                (_("as a montage"), lambda i: self.controller.gui.open_adhoc_view('montage', elements=at.annotations, destination=self.location, label=title)),
                (_("in a table"), lambda i: self.controller.gui.open_adhoc_view('table', source='%s/annotations' % talespath, destination=self.location, label=title)),
                (_("in a query"), lambda i: self.controller.gui.open_adhoc_view('interactivequery', here=at, destination=self.location, label=_("Query %s") % title)),
                (_("in the TALES browser"), lambda i: self.controller.gui.open_adhoc_view('browser', element=at, destination=self.location, label=_("Browsing %s") % title)),
                ):
                i=Gtk.MenuItem("    " + label, use_underline=False)
                i.connect('activate', action)
                menu.append(i)
            menu.show_all()
            menu.popup_at_pointer(None)
            return True
        elif targetType == config.data.target_type['annotation']:
            sources=[ self.controller.package.annotations.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
            # Propose a menu to open various views for the annotation:
            menu=Gtk.Menu()

            if len(sources) == 1:
                a=sources[0]
                title=self.controller.get_title(a, max_size=40)
                i=Gtk.MenuItem(_("Use annotation %s :") % title, use_underline=False)
                menu.append(i)
                for label, action in (
                    (_("to edit it"), lambda i: edit_annotation(a)),
                    (_("to create a new static view"), lambda i: create_and_open_view(sources)),
                    (_("in a query"), lambda i: self.controller.gui.open_adhoc_view('interactivequery', here=a, destination=self.location, label=_("Query %s") % title)),
                    (_("in the TALES browser"), lambda i: self.controller.gui.open_adhoc_view('browser', element=a, destination=self.location, label=_("Browse %s") % title)),
                    (_("to display its contents"), lambda i: self.controller.gui.open_adhoc_view('annotationdisplay', annotation=a, destination=self.location, label=_("%s") % title)) ,
                    (_("as a bookmark"), lambda i: self.controller.gui.open_adhoc_view('activebookmarks', elements=[ a.fragment.begin ], destination=self.location)),
                    ):
                    i=Gtk.MenuItem("    " + label, use_underline=False)
                    i.connect('activate', action)
                    menu.append(i)

                def apply_query(m, q):
                    ctx=self.controller.build_context(here=a)
                    res, qexpr=self.controller.evaluate_query(q, context=ctx)
                    self.controller.gui.open_adhoc_view('interactiveresult', query=q, result=res, destination=self.location)
                    return True

                if self.controller.package.queries:
                    sm=Gtk.Menu()
                    for q in self.controller.package.queries:
                        i=Gtk.MenuItem(self.controller.get_title(q, max_size=40), use_underline=False)
                        i.connect('activate', apply_query, q)
                        sm.append(i)
                    i=Gtk.MenuItem("    " + _("as the context for the query..."), use_underline=False)
                    i.set_submenu(sm)
                    menu.append(i)
            else:
                title=_("Set of annotations")
                i=Gtk.MenuItem(_("Use annotations:"), use_underline=False)
                menu.append(i)
                for label, action in (
                    (_("to edit them"), lambda i: edit_selection(sources)),
                    (_("in a table"), lambda i: self.controller.gui.open_adhoc_view('table', elements=sources, destination=self.location)),
                    (_("to create a new static view"), lambda i: create_and_open_view(sources)),
                    (_("as bookmarks"), lambda i: self.controller.gui.open_adhoc_view('activebookmarks', elements=[ a.fragment.begin for a in sources ], destination=self.location)),
                    ):
                    i=Gtk.MenuItem("    " + label, use_underline=False)
                    i.connect('activate', action)
                    menu.append(i)
            menu.show_all()
            menu.popup_at_pointer(None)
            return True
        elif targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.get_data())
            v=self.controller.gui.open_adhoc_view('activebookmarks', destination=self.location)
            v.append(int(data['timestamp']), comment=data.get('comment', ''))
            return True
        else:
            logger.error("Unknown drag target received %s", targetType)
        return False

    def on_key_press_event(self, widget, event):
        """Keypress handling.
        """
        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            # The Control-key is held. Special actions :
            if event.keyval == Gdk.KEY_Page_Up:
                # Popup the evaluator window
                self.widget.prev_page()
                return True
            elif event.keyval == Gdk.KEY_Page_Down:
                # Popup the evaluator window
                self.widget.next_page()
                return True
        return False

    def build_widget(self):
        notebook=Gtk.Notebook()
        notebook.set_tab_pos(Gtk.PositionType.TOP)
        notebook.popup_disable()
        notebook.set_scrollable(True)

        notebook.connect('key-press-event', self.on_key_press_event)
        notebook.connect('drag-data-received', self.drag_received)
        notebook.drag_dest_set(Gtk.DestDefaults.MOTION |
                               Gtk.DestDefaults.HIGHLIGHT |
                               Gtk.DestDefaults.DROP |
                               Gtk.DestDefaults.ALL,
                               config.data.get_target_types('adhoc-view',
                                                            'adhoc-view-instance',
                                                            'view',
                                                            'query',
                                                            'schema',
                                                            'annotation-type',
                                                            'annotation',
                                                            'relation',
                                                            'timestamp'),
                               Gdk.DragAction.COPY | Gdk.DragAction.MOVE | Gdk.DragAction.LINK)

        return notebook
