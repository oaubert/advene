#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Initial configuration mini-application.
"""

from gettext import gettext as _

import gtk
import gobject
import os

import advene.core.config as config
from advene.gui.edit.properties import EditWidget

class Config:
    def __init__(self):
        self.options={}
        for k in ('language', 'update-check'):
            self.options[k]=config.data.preferences[k]
        for k in ('data', 'imagecache', 'moviepath'):
            self.options[k]=config.data.path[k]
        self.widget=self.build_widget()

    def main(self):
        self.widget.show_all()
        gobject.timeout_add (10, self.run_config)
        gtk.main()

    def run_config(self):
        res=self.widget.popup()
        if res:
            for k in ('language', 'update-check'):
                config.data.preferences[k]=self.options[k]
            for k in ('data', 'imagecache', 'moviepath'):
                config.data.path[k]=self.options[k]
            config.data.save_preferences()
        gtk.main_quit()
        return

    def build_widget(self):
        ew=EditWidget(self.options.__setitem__, self.options.get)
        ew.set_name(_("Initial Advene configuration"))
        ew.add_label("""<span size="large"><b>Welcome in Advene</b>\nThis is the first time that you run Advene. Please answer some basic configuration questions. You will be able to modify these choices from the Advene interface, in the Edit/Preferences menu.</span>""")
        ew.add_option(_("Interface language"), 'language', _("Language used for the interface"),
                      {
                "English": 'C',
                "Francais": 'fr_FR',
                _("System default"): '',
                })
        ew.add_checkbox(_("Daily check for Advene updates on the Advene website"), 'update-check', _("Daily check for updates on the Advene website"))

        ew.add_dir_selector(_("Preferred directory for data files"), "data", _("Preferred directory for storing data files (Advene packages)"))
        #ew.add_dir_selector(_("Imagecache"), "imagecache", _("Directory for storing the snapshot cache"))
        ew.add_dir_selector(_("Directories to search for movies"), "moviepath", _("List of directories (separated by %(pathsep)s) to search for movie files. _ means the same directory as the package referencing the movie file. For instance: _%(pathsep)s%(dir)s%(sep)sadvene") % { 
                'pathsep': os.path.pathsep,
                'sep': os.path.sep,
                'dir': config.data.get_homedir() })
        return ew
