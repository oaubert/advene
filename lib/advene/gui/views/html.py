#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
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
"""HTML viewer component.

FIXME: add navigation buttons (back, history)
"""
import logging
logger = logging.getLogger(__name__)

from gi.repository import Gtk
import urllib.request, urllib.parse, urllib.error
import re

engine=None
try:
    import gi
    gi.require_version('WebKit2', '4.0')
    from gi.repository import WebKit2
    engine='webkit'
except ImportError:
    pass

from gettext import gettext as _
from advene.gui.views import AdhocView

class webkit_wrapper:
    def __init__(self, controller=None, notify=None):
        self.controller=controller
        self.notify=notify
        self.no_content_re = re.compile('^(/media/(play|pause|resume|stop)|/action/.+|/application/adhoc/.+)')
        self.widget=self.build_widget()

    def refresh(self, *p):
        self.component.reload()
        return True

    def back(self, *p):
        self.component.go_back()
        return True

    def set_url(self, url):
        self.component.load_uri(url)
        return True

    def on_load_changed(self, view, event):
        if event == WebKit2.LoadEvent.STARTED:
            self.notify(label=f"Loading  {view.get_title() or ''} - {view.get_uri()}")
        elif event == WebKit2.LoadEvent.FINISHED:
            self.notify(label=f"Loaded {view.get_title() or ''}",
                        url=view.get_uri())
        else:
            self.notify(label="Loading...  {:0.1f}%"
                        .format(view.get_estimated_load_progress()))

    def on_load_failed(self, view, event, url, error):
        self.notify(label=f"Error loading {url} - {error}")

    def on_mouse_target_changed(self, view, hit_test, mods):
        if hit_test.context_is_link():
            self.notify(label=hit_test.get_link_uri())

    def build_widget(self):
        w = WebKit2.WebView()
        w.connect('load-changed', self.on_load_changed)
        w.connect('load-failed', self.on_load_failed)
        w.connect('mouse-target-changed', self.on_mouse_target_changed)

        def update_location(url):
            l=urllib.parse.urlparse(url)
            if self.no_content_re.match(l[2]):
                # webkit does not correctly handle 204 return code.
                # Automatically go back.
                # FIXME: to be removed once webkit is fixed.
                self.back()
            if self.notify:
                self.notify(url=url)
            return False

        def update_label(c):
            if self.notify:
                self.notify(label=c.get_link_message())
            return False

        self.component = w
        s=Gtk.ScrolledWindow()
        s.add(w)

        return s

class HTMLView(AdhocView):
    _engine = engine
    view_name = _("HTML Viewer")
    view_id = 'htmlview'
    tooltip = _("Embedded HTML widget")
    def __init__ (self, controller=None, parameters=None, url=None):
        super(HTMLView, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.component=None
        self.engine = engine

        self.controller=controller
        self.widget=self.build_widget()
        if url is not None:
            self.open_url(url)

    def notify(self, url=None, label=None):
        if url is not None:
            self.current_url(url)
        if label is not None:
            self.url_label.set_text(label)
        return True

    def open_url(self, url=None):
        self.component.set_url(url)
        return True

    def build_widget(self):
        mapping={ 'webkit': webkit_wrapper,
                  None: None}
        wrapper=mapping.get(engine)
        if wrapper is None:
            w=Gtk.Label(label=_("No available HTML rendering component"))
            self.component=w
        else:
            self.component = wrapper(controller=self.controller,
                                     notify=self.notify)
            w=self.component.widget

        def utbv_menu(*p):
            if self.controller and self.controller.gui:
                m=self.controller.gui.build_utbv_menu(action=self.open_url)
                m.popup_at_pointer()
            return True

        tb=Gtk.Toolbar()
        tb.set_style(Gtk.ToolbarStyle.ICONS)

        for icon, action in (
                (Gtk.STOCK_GO_BACK, self.component.back),
                (Gtk.STOCK_REFRESH, self.component.refresh),
                (Gtk.STOCK_HOME, utbv_menu),
            ):
            b=Gtk.ToolButton(stock_id=icon)
            b.connect('clicked', action)
            tb.insert(b, -1)

        def entry_validated(e):
            self.component.set_url(self.current_url())
            return True

        self.url_entry=Gtk.Entry()
        self.url_entry.connect('activate', entry_validated)
        ti=Gtk.ToolItem()
        ti.add(self.url_entry)
        ti.set_expand(True)
        tb.insert(ti, -1)

        vbox=Gtk.VBox()

        vbox.pack_start(tb, False, True, 0)

        vbox.add(w)

        self.url_label=Gtk.Label(label='')
        self.url_label.set_alignment(0, 0)
        vbox.pack_start(self.url_label, False, True, 0)

        return vbox

    def current_url(self, url=None):
        if url is not None:
            self.url_entry.set_text(url)
        return self.url_entry.get_text()
