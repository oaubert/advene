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
import subprocess
import os

import advene.core.config as config
from advene.rules.elements import RegisteredAction
import advene.util.helper as helper

import advene.model.tal.context

name="Text-To-Speech actions"

def register(controller=None):
    if config.data.os == 'linux' and FestivalTTSEngine.can_run():
        engine=FestivalTTSEngine(controller)
    elif config.data.os == 'darwin':
        engine=MacOSXTTSEngine(controller)
    else:
        engine=TTSEngine(controller)
    controller.register_action(RegisteredAction(
            name="Pronounce",
            method=engine.action_pronounce,
            description=_("Pronounce a text"),
            parameters={'message': _("String to pronounce.")},
            defaults={'message': 'annotation/content/data'},
            predefined={'message': (
                    ( 'annotation/content/data', _("The annotation content") ),
                    )},
            category='generic',
            ))

class TTSEngine:
    """Generic TTSEngine.
    """
    def __init__(self, controller=None):
        self.controller=controller
        self.gui=self.controller.gui
        self.language=None

    def can_run():
        """Can this engine run ?
        """
        return True
    can_run=staticmethod(can_run)

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

    def set_language(self, language):
        self.language=language

    def pronounce(self, sentence):
        """Engine-specific method.
        """
        self.controller.log("TTS: pronounce " + sentence)
        return True

    def action_pronounce (self, context, parameters):
        """Pronounce action.
        """
        message=self.parse_parameter(context, parameters, 'message', _("No message..."))
        self.pronounce(message)
        return True

class FestivalTTSEngine(TTSEngine):
    """Festival TTSEngine.

    Note: If it is not the case (depends on the version), festival
    must be configured to play audio through the ALSA subsystem, in
    order to be able to mix it with the movie sound if necessary.

    For this, in older Festival versions (at least until 1.4.3), the
    ~/.festivalrc file must contain:

(Parameter.set 'Audio_Command "aplay -q -c 1 -t raw -f s16 -r $SR $FILE")
(Parameter.set 'Audio_Method 'Audio_Command)

    """
    def __init__(self, controller=None):
        TTSEngine.__init__(self, controller=controller)
        self.festival_path=helper.find_in_path('festival')
        self.festival_pipe=None

    def can_run():
        """Can this engine run ?
        """
        return (helper.find_in_path('festival') is not None)
    can_run=staticmethod(can_run)

    def pronounce (self, sentence):
        if self.festival_pipe is None:
            self.festival_pipe = subprocess.Popen([ self.festival_path, '--pipe' ], shell=False, stdin=subprocess.PIPE).stdin
        self.festival_pipe.write('(SayText "%s")' % sentence.replace('"', ''))
        return True


class MacOSXTTSEngine(TTSEngine):
    """MacOSX TTSEngine.
    """
    def can_run():
        """Can this engine run ?
        """
        return (config.data.os == 'darwin')
    can_run=staticmethod(can_run)

    def pronounce (self, sentence):
        subprocess.call( [ '/usr/bin/say', sentence ] )
        return True

"""
Win32: install pytts + pywin32 (from sf.net) + mfc71.dll + spchapi.exe (from www.microsoft.com/reader/developer/downloads/tts.mspx
)
On some flavors of Windows you can use:
import pyTTS

tts = pyTTS.Create()
tts.Speak('This is the sound of my voice.')

On Mac OS X you can use:
import os

http://farm.tucows.com/blog/_archives/2005/1/19/266813.html

http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/114216
http://www.daniweb.com/code/snippet326.html
http://www.mindtrove.info/articles/pytts.html
"""
