import gtk
import sre

from advene.gui.views.browser import Browser

class TALESEntry:
    """TALES expression entry widget.

    @ivar default: the default text
    @type default: string
    @ivar context: the context ('here' object)
    @type context: object
    @ivar controller: the controller
    @type controller: advene.core.controller
    """
    # Root elements
    root_elements = ('here', 'nothing', 'default', 'options', 'repeat', 'request',
                     # Root elements available in STBVs
                     'package', 'annotation', 'relation', 'activeAnnotations',
                     'player', 'event',
                     # Root elements available in queries
                     'element',
                     )

    # Path elements followed by any syntax
    path_any_re = sre.compile('^(string|python):')

    # Path elements followed by a TALES expression
    path_tales_re = sre.compile('^(exists|not|nocall):(.+)')

    def __init__(self, default="", context=None, controller=None):
        self.default=default
        self.editable=True
        self.controller=controller
        if context is None and controller is not None:
            context=controller.package
        self.context=context

        self.re_id = sre.compile('^([A-Za-z0-9_%]+/?)+$')
        self.re_number = sre.compile('^\d+$')
        
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

    def is_valid(self, expr=None):
        """Return True if the expression looks like a valid TALES expression

        @param expr: the expression to check. If None, will use the current entry value.
        @type expr: string
        """
        if expr is None:
            expr=self.entry.get_text()
        # Empty expressions are considered valid
        if expr == "":
            return True
        if TALESEntry.path_any_re.match(expr):
            return True
        m=TALESEntry.path_tales_re.match(expr)
        if m:
            return self.is_valid(expr=m.group(2))
        # Check that the first element is a valid TALES root element
        root=expr.split('/', 1)[0]
        return root in TALESEntry.root_elements
    
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
        """Launch the Browser.
        """
        browser = Browser(self.context, controller=self.controller)
        
        # FIXME: display initial value in browser        
        def callback(e):
            if e is not None:
                self.entry.set_text(e)
            return True
        
        browser.popup_value(callback=callback)
        return True

