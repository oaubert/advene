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

#"""Module displaying active time bookmarks."""

from gettext import gettext as _
import gtk
import gobject
import pango
import urllib

# Advene part
import advene.core.config as config
from advene.gui.util import dialog, get_small_stock_button, get_pixmap_button, name2color, png_to_pixbuf
from advene.gui.util import encode_drop_parameters, decode_drop_parameters, shaped_window_from_xpm, arrow_right_xpm
from advene.gui.views import AdhocView
from advene.gui.views.bookmarks import BookmarkWidget
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment
from advene.model.view import View
import advene.util.helper as helper
import advene.gui.popup

name="ActiveBookmarks view plugin"

def register(controller):
    controller.register_viewclass(ActiveBookmarks)

class ActiveBookmarks(AdhocView):
    """ActiveBookmarks are another way to create annotations.

    First, a time bookmark is set and associated with some text. This
    represents an incomplete annotation (the end bound is missing). Once
    the end bound is set, the triplet (t1, t2, content) is used to create
    an annotation. If no destination type was specified, then a new
    annotation type is created."""
    view_name = _("ActiveBookmarks")
    view_id = 'activebookmarks'
    tooltip= _("ActiveBookmarks")
    def __init__(self, controller=None, parameters=None, type=None):
        super(ActiveBookmarks, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Clear"), self.clear),
            (_("Export as static view"), lambda v, t: self.export_as_static_view()),
            )
        self.options={
            'snapshot-size': config.data.preferences['bookmark-snapshot-width'],
            }
        self.controller=controller
        # self.bookmarks is a list of ActiveBookmark objects
        self.bookmarks=[]
        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        for n, v in arg:
            if n == 'bookmark':
                b=ActiveBookmark(container=self, from_serialisation=v)
                b.widget.show_all()
                self.bookmarks.append(b)

        self.mainbox=gtk.VBox()
        self.widget=self.build_widget()
        self.type = type
        self.arrow_mark=None
        self.refresh()

    def debug (self, widget, *p):
        print "Debug event."
        if p:
            print "Data: %s" % str(p)
        return True

    def get_type(self):
        if hasattr(self, 'chosen_type_selector'):
            return self.chosen_type_selector.get_current_element()
        else:
            return None

    def set_type(self, t):
        if hasattr(self, 'chosen_type_selector'):
            self.chosen_type_selector.set_current_element(t)
    type=property(get_type, set_type)

    def register_callback (self, controller=None):
        self.loop_id=gobject.timeout_add(1000, self.check_contents)

    def unregister_callback(self, controller=None):
        gobject.source_remove(self.loop_id)

    def get_save_arguments(self):
        # Serialisation format: annotationid:begin:end:content where
        # annotationid and end may be "None" and content is
        # url-encoded
        return self.options, ([ ('bookmark', b.serialize()) for b in self.bookmarks ])

    def refresh(self, *p):
        self.mainbox.foreach(self.mainbox.remove)
        for w in self.bookmarks:
            self.mainbox.pack_start(w.widget, expand=False)
        self.mainbox.show_all()
        self.generate_focus_chain()
        return True

    def remove(self, w):
        """Remove the given widget from mainbox.
        """
        index=self.bookmarks.index(w)
        self.bookmarks.remove(w)
        w.widget.destroy()
        if self.bookmarks:
            self.set_current_bookmark(self.bookmarks[index % len(self.bookmarks)])
        self.generate_focus_chain()
        return True

    def clear(self, *p):
        del self.bookmarks[:]
        self.mainbox.foreach(self.mainbox.remove)
        self.mainbox.set_focus_chain([])
        return True

    def get_current_bookmark(self):
        l=[ b for b in self.bookmarks if b.is_current ]
        if l:
            return l[0]
        else:
            return None

    def set_current_bookmark(self, cur=None):
        b=self.get_current_bookmark()
        if b == cur:
            return
        if b is not None:
            b.set_current(False)
        if cur is not None:
            cur.set_current(True)

    def duplicate_bookmark(self, cur=None):
        """Duplicate a bookmark.

        If no bookmark is given, then try to duplicate the current one.
        """
        if cur is None:
            # Control-D: duplicate current bookmark
            cur=self.get_current_bookmark()
        if cur is not None:
            b=ActiveBookmark(container=cur.container,
                             begin=cur.begin,
                             end=cur.end,
                             content=cur.content,
                             annotation=cur.annotation)
            self.append(b, after_current=True)
        return True

    def generate_focus_chain(self, *p):
        self.mainbox.set_focus_chain([ w for b in self.bookmarks  for w in (b.widget, b.begin_widget.comment_entry) ])

    def append(self, t, index=None, after_current=False):
        if not isinstance(t, ActiveBookmark):
            b=ActiveBookmark(container=self, begin=t, end=None, content=None)
        else:
            b=t
        b.widget.show_all()
        if after_current:
            # Insert the bookmark after the current one.
            cur=self.get_current_bookmark()
            if cur is not None:
                index=self.bookmarks.index(cur) + 1
        if index is None:
            self.bookmarks.append(b)
            self.mainbox.pack_start(b.widget, expand=False)
            self.generate_focus_chain()
        else:
            self.bookmarks.insert(index, b)
            self.refresh()

        return b

    def check_contents(self, *p):
        """Check that annotation contents are in sync.
        """
        for wid in self.bookmarks:
            if wid.annotation is not None and wid.content != wid.annotation.content.data:
                # Mismatch in contents -> update the annotation
                wid.annotation.content.data=wid.content
                self.controller.notify('AnnotationEditEnd', annotation=wid.annotation)
        return True

    def update_model(self, package=None, partial_update=False):
        self.update_annotationtype(None, None)
        return True

    def update_annotationtype(self, annotationtype=None, event=None):
        at=self.chosen_type_selector.get_current_element()
        atlist=self.controller.package.annotationTypes
        # Regenerate the annotation type list.
        types=[ (at, 
                 self.controller.get_title(at), 
                 self.controller.get_element_color(at)) for at in atlist ]
        types.sort(key=lambda a: a[1])

        if at is None:
            at=helper.get_id(atlist, 'annotation')
            if at is None:
                at=helper.get_id(atlist, 'active_bookmark')
        store, i=dialog.generate_list_model(types,
                                            active_element=at)
        self.chosen_type_selector.set_model(store)
        if i is None:
            i = store.get_iter_first()
        if i is not None:
            self.chosen_type_selector.set_active_iter(i)
        return True

    def update_annotation (self, annotation=None, event=None):
        l=[w for w in self.bookmarks if w.annotation == annotation ]
        if l:
            wid=l[0]
        else:
            return True
        if event == 'AnnotationEditEnd':
            # The annotation was updated. Check if an update is necessary
            if wid.begin != annotation.fragment.begin:
                wid.begin=annotation.fragment.begin
            if wid.end != annotation.fragment.end:
                wid.end=annotation.fragment.end
            if wid.content != annotation.content.data:
                wid.content=annotation.content.data
        elif event == 'AnnotationDelete':
            if wid.begin is not None and wid.end is not None:
                # Neither bound is None -> the annotation was deleted
                # (not just invalidated)
                self.remove(wid)
        return True

    def get_matching_bookmark(self, wid):
        """Return the bookmark whose begin or end image is wid.

        Usually used in DND callbacks, with wid=context.get_source_widget()
        """
        l=[ b
            for b in self.bookmarks
            if b.is_widget_in_bookmark(wid) ]
        if l:
            return l[0]
        else:
            return None

    def scroll_to_end(self):
        """Scroll to the bottom of the view.
        """
        adj=self.mainbox.get_parent().get_vadjustment()
        adj.value = adj.upper
        return True

    def scroll_to_bookmark(self, b=None):
        """Ensure that the given bookmark (default: current) is visible.
        """
        if not self.bookmarks:
            return
        b=b or self.get_current_bookmark() or self.bookmarks[0]
        x, y, w, h, depth=b.widget.window.get_geometry()
        parent=self.mainbox.get_parent()
        adj=parent.get_vadjustment()
        pos=adj.value
        height=parent.window.get_geometry()[3]
        if y < pos or y + h > pos + height:
            adj.value = min(y, adj.upper - adj.page_size)
        return True

    def delete_origin_timestamp(self, wid):
        """Delete the timestamp from the widget wid.
        """
        b=self.get_matching_bookmark(wid)
        if b is None:
            return
        if wid == b.begin_widget.image:
            if b.end_widget == b.dropbox:
                # The bookmark should be removed
                self.remove(b)
            else:
                # There was an end.
                b.begin=b.end
                b.end=None
        elif wid == b.end_widget.image:
            b.end=None

    def as_html(self, use_tal=True):
        res=[ """<table border="1">""" ]
        for b in self.bookmarks:
            res.append(b.as_html())
        res.append("</table>")
        return "\n".join(res)
        
    def set_image_size(self, size):
        self.options['snapshot-size']=size
        for b in self.bookmarks:
            b.set_image_size(size)

    def clipboard_get(self, clipboard, selection, info, data):
        if data is None:
            return
        dt=config.data.drag_type
        b=ActiveBookmark(container=self, from_serialisation=data)
        if selection.target in ( dt['STRING'][0][0], dt['text-plain'][0][0]):
            selection.set_text('%s : %s' % (helper.format_time(b.begin), b.content))
        elif selection.target == dt['timestamp'][0][0]:
            selection.set(selection.target, 8, encode_drop_parameters(begin=b.begin, comment=b.content))
        elif selection.target == dt['bookmark'][0][0]:
            selection.set(selection.target, 8, data)
        elif selection.target == dt['annotation'][0][0]:
            if b.annotation is not None:
                selection.set(selection.target, 8, b.annotation.uri.encode('utf8'))
        else:
            del b
            return False
        del b
        return True

    def clipboard_clear(self, clipboard, data):
        del data
        return True

    def copy_current_bookmark(self):
        """Copy the current bookmark into the clipboard.
        """
        c=gtk.clipboard_get()
        cur=self.get_current_bookmark()
        if cur is None:
            return None
        dt=config.data.drag_type
        t=dt['bookmark'] + dt['timestamp'] + dt['text-plain'] + dt['STRING']
        if cur.annotation is not None:
            t=dt['annotation'] + t
        self.targets=t
        c.set_with_data(t, self.clipboard_get, self.clipboard_clear, cur.serialize())
        return cur

    def build_widget(self):
        v=gtk.VBox()
        hb=gtk.HBox()
        hb.set_homogeneous(False)

        def bookmark_current_time(b):
            p=self.controller.player
            if p.status in (p.PlayingStatus, p.PauseStatus):
                v=p.current_position_value
                # Make a snapshot
                self.controller.update_snapshot(v)
                self.append(v)
                return True

        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                # Check if we received the drag from one of our own widget.
                wid=context.get_source_widget()
                b=self.get_matching_bookmark(wid)
                if b is not None:
                    if b.end_widget == b.dropbox:
                        # No end widget, then we have only a begin
                        # time. Thus remove the whole bookmark.
                        b.widget.destroy()
                        self.bookmarks.remove(b)
                        self.refresh()
                    elif wid == b.end_widget.image:
                        # We remove the end widget.
                        b.end=None
                    elif wid == b.begin_widget.image:
                        # Copy the end as new begin, and remove end.
                        b.begin=b.end
                        b.end=None
                return True
            return False

        def do_reorder(b, func):
            self.bookmarks.sort(func)
            self.refresh()
            return True

        def reorder(widget):
            """Display a popup menu proposing various sort options.
            """
            m=gtk.Menu()
            for t, func in (
                (_("Chronological order"), lambda a, b: cmp(a.begin, b.begin)),
                (_("Completeness and chronological order"), lambda a, b: cmp(a.end_widget == a.dropbox,
                                                                             b.end_widget == b.dropbox) or cmp(a.begin, b.begin))
                ):
                i=gtk.MenuItem(t)
                i.connect('activate', do_reorder, func)
                m.append(i)
            m.show_all()
            m.popup(None, widget, None, 0, gtk.get_current_event_time())
            return True

        def do_complete(b, func):
            l=[ b for b in self.bookmarks if b.annotation is None ]
            if isinstance(func, long) or isinstance(func, int):
                for b in l:
                    b.end=b.begin+func
            elif func == 'user':
                d=dialog.entry_dialog(title=_("Bookmark duration"),
                                      text=_("Enter the duration (in ms) to convert bookmarks into annotations"),
                                      default="2000")
                if d is not None:
                    try:
                        d=long(d)
                    except ValueError:
                        return
                    for b in l:
                        b.end=b.begin+d
            elif func == 'coverage':
                begin_list=[ b.begin for b in self.bookmarks ]
                begin_list.sort()
                for b in l:
                    val=[ v for v in begin_list if v > b.begin ]
                    if val:
                        b.end=val[0]
                    else:
                        b.end=self.controller.cached_duration

        def complete(widget):
            m=gtk.Menu()
            for t, func in (
                (_("User-specified duration"), 'user'),
                (_("2s duration"), 2000),
                (_("Complete coverage"), 'coverage'),
                ):
                i=gtk.MenuItem(t)
                i.connect('activate', do_complete, func)
                m.append(i)
            m.show_all()
            m.popup(None, widget, None, 0, gtk.get_current_event_time())
            return True
        
        def remove_current(widget):
            """Remove the current bookmark.
            """
            b=self.get_current_bookmark()
            if b is not None:
                self.remove(b)
            return True

        b=get_small_stock_button(gtk.STOCK_DELETE)
        self.controller.gui.tooltips.set_tip(b, _("Drop a bookmark here to remove it from the list"))
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['timestamp'],
                        gtk.gdk.ACTION_MOVE )
        b.connect('drag-data-received', remove_drag_received)
        b.connect('clicked', remove_current)
        i=gtk.ToolItem()
        i.add(b)
        tb.insert(i, -1)

        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'set-to-now.png') ))
        b=gtk.ToolButton(icon_widget=i)
        b.set_tooltip(self.controller.gui.tooltips, _("Insert a bookmark for the current video time"))
        b.connect('clicked', bookmark_current_time)
        tb.insert(b, -1)

        i=gtk.ToolItem()
        types=[ (at, self.controller.get_title(at), self.controller.get_element_color(at)) for at in self.controller.package.annotationTypes ]
        types.sort(key=lambda a: a[1])

        sel=dialog.list_selector_widget(members=types)
        self.controller.gui.tooltips.set_tip(sel, _("Type of the annotations that will be created"))
        i.add(sel)
        self.chosen_type_selector=sel
        tb.insert(i, -1)

        def scale_snaphots_menu(i):
            def set_scale(i, s):
                self.set_image_size(s)
                return True

            m=gtk.Menu()
            s=config.data.preferences['bookmark-snapshot-width']
            for size, label in (
                (long(.5 * s), _("Smallish")),
                (long(.8 * s), _("Small")),
                (s, _("Normal")),
                (long(1.2 * s), _("Large")),
                (long(1.5 * s), _("Larger")),
                (long(2 * s), _("Huge")),
                ):
                i=gtk.MenuItem(label)
                i.connect('activate', set_scale, size)
                m.append(i)
            m.show_all()
            m.popup(None, None, None, 0, gtk.get_current_event_time())
            return True
        
        for (icon, tip, method) in (
            (gtk.STOCK_REDO, _("Reorder active bookmarks"), reorder),
            (gtk.STOCK_CONVERT, _("Complete incomplete bookmarks"), complete),
            (gtk.STOCK_SAVE, _("Save the current state"), self.save_view),
            (gtk.STOCK_FULLSCREEN, _("Set the size of snaphots"), scale_snaphots_menu),
            ):
            b=get_small_stock_button(icon)
            self.controller.gui.tooltips.set_tip(b, tip)
            b.connect('clicked', method)
            i=gtk.ToolItem()
            i.add(b)
            tb.insert(i, -1)        

        hb.add(tb)
        v.pack_start(hb, expand=False)
        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(self.mainbox)
        self.scrollwindow=sw

        def scroll_on_drag(widget, drag_context, x, y, timestamp):
            adj=widget.get_adjustment()
            v=adj.value
            if y > widget.get_allocation().height / 2:
                # Try to scroll down
                v += max(adj.step_increment, adj.page_increment / 3)
            else:
                v -= max(adj.step_increment, adj.page_increment / 3)
            if v < 0:
                v = 0
            elif v > adj.upper - adj.page_size:
                v=adj.upper - adj.page_size
            adj.value=v
            return True

        sb=sw.get_vscrollbar()
        sb.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                         gtk.DEST_DEFAULT_HIGHLIGHT |
                         gtk.DEST_DEFAULT_ALL,
                         config.data.drag_type['annotation']
                         + config.data.drag_type['timestamp']
                         + config.data.drag_type['annotation-type']
                         ,
                         gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        sb.connect('drag-motion', scroll_on_drag)
        
        def hide_arrow_mark(*p):
            if self.arrow_mark is not None:
                self.arrow_mark.hide()
            return True

        def mainbox_drag_motion(widget, drag_context, x, y, timestamp):
            if self.arrow_mark is None:
                self.arrow_mark=shaped_window_from_xpm(arrow_right_xpm)
            if not self.bookmarks:
                return True
            l=[ b
                for b in self.bookmarks
                if y < b.widget.get_allocation().y + b.widget.get_allocation().height  ]
            if l:
                y=l[0].widget.get_allocation().y - 10
            else:
                a=self.bookmarks[-1].widget.get_allocation()
                y=a.y + a.height
            rx, ry = widget.window.get_origin()
            self.arrow_mark.move(long(rx), long(ry + y))
            self.arrow_mark.show_all()
            actions=drag_context.actions
            is_in_view=drag_context.get_source_widget().is_ancestor(widget)
            if (actions == gtk.gdk.ACTION_MOVE
                or actions == gtk.gdk.ACTION_LINK):
                # Only 1 possible action. Use it.
                drag_context.drag_status(actions, timestamp)
            elif actions == gtk.gdk.ACTION_COPY and is_in_view and config.data.drag_type['annotation'][0][0] in drag_context.targets:
                # We cannot just copy an annotation from our own view,
                # it just can be moved
                drag_context.drag_status(gtk.gdk.ACTION_MOVE, timestamp)
            elif gtk.gdk.ACTION_MOVE & actions and is_in_view:
                # DND from the same view. Force default to move.
                drag_context.drag_status(gtk.gdk.ACTION_MOVE, timestamp)

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            index=None
            if self.arrow_mark is not None:
                self.arrow_mark.hide()
            if widget == self.mainbox:
                l=[ b
                    for b in self.bookmarks
                    if y < b.widget.get_allocation().y + b.widget.get_allocation().height  ]
                if l:
                    index=self.bookmarks.index(l[0])
            if targetType == config.data.target_type['timestamp']:
                data=decode_drop_parameters(selection.data)
                position=long(data['timestamp'])
                b=self.append(position, index)
                if 'comment' in data:
                    b.content=data['comment']
                # If the drag originated from our own widgets, remove it.
                if context.action == gtk.gdk.ACTION_MOVE:
                    self.delete_origin_timestamp(context.get_source_widget())
                return True
            elif targetType == config.data.target_type['annotation-type']:
                # Populate the view with annotation begins
                source=self.controller.package.annotationTypes.get(unicode(selection.data, 'utf8'))
                if source is not None:
                    for a in source.annotations:
                        b=self.append(a.fragment.begin)
                        b.content=self.controller.get_title(a)
                return True
            elif targetType == config.data.target_type['annotation']:
                source=self.controller.package.annotations.get(unicode(selection.data, 'utf8'))
                l=[ b for b in self.bookmarks if b.annotation == source ]
                if l:
                    # We are dropping from the same view. Reorder
                    b=l[0]
                    i=self.bookmarks.index(b)
                    self.bookmarks.remove(b)
                    if i < index:
                        self.bookmarks.insert(index - 1, b)
                    elif index is not None:
                        self.bookmarks.insert(index, b)
                    else:
                        self.bookmarks.append(b)
                    self.refresh()
                else:
                    # Dropping from another view or copying. Create a bookmark
                    b=ActiveBookmark(container=self, annotation=source)
                    if index is None:
                        self.bookmarks.append(b)
                    else:
                        self.bookmarks.insert(index, b)
                    self.refresh()
                return True
            else:
                print "Unknown target type for drop: %d" % targetType
                return False

        self.mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                   gtk.DEST_DEFAULT_HIGHLIGHT |
                                   gtk.DEST_DEFAULT_ALL,
                                   config.data.drag_type['annotation']
                                   + config.data.drag_type['timestamp']
                                   + config.data.drag_type['annotation-type']
                                   ,
                                   gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.mainbox.connect('drag-data-received', mainbox_drag_received)
        self.mainbox.connect('drag-motion', mainbox_drag_motion)
        self.mainbox.connect('drag-end', hide_arrow_mark)
        self.mainbox.connect('drag-leave', hide_arrow_mark)
        self.mainbox.set_spacing(8)

        # Shortcuts
        def mainbox_key_press(widget, event):
            if event.keyval == gtk.keysyms.Delete or event.keyval == gtk.keysyms.BackSpace:
                cur=self.get_current_bookmark()
                if cur is not None:
                    self.remove(cur)
                return True
            elif event.keyval == gtk.keysyms.d and event.state & gtk.gdk.CONTROL_MASK:
                # Control-D: duplicate current bookmark
                self.duplicate_bookmark()
                return True
            elif event.keyval == gtk.keysyms.c and event.state & gtk.gdk.CONTROL_MASK:
                # Copy.
                self.copy_current_bookmark()
                return True
            elif event.keyval == gtk.keysyms.x and event.state & gtk.gdk.CONTROL_MASK:
                # Cut
                cur = self.copy_current_bookmark()
                if cur is not None:
                    self.remove(cur)
                return True
            elif event.keyval == gtk.keysyms.v and event.state & gtk.gdk.CONTROL_MASK:
                # Paste
                c=gtk.clipboard_get()
                def paste_bookmark(cl, sel, data):
                    b=ActiveBookmark(container=self, from_serialisation=sel.data)
                    self.append(b, after_current=True)
                    self.set_current_bookmark(b)
                c.request_contents(config.data.drag_type['bookmark'][0][0], paste_bookmark)
                return True
            return False
        self.mainbox.connect('key-press-event', mainbox_key_press)
        v.add(sw)
        return v

class ActiveBookmark(object):
    """An ActiveBookmark can represent a simple bookmark (i.e. a single
    time, with an optional content) or a completed annotation.

    If the from_serialisation parameter is present, it is used as the source of information.
    
    Else, if the annotation parameter is present, it is used as the source of information.

    Else the begin time is mandatory. It can be associated with an optional content.

    If the end time is None, then the widget is displayed as a simple
    bookmark. DNDing a timestamp over the begin image will set the end
    time.
    """
    def __init__(self, container=None, begin=None, end=None, content=None, annotation=None, from_serialisation=None):
        self.container=container
        self.controller=container.controller

        # If from_serialisation, overwrite all other parameters
        if from_serialisation is not None:
            ident, b, e, c = from_serialisation.split(':')
            if ident != 'None':
                annotation=helper.get_id(self.controller.package.annotations, ident)
            else:
                annotation=None
            begin=long(b)
            if e == 'None':
                end=None
            else:
                end=long(e)
            content=urllib.unquote(c)

        self.annotation=annotation
        if annotation is not None:
            # Set the attributes
            begin=annotation.fragment.begin
            end=annotation.fragment.end
            content=annotation.content.data

        self.is_current=False

        # begin_widget and end_widget are both instances of BookmarkWidget.
        # end_widget may be self.dropbox (if end is not initialized yet)
        self.dropbox=gtk.EventBox()
        self.dropbox.image=None
        self.dropbox.set_size_request(config.data.preferences['bookmark-snapshot-width'], -1)
        self.dropbox.show()
        self.dropbox.set_no_show_all(True)
        self.dropbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                            gtk.DEST_DEFAULT_HIGHLIGHT |
                                            gtk.DEST_DEFAULT_ALL,
                                            config.data.drag_type['timestamp']
                                            + config.data.drag_type['annotation-type'],
                                            gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.dropbox.connect('drag-data-received', self.begin_drag_received)
        self.dropbox.connect('drag-motion', self.bound_drag_motion)

        self.begin_widget=None
        self.end_widget=self.dropbox
        self.widget=self.build_widget()
        self.begin=begin
        self.end=end
        if content is None:
            content=BookmarkWidget.default_comment
        self.content=content
        self.no_image_pixbuf=None

    def set_begin(self, v):
        if v is None:
            v=0
        self.begin_widget.value=v
        self.begin_widget.update()
    def get_begin(self):
        return self.begin_widget.value
    begin=property(get_begin, set_begin)

    def set_end(self, v):
        if v is None:
            if self.end_widget != self.dropbox:
                # Remove the end widget
                self.end_widget.widget.destroy()
                self.end_widget=self.dropbox
                self.dropbox.show()
                self.check_annotation()
            return
        if self.end_widget == self.dropbox:
            self.dropbox.hide()
            # end was not set. We need to create the proper time adjustment
            self.end_widget=BookmarkWidget(controller=self.controller,
                                           timestamp=v,
                                           display_comments=False,
                                           width=self.container.options['snapshot-size'])
            self.end_widget.widget.set_property('can-focus', False)
            parent=self.begin_widget.widget.get_parent()
            parent.pack_start(self.end_widget.widget, expand=False)
            self.end_widget.widget.show_all()

            self.end_widget.image.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                                gtk.DEST_DEFAULT_HIGHLIGHT |
                                                gtk.DEST_DEFAULT_ALL,
                                                config.data.drag_type['timestamp']
                                                + config.data.drag_type['annotation-type'],
                                                gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
            self.end_widget.image.connect('drag-data-received', self.end_drag_received)
            self.end_widget.image.connect('drag-motion', self.bound_drag_motion)
            self.end_widget.image.connect('scroll-event', self.handle_scroll_event, self.get_end, self.set_end, lambda v: v > self.begin)
            self.end_widget.image.connect('key-press-event', self.timestamp_key_press, 'end')
            
            def end_image_button_press_handler(widget, event):
                if not self.is_current:
                    self.container.set_current_bookmark(self)
                return False
            self.end_widget.image.connect('button-press-event', end_image_button_press_handler)

            def extend_end_image_menu(menu, element):
                for (label, action) in (
                    (_("Remove end timestamp"), lambda i: self.set_end(None)), 
                    ):
                    i=gtk.MenuItem(label)
                    i.connect('activate', action)
                    menu.append(i)
                return
            self.end_widget.image.extend_popup_menu=extend_end_image_menu

            def focus_bookmark(widget, event):
                self.container.set_current_bookmark(self)
                return False
            self.end_widget.image.connect('focus-in-event', focus_bookmark)
        else:
            self.end_widget.value=v
            self.end_widget.update()
        self.check_annotation()
    def get_end(self):
        if self.end_widget == self.dropbox:
            return None
        else:
            return self.end_widget.value
    end=property(get_end, set_end)

    def set_current(self, is_current=True):
        """Display the 'current' marker (highlight frame) around the widget.
        """
        if is_current == self.is_current:
            # Nothing to do
            return
        if is_current:
            self.frame.drag_highlight()
            if (not self.begin_widget.comment_entry.props.has_focus
                and not self.begin_widget.image.props.has_focus):
                self.begin_widget.image.grab_focus()
            self.container.scroll_to_bookmark(self)
        else:
            self.frame.drag_unhighlight()
        self.is_current=is_current

    def serialize(self):
        """Return a serialized form of the bookmark.

        It is used when saving the view.
        """
        # Serialisation format: annotationid:begin:end:content where
        # annotationid and end may be "None" and content is
        # url-encoded
        if self.annotation is None:
            ident='None'
        else:
            ident=self.annotation.id
        return ":".join( (ident,
                          str(self.begin),
                          str(self.end),
                          urllib.quote(self.content) ) )

    def as_html(self):
        if self.annotation is not None:
            res="""<tr tal:define="a package/annotations/%s">
                        <td><a tal:attributes="href a/player_url"><img width="120" tal:attributes="src a/snapshot_url" alt="" border="0" /><br /><em tal:content="a/fragment/begin/formatted">ts</em></a></td>
                        <td tal:attributes="style string:background-color:${a/color | }" tal:content="a/content/data">Content</td>
                        <td><a tal:attributes="href a/fragment/end/player_url"><img width="120" tal:attributes="src a/fragment/end/snapshot_url" alt="" border="0" /><br /><em tal:content="a/fragment/end/formatted">ts</em></a></td>
                   </tr>""" % self.annotation.id
        else:
            res="""<tr><td>%s</td><td>%s</td><td>&nbsp;</td></tr>""" % (self.begin_widget.image.as_html(),
                                                                        self.content)
        return res

    def bound_drag_motion(self, widget, drag_context, x, y, timestamp):
        # Force the correct default action.
        actions=drag_context.actions
        is_in_view=drag_context.get_source_widget().is_ancestor(self.container.mainbox)
        if (actions == gtk.gdk.ACTION_MOVE
            or actions == gtk.gdk.ACTION_LINK
            or actions == gtk.gdk.ACTION_COPY):
            # Only 1 possible action. Use it.
            drag_context.drag_status(actions, timestamp)
        elif gtk.gdk.ACTION_MOVE & actions and is_in_view:
            # DND from the same view. Force default to move.
            drag_context.drag_status(gtk.gdk.ACTION_MOVE, timestamp)
        
    def begin_drag_received(self, widget, context, x, y, selection, targetType, time):
        if self.is_widget_in_bookmark(context.get_source_widget()):
            return False
        if targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.data)
            e=long(data['timestamp'])
            if self.end is None:
                if e < self.begin:
                    # Invert begin and end.
                    self.begin, self.end = e, self.begin
                else:
                    self.end=e
            else:
                # Save a copy of the deleted timestamp next to the current bookmark
                i=self.container.bookmarks.index(self)
                self.container.append(self.begin, index=i + 1)
                # Reset the begin time.
                if e > self.end:
                    # Invert new begin and end
                    self.begin, self.end = self.end, e
                else:
                    self.begin=e

            # If the drag originated from our own widgets, remove it.
            # If the drop was done from within our view, then
            # delete the origin widget.
            if context.action == gtk.gdk.ACTION_MOVE:
                self.container.delete_origin_timestamp(context.get_source_widget())
            # Set the current status
            self.container.set_current_bookmark(self)
            return True
        elif targetType == config.data.target_type['annotation-type']:
            source=self.controller.package.annotationTypes.get(unicode(selection.data, 'utf8'))
            if source is not None:
                self.transtype(source)
            return True
        return False

    def end_drag_received(self, widget, context, x, y, selection, targetType, time):
        if self.is_widget_in_bookmark(context.get_source_widget()):
            return False
        self.container.set_current_bookmark(self)
        if targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.data)
            e=long(data['timestamp'])
            if self.end is not None:
                # Save a copy of the deleted timestamp next to the current bookmark
                i=self.container.bookmarks.index(self)
                self.container.append(self.end, index=i + 1)
            if e < self.begin:
                # Invert begin and end.
                self.begin, self.end = e, self.begin
            else:
                self.end=e
            # If the drag originated from our own widgets, remove it.
            # If the drop was done from within our view, then
            # delete the origin widget.
            if context.action == gtk.gdk.ACTION_MOVE:
                self.container.delete_origin_timestamp(context.get_source_widget())
            self.container.set_current_bookmark(self)
            return True
        elif targetType == config.data.target_type['annotation-type']:
            source=self.controller.package.annotationTypes.get(unicode(selection.data, 'utf8'))
            if source is not None:
                self.transtype(source)
            return True
        return False

    def transtype(self, at):
        if self.annotation is not None:
            # There was an existing annotation. Transtype it to the
            # new type.
            a=self.controller.transmute_annotation(self.annotation, at, delete=True, notify=True)
            if a is None:
                return True
            self.annotation=a
            # Update the textview color
            col=self.controller.get_element_color(self.annotation)
            if col is not None:
                color=name2color(col)
                self.begin_widget.comment_entry.modify_base(gtk.STATE_NORMAL, color)
        return True

    def set_content(self, c):
        if c is None:
            c=''
        self.begin_widget.comment=c
        self.begin_widget.update()
    def get_content(self):
        return self.begin_widget.comment
    content=property(get_content, set_content)

    def set_image_size(self, s):
        self.begin_widget.image.set_width(s)
        if self.end_widget != self.dropbox:
            self.end_widget.image.set_width(s)

    def check_annotation(self):
        if self.end is None:
            if self.annotation is not None:
                # Remove the annotation
                self.controller.delete_element(self.annotation)
                self.annotation=None
                self.set_frame_attributes()
        else:
            # Both times are valid.
            if self.annotation is None:
                # Create the annotation
                id_=self.controller.package._idgenerator.get_id(Annotation)
                # Check the type
                at=self.container.type
                if at is None:
                    # First try the Text-annotation type. If it
                    # does not exist, create an appropriate type.
                    at=helper.get_id(self.controller.package.annotationTypes, 'annotation')
                    if at is None:
                        at=helper.get_id(self.controller.package.annotationTypes, 'active_bookmark')
                    if at is None:
                        # Create a new 'active_bookmark' type
                        schema=helper.get_id(self.controller.package.schemas, 'simple-text')
                        if schema is None and self.controller.package.schemas:
                            # Fallback on the first schema
                            schema=self.controller.package.schemas[0]
                        if schema is None:
                            self.log(_("Error: cannot find an appropriate schema to create the Active-bookmark type."))
                            return True
                        at=schema.createAnnotationType(ident='active_bookmark')
                        at.author=config.data.userid
                        at.date=self.controller.get_timestamp()
                        at.title=_("Active bookmark")
                        at.mimetype='text/plain'
                        at.setMetaData(config.data.namespace, 'color', self.controller.package._color_palette.next())
                        at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
                        schema.annotationTypes.append(at)
                        self.controller.notify('AnnotationTypeCreate', annotationtype=at)
                    if at is None:
                        return True
                el=self.controller.package.createAnnotation(
                    ident=id_,
                    type=at,
                    author=config.data.userid,
                    date=self.controller.get_timestamp(),
                    fragment=MillisecondFragment(begin=long(self.begin),
                                                 end=long(self.end)))
                el.content.data=self.content
                self.controller.package.annotations.append(el)
                self.annotation=el
                self.controller.notify('AnnotationCreate', annotation=el, immediate=True)

                self.set_frame_attributes()
            else:
                # Update the annotation
                self.annotation.fragment.begin=self.begin
                self.annotation.fragment.end=self.end
                self.controller.notify('AnnotationEditEnd', annotation=self.annotation)
        return True

    def set_frame_attributes(self):
        if self.annotation is not None:
            # Add a validate button to the frame
            def handle_ok(b):
                self.container.remove(self)
                return True
            b=get_pixmap_button('small_ok.png', handle_ok)
            b.set_relief(gtk.RELIEF_NONE)
            self.controller.gui.tooltips.set_tip(b, _("Validate the annotation"))
            def set_current(widget, event):
                self.container.set_current_bookmark(self)
                return True
            b.connect('focus-in-event', set_current)
            self.frame.set_label_widget(b)
            b.set_property('can-focus', False)
            b.show_all()
            # Update the textview color
            col=self.controller.get_element_color(self.annotation)
            if col is not None:
                color=name2color(col)
                self.begin_widget.comment_entry.modify_base(gtk.STATE_NORMAL, color)
        else:
            # Reset the color and the label widget
            l=self.frame.get_label_widget()
            if l is not None:
                l.destroy()
            # Reset the textview color
            self.begin_widget.comment_entry.modify_base(gtk.STATE_NORMAL, self.default_background_color)

    def grab_focus(self, *p):
        """Set the focus on the comment edition widget.
        """
        self.begin_widget.comment_entry.grab_focus()
        return True

    def handle_scroll_event(self, button, event, get_value, set_value, check_value):
        # Handle scroll actions
        if not (event.state & gtk.gdk.CONTROL_MASK):
            return False
        if event.direction == gtk.gdk.SCROLL_DOWN:
            incr=-config.data.preferences['scroll-increment']
        elif event.direction == gtk.gdk.SCROLL_UP:
            incr=config.data.preferences['scroll-increment']

        v=get_value()
        v += incr
        if check_value(v):
            set_value(v)
        return True

    def is_widget_in_bookmark(self, widget):
        """Check if the widget is in the bookmark.

        It checks the images, which are the source for DND.
        """
        return (widget == self.begin_widget.image or  widget == self.end_widget.image)

    def delete_timestamp(self, position):
        """Delete a timestamp.

        position is either 'begin' or 'end'.
        """
        if position == 'begin':
            self.controller.notify('BookmarkUnhighlight', timestamp=self.begin, immediate=True)
            if self.end is None:
                self.container.remove(self)
            else:
                self.begin = self.end
                self.end = None
        elif position == 'end':
            self.controller.notify('BookmarkUnhighlight', timestamp=self.end, immediate=True)
            self.end = None

    def timestamp_key_press(self, widget, event, source):
        def move_boomark(index):
            """Move the bookmark at the given position.

            -1  is for end of the list
            """
            self.container.bookmarks.remove(self)
            if index < 0:
                self.container.bookmarks.append(self)
            else:
                self.container.bookmarks.insert(index, self)
            self.container.refresh()
            self.container.set_current_bookmark(self)
            self.begin_widget.image.grab_focus()
            self.container.scroll_to_bookmark(self)
            return True

        def move_or_navigate(index, event):
            if event.state & gtk.gdk.SHIFT_MASK:
                # Shift-up/down/home/end: move the bookmark
                move_boomark(index)
            else:
                # Set the current bookmark
                self.container.set_current_bookmark(self.container.bookmarks[index])

        if event.keyval == gtk.keysyms.Delete or event.keyval == gtk.keysyms.BackSpace:
            self.delete_timestamp(source)
            return True
        elif event.keyval == gtk.keysyms.d and event.state & gtk.gdk.CONTROL_MASK:
            # Control-D: duplicate current bookmark
            self.container.duplicate_bookmark()
            return True
        elif event.keyval == gtk.keysyms.Up or event.keyval == gtk.keysyms.Down:
            # Up/Down navigation. It is normally handled by Gtk but
            # the default behaviour has a corner case which makes it
            # impractical in this case (going from a bookmark to an
            # annotation selects the annotation content, and prevents
            # further navigation). Hence we handle it manually.
            index=self.container.bookmarks.index(self)
            if event.keyval == gtk.keysyms.Up:
                if index == 0:
                    return True
                index -= 1
            else:
                index += 1
                if index >= len(self.container.bookmarks):
                    return True
            move_or_navigate(index, event)
            return True
        elif event.keyval == gtk.keysyms.Home:
            move_or_navigate(0, event)
        elif event.keyval == gtk.keysyms.End:
            move_or_navigate(-1, event)
        return False

    def build_widget(self):

        f=gtk.Frame()

        box=gtk.HBox()

        self.begin_widget=BookmarkWidget(self.controller,
                                         display_comments=True,
                                         width=self.container.options['snapshot-size'])
        self.begin_widget.image.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                              gtk.DEST_DEFAULT_HIGHLIGHT |
                                              gtk.DEST_DEFAULT_ALL,
                                              config.data.drag_type['timestamp']
                                              + config.data.drag_type['annotation-type'],
                                              gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE )
        self.begin_widget.image.connect('drag-data-received', self.begin_drag_received)
        self.begin_widget.image.connect('drag-motion', self.bound_drag_motion)
        self.begin_widget.image.connect('scroll-event', self.handle_scroll_event, self.get_begin, self.set_begin, lambda v: self.end is None or v < self.end)

        self.begin_widget.comment_entry.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                              gtk.DEST_DEFAULT_HIGHLIGHT |
                                              gtk.DEST_DEFAULT_ALL,
                                              config.data.drag_type['timestamp']
                                              + config.data.drag_type['annotation-type'],
                                              gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE )
        self.begin_widget.comment_entry.connect('drag-data-received', self.begin_drag_received)
        self.begin_widget.image.connect('key-press-event', self.timestamp_key_press, 'begin')

        def focus_bookmark(widget, event):
            self.container.set_current_bookmark(self)
            return False
        self.begin_widget.comment_entry.connect('focus-in-event', focus_bookmark)
        self.begin_widget.image.connect('focus-in-event', focus_bookmark)

        def extend_image_menu(menu, element):
            l=[
                (_("Duplicate bookmark"), lambda i: self.container.duplicate_bookmark(self)),
                (_("Remove bookmark"), lambda i: self.container.remove(self)),
                ]
            def remove_begin(i):
                self.set_begin(self.end)
                self.set_end(None)
                return True

            if self.end is not None:
                l.append(
                    (_("Remove begin timestamp"), remove_begin)
                    )
            for (label, action) in l:
                i=gtk.MenuItem(label)
                i.connect('activate', action)
                menu.append(i)
            if self.annotation is None:
                i=gtk.MenuItem(_("Complete bookmark"))
                i.connect('activate', lambda i: self.set_end(self.begin + 2000))
                menu.append(i)
            else:
                i=gtk.MenuItem(_("Change type to"))
                sm=gtk.Menu()
                i.set_submenu(sm)
                menu.append(i)
                l=[ (t, self.controller.get_title(t)) 
                    for t in self.controller.package.annotationTypes
                    if t != self.annotation.type ]
                l.sort(key=lambda a: a[1])
                for (typ, title) in l:
                    i=gtk.MenuItem(title, use_underline=False)
                    i.connect('activate', (lambda i, t: self.transtype(t)), typ)
                    sm.append(i)
            return
        self.begin_widget.image.extend_popup_menu=extend_image_menu

        self.begin_widget.comment_entry.set_accepts_tab(False)

        box.pack_start(self.begin_widget.widget, expand=True)
        box.pack_start(self.end_widget, expand=False)
        f.add(box)
        f.show_all()

        self.frame=f

        # Memorize the default textview color.
        self.default_background_color=self.begin_widget.comment_entry.get_style().base[gtk.STATE_NORMAL]

        #if self.annotation is not None:
        self.set_frame_attributes()

        # Add a padding widget so that the frame fits the displayed elements
        #padding=gtk.HBox()
        #padding.pack_start(f, expand=False)

        # Use an Event box to be able to drag the frame representing an annotation
        eb=gtk.EventBox()
        eb.add(f)

        def drag_sent(widget, context, selection, targetType, eventTime):
            """Handle the drag-sent event.
            """
            if targetType == config.data.target_type['annotation']:
                if self.annotation is None:
                    return False
                else:
                    selection.set(selection.target, 8, self.annotation.uri.encode('utf8'))
            elif targetType == config.data.target_type['uri-list']:
                if self.annotation is None:
                    return False
                c=self.controller.build_context(here=self.annotation)
                uri=c.evaluateValue('here/absolute_url')
                selection.set(selection.target, 8, uri.encode('utf8'))
            elif (targetType == config.data.target_type['text-plain']
                  or targetType == config.data.target_type['TEXT']
                  or targetType == config.data.target_type['STRING']):
                # Put the timecode + content
                selection.set(selection.target, 8, ("%s : %s" % (helper.format_time(self.begin),
                                                                 self.content)).encode('utf8'))
            elif targetType == config.data.target_type['timestamp']:
                selection.set(selection.target, 8, encode_drop_parameters(timestamp=self.begin))
            else:
                return False
            return True

        eb.drag_source_set(gtk.gdk.BUTTON1_MASK,
                           config.data.drag_type['annotation']
                           + config.data.drag_type['uri-list']
                           + config.data.drag_type['text-plain']
                           + config.data.drag_type['TEXT']
                           + config.data.drag_type['STRING']
                           + config.data.drag_type['timestamp']
                           + config.data.drag_type['tag']
                           ,
                           gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        eb.connect('drag-data-get', drag_sent)

        def _drag_begin(widget, context):
            w=gtk.Window(gtk.WINDOW_POPUP)
            w.set_decorated(False)

            style=w.get_style().copy()
            black=gtk.gdk.color_parse('black')
            white=gtk.gdk.color_parse('white')

            for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                          gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                          gtk.STATE_PRELIGHT):
                style.bg[state]=black
                style.fg[state]=white
                style.text[state]=white
                #style.base[state]=white
            w.set_style(style)

            v=gtk.VBox()
            v.set_style(style)
            h=gtk.HBox()
            h.set_style(style)
            begin=gtk.Image()
            h.pack_start(begin, expand=False)
            padding=gtk.HBox()
            # Padding
            h.pack_start(padding, expand=True)
            end=gtk.Image()
            h.pack_start(end, expand=False)
            v.pack_start(h, expand=False)
            l=gtk.Label()
            l.set_ellipsize(pango.ELLIPSIZE_END)
            l.set_style(style)
            v.pack_start(l, expand=False)

            def set_cursor(wid, t=None):
                if t is None:
                    t=self.annotation or self.begin
                cache=self.controller.package.imagecache
                if self.no_image_pixbuf is None:
                    self.no_image_pixbuf=png_to_pixbuf(cache.not_yet_available_image, width=config.data.preferences['drag-snapshot-width'])
                if not t == w._current:
                    if isinstance(t, long) or isinstance(t, int):
                        if cache.is_initialized(t, epsilon=config.data.preferences['bookmark-snapshot-precision']):
                            begin.set_from_pixbuf(png_to_pixbuf (cache.get(t, epsilon=config.data.preferences['bookmark-snapshot-precision']), width=config.data.preferences['drag-snapshot-width']))
                        elif begin.get_pixbuf() != self.no_image_pixbuf:
                            begin.set_from_pixbuf(self.no_image_pixbuf)
                        end.hide()
                        padding.hide()
                        l.set_text(helper.format_time(t))
                    elif isinstance(t, Annotation):
                        # It can be an annotation
                        begin.set_from_pixbuf(png_to_pixbuf (cache.get(t.fragment.begin), width=config.data.preferences['drag-snapshot-width']))
                        end.set_from_pixbuf(png_to_pixbuf (cache.get(t.fragment.end), width=config.data.preferences['drag-snapshot-width']))
                        end.show()
                        padding.show()
                        l.set_text(self.controller.get_title(t))
                wid._current=t
                return True

            w.add(v)
            w.show_all()
            w._current=None
            w.set_cursor = set_cursor.__get__(w)
            w.set_cursor()
            w.set_size_request(long(2.5 * config.data.preferences['drag-snapshot-width']), -1)
            widget._icon=w
            context.set_icon_widget(w, 0, 0)
            return True

        def _drag_end(widget, context):
            widget._icon.destroy()
            widget._icon=None
            return True

        def _drag_motion(widget, drag_context, x, y, timestamp):
            w=drag_context.get_source_widget()
            try:
                w._icon.set_cursor()
            except AttributeError:
                pass
            return True

        eb.connect('drag-begin', _drag_begin)
        eb.connect('drag-end', _drag_end)
        eb.connect('drag-motion', _drag_motion)

        def _button_press(widget, event):
            if event.button == 3 and event.type == gtk.gdk.BUTTON_PRESS:
                if self.annotation is not None:
                    menu=advene.gui.popup.Menu(self.annotation, controller=self.controller)
                    menu.popup()
                    return True
            return False
        eb.connect('button-press-event', _button_press)

        return eb
