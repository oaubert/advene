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
"""LogWindow plugin for Advene.

This view defines a new action, Log. It will be invoked with a text
and an associated URL as parameter.  Every invocation will be stored
in a timestamped clickable list."""

import sys
import time

import advene.core.config as config
from advene.model.package import Package
from advene.model.annotation import Annotation
from advene.model.schema import Schema, AnnotationType
from advene.model.bundle import AbstractBundle
from advene.model.view import View
from advene.gui.views import AdhocView

import advene.util.vlclib as vlclib

from gettext import gettext as _

import gtk
import gobject

import advene.rules.elements

class LogWindow(AdhocView):
    def __init__ (self, controller=None):
        self.view_name = _("URL stack")
	self.view_id = 'urlstackview'
	self.close_on_package_load = False

        self.controller=controller
        self.tooltips=gtk.Tooltips()
        # Timeout for messages in ms
        self.timeout=5000
        # Data is a tuple list: (timestamp, position, message, url, widget)
        # It should be sorted in timestamp order, so that the expiry
        # can be more quickly done
        self.data=[]
        self.widget=self.build_widget()        
        self.window=None

    def close(self, *p):
	return False

    def build_widget(self):
        w=gtk.VBox()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        w.add(sw)

        self.datawidget=gtk.VBox()
        sw.add_with_viewport(self.datawidget)

        hb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_CLEAR)
        b.connect("clicked", lambda b: self.clear_data())
        hb.pack_start(b, expand=False)

	w.buttonbox = hb

        w.pack_start(hb, expand=False)

        return w

    def clear_data(self):
        """Clear the logwindow."""
        for item in self.data:
            self.datawidget.remove(item[4])
        self.data=[]
        return True

    def update_position(self, position):
        """Regenerate the display according to the data.
        
        This method is regularly called by the GUI."""
        while self.data:
            t=time.time()
            if self.data[0][0] - t > self.timeout:
                self.datawidget.remove(self.data[0][4])
                del self.data[0]
            else:
                break
        return True

    def goto_position(self, button=None, position=None):
        self.controller.update_status("set", position)
        return True

    def goto_url(self, button=None, url=None):
        if url:
            self.controller.open_url(url)
        return True

    def add_data(self, message, position, url=None):
        # Check for identical data already pushed
        l=[ t
            for t in self.data
            if t[2] == message and t[3] == url ]
        if l:
            return True
            
        hb=gtk.HBox()

        b=gtk.Button(message)
        # Make the message left-aligned
        b.child.set_alignment(0.0, 0.5)
        b.connect("clicked", self.goto_url, url)
        self.tooltips.set_tip(b, _("Go to %s") % url)
        hb.add(b)

        b=gtk.Button(vlclib.format_time(position))
        b.child.set_alignment(0.0, 0.5)
        b.connect("clicked", self.goto_position, position)
        self.tooltips.set_tip(b, _("Go to the given position"))
        hb.pack_start(b, expand=False)

        hb.show_all()
        
        self.datawidget.pack_start(hb, expand=False)
        self.data.append( (time.time(), position, message, url, hb) )
        return True

    def pushURL (self, context, parameters):
        """Log the url and message in a specialized window"""
        if parameters.has_key('message'):
            message=context.evaluateValue(parameters['message'])
        else:
            return False
        if parameters.has_key('url'):
            url=context.evaluateValue(parameters['url'])
        else:
            url=None
        position=context.evaluateValue('player/current_position_value')
        # We log the given annotation
        self.add_data(message, position, url)

    def register_callback (self, controller=None):
        """Add the activate handler for annotations."""
        controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name='PushURL',
            method=self.pushURL,
            description=_("Push a URL on the stack"),
            parameters={'message': _("Associated message"),
                        'url': _("URL")},
            category='gui',
            ))
