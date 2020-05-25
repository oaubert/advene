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
"""Import external data.
=====================

Provides a generic framework to import/convert external data.

The general idea is:

  - Create an instance of Importer, called im.
    If the destination package already exists, call the constructor with
    package and defaultype named parameters.

  - Initialisation:
    - If the destination package already exists, set the
      ``im.package``
      and
      ``im.defaultype``
      to appropriate values

    - If you want to create a new package with specific type and schema id, use
      ``im.init_package(schemaid=..., annotationtypeid=...)``

    - If nothing is given, a default package will be created, with a
      default schema and annotationtype

  - Conversion:
  Call

  ``im.process_file(filename)``

  which will return the package containing the converted annotations

  OR

  Use

  ``im.async_process_file(filename, callback)``

  which is an asynchronous version of the importer, which will return
  immediately. When the import is complete, the callback function
  passed as parameter will be invoked. Produced package can then be
  accessed as ``ìm.package``

im.statistics hold a dictionary containing the creation statistics.

"""

import logging
logger = logging.getLogger(__name__)

import json
import os
import optparse
import shutil
import signal
import subprocess
import sys
import threading

from gettext import gettext as _

from gi.repository import GObject

if __name__ != '__main__':
    import advene.core.config as config

    from advene.model.package import Package
    from advene.model.annotation import Annotation
    from advene.model.schema import AnnotationType, Schema
    from advene.model.fragment import MillisecondFragment

    import advene.util.helper as helper

IMPORTERS=[]

def subprocess_setup():
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def register(imp):
    """Register an importer
    """
    if hasattr(imp, 'can_handle'):
        IMPORTERS.append(imp)
        return imp
    else:
        return None

def get_valid_importers(fname):
    """Return two lists of importers (valid importers, not valid ones) for fname.

    The valid importers list is sorted in priority order (best choice first)
    """
    valid=[]
    invalid=[]
    n=fname.lower()
    for i in IMPORTERS:
        v=i.can_handle(n)
        if v:
            valid.append( (i, v) )
        else:
            invalid.append(i)
    # reverse sort along matching scores
    valid.sort(key=lambda a: a[1], reverse=True)
    return [ i for (i, r) in valid ], invalid

def get_importer(fname, **kw):
    """Return the first/best valid importer.
    """
    valid, invalid=get_valid_importers(fname)
    i=None
    if len(valid) == 0:
        logger.warning("No valid importer")
    else:
        if len(valid) > 1:
            logger.warning("Multiple importers: %s. Using first one.", str(valid))
        i=valid[0](**kw)
    return i

class GenericImporter:
    """Generic importer class
    @ivar statistics: Dictionary holding the creation statistics
    @type statistics: dict
    """
    name = _("Generic importer")
    annotation_filter = False

    def __init__(self, author=None, package=None, defaulttype=None, controller=None, callback=None, source_type=None):
        """Instanciate the importer.

        Note: some importers can use an existing annotation type as
        source element (for processing annotations, e.g. concept
        extraction). In this case, the annotation_filter attribute
        must be set to True, and an additional annotation_type
        parameter is provided to __init__.

        @param author: author for imported/created elements
        @type author: string
        @param package: package where elements will be created
        @type package: advene.model.Package
        @param defaulttype: default annotation type for created annotations
        @type defaulltype: advene.model.AnnotationType
        @param controller: controller
        @type controller: advene.core.controller
        @param callback: callback method for progress report
        @type callback: method

        @param source_type: source annotation type (optional - for annotation filters)
        @param source_type: advene.model.AnnotationType
        """
        self.package=package
        if author is None:
            author=config.data.userid
        self.author=author
        self.controller=controller
        self.timestamp=helper.get_timestamp()
        self.defaulttype=defaulttype
        self.source_type=source_type
        self.callback=callback
        # Default offset in ms
        self.offset=0
        # Dictionary holding the number of created elements
        self.statistics={
            'annotation': 0,
            'relation': 0,
            'annotation-type': 0,
            'relation-type' : 0,
            'schema': 0,
            'view': 0,
            'package': 0,
            }
        # Optional output message that can be set by the importer to
        # provide feedback to the user
        self.output_message = ""

        # The convention for OptionParser is to have the "dest"
        # attribute of the same name as the Importer attribute
        # (e.g. here offset)
        self.optionparser = optparse.OptionParser(usage=_("Usage: %prog [options] source-file destination-file"),
                                                  epilog=self.name)
        self.optionparser.add_option("-o", "--offset",
                                     action="store", type="int", dest="offset", default=0,
                                     help=_("Specify the offset in ms"))

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        return 0

    def progress(self, value=None, label=None):
        """Display progress information and notify cancel.

        The callback method can indicate that the action should be
        cancelled by returning False. In this case, the Importer
        should take this information into account and cleanly exit.
        """
        if self.callback:
            return self.callback(value if value is None else min(value, 1.0), label)
        else:
            return True

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

    def process_file(self, filename):
        """Abstract method.

        This method returns when the conversion is complete. See
        async_process_file for an asynchronous variant.

        When called, it will parse the file and execute the
        self.convert annotations with a dictionary as parameter.
        """
        if hasattr(self, 'async_process_file'):
            # FIXME: should "synchronize" the async_process_file method.
            raise Exception(_("Import filter error. The asynchronous API should be used, please report a bug."))
        else:
            raise Exception(_("Import filter error. No conversion method is defined,  please report a bug."))
        pass

    #def async_process_file(self, filename, end_callback):
    #    """Abstract method.
    #
    #    If defined, it will be used in priority over process_file.
    #    This method returns immediately, and call the provided
    #    end_callback method when it is finished.
    #    The end_callback method takes an optional message as parameter.
    #    """
    #    pass

    def log (self, *p):
        if self.controller is not None:
            self.controller.log(*p)
        else:
            logger.warning(" ".join(p))

    def update_statistics(self, elementtype):
        self.statistics[elementtype] = self.statistics.get(elementtype, 0) + 1

    def ensure_new_type(self, prefix="at_converted", title="Converted data", schemaid=None, mimetype=None, description=None):
        """Create a new type.
        """
        l=[ at.id for at in self.package.annotationTypes ]
        if prefix in l:
            i = 1
            atid = None
            while atid is None:
                t=prefix + str(i)
                if not t in l:
                    atid = t
                else:
                    i += 1
        else:
            atid = prefix

        if schemaid is None:
            schemaid = 's_converted'
        s = self.create_schema(id_=schemaid, title=schemaid)
        if not isinstance(s, Schema):
            raise Exception("Error during conversion: %s is not a schema" % schemaid)
        self.defaulttype = self.create_annotation_type(s, atid, title=title, mimetype=mimetype, description=description)
        return self.defaulttype

    def create_annotation_type (self, schema, id_, author=None, date=None, title=None,
                                representation=None, description=None, mimetype=None):
        at=helper.get_id(self.package.annotationTypes, id_)
        if at is not None:
            return at
        at=schema.createAnnotationType(ident=id_)
        at.author=author or schema.author
        at.date=date or self.timestamp
        at.title=title or at.id.title()
        at.mimetype=mimetype or 'text/plain'
        if description:
            at.setMetaData(config.data.namespace_prefix['dc'], "description", description)
        if representation:
            at.setMetaData(config.data.namespace, "representation", representation)
        try:
            color=next(self.package._color_palette)
            at.setMetaData(config.data.namespace, "color", color)
        except AttributeError:
            # The package does not have a _color_palette
            pass
        at.setMetaData(config.data.namespace, 'item_color', 'here/tag_color')
        schema.annotationTypes.append(at)
        self.update_statistics('annotation-type')
        return at

    def create_schema (self, id_, author=None, date=None, title=None, description=None):
        s=helper.get_id(self.package.schemas, id_)
        if s is not None:
            return s
        schema=self.package.createSchema(ident=id_)
        schema.author=author or self.author
        schema.date=date or self.timestamp
        schema.title=title or "Generated schema"
        if description:
            schema.setMetaData(config.data.namespace_prefix['dc'], "description", description)
        self.package.schemas.append(schema)
        self.update_statistics('schema')
        return schema

    def create_annotation (self, type_=None, begin=None, end=None,
                           data=None, ident=None, author=None,
                           timestamp=None, title=None):
        """Create an annotation in the package
        """
        begin += self.offset
        end += self.offset
        if ident is None and self.controller is not None:
            ident=self.controller.package._idgenerator.get_id(Annotation)

        if ident is None:
            a=self.package.createAnnotation(type=type_,
                                            fragment=MillisecondFragment(begin=begin, end=end))
        else:
            a=self.package.createAnnotation(type=type_,
                                            ident=ident,
                                            fragment=MillisecondFragment(begin=begin, end=end))
        a.author=author
        a.date=timestamp
        a.title=title
        a.content.data = data
        self.package.annotations.append(a)
        self.update_statistics('annotation')
        return a

    def statistics_formatted(self):
        """Return a string representation of the statistics."""
        res=[]
        kl=list(self.statistics.keys())
        kl.sort()
        for k in kl:
            v=self.statistics[k]
            res.append("\t%s" % helper.format_element_name(k, v))
        return "\n".join(res)

    def init_package(self,
                     filename=None,
                     annotationtypeid=None,
                     schemaid=None):
        """Create (if necessary) a package with the given schema and  annotation type.
        Returns a tuple (package, annotationtype)
        """
        if self.package is None:
            p=Package(uri='new_pkg', source=None)
            if filename is not None:
                p.setMetaData(config.data.namespace_prefix['dc'],
                              'description',
                              _("Converted from %s") % filename)
            self.update_statistics('package')
            self.package=p
        else:
            p=self.package


        at=None
        if annotationtypeid:
            at = self.ensure_new_type(prefix=annotationtypeid, schemaid=schemaid)
        elif schemaid is not None:
            s = self.package.get_element_by_id(schemaid)
            if s is None:
                s = self.create_schema(id_=schemaid, title=schemaid)
            if not isinstance(s, Schema):
                raise Exception("Error during conversion: %s is not a schema" % schemaid)

        return p, at

    def check_requirements(self):
        """Check if external requirements for the importers are met.

        It returns a list of strings describing the unmet
        requirements. If the list is empty, then all requirements are
        met.
        """
        return []

    def convert(self, source):
        """Converts the source elements to annotations.

        Source is an iterator or a list returning dictionaries.
        The following keys MUST be defined:
          - begin (in ms)
          - end or duration (in ms)
          - content

        The following keys are optional:
          - id
          - type (can be an annotation-type instance or a type-id)
          - mimetype (used when specifying a type-id)
          - notify: if True, then each annotation creation will generate a AnnotationCreate signal
          - complete: boolean. Used to mark the completeness of the annotation.
          - send: yield should return the created annotation
        """
        if self.package is None:
            self.package, self.defaulttype=self.init_package(annotationtypeid='imported', schemaid='imported-schema')
        if not hasattr(source, '__next__'):
            # It is not an iterator, so it may be another iterable
            # (most probably a list). Replace it by an iterator to
            # access its contents.
            source = iter(source)

        try:
            if hasattr(source, 'send'):
                d = source.send(None)
            else:
                d = next(source)
        except StopIteration:
            return
        while True:
            try:
                begin=helper.parse_time(d['begin'])
            except KeyError:
                raise Exception("Begin is mandatory")
            if 'end' in d:
                end=helper.parse_time(d['end'])
            elif 'duration' in d:
                end=begin + helper.parse_time(d['duration'])
            else:
                raise Exception("end or duration is missing")
            content = d.get('content', "Default content")
            if not isinstance(content, str):
                content = json.dumps(content)
            ident = d.get('id', None)
            author = d.get('author', self.author)
            title = d.get('title', content[:20])
            timestamp = d.get('timestamp', self.timestamp)

            try:
                type_=d['type']
                if isinstance(type_, str):
                    # A type id was specified. Dereference it, and
                    # create it if necessary.
                    type_id = type_
                    type_ = self.package.get_element_by_id(type_id)
                    if type_ is None:
                        # Not existing, create it.
                        type_ = self.ensure_new_type(type_id, title=type_id, mimetype=d.get('mimetype', None))
                    elif not isinstance(type_, AnnotationType):
                        raise Exception("Error during import: the specified type id %s is not an annotation type" % type_id)
            except KeyError:
                type_=self.defaulttype
                if type_ is None:
                    if len(self.package.annotationTypes) > 0:
                        type_ = self.package.annotationTypes[0]
                    else:
                        raise Exception("No type")

            a = self.create_annotation(type_=type_,
                                       begin=begin,
                                       end=end,
                                       data=content,
                                       ident=ident,
                                       author=author,
                                       title=title,
                                       timestamp=timestamp)
            self.package._modified = True
            if 'complete' in d:
                a.complete=d['complete']
            if 'notify' in d and d['notify'] and self.controller is not None:
                logger.debug("Notifying %s", a)
                self.controller.notify('AnnotationCreate', annotation=a)
            try:
                if hasattr(source, 'send'):
                    d = source.send(None)
                else:
                    d = next(source)
            except StopIteration:
                break

class ExternalAppImporter(GenericImporter):
    """External application importer.

    This specialized importer implements the async_process_file
    method, that allows to easily import data from an external
    application.

    To use it, you have to override the __init__ method and set
    self.app_path to the appropriate value, as well as other specific
    attributes (parameters, etc).

    Then, properly override the following methods :
    * app_setup
    * get_process_args
    * iterator
    """
    name = _("ExternalApp importer")

    def __init__(self, *p, **kw):
        super(ExternalAppImporter, self).__init__(*p, **kw)

        self.process = None
        self.temporary_resources = []

        # This value should be setup by descendant classes
        self.app_path = None

    def async_process_file(self, filename, end_callback):
        appname = os.path.basename(self.app_path)
        if not os.path.exists(self.app_path):
            raise Exception(_("The <b>%s</b> application does not seem to be installed. Please check that it is present and that its path is correctly specified in preferences." ) % appname)
        if not os.path.exists(filename):
            raise Exception(_("The file %s does not seem to exist.") % filename)

        self.app_setup(filename, end_callback)

        argv = [ self.app_path ] + self.get_process_args(filename)

        if config.data.os == 'win32':
            import win32process
            kw = { 'creationflags': win32process.CREATE_NO_WINDOW }
        else:
            kw = { 'preexec_fn': subprocess_setup }

        try:
            self.process = subprocess.Popen( argv,
                                             bufsize=0,
                                             shell=False,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE,
                                             **kw )
        except OSError as e:
            self.cleanup()
            msg = str(e.args)
            raise Exception(_("Could not run %(appname)s: %(msg)s") % locals())

        self.progress(.01, _("Processing %s") % GObject.filename_display_name(filename))

        def execute_process():
            self.convert(self.iterator())
            self.progress(.95, _("Cleaning up..."))
            self.cleanup()
            self.progress(1.0)
            end_callback()
            return True

        # Note: the "proper" way would be to use Gobject.io_add_watch,
        # but last time I tried, this had cross-platform issues. The
        # threading approach seems to work across platforms, so "if it
        # ain't broke, don't fix it".
        t=threading.Thread(target=execute_process)
        t.start()
        return self.package

    def cleanup(self, forced=False):
        """Cleanup, and possibly cancel import.
        """
        # Terminate the process if necessary
        if self.process:
            try:
                self.process.terminate()
            except:
                logger.warning("Cannot terminate application", exc_info=True)
        self.process = None

        for r in self.temporary_resources:
            # Cleanup temp. dir. and files
            if os.path.isdir(r):
                # Remove temp dir.
                shutil.rmtree(r, ignore_errors=True)
            elif os.path.exists(r):
                os.unlink(r)
        return True

    def app_setup(self, filename, end_callback):
        """Setup various attributes/parameters.

        You can for instance create temporary directories here. Add
        them to self.temporary_resources so that they are cleaned up
        in the end.
        """
        pass

    def get_process_args(self, filename):
        """Get the process args.

        Return the process arguments (the app_path, argv[0], will be
        prepended in async_process_file and should not be included here).
        """
        return [ ]

    def iterator(self):
        """Process input data.

        You can read the output from self.process.stdout or
        self.process.stderr, or any other communication means provided
        by the external application.

        This method should yield dictionaries containing data (see
        GenericImporter for details).

        You can call self.progress in this method. If it returns
        False, the process should be cancelled.
        """
        yield {}

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    USAGE = "%prog filter_name input_file [options] output_file"
    if sys.argv[1:]:
        filtername = sys.argv[1]
    else:
        filtername = None
    params = sys.argv[2:]
    sys.argv[2:] = []

    import advene.core.config as config
    import advene.core.controller as controller
    import advene

    from advene.model.package import Package
    from advene.model.annotation import Annotation
    from advene.model.schema import AnnotationType, Schema
    from advene.model.fragment import MillisecondFragment

    import advene.util.helper as helper

    import io

    log = io.StringIO()
    saved, sys.stdout = sys.stdout, log
    # Load plugins
    c = controller.AdveneController()
    c.load_package()
    try:
        app_plugins = c.load_plugins(os.path.join(os.path.dirname(advene.__file__), 'plugins'),
                                     prefix="advene_app_plugins")
    except OSError:
        pass

    try:
        user_plugins = c.load_plugins(config.data.advenefile('plugins', 'settings'),
                                      prefix="advene_user_plugins")
    except OSError:
        pass
    sys.stdout = saved

    if filtername is None or len(params) == 0:
        logger.error("""Syntax: %s
filter_name can be "auto" for autodetection.
Available filters:
  * %s
        """ % (USAGE.replace('%prog', sys.argv[0]),
               "\n  * ".join(sorted(i.name for i in controller.advene.util.importer.IMPORTERS))))
        sys.exit(0)

    def progress(value, label):
        print('\rProgress %02d%% - %s' % (int(100 * value), label), end='', flush=True)
        return True

    if filtername == 'auto':
        i = get_importer(params[0], package=c.package, controller=c, callback=progress)
    else:
        i = None
        cl = [ f for f in controller.advene.util.importer.IMPORTERS if f.name.startswith(filtername) ]
        if len(cl) == 1:
            i = cl[0](package=c.package, controller=c, callback=progress)
        elif len(cl) > 1:
            logger.error("Too many possibilities:\n%s", "\n".join(f.name for f in cl))
            sys.exit(1)

    if i is None:
        logger.error("No matching importer for %s", filtername)
        sys.exit(1)

    i.optionparser.set_usage(USAGE)
    args = i.process_options(params)
    if not args:
        i.optionparser.print_help()
        sys.exit(0)
    inputfile = args[0]
    try:
        outputfile = args[1]
    except IndexError:
        outputfile = ''
    # (for .sub conversion for instance, --fps, --offset)
    logger.info("Converting %s to %s using %s", inputfile, outputfile, i.name)

    def json_serialize(p):
        from advene.util.exporter import FlatJsonExporter
        e = FlatJsonExporter(controller=c)
        e.set_source(p)
        e.export('-')
    if hasattr(i, 'async_process_file'):
        # async mode

        from gi.repository import GLib
        mainloop = GLib.MainLoop()
        def end_callback():
            if outputfile:
                logger.info("Saving package to %s", outputfile)
                i.package.save(outputfile)
            else:
                json_serialize(i.package)
            mainloop.quit()
            return True
        i.async_process_file(inputfile, end_callback)
        mainloop.run()
    else:
        p = i.process_file(inputfile)
        if outputfile:
            p.save(outputfile)
        else:
            json_serialize(p)
        logger.info(i.statistics_formatted())
    sys.exit(0)
