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
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk
import re
import cairo

import advene.core.config as config
from advene.gui.edit.elements import ContentHandler, TextContentHandler
from advene.gui.util import png_to_pixbuf, decode_drop_parameters, get_pixmap_toolbutton, overlay_svg_as_pixbuf, get_clipboard

from advene.gui.edit.htmleditor import HTMLEditor, ContextDisplay
import advene.util.helper as helper

name="HTML content handler"

def register(controller=None):
    controller.register_content_handler(HTMLContentHandler)

class AnnotationPlaceholder:
    def __init__(self, annotation=None, controller=None, presentation=None, update_pixbuf=None):
        self.annotation=annotation
        self.controller=controller
        if presentation is None:
            presentation=('snapshot', 'link')
        self.presentation=presentation
        self.update_pixbuf=update_pixbuf
        self.width=160
        # FIXME: how to pass/parse width, height, alt, link ?
        self.rules=[]
        self.pixbuf=self.build_pixbuf()
        self.refresh()

    def cleanup(self):
        for r in self.rules:
            self.controller.event_handler.remove_rule(r, 'internal')
        self.rules=[]

    def process_enclosed_tags(self, typ, tag, attr=None):
        """Process enclosed data.

        typ is in ('start', 'end', 'data').
        if typ == 'data': tag is in fact the data itself.
        if typ == 'start': attr is a dictionary with the attributes
        """
        if typ == 'end' and tag == 'span':
            return False
        return True

    def parse_html(self, tag, attr):
        if attr['class'] == 'advene:annotation':
            self.presentation=attr['advene:presentation'].split(':')
            aid=attr['advene:annotation']
            self.annotation=self.controller.package.get_element_by_id(aid)
            if self.annotation is None:
                logger.warn("Problem: non-existent annotation %s", aid)
            self.refresh()
            return self.pixbuf, self.process_enclosed_tags
        return None, None

    def as_html(self):
        if self.annotation is None:
            return """<span advene:error="Non-existent annotation"></span>"""

        ctx=self.controller.build_context(self.annotation)
        d={
            'id': self.annotation.id,
            'href': self.controller.get_urlbase() + ctx.evaluateValue('here/player_url'),
            'imgurl': self.controller.get_urlbase() + ctx.evaluateValue('here/snapshot_url'),
            'timestamp': helper.format_time(self.annotation.fragment.begin),
            'content': self.controller.get_title(self.annotation),
            'urlbase': self.controller.get_urlbase().rstrip('/'),
            }
        data=[ """<span class="advene:annotation" advene:annotation="%s" advene:presentation="%s">""" % (self.annotation.id, ':'.join(self.presentation)) ]

        if 'link' in self.presentation:
            data.append("""<a title="Click to play the movie in Advene" tal:attributes="href package/annotations/%(id)s/player_url" href="%(href)s">""" % d)

        if 'overlay' in self.presentation:
            data.append("""<img title="Click here to play"  width="160" height="100" src="%(urlbase)s/media/overlay/advene/%(id)s"></img>""" % d)
        elif 'snapshot' in self.presentation:
            if 'timestamp' in self.presentation:
                data.append("""<img title="Click here to play"  width="160" height="100" src="%(urlbase)s/media/overlay/advene/%(id)s/fragment/formatted/begin"></img>""" % d)
            else:
                data.append("""<img title="Click here to play" width="160" height="100" tal:attributes="src package/annotations/%(id)s/snapshot_url" src="%(imgurl)s" ></img>""" % d)
        elif 'timestamp' in self.presentation:
            # timestamp without snapshot or overlay
            data.append("""<em tal:content="package/annotations/%(id)s/fragment/formatted/begin">%(timestamp)s</em><br>""" % d)
        elif 'content' in self.presentation:
            data.append("""<span tal:content="package/annotations/%(id)s/representation">%(content)s</span>""" % d)
        if 'link' in self.presentation:
            data.append('</a>')

        data.append('</span>')

        return "".join(data)

    def snapshot_updated(self, context, target):
        if (self.annotation is not None
            and context.globals['media'] == self.annotation.media
            and abs(context.globals['position'] - self.annotation.fragment.begin) <= 20):
            # Update the representation
            self.refresh()
        return True

    def annotation_updated(self, context, target):
        if context.globals['annotation'] == self.annotation:
            self.refresh()
        return True

    def annotation_deleted(self, context, target):
        if context.globals['annotation'] == self.annotation:
            self.annotation=None
            self.cleanup()
            self.refresh()
        return True

    def refresh(self):
        if not self.rules and self.annotation:
            # Now that an annotation is defined, we can connect the notifications
            self.rules.append(self.controller.event_handler.internal_rule (event='AnnotationEditEnd',
                                                                           method=self.annotation_updated))
            self.rules.append(self.controller.event_handler.internal_rule (event='AnnotationDelete',
                                                                           method=self.annotation_deleted))
            self.rules.append(self.controller.event_handler.internal_rule (event='SnapshotUpdate',
                                                                           method=self.snapshot_updated))

        old=self.pixbuf
        new=self.build_pixbuf()
        if not self.update_pixbuf:
            new.composite(old, 0, 0, old.get_width(), old.get_height(),
                          0, 0, 1.0, 1.0, GdkPixbuf.InterpType.BILINEAR, 255)
        else:
            self.update_pixbuf(old, new)
        self.pixbuf=new
        return True

    def render_text(self, text):
        """Render the given text as a pixbuf.
        """

        # Find out the pixbuf size
        import cairo
        context = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
        context.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(12)
        x_bearing, y_bearing, width, height = context.text_extents(text)[:4]

        # Generate text
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(width) + 4, int(height) + 4)
        context = cairo.Context(surface)
        context.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(12)
        context.set_source_rgba(0, 0, 0, 1)
        context.move_to(2 - x_bearing, 2 - y_bearing)
        context.text_path(text)
        context.set_line_width(0.5)
        context.stroke_preserve()
        context.fill()

        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            surface.get_data(),
            GdkPixbuf.Colorspace.RGB, True, 8,
            surface.get_width(), surface.get_height(),
            surface.get_stride())
        return pixbuf

    def build_pixbuf(self):
        if self.annotation is None:
            pixbuf=png_to_pixbuf(self.controller.package.imagecache.not_yet_available_image,
                                 width=self.width)
        elif 'overlay' in self.presentation:
            pixbuf=overlay_svg_as_pixbuf(self.annotation.rootPackage.imagecache[self.annotation.fragment.begin],
                                         self.annotation.content.data,
                                         width=self.width)
        elif 'snapshot' in self.presentation:
            if 'timestamp' in self.presentation:
                pixbuf=overlay_svg_as_pixbuf(self.annotation.rootPackage.imagecache[self.annotation.fragment.begin],
                                             helper.format_time(self.annotation.fragment.begin),
                                             width=self.width)
            else:
                pixbuf=png_to_pixbuf(self.annotation.rootPackage.imagecache[self.annotation.fragment.begin],
                                     width=self.width)
        elif 'timestamp' in self.presentation:
            # Generate only a timestamp
            pixbuf = self.render_text(helper.format_time(self.annotation.fragment.begin))
        elif 'content' in self.presentation:
            # Display text
            pixbuf = self.render_text(self.controller.get_title(self.annotation))
        else:
            pixbuf=png_to_pixbuf(self.controller.package.imagecache.not_yet_available_image,
                                 width=self.width)
        pixbuf.as_html=self.as_html
        pixbuf._placeholder=self
        pixbuf._tag='span'
        pixbuf._attr=[]
        return pixbuf

class AnnotationTypePlaceholder:
    """AnnotationType representation.

    presentation is a list of presentation modalities. Values include:
    * list : display as a bulleted list
    * transcription : display as a transcription
    * table : display as a table
    """
    def __init__(self, annotationtype=None, controller=None, presentation=None, update_pixbuf=None):
        self.annotationtype=annotationtype
        self.controller=controller
        if presentation is None:
            presentation=[ 'list' ]
        self.presentation=presentation
        self.span_count = 0
        self.update_pixbuf=update_pixbuf
        self.width=160
        # FIXME: how to pass/parse width, height, alt, link ?
        self.rules=[]
        self.pixbuf=self.build_pixbuf()
        self.refresh()

    def cleanup(self):
        for r in self.rules:
            self.controller.event_handler.remove_rule(r, 'internal')
        self.rules=[]

    def process_enclosed_tags(self, typ, tag, attr=None):
        """Process enclosed data.

        FIXME: what should we do here?
        """
        if typ == 'start' and tag == 'span':
            self.span_count += 1
        if typ == 'end' and tag == 'span':
            self.span_count -= 1
            if self.span_count == 0:
                return False
        return True

    def parse_html(self, tag, attr):
        if attr['class'] == 'advene:annotationtype':
            self.presentation=attr['advene:presentation'].split(':')
            aid=attr['advene:annotationtype']
            self.annotationtype = self.controller.package.get_element_by_id(aid)
            if self.annotationtype is None:
                logger.warn("Problem: non-existent annotation type %s", aid)
            self.refresh()
            return self.pixbuf, self.process_enclosed_tags
        return None, None

    def as_html(self):
        if self.annotationtype is None:
            return """<span advene:error="Non-existent annotation type"></span>"""

        ctx=self.controller.build_context(self.annotationtype)
        d={
            'id': self.annotationtype.id,
            'href': self.controller.get_urlbase() + ctx.evaluateValue('here/absolute_url'),
            'content': self.controller.get_title(self.annotationtype),
            'urlbase': self.controller.get_urlbase().rstrip('/'),
            }
        data=[ """<span class="advene:annotationtype" advene:annotationtype="%s" advene:presentation="%s">""" % (self.annotationtype.id, ':'.join(self.presentation)) ]

        if 'list' in self.presentation:
            data.append("<ul>")
            data.append("""<li tal:repeat="a package/annotationTypes/%(id)s/annotations/sorted"><a title="Click to play the movie" tal:attributes="href a/player_url" tal:content="a/content/data"></a>""" % d)
            data.append("""</li></ul>""")
        elif 'grid' in self.presentation:
            data.append("""
<div class="screenshot_container" style="text-align: center; float: left; width: 200; height: 170; font-size: 0.8em;" tal:repeat="a package/annotationTypes/%(id)s/annotations/sorted">
<a title="Play this annotation" tal:attributes="href a/player_url">
        <img class="screenshot" style="border:1px solid #FFCCCC; height:100px; width:160px;" alt="" tal:attributes="src a/snapshot_url" />
	<br />
	<strong tal:content="a/representation">Nom</strong>
</a><br />
<span>(<span tal:content="a/fragment/formatted/begin">Debut</span> - <span tal:content="a/fragment/formatted/end">Fin</span>)</span>
<br />
</div>""" % d)
        elif 'table' in self.presentation:
            data.append("""
<table border="1">

<tr><td>Vignette</td><td>Contenu</td><td>D&eacute;but</td><td>Dur&eacute;</td></tr>

<tr tal:repeat="a package/annotationTypes/%(id)s/annotations/sorted">
<td><a title="Play this annotation" tal:attributes="href a/player_url">
        <img class="screenshot" style="border:1px solid #FFCCCC; height:100px; width:160px;" alt="" tal:attributes="src a/snapshot_url" /></a></td>
<td><strong tal:content="a/representation">Nom</strong></td>
<td><span tal:content="a/fragment/formatted/begin">Debut</span></td>
<td><span tal:content="a/fragment/formatted/duration">Duree</span></td>
</tr>

</table>""" % d)
        elif 'transcription' in self.presentation:
            data.append("""<span class="transcript" tal:repeat="a package/annotationTypes/%(id)s/annotations/sorted" tal:attributes="annotation-id a/id">
<a title="Click to play the movie" tal:attributes="href a/player_url" tal:content="a/content/data"></a></span>""" % d)

        data.append('</span>')
        return "".join(data)

    def annotationtype_updated(self, context, target):
        if context.globals['annotationtype'] == self.annotationtype:
            self.refresh()
        return True

    def annotationtype_deleted(self, context, target):
        if context.globals['annotationtype'] == self.annotationtype:
            self.annotationtype=None
            self.cleanup()
            self.refresh()
        return True

    def refresh(self):
        if not self.rules and self.annotationtype:
            # Now that an annotation is defined, we can connect the notifications
            self.rules.append(self.controller.event_handler.internal_rule (event='AnnotationTypeEditEnd',
                                                                           method=self.annotationtype_updated))
            self.rules.append(self.controller.event_handler.internal_rule (event='AnnotationTypeDelete',
                                                                           method=self.annotationtype_deleted))
        old=self.pixbuf
        new=self.build_pixbuf()
        if not self.update_pixbuf:
            new.composite(old, 0, 0, old.get_width(), old.get_height(),
                          0, 0, 1.0, 1.0, GdkPixbuf.InterpType.BILINEAR, 255)
        else:
            self.update_pixbuf(old, new)
        self.pixbuf=new
        return True

    def render_text(self, text):
        """Render the given text as a pixbuf.
        """

        # Find out the pixbuf size
        import cairo
        context = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
        context.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(12)
        x_bearing, y_bearing, width, height = context.text_extents(text)[:4]

        # Generate text
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(width) + 4, int(height) + 4)
        context = cairo.Context(surface)
        context.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        context.set_font_size(12)
        context.set_source_rgba(0, 0, 0, 1)
        context.move_to(2 - x_bearing, 2 - y_bearing)
        context.text_path(text)
        context.set_line_width(0.5)
        context.stroke_preserve()
        context.fill()

        pixbuf = GdkPixbuf.Pixbuf.new_from_data(
            surface.get_data(),
            GdkPixbuf.Colorspace.RGB, True, 8,
            surface.get_width(), surface.get_height(),
            surface.get_stride())
        return pixbuf

    def build_pixbuf(self):
        pixbuf = self.render_text(_("Rendering type %(type)s as %(presentation)s") % {
                'type': self.controller.get_title(self.annotationtype),
                'presentation': self.presentation[0],
                })
        pixbuf.as_html=self.as_html
        pixbuf._placeholder=self
        pixbuf._tag='span'
        pixbuf._attr=[]
        return pixbuf

class HTMLContentHandler (ContentHandler):
    """Create a HTML edit form for the given element."""
    def can_handle(mimetype):
        res=0
        if mimetype == 'text/html':
            res=90
        return res
    can_handle=staticmethod(can_handle)

    def __init__ (self, element, controller=None, parent=None, **kw):
        self.element = element
        self.controller=controller
        self.parent=parent
        self.editable = True
        self.fname=None
        self.last_dndtime=None
        self.last_x = None
        self.last_y = None
        # HTMLEditor component (Gtk.Textview subclass)
        self.editor = None

        # Widgets holding editors (basic and html)
        self.view = None
        self.sourceview=None

        self.placeholders=[]

        self.editing_source=False

    def close(self):
        for p in self.placeholders:
            p.cleanup()

    def set_editable (self, boolean):
        self.editable = boolean
        if self.sourceview:
            self.sourceview.set_editable(boolean)

    def get_modified(self):
        if self.editing_source:
            return self.sourceview.get_modified()
        else:
            return self.editor.get_modified()

    def update_element (self):
        """Update the element fields according to the values in the view."""
        if not self.editable:
            return False

        if self.editing_source:
            self.sourceview.update_element()
            # We applied our modifications to the HTML source, so
            # parse the source again in the HTML editor
            if self.editor is not None:
                self.editor.set_text(self.element.data)
                self.editor.set_modified(False)
            return True

        if self.editor is None:
            return True

        self.element.data = self.editor.get_html()
        # Update the HTML source representation
        if self.sourceview is not None:
            self.sourceview.content_set(self.element.data)
            self.sourceview.set_modified(False)
        return True

    def open_link(self, link=None):
        if link:
            pos=re.findall('/media/play/(\d+)', link)
            if pos:
                # A position was specified. Directly use it.
                self.controller.update_status('seek', int(pos[0]))
            else:
                self.controller.open_url(link)
        return True

    def insert_annotation_content(self, choice, annotation, focus=False):
        """
        choice: list of one or more strings: 'snapshot', 'timestamp', 'content', 'overlay'
        """
        a=AnnotationPlaceholder(annotation, self.controller, choice, self.editor.update_pixbuf)
        self.placeholders.append(a)
        self.editor.insert_pixbuf(a.pixbuf)
        if focus:
            self.grab_focus()
        return True

    def insert_annotationtype_content(self, choice, annotationtype, focus=False):
        """
        choice: list of one or more strings: 'list', 'table', 'transcription'
        """
        a=AnnotationTypePlaceholder(annotationtype, self.controller, choice, self.editor.update_pixbuf)
        self.placeholders.append(a)
        self.editor.insert_pixbuf(a.pixbuf)
        if focus:
            self.grab_focus()
        return True

    def grab_focus(self, *p):
        self.editor.grab_focus()
        return True

    def editor_drag_received(self, widget, context, x, y, selection, targetType, time):
        """Handle the drop from an annotation to the editor.
        """
        # FIXME: Upon DND, TextView receives the event twice. Some
        # posts from 2004 signal the same problem, some hacks can be
        # found in existing code :
        #   widget.emit_stop_by_name ("drag-data-received")
        #   context.finish(False, False, time)
        #   widget.stop_emission("drag-data-received")
        # but none of them seems to work here. Just use a basic approach,
        # imagining that nobody is fast enough to really do two DNDs
        # at the same time.
        # But on win32, timestamp is always 0. So we must use x and y information as well.
        if time == self.last_dndtime and x == self.last_x and y == self.last_y:
            return True
        self.last_dndtime=time
        self.last_x=x
        self.last_y=y

        x, y = self.editor.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
                                                   *widget.get_pointer())
        it = self.editor.get_iter_at_location(x, y)
        self.editor.get_buffer().place_cursor(it.iter)

        if targetType == config.data.target_type['annotation']:
            for uri in str(selection.get_data(), 'utf8').split('\n'):
                source=self.controller.package.annotations.get(uri)
                if source is None:
                    return True
                m=Gtk.Menu()
                for (title, choice) in (
                    (_("Snapshot only"), ['link', 'snapshot', ]),
                    (_("Overlayed snapshot only"), ['link', 'overlay', ]),
                    (_("Timestamp only"), ['link', 'timestamp', ]),
                    (_("Snapshot+timestamp"), ['link', 'snapshot', 'timestamp']),
                    (_("Annotation content"), ['link', 'content']),
                    ):
                    i=Gtk.MenuItem(title)
                    i.connect('activate', (lambda it, ann, data: self.insert_annotation_content(data, ann, focus=True)), source, choice)
                    m.append(i)
                m.show_all()
                m.popup(None, None, None, 0, Gtk.get_current_event_time())
            return True
        elif targetType == config.data.target_type['annotation-type']:
            for uri in str(selection.get_data(), 'utf8').split('\n'):
                source = self.controller.package.annotationTypes.get(uri)
                if source is None:
                    return True
                m=Gtk.Menu()
                for (title, choice) in (
                    (_("as a list"), [ 'list' ]),
                    (_("as a grid"), [ 'grid' ]),
                    (_("as a table"), [ 'table' ]),
                    (_("as a transcription"), ['transcription' ]),
                    ):
                    i=Gtk.MenuItem(title)
                    i.connect('activate', (lambda it, at, data: self.insert_annotationtype_content(data, at, focus=True)), source, choice)
                    m.append(i)
                m.show_all()
                m.popup(None, None, None, 0, Gtk.get_current_event_time())
            return True
        elif targetType == config.data.target_type['timestamp']:
            data=decode_drop_parameters(selection.get_data())
            t=int(data['timestamp'])
            # FIXME: propose various choices (insert timestamp, insert snapshot, etc)
            self.editor.get_buffer().insert_at_cursor(helper.format_time(t))
            return True
        else:
            logger.warn("Unknown target type for drop: %d" % targetType)
        return False

    def class_parser(self, tag, attr):
        if attr['class'] == 'advene:annotation':
            a=AnnotationPlaceholder(annotation=None,
                                    controller=self.controller,
                                    update_pixbuf=self.editor.update_pixbuf)
            self.placeholders.append(a)
            return a.parse_html(tag, attr)
        elif attr['class'] == 'advene:annotationtype':
            a=AnnotationTypePlaceholder(annotationtype=None,
                                        controller=self.controller,
                                        update_pixbuf=self.editor.update_pixbuf)
            self.placeholders.append(a)
            return a.parse_html(tag, attr)
        return None, None

    def custom_url_loader(self, url):
        """Custom URL loader.

        This method processes URLs internally when possible, instead
        of going through the webserver. This is at the cost of some
        code, and possible discrepancies with the original webcherry
        code. It is absolutely unnecessary on linux/macosx. However,
        win32 (svg?) pixbuf loader is broken wrt. threads, and this is
        the solution to have the overlay() code (and thus the pixbuf
        loader) execute in the main thread.
        """
        m=re.search('/media/overlay/(.+?)/(.+)', url)
        if m:
            (alias, element)=m.groups()
            if '/' in element:
                # There is a TALES expression specifying the overlayed
                # content
                aid, path = element.split('/', 1)
            else:
                aid, path = element, None
            p=self.controller.packages.get(alias)
            if not p:
                return None
            a=p.get_element_by_id(aid)
            if a is None:
                return None
            if path:
                # There is a TALES expression
                path='here/'+path
                ctx=self.controller.build_context(here=a)
                svg_data=str( ctx.evaluateValue(path) )
            elif 'svg' in a.content.mimetype:
                # Overlay svg
                svg_data=a.content.data
            else:
                # Overlay annotation title
                svg_data=self.controller.get_title(a)

            png_data=str(p.imagecache[a.fragment.begin])
            return self.controller.gui.overlay(png_data, svg_data)

        m=re.search('/packages/(.+?)/imagecache/(\d+)', url)
        if m:
            alias, timestamp = m.groups()
            p=self.controller.packages.get(alias)
            if p is None:
                return None
            return str(p.imagecache[int(timestamp)])
        return None

    def contextual_popup(self, ctx=None, menu=None):
        """Popup a contextual menu for the given context.
        """
        if menu is None:
            menu=Gtk.Menu()

        def open_link(i, l):
            self.open_link(l)
            return True

        def goto_position(i, pos):
            self.controller.update_status('seek', pos)
            return True

        def select_presentation(i, ap, modes):
            ap.presentation = modes[:]
            ap.refresh()
            return True

        def new_menuitem(label, action, *params):
            item=Gtk.MenuItem(label)
            if action is not None:
                item.connect('activate', action, *params)
            item.show()
            menu.append(item)
            return item

        if ctx is None:
            ctx=self.editor.get_current_context()

        if ctx:
            if hasattr(ctx[-1], '_placeholder'):
                ap=ctx[-1]._placeholder

                if getattr(ap, 'annotation', None) is not None:
                    new_menuitem(_("Annotation %s") % self.controller.get_title(ap.annotation), None)
                    new_menuitem(_("Play video"), goto_position, ap.annotation.fragment.begin)
                    new_menuitem(_("Show timestamp only"), select_presentation, ap, ['timestamp', 'link'])
                    new_menuitem(_("Show content only"), select_presentation, ap, ['content', 'link'])
                    new_menuitem(_("Show snapshot only"), select_presentation, ap, ['snapshot', 'link'])

                    new_menuitem(_("Show overlayed timestamp"), select_presentation, ap, ['timestamp', 'snapshot', 'link'])
                    new_menuitem(_("Show overlayed content"), select_presentation, ap, ['overlay', 'link'])
                elif getattr(ap, 'annotationtype', None) is not None:
                    new_menuitem(_("Annotation type %s") % self.controller.get_title(ap.annotationtype), None)
                    new_menuitem(_("display as list"), select_presentation, ap, ['list'])
                    new_menuitem(_("display as grid"), select_presentation, ap, ['grid'])
                    new_menuitem(_("display as table"), select_presentation, ap, ['table'])
                    new_menuitem(_("display as transcription"), select_presentation, ap, ['transcription'])

            l=[ m for m in ctx if m._tag == 'a' ]
            if l:
                link=dict(l[0]._attr).get('href', None)
                if link:
                    if '/media/play' in link:
                        new_menuitem(_("Play video"), open_link, link)
                    else:
                        new_menuitem(_("Open link"), open_link, link)
        return menu

    def button_press_cb(self, textview, event):
        if not (event.button == 3 or (event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS)):
            return False

        textwin=textview.get_window(Gtk.TextWindowType.TEXT)
        if event.get_window() != textwin:
            return False
        (x, y) = textview.window_to_buffer_coords(Gtk.TextWindowType.TEXT,
                                                  int(event.x),
                                                  int(event.y))
        it=textview.get_iter_at_location(x, y)
        if it is None:
            logger.warn("Error in get_iter_at_location")
            return False
        ctx=self.editor.get_current_context(it.iter)
        if not ctx:
            return False

        if event.button == 3:
            # Right button
            if hasattr(ctx[-1], '_placeholder'):
                # An annotation placeholder is here. Display popup menu.
                menu=self.contextual_popup(ctx)
                menu.popup_at_pointer(None)
            return True
        else:
            # Double click with left button
            if hasattr(ctx[-1], '_placeholder'):
                # There is an placeholder
                p = ctx[-1]._placeholder
                if isinstance(p, AnnotationPlaceholder):
                    a=ctx[-1]._placeholder.annotation
                    if a is not None:
                        self.controller.update_status('seek', a.fragment.begin)
                return False

            l=[ m for m in ctx if m._tag == 'a' ]
            if l:
                link=dict(l[0]._attr).get('href', None)
                self.open_link(link)
                return False
        return False

    def get_view (self, compact=False):
        """Generate a view widget for editing HTML."""
        vbox=Gtk.VBox()

        self.editor=HTMLEditor()
        self.editor.custom_url_loader=self.custom_url_loader
        self.editor.register_class_parser(self.class_parser)
        try:
            self.editor.set_text(self.element.data)
        except Exception as e:
            self.controller.log(_("HTML editor: cannot parse content (%s)") % str(e))

        self.editor.connect('drag-data-received', self.editor_drag_received)
        self.editor.drag_dest_set(Gtk.DestDefaults.MOTION |
                                  Gtk.DestDefaults.HIGHLIGHT |
                                  Gtk.DestDefaults.ALL,
                                  config.data.get_target_types('annotation', 'annotation-type', 'timestamp'),
                                  Gdk.DragAction.COPY | Gdk.DragAction.LINK | Gdk.DragAction.ASK )
        self.editor.connect('button-press-event', self.button_press_cb)

        self.view = Gtk.VBox()

        def sel_copy(i):
            self.editor.get_buffer().copy_clipboard(get_clipboard())
            return True

        def sel_cut(i):
            self.editor.get_buffer().cut_clipboard(get_clipboard())
            return True

        def sel_paste(i):
            self.editor.get_buffer().paste_clipboard(get_clipboard())
            return True

        def refresh(i):
            self.editor.refresh()
            return True

        def display_header_menu(i):
            m=Gtk.Menu()
            for h in (1, 2, 3):
                i=Gtk.MenuItem(_("Heading %d") % h)
                i.connect('activate', lambda w, level: self.editor.apply_html_tag('h%d' % level), h)
                m.append(i)
            m.show_all()
            m.popup(None, i, None, 1, Gtk.get_current_event_time())
            return True

        tb=Gtk.Toolbar()
        vbox.toolbar=tb
        tb.set_style(Gtk.ToolbarStyle.ICONS)
        for (icon, tooltip, action) in (
            (Gtk.STOCK_BOLD, _("Bold"), lambda i: self.editor.apply_html_tag('b')),
            (Gtk.STOCK_ITALIC, _("Italic"), lambda i: self.editor.apply_html_tag('i')),
            ("title_icon.png", _("Header"), display_header_menu),
            (None, None, None),
            (Gtk.STOCK_COPY, _("Copy"), sel_copy),
            (Gtk.STOCK_CUT, _("Cut"), sel_cut),
            (Gtk.STOCK_PASTE, _("Paste"), sel_paste),
            (None, None, None),
            (Gtk.STOCK_REFRESH, _("Refresh"), refresh),
            ):
            if not config.data.preferences['expert-mode'] and icon == Gtk.STOCK_REFRESH:
                continue
            if not icon:
                b=Gtk.SeparatorToolItem()
            else:
                b=get_pixmap_toolbutton(icon, action)
                b.set_tooltip_text(tooltip)
            tb.insert(b, -1)
            b.show()

        if self.editor.can_undo():
            b=Gtk.ToolButton(Gtk.STOCK_UNDO)
            b.connect('clicked', lambda i: self.editor.undo())
            b.set_tooltip_text(_("Undo"))
            tb.insert(b, -1)
            b.show()

        self.view.pack_start(tb, False, True, 0)
        sw=Gtk.ScrolledWindow()
        sw.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self.editor)

        context_data=ContextDisplay()
        def cursor_moved(buf, it, mark):
            if mark.get_name() == 'insert':
                context_data.set_context(self.editor.get_current_context(it))
            return True
        self.editor.get_buffer().connect('mark-set', cursor_moved)
        sw2=Gtk.ScrolledWindow()
        sw2.set_policy (Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw2.add(context_data)

        p=Gtk.HPaned()
        p.add1(sw2)
        p.add2(sw)
        # Hide by default
        p.set_position(0)
        p.show_all()
        self.view.add(p)

        def edit_wysiwyg(*p):
            vbox.foreach(vbox.remove)
            vbox.add(self.view)
            self.editing_source=False
            vbox.show_all()
            return True

        def edit_source(*p):
            if self.sourceview is None:
                self.sourceview=TextContentHandler(element=self.element,
                                                   controller=self.controller,
                                                   parent=self.parent)
                self.sourceview.widget = self.sourceview.get_view()
                b=get_pixmap_toolbutton('xml.png', edit_wysiwyg)
                b.set_tooltip_text(_("WYSIWYG editor"))
                self.sourceview.toolbar.insert(b, 0)

            vbox.foreach(vbox.remove)
            vbox.add(self.sourceview.widget)
            self.editing_source=True
            vbox.show_all()
            return True

        b=get_pixmap_toolbutton('xml.png', edit_source)
        b.set_tooltip_text(_("Edit HTML source"))
        tb.insert(b, 0)

        if config.data.preferences['prefer-wysiwyg']:
            edit_wysiwyg()
            self.editor.set_modified(False)
        else:
            edit_source()
            self.sourceview.set_modified(False)

        return vbox
