"""Player factory.
"""

import advene.core.config as config

from gettext import gettext as _

class PlayerFactory:
    def __init__(self):
        pass

    def get_player(self):
        if config.data.os == 'win32':
            import advene.player.dummy as playermodule
        else:
            #import advene.player.xine as playermodule
            import advene.player.vlcorbit as playermodule
            
        return playermodule.Player()

