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
"""Player factory.
"""
import logging
logger = logging.getLogger(__name__)

import advene.core.config as config

class PlayerFactory:
    def __init__(self):
        pass

    def get_player(self, p=None):
        """Return an appropriate player instance.
        """
        if p is None:
            p=config.data.player['plugin']
        logger.info("mediacontrol: using %s", p)

        try:
            if p == 'dummy':
                import advene.player.dummy as playermodule
            elif p == 'gstreamer':
                import advene.player.gstreamer as playermodule
            elif p == 'gstrecorder':
                import advene.player.gstrecorder as playermodule
            else:
                logger.warning("Fallback to dummy module")
                import advene.player.dummy as playermodule
        except ImportError as e:
            if p != 'gstreamer':
                logger.warning("Cannot import %(player)s mediaplayer: %(error)s.\nTrying gstreamer player." % {
                    'player': p,
                    'error': str(e) })
                return self.get_player('gstreamer')
            else:
                logger.warning("Cannot import %(player)s mediaplayer: %(error)s.\nUsing dummy player." % {
                    'player': p,
                    'error': str(e) })
                import advene.player.dummy as playermodule

        return playermodule.Player()
