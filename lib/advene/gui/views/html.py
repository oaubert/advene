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
"""HTML viewer component.

FIXME: add navigation buttons (back, history)
"""

import advene.core.config as config

import gtk
import gobject
import pango
import urllib

engine=None
try:
    import gtkmozembed
    engine='mozembed'
except ImportError:
    try:
	import gtkhtml2
	engine='gtkhtml2'
    except ImportError:
	pass

from gettext import gettext as _
from advene.gui.views import AdhocView

class HTMLView(AdhocView):
    def __init__ (self, controller=None, url=None):
        self.view_name = _("HTML Viewer")
	self.view_id = 'htmlview'
	self.close_on_package_load = False
	self.component=None
	self.engine = engine
	self.history = []

	self.controller=controller
        self.widget=self.build_widget()
	if url is not None:
	    self.open_url(url)

    def build_widget(self):
	if engine is None:
	    w=gtk.Label(_("No available HTML rendering component"))
	    self.component=w
	elif engine == 'mozembed':
	    w=gtkmozembed.MozEmbed()
	    self.component=w
	elif engine == 'gtkhtml2':
	    w=gtk.ScrolledWindow()
            w.set_policy (gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

	    c=gtkhtml2.View()
	    c.document=gtkhtml2.Document()

	    def request_url(document, url, stream):
		print "request url", url, stream
		pass

	    def link_clicked(document, link):
		if self.component.current_url:
		    url=urllib.basejoin(self.component.current_url, link)
		else:
		    url=link
		self.open_url(url)
		return True

	    c.document.connect("link-clicked", link_clicked)
	    c.document.connect("request-url", request_url)
	    c.get_vadjustment().set_value(0)
	    w.set_hadjustment(c.get_hadjustment())
	    w.set_vadjustment(c.get_vadjustment())
	    c.document.clear()
	    c.set_document(c.document)
	    w.add(c)
	    self.component=c

	self.component.current_url = None

	vbox=gtk.VBox()
	vbox.add(w)
	
	buttonbox=gtk.HButtonBox()
	
	b=gtk.Button(stock=gtk.STOCK_GO_BACK)
	b.connect("clicked", self.history_back)
	buttonbox.add(b)

	vbox.pack_start(buttonbox, expand=False)

	vbox.buttonbox = buttonbox
        return vbox

    def history_back(self, *p):
	if len(self.history) <= 1:
	    self.controller.log(_("Cannot go back: first item in history"))
	else:
	    # Current URL
	    u=self.history.pop()
	    # Previous one
	    self.open_url(self.history[-1])
	return True

    def open_url(self, url):
	if not self.history:
	    self.history.append(url)	
	elif self.history[-1] != url:
	    self.history.append(url)	
	if engine is None:
	    self.component.set_text(_("No engine to render\n%s") % url)
	elif engine == 'mozembed':
	    self.component.load_url(url)
	    self.component.current_url = url
	elif engine == 'gtkhtml2':
	    d=self.component.document
	    d.clear()

	    u=urllib.urlopen(url)

	    d.open_stream(u.info().type)
	    for l in u:
		d.write_stream (l)

	    u.close()
	    d.close_stream()
	    self.component.current_url = url

	return True
