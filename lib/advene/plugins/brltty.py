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

from gettext import gettext as _

try:
    import brlapi
except ImportError:
    brlapi = None

from advene.rules.elements import RegisteredAction
import advene.model.tal.context

name="BrlTTY actions"

def register(controller=None):
    if brlapi is None:
        controller.log(_("BrlTTY not initialised. There will be no braille support."))
        return True
    engine=BrlEngine(controller)
    controller.register_action(RegisteredAction(
            name="Braille",
            method=engine.action_brldisplay,
            description=_("Display a message in Braille"),
            parameters={'message': _("Message to display.")},
            defaults={'message': 'annotation/content/data'},
            predefined={'message': (  
                    ( 'annotation/content/data', _("The annotation content") ),
                    )},            
            category='generic',
            ))

class BrlEngine:
    """BrlEngine.
    """
    def __init__(self, controller=None):
        self.controller=controller
        self.brlconnection=None

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

    def init_brlapi(self):
        print "Connecting brltty..."
        try:
            b = brlapi.Connection()
            b.enterTtyMode()
            self.brlconnection=b
        except brlapi.ConnectionError, e:
            self.controller.log(_("BrlTTY connection error: %s") % unicode(e))
            self.brlconnection=None

    def disconnect_brlapi(self):
        if self.brlconnection is not None:
            print "Disconnecting brltty"
            self.brlconnection.leaveTtyMode()
        
    def brldisplay(self, message):
        if self.brlconnection is None:
            self.init_brlapi()
        if self.brlconnection is not None:
            self.brlconnection.writeText(message)
        return True

    def action_brldisplay(self, context, parameters):
        """Pronounce action.
        FIXME: if we switch to python2.5, this could be made a decorator.
        """
        message=self.parse_parameter(context, parameters, 'message', _("No message"))
        self.brldisplay(message)
        return True
