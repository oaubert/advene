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
"""Python expression evaluator.
"""

import os
import time
import StringIO
import traceback
import gtk
import gobject
import re
import __builtin__
import inspect

class Evaluator:
    """Evaluator window. Shortcuts:
    
    F1: display this help
    
    Control-Return: evaluate the expression. If a selection is
    active, evaluate only the selection.
    
    Control-l: clear the expression buffer
    Control-S: save the expression buffer
    Control-n: next item in history
    Control-p: previous item in history
    Control-b: store the expression as a bookmark
    Control-space: display bookmarks
    
    Control-PageUp/PageDown: scroll the output window
    Control-s: save the output
    
    Control-d: display completion possibilities
    Tab: perform autocompletion
    Control-h:   display docstring for element before cursor
    Control-H:   display source for element before cursor
    Control-f:   auto-fill parameters for a function
    """
    def __init__(self, globals_=None, locals_=None, historyfile=None, display_info_widget=False):
        if globals_ is None:
            globals_ = {}
        if locals_ is None:
            locals_ = {}
        self.globals_ = globals_
        self.locals_ = locals_
        # display info widget (additional messages)
        self.display_info_widget = display_info_widget

        # History and bookmark handling
        self.history = []
        self.bookmarks = []

        self.historyfile=historyfile
        if historyfile:
            self.bookmarkfile=historyfile + '-bookmarks'
        else:
            self.bookmarkfile=None
        self.load_history()

        self.current_entry=None
        self.history_index = None

        self.control_shortcuts = {
            gtk.keysyms.w: self.close,
            gtk.keysyms.b: self.add_bookmark,
            gtk.keysyms.space: self.display_bookmarks,
            gtk.keysyms.l: self.clear_expression,
            gtk.keysyms.f: lambda: self.fill_method_parameters(),
            gtk.keysyms.d: lambda: self.display_completion(completeprefix=False),
            gtk.keysyms.h: lambda: self.display_info(self.get_selection_or_cursor(), typ="doc"),
            gtk.keysyms.H: lambda: self.display_info(self.get_selection_or_cursor(), typ="source"),
            gtk.keysyms.Return: self.evaluate_expression,
            gtk.keysyms.s: self.save_output_cb,
            gtk.keysyms.n: self.next_entry,
            gtk.keysyms.p: self.previous_entry,
            gtk.keysyms.Page_Down: lambda: self.scroll_output(+1),
            gtk.keysyms.Page_Up: lambda: self.scroll_output(-1),
            }

        self.widget=self.build_widget()

    def true_cb(self, *p):
        self.status_message("true_cb", str(p))
        return True

    def false_cb(self, *p):
        self.status_message("false_cb", str(p))
        return False

    def load_history(self, name=None):
        """Load a command history and return the data.
        """
        if name is None:
            name=self.historyfile
            bname=self.bookmarkfile
        else:
            bname=name + '-bookmarks'
        self.history=self.load_data(name)
        self.bookmarks=self.load_data(bname)
        return

    def save_history(self, name=None):
        if name is None:
            name=self.historyfile
            bname=self.bookmarkfile
        else:
            bname=name + '-bookmarks'
        self.save_data(self.history, self.historyfile)
        self.save_data(self.bookmarks, self.bookmarkfile)
        return

    def load_data(self, name):
        res=[]
        if name is None:
            return res
        try:
            f=open(name, 'r')
        except IOError:
            return []
        for l in f:
            res.append(l.rstrip())
        f.close()
        return res

    def save_data(self, data, name):
        """Save a command history.
        """
        if name is None:
            return
        try:
            f=open(name, 'w')
        except IOError:
            return []
        for l in data:
            f.write(l + "\n")
        f.close()
        return

    def close(self, *p):
        """Close the window.

        Closing the window will save the history, if a history file
        was specified.
        """
        self.save_history()

        if isinstance(self.widget.parent, gtk.Window):
            # Embedded in a toplevel window
            self.widget.parent.destroy()
        else:
            # Embedded in another component, just destroy the widget
            self.widget.destroy()
        return True

    def clear_output(self, *p, **kw):
        """Clear the output window.
        """
        b=self.output.get_buffer()
        b.delete(*b.get_bounds())
        return True

    def scroll_output(self, d):
        a=self.resultscroll.get_vadjustment()
        new=a.value + d * a.page_increment
        if  new >= 0 and new < a.upper:
            a.value=new
        a.value_changed ()
        return True

    def save_output_cb(self, *p, **kw):
        """Callback for save output functionality.
        """
        fs = gtk.FileSelection ("Save output to...")

        def close_and_save(button, fs):
            """Save the output and close the fileselector dialog.
            """
            self.save_output(filename=fs.get_filename())
            fs.destroy()
            return True

        fs.ok_button.connect_after ('clicked', close_and_save, fs)
        fs.cancel_button.connect('clicked', lambda win: fs.destroy ())

        fs.show ()
        return True

    def save_output(self, filename=None):
        """Save the output window content to the given filename.
        """
        b=self.output.get_buffer()
        begin,end=b.get_bounds()
        out=b.get_text(begin, end)
        f=open(filename, "w")
        f.write(out)
        f.close()
        self.status_message("Output saved to %s" % filename)
        return True

    def get_expression(self):
        """Return the content of the expression window.
        """
        b=self.source.get_buffer()
        return b.get_text(*b.get_bounds())

    def set_expression(self, e, clear=True):
        """Set the content of the expression window.
        """
        if clear:
            self.clear_expression()
        b=self.source.get_buffer()
        begin,end=b.get_bounds()
        b.place_cursor(end)
        b.insert_at_cursor(e)
        return True

    def clear_expression(self, *p, **kw):
        """Clear the expression window.
        """
        b=self.source.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)
        return True

    def log(self, *p):
        """Log a message.
        """
        b=self.output.get_buffer()
        end=b.get_bounds()[1]
        b.place_cursor(end)
        for l in p:
            b.insert_at_cursor(l)
        return True

    def help(self, *p, **kw):
        """Display the help message.
        """
        self.clear_output()
        self.log(self.__doc__)
        return True

    def previous_entry(self, *p, **kw):
        """Display the previous entry from the history.
        """
        if not self.history:
            return True
        e=self.get_expression()
        if self.history_index is None:
            # New search. Save current entry.
            self.current_entry=e
            self.history_index = len(self.history) - 1
        else:
            self.history_index -= 1
        # Keep at the beginning
        if self.history_index < 0:
            self.history_index = 0
        self.set_expression(self.history[self.history_index])
        return True

    def next_entry(self, *p, **kw):
        """Display the next entry from the history.
        """
        if not self.history:
            return True
        e=self.get_expression()
        if self.history_index is None:
            # New search. Save current entry.
            self.current_entry=e
            self.history_index=None
        else:
            self.history_index += 1
        if self.history_index is None or self.history_index >= len(self.history):
            self.history_index=None
            self.set_expression(self.current_entry)
        else:
            self.set_expression(self.history[self.history_index])
        return True

    def display_info(self, expr, typ="doc"):
        """Display information about expr.

        Typ can be "doc" or "source"
        """
        if expr == '':
            self.help()
            return True
        p=expr.rfind('(')
        if p > expr.rfind(')'):
            # We are in a non-closed open brace, so we start from there
            expr=expr[p+1:]
        for c in ('+', '-', '*', '/'):
            p=expr.rfind(c)
            if p >= 0:
                expr=expr[p+1:]
        for c in ('.', '(', ' '):
            while expr.endswith(c):
                expr=expr[:-1]
        m=re.match('(\w+)=(.+)', expr)
        if m is not None:
            expr=m.group(2)
        try:
            res=eval(expr, self.globals_, self.locals_)
            if typ == "doc":
                d=res.__doc__
            elif typ == "source":
                try:
                    d="[Code found in " + inspect.getabsfile(res)
                except TypeError:
                    d=None
                try:
                    source=inspect.getsource(res)
                except TypeError:
                    source=''
                if d and source:
                    d += "]\n\n" + source
            self.clear_output()
            if d is not None:
                self.log("%s for %s:\n\n" % (typ, repr(expr)))
                self.log(unicode(d))
            else:
                if typ == 'doc':
                    self.log("No available documentation for %s" % expr)
                else:
                    self.log("Cannot get source for %s" % expr)
        except Exception:
            f=StringIO.StringIO()
            traceback.print_exc(file=f)
            self.clear_output()
            self.log("Error in fetching %s for %s:\n\n" % (typ, expr))
            self.log(f.getvalue())
            f.close()
        return True

    def evaluate_expression(self, *p, **kw):
        """Evaluate the expression.

        If a part of the expression is selected, then evaluate only
        the selection.
        """
        b=self.source.get_buffer()
        if b.get_selection_bounds():
            begin, end = b.get_selection_bounds()
            b.place_cursor(end)
        else:
            begin,end=b.get_bounds()
        expr=b.get_text(begin, end)
        if (not self.history) or self.history[-1] != expr:
            self.history.append(expr)
        symbol=None

        m=re.match('import\s+(\S+)', expr)
        if m is not None:
            modname=m.group(1)
            self.clear_output()
            try:
                mod=__import__(modname)
                self.globals_[modname]=mod
                self.log("Successfully imported %s" % modname)
            except ImportError:
                self.log("Cannot import module %s:" % modname)
                f=StringIO.StringIO()
                traceback.print_exc(file=f)
                self.log(f.getvalue())
                f.close()
            return True

        # Handle variable assignment only for restricted forms of
        # variable names (so that we do not mistake named parameters
        # in function calls)
        m=re.match('([\[\]\'\"\w\.-]+?)=(.+)', expr)
        if m is not None:
            symbol=m.group(1)
            expr=m.group(2)

        try:
            t0=time.time()
            res=eval(expr, self.globals_, self.locals_)
            self.status_message("Execution time: %f s" % (time.time() - t0))
            self.clear_output()
            try:
                self.log(unicode(res))
            except UnicodeDecodeError:
                self.log(unicode(repr(res)))
            if symbol is not None:
                if not '.' in symbol and not symbol.endswith(']'):
                    self.log('\n\n[Value stored in %s]' % symbol)
                    self.locals_[symbol]=res
                else:
                    m=re.match('(.+?)\[["\']([^\[\]]+)["\']\]$', symbol)
                    if m:
                        obj, attr = m.group(1, 2)
                        try:
                            o=eval(obj, self.globals_, self.locals_)
                        except Exception, e:
                            self.log('\n\n[Unable to store data in %s[%s]]:\n%s'
                                     % (obj, attr, e))
                            return True
                        #print "%s, %s" % (o, attr)
                        o[attr]=res
                        self.log('\n\n[Value stored in %s]' % symbol)
                        return True

                    m=re.match('(.+)\.(\w+)$', symbol)
                    if m:
                        obj, attr = m.group(1, 2)
                        try:
                            o=eval(obj, self.globals_, self.locals_)
                        except Exception, e:
                            self.log('\n\n[Unable to store data in %s.%s]'
                                     % (obj, attr))
                            return True
                        setattr(o, attr, res)
                        self.log('\n\n[Value stored in %s]' % symbol)

        except Exception, e:
            f=StringIO.StringIO()
            traceback.print_exc(file=f)
            self.clear_output()
            self.log(f.getvalue())
            f.close()
        return True

    def commonprefix(self, m):
        "Given a list of strings, returns the longest common leading component"
        if not m:
            return ''
        a, b = min(m), max(m)
        lo, hi = 0, min(len(a), len(b))
        while lo < hi:
            mid = (lo+hi)//2 + 1
            if a[lo:mid] == b[lo:mid]:
                lo = mid
            else:
                hi = mid - 1
        return a[:hi]

    def display_completion(self, completeprefix=True):
        """Display the completion.
        """
        b=self.source.get_buffer()
        if b.get_selection_bounds():
            begin, end = b.get_selection_bounds()
            cursor=end
            b.place_cursor(end)
        else:
            begin,end=b.get_bounds()
            cursor=b.get_iter_at_mark(b.get_insert())
        expr=b.get_text(begin, cursor)
        if expr.endswith('.'):
            expr=expr[:-1]
            trailingdot=True
        else:
            trailingdot=False
        p=expr.rfind('(')
        if p > expr.rfind(')'):
            # We are in a non-closed open brace, so we start from there
            expr=expr[p+1:]
        for c in ('+', '-', '*', '/', ' ', ',', '\n'):
            p=expr.rfind(c)
            if p >= 0:
                expr=expr[p+1:]
        m=re.match('(.+)=(.+)', expr)
        if m is not None:
            expr=m.group(2)
        completion=None

        attr=None

        try:
            res=eval(expr, self.globals_, self.locals_)
            completion=dir(res)
            # Do not display private elements by default.
            # Display them when completion is invoked
            # on element._ type string.
            completion=[ a for a in completion if not a.startswith('_') ]
        except (Exception, SyntaxError):
            if not '.' in expr:
                # Beginning of an element name (in global() or locals() or builtins)
                v=dict(self.globals_)
                v.update(self.locals_)
                v.update(__builtin__.__dict__)
                completion=[ a
                             for a in v
                             if a.startswith(expr) ]
                attr=expr
            else:
                # Maybe we have the beginning of an attribute.
                m=re.match('^(.+?)\.(\w*)$', expr)
                if m:
                    expr=m.group(1)
                    attr=m.group(2)
                    try:
                        res=eval(expr, self.globals_, self.locals_)
                        completion=[ a
                                     for a in dir(res)
                                     if a.startswith(attr) ]
                    except Exception, e:
                        print "Exception when trying to complete attribute for %s starting with %s:\n%s" % (expr, attr, e)
                        self.status_message("Completion exception for %s starting with %s" % (expr, attr))
                    if completion and attr == '':
                        # Do not display private elements by default.
                        # Display them when completion is invoked
                        # on element._ type string.
                        completion=[ a for a in completion if not a.startswith('_') ]
                else:
                    # Dict completion
                    m=re.match('^(.+)\[[\'"]([^\]]*)', expr)
                    if m is not None:
                        obj, key=m.group(1, 2)
                        attr=key
                        try:
                            o=eval(obj, self.globals_, self.locals_)
                            completion=[ k
                                         for k in o.keys()
                                         if k.startswith(key) ]
                        except Exception, e:
                            print "Exception when trying to complete dict key for %s starting with %s:\n%s" % (expr, attr, e)
                            self.status_message("Completion exception for %s starting with %s" % (expr, attr))

        self.clear_output()
        if completion is None:
            f=StringIO.StringIO()
            traceback.print_exc(file=f)
            self.log(f.getvalue())
            f.close()
        else:
            element=""
            if len(completion) == 1:
                element = completion[0]
            elif completeprefix:
                element = self.commonprefix(completion)

            if element != "":
                # Got one completion. We can complete the buffer.
                if attr is not None:
                    element=element.replace(attr, "", 1)
                else:
                    if not expr.endswith('.') and not trailingdot:
                        element='.'+element
                b.insert_at_cursor(element)
                if attr is not None and attr+element in completion:
                    self.fill_method_parameters()

            if len(completion) > 1:
                completion.sort()
                self.log("\n".join(completion))

        return True

    def fill_method_parameters(self):
        """Fill the parameter names for the method before cursor.
        """
        b=self.source.get_buffer()
        if b.get_selection_bounds():
            begin, end = b.get_selection_bounds()
            cursor=end
            b.place_cursor(end)
        else:
            begin,end=b.get_bounds()
            cursor=b.get_iter_at_mark(b.get_insert())
        expr=b.get_text(begin, cursor)

        m=re.match('.+[=\(\[\s](.+?)$', expr)
        if m:
            expr=m.group(1)
        try:
            res=eval(expr, self.globals_, self.locals_)
        except (Exception, SyntaxError):
            res=None
        if inspect.ismethod(res):
            res=res.im_func
        args=None
        if inspect.isfunction(res):
            # Complete with getargspec
            (args, varargs, varkw, defaults)=inspect.getargspec(res)
            if args and args[0] == 'self':
                args.pop(0)
                if defaults:
                    n=len(defaults)
                    cp=args[:-n]
                    cp.extend("=".join( (k, repr(v)) ) for (k, v) in zip(args[-n:], defaults))
                    args=cp
            if varargs:
                args.append("*" + varargs)
            if varkw:
                args.append("**" + varkw)
        #elif inspect.isbuiltin(res) and res.__doc__:
        # isbuiltin does not work
        elif callable(res) and res.__doc__:
            # Extract parameters from docstring
            args=re.findall('\((.*?)\)', res.__doc__.splitlines()[0])

        if args is not None:
            beginmark=b.create_mark(None, cursor, True)
            b.insert_at_cursor("(%s)" % ", ".join(args))
            it=b.get_iter_at_mark(beginmark)
            it.forward_char()
            if not args:
                # No args inserted. Put the cursor after the closing
                # parenthesis.
                it.forward_char()
            b.move_mark_by_name('selection_bound', it)
            b.delete_mark(beginmark)

    def get_selection_or_cursor(self):
        """Return either the selection or what is on the line before the cursor.
        """
        b=self.source.get_buffer()
        if b.get_selection_bounds():
            begin, end = b.get_selection_bounds()
            cursor=end
            b.place_cursor(end)
        else:
            cursor=b.get_iter_at_mark(b.get_insert())
            begin=b.get_iter_at_line(cursor.get_line())
        expr=b.get_text(begin, cursor)
        return expr

    def make_window(self, widget=None):
        """Built the application window.
        """
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        vbox=gtk.VBox()
        window.add(vbox)

        window.vbox = gtk.VBox()
        vbox.add(window.vbox)
        if widget:
            window.vbox.add(widget)

        hb=gtk.HButtonBox()
        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect('clicked', lambda b: window.destroy())
        hb.add(b)
        vbox.pack_start(hb, expand=False)

        return window

    def popup(self, embedded=True):
        """Popup the application window.
        """
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.connect('key-press-event', self.key_pressed_cb)
        window.set_title ("Python evaluation")

        b=gtk.SeparatorToolItem()
        b.set_expand(True)
        b.set_draw(False)
        self.toolbar.insert(b, -1)

        if embedded:
            # Add the Close button to the toolbar
            b=gtk.ToolButton(gtk.STOCK_CLOSE)
            b.connect('clicked', self.close)
            self.toolbar.insert(b, -1)
            self.control_shortcuts[gtk.keysyms.w] = self.close
        else:
            # Add the Quit button to the toolbar
            b=gtk.ToolButton(gtk.STOCK_QUIT)
            b.connect('clicked', lambda b: window.destroy())
            self.toolbar.insert(b, -1)
            window.connect('destroy', lambda e: gtk.main_quit())
            self.control_shortcuts[gtk.keysyms.q] = lambda: gtk.main_quit()

        window.add (self.widget)
        window.show_all()
        window.resize(800, 600)
        self.help()
        self.source.grab_focus()
        return window

    def status_message(self, m):
        cid=self.statusbar.get_context_id('info')
        message_id=self.statusbar.push(cid, unicode(m))
        # Display the message only 4 seconds
        def undisplay():
            self.statusbar.pop(cid)
            return False
        gobject.timeout_add(4000, undisplay)

    def key_pressed_cb(self, win, event):
        """Handle key press event.
        """
        if event.keyval == gtk.keysyms.F1:
            self.help()
            return True
        if event.keyval == gtk.keysyms.Tab:
            self.display_completion()
            return True

        if event.state & gtk.gdk.CONTROL_MASK:
            action=self.control_shortcuts.get(event.keyval)
            if action:
                action()
                return True

        return False

    def add_bookmark(self, *p):
        """Add the current expression as a bookmark.
        """
        ex=self.get_expression()
        if not re.match('^\s*$', ex) and not ex in self.bookmarks:
            self.bookmarks.append(ex)
            self.save_data(self.bookmarks, self.bookmarkfile)
            self.status_message("Bookmark saved")
        return True

    def remove_bookmark(self, *p):
        """Remove the current expression from bookmarks.
        """
        ex=self.get_expression()
        if ex in self.bookmarks:
            self.bookmarks.remove(ex)
            self.save_data(self.bookmarks, self.bookmarkfile)
            self.status_message("Bookmark removed")
        return True

    def display_bookmarks(self, widget=None, *p):
        """Display bookmarks as a popup menu.
        """
        def set_expression(i, b):
            self.set_expression(b)
            return True
        if not self.bookmarks:
            return True
        m=gtk.Menu()
        for b in reversed(self.bookmarks):
            i=gtk.MenuItem(b, use_underline=False)
            i.connect('activate', set_expression, b)
            m.append(i)
        m.show_all()
        m.popup(None, widget, None, 0, gtk.get_current_event_time())
        return True

    def info(self, *p):
        if self.display_info_widget:
            for l in p:
                self.logbuffer.insert_at_cursor(time.strftime("%H:%M:%S") + l + "\n")
        return True

    def build_widget(self):
        """Build the evaluator widget.
        """
        vbox=gtk.VBox()

        tb=gtk.Toolbar()
        tb.set_style(gtk.TOOLBAR_ICONS)
        # Use small toolbar button everywhere
        gtk.settings_get_default().set_property('gtk_toolbar_icon_size', gtk.ICON_SIZE_SMALL_TOOLBAR)

        for (icon, tip, action) in (
            (gtk.STOCK_SAVE, "Save output window (C-s)", self.save_output_cb),
            (gtk.STOCK_CLEAR, "Clear output window", self.clear_output),
            (gtk.STOCK_DELETE, "Clear expression (C-l)", self.clear_expression),
            (gtk.STOCK_EXECUTE, "Evaluate expression (C-Return)", self.evaluate_expression),
            (gtk.STOCK_ADD, "Add a bookmark (C-b)", self.add_bookmark),
            (gtk.STOCK_REMOVE, "Remove a bookmark", self.remove_bookmark),
            (gtk.STOCK_INDEX, "Display bookmarks (C-Space)", self.display_bookmarks),
            ):
            b=gtk.ToolButton(icon)
            b.connect('clicked', action)
            b.set_tooltip_text(tip)
            tb.insert(b, -1)

        # So that applications can define their own buttons
        self.toolbar=tb
        vbox.pack_start(tb, expand=False)

        self.source=gtk.TextView ()
        self.source.set_editable(True)
        self.source.set_wrap_mode (gtk.WRAP_CHAR)

        f=gtk.Frame("Expression")
        s=gtk.ScrolledWindow()
        s.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        s.add(self.source)
        f.add(s)
        vbox.pack_start(f, expand=False)

        self.output=gtk.TextView()
        self.output.set_editable(False)
        self.output.set_wrap_mode (gtk.WRAP_CHAR)

        f=gtk.Frame("Result")
        self.resultscroll=gtk.ScrolledWindow()
        self.resultscroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.resultscroll.add(self.output)
        self.resultscroll.set_size_request( -1, 200 )
        f.add(self.resultscroll)

        if self.display_info_widget:
            self.logwidget = gtk.TextView()
            self.logbuffer = self.logwidget.get_buffer()
            sw=gtk.ScrolledWindow()
            sw.add(self.logwidget)

            pane=gtk.VPaned()
            vbox.add(pane)
            pane.add1(f)
            pane.pack2(sw)
        else:
            vbox.add(f)

        self.source.connect('key-press-event', self.key_pressed_cb)
        self.output.connect('key-press-event', self.key_pressed_cb)

        self.statusbar=gtk.Statusbar()
        self.statusbar.set_has_resize_grip(False)
        vbox.pack_start(self.statusbar, expand=False)

        vbox.show_all()

        return vbox

def launch(globals_=None, locals_=None, historyfile=None):
    if globals_ is None:
        globals_={}
    if locals_ is None:
        locals_={}
    if historyfile is None:
        historyfile=os.path.join(os.getenv('HOME'), '.pyeval.log')
    ev=Evaluator(globals_=globals_, locals_=locals_, historyfile=historyfile)

    ev.locals_['self']=ev
    window=ev.popup(embedded=False)
    ev.locals_['w']=window

    window.connect('destroy', lambda e: gtk.main_quit())

    gtk.main ()
    ev.save_history()

if __name__ == "__main__":
    launch(globals(), locals())
