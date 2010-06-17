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
import gtk
import pango
import os

import advene.core.config as config
from advene.gui.views import AdhocView
import advene.gui.util.dialog as dialog

name="Videoplayer view plugin"

def register(controller):
    controller.register_viewclass(VideoPlayer)

class VideoPlayer(AdhocView):
    view_name = _("Video player")
    view_id = 'videoplayer'
    tooltip=_("Complementary video player")

    def __init__(self, controller=None, uri=None, parameters=None):
        super(VideoPlayer, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = [ 
            (_("Save view"), self.save_view),
            (_("Save default options"), self.save_default_options),
            (_("Select video file"), self.select_file),
            ]
        self.controller = controller
        self.registered_rules = []

        # Load options
        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        a=dict(arg)
        if uri is None and a.has_key('uri'):
            uri=a['uri']

        self.uri = uri
        # Offset in ms
        self.offset = 0

        self.widget = self.build_widget()
        if self.uri is None:
            self.select_file()
        else:
            self.set_file(self.uri)

    def register_callback (self, controller=None):
        """Add the event handlers.
        """
        self.controller.register_slave_player(self)
        self.registered_rules.extend( 
            controller.event_handler.internal_rule(event=name,
                                                   method=self.synchronize)
            for name in ('PlayerStart',
                         'PlayerStop',
                         'PlayerPause',
                         'PlayerResume',
                         'PlayerSet',
                         )
            )

    def unregister_callback (self, controller=None):
        self.controller.unregister_slave_player(self)
        for r in self.registered_rules:
            controller.event_handler.remove_rule(r, type_="internal")

    def synchronize(self, *p):
        """Synchronize the player with the main player.
        """
        if self.player is None:
            return True
        s=self.player.get_stream_information()
        ps=self.controller.player.status
        if s.status != ps:
            # Update status
            if ps == self.player.PauseStatus:
                self.player.update_status("pause")
            elif ps == self.player.PlayingStatus:
                self.player.update_status("start", self.controller.player.current_position_value)
            else:
                self.player.update_status("stop")

        # Synchronize time
        if ( (ps == self.player.PauseStatus or ps == self.player.PlayingStatus)
             and self.controller.player.current_position_value > 0
             and abs( long(s.position) + self.offset - self.controller.player.current_position_value ) > 80 ):
            self.player.update_status("set", self.controller.player.current_position_value + self.offset)
        return True

    def get_save_arguments(self):
        if self.uri is not None:
            arguments = [ ('uri', self.uri),
                          ('offset', self.offset) ]
        else:
            arguments = [ ('offset', self.offset) ]
        return self.options, arguments

    def select_file(self, button=None):
        mp=[ d for d in config.data.path['moviepath'].split(os.path.pathsep) if d != '_' ]
        if mp:
            default=mp[0]
        else:
            default=None
        fname = dialog.get_filename(title=_("Select a video file"),
                                    default_dir=default,
                                    filter='video')
        if fname is not None:
            self.set_file(fname)
        return True

    def set_file(self, fname):
        if self.player is None:
            return True
        self.uri = self.controller.locate_mediafile(fname)
        self.player.playlist_clear()
        self.player.playlist_add_item(self.uri)
        self.label.set_text(os.path.basename(self.uri))

    def reparent_prepare(self):
        if config.data.os != 'win32':
            # On X11, the socket id changes. Since we destroy the
            # origin socket before having realized the destination
            # one, we cannot maintain a valid xid for the
            # application. Create a temporary window for this.
            self.temp_window = self._popup()
        return True

    def reparent_done(self):
        if config.data.os != 'win32':
            self.drawable.connect_after('realize', self.register_drawable)
            if hasattr(self, 'temp_window') and self.temp_window is not None:
                self.temp_window.destroy()
                self.temp_window = None
        return True

    def close(self, *p):
        p=self.player
        self.player=None
        p.exit()
        super(VideoPlayer, self).close()
        return True

    def register_drawable(self, drawable):
        if self.drawable.get_parent_window() is not None:
            self.player.set_widget(self.drawable)
        return False

    def update_status(self, status, position=None):
        """Wrapper for update_status to handle offsets.
        """
        if self.player is None:
            return
        if hasattr(position, 'value'):
            position.value = position.value + self.offset
        elif position is not None:
            position = position + self.offset
        self.player.update_status(status, position)

    def _popup(self, *p):
        """Open a popup window for temporary anchoring the player video.
        """
        if self.player is None:
            return None
        w=gtk.Window()
        d=gtk.Socket()
        w.add(d)
        w.show_all()
        self.player.set_visual(d.get_id())
        return w

    def build_widget(self):
        vbox=gtk.VBox()

        self.player = self.controller.playerfactory.get_player()

        self.player.sound_mute()

        self.drawable=gtk.Socket()
        def handle_remove(socket):
            # Do not kill the widget if the application exits
            return True
        self.drawable.connect('plug-removed', handle_remove)

        black=gtk.gdk.Color(0, 0, 0)
        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            self.drawable.modify_bg (state, black)

        self.drawable.set_size_request(320, 200)


        self.toolbar=gtk.Toolbar()
        self.toolbar.set_style(gtk.TOOLBAR_ICONS)

        # Append the volume control to the toolbar
        def volume_change(scale, value):
            if self.player.sound_get_volume() != int(value * 100):
                self.player.sound_set_volume(int(value * 100))
            return True

        self.audio_volume = gtk.VolumeButton()
        self.audio_volume.set_value(self.player.sound_get_volume() / 100.0)
        ti = gtk.ToolItem()
        ti.add(self.audio_volume)
        self.audio_volume.connect('value-changed', volume_change)
        self.toolbar.insert(ti, -1)

        sync_button=gtk.ToolButton(gtk.STOCK_CONNECT)
        sync_button.set_tooltip_text(_("Synchronize"))
        sync_button.connect('clicked', self.synchronize)
        self.toolbar.insert(sync_button, -1)

        def offset_changed(spin):
            self.offset = long(spin.get_value())
            return True

        ti = gtk.ToolItem()
        spin = gtk.SpinButton(gtk.Adjustment(value = self.offset,
                                                         lower = - 24 * 60 * 60 * 1000,
                                                         upper =   24 * 60 * 60 * 1000,
                                                         step_incr = 1000 / 25,
                                                         page_incr = 1000))
        spin.get_adjustment().connect('value-changed', offset_changed)
        ti.add(spin)
        spin.set_tooltip_text(_("Offset in ms"))
        self.toolbar.insert(ti, -1)

        self.label = gtk.Label()
        self.label.set_alignment(0, 0)
        self.label.modify_font(pango.FontDescription("sans 10"))

        black=gtk.gdk.color_parse('black')
        white=gtk.gdk.color_parse('white')
        eb=gtk.EventBox()
        eb.add(self.label)
        for state in (gtk.STATE_ACTIVE, gtk.STATE_NORMAL,
                      gtk.STATE_SELECTED, gtk.STATE_INSENSITIVE,
                      gtk.STATE_PRELIGHT):
            self.label.modify_bg(state, black)
            eb.modify_bg(state, black)
            self.label.modify_fg(state, white)

        vbox.add(self.drawable)
        vbox.pack_start(eb, expand=False)
        vbox.pack_start(self.toolbar, expand=False)

        self.drawable.connect_after('realize', self.register_drawable)

        vbox.show_all()
        return vbox
