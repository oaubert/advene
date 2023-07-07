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

import io
import json
import optparse
import os
import sys

import advene.core.config as config

from advene.model.package import Package
from advene.model.content import KeywordList

from simpletal import simpleTAL, simpleTALES

EXPORTERS = {}

def register_exporter(exp):
    """Register an exporter
    """
    if hasattr(exp, 'name'):
        ident = exp.get_id()
        logger.debug("registering exporter %s", ident)
        if ident in EXPORTERS:
            logger.warning("Overriding existing exporter with name %s", ident)
        EXPORTERS[ident] = exp
        return exp
    else:
        return None

def get_exporter(name=None):
    """Return the list of exporters.
    """
    if name is None:
        return EXPORTERS
    else:
        return EXPORTERS.get(name)

class GenericExporter:
    """Generic exporter class
    """
    name = _("Generic exporter")
    extension = ".txt"
    mimetype = "text/plain"

    def __init__(self, controller=None, source=None, callback=None):
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

        callback is a method that will be called to inform of the
        export progression.

        @param controller: controller
        @type controller: advene.core.controller

        """
        self.controller = controller
        self.set_source(source)
        self.callback = callback

        # Optional output message that can be set by the exporter to
        # provide feedback to the user
        self.output_message = ""

        # The convention for OptionParser is to have the "dest"
        # attribute of the same name as the Exporter attribute
        # (e.g. here offset)
        self.optionparser = optparse.OptionParser(epilog=self.name)
        #self.optionparser.add_argument("-o", "--offset",
        #                               action="store", type=int, dest="offset", default=0,
        #                               help=_("Specify the offset in ms"))


    @classmethod
    def get_id(cls):
        return cls.__name__

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
        if self.extension:
            return "{}.{}".format(basename, self.extension)
        else:
            return basename

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

    def serialize(self, data, textstream):
        """Serialize the data to the given textstream.

        This can be customized by exporters, depending on the nature of the data.
        """
        textstream.write(str(data, 'utf-8'))

    def output(self, data, filename):
        """Output data to the specified filename.

        We assume here to have text-based data, utf-8 encoded. If the
        export filter is supposed to output binary data, then the
        output method should be customized.

        This method either returns the data, or outputs it to the
        filename/file-like parameter.
        """
        if filename is None:
            return data
        elif isinstance(filename, io.TextIOBase):
            self.serialize(data, filename)
            return ""
        elif isinstance(filename, io.BytesIO):
            with io.StringIO() as buf:
                self.serialize(data, buf)
                filename.write(buf.encode('utf-8'))
            return ""
        elif filename == '-':
            # Export to stdout
            self.serialize(data, sys.stdout)
            return ""
        else:
            with open(filename, 'wt', encoding='utf-8') as fd:
                self.serialize(data, fd)
            return ""

    def export(self, filename=None):
        """Export the source to the specified filename.

        filename may be a file-like object or a pathname, or None.

        Return a status message if filename is specified.
        Return the exported object in native form if filename is None.
        """
        return "Generic export"

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

    def export(self, filename=None):
        ctx = self.controller.build_context(here=self.source)
        if filename is None:
            # No filename is provided. Return string.
            stream = io.BytesIO()
        elif isinstance(filename, io.TextIOBase):
            # Use an intermediary BytesIO
            stream = io.BytesIO()
        elif isinstance(filename, io.BytesIO):
            stream = filename
        else:
            try:
                stream = open(filename, 'wb')
            except Exception:
                logger.error(_("Cannot export to %(filename)s"), exc_info=True)
                raise

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
                raise
            if self.templateview.content.mimetype == 'text/plain':
                stream.write(output.getvalue().replace(b'&lt;', b'<').replace(b'&gt;', b'>').replace(b'&amp;', b'&'))
        else:
            compiler = simpleTAL.XMLTemplateCompiler ()
            compiler.parseTemplate(self.templateview.content.stream)
            try:
                compiler.getTemplate().expand(context=ctx, outputFile=stream, outputEncoding='utf-8', suppressXMLDeclaration=True)
            except simpleTALES.ContextContentException:
                logger.error(_("Error when exporting XML template"), exc_info=True)
        if filename is None:
            value = stream.getvalue()
            stream.close()
            return value
        elif isinstance(filename, io.TextIOBase):
            # Enforce UTF-8
            filename.write(stream.getvalue().encode('utf-8'))
        elif isinstance(filename, io.BytesIO):
            # Nothing to do: it is the responsibility of the caller to close the stream
            pass
        else:
            stream.close()
            return _("Data exported to %s") % filename

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, KeywordList):
            return list(o)
        return json.JSONEncoder.default(self, o)

@register_exporter
class FlatJsonExporter(GenericExporter):
    """Flat json exporter.
    """
    name = _("Flat JSON exporter")
    extension = 'json'
    mimetype = "application/json"

    @classmethod
    def is_valid_for(cls, expr):
        """Is the template valid for different types of sources.

        expr is either "package" or "annotation-type" or "annotation-container".
        """
        return expr in ('package', 'annotation-type', 'annotation-container')

    def serialize(self, data, textstream):
        json.dump(data, textstream, skipkeys=True, ensure_ascii=False, sort_keys=True, indent=4, cls=CustomJSONEncoder)

    def export(self, filename=None):
        # Works if source is a package or a type
        package = self.source.ownerPackage
        media_uri = package.getMetaData(config.data.namespace, "media_uri") or self.controller.get_default_media()

        def flat_json_annotation(a):
            return {
                "id": a.id,
                "title": self.controller.get_title(a),
                "creator": a.author,
                "type": a.type.id,
                "type_title": self.controller.get_title(a.type),
                "type_color": self.controller.get_element_color(a.type),
                "media": media_uri,
                "begin": a.fragment.begin,
                "end": a.fragment.end,
                "color": self.controller.get_element_color(a),
                "content_type": a.content.mimetype,
                "content": a.content.data,
                "parsed": a.content.parsed()
            }

        def flat_json_relation(r):
            return {
                "id": r.id,
                "title": self.controller.get_title(r),
                "creator": r.author,
                "type": r.type.id,
                "type_title": self.controller.get_title(r.type),
                "type_color": self.controller.get_element_color(r.type),
                "media": media_uri,
                "color": self.controller.get_element_color(r),
                "content_type": r.content.mimetype,
                "content": r.content.data,
                "parsed": r.content.parsed(),
                # Dump the whole annotation, it is more verbose but
                # avoids to have to do the id lookup when interpreting
                # the file
                "members":  [ flat_json_annotation(a)
                              for a in r.members ]
            }

        data = { "annotations": [ flat_json_annotation(a)
                                  for a in self.source.annotations ],
                 "relations": [ flat_json_relation(r)
                                for r in self.source.relations ] }

        return self.output(data, filename)

def init_templateexporters():
    exporter_package = Package(uri=config.data.advenefile('exporters.xml', as_uri=True))
    for v in exporter_package.views:
        if v.id == 'index':
            continue
        klass = type("{}Exporter".format(v.id), (TemplateExporter,), {
            'name': v.title,
            'templateview': v,
            'extension': v.getMetaData(config.data.namespace, 'extension') or v.id,
            'mimetype': v.content.mimetype
        })
        register_exporter(klass)

def main():
    logging.basicConfig(level=logging.INFO)
    USAGE = f"{sys.argv[0]} [-o filter_options] filter_name input_file [output_file]"

    import advene.core.controller as controller
    c = controller.AdveneController()
    c.init_plugins()
    controller.init_templateexporters()

    if (len(config.data.args) < 2
        or config.data.args[0] == 'list'):
        logger.error("""Syntax: %s

Available filters:
  * %s
        """ % (USAGE,
               "\n  * ".join(i.get_id() for i in c.get_export_filters())))
        sys.exit(0)

    # Handle input parameters/options
    filtername = config.data.args[0]
    inputfile = config.data.args[1]
    if config.data.args[2:]:
        outputfile = config.data.args[2]
    else:
        outputfile = ''

    # Filter options are passed using the -o option
    # Rebuild filter option string from config.data.options.options dict
    option_list = [ (f"--{k}={v}" if v else f"--{k}")
                    for (k, v) in config.data.options.options.items() ]

    e = None
    cl = [ f for f in c.get_export_filters() if f.get_id().startswith(filtername) ]
    if len(cl) == 1:
        e = cl[0](controller=c)
    elif len(cl) > 1:
        logger.error("Too many possibilities:\n%s", "\n".join(f.get_id() for f in cl))
        sys.exit(1)

    if e is None:
        logger.error("No matching exporter for %s", filtername)
        sys.exit(1)

    e.optionparser.set_usage(USAGE)
    e.process_options(option_list)

    c.load_package(inputfile)
    e.set_source(c.package)

    if outputfile:
        outputfile = e.get_filename(outputfile)
        logger.info("Converting %s to %s using %s", inputfile, outputfile, e.name)
        e.export(outputfile)
    else:
        e.export(sys.stdout)
    sys.exit(0)

if __name__ == "__main__":
    main()
