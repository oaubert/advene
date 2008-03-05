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
"""GUI to export to external file formats.
"""
import os
import gtk

from gettext import gettext as _

import advene.core.config as config
import advene.gui.popup
from advene.gui.util import dialog
from advene.model.package import Package

from advene.gui.views import AdhocView

from simpletal import simpleTAL

name="Exporter view"

def register(controller):
    controller.register_viewclass(Exporter)

class Exporter(AdhocView):
    view_name = _("Exporter")
    view_id = 'exporter'

    def __init__(self, controller=None, parameters=None):
        super(Exporter, self).__init__(controller=controller)
        self.controller=controller
        self.parameters=parameters

        self.close_on_package_load = False
        self.contextual_actions = ()
        self.options={
            }

        self.importer_package=Package(uri=config.data.advenefile('exporters.xml'))
        self.widget=self.build_widget()

    def export_file(self, *p):
        v=self.exporters.get_current_element()

        ctx=self.controller.build_context()
        fname=self.filename_entry.get_text()
        try:
            stream=open(fname, 'wb')
        except Exception, e:
            self.log(_("Cannot export to %(fname)s: %(e)s") % locals())
            return True

        kw = {}
        if v.content.mimetype is None or v.content.mimetype in ('text/html', 'text/plain'):
            compiler = simpleTAL.HTMLTemplateCompiler ()
            compiler.parseTemplate (v.content.stream, 'utf-8')
        else:
            compiler = simpleTAL.XMLTemplateCompiler ()
            compiler.parseTemplate (v.content.stream)
        compiler.getTemplate ().expand (context=ctx, outputFile=stream, outputEncoding='utf-8')
        stream.close()
        self.log(_("Data exported to %s") % fname)
        self.close()
        return True

    def build_widget(self):
        vbox=gtk.VBox()

        def select_filename(b):
            if config.data.path['data']:
                d=config.data.path['data']
            else:
                d=None
            filename=dialog.get_filename(title=_("Choose the destination file for export"),
                                                  action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                                  button=gtk.STOCK_SAVE,
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
        line.pack_start(self.filename_entry)

        b=gtk.Button(stock=gtk.STOCK_SAVE)
        b.connect("clicked", select_filename)
        line.pack_start(b, expand=False)

        # Importer choice list
        line=gtk.HBox()
        vbox.pack_start(line, expand=False)

        line.pack_start(gtk.Label(_("Export filter")), expand=False)
        self.exporters=dialog.list_selector_widget([ ( v, v.title )
                                                     for v in self.importer_package.views
                                                     if v.id != 'index' ], None)
        line.pack_start(self.exporters, expand=False)

        bb=gtk.HButtonBox()

        b=gtk.Button(stock=gtk.STOCK_CONVERT)
        b.connect("clicked", self.export_file)
        bb.pack_start(b, expand=False)
        self.convert_button=b

        vbox.buttonbox=bb
        vbox.pack_start(bb, expand=False)

        vbox.show_all()

        return vbox
