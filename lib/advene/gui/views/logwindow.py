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
"""LogWindow plugin for Advene.

This view defines a new action, Log. It will be invoked with a text
and an associated URL as parameter.  Every invocation will be stored
in a timestamped clickable list."""

import time

from gettext import gettext as _

from gi.repository import Gtk

from advene.gui.views import AdhocView
import advene.rules.elements
import advene.util.helper as helper

name="Link view plugin"

def register(controller):
    controller.register_viewclass(LogWindow)

class LogWindow(AdhocView):
    view_name = _("Links")
    view_id = 'linksview'
    tooltip = _("URL stack")
    def __init__ (self, controller=None, parameters=None):
        super(LogWindow, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = (
            (_("Clear"), self.clear_data),
            )

        self.options={}

        self.controller=controller
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
        w=Gtk.VBox()

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        w.add(sw)

        self.datawidget=Gtk.VBox()
        sw.add_with_viewport(self.datawidget)

        return w

    def clear_data(self, *p):
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
        self.controller.update_status("seek", position)
        return True

    def goto_url(self, button=None, url=None):
        if url:
            self.controller.open_url(url)
        return True

    def add_data(self, message, position, url=None):
        # Check for identical data already pushed
        items = [ t
                  for t in self.data
                  if t[2] == message and t[3] == url ]
        if items:
            return True

        hb = Gtk.HBox()

        b = Gtk.Button(message)
        # Make the message left-aligned
        b.get_child().set_alignment(0.0, 0.5)
        b.connect('clicked', self.goto_url, url)
        b.set_tooltip_text(_("Go to %s") % url)
        hb.add(b)

        b = Gtk.Button(helper.format_time(position))
        b.get_child().set_alignment(0.0, 0.5)
        b.connect('clicked', self.goto_position, position)
        b.set_tooltip_text(_("Go to the given position"))
        hb.pack_start(b, False, True, 0)

        hb.show_all()

        self.datawidget.pack_start(hb, False, True, 0)
        self.data.append( (time.time(), position, message, url, hb) )
        return True

    def pushURL (self, context, parameters):
        """Log the url and message in a specialized window"""
        if 'message' in parameters:
            message = context.evaluateValue(parameters['message'])
        else:
            return False
        if 'url' in parameters:
            url = context.evaluateValue(parameters['url'])
        else:
            url = None
        position = context.evaluateValue('player/current_position_value')
        # We log the given annotation
        self.add_data(message, position, url)

    def register_callback (self, controller=None):
        """Add the activate handler for annotations."""
        controller.event_handler.register_action(advene.rules.elements.RegisteredAction(
            name='PushURL',
            method=self.pushURL,
            description=_("Push a URL on the stack"),
            parameters={'message': _("Description of the URL"),
                        'url': _("URL")},
            defaults={'message': "string:"+_("See the Advene website"),
                      'url': 'string:http://www.advene.org/'},
            predefined={'message': (
                ('string:'+_('See the Advene website'), _('See the Advene website')),
                ('string:'+_('See the annotation'), _('See the annotation')),
            ),
                        'url': (
                            ('string:http://www.advene.org/', _("The Advene website")),
                            ('annotation/absolute_url', _("The annotation URL")),
                        )},
            category='gui',
            ))
        self.callback=controller.event_handler.internal_rule (event="PackageActivate",
                                                              method=self.clear_data)

    def unregister_callback (self, controller=None):
        controller.event_handler.remove_rule(self.callback, type_="internal")
