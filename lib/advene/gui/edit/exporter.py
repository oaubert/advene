#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2021 Olivier Aubert <contact@olivieraubert.net>
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
"""GUI to apply exporters
"""
import logging
logger = logging.getLogger(__name__)

from gi.repository import Gtk
from gi.repository import Pango

from gettext import gettext as _
import os

import advene.core.config as config
from advene.gui.edit.properties import OptionParserGUI
from advene.gui.util import dialog
from advene.gui.views import AdhocView
from advene.util.exporter import get_exporter
from advene.util.tools import open_in_filebrowser

name = "AnnotationExporter view plugin"

def register(controller):
    controller.register_viewclass(AnnotationExporter)

class AnnotationExporter(AdhocView):
    view_name = _("Exporter")
    view_id = 'exporterview'

    def __init__(self, controller=None, filename=None, source=None, title=None, message=None, parameters=None, exporterclass=None):
        super(AnnotationExporter, self).__init__(controller=controller)
        self.controller = controller
        self.parameters = parameters
        self.title = title
        self.message = message
        self.source = source

        self.close_on_package_load = False
        self.contextual_actions = ()
        self.options = {
            }

        self.exporter = None
        if self.source is None:
            self.source = controller.package
        if exporterclass is not None:
            self.exporter = exporterclass(controller=self.controller, source=self.source)
        self.filename = filename
        self.widget = self.build_widget()

    def export(self, b, *p):
        if self.exporter is None:
            ec = self.exporters.get_current_element()
            fname = self.filename or self.get_filename()

            if fname.startswith('file://'):
                fname = fname.replace('file://', '')
            if ec is None:
                return True
            e = ec(controller=self.controller, source=self.source)
            self.exporter = e
        else:
            e = self.exporter
            fname = self.filename or self.get_filename()
        e.set_options(self.optionform.options)
        e.set_source(self.source)
        e.get_preferences().update(dict(self.optionform.options))
        e.package = self.controller.package

        message = "Exporting data"
        # Standard, synchronous version
        try:
            e.export(fname)
            message = _("Data exported to\n%s\nDo you want to open it?") % fname
            icon =  Gtk.MessageType.QUESTION
        except Exception as e:
            message = _("Error when exporting data: %s") % "\n".join(str(a) for a in e.args)
            logger.exception(message)
            icon = Gtk.MessageType.ERROR
        if dialog.message_dialog(message, icon=icon):
            # Try to open the file
            open_in_filebrowser(fname)
            pass
        return True

    def update_options(self, combo, forced=None):
        if forced:
            ec = forced.__class__
        else:
            # Instanciate a dummy importer, to get its options.
            ec = combo.get_current_element()
        self.options_frame.foreach(self.options_frame.remove)
        if ec is not None:
            if forced:
                e = forced
            else:
                e = ec(controller=self.controller)
            # Restore cached options if any
            e.set_options(e.get_preferences())
            self.optionform = OptionParserGUI(e.optionparser, e)
            self.options_frame.add(self.optionform)
            # Update filename
            self.set_filename(e.get_filename(self.get_filename()))
        return True

    def get_filename(self):
        return self.fname_label.get_label()

    def set_filename(self, name):
        self.fname_label.set_label(os.path.abspath(name))
        return True

    def build_widget(self):
        vbox = Gtk.VBox()

        if self.title is not None:
            line = Gtk.HBox()
            vbox.pack_start(line, False, True, 0)
            line.pack_start(Gtk.Label(self.title), True, True, 0)

        exporter_items = list(sorted(( (e, e.get_name())
                                       for e in self.controller.get_export_filters(self.source) ),
                                     key=lambda t: t[1].lower()))

        line = Gtk.HBox()
        vbox.pack_start(line, False, True, 0)

        line.pack_start(Gtk.Label(_("Export to") + " "), False, False, 0)

        def filename_chooser(button):
            name = dialog.get_filename(title=_("Select destination"),
                                       action=Gtk.FileChooserAction.SAVE,
                                       button=Gtk.STOCK_SAVE,
                                       default_dir=str(config.data.path['data']),
                                       default_file=self.get_filename())
            if name is not None:
                button.set_label(name)
            return True

        self.fname_button = Gtk.Button()
        self.fname_label = Gtk.Label()
        self.fname_label.set_ellipsize(Pango.EllipsizeMode.START)
        self.fname_button.add(self.fname_label)
        self.fname_button.connect('clicked', filename_chooser)

        default_exporter = exporter_items[0][0](self.controller, self.source)
        default_filename = default_exporter.get_filename(source=self.source)
        self.set_filename(default_filename)

        line.pack_start(self.fname_button, True, True, 0)

        if self.message is not None:
            line.pack_start(Gtk.Label(self.message), True, True, 0)

        # Exporter choice list
        line = Gtk.HBox()
        vbox.pack_start(line, False, True, 0)

        line.pack_start(Gtk.Label(_("Filter") + " "), False, False, 0)
        self.exporters = dialog.list_selector_widget(exporter_items,
                                                     preselect=self.exporter and self.exporter.__class__,
                                                     callback=self.update_options)
        line.pack_start(self.exporters, False, True, 0)
        # A specific exporter was specified. Do no display the exporter list
        if self.exporter is not None:
            self.exporters.set_no_show_all(True)
            self.exporters.hide()
            line.pack_start(Gtk.Label(self.exporter.name), False, True, 0)

        exp = Gtk.Frame.new(_("Options"))
        self.options_frame = Gtk.VBox()
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add_with_viewport(self.options_frame)
        exp.add(sw)
        vbox.pack_start(exp, True, True, 0)

        bb = Gtk.HButtonBox()

        b = Gtk.Button(_("Export"))
        b.connect('clicked', self.export)
        bb.pack_start(b, False, True, 0)
        self.convert_button = b

        vbox.pack_start(bb, False, True, 0)

        self.update_options(self.exporters)

        vbox.show_all()

        return vbox
