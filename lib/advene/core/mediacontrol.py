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
"""Player factory.
"""

import advene.core.config as config
import os

from gettext import gettext as _

class PlayerFactory:
    def __init__(self):
        pass

    def get_player(self, p=None):
        """Return an appropriate player instance.
        """
        if p is None:
            p=config.data.player['plugin']
        print "mediacontrol: using %s" % p
        # vlcnative is deprecated and has been removed.
        if p == 'vlcnative':
            p = 'vlcctypes'

        try:
            if p == 'vlcctypes':
                import advene.player.vlcctypes as playermodule
            elif p == 'dummy':
                import advene.player.dummy as playermodule
            elif p == 'mplayer':
                import advene.player.mplayer as playermodule
            elif p == 'gstreamer':
                import advene.player.gstreamer as playermodule
            elif p == 'gstrecorder':
                import advene.player.gstrecorder as playermodule
            elif p == 'quicktime':
                import advene.player.quicktime as playermodule
            else:
                print "Fallback to dummy module"
                import advene.player.dummy as playermodule
        except ImportError, e:
            if p != 'gstreamer':
                print "Cannot import %(player)s mediaplayer: %(error)s.\nTrying gstreamer player." % {
                    'player': p,
                    'error': str(e) }
                return self.get_player('gstreamer')
            else:
                print "Cannot import %(player)s mediaplayer: %(error)s.\nUsing dummy player." % {
                    'player': p,
                    'error': str(e) }
                import advene.player.dummy as playermodule

        return playermodule.Player()
