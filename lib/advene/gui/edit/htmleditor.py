# -*- coding: utf-8 -*-
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
"""Basic pseudo-WYSIWYG HTML editor, with simple ZPT editing facilities.
"""

# Derived from facilhtml code (GPLv2 - http://code.google.com/p/facilhtml/)

# TODO:
# - Handle TAL attributes (replace, repeat, content at least)
# - Insert bullets in list items
# - Handle list item insertion

import gobject
import pygtk
pygtk.require('2.0')
import gtk
import pango
import sys
import urllib2
import socket
import StringIO
import re
from HTMLParser import HTMLParser
try:
    import gtksourceview
except ImportError:
    gtksourceview=None

if gtksourceview is None:
    textview_class=gtk.TextView
else:
    textview_class=gtksourceview.SourceView

broken_xpm="""20 22 5 1
  c black
. c gray20
X c gray60
o c gray100
O c None
.............OOOOOOO
.oooooooooo.o.OOOOOO
.oooooooooo.oo.OOOOO
.oooooooooo.ooo.OOOO
.oooooooooo.oooo.OOO
.oooooooooo . . . OO
.oooooooooo       OO
.ooooooooooooXXXX OO
.oooooooooooooXXX OO
.oooooooooooooooX OO
.o.ooooooooooo.oX OO
.. .ooo.ooo.o. .X OO
  O .o. .o. . O . OO
 OOO . O . O OOO  OO
OO OO OOO OOOO OO OO
O o OOO OOO O o OOOO
 ooo O o O o ooo OOO
 oooo ooo ooooooX OO
.oooooooooooooooX OO
.oooooooooooooooX OO
..XXXXXXXXXXXXXX. OO
OO                OO""".splitlines()

class HTMLEditor(textview_class, HTMLParser):

    # Define the inline tags (unused for now)
    __inline = [ "b", "i", "strong", "a", "em" ]

    # Here define the tags that generate their own blocks:
    __block = [ "h1", "h2", "h3", "p", "dl", "dt", "dd", "head", "table" ]

    # Here some tags that we will not render
    __ignore = [ "body", "html", "div", "title", "style", "td", "tr", "form", "span", "script" ]

    # Here some tags that are usually left open:
    __open = [ "dt", "dd", "p", "li", 'input' ]

    # Standalone tags without content
    __standalone = [ 'img', 'br' ]

    # Formats and fonts applied to Tags
    # FIXME: we should parse at least a subset of CSS to get some things right
    __formats = {
         'h1': { 'font': "sans bold 16",
                 #'justification': gtk.JUSTIFY_CENTER,
                 'pixels-above-lines': 8,
                 'pixels-below-lines': 4 },
         'h2': { 'font': "sans bold 12",
                 #'justification': gtk.JUSTIFY_CENTER,
                 'pixels-above-lines': 6,
                 'pixels-below-lines': 3 },
         'h3': { 'font': "sans bold italic 10",
                 'pixels-above-lines': 4,
                 'pixels-below-lines': 0 },
         'dl': { 'font': "sans 10" },
         'dd': { 'font': "sans 10",
                 'left-margin': 10, 'right-margin': 10,
                 'pixels-above-lines': 2,
                 'pixels-below-lines': 2 },
         'dt': { 'font': "sans bold 10",
                 'pixels-above-lines': 3,
                 'pixels-below-lines': 2,
                 'left-margin': 48 },
         'p': { 'font': "sans 10",
                'pixels-above-lines': 4,
                'pixels-below-lines': 4 },
         'b': { 'font': "sans bold 10", },
         'i': { 'font': "sans italic 10", },
         'em': { 'font': "sans italic 10", },
         'strong': { 'font': "sans bold italic 10" },
         'code': { 'font': "monospace 10" },
         'a': { 'font': "sans 10",
                'underline': pango.UNDERLINE_SINGLE,
                'foreground': 'blue' },
         'head': { 'invisible': True },
         'table': {},
         'br': {},
         'img': {},
         'li': { 'left-margin': 48 },
         'ul': {},
         'ol': {},
         'tal': { 'background': 'violet' }
         }

    def __init__(self, *cnf, **kw):
        """Initialisation of HTMLParser and TextView.

        The TextView must be editable and not be configured with
         'word-wraping', ie breaking line within words. Formatting
         from the tags is also initialized. The dictionary contains
         __tags as a list of tags in the text and present their
         positions so we can allocate the formatting.
        """
        gtk.TextView.__init__(self, *cnf, **kw)
        HTMLParser.__init__(self)
        if gtksourceview is not None:
            self.set_buffer(gtksourceview.SourceBuffer())
        self.set_editable(True)
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.__tb = self.get_buffer()
        self.__last = None
        self.__tags = { }
        for tag in self.__formats:
            self.__tb.create_tag(tag, **self.__formats[tag])
        def debug_mark(buf, m):
            if hasattr(m, '_tag'):
                print "Deleted ", m._tag
            elif hasattr(m, '_endtag'):
                print "Deleted /", m._endtag
            else:
                #print "Deleted ", m
                pass

            return True
        self.__tb.connect('mark-deleted', debug_mark)
        def delete_range(b, start, end):
            it=start.copy()
            while True:
                # Remove marks
                for m in it.get_marks():
                    if hasattr(m, '_tag'):
                        try:
                            b.remove_tag_by_name(m._tag,
                                                 b.get_iter_at_mark(m),
                                                 b.get_iter_at_mark(m._endmark))
                            b.delete_mark(m)
                            b.delete_mark(m._endmark)
                        except AttributeError, e:
                            print "Exception for %s" % m._tag, unicode(e).encode('utf-8')
                    elif  hasattr(m, '_endtag'):
                        b.remove_tag_by_name(m._endtag,
                                             b.get_iter_at_mark(m._startmark),
                                             b.get_iter_at_mark(m))
                        b.delete_mark(m)
                        b.delete_mark(m._startmark)
                if not it.forward_char() or it.equal(end):
                    break
            return True
        self.__tb.connect('delete-range', delete_range)

    def can_undo(self):
        return (gtksourceview is not None and self.get_buffer().can_undo())

    def undo(self, *p):
        b=self.get_buffer()
        if b.can_undo():
            b.undo()
        return True

    def refresh(self):
        """Refresh the current view.
        """
        self.set_text(self.get_html())

    def html_reset(self):
        """Clear the buffer contents.
        """
        # Empty the buffer
        b=self.get_buffer()
        b.delete(*b.get_bounds())

        # Clear all tags.
        self.__last = None
        self.__tags = {}

    def set_text(self, txt):
        """Set text.

        The widget TextView of PyGTK is unnecessarily complicated.
        For the addition of text, it is necessary to indicate a buffer of
        text; to format the text, we must find brands and
        tags in the text and so on. For simplicity, this method feeds the
        text to HTML parser which formats it automatically.

        The name is to follow the apparent agreement on names of
        PyGTK.
        """
        self.html_reset()
        if not isinstance(txt, unicode):
            # <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
            l=re.findall('http-equiv.+content-type.+charset=([\w\d-]+)', txt)
            if l:
                charset=l[0]
                print "Detected %s charset"
            else:
                charset='utf-8'
            try:
                txt=unicode(txt, charset)
            except UnicodeDecodeError:
                # Fallback to latin1.
                txt=unicode(txt, 'latin1')
        self.feed(txt.encode('utf-8'))
        for k, v in self.__tags.iteritems():
            if v:
                print "Unbalanced tag at end ", k

    def _get_iter_for_creating_mark(self):
        """Return an appropriate iter for creating a mark.
        """
        cursor = self.__tb.get_iter_at_mark(self.__tb.get_insert())
        m=[ m for m in cursor.get_marks() if hasattr(m, '_tag') or hasattr(m, '_endtag') ]
        if m:
            # There is already a mark/tag at the current cursor
            # position. So if we add a new mark here, we cannot
            # guarantee their order.
            # Insert an invisile chara to alleviate this problem.
            self.__tb.insert_at_cursor(u'\u2063')
            cursor = self.__tb.get_iter_at_mark(self.__tb.get_insert())
            # Safety test. Normally useles...
            m=[ m for m in cursor.get_marks() if hasattr(m, '_tag') or hasattr(m, '_endtag') ]
            if m:
                print "Strange, there should be not tag mark here."
        return cursor

    def handle_img(self, tag, attr):
        dattr=dict(attr)
        # Wait maximum 1s for connection
        socket.setdefaulttimeout(1)
        try:
            src=dattr['src']
            if not src.startswith('http:') and not src.startswith('file:'):
                src='file:'+src
            f = urllib2.urlopen(src)
            data = f.read()
            alt=dattr.get('alt', '')
        except Exception, ex:
            print "Error loading %s: %s" % (dattr.get('src', "[No src attribute]"), ex)
            data = None
            alt=dattr.get('alt', 'Broken image')
        # Process width and height attributes
        attrwidth = dattr.get('width')
        attrheight = dattr.get('height')

        if data is not None:
            # Caveat: GdkPixbuf is known not to be safe to load images
            # from network... this program is now potentially hackable
            # ;)
            loader = gtk.gdk.PixbufLoader()

            def set_size(pixbuf, width, height):
                if attrwidth and attrheight:
                    # Both are specified. Simple use them.
                    width, height = attrwidth, attrheight
                elif attrwidth and not attrheight:
                    # Only width is specified.
                    height = 1.0 * attrheight / attrwidth * width
                    width = attrwidth
                elif attrheight and not attrwidth:
                    width = 1.0 * attrwidth / attrheight * height
                    height = attrheight
                loader.set_size(int(width), int(height))
            if attrwidth or attrheight:
                loader.connect('size-prepared', set_size)
            try:
                loader.write(data)
                loader.close()
                pixbuf = loader.get_pixbuf()
            except gobject.GError:
                pixbuf=None
        else:
            pixbuf=None

        if pixbuf is None:
            pixbuf=gtk.gdk.pixbuf_new_from_xpm_data(broken_xpm)

        cursor = self._get_iter_for_creating_mark()
        if pixbuf is not None:
            self.__tb.insert_pixbuf(cursor, pixbuf)
            pixbuf._tag=tag
            pixbuf._attr=attr
        else:
            mark = self.__tb.create_mark(None, cursor, True)
            mark._tag=tag
            mark._attr=attr
            mark._startmark=mark
            mark._endmark=mark
            self.__tb.insert(cursor, alt)

    def handle_starttag(self, tag, attr):
        """Tag opening.

        Here we handle the opening of tags. When opened, the tag has
        registered its position so that the format is applied later,
        when closing it.
        """
        if tag == 'img':
            self.handle_img(tag, attr)
            return

        # If the tag must create a block, add a newline to the
        # paragraph, to simulate the effect of blocking.
        # Additionally, blocks 'close' Tag previously open.
        if tag in self.__block:
            # FIXME: this is too brutal. We should check if we are
            # starting a new block while the previous one is not
            # closed, and then automarically close.
            #if self.__last in self.__open:
            #    self.handle_endtag(self.__last)
            self.__last = tag
            self.__tb.insert_at_cursor("\n")

        # Mark the position of tag for further application of formatting
        cursor = self._get_iter_for_creating_mark()
        mark = self.__tb.create_mark(None, cursor, True)
        mark._tag=tag
        mark._attr=attr
        mark.has_tal = [ (k, v) for (k, v) in attr if k.startswith('tal:') ]
        if tag in self.__tags:
            self.__tags[tag].append(mark)
        else:
            self.__tags[tag] = [ mark ]

        if tag == 'br':
            self.__tb.insert(cursor, '\n')
            mark._endmark=mark
            mark._startmark=mark
        elif tag == 'li' or tag == 'dt':
            # FIXME: should insert a bullet here, and maybe render
            # nested lists
            self.__tb.insert(cursor, '\n')


    def handle_data(self, data):
        """
        This method receives data from a tag which, typically, is text
        to be rendered. Simply insert the text in the widget. However,
        the rendition of HTML must treat contiguous spaces and
        characters of tabulation and fall as a simple page of blank
        space. In the first line we do this service.
        """
        data = ' '.join(data.split()) + ' '
        cursor = self.__tb.get_iter_at_mark(self.__tb.get_insert())
        self.__tb.insert(cursor, data)


    def handle_endtag(self, tag):
        """Closing tags.

        Here the tags are closed. Their positions are found and the
        formats are applied. The process is to restore the original
        position where the format should be applied (from
        handle_starttag), to obtain the Current position (after the
        text was inserted in handle_data), Text of inserting the
        labels and apply the formatting. The process is extremely
        simple.
        """
        if tag in self.__standalone:
            return
        # Create an end-mark to be able to restore HTML tags
        cursor = self._get_iter_for_creating_mark()
        mark = self.__tb.create_mark(None, cursor, True)
        mark._endtag=tag
        try:
            start_mark = self.__tags[tag].pop()
            start = self.__tb.get_iter_at_mark(start_mark)
            if tag in self.__formats:
                self.__tb.apply_tag_by_name(tag, start, cursor)
            if start_mark.has_tal:
                self.__tb.apply_tag_by_name('tal', start, cursor)
            if tag in self.__block:
                self.__tb.insert(cursor, '\n')
            mark._startmark=start_mark
            start_mark._endmark=mark
            return
        except IndexError:
            print "Unbalanced tag", tag
            mark._startmark=mark
            mark._endmark=mark
        except KeyError:
            print "Unhandled tag", tag
            mark._startmark=mark
            mark._endmark=mark

    def dump_html(self, fd=None):
        """Dump html.
        """
        if fd is None:
            fd=sys.stdout
        b=self.__tb
        i=b.get_start_iter()
        textstart=i.copy()

        # We add an index for every startmark, so that we can close
        # the corresponding endmarks with the right order
        index=0

        self._last_endtag=None

        def output_text(fr, to, tag):
            """Output text data.

            Appropriately strip starting newline if it was inserted
            after a block endtag.
            """
            txt=b.get_text(fr, to).replace(u'\u2063', '')
            if self._last_endtag in self.__block:
                txt=txt.lstrip()
            if tag in self.__block:
                txt=txt.rstrip()
            txt=txt.replace('\n', '<br>')
            self._last_endtag=None
            fd.write(txt)

        while True:
            p=i.get_pixbuf()
            if p is not None:
                fd.write("<img %s></img>" % " ".join( '%s="%s"' % (k, v) for (k, v) in p._attr ))

            for m in i.get_marks():
                if hasattr(m, '_endtag'):
                    if m._endtag in self.__standalone:
                        continue
                    output_text(textstart, i, m._endtag)
                    fd.write("</%s>" % m._endtag)
                    if m._endtag in self.__block:
                        fd.write('\n')
                    textstart=i.copy()
                    self._last_endtag=m._endtag
                elif hasattr(m, '_tag'):
                    output_text(textstart, i, m._tag)
                    if m._tag in self.__standalone:
                        closing='></%s>' % m._tag
                    else:
                        closing='>'
                    if m._attr:
                        fd.write("<%s %s%s" % (m._tag,
                                              " ".join( '%s="%s"' % (k, v) for (k, v) in m._attr ),
                                               closing))
                    else:
                        fd.write("<%s%s" % (m._tag, closing))

                    if m._tag in self.__block or m._tag == 'br':
                        fd.write('\n')
                    textstart=i.copy()

            if not i.forward_char():
                break
        # Write the remaining text
        output_text(textstart, b.get_end_iter(), 'end')
        if fd == sys.stdout:
            # fd.flush() + newline
            fd.write('\n')

    def get_current_context(self, cursor=None):
        b=self.__tb
        if cursor is None:
            cursor=b.get_iter_at_mark(b.get_insert())

        context=[]
        i=b.get_start_iter()

        while True:
            for m in i.get_marks():
                if hasattr(m, '_endtag'):
                    # Remove the opening tag from the context
                    try:
                        context.remove(m._startmark)
                    except ValueError:
                        print "Cannot remove start mark for ", m._endtag
                elif hasattr(m, '_tag') and not m._tag in self.__standalone:
                    context.append(m)
            if i.equal(cursor):
                break
            if not i.forward_char():
                break
        if i.get_pixbuf():
            context.append(i.get_pixbuf())
        return context

    def get_html(self):
        """Return the buffer contents as html.
        """
        s=StringIO.StringIO()
        self.dump_html(s)
        res=s.getvalue()
        s.close()
        return res

    def _find_enclosing_marks(self, tagname, begin, end):
        """Return the iterators and marks corresponding to tagname in the begin-end selection.
        """
        it=begin.copy()
        while True:
            t=[ m
                for m in it.get_marks()
                if hasattr(m, '_tag') and m._tag == tagname ]
            if t or not it.backward_char():
                break
        if t:
            startiter=it.copy()
            startmark=t[0]
        else:
            # We did not find any matching tag. Strange...
            return (begin, end, None, None)

        # Look for the matching endtag mark, starting from begin
        # anyway.
        endmark=startmark._endmark
        enditer=self.__tb.get_iter_at_mark(endmark)
        return (startiter, enditer, startmark, endmark)

    def apply_html_tag(self, tagname, attr=None):
        if attr is None:
            attr={}
        tag = self.__tb.get_tag_table().lookup(tagname)
        bounds=self.__tb.get_selection_bounds()
        if bounds:
            if bounds[0].has_tag(tag):
                self.__tb.remove_tag(tag, *bounds)
                startiter, enditer, startmark, endmark = self._find_enclosing_marks(tagname, *bounds)
                if startiter.equal(bounds[0]) and enditer.equal(bounds[1]):
                    # We are at the same location. Remove the tags.
                    self.__tb.delete_mark(startmark)
                    self.__tb.delete_mark(endmark)
                elif startiter.equal(bounds[0]):
                    # Remove the begin mark
                    startmark.move(bounds[1])
                elif enditer.equal(bounds[1]):
                    endmark.move(bounds[0])
                else:
                    # We are untagging a portion of a larger
                    # string. Then we must create new marks as
                    # appropriate.
                    emark = self.__tb.create_mark(None, bounds[0], True)
                    emark._endtag=tagname
                    emark._startmark=startmark
                    startmark._endmark=emark

                    smark = self.__tb.create_mark(None, bounds[1], True)
                    smark._tag=tagname
                    smark._attr=attr
                    smark.has_tal = [ (k, v) for (k, v) in attr if k.startswith('tal:') ]
                    endmark._startmark=smark
                    smark._endmark=endmark
            else:
                if tagname in self.__formats:
                    self.__tb.apply_tag(tag, *bounds)
                # Insert marks
                mark = self.__tb.create_mark(None, bounds[0], True)
                mark._tag=tagname
                mark._attr=attr
                mark.has_tal = [ (k, v) for (k, v) in attr if k.startswith('tal:') ]

                endmark = self.__tb.create_mark(None, bounds[1], True)
                endmark._endtag=tagname
                endmark._startmark=mark
                mark._endmark=endmark
        else:
            # No selection.
            start = self._get_iter_for_creating_mark()

            mark = self.__tb.create_mark(None, start, True)
            mark._tag=tagname
            mark._attr=attr
            mark.has_tal = [ (k, v) for (k, v) in attr if k.startswith('tal:') ]

            end=self._get_iter_for_creating_mark()
            if tag in self.__formats:
                self.__tb.apply_tag(tag, start, end)

            endmark = self.__tb.create_mark(None, end, True)
            endmark._endtag=tagname
            endmark._startmark=mark
            mark._endmark=endmark

class ContextDisplay(gtk.TreeView):
    def __init__(self):
        super(ContextDisplay, self).__init__()
        self.set_model(gtk.TreeStore(object, str, str))

        def edited_cell(renderer, path, newtext, col):
            model=self.get_model()
            row=model[path]
            parent=model.iter_parent(model.get_iter_from_string(path))
            mark=row[0]
            row[col]=newtext

            if parent is None:
                # Changed the tag name
                mark._tag=newtext
                mark._endmark._endtag=newtext
            else:
                # Changed an attribute. Regenerate the whole _attr
                # list
                l=[]
                it=model.iter_children(parent)
                while it is not None:
                    l.append( model.get(it, 1, 2) )
                    it=model.iter_next(it)
                mark._attr=l
                
            print "Edited", mark._tag, mark._attr
            return False

        cell=gtk.CellRendererText()
        cell.set_property('editable', True)
        cell.connect('edited', edited_cell, 1)
        self.append_column(gtk.TreeViewColumn("Name", cell, text=1))

        cell=gtk.CellRendererText()
        cell.set_property('editable', True)
        cell.connect('edited', edited_cell, 2)
        self.append_column(gtk.TreeViewColumn("Value", cell, text=2))
        
    def set_context(self, context):
        model=self.get_model()
        model.clear()
        for m in context:
            tagligne=model.append( None, ( m, m._tag, '' ) )
            for (k, v) in m._attr:
                model.append(tagligne, ( m, k, v ) )

if __name__ == "__main__":
    try:
        source=sys.argv[1]
    except IndexError:
        source=None

    t = HTMLEditor()
    if source is not None:
        t.set_text(open(source).read())
    t.show()
    sb = gtk.ScrolledWindow()
    sb.add(t)
    sb.show()

    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from evaluator import Evaluator

    ev=Evaluator(globals_=globals(), locals_=locals(),
                 historyfile=os.path.join(os.getenv('HOME'),
                                          '.pyeval.log'))

    context_data=ContextDisplay()
    def cursor_moved(buf, it, mark):
        if mark.get_name() == 'insert':
            context_data.set_context(t.get_current_context(it))
        return True
    t.get_buffer().connect('mark-set', cursor_moved)
    context_data.show()

    p=gtk.HPaned()
    sw=gtk.ScrolledWindow()
    sw.add(context_data)
    p.add1(sw)
    p.add2(sb)
    p.set_position(100)
    p.show_all()
    ev.widget.add(p)

    for (icon, action) in (
        (gtk.STOCK_CONVERT, lambda i: t.dump_html()),
        (gtk.STOCK_REFRESH, lambda i: t.refresh()),
        (gtk.STOCK_BOLD, lambda i: t.apply_html_tag('b')),
        (gtk.STOCK_ITALIC, lambda i: t.apply_html_tag('i')),
        ):
        b=gtk.ToolButton(icon)
        b.connect('clicked', action)
        ev.toolbar.insert(b, -1)
        b.show()

    if gtksourceview is not None:
        b=gtk.ToolButton(gtk.STOCK_UNDO)
        b.connect('clicked', lambda i: t.undo())
        ev.toolbar.insert(b, -1)
        b.show()

    actions={
        gtk.keysyms.b: lambda: t.apply_html_tag('b'),
        gtk.keysyms.i: lambda: t.apply_html_tag('i'),
        gtk.keysyms.z: lambda: t.dump_html(),
        }

    w=ev.popup(embedded=False)

    def key_press(win, event):
        # Control-shortcuts
        if event.state & gtk.gdk.CONTROL_MASK and event.keyval in actions:
            actions[event.keyval]()
            return True
        return False
    w.connect('key-press-event', key_press)

    t.grab_focus()
    gtk.main()
