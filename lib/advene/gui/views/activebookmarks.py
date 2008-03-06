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

# Advene part
import advene.core.config as config
from advene.gui.util import dialog, get_small_stock_button, get_pixmap_button, name2color
from advene.gui.views import AdhocView
from advene.gui.views.bookmarks import BookmarkWidget
from advene.model.annotation import Annotation
from advene.model.fragment import MillisecondFragment
import advene.util.helper as helper

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
            )
        self.options={
            'snapshot_width': 60,
            }
        self.controller=controller
        # self.bookmarks is a list of ActiveBookmark objects
        self.bookmarks=[]
        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        # FIXME: think about serialization...
        #h=[ long(v) for (n, v) in arg if n == 'timestamp' ]
        #if h:
        #    self.history=h
        #for n, v in arg:
        #    if n == 'comment':
        #       t, c = v.split(':', 1)
        #       self.comments[long(t)]=c
        self.mainbox=gtk.VBox()
        self.widget=self.build_widget()
        self.type = type
        self.refresh()

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
        # FIXME: save arguments
        #return self.options, ([ ('timestamp', t) for t in self.history ]
        return self.options, []

    def refresh(self, *p):
        self.mainbox.foreach(self.mainbox.remove)
        for w in self.bookmarks:
            self.mainbox.pack_start(w.widget, expand=False)
        self.mainbox.show_all()
        return True

    def remove(self, w):
        """Remove the given widget from mainbox.
        """
        self.bookmarks.remove(w)
        w.widget.destroy()
        return True

    def clear(self, *p):
        del self.bookmarks[:]
        self.mainbox.foreach(self.mainbox.remove)
        return True

    def append(self, t):
        b=ActiveBookmark(container=self, begin=t, end=None, content=None, type=self.type)
        self.bookmarks.append(b)
        self.mainbox.pack_start(b.widget, expand=False)
        b.widget.show_all()
        return True

    def check_contents(self, *p):
        """Check that annotation contents are in sync.
        """
        for wid in self.bookmarks:
            if wid.annotation is not None and wid.content != wid.annotation.content.data:
                # Mismatch in contents -> update the annotation
                wid.annotation.content.data=wid.content
                self.controller.notify('AnnotationEditEnd', annotation=wid.annotation)
        return True
    
    def update_annotationtype(self, annotationtype=None, event=None):
        # Regenerate the annotation type list.
        types=[ (at, self.controller.get_title(at)) for at in self.controller.package.annotationTypes ]
        types.sort(key=lambda a: a[1])
        store, i=dialog.generate_list_model(types,
                                            active_element=self.type)
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
            for w in (b.begin_widget.image, (b.end_widget is not None and b.end_widget.image))
            if w == wid ]
        if l:
            return l[0]
        else:
            return None

    def delete_origin_timestamp(self, wid):
        """Delete the timestamp from the widget wid.
        """
        b=self.get_matching_bookmark(wid)
        if b is None:
            return
        if wid == b.begin_widget.image:
            if b.end_widget is None:
                # The bookmark should be removed
                self.remove(b)
            else:
                # There was an end.
                b.begin=b.end
                b.end=None
        elif wid == b.end_widget.image:
            b.end=None

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
                    if b.end_widget is None:
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
                (_("Completeness and chronological order"), lambda a, b: cmp(a.end_widget is None, 
                                                                             b.end_widget is None) or cmp(a.begin, b.begin)) 
                ):
                i=gtk.MenuItem(t)
                i.connect('activate', do_reorder, func)
                m.append(i)
            m.show_all()
            m.popup(None, widget, None, 0, gtk.get_current_event_time())
            return True

        b=get_small_stock_button(gtk.STOCK_DELETE)
        self.controller.gui.tooltips.set_tip(b, _("Drop a bookmark here to remove it from the list"))
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['timestamp'], 
                        gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY )
        b.connect("drag_data_received", remove_drag_received)
        i=gtk.ToolItem()
        i.add(b)
        tb.insert(i, -1)

        i=gtk.Image()
        i.set_from_file(config.data.advenefile( ( 'pixmaps', 'set-to-now.png') ))
        b=gtk.ToolButton(icon_widget=i)
        b.set_tooltip(self.controller.gui.tooltips, _("Insert a bookmark for the current video time"))
        b.connect("clicked", bookmark_current_time)
        tb.insert(b, -1)

        i=gtk.ToolItem()
        types=[ (at, self.controller.get_title(at)) for at in self.controller.package.annotationTypes ]
        types.sort(key=lambda a: a[1])
        sel=dialog.list_selector_widget(members=types)
        self.controller.gui.tooltips.set_tip(sel, _("Type of the annotations that will be created"))
        i.add(sel)
        self.chosen_type_selector=sel
        tb.insert(i, -1)

        b=get_small_stock_button(gtk.STOCK_REDO)
        self.controller.gui.tooltips.set_tip(b, _("Reorder active bookmarks"))
        b.connect("clicked", reorder)
        i=gtk.ToolItem()
        i.add(b)
        tb.insert(i, -1)

        hb.add(tb)
        v.pack_start(hb, expand=False)
        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add_with_viewport(self.mainbox)
        self.scrollwindow=sw

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                position=long(selection.data)
                self.append(position)
                # If the drag originated from our own widgets, remove it.
                self.delete_origin_timestamp(context.get_source_widget())
                return True
            elif targetType == config.data.target_type['annotation-type']:
                # Populate the view with annotation begins
                source=self.controller.package.annotationTypes.get(unicode(selection.data, 'utf8'))
                if source is not None:
                    for a in source.annotations:
                        self.append(a.fragment.begin)
                return True
            else:
                print "Unknown target type for drop: %d" % targetType
                return False

        self.mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                   gtk.DEST_DEFAULT_HIGHLIGHT |
                                   gtk.DEST_DEFAULT_ALL,
                                   config.data.drag_type['timestamp']
                                   + config.data.drag_type['annotation-type']
                                   ,
                                   gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
        self.mainbox.connect("drag_data_received", mainbox_drag_received)
        v.add(sw)
        return v

class ActiveBookmark(object):
    """An ActiveBookmark can represent a simple bookmark (i.e. a single
    time, with an optional content) or a completed annotation.

    The begin time is mandatory. It can be associated with an optional content.

    If the end time is None, then the widget is displayed as a simple
    bookmark. DNDing a timestamp over the begin image will set the end
    time.
    
    Once the end time is set, both times are displayed through a
    TimeAdjustment widget, so that they are editable.
    """
    def __init__(self, container=None, begin=None, end=None, content=None, type=None):
        self.container=container
        self.controller=container.controller
        self.annotation=None
        self.type=type
        # begin_widget and end_widget are both instances of BookmarkWidget.
        # end_widget may be None (if end is not initialized yet)
        self.begin_widget=None
        self.end_widget=None
        self.widget=self.build_widget()
        self.begin=begin
        self.end=end
        if content is None:
            content=BookmarkWidget.default_comment
        self.content=content

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
            if self.end_widget is not None:
                # Remove the end widget
                self.end_widget.widget.destroy()
                self.end_widget=None
                self.check_annotation()
            return
        if self.end_widget is None:
            # end was not set. We need to create the proper time adjustment
            self.end_widget=BookmarkWidget(controller=self.controller,
                                           timestamp=v,
                                           display_comments=False)
            parent=self.begin_widget.widget.get_parent()
            parent.pack_start(self.end_widget.widget, expand=False)
            self.end_widget.widget.show_all()

            def end_drag_received(widget, context, x, y, selection, targetType, time):
                if targetType == config.data.target_type['timestamp']:
                    e=long(selection.data)
                    if e < self.begin:
                        # Invert begin and end.
                        self.begin, self.end = e, self.begin
                    else:
                        self.end=e
                    # If the drag originated from our own widgets, remove it.
                    # If the drop was done from within our view, then
                    # delete the origin widget.
                    self.container.delete_origin_timestamp(context.get_source_widget())
                    return True
                return False
            self.end_widget.image.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                                gtk.DEST_DEFAULT_HIGHLIGHT |
                                                gtk.DEST_DEFAULT_ALL,
                                                config.data.drag_type['timestamp'],
                                                gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE)
            self.end_widget.image.connect("drag_data_received", end_drag_received)
        else:
            self.end_widget.value=v
            self.end_widget.update()
        self.check_annotation()
    def get_end(self):
        if self.end_widget is None:
            return None
        else:
            return self.end_widget.value
    end=property(get_end, set_end)

    def set_content(self, c):
        if c is None:
            c=''
        self.begin_widget.comment=c
        self.begin_widget.update()
    def get_content(self):
        return self.begin_widget.comment
    content=property(get_content, set_content)
    
    def check_annotation(self):
        if self.end is None:
            if self.annotation is not None:
                # Remove the annotation
                self.controller.delete_element(self.annotation)
                self.annotation=None
                l=self.frame.get_label_widget()
                if l is not None:
                    l.destroy()
                # Reset the textview color
                self.begin_widget.comment_entry.modify_base(gtk.STATE_NORMAL, self.default_background_color)
        else:
            # Both times are valid.
            if self.annotation is None:
                # Create the annotation
                id_=self.controller.package._idgenerator.get_id(Annotation)
                # Check the type
                if self.type is None:
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
                    self.type=at
                el=self.controller.package.createAnnotation(
                    ident=id_,
                    type=self.type,
                    author=config.data.userid,
                    date=self.controller.get_timestamp(),
                    fragment=MillisecondFragment(begin=long(self.begin),
                                                 end=long(self.end)))
                el.content.data=self.content
                self.controller.package.annotations.append(el)
                self.annotation=el
                self.controller.notify('AnnotationCreate', annotation=el, immediate=True)
                # Add a validate button to the frame
                def handle_ok(b):
                    self.container.remove(self)
                    return True
                b=get_pixmap_button('small_ok.png', handle_ok)
                b.set_relief(gtk.RELIEF_NONE)
                self.controller.gui.tooltips.set_tip(b, _("Validate the annotation"))
                self.frame.set_label_widget(b)
                b.show_all()
                # Update the textview color
                col=self.controller.get_element_color(el)
                if col is not None:
                    color=name2color(col)
                    self.begin_widget.comment_entry.modify_base(gtk.STATE_NORMAL, color)
            else:
                # Update the annotation
                self.annotation.fragment.begin=self.begin
                self.annotation.fragment.end=self.end
                self.controller.notify('AnnotationEditEnd', annotation=self.annotation)
        return True

    def build_widget(self):

        f=gtk.Frame()

        box=gtk.HBox()

        def begin_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                e=long(selection.data)
                if self.end is None:
                    if e < self.begin:
                        # Invert begin and end.
                        self.begin, self.end = e, self.begin
                    else:
                        self.end=e
                else:
                    # Reset the begin time.
                    if e > self.end:
                        # Invert new begin and end
                        self.begin, self.end = self.end, e
                    else:
                        self.begin=e

                # If the drag originated from our own widgets, remove it.
                # If the drop was done from within our view, then
                # delete the origin widget.
                self.container.delete_origin_timestamp(context.get_source_widget())
                return True
            return False

        self.begin_widget=BookmarkWidget(self.controller, display_comments=True)
        self.begin_widget.image.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                              gtk.DEST_DEFAULT_HIGHLIGHT |
                                              gtk.DEST_DEFAULT_ALL,
                                              config.data.drag_type['timestamp'],
                                              gtk.gdk.ACTION_COPY | gtk.gdk.ACTION_MOVE )
        self.begin_widget.image.connect("drag_data_received", begin_drag_received)

        box.pack_start(self.begin_widget.widget, expand=False)
        f.add(box)
        f.show_all()

        self.frame=f

        # Add a padding widget so that the frame fits the displayed elements
        padding=gtk.HBox()
        padding.pack_start(f, expand=False)

        # Memorize the default textview color.
        self.default_background_color=self.begin_widget.comment_entry.get_style().base[gtk.STATE_NORMAL]

        return padding
