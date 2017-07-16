#! /usr/bin/env python3
#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert>
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
import logging
logger = logging.getLogger(__name__)

import os
import time
import io
import traceback
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GObject
import re
import builtins
import inspect
import collections

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
            Gdk.KEY_w: self.close,
            Gdk.KEY_b: self.add_bookmark,
            Gdk.KEY_space: self.display_bookmarks,
            Gdk.KEY_l: self.clear_expression,
            Gdk.KEY_f: lambda: self.fill_method_parameters(),
            Gdk.KEY_d: lambda: self.display_completion(completeprefix=False),
            Gdk.KEY_h: lambda: self.display_info(self.get_selection_or_cursor(), typ="doc"),
            Gdk.KEY_H: lambda: self.display_info(self.get_selection_or_cursor(), typ="source"),
            Gdk.KEY_Return: self.evaluate_expression,
            Gdk.KEY_s: self.save_output_cb,
            Gdk.KEY_n: self.next_entry,
            Gdk.KEY_p: self.previous_entry,
            Gdk.KEY_Page_Down: lambda: self.scroll_output(+1),
            Gdk.KEY_Page_Up: lambda: self.scroll_output(-1),
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
        self.save_data(self.history, name)
        self.save_data(self.bookmarks, bname)
        return

    def load_data(self, name):
        res=[]
        if name is None:
            return res
        try:
            f=open(name, 'r', encoding='utf-8')
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
            f=open(name, 'w', encoding='utf-8')
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

        if isinstance(self.widget.get_parent(), Gtk.Window):
            # Embedded in a toplevel window
            self.widget.get_parent().destroy()
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
        new=a.get_property("value") + d * a.get_property("page_increment")
        if new < 0:
            new = 0
        if new < a.get_property("upper"):
            a.set_property("value", new)
        a.value_changed ()
        return True

    def save_output_cb(self, *p, **kw):
        """Callback for save output functionality.
        """
        fs = Gtk.FileChooserDialog ("Save output to...",
                                    self.widget.get_toplevel(),
                                    Gtk.FileChooserAction.SAVE,
                                    ("_Cancel", Gtk.ResponseType.CANCEL,
                                     "_Save", Gtk.ResponseType.ACCEPT))
        ret = fs.run()
        if ret == Gtk.ResponseType.ACCEPT:
            self.save_output(filename=fs.get_filename())
        fs.destroy()
        return True

    def save_output(self, filename=None):
        """Save the output window content to the given filename.
        """
        b=self.output.get_buffer()
        begin,end=b.get_bounds()
        out=b.get_text(begin, end, False)
        f=open(filename, "w", encoding='utf-8')
        f.write(out)
        f.close()
        self.status_message("Output saved to %s" % filename)
        return True

    def get_expression(self):
        """Return the content of the expression window.
        """
        b=self.source.get_buffer()
        if b.get_selection_bounds():
            begin, end = b.get_selection_bounds()
            b.place_cursor(end)
        else:
            begin,end=b.get_bounds()
        return b.get_text(begin, end, False)

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
            if not isinstance(l, str):
                l = str(l, 'utf-8')
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
                self.log(str(d))
            else:
                if typ == 'doc':
                    self.log("No available documentation for %s" % expr)
                else:
                    self.log("Cannot get source for %s" % expr)
        except Exception:
            f=io.StringIO()
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
        expr = self.get_expression()
        if (not self.history) or self.history[-1] != expr:
            self.history.append(expr)
        symbol=None

        silent_mode = expr.startswith('@')
        expr = expr.lstrip('@')

        m=re.match('(from\s+(\S+)\s+)?import\s+(\S+)(\s+as\s+(\S+))?', expr)
        if m is not None:
            modname = m.group(2)
            symname = m.group(3)
            alias = m.group(5) or symname or modname
            if modname and symname:
                modname = '.'.join((modname, symname))
            self.clear_output()
            try:
                mod = __import__(modname or symname)
                self.globals_[alias]=mod
                self.log("Successfully imported %s as %s" % (modname or symname, alias))
            except ImportError:
                self.log("Cannot import module %s:" % modname)
                f=io.StringIO()
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
            if not silent_mode:
                self.clear_output()
                try:
                    view = str(res)
                except UnicodeDecodeError:
                    view = str(repr(res))
                try:
                    self.log(view)
                except Exception as e:
                    self.log("Exception in result visualisation: ", str(e))
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
                        except Exception as e:
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
                        except Exception as e:
                            self.log('\n\n[Unable to store data in %s.%s]'
                                     % (obj, attr))
                            return True
                        setattr(o, attr, res)
                        self.log('\n\n[Value stored in %s]' % symbol)

        except Exception as e:
            f=io.StringIO()
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
        expr = self.get_selection_or_cursor().lstrip('@')
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
                v.update(builtins.__dict__)
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
                    except Exception as e:
                        logger.error("Exception when trying to complete attribute for %s starting with %s:\n%s", expr, attr, e)
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
                                         for k in list(o.keys())
                                         if k.startswith(key) ]
                        except Exception as e:
                            logger.error("Exception when trying to complete dict key for %s starting with %s:\n%s", expr, attr, e)
                            self.status_message("Completion exception for %s starting with %s" % (expr, attr))

        self.clear_output()
        if completion is None:
            f=io.StringIO()
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
                b = self.source.get_buffer()
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
        expr = self.get_selection_or_cursor().lstrip('@')

        m=re.match('.+[=\(\[\s](.+?)$', expr)
        if m:
            expr=m.group(1)
        try:
            res=eval(expr, self.globals_, self.locals_)
        except (Exception, SyntaxError):
            res=None
        if inspect.ismethod(res):
            res=res.__func__
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
        elif isinstance(res, collections.Callable) and res.__doc__:
            # Extract parameters from docstring
            args=re.findall('\((.*?)\)', res.__doc__.splitlines()[0])

        if args is not None:
            b = self.source.get_buffer()
            cursor=b.get_iter_at_mark(b.get_insert())
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
        expr=b.get_text(begin, cursor, False)
        return expr

    def make_window(self, widget=None):
        """Built the application window.
        """
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        vbox=Gtk.VBox()
        window.add(vbox)

        window.vbox = Gtk.VBox()
        vbox.add(window.vbox)
        if widget:
            window.vbox.add(widget)

        hb=Gtk.HButtonBox()
        b=Gtk.Button("window-close")
        b.connect('clicked', lambda b: window.destroy())
        hb.add(b)
        vbox.pack_start(hb, False, True, 0)

        return window

    def popup(self, embedded=True):
        """Popup the application window.
        """
        window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
        window.connect('key-press-event', self.key_pressed_cb)
        window.set_title ("Python evaluation")

        b=Gtk.SeparatorToolItem()
        b.set_expand(True)
        b.set_draw(False)
        self.toolbar.insert(b, -1)

        if embedded:
            # Add the Close button to the toolbar
            b=Gtk.ToolButton("window-close")
            b.connect('clicked', self.close)
            self.toolbar.insert(b, -1)
            self.control_shortcuts[Gdk.KEY_w] = self.close
        else:
            # Add the Quit button to the toolbar
            b=Gtk.ToolButton("window-quit")
            b.connect('clicked', lambda b: window.destroy())
            self.toolbar.insert(b, -1)
            window.connect('destroy', lambda e: Gtk.main_quit())
            self.control_shortcuts[Gdk.KEY_q] = lambda: Gtk.main_quit()

        window.add (self.widget)
        window.show_all()
        window.resize(800, 600)
        self.help()
        self.source.grab_focus()
        return window

    def run(self):
        self.locals_['self'] = self
        window = self.popup(embedded=False)
        center_on_mouse(window)
        self.locals_['w'] = window
        window.connect('destroy', lambda e: Gtk.main_quit())
        Gtk.main ()
        self.save_history()

    def status_message(self, m):
        cid=self.statusbar.get_context_id('info')
        self.statusbar.push(cid, str(m))
        # Display the message only 4 seconds
        def undisplay():
            self.statusbar.pop(cid)
            return False
        GObject.timeout_add(4000, undisplay)

    def key_pressed_cb(self, win, event):
        """Handle key press event.
        """
        if event.keyval == Gdk.KEY_F1:
            self.help()
            return True
        if event.keyval == Gdk.KEY_Tab:
            self.display_completion()
            return True

        if event.get_state() & Gdk.ModifierType.CONTROL_MASK:
            action=self.control_shortcuts.get(event.keyval)
            if action:
                try:
                    action()
                except Exception:
                    f=io.StringIO()
                    traceback.print_exc(file=f)
                    self.log(f.getvalue())
                    f.close()
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
        m=Gtk.Menu()
        for b in reversed(self.bookmarks):
            i=Gtk.MenuItem(b, use_underline=False)
            i.connect('activate', set_expression, b)
            m.append(i)
        m.show_all()
        m.popup(None, widget, None, 0, 1, Gtk.get_current_event_time())
        return True

    def info(self, *p):
        if self.display_info_widget:
            for l in p:
                self.logbuffer.insert_at_cursor(time.strftime("%H:%M:%S") + l + "\n")
        return True

    def dump_tree(self, w, indent=0):
        """Dump a tree representation of the widget and its children.
        """
        tree = "%s%s %s %s\n%s%s" % (" " * indent, w.get_name(), w.get_css_name(), repr(w),
                                     " " * indent, " ".join(".%s" % cl for cl in w.get_style_context().list_classes()))
        try:
            tree = "\n\n".join((tree, "\n".join(self.dump_tree(c, indent + 8) for c in w.get_children())))
        except AttributeError:
            pass
        return tree

    def build_widget(self):
        """Build the evaluator widget.
        """
        vbox=Gtk.VBox()
        self.vbox = vbox

        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        for (icon, tip, action) in (
            (Gtk.STOCK_SAVE, "Save output window (C-s)", self.save_output_cb),
            (Gtk.STOCK_CLEAR, "Clear output window", self.clear_output),
            (Gtk.STOCK_DELETE, "Clear expression (C-l)", self.clear_expression),
            (Gtk.STOCK_EXECUTE, "Evaluate expression (C-Return)", self.evaluate_expression),
            (Gtk.STOCK_ADD, "Add a bookmark (C-b)", self.add_bookmark),
            (Gtk.STOCK_REMOVE, "Remove a bookmark", self.remove_bookmark),
            (Gtk.STOCK_INDEX, "Display bookmarks (C-Space)", self.display_bookmarks),
            ):
            b=Gtk.ToolButton(icon)
            b.connect('clicked', action)
            b.set_tooltip_text(tip)
            tb.insert(b, -1)

        # So that applications can define their own buttons
        self.toolbar=tb
        vbox.pack_start(tb, False, True, 0)

        self.source=Gtk.TextView ()
        self.source.set_editable(True)
        self.source.set_wrap_mode (Gtk.WrapMode.CHAR)

        f=Gtk.Frame.new(label="Expression")
        s=Gtk.ScrolledWindow()
        s.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        s.add(self.source)
        f.add(s)
        vbox.pack_start(f, True, True, 0)

        self.output=Gtk.TextView()
        self.output.set_editable(False)
        self.output.set_wrap_mode (Gtk.WrapMode.CHAR)

        f=Gtk.Frame.new(label="Result")
        self.resultscroll=Gtk.ScrolledWindow()
        self.resultscroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.resultscroll.add(self.output)
        self.resultscroll.set_size_request( -1, 200 )
        f.add(self.resultscroll)

        if self.display_info_widget:
            self.logwidget = Gtk.TextView()
            self.logbuffer = self.logwidget.get_buffer()
            sw=Gtk.ScrolledWindow()
            sw.add(self.logwidget)

            pane=Gtk.VPaned()
            vbox.add(pane)
            pane.add1(f)
            pane.pack2(sw)
        else:
            vbox.add(f)

        self.source.connect('key-press-event', self.key_pressed_cb)
        self.output.connect('key-press-event', self.key_pressed_cb)

        self.statusbar=Gtk.Statusbar()
        #self.statusbar.set_has_resize_grip(False)
        vbox.pack_start(self.statusbar, False, True, 0)

        vbox.show_all()

        return vbox

def center_on_mouse(w):
    """Center the given Gtk.Window on the mouse position.
    """
    root=w.get_toplevel().get_root_window()
    (screen, x, y, mod) = root.get_display().get_pointer()
    r = screen.get_monitor_geometry(screen.get_monitor_at_point(x, y))

    # Let's try to center the window on the mouse as much as possible.
    width, height = w.get_size()

    posx = max(r.x, x - int(width / 2))
    if posx + width > r.x + r.width:
        posx = r.x + r.width - width

    posy = max(r.y, y - int(height / 2))
    if posy + height > r.y + r.height:
        posy = r.y + r.height - height

    w.move(posx, posy)

def launch(globals_=None, locals_=None, historyfile=None):
    if historyfile is None:
        historyfile=os.path.join(os.getenv('HOME'), '.pyeval.log')
    ev = Evaluator(globals_=globals_, locals_=locals_, historyfile=historyfile)
    ev.run()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    launch(globals(), locals())
