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
"""GUI to apply importers to files or internal data
"""
import logging
logger = logging.getLogger(__name__)

import os
import _thread
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk

from gettext import gettext as _

import advene.core.config as config
import advene.gui.popup
from advene.gui.util import dialog
from advene.model.package import Package
from advene.gui.edit.properties import OptionParserGUI

from advene.gui.views import AdhocView

dummy_advene_importer = object()

name="AnnotationImporter view plugin"

def register(controller):
    controller.register_viewclass(AnnotationImporter)

class AnnotationImporter(AdhocView):
    view_name = _("Importer")
    view_id = 'importerview'

    def __init__(self, controller=None, filename=None, message=None, display_unlikely=True, parameters=None, importerclass=None, source_type=None):
        super(AnnotationImporter, self).__init__(controller=controller)
        self.controller=controller
        self.parameters=parameters
        self.message = message

        self.close_on_package_load = False
        self.contextual_actions = ()
        self.options={
            'display-unlikely': display_unlikely,
            }

        # Flag used to cancel import
        self.should_continue = True

        # Assume that the view is initialized in the current
        # thread. Store its id, so that we detect if calls
        # (esp. progress_callback) are made from another thread and
        # act accordingly.
        self.main_thread_id = _thread.get_ident()
        self.importer = None
        if importerclass is not None:
            self.importer = importerclass(controller=self.controller, callback=self.progress_callback, source_type=source_type)
        self.filename = filename
        self.widget=self.build_widget()

        if filename:
            self.fb.set_filename(filename)
            self.update_importers(filename=filename)

    def update_importers(self, filename=None):
        if filename is not None:
            n = filename
        else:
            n=self.filename or self.fb.get_filename() or self.fb.get_uri()
        if not n:
            return
        if n.startswith('file://'):
            n = n.replace('file://', '')
        if not self.fb.get_filename():
            # It was not a filename, hence the Button did not get
            # updated. Update it explicitly.
            b = self.fb.get_children()[0]
            if isinstance(b, Gtk.Button):
                # Normally, the Gtk.Button contains a Gtk.HBox, which
                # contains some widgets among which a Gtk.Label
                l = [ c
                      for w in b.get_children()
                      for c in w.get_children()
                      if isinstance(c, Gtk.Label) ]
                if l:
                    # Found the label
                    l[0].set_text(n)
        model = self.importers.get_model()
        model.clear()
        if n.lower().endswith('.azp'):
            model.append( ( _("Advene package importer"), dummy_advene_importer, None) )
            self.importers.set_active(0)
            self.convert_button.set_sensitive(True)
            return
        if (os.path.exists(n) and not os.path.isdir(n)) or n.startswith('http:'):
            # Valid filename. Guess importers
            valid, invalid = advene.util.importer.get_valid_importers(n)
            for i in valid:
                model.append( ( i.name, i, None) )
            if n.lower().endswith('.xml'):
                model.append( ( _("Advene package importer"), dummy_advene_importer, None) )
            if valid:
                self.importers.set_active(0)
            if invalid and self.options['display-unlikely']:
                model.append( ( "--- " + _("Not likely") + " ---", None, None) )
                for i in invalid:
                    model.append( (i.name, i, None) )
            self.convert_button.set_sensitive(True)
        else:
            # Invalid filenames. Empty importers and disable convert button
            #model.append( (_("Possible importers"), None, None) )
            for i in advene.util.importer.IMPORTERS:
                model.append( (i.name, i, None) )
            self.importers.set_active(0)
            self.convert_button.set_sensitive(False)

        return True

    def processing_ended(self, msg=None):
        if _thread.get_ident() != self.main_thread_id:
            self.do_gui_operation(self.processing_ended, msg=msg)
            return True
        self.progress_callback(1.0)
        self.controller.notify("PackageActivate", package=self.controller.package)
        self.close()
        if msg is None:
            msg = _('Completed conversion: %(message)s\n%(statistics)s') % {
                'message': self.importer.output_message,
                'statistics': self.importer.statistics_formatted() }
        dialog.message_dialog(msg, modal=False)
        self.log(msg)

    def convert_file(self, b, *p):
        stop_label = _("Stop")
        if b.get_label() == stop_label:
            # Cancel action
            self.should_continue = False
            b.set_sensitive(False)
            return True

        if self.importer is None:
            ic = self.importers.get_current_element()
            fname = self.filename or self.fb.get_filename() or self.fb.get_uri()

            if fname.startswith('file://'):
                fname = fname.replace('file://', '')
            if ic == dummy_advene_importer:
                # Invoke the package merge functionality.
                try:
                    source = Package(uri=fname)
                except Exception as e:
                    self.log("Cannot load %s file: %s" % (fname, str(e)))
                    return True
                self.controller.gui.open_adhoc_view('packageimporter', sourcepackage=source, destpackage=self.controller.package)
                self.close()
                return True

            if ic is None:
                return True
            i = ic(controller=self.controller, callback=self.progress_callback)
            self.importer = i
        else:
            i = self.importer
            fname = self.filename
        i.set_options(self.optionform.options)
        i.get_preferences().update(dict(self.optionform.options))
        i.package=self.controller.package

        reqs = i.check_requirements()
        if reqs:
            # Not all requirements are met. Display some information.
            dialog.message_dialog(_("The filter is not ready.\n%s") % "\n".join(reqs), modal=True)
            return True

        # Update Start button to Stop and disable GUI elements
        b.set_label(stop_label)
        self.importers.set_sensitive(False)
        self.fb.set_sensitive(False)

        if hasattr(i, 'async_process_file'):
            # Asynchronous version.
            try:
                i.async_process_file(fname, self.processing_ended)
            except Exception as e:
                dialog.message_dialog(str(e.args), modal=False)
                self.close()
        else:
            # Standard, synchronous version
            try:
                i.process_file(fname)
            except Exception as e:
                dialog.message_dialog(str(e.args), modal=False)
                logger.exception("Error in processing import data")
            finally:
                self.processing_ended()
        return True

    def do_gui_operation(self, func, *args, **kw):
        """Execute a method in the main loop.

        Ensure that we execute all Gtk operations in the mainloop.
        """
        def idle_func():
            Gdk.threads_enter()
            try:
                func(*args, **kw)
            finally:
                Gdk.threads_leave()
            return False
        GObject.idle_add(idle_func)

    def progress_callback(self, value=None, label=None):
        if _thread.get_ident() != self.main_thread_id:
            self.do_gui_operation(self.progress_callback, value=value, label=label)
            return self.should_continue

        if value is None:
            self.progressbar.pulse()
        else:
            self.progressbar.set_fraction(value)
        if label is not None:
            self.progressbar.set_text(label)
        # We could do a "while Gtk.events_pending()" but we want to
        # avoid process lock because of too many pending events
        # processing.
        for i in range(8):
            if Gtk.events_pending():
                Gtk.main_iteration()
            else:
                break
        return self.should_continue

    def update_options(self, combo, forced=None):
        if forced:
            ic = forced.__class__
        else:
            # Instanciate a dummy importer, to get its options.
            ic = combo.get_current_element()
        self.options_frame.foreach(self.options_frame.remove)
        if ic is not None and ic != dummy_advene_importer:
            if forced:
                i = forced
            else:
                i = ic(controller=self.controller)
            # Restore cached options if any
            i.set_options(i.get_preferences())
            self.optionform = OptionParserGUI(i.optionparser, i)
            self.options_frame.add(self.optionform)
        return True

    def build_widget(self):
        vbox=Gtk.VBox()

        def updated_filename(entry):
            self.update_importers()
            return True

        line=Gtk.HBox()
        vbox.pack_start(line, False, True, 0)

        self.fb = Gtk.FileChooserButton(_("Choose the file to import"))
        self.fb.set_local_only(False)
        self.fb.set_action(Gtk.FileChooserAction.OPEN)
        self.fb.set_current_folder(config.data.path['data'])
        self.fb.connect('file-set', updated_filename)

        line.pack_start(self.fb, True, True, 0)
        # We pass a message, assume that the source is already specified and hide FileChooser
        if self.message is not None:
            line.pack_start(Gtk.Label(self.message), True, True, 0)
            self.fb.set_no_show_all(True)
            self.fb.hide()

        self.progressbar=Gtk.ProgressBar()
        vbox.pack_start(self.progressbar, False, True, 0)

        # Importer choice list
        line=Gtk.HBox()
        vbox.pack_start(line, False, True, 0)

        line.pack_start(Gtk.Label(_("Filter") + " "), False, False, 0)
        self.importers = dialog.list_selector_widget([], None, callback=self.update_options)
        line.pack_start(self.importers, False, True, 0)
        # An importer was specified. Do no display the importer list
        if self.importer is not None:
            self.importers.set_no_show_all(True)
            self.importers.hide()
            line.pack_start(Gtk.Label(self.importer.name), False, True, 0)

        exp = Gtk.Frame.new(_("Options"))
        self.options_frame = Gtk.VBox()
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add_with_viewport(self.options_frame)
        exp.add(sw)
        vbox.pack_start(exp, True, True, 0)

        bb=Gtk.HButtonBox()

        b=Gtk.Button(_("Start"))
        b.connect('clicked', self.convert_file)
        bb.pack_start(b, False, True, 0)
        self.convert_button=b

        vbox.pack_start(bb, False, True, 0)

        if self.importer is None:
            self.convert_button.set_sensitive(False)
            self.update_importers()
        else:
            self.update_options(self.importers, forced=self.importer)
            self.convert_button.set_sensitive(True)

        vbox.show_all()

        return vbox
