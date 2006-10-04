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
import gtk
import sre

from advene.gui.views.browser import Browser
import advene.util.helper

class TALESEntry:
    """TALES expression entry widget.

    @ivar default: the default text
    @type default: string
    @ivar context: the context ('here' object)
    @type context: object
    @ivar controller: the controller
    @type controller: advene.core.controller
    """
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
        return advene.util.helper.is_valid_tales(expr)

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
        # FIXME: display initial value in browser
        def callback(e):
            if e is not None:
                self.entry.set_text(e)
            return True

        browser = Browser(self.context,
                          controller=self.controller,
                          callback=callback)
        browser.popup()
        return True

