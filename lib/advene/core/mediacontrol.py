"""Player factory.
"""

import advene.core.config as config                
import os

from gettext import gettext as _

class PlayerFactory:
    def __init__(self):
        pass

    def get_player(self):
        if config.data.os == 'win32':
            # Try to determine wether VLC is installed or not
            vlcpath=config.data.get_registry_value('Software\\VideoLAN\\VLC','Path')
            
            # FIXME: Hack: for local versions of VLC (development tree)
            # You should define the correct path in advene.ini
            if (vlcpath is None
                and os.path.exists(os.sep.join( (config.data.path['vlc'],
                                                 'vlc.exe') ))):
                print "Using local version of VLC from %s" % config.data.path['vlc']
                vlcpath = config.data.path['vlc']
                
            if vlcpath is None:
                print _("VLC does not seem to be installed. Using dummy player.")
                import advene.player.dummy as playermodule
            else:
                print _("Using VLC player module")
                # Hack needed to get the vlc module running correctly
                # (find the interfaces)
                try:
                    os.chdir(vlcpath)
                except:
                    print "Cannot cd to %s. The player certainly won't work." % vlcpath
                import advene.player.vlcnative as playermodule
        else:
            #import advene.player.xine as playermodule

            p=config.data.player['plugin']

            if p == 'vlcnative':
                # Should do some checks to verify it is present
                import advene.player.vlcnative as playermodule
            elif p == 'dummy':
                import advene.player.dummy as playermodule
            elif p == 'vlcorbit':
                import advene.player.vlcorbit as playermodule
            else:
                import advene.player.dummy as playermodule
           
        return playermodule.Player()
