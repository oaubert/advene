"""Python expressions evaluator.

"""
import sys
import StringIO
import traceback
import gtk
import sre
import __builtin__

from gettext import gettext as _

class Window:
    def __init__(self, globals_=None, locals_=None):
        if globals_ is None:
            globals_ = {}
        if locals_ is None:
            locals_ = {}
        self.globals_ = globals_
        self.locals_ = locals_
        self.widget=self.build_widget()

    def get_widget(self):
        return self.widget

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
        Control-Return: evaluate the expression
        Control-l: clear the expression buffer
        Control-w: close the window
        Control-u: update the interface views
        Control-PageUp/PageDown: scroll the result window
        Control-d: display completion possibilities
        Tab: perform autocompletion
        ?:   display docstring for element before cursor
        """)
        return True

    def display_doc(self, expr):
        if expr == '':
            self.help()
            return True
        for c in ('.', '(', ' '):
            while expr.endswith(c):
                expr=expr[:-1]
        m=sre.match('(\w+)=(.+)', expr)
        if m is not None:
            expr=m.group(2)                
        try:
            res=eval(expr, self.globals_, self.locals_)
            d=res.__doc__
            self.clear_output()
            self.log(unicode(d))
        except Exception, e:
            f=StringIO.StringIO()
            traceback.print_exc(file=f)
            self.clear_output()
            self.log(f.getvalue())
            f.close()
        return True
        
    def evaluate_expression(self, *p, **kw):
        b=self.source.get_buffer()
        begin,end=b.get_bounds()
        expr=b.get_text(begin, end)
        symbol=None
        m=sre.match('(\w+)=(.+)', expr)
        if m is not None:
            symbol=m.group(1)
            expr=m.group(2)
        if expr.endswith('?'):
            self.display_doc(expr[:-1])
            return True
        try:
            res=eval(expr, self.globals_, self.locals_)
            self.clear_output()
            self.log(unicode(res))
            if symbol is not None:
                self.log('\n\n[Value stored in %s]' % symbol)
                self.locals_[symbol]=res
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
        begin,end=b.get_bounds()
        cursor=b.get_iter_at_mark(b.get_insert())
        expr=b.get_text(begin, cursor)
        if expr.endswith('.'):
            expr=expr[:-1]
        for c in (' ', '(', ','):
            if c in expr:
                expr=expr[expr.rindex(c)+1:]
                print "using %s from %s" % (expr, c)
        m=sre.match('(\w+)=(.+)', expr)
        if m is not None:
            expr=m.group(2)
        completion=None

        attr=None
        try:
            res=eval(expr, self.globals_, self.locals_)
            completion=dir(res)
        except Exception, e:
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
                m=sre.match('^(.+?)\.(\w+)$', expr)
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
                    if not expr.endswith('.'):
                        element='.'+element
                b.insert_at_cursor(element)

            if len(completion) > 1:
                self.log("\n".join(completion))
        
        return True

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        
        def key_pressed_cb (win, event):

            if event.keyval == gtk.keysyms.F1:
                self.help()
                return True
            if event.keyval == gtk.keysyms.Tab:
                item=self.display_completion()                
                return True

            if event.keyval == gtk.keysyms.question:
                b=self.source.get_buffer()
                begin,end=b.get_bounds()
                cursor=b.get_iter_at_mark(b.get_insert())
                expr=b.get_text(begin, cursor)
                self.display_doc(expr)
                return True

            if event.state & gtk.gdk.CONTROL_MASK:
                if event.keyval == gtk.keysyms.w:
                    window.destroy()
                    return True
                elif event.keyval == gtk.keysyms.l:
                    self.clear_expression()
                    return True
                elif event.keyval == gtk.keysyms.d:
                    item=self.display_completion(completeprefix=False)
                    return True
                elif event.keyval == gtk.keysyms.Return:
                    self.evaluate_expression()
                    return True
                elif event.keyval == gtk.keysyms.u:
                    self.update_views()
                    return True
                elif event.keyval == gtk.keysyms.s:
                    self.save_output_cb()
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

        window.connect ("key-press-event", key_pressed_cb)
        window.connect ("destroy", lambda e: window.destroy())
        window.set_title (_("Python evaluation"))

        window.add (self.get_widget())
        window.show_all()
        self.help()
        return window

    def build_widget(self):
        vbox=gtk.VBox()

        self.source=gtk.TextView ()
        self.source.set_editable(True)
        self.source.set_wrap_mode (gtk.WRAP_CHAR)

        f=gtk.Frame(_("Expression"))
        s=gtk.ScrolledWindow()
        s.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        s.add(self.source)
        f.add(s)
        vbox.pack_start(f, expand=False)

        self.output=gtk.TextView()
        self.output.set_editable(False)
        self.output.set_wrap_mode (gtk.WRAP_CHAR)

        f=gtk.Frame(_("Result"))
        self.resultscroll=gtk.ScrolledWindow()
        self.resultscroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.resultscroll.add(self.output)
        f.add(self.resultscroll)
        vbox.add(f)

        hb=gtk.HButtonBox()

        b=gtk.Button(_("Clear output"))
        b.connect("clicked", self.clear_output)
        hb.add(b)

        b=gtk.Button(_("Clear expression"))
        b.connect("clicked", self.clear_expression)
        hb.add(b)

        b=gtk.Button(_("Evaluate expression"))
        b.connect("clicked", self.evaluate_expression)
        hb.add(b)

        vbox.pack_start(hb, expand=False)

        vbox.show_all()

        return vbox

if __name__ == "__main__":
    ev=Window(globals_=globals())

    window=ev.popup()

    gtk.main ()
