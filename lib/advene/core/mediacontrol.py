"""Player factory.
"""

import advene.core.config as config

from gettext import gettext as _

class PlayerFactory:
    def __init__(self):
        pass

    def get_player(self):
        import advene.player.vlcplayer
        return advene.player.vlcplayer.Player()
