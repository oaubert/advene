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

import advene.util.vlclib as vlclib

from gettext import gettext as _

import gtk
import gobject

import advene.rules.elements

class LogWindow:
    def __init__ (self, controller=None, container=None, embedded=False):
        self.controller=controller
        self.container=container
        self.tooltips=gtk.Tooltips()
        if container is not None:
            embedded=True
        self.embedded=embedded
        # Timeout for messages in ms
        self.timeout=5000
        # Data is a tuple list: (timestamp, position, message, url, widget)
        # It should be sorted in timestamp order, so that the expiry
        # can be more quickly done
        self.data=[]
        self.widget=self.build_widget()        
        self.window=None

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

        if not self.embedded:
            b=gtk.Button(stock=gtk.STOCK_CLOSE)
            b.connect("clicked", self.hide)
            hb.pack_start(b, expand=False)

        w.pack_start(hb, expand=False)

        w.show_all()
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

        b=gtk.Button()
        l=gtk.Label(message)
        l.set_justify(gtk.JUSTIFY_LEFT)
        b.add(l)
        b.connect("clicked", self.goto_url, url)
        self.tooltips.set_tip(b, _("Go to %s") % url)
        hb.add(b)

        b=gtk.Button()
        l=gtk.Label(vlclib.format_time(position))
        l.set_justify(gtk.JUSTIFY_LEFT)
        b.add(l)
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

    def get_view (self):
        """Return the display widget."""
        return self.widget

    def get_widget (self):
        """Return the display widget."""
        return self.widget

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

    def hide(self, *p, **kw):
        if self.window is not None:
            self.window.hide()
        return True
    
    def popup(self):
        if self.window is None:
            self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
            self.window.set_title (_("URL stack"))
            self.window.add (self.get_widget())
            self.window.connect ("destroy-event", lambda w, e: True)
            self.window.connect ("delete-event", lambda w, e: True)
            self.window.connect ("unrealize", lambda w: True)
        self.window.show_all()
