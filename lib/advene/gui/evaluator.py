"""Python evaluator.

"""
import sys
import StringIO
import traceback
import gtk

from gettext import gettext as _

class Window:
    def __init__(self, controller=None, globals_=None, locals_=None):
        self.controller=controller
        if globals_ is None:
            globals_ = {}
        if locals_ is None:
            locals_ = {}
        self.globals_ = globals_
        self.locals_ = locals_            
        self.widget=self.build_widget()

    def get_widget(self):
        return self.widget
    
    def update_views(self, *p, **kw):
        # Hackish, but it will update the display
        self.controller.notify("PackageLoad", package=self.controller.package)
        return True

    def clear_output(self, *p, **kw):
        b=self.output.get_buffer()
        begin,end=b.get_bounds()
        b.delete(begin, end)
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
        self.log("""Evaluator window help:
        Control-Return: evaluate the expression
        Control-l: clear the expression buffer
        Control-w: close the window
        Control-u: update the interface views
        """)
        return True

    def evaluate_expression(self, *p, **kw):
        b=self.source.get_buffer()
        begin,end=b.get_bounds()
        expr=b.get_text(begin, end)
        try:
            res=eval(expr, self.globals_, self.locals_)
            self.clear_output()
            self.log(unicode(res))
        except Exception, e:
            f=StringIO.StringIO()
            traceback.print_exc(file=f)
            self.clear_output()
            self.log(f.getvalue())
            f.close()
        return True

    def popup(self):
        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_size_request (640, 400)

        def key_pressed_cb (win, event):
            
            if event.keyval == gtk.keysyms.F1:
                self.help()
                return True
            
            if event.state & gtk.gdk.CONTROL_MASK:
                if event.keyval == gtk.keysyms.w:
                    window.destroy()
                    return True
                elif event.keyval == gtk.keysyms.l:
                    self.clear_expression()
                    return True
                elif event.keyval == gtk.keysyms.Return:
                    self.evaluate_expression()
                    return True
                elif event.keyval == gtk.keysyms.u:
                    self.update_views()
                    return True
                
            return False

        window.connect ("key-press-event", key_pressed_cb)
        window.connect ("destroy", lambda e: window.destroy())
        window.set_title (_("Python evaluation"))

        window.add (self.get_widget())
        window.show_all()
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
        vbox.add(f)

        self.output=gtk.TextView()
        self.output.set_editable(False)
        self.output.set_wrap_mode (gtk.WRAP_CHAR)

        f=gtk.Frame(_("Result"))
        s=gtk.ScrolledWindow()
        s.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        s.add(self.output)
        f.add(s)
        vbox.add(f)

        hb=gtk.HButtonBox()

        b=gtk.Button(_("Update views"))
        b.connect("clicked", self.update_views)
        hb.add(b)

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
    class DummyController:
        pass

    def notify(*p, **kw):
        print "Notify (%s, %s)" % (p, kw)
        return True
    
    controller=DummyController()
    controller.notify = notify
    controller.package=None

    ev=Window(controller=controller, globals_=globals())

    window=ev.popup()

    gtk.main ()
