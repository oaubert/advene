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

        try:
            if p == 'vlcnative':
                # Should do some checks to verify it is present
                if config.data.os == 'win32':
                    return self.nativevlc_win32_import()
                else:
                    import advene.player.vlcnative as playermodule
            elif p == 'dummy':
                import advene.player.dummy as playermodule
            elif p == 'vlcorbit':
                import advene.player.vlcorbit as playermodule
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
            if config.data.os == 'linux' and p != 'gstreamer':
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

    def nativevlc_win32_import(self):
        """Specific importer for win32 vlc.
        """
        vlcpath=None
        if (config.data.player['bundled']==True
            and os.path.exists(os.path.join('.','libvlc.dll'))):

            #we need to clean vlc cache path
            # --no-plugins-cache
            print "Using included version of VLC"
            vlcpath = '.'

        if (vlcpath is None):
            vlcpath=config.data.get_registry_value('Software\\VideoLAN\\VLC','InstallDir')
            if vlcpath is None:
                # Try the Path key
                vlcpath=config.data.get_registry_value('Software\\VideoLAN\\VLC','Path')


        # FIXME: Hack: for local versions of VLC (development tree)
        # You should define the correct path in advene.ini
        if (vlcpath is None
            and os.path.exists(os.path.join( config.data.path['vlc'],
                                             'vlc.exe' ))):
            print "Using local version of VLC from %s" % config.data.path['vlc']
            vlcpath = config.data.path['vlc']

        if vlcpath is None:
            print "VLC does not seem to be installed. Using dummy player."
            import advene.player.dummy as playermodule
        else:
            print "Using VLC player module"
            # Hack needed to get the vlc module running correctly
            # (find the interfaces)
            try:
                os.chdir(vlcpath)
            except OSError:
                print "Cannot cd to %s. The player certainly won't work." % vlcpath
            import advene.player.vlcnative as playermodule

        return playermodule.Player()
