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
import gtk
import re

import advene.core.config as config
from advene.gui.views.browser import Browser
import advene.util.helper
from advene.gui.util import dialog

re_tales=re.compile('^\$\{(.+)\}\s*$')

class TALESEntry:
    """TALES expression entry widget.

    In order to hide complexity to the user, TALES expressions are
    converted before display: TALES path expr will be represented as
    ${expr}, and string expressions string:foobar will be represented
    simply as foobar.

    @ivar default: the default text
    @type default: string
    @ivar context: the context ('here' object)
    @type context: object
    @ivar controller: the controller
    @type controller: advene.core.controller
    @ivar predefined: list of (tales_expression, title) tuples
    @type predefined: list
    """
    def __init__(self, default="", context=None, controller=None, predefined=None):
        self.default=default
        self.editable=True
        self.controller=controller
        if context is None and controller is not None:
            context=controller.package
        self.context=context
        if predefined is None:
            predefined=[]
        self.predefined=predefined

        self.widget=self.build_widget()

    def text2tales(self, t):
        """Return the TALES expression corresponding to the given text.
        """
        l=re_tales.findall(t)
        if l:
            return l[0]
        return 'string:' + t

    def tales2text(self, t):
        """Return the text representing the TALES expression.
        """
        if t.startswith('string:'):
            return t[7:].strip()
        else:
            return "${"+t+"}"

    def set_context(self, el):
        self.context=el

    def set_text(self, t):
        # Convert the value to its simplified representation
        t=self.tales2text(t)
        # Check if the new value is in self.predefined. If so, use
        # set_active_iter, else use self.entry
        m=self.combo.get_model()
        it=None
        i=m.get_iter_first()
        while i is not None:
            #print m.get_value(i, 1)
            if m.get_value(i, 1) == t:
                it=i
                break
            i=m.iter_next(i)
        if it is not None:
            self.combo.set_active_iter(it)
        else:
            self.entry.set_text(t)
        self.default=t

    def get_text(self):
        return self.text2tales(self.combo.get_current_element())

    def set_no_show_all(self, b):
        self.widget.set_no_show_all(b)

    def set_editable(self, b):
        self.editable=b
        self.entry.set_editable(b)

    def show(self):
        self.widget.show()
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
            expr=self.combo.get_current_element()
        return advene.util.helper.is_valid_tales(self.text2tales(expr))

    def build_widget(self):
        hbox=gtk.HBox()

        if self.predefined:
            preselect=self.tales2text(self.predefined[0][0])
        else:
            preselect=None
        self.combo=dialog.list_selector_widget(members=[ (self.tales2text(e), d) for (e, d) in self.predefined ],
                                               preselect=preselect,
                                               entry=True)
        self.entry=self.combo.child
        self.entry.connect('changed', lambda e: self.controller.gui.tooltips.set_tip(self.entry, self.combo.get_current_element()))
        self.controller.gui.tooltips.set_tip(self.entry, self.combo.get_current_element())

        hbox.pack_start(self.combo, expand=True)

        if config.data.preferences['expert-mode']:
            b=gtk.Button(stock=gtk.STOCK_FIND)
            b.connect('clicked', self.browse_expression)
            hbox.pack_start(b, expand=False)

        hbox.show_all()
        return hbox

    def browse_expression(self, b):
        """Launch the Browser.
        """
        # FIXME: display initial value in browser
        def callback(e):
            if e is not None:
                self.entry.set_text(self.tales2text(e))
            return True

        browser = Browser(controller=self.controller,
                          element=self.context,
                          callback=callback)
        browser.popup()
        return True

