#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2018 Olivier Aubert <contact@olivieraubert.net>
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
"""
Export filter API
=================

Provides a generic framework to export data.
"""

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import argparse
import io
import os
from simpletal import simpleTAL, simpleTALES

import advene.core.config as config
from advene.model.package import Package

EXPORTERS = []

def register_exporter(imp):
    """Register an importer
    """
    if hasattr(imp, 'name'):
        EXPORTERS.append(imp)

def get_exporters():
    """Return the list of exporters.
    """
    return EXPORTERS

class GenericExporter(object):
    """Generic exporter class
    """
    name = _("Generic exporter")
    extension = ".txt"

    def __init__(self, controller=None, source=None):
        """Instanciate the exporter.

        source is the source of elements to export (usually a package,
        or a list annotations).

        If isinstance(source, Package) then all of the package
        elements will be exported.

        If isinstance(source, AnnotationType) then all of the type
        annotations will be exported.

        If isinstance(source, string) then it will be considered as a
        TALES expression that should be evaluated to output the actual
        elements to export.

        @param controller: controller
        @type controller: advene.core.controller
        """
        self.controller = controller
        self.source = self.set_source(source)

        # Optional output message that can be set by the exporter to
        # provide feedback to the user
        self.output_message = ""

        # The convention for OptionParser is to have the "dest"
        # attribute of the same name as the Exporter attribute
        # (e.g. here offset)
        self.optionparser = argparse.ArgumentParser(epilog=self.name)
        #self.optionparser.add_argument("-o", "--offset",
        #                               action="store", type=int, dest="offset", default=0,
        #                               help=_("Specify the offset in ms"))


    @classmethod
    def get_name(cls):
        """Return exporter name.
        """
        return cls.name

    def set_source(self, source):
        if isinstance(source, str):
            self.source = self.controller.build_context().evaluateValue(source)
        else:
            self.source = source

    @classmethod
    def is_valid_for(cls, expr):
        """Is the template valid for different types of sources.

        expr is either "package" or "annotation-type" or "annotation-container".
        """
        return False

    def get_filename(self, basename=None, source=None):
        """Return a filename with the appropriate extension.

        If basename is specified, then use it. Else, build an
        appropriate filename based on the data.
        """
        if source is None:
            source = self.source
        if basename:
            basename = os.path.splitext(basename)[0]
        else:
            if source is not None:
                basename = self.controller.get_title(source)
            else:
                basename = "exported_data"
        return "{}.{}".format(basename, self.extension)

    def set_options(self, options):
        """Set importer options (attributes) according to the given options.

        options may be either an option object from OptionParser (where
        options are attributes of the object) or a dictionary.
        """
        if isinstance(options, dict):
            for k, v in options.items():
                k = k.replace('-', '_')
                if hasattr(self, k):
                    logger.debug("Set option %s %s", k, v)
                    setattr(self, k, v)
                else:
                    logger.info("Unknown option %s", k)
        else:
            for k in (n
                      for n in dir(options)
                      if not n.startswith('_')):
                k = k.replace('-', '_')
                if hasattr(self, k):
                    v = getattr(options, k)
                    logger.debug("Set option %s %s", k, v)
                    setattr(self, k, v)
                else:
                    logger.info("Unknown option %s", k)

    def get_preferences(self):
        """Get the plugin preferences as a dict.

        The plugin prefs are stored in the Advene preferences and
        persist across sessions. The plugin options are saved in it.

        """
        return config.data.preferences['filter-options'].setdefault(type(self).__name__, {})

    def process_options(self, source):
        (options, args) = self.optionparser.parse_args(args=source)
        self.set_options(options)
        return args

    def export(self, filename):
        """Export the source to the specified filename.

        Return a status message.
        """
        pass

class TemplateExporter(GenericExporter):
    """Template exporter.

    This exporter uses a TAL template as processing method.
    """
    # This will be overwritten
    name = _("Template exporter")
    # This is supposed to be a view
    templateview = None

    @classmethod
    def get_name(cls):
        return cls.templateview.title or cls.name

    @classmethod
    def is_valid_for(cls, expr):
        is_valid_for_package = cls.templateview.matchFilter['class'] in ('package', '*')
        is_valid_for_annotationtype = cls.templateview.matchFilter['class'] in ('annotation-type', '*')
        if expr == 'annotation-container':
            return is_valid_for_package or is_valid_for_annotationtype
        if expr == 'package':
            return is_valid_for_package
        if expr == 'annotation-type':
            return is_valid_for_annotationtype
        return True

    def export(self, filename):
        ctx = self.controller.build_context(here=self.source)
        try:
            stream = open(filename, 'wb')
        except Exception:
            logger.error(_("Cannot export to %(filename)s"), exc_info=True)
            return True

        if self.templateview.content.mimetype is None or self.templateview.content.mimetype.startswith('text/'):
            compiler = simpleTAL.HTMLTemplateCompiler ()
            compiler.parseTemplate(self.templateview.content.stream, 'utf-8')
            if self.templateview.content.mimetype == 'text/plain':
                # Convert HTML entities to their values
                output = io.BytesIO()
            else:
                output = stream
            try:
                compiler.getTemplate().expand(context=ctx, outputFile=output, outputEncoding='utf-8')
            except simpleTALES.ContextContentException:
                logger.error(_("Error when exporting text template"), exc_info=True)
            if self.templateview.content.mimetype == 'text/plain':
                stream.write(output.getvalue().replace(b'&lt;', b'<').replace(b'&gt;', b'>').replace(b'&amp;', b'&'))
        else:
            compiler = simpleTAL.XMLTemplateCompiler ()
            compiler.parseTemplate(self.templateview.content.stream)
            try:
                compiler.getTemplate().expand(context=ctx, outputFile=stream, outputEncoding='utf-8', suppressXMLDeclaration=True)
            except simpleTALES.ContextContentException:
                logger.error(_("Error when exporting XML template"), exc_info=True)
        stream.close()
        return _("Data exported to %s") % filename

def init_templateexporters():
    exporter_package = Package(uri=config.data.advenefile('exporters.xml'))
    for v in exporter_package.views:
        if v.id == 'index':
            continue
        klass = type("{}Exporter".format(v.id), (TemplateExporter,), {
            'name': v.title,
            'templateview': v,
            'extension': v.getMetaData(config.data.namespace, 'extension') or v.id
        })
        register_exporter(klass)

init_templateexporters()
