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
"""GUI to import external file formats.
"""
import os
import gtk

from gettext import gettext as _

import advene.core.config as config
import advene.gui.popup
import advene.gui.util

from advene.gui.views import AdhocView

class ExternalImporter(AdhocView):
    def __init__(self, controller=None, parameters=None):
        self.controller=controller
        self.parameters=parameters

        self.view_name = _("Importer")
        self.view_id = 'importerview'
        self.close_on_package_load = False
        self.contextual_actions = ()
        self.options={
            }

        self.widget=self.build_widget()

    def update_importers(self):
        n=self.filename_entry.get_text()
        model=self.importers.get_model()
        model.clear()
        if os.path.exists(n) and not os.path.isdir(n):
            # Valid filename. Guess importers
            valid=advene.util.importer.get_valid_importers(n)
            for i in valid:
                model.append( ( i.name, i) )
            if valid:
                self.importers.set_active(0)
            self.convert_button.set_sensitive(True)
        else:
            # Invalid filenames. Empty importers and disable convert button
            self.convert_button.set_sensitive(False)

        return True

    def convert_file(self, *p):
        ic=self.importers.get_current_element()
        fname=self.filename_entry.get_text()
        if ic is None:
            return True
        i=ic(controller=self.controller, callback=self.progress_callback)
        i.package=self.controller.package
        i.process_file(fname)
        self.progress_callback(1.0)
        self.controller.package._modified = True
        self.controller.notify("PackageActivate", package=self.controller.package)
        self.close()
        mes=_('Completed conversion from file %(filename)s :\n%(statistics)s') % {
            'filename': fname,
            'statistics': i.statistics_formatted() }
        advene.gui.util.message_dialog(mes)
        self.log(mes)
        return True

    def progress_callback(self, value=None, label=None):
        if value is None:
            self.progressbar.pulse()
        else:
            self.progressbar.set_fraction(value)
        if label is not None:
            self.progressbar.set_text(label)
        while gtk.events_pending():
            gtk.main_iteration()
        return True

    def build_widget(self):
        vbox=gtk.VBox()

        def updated_filename(entry):
            self.update_importers()
            return True

        def select_filename(b):
            if config.data.path['data']:
                d=config.data.path['data']
            else:
                d=None
            filename=advene.gui.util.get_filename(title=_("Choose the file to import"),
                                                  action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                                  button=gtk.STOCK_OPEN,
                                                  default_dir=d,
                                                  filter='any')
            if not filename:
                return True
            self.filename_entry.set_text(filename)
            return True

        line=gtk.HBox()
        vbox.pack_start(line, expand=False)

        line.pack_start(gtk.Label(_("Filename")), expand=False)
        self.filename_entry=gtk.Entry()
        self.filename_entry.connect("changed", updated_filename)
        line.pack_start(self.filename_entry)

        self.progressbar=gtk.ProgressBar()
        vbox.pack_start(self.progressbar, expand=False)

        b=gtk.Button(stock=gtk.STOCK_OPEN)
        b.connect("clicked", select_filename)
        line.pack_start(b, expand=False)

        # Importer choice list
        self.importers=advene.gui.util.list_selector_widget([], None)
        vbox.pack_start(self.importers, expand=False)

        bb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_CONVERT)
        b.connect("clicked", self.convert_file)
        b.set_sensitive(False)
        bb.pack_start(b, expand=False)
        self.convert_button=b

        vbox.buttonbox=bb
        vbox.pack_start(bb, expand=False)

        vbox.show_all()

        return vbox
