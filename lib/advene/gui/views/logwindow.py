"""LogWindow plugin for Advene.

This view defines a new action, Log. It will be invoked with a HTML
fragment as parameter.  Every invocation will be stored in a
timestamped clickable list."""

import sys
import time

# Advene part
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
    def __init__ (self, controller=None):
        self.widget=self.build_widget()
        self.controller=controller
        self.tooltips=gtk.Tooltips()
        # Data is a tuple list: (timestamp, position, message, url, widget)
        self.data=[]

    def build_widget(self):
        w=gtk.VBox()

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        w.add(sw)

        self.datawidget=gtk.VBox()
        sw.add_with_viewport(self.datawidget)

        hb=gtk.HBox()
        b=gtk.Button(stock=gtk.STOCK_CLEAR)
        b.connect("clicked", lambda b: self.clear_data())
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

    def update_display(self):
        """Regenerate the display according to the data."""
        # FIXME: remove obsolete messages
        pass

    def goto_position(self, button=None, position=None):
        self.controller.update_status("set", position)
        return True

    def goto_url(self, button=None, url=None):
        if url:
            self.controller.open_url(url)
        return True

    def add_data(self, message, position, url=None):
        
        hb=gtk.HBox()

        b=gtk.Button(vlclib.format_time(position))
        b.connect("clicked", self.goto_position, position)
        self.tooltips.set_tip(b, _("Go to the given position"))
        hb.pack_start(b, expand=False)

        b=gtk.Button(message)
        b.connect("clicked", self.goto_url, url)
        self.tooltips.set_tip(b, _("Go to %s") % url)
        hb.add(b)

        hb.show_all()
        
        self.datawidget.pack_start(hb, expand=False)
        self.data.append( (time.time(), position, message, url, hb) )
        return True

    def logMessage (self, context, parameters):
        """Log the message in a specialized window"""
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
            name='LogMessage',
            method=self.logMessage,
            description=_("Log a message"),
            parameters={'message': _("Message to log."),
                        'url': _("Corresponding URL.")}
            ))
