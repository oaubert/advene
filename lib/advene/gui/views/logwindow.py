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
    def __init__ (self):
        self.widget=self.build_widget()
        # Data is a tuple list: (timestamp, position, message, widget)
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
            self.datawidget.remove(item[3])
        self.data=[]
        return True
    
    def update_display(self):
        """Regenerate the display according to the data."""
        # FIXME: remove obsolete messages
        pass
        
    def add_data(self, message, position):
        l=gtk.Label()
        l.set_justify(gtk.JUSTIFY_LEFT)
        l.set_markup("%s : <b>%s</b>" % (vlclib.format_time(position),
                                         message))
        l.show()
        self.datawidget.pack_start(l, expand=False)
        self.data.append( (time.time(), position, message, l) )
        return True
    
    def logMessage (self, context, parameters):
        """Log the message in a specialized window"""
        if parameters.has_key('message'):
            message=context.evaluateValue(parameters['message'])
        else:
            return False
        position=context.evaluateValue('player/current_position_value')
        # We log the given annotation
        self.add_data(message, position)
        
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
            parameters={'message': _("Message to log.")}
            ))
