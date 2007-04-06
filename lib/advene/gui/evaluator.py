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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Python expressions evaluator.
"""

# FIXME: completion of named parameters: inspect.getargspec

import os
import StringIO
import traceback
import gtk
import sre
import __builtin__
import inspect

class Window:
    def __init__(self, globals_=None, locals_=None, historyfile=None):
        if globals_ is None:
            globals_ = {}
        if locals_ is None:
            locals_ = {}
        self.globals_ = globals_
        self.locals_ = locals_
        self.historyfile=historyfile
        self.history = []
        self.history_index = None
        if self.historyfile:
            self.load_history ()
        self.widget=self.build_widget()

    def load_history(self, name=None):
        if name is None:
            name=self.historyfile
        if name is None:
            return
        try:
            f=open(name, 'r')
        except IOError:
            return
        for l in f:
            l=l.rstrip().replace('\n', "\n")
            self.history.append(l)
        f.close()
        return

    def save_history(self, name=None):
        if name is None:
            name=self.historyfile
        if name is None:
            return
        try:
            f=open(name, 'w')
        except IOError:
            return
        for l in self.history:
            l=l.replace("\n", '\n')
            f.write(l + "\n")
        f.close()
        return

    def get_widget(self):
        return self.widget

    def close(self, *p):
        self.save_history()
        if isinstance(self.widget.parent, gtk.Window):
            # Embedded in a toplevel window
            self.widget.parent.destroy()
        else:
            # Embedded in another component, just destroy the widget
            self.widget.destroy()
        return True

    def clear_output(self, *p, **kw):
        b=self.output.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)
        return True

    def save_output_cb(self, *p, **kw):
        fs = gtk.FileSelection ("Save output to...")

        def close_and_save(button, fs):
            self.save_output(filename=fs.get_filename())
            fs.destroy()
            return True

        fs.ok_button.connect_after ("clicked", close_and_save, fs)
        fs.cancel_button.connect ("clicked", lambda win: fs.destroy ())

        fs.show ()
        return True

    def save_output(self, filename=None):
        b=self.output.get_buffer()
        begin,end=b.get_bounds()
        out=b.get_text(begin, end)
        f=open(filename, "w")
        f.write(out)
        f.close()
        print "output saved to %s" % filename
        return True

    def get_expression(self):
        b=self.source.get_buffer()
        begin,end=b.get_bounds()
        return b.get_text(begin, end)

    def set_expression(self, e, clear=True):
        if clear:
            self.clear_expression()
        b=self.source.get_buffer()
        begin,end=b.get_bounds()
        b.place_cursor(end)
        b.insert_at_cursor(e)
        return True

    def clear_expression(self, *p, **kw):
        b=self.source.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)
        return True

    def log(self, *p):
        b=self.output.get_buffer()
        begin,end=b.get_bounds()
        b.place_cursor(end)
        for l in p:
            b.insert_at_cursor(l)
        return True

    def help(self, *p, **kw):
        self.clear_output()
        self.log("""Evaluator window help:

        F1: display this help
        Control-w: close the window

        Control-Return: evaluate the expression

        Control-l: clear the expression buffer
        Control-S: save the expression buffer
        Control-n: next item in history
        Control-p: previous item in history

        Control-PageUp/PageDown: scroll the output window
        Control-s: save the output

        Control-d: display completion possibilities
        Tab: perform autocompletion
        Control-h:   display docstring for element before cursor
        Control-H:   display source for element before cursor
        """)
        return True

    def previous_entry(self, *p, **kw):
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
        m=sre.match('(\w+)=(.+)', expr)
        if m is not None:
            expr=m.group(2)
        try:
            res=eval(expr, self.globals_, self.locals_)
            if typ == "doc":
                d=res.__doc__
            elif typ == "source":
                d="[Code found in " + inspect.getabsfile(res) + "]\n\n" + inspect.getsource(res)
            self.clear_output()
            if d is not None:
                self.log("%s for %s:\n\n" % (typ, repr(expr)))
                self.log(unicode(d))
            else:
                self.log("No available documentation for %s" % expr)
        except Exception, e:
            f=StringIO.StringIO()
            traceback.print_exc(file=f)
            self.clear_output()
            self.log("Error in fetching %s for %s:\n\n" % (typ, expr))
            self.log(f.getvalue())
            f.close()
        return True

    def evaluate_expression(self, *p, **kw):
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

        m=sre.match('import\s+(\S+)', expr)
        if m is not None:
            modname=m.group(1)
            self.clear_output()
            try:
                mod=__import__(modname)
                self.globals_[modname]=mod
                self.log("Successfully imported %s" % modname)
            except ImportError, e:
                self.log("Cannot import module %s:" % modname)
                f=StringIO.StringIO()
                traceback.print_exc(file=f)
                self.log(f.getvalue())
                f.close()
            return True

        # Handle variable assignment only for restricted forms of
        # variable names (so that do not mistake named parameters in
        # function calls)
        m=sre.match('([\[\]\'\"\w\.]+?)=(.+)', expr)
        if m is not None:
            symbol=m.group(1)
            expr=m.group(2)

        try:
            res=eval(expr, self.globals_, self.locals_)
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
                    m=sre.match('(.+?)\[["\']([^\[\]]+)["\']\]$', symbol)
                    if m:
                        obj, attr = m.group(1, 2)
                        try:
                            o=eval(obj, self.globals_, self.locals_)
                        except Exception, e:
                            self.log('\n\n[Unable to store data in %s[%s]]'
                                     % (obj, attr))
                            return True
                        #print "%s, %s" % (o, attr)
                        o[attr]=res
                        self.log('\n\n[Value stored in %s]' % symbol)
                        return True

                    m=sre.match('(.+)\.(\w+)$', symbol)
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
        if not m: return ''
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
        b=self.source.get_buffer()
        if b.get_selection_bounds():
            begin, end = b.get_selection_bounds()
            cursor=end
            b.place_cursor(end)
        else:
            begin,end=b.get_bounds()
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
        m=sre.match('(.+)=(.+)', expr)
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
        except (Exception, SyntaxError), e:
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
                m=sre.match('^(.+?)\.(\w*)$', expr)
                if m:
                    expr=m.group(1)
                    attr=m.group(2)
                    try:
                        res=eval(expr, self.globals_, self.locals_)
                        completion=[ a
                                     for a in dir(res)
                                     if a.startswith(attr) ]
                    except Exception, e:
                        pass
                    if attr == '':
                        # Do not display private elements by default.
                        # Display them when completion is invoked
                        # on element._ type string.
                        completion=[ a for a in completion if not a.startswith('_') ]
                else:
                    # Dict completion
                    m=sre.match('^(.+)\[[\'"]([^\]]*)', expr)
                    if m is not None:
                        obj, key=m.group(1, 2)
                        attr=key
                        try:
                            o=eval(obj, self.globals_, self.locals_)
                            completion=[ k
                                         for k in o.keys()
                                         if k.startswith(key) ]
                        except Exception, e:
                            pass
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
                    element=element.replace(attr, "")
                else:
                    if not expr.endswith('.') and not trailingdot:
                        element='.'+element
                b.insert_at_cursor(element)

            if len(completion) > 1:
                completion.sort()
                self.log("\n".join(completion))

        return True

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
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        vbox=gtk.VBox()
        window.add(vbox)

        window.vbox = gtk.VBox()
        vbox.add(window.vbox)
        if widget:
            window.vbox.add(widget)

        hb=gtk.HButtonBox()
        b=gtk.Button(stock=gtk.STOCK_CLOSE)
        b.connect("clicked", lambda b: window.destroy())
        hb.add(b)
        vbox.pack_start(hb, expand=False)

        return window

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.connect ("destroy", lambda e: window.destroy())
        window.set_title ("Python evaluation")

        window.add (self.get_widget())
        window.show_all()
        self.help()
        return window

    def build_widget(self):
        vbox=gtk.VBox()

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
        vbox.add(f)

        hb=gtk.HButtonBox()

        b=gtk.Button("_Save output")
        b.connect("clicked", self.save_output_cb)
        hb.add(b)

        b=gtk.Button("Clear _output")
        b.connect("clicked", self.clear_output)
        hb.add(b)

        b=gtk.Button("Clear _expression")
        b.connect("clicked", self.clear_expression)
        hb.add(b)

        b=gtk.Button("E_valuate expression")
        b.connect("clicked", self.evaluate_expression)
        hb.add(b)

        # So that applications can defined their own buttons
        self.hbox=hb

        vbox.pack_start(hb, expand=False)

        def key_pressed_cb (win, event):

            if event.keyval == gtk.keysyms.F1:
                self.help()
                return True
            if event.keyval == gtk.keysyms.Tab:
                item=self.display_completion()
                return True

            if event.state & gtk.gdk.CONTROL_MASK:
                if event.keyval == gtk.keysyms.w:
                    self.close()
                    return True
                elif event.keyval == gtk.keysyms.l:
                    self.clear_expression()
                    return True
                elif event.keyval == gtk.keysyms.d:
                    item=self.display_completion(completeprefix=False)
                    return True
                elif event.keyval == gtk.keysyms.h:
                    self.display_info(self.get_selection_or_cursor(), typ="doc")
                    return True
                elif event.keyval == gtk.keysyms.H:
                    self.display_info(self.get_selection_or_cursor(), typ="source")
                    return True
                elif event.keyval == gtk.keysyms.Return:
                    self.evaluate_expression()
                    return True
                elif event.keyval == gtk.keysyms.s:
                    self.save_output_cb()
                    return True
                elif event.keyval == gtk.keysyms.n:
                    self.next_entry()
                    return True
                elif event.keyval == gtk.keysyms.p:
                    self.previous_entry()
                    return True
                elif event.keyval == gtk.keysyms.Page_Down:
                    a=self.resultscroll.get_vadjustment()
                    if a.value + a.page_increment < a.upper:
                        a.value += a.page_increment
                    a.value_changed ()
                    return True
                elif event.keyval == gtk.keysyms.Page_Up:
                    a=self.resultscroll.get_vadjustment()
                    if a.value - a.page_increment >= a.lower:
                        a.value -= a.page_increment
                    a.value_changed ()
                    return True

            return False

        self.source.connect ("key-press-event", key_pressed_cb)
        self.output.connect ("key-press-event", key_pressed_cb)

        vbox.show_all()

        return vbox

if __name__ == "__main__":

    ev=Window(globals_=globals(), locals_=locals(),
              historyfile=os.path.join(os.getenv('HOME'),
                                       '.pyeval.log'))

    ev.locals_['self']=ev
    window=ev.popup()

    window.connect ("destroy", lambda e: gtk.main_quit())

    b=gtk.Button(stock=gtk.STOCK_QUIT)
    b.connect("clicked", lambda e: gtk.main_quit())
    ev.hbox.add(b)
    b.show()

    gtk.main ()
    ev.save_history(ev.historyfile)
