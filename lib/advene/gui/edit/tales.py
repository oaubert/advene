import gtk

import advene.gui.views.browser

class TALESEntry:
    def __init__(self, default="", context=None, controller=None):
        self.default=""
        self.editable=True
        self.controller=controller
        if context is None and controller is not None:
            context=controller.package
        self.context=context
        self.widget=self.build_widget()

    def set_context(self, el):
        self.context=el

    def set_text(self, t):
        self.default=t
        self.entry.set_text(t)

    def get_text(self):
        return self.entry.get_text()
    
    def set_editable(self, b):
        self.editable=b
        self.entry.set_editable(b)

    def show(self):
        self.widget.show_all()
        return True

    def hide(self):
        self.widget.hide()
        return True
        
    def build_widget(self):
        hbox=gtk.HBox()
        self.entry=gtk.Entry()
        b=gtk.Button(stock=gtk.STOCK_FIND)
        b.connect("clicked", self.browse_expression)
        hbox.pack_start(self.entry, expand=True)
        hbox.pack_start(b, expand=False)
        hbox.show_all()
        return hbox
        
    def browse_expression(self, b):
        browser = advene.gui.views.browser.Browser(self.context, controller=self.controller)
        
        # FIXME: display initial value in browser
        
        def callback(e):
            if e is not None:
                self.entry.set_text(e)
            return True
        
        browser.popup_value(callback=callback)
        return True

