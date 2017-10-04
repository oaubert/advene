#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2011-2017 Olivier Aubert <contact@olivieraubert.net>
#
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

import time
from gettext import gettext as _
from gi.repository import Gtk

import advene.core.config as config
from advene.gui.views import AdhocView

name="Kinect view/control plugin"

try:
    import pytrack
except ImportError:
    pytrack = None

def register(controller):
    if pytrack is not None:
        controller.register_viewclass(KinectController)

class KinectController(AdhocView):
    view_name = _("Kinect Controller")
    view_id = 'kinect'
    tooltip=_("Kinect control interface")

    def __init__(self, controller=None, uri=None, parameters=None):
        super(KinectController, self).__init__(controller=controller)
        self.close_on_package_load = False
        self.contextual_actions = []
        self.controller = controller
        self.registered_rules = []

        self.mode = ''
        # When was the last seek done ?
        self.last_seek = 0
        self.seek_threshold = .5

        if pytrack.pytrack_init(config.data.advenefile('Sample-Tracking.xml')):
            self.log("Problem when initializing Kinect controller")

        @pytrack.callback_function
        def callback(*p):
            self.callback(*p)
        self.callbacks = pytrack.CallbacksT()
        for (n, t) in self.callbacks._fields_:
            setattr(self.callbacks, n, callback)
        pytrack.pytrack_set_callbacks(self.callbacks)

        # Load options
        opt, arg = self.load_parameters(parameters)
        self.options.update(opt)
        self.widget = self.build_widget()
        pytrack.pytrack_start_loop()

    def handle_rate_control(self, fx):
        if fx > .9:
            rate = 8.0
        elif fx > .8:
            rate = 4.0
        elif fx > .7:
            rate = 2.0
        elif fx > .4:
            rate = 1.0
        elif fx > .3:
            rate = .5
        elif fx > .2:
            rate = .1
        else:
            rate = 1 / config.data.preferences['default-fps']
        if self.controller.player.get_rate() != rate:
            self.action.set_text("Set rate %.2f" % rate)
            self.controller.queue_action(self.controller.player.set_rate, rate)

    def handle_seek_control(self, fx):
        t = time.time()
        if t - self.last_seek < self.seek_threshold:
            return
        self.last_seek = t
        if fx > .8:
            seek = config.data.preferences['second-time-increment']
        elif fx > .6:
            seek = config.data.preferences['time-increment']
        elif fx < .2:
             seek = -config.data.preferences['second-time-increment']
        elif fx < .4:
            seek = -config.data.preferences['time-increment']
        else:
            seek =0
        if seek:
            self.action.set_text("Seek %d" % seek)
            self.controller.queue_action(self.controller.update_status, "seek_relative", seek)

    def handle_mode_selection(self, fx):
        if fx < .3:
            mode = 'rate'
        elif fx > .7:
            mode = 'seek'
        else:
            mode = 'none'
        if mode != self.mode:
            self.set_mode(mode)

    def set_mode(self, mode):
        if mode != self.mode:
            if self.mode in self.mode_buttons:
                self.mode_buttons[self.mode].set_sensitive(False)
            self.mode = mode
            self.mode_buttons[self.mode].set_sensitive(True)
            self.action.set_text("Mode: %s" % mode)

    def callback(self, event, fx, fy, ix, iy, d):
        #self.log("Kinect: %s (%f, %f) (%d, %d) %d"  % (event, fx, fy, ix, iy, d))
        self.label.set_text("%s (%f, %f) (%d, %d) %d"  % (event, fx, fy, ix, iy, d))
        if event == 'push' and d == 5:
            # Any direction
            self.action.set_text("Play/pause")
            self.controller.update_status('pause')
        elif event == 'move':
            if .5 < fy < .9:
                # Control zone
                if self.mode == 'rate':
                    self.handle_rate_control(fx)
                elif self.mode == 'seek':
                    self.handle_seek_control(fx)
            elif fy < .3:
                # Mode selection
                self.handle_mode_selection(fx)

    def build_widget(self):
        vbox=Gtk.VBox()

        vbox.add(Gtk.Label(label="Kinect control"))

        hb = Gtk.HBox()
        self.mode_buttons = {
            'rate': Gtk.Button("Rate"),
            'none': Gtk.Button("Disabled"),
            'seek': Gtk.Button("Seek"),
            }
        for k in ('rate', 'none', 'seek'):
            hb.add(self.mode_buttons[k])
            self.mode_buttons[k].set_sensitive(False)
        vbox.pack_start(hb, False, True, 0)

        self.label = Gtk.Label(label="Perform a Wave to start.")
        vbox.add(self.label)
        self.action = Gtk.Label(label="No action")
        vbox.add(self.action)
        # FIXME
        #self.slider = Gtk.

        vbox.show_all()
        self.set_mode('none')
        return vbox
