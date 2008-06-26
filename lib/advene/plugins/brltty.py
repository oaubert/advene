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
import gobject

try:
    import brlapi
except ImportError:
    brlapi = None

import advene.core.config as config
from advene.rules.elements import RegisteredAction
import advene.model.tal.context
import advene.util.helper as helper

name="BrlTTY actions"

def register(controller=None):
    if brlapi is None:
        controller.log(_("BrlTTY not initialised. There will be no braille support."))
        method=controller.message_log
    else:
        engine=BrlEngine(controller)
        method=engine.action_brldisplay
        engine.init_brlapi()
        if engine.brlconnection is not None:
            gobject.io_add_watch(engine.brlconnection.fileDescriptor, 
                                 gobject.IO_IN,
                                 engine.input_handler)

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
            category='generic',
            ))
        
class BrlEngine:
    """BrlEngine.
    """
    def __init__(self, controller=None):
        self.controller=controller
        self.brlconnection=None
        self.currenttype=None
        self.revmap=None

    def generate_reverse_mapping(self):
        self.revmap={}
        for n, v in brlapi.__dict__.iteritems():
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
            self.controller.move_position(bookmark.begin, relative=False)
            v.set_current_bookmark(bookmark)
            self.brldisplay(bookmark.content)
            return
        if not self.brlconnection:
            return True
        k=self.brlconnection.readKey(0)
        if k is None:
            return True
        #command=self.brlconnection.expandKey(k)['command']
        if k == brlapi.KEY_SYM_RIGHT:
            # Next annotation
            if self.currenttype is None:
                self.controller.move_position(config.data.preferences['time-increment'], relative=True)
            elif self.currenttype == 'bookmarks':
                navigate_bookmark(+1)
            else:
                # Navigate to the next annotation in the type
                l=[an
                   for an in self.controller.future_begins
                   if an[0].type == self.currenttype ]
                if l:
                    self.controller.queue_action(self.controller.update_status, 'set', l[0][1])
        elif k == brlapi.KEY_SYM_LEFT:
            # Next annotation
            if self.currenttype is None:
                self.controller.move_position(-config.data.preferences['time-increment'], relative=True)
            elif self.currenttype == 'bookmarks':
                navigate_bookmark(-1)
            else:
                # Navigate to the previous annotation in the type
                pos=self.controller.player.current_position_value
                l=[ an for an in self.currenttype.annotations if an.fragment.end < pos ]
                l.sort(key=lambda a: a.fragment.begin, reverse=True)
                if l:
                    self.controller.queue_action(self.controller.update_status, 'set', l[0].fragment.begin)
        elif k == brlapi.KEY_SYM_UP or k == brlapi.KEY_SYM_DOWN:
            types=list( self.controller.package.annotationTypes )
            types.sort(key=lambda at: at.title or at.id)
            types.append( 'bookmarks' )
            try:
                i=types.index(self.currenttype)
            except ValueError:
                if k == brlapi.KEY_SYM_UP:
                    # So that i-1 => last item
                    i=0
                elif k == brlapi.KEY_SYM_DOWN:
                    # So that i+1 => first item
                    i=-1
            if k == brlapi.KEY_SYM_UP:
                i = i - 1
            elif k == brlapi.KEY_SYM_DOWN:
                i = i + 1
            try:
                self.currenttype=types[i]
            except IndexError:
                self.currenttype=None
            if self.currenttype == 'bookmarks':
                self.brldisplay('Nav. bookmarks')
            elif self.currenttype is not None:
                self.brldisplay('Nav. ' + (self.currenttype.title or self.currenttype.id))
            else:
                self.brldisplay('Nav. video')            
        elif k == brlapi.KEY_SYM_DELETE:
            # Play/pause
            self.controller.update_status("pause")
        elif k == brlapi.KEY_SYM_INSERT:
            # Insert a bookmark
            self.controller.gui.create_bookmark(self.controller.player.current_position_value)
        else:
            d=self.brlconnection.expandKeyCode(k)
            if self.revmap is None:
                self.generate_reverse_mapping()
            print "brltty: unknown key ", k, "expanded", str(d)
            if k in self.revmap:
                print "Symbol", self.revmap[k]
            elif d['command'] in self.revmap:
                print "Command", self.revmap[d['command']]
        return True

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
        self.controller.log("Connecting brltty...")
        try:
            b = brlapi.Connection()
            b.enterTtyMode()
            self.brlconnection=b
        except (brlapi.ConnectionError, TypeError), e:
            self.controller.log(_("BrlTTY connection error: %s") % unicode(e))
            self.brlconnection=None

    def disconnect_brlapi(self):
        if self.brlconnection is not None:
            self.controller.log("Disconnecting brltty")
            self.brlconnection.leaveTtyMode()
        
    def brldisplay(self, message):
        if self.brlconnection is None:
            self.init_brlapi()
        if self.brlconnection is not None:
            self.brlconnection.writeText(helper.unaccent(message))
        return True

    def action_brldisplay(self, context, parameters):
        """Pronounce action.
        FIXME: if we switch to python2.5, this could be made a decorator.
        """
        message=self.parse_parameter(context, parameters, 'message', _("No message"))
        self.brldisplay(message)
        return True
