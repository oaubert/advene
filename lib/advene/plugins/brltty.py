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
import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
from gi.repository import GObject

try:
    import brlapi
except ImportError:
    brlapi = None

from advene.rules.elements import RegisteredAction
import advene.model.tal.context
import advene.util.helper as helper

name="BrlTTY actions"

# The Alva Satellite that we are using for experiments sends strange
# keycodes. It may be a misconfiguration of brltty that should be
# fixed, but in the meantime, hardcode appropriate values.
ALVA_LPAD_UP=536870976
ALVA_LPAD_DOWN=536870977
ALVA_LPAD_LEFT=536870973
ALVA_LPAD_RIGHT=536870975
ALVA_LPAD_LEFTLEFT=536870974
ALVA_LPAD_RIGHTRIGHT=536870960

ALVA_RPAD_UP=536870927
ALVA_RPAD_DOWN=536870928
ALVA_RPAD_LEFT=536870964
ALVA_RPAD_RIGHT=536870962
ALVA_RPAD_LEFTLEFT=536870961
ALVA_RPAD_RIGHTRIGHT=536870963

ALVA_MPAD_BUTTON0=536870942
ALVA_MPAD_BUTTON1=536870935
ALVA_MPAD_BUTTON2=536870913
ALVA_MPAD_BUTTON3=536870914
ALVA_MPAD_BUTTON4=536870936
ALVA_MPAD_BUTTON5=536870941

def register(controller=None):
    # The BrailleInput event has a 'cursor' parameter, which is the
    # cursor position, available through the request/cursor TALES
    # expression
    controller.register_event('BrailleInput', _("Input from the braille table."))
    method=controller.message_log

    if brlapi is None:
        controller.log(_("BrlTTY not installed. There will be no braille support."))
    else:
        engine=BrlEngine(controller)
        try:
            engine.init_brlapi()
            if engine.brlconnection is not None:
                GObject.io_add_watch(engine.brlconnection.fileDescriptor,
                                     GObject.IO_IN,
                                     engine.input_handler)
                method=engine.action_brldisplay
                engine.brldisplay("Advene connected")
        except:
            controller.log(_("Could not initialize BrlTTY. No braille support."))

    # Register the Braille action even if the API is not available.
    controller.register_action(RegisteredAction(
            name="Braille",
            method=method,
            description=_("Display a message in Braille"),
            parameters={'message': _("Message to display.")},
            defaults={'message': 'annotation/content/data'},
            predefined={'message': (
                    ( 'annotation/content/data', _("The annotation content") ),
                    )},
            category='external',
            ))

class InputRequest(object):
    def __init__(self, cursor):
        self.cursor=str(cursor)

class BrlEngine:
    """BrlEngine.
    """
    def __init__(self, controller=None):
        self.controller=controller
        self.brlconnection=None
        self.currenttype='scroll'
        self.revmap=None

        # Memorize current text so that it can be scrolled
        self.current_message = ""
        self.char_index = 0

    def generate_reverse_mapping(self):
        self.revmap={}
        for n, v in brlapi.__dict__.items():
            if n.startswith('KEY_'):
                self.revmap[v]=n

    def input_handler(self, source=None, condition=None):
        """Handler for BrlTTY input events.
        """
        def navigate_bookmark(direction):
            v=self.controller.gui.find_bookmark_view()
            if v is None:
                return
            cur=v.get_current_bookmark()

            if cur is None:
                if v.bookmarks:
                    # Navigate to the first bookmark
                    bookmark=v.bookmarks[0]
                else:
                    return
            else:
                index=v.bookmarks.index(cur)
                index += direction
                try:
                    bookmark=v.bookmarks[index]
                except IndexError:
                    return
            self.controller.update_status("seek", bookmark.begin)
            v.set_current_bookmark(bookmark)
            self.brldisplay(bookmark.content)
            return
        if not self.brlconnection:
            return True
        k=self.brlconnection.readKey(0)
        if k is None:
            return True
        #command=self.brlconnection.expandKey(k)['command']
        if k == brlapi.KEY_SYM_RIGHT or k == ALVA_LPAD_RIGHT or k == ALVA_MPAD_BUTTON4:
            if self.currenttype == 'scroll':
                i = self.char_index + self.brlconnection.displaySize[0]
                if i <= len(self.current_message):
                    self.char_index = i
                    self.brldisplay(self.current_message, reset_index=False)
            elif self.currenttype == 'bookmarks':
                navigate_bookmark(+1)
            else:
                # Navigate to the next annotation in the type
                l=[an
                   for an in self.controller.future_begins
                   if an[0].type == self.currenttype ]
                if l:
                    self.controller.queue_action(self.controller.update_status, 'seek', l[0][1])
        elif k == brlapi.KEY_SYM_LEFT or k == ALVA_LPAD_LEFT or k == ALVA_MPAD_BUTTON1:
            if self.currenttype == 'scroll':
                if self.char_index >= 0:
                    i = self.char_index - self.brlconnection.displaySize[0]
                    if i >= 0:
                        self.char_index = i
                    self.brldisplay(self.current_message, reset_index=False)
            elif self.currenttype == 'bookmarks':
                navigate_bookmark(-1)
            else:
                # Navigate to the previous annotation in the type
                pos=self.controller.player.current_position_value
                l=[ an for an in self.currenttype.annotations if an.fragment.end < pos ]
                l.sort(key=lambda a: a.fragment.begin, reverse=True)
                if l:
                    self.controller.queue_action(self.controller.update_status, 'seek', l[0].fragment.begin)
        elif k == brlapi.KEY_SYM_UP or k == brlapi.KEY_SYM_DOWN or k == ALVA_LPAD_UP or k == ALVA_LPAD_DOWN:
            types=list( self.controller.package.annotationTypes )
            types.sort(key=lambda at: at.title or at.id)
            types.insert(0, 'scroll' )
            types.insert(1, 'bookmarks' )
            try:
                i=types.index(self.currenttype)
            except ValueError:
                if k == brlapi.KEY_SYM_UP or k == ALVA_LPAD_UP:
                    # So that i-1 => last item
                    i=0
                elif k == brlapi.KEY_SYM_DOWN or k == ALVA_LPAD_DOWN:
                    # So that i+1 => first item
                    i=-1
            if k == brlapi.KEY_SYM_UP or k == ALVA_LPAD_UP:
                i = i - 1
            elif k == brlapi.KEY_SYM_DOWN or k == ALVA_LPAD_DOWN:
                i = i + 1
            try:
                self.currenttype = types[i]
            except IndexError:
                self.currenttype = 'scroll'

            if self.currenttype == 'bookmarks':
                self.brldisplay('Nav. bookmarks')
            elif self.currenttype == 'scroll':
                self.brldisplay('Scrolling text')
            elif self.currenttype is not None and hasattr(self.currenttype, 'id'):
                self.brldisplay('Nav. ' + (self.currenttype.title or self.currenttype.id))
            else:
                self.brldisplay('Error in navigation mode')
        elif k == brlapi.KEY_SYM_DELETE or k == ALVA_LPAD_RIGHTRIGHT:
            # Play/pause
            self.controller.update_status("pause")
        elif k == brlapi.KEY_SYM_INSERT or k == ALVA_LPAD_LEFTLEFT:
            # Insert a bookmark
            self.controller.gui.create_bookmark(self.controller.player.current_position_value)
        else:
            d=self.brlconnection.expandKeyCode(k)
            if d['command'] == brlapi.KEY_CMD_ROUTE:
                self.controller.notify('BrailleInput', request=InputRequest(d['argument']))
                return True
            if self.revmap is None:
                self.generate_reverse_mapping()
            logger.error("brltty: unknown key %s - expanded %s", k, str(d))
            if k in self.revmap:
                logger.info("Symbol %s", self.revmap[k])
            elif d['command'] in self.revmap:
                logger.info("Command %s", self.revmap[d['command']])
        return True

    def parse_parameter(self, context, parameters, name, default_value):
        """Helper method used in actions.
        """
        if name in parameters:
            try:
                result=context.evaluateValue(parameters[name])
            except advene.model.tal.context.AdveneTalesException as e:
                try:
                    rulename=context.evaluateValue('rule')
                except advene.model.tal.context.AdveneTalesException:
                    rulename=_("Unknown rule")
                self.controller.log(_("Rule %(rulename)s: Error in the evaluation of the parameter %(parametername)s:") % {'rulename': rulename,
                                                                                                                          'parametername': name})
                self.controller.log(str(e)[:160])
                result=default_value
        else:
            result=default_value
        return result

    def init_brlapi(self):
        self.controller.log("Connecting brltty...")
        try:
            b = brlapi.Connection()
            b.enterTtyMode()
            self.brlconnection=b
        except (brlapi.ConnectionError, TypeError) as e:
            self.controller.log(_("BrlTTY connection error: %s") % str(e))
            self.brlconnection=None

    def disconnect_brlapi(self):
        if self.brlconnection is not None:
            self.controller.log("Disconnecting brltty")
            self.brlconnection.leaveTtyMode()

    def brldisplay(self, message, reset_index=True):
        if self.brlconnection is None:
            self.init_brlapi()
        if reset_index:
            self.char_index = 0
        msg = helper.unaccent(message)[self.char_index:]
        if self.brlconnection is not None:
            self.brlconnection.writeText(msg)
        else:
            self.controller.log(_("Braille display: ") + msg)
        return True

    def action_brldisplay(self, context, parameters):
        """Pronounce action.
        """
        message = self.parse_parameter(context, parameters, 'message', _("No message"))
        self.current_message = message
        self.brldisplay(self.current_message)
        return True
