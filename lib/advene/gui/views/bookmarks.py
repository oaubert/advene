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
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Module displaying time bookmarks (for navigation history for instance)."""

# Advene part
import advene.core.config as config
import advene.util.helper as helper
from advene.gui.util import image_from_position, get_small_stock_button, dialog, png_to_pixbuf
from advene.gui.views import AdhocView
import advene.util.importer
from gettext import gettext as _

import gtk

name="Bookmarks view plugin"

def register(controller):
    controller.register_viewclass(Bookmarks)

class HistoryImporter(advene.util.importer.GenericImporter):
    """History importer.
    """
    def __init__(self, elements=None, comments=None, duration=2000, **kw):
        super(HistoryImporter, self).__init__(**kw)
        self.elements=elements
        self.comments=comments
        self.duration=duration
        self.name = _("Bookmarks importer")

    def iterator(self):
        for b in self.elements:
            if self.comments is not None and b in self.comments:
                content=self.comments[b]
            else:
                content="Bookmark %s" % helper.format_time(b)
            yield {
                'begin': b,
                'end': b + self.duration,
                'content': content,
                'notify': True,
                }

    def process_file(self, filename):
        if filename != 'history':
            return None
        if self.package is None:
            self.init_package()
        self.convert(self.iterator())
        return self.package

class Bookmarks(AdhocView):
    view_name = _("Bookmarks")
    view_id = 'bookmarks'
    tooltip= _("Bookmark timecodes with their corresponding screenshots")
    def __init__(self, controller=None, parameters=None,
                 history=None, vertical=True, ordered=False, closable=True, display_comments=True):
        super(Bookmarks, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            #(_("Save view"), self.save_view),
            (_("Clear"), self.clear),
            #(_("Convert to annotations"), self.convert_to_annotations),
            )
        self.options={
            'ordered': ordered,
            'snapshot_width': 100,
            'vertical': vertical,
            }
        self.controller=controller
        self.history=history
        self.display_comments=display_comments

        if history is None:
            self.history=[]
        self.comments={}

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        h=[ long(v) for (n, v) in arg if n == 'timestamp' ]
        if h:
            self.history=h

        for n, v in arg:
            if n == 'comment':
                t, c = v.split(':', 1)
                self.comments[long(t)]=c

        self.closable=closable
        self.mainbox=None
        self.scrollwindow=None
        self.widget=self.build_widget()
        self.refresh()

    def get_save_arguments(self):
        return self.options, ([ ('timestamp', t) for t in self.history ]
                              + [ ('comment', '%d:%s' % (t, c)) for (t, c) in self.comments.iteritems() ])

    def close(self, *p):
        if self.closable:
            AdhocView.close(self)
            return True
        else:
            return False

    def register_callback (self, controller=None):
        self.changerule=controller.event_handler.internal_rule (event="MediaChange",
                                                                method=self.clear)
        return True

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.changerule, type_="internal")
        return True

    def convert_to_annotations(self, *p):
        """Convert bookmarks to annotations with a fixed duration.
        """
        at=self.controller.gui.ask_for_annotation_type(text=_("Select the annotation type to generate"), create=True)

        if at is None:
            return True

        d=dialog.entry_dialog(title=_("Choose a duration"),
                              text=_("Enter the standard duration (in ms) of created annotations."),
                              default="2000")
        if d is None:
            return True

        try:
            d=long(d)
        except ValueError:
            # Use a default value
            d=2000
        ti=HistoryImporter(package=self.controller.package,
                           controller=self.controller,
                           defaulttype=at,
                           elements=self.history,
                           comments=self.comments,
                           duration=d)
        ti.process_file('history')
        self.controller.package._modified=True
        self.log(_('Converted from bookmarks'))
        self.log(ti.statistics_formatted())
        # Feedback
        dialog.message_dialog(
            _("Conversion completed.\n%s annotations generated.") % ti.statistics['annotation'])
        return True

    def activate(self, widget=None, timestamp=None):
        self.controller.update_status("set", timestamp, notify=False)
        return True

    def append(self, position):
        if position in self.history:
            return True
        self.history.append(position)
        if self.options['ordered']:
            self.history.sort()
            self.refresh()
        else:
            self.append_repr(position)
        return True

    def remove_widget(self, widget=None, container=None):
        container.remove(widget)
        return True

    def refresh(self, *p):
        self.mainbox.foreach(self.remove_widget, self.mainbox)
        for p in self.history:
            self.append_repr(p)
        self.mainbox.show_all()
        return True

    def clear(self, *p):
        del self.history[:]
        self.mainbox.foreach(self.remove_widget, self.mainbox)
        return True

    def append_repr(self, t):

        def drag_sent(widget, context, selection, targetType, eventTime):
            if targetType == config.data.target_type['timestamp']:
                selection.set(selection.target, 8, str(t))
                return True
            else:
                print "Unknown target type for drag: %d" % targetType
            return False

        if self.display_comments:
            box=gtk.HBox()
        else:
            box=gtk.VBox()
        i=image_from_position(self.controller,
                              t,
                              width=self.options['snapshot_width'])
        b=gtk.Button()
        b.connect("clicked", self.activate, t)
        b.add(i)

        # The button can generate drags
        b.connect("drag_data_get", drag_sent)

        b.drag_source_set(gtk.gdk.BUTTON1_MASK,
                          config.data.drag_type['timestamp'],
                          gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY)

        # Define drag cursor
        def _drag_begin(widget, context):
            w=gtk.Window(gtk.WINDOW_POPUP)
            w.set_decorated(False)

            v=gtk.VBox()
            i=gtk.Image()
            v.pack_start(i, expand=False)
            l=gtk.Label()
            v.pack_start(l, expand=False)

            i.set_from_pixbuf(png_to_pixbuf (self.controller.package.imagecache.get(t, epsilon=500), width=50))
            l.set_text(helper.format_time(t))

            w.add(v)
            w.show_all()
            widget._icon=w
            context.set_icon_widget(w, 0, 0)
            return True

        def _drag_end(widget, context):
            widget._icon.destroy()
            widget._icon=None
            return True

        b.connect("drag_begin", _drag_begin)
        b.connect("drag_end", _drag_end)

        box.pack_start(b, expand=False)

        l = gtk.Label(helper.format_time(t) + " - ")
        if self.display_comments:
            vbox=gtk.VBox()
            vbox.pack_start(l, expand=False)
            comment_entry=gtk.TextView()
            b=comment_entry.get_buffer()
            if t in self.comments:
                b.set_text(self.comments[t])
            else:
                b.set_text(_("No comment"))
            def update_comment(buf, ti):
                self.comments[ti]=buf.get_text(*buf.get_bounds())
                return True
            b.connect('changed', update_comment, t)
            vbox.pack_start(comment_entry, expand=True)
            box.pack_start(vbox, expand=False)
        else:
            box.pack_start(l)

        box.show_all()
        if self.scrollwindow:
            if self.options['vertical']:
                adj=self.scrollwindow.get_vadjustment()
            else:
                adj=self.scrollwindow.get_hadjustment()
            adj.set_value(adj.upper)
        self.mainbox.pack_start(box, expand=False)

    def build_widget(self):
        v=gtk.VBox()

        hb=gtk.HBox()
        hb.set_homogeneous(False)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                position=long(selection.data)
                if position in self.history:
                    self.history.remove(position)
                self.refresh()
                return True
            else:
                print "Unknown target type for drop: %d" % targetType
            return False

        b=get_small_stock_button(gtk.STOCK_DELETE)
        self.controller.gui.tooltips.set_tip(b, _("Drop a position here to remove it from the list"))
        b.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                        gtk.DEST_DEFAULT_HIGHLIGHT |
                        gtk.DEST_DEFAULT_ALL,
                        config.data.drag_type['timestamp'], gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY)
        b.connect("drag_data_received", remove_drag_received)
        hb.pack_start(b, expand=False)

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
        for icon, action, tip in (
            ('set-to-now.png', bookmark_current_time, _("Insert a bookmark for the current video time")),
            (gtk.STOCK_CONVERT, self.convert_to_annotations, _("Convert bookmarks to annotations")),
            (gtk.STOCK_SAVE, self.save_view, _("Save view")),
            ):
            if icon.endswith('.png'):
                i=gtk.Image()
                i.set_from_file(config.data.advenefile( ( 'pixmaps', icon) ))
                b=gtk.ToolButton(icon_widget=i)
            else:
                b=gtk.ToolButton(stock_id=icon)
            b.set_tooltip(self.controller.gui.tooltips, tip)
            b.connect("clicked", action)
            tb.insert(b, -1)
        hb.add(tb)
        v.pack_start(hb, expand=False)

        if self.options['vertical']:
            mainbox=gtk.VBox()
        else:
            mainbox=gtk.HBox()

        sw=gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        sw.add_with_viewport(mainbox)
        self.scrollwindow=sw
        self.mainbox=mainbox

        def mainbox_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                position=long(selection.data)
                self.append(position)
                return True
            else:
                print "Unknown target type for drop: %d" % targetType
            return False

        self.mainbox.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
                                  gtk.DEST_DEFAULT_HIGHLIGHT |
                                  gtk.DEST_DEFAULT_ALL,
                                  config.data.drag_type['timestamp'], gtk.gdk.ACTION_LINK | gtk.gdk.ACTION_COPY)
        self.mainbox.connect("drag_data_received", mainbox_drag_received)

        v.add(sw)

        return v
