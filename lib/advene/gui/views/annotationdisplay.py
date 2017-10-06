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
"""Module displaying the contents of an annotation.
"""

from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
from gettext import gettext as _

import advene.core.config as config
from advene.gui.views import AdhocView
import advene.util.helper as helper
from advene.gui.util import overlay_svg_as_pixbuf, get_pixmap_button
from advene.model.annotation import Annotation
from advene.model.schema import AnnotationType
from advene.gui.widget import TimestampRepresentation
from advene.gui.util.completer import Completer

name="Annotation display plugin"

def register(controller):
    controller.register_viewclass(AnnotationDisplay)

class AnnotationDisplay(AdhocView):
    view_name = _("AnnotationDisplay")
    view_id = 'annotationdisplay'
    tooltip = _("Display the contents of an annotation")

    def __init__(self, controller=None, parameters=None, annotation=None):
        super(AnnotationDisplay, self).__init__(controller=controller)
        self.close_on_package_load = True
        self.contextual_actions = ()
        self.controller=controller
        self.annotation=annotation
        self.completer = None
        self.widget=self.build_widget()
        self.refresh()

    def set_annotation(self, a=None):
        """This method takes either an annotation, a time value or None as parameter.
        """
        self.annotation = a
        if self.completer is not None:
            self.completer.element = a
        self.refresh()
        return True

    def set_master_view(self, v):
        v.register_slave_view(self)
        self.close_on_package_load = False

    def update_annotation(self, annotation=None, event=None):
        if annotation != self.annotation:
            return True
        if event == 'AnnotationEditEnd':
            self.refresh()
        elif event == 'AnnotationDelete':
            if self.master_view is None:
                # Autonomous view. We should close it.
                self.close()
            else:
                # There is a master view, just empty the representation
                self.set_annotation(None)
        return True

    def refresh(self, *p):
        if self.annotation is None:
            d={ 'title': _("No annotation"),
                'begin': helper.format_time(None),
                'end': helper.format_time(None),
                'contents': '',
                'imagecontents': None}
        elif isinstance(self.annotation, int):
            d={ 'title': _("Current time"),
                'begin': helper.format_time(self.annotation),
                'end': helper.format_time(None),
                'contents': '',
                'imagecontents': None}
        elif isinstance(self.annotation, AnnotationType):
            col=self.controller.get_element_color(self.annotation)
            if col:
                title='<span background="%s">Annotation Type <b>%s</b></span>' % (col, self.controller.get_title(self.annotation))
            else:
                title='Annotation Type <b>%s</b>' % self.controller.get_title(self.annotation)
            if len(self.annotation.annotations):
                b=min(a.fragment.begin for a in self.annotation.annotations)
                e=max(a.fragment.end for a in self.annotation.annotations)
            else:
                b=None
                e=None
            d={ 'title': title,
                'begin': helper.format_time(b),
                'end': helper.format_time(e),
                'contents': _("Schema %(schema)s (id %(id)s)\n%(description)s\n%(stats)s") % {
                    'schema': self.controller.get_title(self.annotation.schema),
                    'id': self.annotation.id,
                    'description': self.annotation.getMetaData(config.data.namespace_prefix['dc'], "description") or "",
                    'stats': helper.get_annotations_statistics(self.annotation.annotations)
                    },
                'imagecontents': None,
                }
        else:
            # FIXME: there should be a generic content handler
            # mechanism for basic display of various contents
            d={ 'id': self.annotation.id,
                'begin': helper.format_time(self.annotation.fragment.begin),
                'end': helper.format_time(self.annotation.fragment.end),
                'duration': helper.format_time(self.annotation.fragment.duration),
                'color': self.controller.get_element_color(self.annotation),
                }
            if d['color']:
                d['title']='<span background="%(color)s">Annotation <b>%(id)s</b></span> (d: %(duration)s)' % d
            else:
                d['title']='Annotation <b>%(id)s</b> (d: %(duration)s)' % d
            svg_data=None
            if self.annotation.content.mimetype.startswith('image/svg'):
                svg_data=self.annotation.content.data
            elif self.annotation.content.mimetype == 'application/x-advene-zone':
                # Build svg
                data=self.annotation.content.parsed()
                svg_data='''<svg xmlns='http://www.w3.org/2000/svg' version='1' viewBox="0 0 320 300" x='0' y='0' width='320' height='200'><%(shape)s style="fill:none;stroke:green;stroke-width:2;" width="%(width)s%%" height="%(height)s%%" x="%(x)s%%" y="%(y)s%%"></rect></svg>''' % data
            if svg_data:
                pixbuf=overlay_svg_as_pixbuf(self.controller.package.imagecache[self.annotation.fragment.begin],
                                             self.annotation.content.data)
                d['contents']=''
                d['imagecontents']=pixbuf
            elif self.annotation.content.mimetype.startswith('image/'):
                # Image content, other than image/svg
                # Load the element content
                loader = GdkPixbuf.PixbufLoader()
                try:
                    loader.write (self.annotation.content.data, len (self.annotation.content.data))
                    loader.close ()
                    pixbuf = loader.get_pixbuf ()
                except GObject.GError:
                    # The PNG data was invalid.
                    pixbuf=GdkPixbuf.Pixbuf.new_from_file(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ))

                d['contents']=''
                d['imagecontents'] = pixbuf
            else:
                d['contents']=self.annotation.content.data
                d['imagecontents']=None

        for k, v in d.items():
            if k == 'title':
                self.label[k].set_markup(v)
            elif k == 'imagecontents':
                if v is None:
                    self.sw['imagecontents'].hide()
                    self.sw['contents'].show()
                else:
                    self.sw['imagecontents'].show_all()
                    self.sw['contents'].hide()

                    pixbuf=d['imagecontents']
                    w=self.widget.get_allocation().width - 6
                    width=pixbuf.get_width()
                    height=pixbuf.get_height()
                    if width > w and w > 0:
                        height = 1.0 * w * height / width
                        pixbuf=pixbuf.scale_simple(int(w), int(height), GdkPixbuf.InterpType.BILINEAR)
                    self.label['imagecontents'].set_from_pixbuf(pixbuf)
            else:
                widget = self.label.get(k)
                if widget is not None:
                    widget.set_text(v)
        if self.annotation is None or isinstance(self.annotation, AnnotationType):
            self.label['image'].hide()
        else:
            if isinstance(self.annotation, int):
                b=self.annotation
            elif isinstance(self.annotation, Annotation):
                b=self.annotation.fragment.begin
            self.label['image'].value = b
            self.label['image'].show()
        return False

    def build_widget(self):
        v=Gtk.VBox()

        self.label={}
        self.sw={}

        h=Gtk.HBox()
        self.label['title']=Gtk.Label()
        h.pack_start(self.label['title'], False, True, 0)
        v.pack_start(h, False, True, 0)

        h=Gtk.HBox()
        self.label['begin']=Gtk.Label()
        h.pack_start(self.label['begin'], False, True, 0)
        l=Gtk.Label(label=' - ')
        h.pack_start(l, False, True, 0)
        self.label['end']=Gtk.Label()
        h.pack_start(self.label['end'], False, True, 0)
        v.pack_start(h, False, True, 0)

        def handle_motion(widget, event):
            if isinstance(self.annotation, Annotation):
                i = self.label['image']
                i.precision = int(self.annotation.fragment.duration / widget.get_allocation().width)
                v = self.annotation.fragment.begin + i.precision * 20 * int(event.x / 20)
                i.set_value(v)
            return True

        def handle_leave(widget, event):
            if isinstance(self.annotation, Annotation):
                i = self.label['image']
                i.precision = config.data.preferences['bookmark-snapshot-precision']
                i.set_value(self.annotation.fragment.begin)
            return True

        fr = Gtk.Expander ()
        fr.set_label(_("Screenshot"))
        self.label['image'] = TimestampRepresentation(-1, None, self.controller, width=config.data.preferences['drag-snapshot-width'], precision=config.data.preferences['bookmark-snapshot-precision'], visible_label=False)
        self.label['image'].add_events(Gdk.EventMask.POINTER_MOTION_MASK
                                       | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.label['image'].connect('motion-notify-event', handle_motion)
        self.label['image'].connect('leave-notify-event', handle_leave)

        fr.add(self.label['image'])
        fr.set_expanded(True)
        v.pack_start(fr, False, True, 0)

        # Contents frame
        def handle_ok(b):
            b.hide()
            if isinstance(self.annotation, Annotation):
                self.controller.notify('EditSessionStart', element=self.annotation, immediate=True)
                self.annotation.content.data = self.label['contents'].get_text()
                self.controller.notify("AnnotationEditEnd", annotation=self.annotation)
                self.controller.notify('EditSessionEnd', element=self.annotation)
            return True

        hbox = Gtk.HBox()
        hbox.pack_start(Gtk.Label(_("Contents")), False, False, 0)
        ok_button=get_pixmap_button('small_ok.png', handle_ok)
        ok_button.set_relief(Gtk.ReliefStyle.NONE)
        ok_button.set_tooltip_text(_("Validate"))
        ok_button.set_no_show_all(True)
        hbox.pack_start(ok_button, False, True, 0)

        f=Gtk.Frame()
        f.set_label_widget(hbox)

        def contents_modified(buf):
            if buf.get_modified():
                if not buf.ignore_modified:
                    ok_button.show()
            else:
                ok_button.hide()
            return True

        c=self.label['contents']=Gtk.TextView()
        c.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        c.get_buffer().ignore_modified = False
        c.get_buffer().connect('modified-changed', contents_modified)
        sw=Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(c)
        def set_text(widget, t):
            b=widget.get_buffer()
            b.ignore_modified = True
            b.delete(*b.get_bounds())
            b.set_text(t)
            b.set_modified(False)
            b.ignore_modified = False
            return True
        c.set_text = set_text.__get__(c)
        def get_text(widget):
            b=widget.get_buffer()
            return b.get_text(*b.get_bounds() + ( False, ))
        c.get_text = get_text.__get__(c)
        self.sw['contents']=sw

        def handle_keypress(widget, event):
            if (event.keyval == Gdk.KEY_Return
                and event.get_state() & Gdk.ModifierType.CONTROL_MASK
                and widget.get_buffer().get_modified()):
                handle_ok(ok_button)
                return True
            return False
        c.connect('key-press-event', handle_keypress)

        # Hook the completer component
        if hasattr(self.controller.package, '_indexer'):
            self.completer=Completer(textview=c,
                                     controller=self.controller,
                                     element=self.annotation,
                                     indexer=self.controller.package._indexer)

        image=self.label['imagecontents']=Gtk.Image()

        swi=Gtk.ScrolledWindow()
        swi.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        swi.add_with_viewport(image)
        self.sw['imagecontents']=swi

        vb=Gtk.VBox()
        vb.add(sw)
        vb.add(swi)

        f.add(vb)
        v.add(f)

        v.show_all()
        image.hide()
        v.set_no_show_all(True)

        def annotation_drag_received_cb(widget, context, x, y, selection, targetType, time):
            """Handle the drop of an annotation.
            """
            if targetType == config.data.target_type['annotation']:
                sources=[ self.controller.package.annotations.get(uri) for uri in str(selection.get_data(), 'utf8').split('\n') ]
                if sources:
                    self.set_annotation(sources[0])
                return True
            return False
        # The button can receive drops (to display annotations)
        v.connect('drag-data-received', annotation_drag_received_cb)
        v.drag_dest_set(Gtk.DestDefaults.MOTION |
                        Gtk.DestDefaults.HIGHLIGHT |
                        Gtk.DestDefaults.ALL,
                        config.data.get_target_types('annotation'),
                        Gdk.DragAction.COPY | Gdk.DragAction.LINK | Gdk.DragAction.MOVE)

        return v
