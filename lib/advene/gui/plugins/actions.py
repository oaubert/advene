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
import advene.core.config as config
from advene.rules.elements import RegisteredAction

import advene.model.tal.context
import textwrap
import gtk

name="Default GUI actions"

def register(controller=None):
    #print "Registering default GUI actions"

    ac=DefaultGUIActions(controller)

    controller.register_action(RegisteredAction(
            name="Message",
            method=ac.action_message_log,
            description=_("Display a message"),
            parameters={'message': _("String to display.")},
            defaults={'message': 'annotation/content/data'},
            category='gui',
            ))

    controller.register_action(RegisteredAction(
            name="Popup",
            method=ac.action_popup,
            description=_("Display a popup"),
            parameters={'message': _("String to display."),
                        'duration': _("Display duration in ms. Ignored if empty.")},
            defaults={'message': 'annotation/content/data',
                      'duration': 'annotation/fragment/duration'},
            category='gui',
            ))

    controller.register_action(RegisteredAction(
            name="Entry",
            method=ac.action_entry,
            description=_("Popup an entry box"),
            parameters={'message': _("String to display."),
                        'destination': _("Object where to store the answer (should have a content)"),
                        'duration': _("Display duration in ms. Ignored if empty.")},
            defaults={'message': 'annotation/content/data',
                      'destination': 'annotation/related',
                      'duration': 'annotation/fragment/duration'},
            category='gui',
            ))

    controller.register_action(RegisteredAction(
            name="PopupGoto",
            method=ac.action_popup_goto,
            description=_("Display a popup to go to another position"),
            parameters={'description': _("General description"),
                        'message': _("String to display."),
                        'position': _("New position"),
                        'duration': _("Display duration in ms. Ignored if empty.")},
            defaults={'description': 'annotation/content/data',
                      'message': _('string:Go to related annotation'),
                      'position': 'annotation/related/fragment/begin',
                      'duration': 'annotation/fragment/duration'},
            category='gui',
            ))

    controller.register_action(RegisteredAction(
            name="PopupURL",
            method=ac.action_popup_url,
            description=_("Display a popup linking to an URL"),
            parameters={'description': _("General description"),
                        'message': _("String to display."),
                        'url': _("URL"),
                        'duration': _("Display duration in ms. Ignored if empty.")},
            defaults={'description': 'annotation/content/data',
                      'message': _('string:Display annotation in web browser'),
                      'url': 'annotation/absolute_url',
                      'duration': 'annotation/fragment/duration'},
            category='gui',
            ))

    controller.register_action(RegisteredAction(
            name="OpenView",
            method=ac.action_open_view,
            description=_("Open a GUI view"),
            parameters={'guiview': _("View name (timeline, tree, transcription, browser, webbrowser, transcribe)"),
                        'destination': _("Destination: popup, south, east"),
                        },
            defaults={'guiview': 'string:timeline',
                      'destination': 'string:south',
                      },
            category='gui',
            ))

    controller.register_action(RegisteredAction(
            name="PopupGoto2",
            method=ac.generate_action_popup_goton(2),
            description=_("Display a popup with 2 options"),
            parameters={'description': _("General description"),
                        'message1': _("First option description"),
                        'position1': _("First position"),
                        'message2': _("Second option description"),
                        'position2': _("Second position"),
                        'duration': _("Display duration in ms. Ignored if empty.")
                        },
            defaults={'description': 'annotation/content/data',
                      'message1': 'string:Go to the beginning',
                      'position1': 'annotation/fragment/begin',
                      'message2': 'string:Go to the end',
                      'position2': 'annotation/fragment/end',
                      'duration': 'annotation/fragment/duration',
                      },
            category='gui',
            ))

    controller.register_action(RegisteredAction(
            name="PopupGoto3",
            method=ac.generate_action_popup_goton(3),
            description=_("Display a popup with 3 options"),
            parameters={'description': _("General description"),
                        'message1': _("First option description"),
                        'position1': _("First position"),
                        'message2': _("Second option description"),
                        'position2': _("Second position"),
                        'message3': _("Third option description"),
                        'position3': _("Third position"),
                        'duration': _("Display duration in ms. Ignored if empty.")
                        },
            defaults={'description': 'annotation/content/data',
                      'message1': 'string:Go to the beginning',
                      'position1': 'annotation/fragment/begin',
                      'message2': 'string:Go to the end',
                      'position2': 'annotation/fragment/end',
                      'message3': 'string:Go to related annotation',
                      'position3': 'annotation/related/fragment/begin',
                      'duration': 'annotation/fragment/duration',
                      },
            category='gui',
            ))

class DefaultGUIActions:
    def __init__(self, controller=None):
        self.controller=controller
        self.gui=self.controller.gui

    def parse_parameter(self, context, parameters, name, default_value):
        """Helper method used in actions.
        """
        if name in parameters:
            try:
                result=context.evaluateValue(parameters[name])
            except advene.model.tal.context.AdveneTalesException, e:
                try:
                    rulename=context.evaluateValue('rule')
                except advene.model.tal.context.AdveneTalesException:
                    rulename=_("Unknown rule")
                self.controller.log(_("Rule %(rulename)s: Error in the evaluation of the parameter %(parametername)s:") % {'rulename': rulename, 
                                                                                                                          'parametername': name})
                self.controller.log(unicode(e)[:160])
                result=default_value
        else:
            result=default_value
        return result

    def action_message_log (self, context, parameters):
        """Event Handler for the message action.

        Essentialy a wrapper for the X{log} method.

        The parameters should have a 'message' key.
        """
        message=self.parse_parameter(context, parameters, 'message', _("No message..."))
        message=message.replace('\\n', '\n')
        self.gui.log (message)
        return True

    def action_open_view (self, context, parameters):
        """Event Handler for the OpenView action.

        The parameters should have a 'guiview' key and a 'destination' key.
        """
        view=self.parse_parameter(context, parameters, 'guiview', None)
        dest=self.parse_parameter(context, parameters, 'destination', 'popup')
        if view is None:
            return True
        if view in ('tree', 'timeline', 'browser', 'transcribe', 'transcription'):
            self.gui.open_adhoc_view(view, destination=dest)
        else:
            self.gui.log(_("Error: undefined GUI view %s") % view)
        return True

    def action_popup (self, context, parameters):
        """Popup action.

        Displays a popup with an informational message.
        """
        message=self.parse_parameter(context, parameters, 'message', _("No message..."))
        message=message.replace('\\n', '\n')
        message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

        duration=self.parse_parameter(context, parameters, 'duration', None)
        if duration == "" or duration == 0:
            duration = None

        w=self.gui.get_illustrated_text(message)

        self.gui.popupwidget.display(widget=w, timeout=duration, title=_("Information popup"))
        return True

    def action_entry (self, context, parameters):
        """Entry action.

        Displays a popup to ask for a text string.
        """
        message=self.parse_parameter(context, parameters, 'message', _("No message..."))
        message=message.replace('\\n', '\n')
        message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

        destination=self.parse_parameter(context, parameters, 'destination', None)
        if destination is None:
            self.log(_("Empty destination for entry popup: %s") % parameters['destination'])
            return True
        if not hasattr(destination, 'content'):
            self.log(_("Destination does not have a content: %s") % parameters['destination'])
            return True

        duration=self.parse_parameter(context, parameters, 'duration', None)
        if duration == "" or duration == 0:
            duration = None

        def handle_response(button, widget, entry, dest):
            # Update the destination
            dest.content.data = entry.get_text()
            # FIXME: notify element modification
            self.gui.popupwidget.undisplay(widget)
            return True

        v=gtk.VBox()

        w=self.gui.get_illustrated_text(message)
        v.add(w)
        e=gtk.Entry()
        e.set_text(destination.content.data)
        v.add(e)
        b=gtk.Button(stock=gtk.STOCK_OK)
        b.connect("clicked", handle_response, v, e, destination)
        v.add(b)

        v.show_all()

        self.gui.popupwidget.display(widget=v, timeout=duration, title=_("Entry popup"))
        return True

    def action_popup_url (self, context, parameters):
        """PopupURL action.

        Displays a popup with a message and a linked URL.
        """
        def handle_response(button, url, widget):
            if url:
                self.controller.open_url(url)
            self.gui.popupwidget.undisplay(widget)
            return True

        description=self.parse_parameter(context, parameters, 'description', _("Follow a link"))
        description=description.replace('\\n', '\n')
        description=textwrap.fill(description, config.data.preferences['gui']['popup-textwidth'])

        message=self.parse_parameter(context, parameters, 'message', _("Click to open the URL"))
        message=message.replace('\\n', '\n')
        message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

        url=self.parse_parameter(context, parameters, 'url', 'string:http://liris.cnrs.fr/advene/')
        duration=self.parse_parameter(context, parameters, 'duration', None)
        if duration == "" or duration == 0:
            duration = None

        vbox=gtk.VBox()

        vbox.pack_start(self.gui.get_illustrated_text(description), expand=False)

        b=gtk.Button(message)
        vbox.pack_start(b, expand=False)

        b.connect("clicked", handle_response, url, vbox)

        self.gui.popupwidget.display(widget=vbox, timeout=duration, title=_("URL popup"))
        return True

    def action_popup_goto (self, context, parameters):
        """PopupGoto action.

        Displays a popup with a message and a new possible position.
        """
        def handle_response(button, position, widget):
            self.controller.update_status("set", position)
            self.gui.popupwidget.undisplay(widget)
            return True

        description=self.parse_parameter(context, parameters, 'description', _("Make a choice"))
        description=description.replace('\\n', '\n')
        description=textwrap.fill(description, config.data.preferences['gui']['popup-textwidth'])

        message=self.parse_parameter(context, parameters, 'message', _("Click to go to another position"))
        message=message.replace('\\n', '\n')
        message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

        position=self.parse_parameter(context, parameters, 'position', 0)
        duration=self.parse_parameter(context, parameters, 'duration', None)
        if duration == "" or duration == 0:
            duration = None

        vbox=gtk.VBox()

        vbox.pack_start(self.gui.get_illustrated_text(description), expand=False)

        b=gtk.Button()
        b.add(self.gui.get_illustrated_text(message, position))
        vbox.pack_start(b, expand=False)

        b.connect("clicked", handle_response, position, vbox)

        self.gui.popupwidget.display(widget=vbox, timeout=duration, title=_("Navigation popup"))
        return True

    def generate_action_popup_goton(self, size):
        def generate (context, parameters):
            """Display a popup with 'size' choices."""
            def handle_response(button, position, widget):
                self.controller.update_status("set", long(position))
                self.gui.popupwidget.undisplay(widget)
                return True

            vbox=gtk.VBox()

            description=self.parse_parameter(context,
                                             parameters, 'description', _("Make a choice"))
            description=description.replace('\\n', '\n')
            description=textwrap.fill(description,
                                      config.data.preferences['gui']['popup-textwidth'])

            vbox.add(self.gui.get_illustrated_text(description))

            for i in range(1, size+1):
                message=self.parse_parameter(context, parameters,
                                             'message%d' % i, _("Choice %d") % i)
                message=message.replace('\\n', '\n')
                message=textwrap.fill(message, config.data.preferences['gui']['popup-textwidth'])

                position=self.parse_parameter(context, parameters, 'position%d' % i, 0)

                b=gtk.Button()
                b.add(self.gui.get_illustrated_text(message, position))
                b.connect("clicked", handle_response, position, vbox)
                vbox.add(b)

            duration=self.parse_parameter(context, parameters, 'duration', None)
            if duration == "" or duration == 0:
                duration = None

            self.gui.popupwidget.display(widget=vbox, timeout=duration, title=_("Navigation popup"))
            return True
        return generate
