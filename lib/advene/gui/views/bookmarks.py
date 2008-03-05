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
"""Module displaying time bookmarks (for navigation history for instance)."""

import gtk
import pango
import urllib

# Advene part
import advene.core.config as config
import advene.util.helper as helper
from advene.gui.util import image_from_position, get_small_stock_button, dialog, png_to_pixbuf
from advene.gui.views import AdhocView
from advene.gui.widget import TimestampRepresentation
import advene.util.importer
from gettext import gettext as _

name="Bookmarks view plugin"

def register(controller):
    controller.register_viewclass(Bookmarks)

class HistoryImporter(advene.util.importer.GenericImporter):
    """History importer.
    """
    def __init__(self, elements=None, duration=2000, **kw):
        super(HistoryImporter, self).__init__(**kw)
        self.elements=elements
        self.duration=duration
        self.name = _("Bookmarks importer")

    def iterator(self):
        for b in self.elements:
            yield {
                'begin': b.value,
                'end': b.value + self.duration,
                'content': b.comment or  "Bookmark %s" % helper.format_time(b.value),
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

    def __init__(self, controller=None, parameters=None, history=None, vertical=True, closable=True, display_comments=True): 
        super(Bookmarks, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Clear"), self.clear),
            )
        self.options={
            'vertical': vertical,
            }
        self.controller=controller
        self.display_comments=display_comments
        self.bookmarks=[]

        # History may be a list of timestamps.
        if history is None:
            history=[]
        # Convert the list of timestamps to a list of tuples (timestamp, empty comment)
        history=[ (t, '') for t in history ]

        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)

        h=[]
        # Bookmark format: timestamp:url-encoded_comment
        for n, v in arg:
            if n == 'bookmark':
                t, c = v.split(':', 1)
                h.append( (long(float(t)), urllib.unquote(c)) )
        if h:
            history=h

        for (t, c) in history:
            self.bookmarks.append( BookmarkWidget(self.controller, t, c, self.display_comments) )

        self.closable=closable
        self.mainbox=None
        self.scrollwindow=None
        self.widget=self.build_widget()
        self.refresh()

    def get_matching_bookmark(self, t):
        l=[ w for w in self.bookmarks if w.value == t ]
        if l:
            return l[0]
        else:
            return None

    def get_save_arguments(self):
        return self.options, ([ ('bookmark', '%d:%s' % (b.value, urllib.quote(b.comment)) ) for b in self.bookmarks ])

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
                           elements=self.bookmarks,
                           duration=d)
        ti.process_file('history')
        self.controller.package._modified=True
        self.log(_('Converted from bookmarks'))
        self.log(ti.statistics_formatted())
        # Feedback
        dialog.message_dialog(
            _("Conversion completed.\n%s annotations generated.") % ti.statistics['annotation'])
        return True

    def append(self, position, comment=''):
        if position in [ w.value for w in self.bookmarks ]:
            return True
        b=BookmarkWidget(self.controller, position, comment, self.display_comments)
        self.bookmarks.append(b)
        self.mainbox.pack_start(b.widget, expand=False)
        b.widget.show_all()
        self.autoscroll()
        return True

    def refresh(self, *p):
        self.mainbox.foreach(self.mainbox.remove)
        for b in self.bookmarks:
            self.mainbox.pack_start(b.widget, expand=False)
        self.mainbox.show_all()
        self.autoscroll()
        return True

    def clear(self, *p):
        self.mainbox.foreach(self.mainbox.remove)
        del self.bookmarks[:]
        return True

    def autoscroll(self):
        if self.scrollwindow:
            if self.options['vertical']:
                adj=self.scrollwindow.get_vadjustment()
            else:
                adj=self.scrollwindow.get_hadjustment()
            adj.set_value(adj.upper)

    def build_widget(self):
        v=gtk.VBox()

        hb=gtk.HBox()
        hb.set_homogeneous(False)

        def remove_drag_received(widget, context, x, y, selection, targetType, time):
            if targetType == config.data.target_type['timestamp']:
                position=long(selection.data)
                w=self.get_matching_bookmark(position)
                if position is not None:
                    self.bookmarks.remove(w)
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

class BookmarkWidget(object):
    def __init__(self, controller=None, timestamp=0, comment=None, display_comments=False):
        self.controller=controller
        self.value=timestamp
        if comment is None:
            comment=_("No comment")
        self.comment=comment
        self.display_comments=display_comments
        self.widget=self.build_widget()

    def update(self):
        self.image.value=self.value
        return True

    def build_widget(self):
        self.image=TimestampRepresentation(self.value, self.controller)

        def activate(widget=None):
            if self.value is not None:
                self.controller.update_status("set", self.value, notify=False)
            return True

        self.image.connect("clicked", activate)

        if self.display_comments:
            hbox=gtk.HBox()
            comment_entry=gtk.TextView()
            comment_entry.set_wrap_mode(gtk.WRAP_WORD)
            fd=pango.FontDescription('sans %d' % config.data.preferences['timeline']['font-size'])
            comment_entry.modify_font(fd)
            b=comment_entry.get_buffer()
            b.set_text(self.comment)
            def update_comment(buf):
                self.comment=buf.get_text(*buf.get_bounds())
                return True
            b.connect('changed', update_comment)
            
            comment_entry.set_size_request(config.data.preferences['bookmark-snapshot-width'], -1)

            sw=gtk.ScrolledWindow()
            sw.add(comment_entry)
            sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER)
            hbox.pack_start(self.image, expand=False)
            hbox.pack_start(sw, expand=False)
            hbox.show_all()
            return hbox
        else:
            return self.image
