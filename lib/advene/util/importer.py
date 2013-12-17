#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2012 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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
Import external data.
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

im.statistics hold a dictionary containing the creation statistics.
"""

import sys
import time
import re
import os
import optparse
import gzip
import urllib

from gettext import gettext as _

import gobject
import shutil
import subprocess
import signal
import threading

import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation
from advene.model.schema import AnnotationType, Schema
from advene.model.fragment import MillisecondFragment

import advene.util.helper as helper
import advene.util.handyxml as handyxml
import xml.dom
import xml.etree.ElementTree as ET

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
    valid.sort(lambda a, b: cmp(b[1], a[1]))
    return [ i for (i, v) in valid ], invalid

def get_importer(fname, **kw):
    """Return the first/best valid importer.
    """
    valid, invalid=get_valid_importers(fname)
    i=None
    if len(valid) == 0:
        print "No valid importer"
    else:
        if len(valid) > 1:
            print "Multiple importers: ", str(valid)
            print "Using first one."
        i=valid[0](**kw)
    return i

class GenericImporter(object):
    """Generic importer class

    @ivar statistics: Dictionary holding the creation statistics
    @type statistics: dict
    FIXME...
    """
    name = _("Generic importer")

    def __init__(self, author=None, package=None, defaulttype=None, controller=None, callback=None):
        self.package=package
        if author is None:
            author=config.data.userid
        self.author=author
        self.controller=controller
        self.timestamp=time.strftime("%Y-%m-%d")
        self.defaulttype=defaulttype
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

        # The convention for OptionParser is to have the "dest"
        # attribute of the same name as the Importer attribute
        # (e.g. here offset)
        self.optionparser = optparse.OptionParser(usage=_("Usage: %prog [options] source-file destination-file"))
        self.optionparser.add_option("-o", "--offset",
                                     action="store", type="int", dest="offset", default=0,
                                     help=_("Specify the offset in ms"))

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        return 0
    can_handle=staticmethod(can_handle)

    def progress(self, value=None, label=None):
        """Display progress information and notify cancel.

        The callback method can indicate that the action should be
        cancelled by returning False. In this case, the Importer
        should take this information into account and cleanly exit.
        """
        if self.callback:
            return self.callback(min(value, 1.0), label)
        else:
            return True

    def set_options(self, options):
        for k, v in options.iteritems():
            if hasattr(self, k):
                setattr(self, k, v)

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
            print " ".join(p)

    def update_statistics(self, elementtype):
        self.statistics[elementtype] = self.statistics.get(elementtype, 0) + 1

    def ensure_new_type(self, prefix="at_converted", title="Converted data", schemaid=None):
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
        self.defaulttype=self.create_annotation_type(s, atid, title=title)
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
            color=self.package._color_palette.next()
            at.setMetaData(config.data.namespace, "color", color)
        except AttributeError:
            # The package does not have a _color_palette
            pass
        at._fieldnames = set()
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
        kl=self.statistics.keys()
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
          - notify: if True, then each annotation creation will generate a AnnotationCreate signal
          - complete: boolean. Used to mark the completeness of the annotation.
          - send: yield should return the created annotation
        """
        if self.package is None:
            self.package, self.defaulttype=self.init_package(annotationtypeid='imported', schemaid='imported-schema')
        for d in source:
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
            try:
                content=d['content']
            except KeyError:
                content="Default content"
            try:
                ident=d['id']
            except KeyError:
                ident=None
            try:
                type_=d['type']
                if isinstance(type_, basestring):
                    # A type id was specified. Dereference it, and
                    # create it if necessary.
                    type_id = type_
                    type_ = self.package.get_element_by_id(type_id)
                    if type_ is None:
                        # Not existing, create it.
                        type_ = self.ensure_new_type(type_id)
                    elif not isinstance(type_, AnnotationType):
                        raise Exception("Error during import: the specified type id %s is not an annotation type" % type_id)
            except KeyError:
                type_=self.defaulttype
                if type_ is None:
                    if len(self.package.annotationTypes) > 0:
                        type_ = self.package.annotationTypes[0]
                    else:
                        raise Exception("No type")
            try:
                author=d['author']
            except KeyError:
                author=self.author
            try:
                title=d['title']
            except KeyError:
                title=(content or '')[:20]
            try:
                timestamp=d['timestamp']
            except KeyError:
                timestamp=self.timestamp

            a=self.create_annotation (type_=type_,
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
                print "Notifying", a
                self.controller.notify('AnnotationCreate', annotation=a)
            if 'send' in d:
                # We are expected to return a value in the yield call
                try:
                    source.send(a)
                except StopIteration:
                    pass

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
        except OSError, e:
            self.cleanup()
            msg = unicode(e.args)
            raise Exception(_("Could not run %(appname)s: %(msg)s") % locals())

        self.progress(.01, _("Processing %s") % gobject.filename_display_name(filename))

        def execute_process():
            self.convert(self.iterator())
            self.progress(.95, _("Cleaning up..."))
            self.cleanup()
            self.progress(1.0)
            end_callback()
            return True

        # Note: the "proper" way would be to use gobject.io_add_watch,
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
            if config.data.os == 'win32':
                import ctypes
                ctypes.windll.kernel32.TerminateProcess(int(self.process._handle), -1)
            else:
                try:
                    # Python 2.6 only
                    self.process.terminate()
                except AttributeError:
                    try:
                        os.kill(self.process.pid, 9)
                        os.waitpid(self.process.pid, os.WNOHANG)
                    except OSError, e:
                        print "Cannot kill application", unicode(e)
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

class TextImporter(GenericImporter):
    """Text importer.

    The text importer handles input files with 1 annotation per
    line. Each line consists in whitespace-separated data items
    (whitespace can be any number of actual space or tab characters).

    The format of each line is either

    begin_time end_time annotation_data
    or
    begin_time annotation_data

    The "timestamp" setting specifies which format must be used. If
    set to "auto" (automatic detection), it will try to detect the
    appropriate format but can be mislead if annotation data looks
    like a timestamp. In doubt, specify your format.

    begin_time and end_time can be formatted in various ways.

    This function tries to handle multiple formats:

    - plain integers are considered as milliseconds.
      Regexp: \d+
      Example: 2134 or 134 or 2000

    - float numbers are considered as seconds
      Regexp: \d*\.\d*
      Example: 2.134 or .134 or 2. (note the trailing dot)

    - formatted timestamps with colons in them will be interpreted as follows.
      m:s (1 colon)
      m:s.ms (1 colon)
      m:sfNN
      h:m:s (2 colons)
      h:m:s.ms (2 colons)
      h:m:sfNN

      Legend:
      h: hours
      m: minutes
      s: seconds
      ms: milliseconds
      NN: frame number
    """
    name=_("Text importer")

    def __init__(self, regexp=None, encoding=None, **kw):
        super(TextImporter, self).__init__(**kw)
        if encoding is None:
            encoding = 'latin1'
        self.encoding = encoding
        self.relative = False
        self.first_timestamp = None
        self.unit = "ms"
        self.timestampmode = "auto"
        self.optionparser.add_option("-e", "--encoding",
                                     action="store", type="string", dest="encoding", default=self.encoding,
                                     help=_("Specify the encoding of the input file (latin1, utf8...)"))
        self.optionparser.add_option("-r", "--relative",
                                     action="store_true", dest="relative", default=self.relative,
                                     help=_("Should the timestamps be encoded relative to the first timestamp?"))
        self.optionparser.add_option("-u", "--unit",
                                     action="store", type="choice", dest="unit", choices=("ms", "s"), default=self.unit,
                                     help=_("Unit to consider for integers"))
        self.optionparser.add_option("-t", "--timestampmode",
                                     action="store", type="choice", dest="timestamp", choices=("begin", "both", "auto"), default=self.timestampmode,
                                     help=_("What timestamps are present in a line (only begin, both begin and end, or automatic recognition)"))


    def can_handle(fname):
        ext = os.path.splitext(fname)[1].lower()
        if ext == '.txt' or ext == '.log':
            return 100
        elif ext == '.gz':
            return 50
        elif ext in config.data.video_extensions:
            return 0
        else:
            # It may handle any type of file ?
            return 1
    can_handle=staticmethod(can_handle)

    def log(self, *p):
        self.controller.log(self.name + " error: " + " ".join(p))

    def iterator(self, f):
        filesize = float(os.path.getsize(f.name))
        # We cannot simply use string.split() since we want to be able
        # to specify the number of splits() while keeping the
        # flexibility of having any blank char as separator
        whitespace_re = re.compile('\s+')
        stored_begin = 0
        stored_data = None
        index = 1
        for l in f:
            if not self.progress(f.tell() / filesize):
                break
            l = unicode(l.strip(), self.encoding)
            data = whitespace_re.split(l, 1)

            if not data:
                # Error, cannot do anything with it.
                self.log("invalid data: ", l)
                continue

            try:
                begin = helper.parse_time(data[0])
            except helper.InvalidTimestamp:
                self.log("cannot parse " + data[0] + " as a timestamp.")
                continue
            if self.first_timestamp is None:
                self.first_timestamp = begin
                if not self.relative:
                    stored_begin = begin

            if self.relative:
                begin = begin - self.first_timestamp

            if self.unit == "s":
                begin = begin * 1000

            # We have only a begin time.
            if len(data) == 1:
                if self.timestampmode == 'both':
                    self.log("Cannot find end timestamp: ", l)
                    continue
                if stored_data is None:
                    # First line. Just buffer timestamp
                    stored_data = str(index)
                    stored_begin = begin
                else:
                    # Only 1 time.
                    yield {
                        'begin': stored_begin,
                        'end': max(begin - 1, 0),
                        'content': stored_data,
                        }
                    stored_begin = begin
                index += 1
                continue
            else:
                try:
                    end = helper.parse_time(data[1])
                except helper.InvalidTimestamp:
                    end = None

                if self.timestampmode == 'begin' or (self.timestampmode == 'auto' and end is None):
                    # Invalid timestamp or 'begin' mode - consider
                    # that we have only a begin time, followed by
                    # data.
                    data = whitespace_re.split(l, 1)
                    if stored_data is None:
                        # First line. Just buffer timestamp and data
                        stored_data = data[1]
                        stored_begin = begin
                    else:
                        yield {
                            'begin': stored_begin,
                            'end': max(begin - 1, 0),
                            'content': stored_data,
                        }
                        stored_begin = begin
                        stored_data = data[1]
                    index += 1
                    continue
                elif end is None and self.timestampmode == 'both':
                    self.log("Cannot find end timestamp: ", l)
                    continue
                else:
                    # We have valid begin and end times.
                    if self.relative:
                        end = end - self.first_timestamp
                    if self.unit == "s":
                        end = end * 1000
                    if len(data) == 3:
                        content = data[2]
                    else:
                        content = ""
                    yield {
                        'begin': begin,
                        'end': end,
                        'content': content,
                        }
                    stored_begin = begin
                    index += 1

    def set_regexp(self, r):
        self.re = re.compile(r)

    def process_file(self, filename):
        if filename.lower().endswith('.gz'):
            f = gzip.open(filename, 'r')
        elif filename.startswith('http'):
            f = urllib.urlopen(filename)
        else:
            f = open(filename, 'r')
        if self.package is None:
            self.init_package(filename=filename)
        self.ensure_new_type()
        self.convert(self.iterator(f))
        self.progress(1.0)
        f.close()
        return self.package

register(TextImporter)

class LsDVDImporter(GenericImporter):
    """lsdvd importer.
    """
    name = _("lsdvd importer")

    def __init__(self, regexp=None, encoding='latin1', **kw):
        super(LsDVDImporter, self).__init__(**kw)
        lsdvd=helper.find_in_path('lsdvd')
        if lsdvd is None:
            raise Exception("Cannot find lsdvd")
        self.command=self.lsdvd + " -c"
        # FIXME: handle Title- lines
        #Chapter: 01, Length: 00:01:16, Start Cell: 01
        self.regexp="^\s*Chapter:\s*(?P<chapter>\d+),\s*Length:\s*(?P<duration>[0-9:]+)"
        self.encoding=encoding

    def can_handle(fname):
        if 'dvd' in fname:
            return 100
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def iterator(self, f):
        reg=re.compile(self.regexp)
        begin=1
        incr=0.02
        progress=0.1
        for l in f:
            progress += incr
            if not self.progress(progress, _("Processing data")):
                break
            l=l.rstrip()
            l=unicode(l, self.encoding).encode('utf-8')
            m=reg.search(l)
            if m is not None:
                d=m.groupdict()
                duration=helper.parse_time(d['duration'])
                res={'content': "Chapter %s" % d['chapter'],
                     'begin': begin,
                     'duration': duration}
                begin += duration + 10
                yield res

    def process_file(self, filename):
        if filename != 'lsdvd':
            pass
        self.init_package(filename=filename)
        self.ensure_new_type('chapter', _("DVD Chapter"))
        if not self.package.getMetaData(config.data.namespace, "mediafile"):
            # We created a new package. Set the mediafile
            p.setMetaData (config.data.namespace, "mediafile", "dvd@1,1")
        self.progress(0.1, _("Launching lsdvd..."))
        f=os.popen(self.command, "r")
        self.convert(self.iterator(f))
        f.close()
        self.progress(1.0)
        return self.package

register(LsDVDImporter)

class ChaplinImporter(GenericImporter):
    """Chaplin importer.
    """
    name = _("chaplin importer")

    def __init__(self, **kw):
        super(ChaplinImporter, self).__init__(**kw)

        self.command="/usr/bin/chaplin -c"
        #   chapter 03  begin:    200.200 005005 00:03:20.05
        self.regexp="^\s*chapter\s*(?P<chapter>\d+)\s*begin:\s*.+(?P<begin>[0-9:])\s*$"
        self.encoding='latin1'

    def can_handle(fname):
        if 'dvd' in fname:
            return 100
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def iterator(self, f):
        reg=re.compile(self.regexp)
        begin=1
        end=1
        chapter=None
        for l in f:
            l=l.rstrip()
            l=unicode(l, self.encoding).encode('utf-8')
            m=reg.search(l)
            if m is not None:
                d=m.groupdict()
                end=helper.parse_time(d['begin'])
                if chapter is not None:
                    res={ 'content': "Chapter %s" % chapter,
                          'begin': begin,
                          'end': end }
                    yield res
                chapter=d['chapter']
                begin=end
        # FIXME: the last chapter is not valid (no end value). We
        # should run 'chaplin -l' and get its length there.

    def process_file(self, filename):
        if filename != 'chaplin':
            return None
        f=os.popen(self.command, "r")
        self.init_package(filename=filename)
        self.ensure_new_type('chapter', _("DVD Chapter"))
        if not self.package.getMetaData(config.data.namespace, "mediafile"):
            # We created a new package. Set the mediafile
            p.setMetaData (config.data.namespace, "mediafile", "dvd@1,1")
        self.convert(self.iterator(f))
        f.close()
        self.progress(1.0)
        return self.package

register(ChaplinImporter)

class XiImporter(GenericImporter):
    """Xi importer.
    """
    name = _("Xi importer")

    def __init__(self, **kw):
        super(XiImporter, self).__init__(**kw)
        self.factors = {'s': 1000,
                        'ms': 1}
        self.anchors={}
        self.signals={}

    def can_handle(fname):
        if fname.endswith('.xi'):
            return 100
        elif fname.endswith('.xml'):
            return 50
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def iterator(self, xi):
        for t in xi.Turn:
            d={}
            d['begin']=self.anchors[t.start]
            d['end']=self.anchors[t.end]
            clist=[]
            try:
                for vc in t.Verbal[0].VContent:
                    clist.append(" ".join([ t.value for t in vc.Token ]))
                content = "\n".join(clist)
            except AttributeError:
                content = "No verbal content"

            d['content']=content
            yield d

    def process_file(self, filename):
        xi=handyxml.xml(filename)

        p, at=self.init_package(filename=filename,
                                schemaid='xi-schema',
                                annotationtypeid='xi-verbal')
        self.defaulttype=at

        # self.signals init
        for s in xi.Signals[0].Signal:
            self.signals[s.id] = s.loc

        # self.anchors init
        filename=None
        for a in xi.Anchors[0].Anchor:
            self.anchors[a.id] = long(float(a.offset.replace(',','.')) * self.factors[a.unit])
            if filename is None:
                filename = self.signals[a.refSignal]
            elif filename != self.signals[a.refSignal]:
                print "Erreur: plusieurs fichiers sources, non supportes"
                sys.exit(1)

        if self.package.getMetaData(config.data.namespace, "mediafile") in (None, ""):
            self.package.setMetaData (config.data.namespace,
                                      "mediafile", filename)

        self.convert(self.iterator(xi))
        self.progress(1.0)
        return self.package

register(XiImporter)

class ElanImporter(GenericImporter):
    """Elan importer.
    """
    name=_("ELAN importer")

    def __init__(self, **kw):
        super(ElanImporter, self).__init__(**kw)
        self.anchors={}
        self.atypes={}
        self.schema=None
        self.relations=[]

    def can_handle(fname):
        if fname.endswith('.eaf'):
            return 100
        elif fname.endswith('.elan'):
            return 100
        elif fname.endswith('.xml'):
            return 50
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def xml_to_text(self, element):
        l=[]
        if isinstance(element, handyxml.HandyXmlWrapper):
            element=element.node
        if element.nodeType is xml.dom.Node.TEXT_NODE:
            # Note: element.data returns a unicode object
            # that happens to be in the default encoding (iso-8859-1
            # currently on my system). We encode it to utf-8 to
            # be sure to deal only with this encoding afterwards.
            l.append(element.data.encode('utf-8'))
        elif element.nodeType is xml.dom.Node.ELEMENT_NODE:
            for e in element.childNodes:
                l.append(self.xml_to_text(e))
        return "".join(l)

    def iterator(self, elan):
        valid_id_re = re.compile('[^a-zA-Z_0-9]')
        # List of tuples (annotation-id, related-annotation-uri) of
        # forward referenced annotations
        self.forward_references = []
        progress=0.1
        incr=0.02
        for tier in elan.TIER:
            if not hasattr(tier, 'ANNOTATION'):
                # Empty tier
                continue
            tid = tier.LINGUISTIC_TYPE_REF.replace(' ','_') + '__' + tier.TIER_ID.replace(' ', '_')

            tid=valid_id_re.sub('', tid)

            if not self.atypes.has_key(tid):
                self.atypes[tid]=self.create_annotation_type(self.schema, tid)

            if not self.progress(progress, _("Converting tier %s") % tid):
                break
            progress += incr
            for an in tier.ANNOTATION:
                d={}

                d['type']=self.atypes[tid]
                #d['type']=self.atypes[tier.TIER_ID.replace(' ','_')]

                #print "Creating " + al.ANNOTATION_ID
                if hasattr(an, 'ALIGNABLE_ANNOTATION'):
                    # Annotation on a timeline
                    al=an.ALIGNABLE_ANNOTATION[0]
                    d['begin']=self.anchors[al.TIME_SLOT_REF1]
                    d['end']=self.anchors[al.TIME_SLOT_REF2]
                    d['id']=al.ANNOTATION_ID
                    d['content']=self.xml_to_text(al.ANNOTATION_VALUE[0].node)
                    yield d
                elif hasattr(an, 'REF_ANNOTATION'):
                    # Reference to another annotation. We will reuse the
                    # related annotation's fragment and put it in relation
                    ref=an.REF_ANNOTATION[0]
                    d['id']=ref.ANNOTATION_ID
                    d['content']=self.xml_to_text(ref.ANNOTATION_VALUE[0].node)
                    # Related annotation:
                    rel_id = ref.ANNOTATION_REF
                    rel_uri = '#'.join( (self.package.uri, rel_id) )

                    if self.package.annotations.has_key(rel_uri):
                        rel_an=self.package.annotations[rel_uri]
                        # We reuse the related annotation fragment
                        d['begin'] = rel_an.fragment.begin
                        d['end'] = rel_an.fragment.end
                    else:
                        self.forward_references.append( (d['id'], rel_uri) )
                        d['begin'] = 0
                        d['end'] = 0
                    self.relations.append( (rel_id, d['id']) )
                    yield d
                else:
                    raise Exception('Unknown annotation type')

    def create_relations(self):
        """Postprocess the package to create relations."""
        for (source_id, dest_id) in self.relations:
            source=self.package.annotations['#'.join( (self.package.uri,
                                                       source_id) ) ]
            dest=self.package.annotations['#'.join( (self.package.uri,
                                                     dest_id) ) ]

            #print "Relation %s -> %s" % (source, dest)
            rtypeid='_'.join( ('rt', source.type.id, dest.type.id) )
            try:
                rtype=self.package.relationTypes['#'.join( (self.package.uri,
                                                            rtypeid) ) ]
            except KeyError:
                rtype=self.schema.createRelationType(ident=rtypeid)
                #rt.author=schema.author
                rtype.date=self.schema.date
                rtype.title="Relation between %s and %s" % (source.type.id,
                                                            dest.type.id)
                rtype.mimetype='text/plain'
                # FIXME: Update membertypes (missing API)
                rtype.setHackedMemberTypes( ('#'+source.type.id,
                                             '#'+dest.type.id) )
                self.schema.relationTypes.append(rtype)
                self.update_statistics('relation-type')

            r=self.package.createRelation(
                ident='_'.join( ('r', source_id, dest_id) ),
                type=rtype,
                author=source.author,
                date=source.date,
                members=(source, dest))
            r.title="Relation between %s and %s" % (source_id, dest_id)
            self.package.relations.append(r)
            self.update_statistics('relation')

    def fix_forward_references(self):
        for (an_id, rel_uri) in self.forward_references:
            an_uri = '#'.join( (self.package.uri, an_id) )
            an=self.package.annotations[an_uri]
            rel_an=self.package.annotations[rel_uri]
            # We reuse the related annotation fragment
            an.fragment.begin = rel_an.fragment.begin
            an.fragment.end   = rel_an.fragment.end

    def process_file(self, filename):
        elan=handyxml.xml(filename)

        self.init_package(filename)
        self.schema=self.create_schema(id_='elan', title="ELAN converted schema")
        try:
            self.schema.date=elan.DATE
        except AttributeError:
            self.schema.date = self.timestamp

        # self.anchors init
        if elan.HEADER[0].TIME_UNITS != 'milliseconds':
            raise Exception('Cannot process non-millisecond fragments')

        self.progress(0.1, _("Processing time slots"))
        for a in elan.TIME_ORDER[0].TIME_SLOT:
            try:
                self.anchors[a.TIME_SLOT_ID] = long(a.TIME_VALUE)
            except AttributeError:
                # FIXME: should not silently ignore error
                self.anchors[a.TIME_SLOT_ID] = 0

        # Process types
        #for lt in elan.LINGUISTIC_TYPE:
        #    i=lt.LINGUISTIC_TYPE_ID
        #    i=i.replace(' ', '_')
        #    self.create_annotation_type(schema, i)

        self.convert(self.iterator(elan))
        self.progress(0.8, _("Fixing forward references"))
        self.fix_forward_references()
        self.progress(0.9, _("Creating relations"))
        self.create_relations()
        self.progress(1.0)
        return self.package

register(ElanImporter)

class SubtitleImporter(GenericImporter):
    """Subtitle importer.

    srt importer
    """
    name = _("Subtitle (SRT) importer")

    def __init__(self, encoding=None, **kw):
        super(SubtitleImporter, self).__init__(**kw)
        self.encoding=encoding
        self.optionparser.add_option("-e", "--encoding",
                                     action="store", type="string", dest="encoding", default=self.encoding,
                                     help=_("Specify the encoding of the input file (latin1, utf8...)"))

    def can_handle(fname):
        if fname.lower().endswith('.srt') or fname.lower().endswith('.webvtt'):
            return 100
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def srt_iterator(self, f, filesize):
        if filesize == 0:
            # Dummy value, but we will be sure not to divide by 0
            filesize = 1
        base=r'\d+:\d+:\d+[,\.:]\d+'
        pattern=re.compile('(' + base + ').+(' + base + ')')
        tc=None
        content=[]
        for line in f:
            if not self.progress(1.0 * f.tell() / filesize):
                break
            line=line.rstrip()
            match=pattern.search(line)
            if match is not None:
                tc=(match.group(1), match.group(2))
            elif len(line) == 0:
                # Empty line: end of subtitle
                # Convert it and reset the data
                if tc is None:
                    if content:
                        print "Strange error: no timestamp was found for content ", "".join(content)
                        content = []
                else:
                    d={'begin': tc[0],
                       'end': tc[1],
                       'content': u"\n".join(content)}
                    tc=None
                    content=[]
                    yield d
            else:
                if tc is not None:
                    if self.encoding:
                        data=unicode(line, self.encoding)
                    else:
                        # We will try utf8 first, then fallback on latin1
                        try:
                            data=unicode(line, 'utf8')
                        except UnicodeDecodeError:
                            # Fallback on latin1, which is very common, but may
                            # sometimes fail
                            data=unicode(line, 'latin1')
                    content.append(data)
                    # else We could check line =~ /^\d+$/
        # End of for-loop: if there is a last item, convert it.
        if tc is not None:
            d={'begin': tc[0],
               'end': tc[1],
               'content': u"\n".join(content)}
            yield d

    def process_file(self, filename):
        f=open(filename, 'r')
        p, at = self.init_package(filename=filename, annotationtypeid='subtitle')
        at.title = _("Subtitles from %s") % os.path.basename(filename)
        # FIXME: implement subtitle type detection
        self.convert(self.srt_iterator(f, os.path.getsize(filename)))
        f.close()
        self.progress(1.0)
        return self.package

register(SubtitleImporter)

class PraatImporter(GenericImporter):
    """PRAAT importer.

    """
    name = _("PRAAT importer")

    def __init__(self, **kw):
        super(PraatImporter, self).__init__(**kw)
        self.atypes={}
        self.schema=None

    def can_handle(fname):
        if fname.endswith('.praat') or fname.endswith('.textgrid'):
            return 100
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def iterator(self, f):
        l=f.readline()
        if not 'ooTextFile' in l:
            print "Invalid PRAAT file"
            return

        name_re=re.compile('^(\s+)name\s*=\s*"(.+)"')
        boundary_re=re.compile('^(\s+)(xmin|xmax)\s*=\s*([\d\.]+)')
        text_re=re.compile('^(\s+)text\s*=\s*"(.*)"')

        current_type=None
        type_align=0

        begin=None
        end=None

        while True:
            l=f.readline()
            if not l:
                break
            l=unicode(l, 'iso-8859-1').encode('utf-8')
            m=name_re.match(l)
            if m:
                ws, current_type=m.group(1, 2)
                type_align=len(ws)
                if not self.atypes.has_key(current_type):
                    self.atypes[current_type]=self.create_annotation_type(self.schema, current_type)
                continue
            m=boundary_re.match(l)
            if m:
                ws, name, t = m.group(1, 2, 3)
                if len(ws) <= type_align:
                    # It is either the xmin/xmax for the current type
                    # or a upper-level xmin. Ignore.
                    continue
                v=long(float(t) * 1000)
                if name == 'xmin':
                    begin=v
                else:
                    end=v
                continue
            m=text_re.match(l)
            if m:
                ws, text = m.group(1, 2)
                if len(ws) <= type_align:
                    print "Error: invalid alignment for %s" % l
                    continue
                if begin is None or end is None or current_type is None:
                    print "Error: found text tag before xmin or xmax info"
                    print l
                    continue
                yield {
                    'type': self.atypes[current_type],
                    'begin': begin,
                    'end': end,
                    'content': text,
                    }

    def process_file(self, filename):
        f=open(filename, 'r')

        self.init_package(filename)
        self.schema=self.create_schema('praat',
                                       title="PRAAT converted schema")
        self.convert(self.iterator(f))
        f.close()
        self.progress(1.0)
        return self.package

register(PraatImporter)

class CmmlImporter(GenericImporter):
    """CMML importer.

    Cf http://www.annodex.net/
    """
    name=_("CMML importer")

    def __init__(self, **kw):
        super(CmmlImporter, self).__init__(**kw)
        self.atypes={}
        self.schema=None

    def can_handle(fname):
        if fname.endswith('.cmml'):
            return 100
        elif fname.endswith('.xml'):
            return 50
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def npt2time(self, npt):
        """Convert a NPT timespec into a milliseconds time.

        Cf http://www.annodex.net/TR/draft-pfeiffer-temporal-fragments-03.html#anchor5
        """
        if isinstance(npt, long) or isinstance(npt, int):
            return npt

        if npt.startswith('npt:'):
            npt=npt[4:]

        try:
            msec=helper.parse_time(npt)
        except Exception, e:
            self.log("Unhandled NPT format: " + npt)
            self.log(str(e))
            msec=0

        return msec

    def xml_to_text(self, element):
        l=[]
        if isinstance(element, handyxml.HandyXmlWrapper):
            element=element.node
        if element.nodeType is xml.dom.Node.TEXT_NODE:
            # Note: element.data returns a unicode object
            # that happens to be in the default encoding (iso-8859-1
            # currently on my system). We encode it to utf-8 to
            # be sure to deal only with this encoding afterwards.
            l.append(element.data.encode('utf-8'))
        elif element.nodeType is xml.dom.Node.ELEMENT_NODE:
            for e in element.childNodes:
                l.append(self.xml_to_text(e))
        return "".join(l)

    def iterator(self, cm):
        # Parse stream information

        # Delayed is a list of yielded dictionaries,
        # which may be not complete on the first pass
        # if the end attribute was not filled.
        delayed=[]

        progress=0.5
        incr=0.5 / len(cm.clip)

        for clip in cm.clip:
            if not self.progress(progress, _("Parsing clip information")):
                break
            progress += incr
            try:
                begin=clip.start
            except AttributeError, e:
                print str(e)
                begin=0
            begin=self.npt2time(begin)

            for d in delayed:
                # We can now complete the previous annotations
                d['end']=begin
                yield d
            delayed=[]

            try:
                end=self.npt2time(clip.end)
            except AttributeError:
                end=None

            # Link attribute
            try:
                l=clip.a[0]
                d={
                    'type': self.atypes['link'],
                    'begin': begin,
                    'end': end,
                    'content': "href=%s\ntext=%s" % (l.href,
                                                     self.xml_to_text(l).replace("\n", "\\n")),
                    }
                if end is None:
                    delayed.append(d)
                else:
                    yield d
            except AttributeError, e:
                #print "Erreur dans link" + str(e)
                pass

            # img attribute
            try:
                i=clip.img[0]
                d={
                    'type': self.atypes['image'],
                    'begin': begin,
                    'end': end,
                    'content': i.src,
                    }
                if end is None:
                    delayed.append(d)
                else:
                    yield d
            except AttributeError:
                pass

            # desc attribute
            try:
                d=clip.desc[0]
                d={
                    'type': self.atypes['description'],
                    'begin': begin,
                    'end': end,
                    'content': self.xml_to_text(d).replace("\n", "\\n"),
                    }
                if end is None:
                    delayed.append(d)
                else:
                    yield d
            except AttributeError:
                pass

            # Meta attributes (need to create schemas as needed)
            try:
                for meta in clip.meta:
                    if not self.atypes.has_key(meta.name):
                        self.atypes[meta.name]=self.create_annotation_type(self.schema, meta.name)
                    d={
                        'type': self.atypes[meta.name],
                        'begin': begin,
                        'end': end,
                        'content': meta.content,
                        }
                    if end is None:
                        delayed.append(d)
                    else:
                        yield d
            except AttributeError:
                pass

    def process_file(self, filename):
        cm=handyxml.xml(filename)

        if cm.node.nodeName != 'cmml':
            self.log("This does not look like a CMML file.")
            return

        if self.package is None:
            self.progress(0.1, _("Creating package"))
            self.package=Package(uri='new_pkg', source=None)

        self.progress(0.2, _("Creating CMML schema"))
        self.schema=self.create_schema('cmml', title="CMML converted schema")

        # Create the 3 default types : link, image, description
        self.progress(0.3, _("Creating annotation types"))
        for n in ('link', 'image', 'description'):
            self.atypes[n]=self.create_annotation_type(self.schema, n)
        self.atypes['link'].mimetype = 'application/x-advene-structured'

        # Handle heading information
        self.progress(0.4, _("Parsing header information"))
        try:
            h=cm.head[0]
            try:
                t=h.title
                self.schema.title=self.xml_to_text(t)
            except AttributeError:
                pass
            #FIXME: conversion of metadata (meta name=Producer, DC.Author)
        except AttributeError:
            # Not <head> componenent
            pass

        # Handle stream information
        self.progress(0.5, _("Parsing stream information"))
        if len(cm.stream) > 1:
            self.log("Multiple streams. Will handle only the first one. Support yet to come...")
        s=cm.stream[0]
        try:
            t=s.basetime
            if t:
                t=long(t)
        except AttributeError:
            t=0
        self.basetime=t

        # Stream src:
        try:
            il=cm.node.xpath('//import')
            if il:
                i=il[0]
                src=i.getAttributeNS(xml.dom.EMPTY_NAMESPACE, 'src')
        except AttributeError:
            src=""
        self.package.setMetaData (config.data.namespace, "mediafile", src)

        self.convert(self.iterator(cm))

        self.progress(1.0)

        return self.package

register(CmmlImporter)


class IRIImporter(GenericImporter):
    """IRI importer.
    """
    name = _("IRI importer")

    def __init__(self, **kw):
        super(IRIImporter, self).__init__(**kw)
        self.atypes={}
        self.duration=0
        self.multiple_types=False
        self.optionparser.add_option("-m", "--multiple-types",
                                     action="store_true", dest="multiple_types", default=False,
                                     help=_("Generate one type per view"))

    def can_handle(fname):
        if fname.endswith('.iri'):
            return 100
        elif fname.endswith('.xml'):
            return 60
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def iterator(self, iri):
        schema = None
        ensembles=iri.body[0].ensembles[0].ensemble
        progress=0.1
        incr=0.02
        for ensemble in ensembles:
            sid=ensemble.id
            print "Ensemble", sid
            progress += incr
            if not self.progress(progress, _("Parsing ensemble %s") % sid):
                break
            schema=self.create_schema(sid,
                                      author=ensemble.author or self.author,
                                      date=ensemble.date,
                                      title=ensemble.title,
                                      description=ensemble.abstract)

            for decoupage in ensemble.decoupage:
                tid = decoupage.id
                progress += incr
                if not self.progress(progress, _("Parsing decoupage %s") % tid):
                    break
                print "  Decoupage ", tid
                # Update self.duration
                self.duration=max(long(decoupage.dur), self.duration)

                # Create the type
                if not self.atypes.has_key(tid):
                    at=self.create_annotation_type(schema, tid,
                                                   mimetype='application/x-advene-structured',
                                                   author=decoupage.author or self.author,
                                                   title= decoupage.title,
                                                   date = decoupage.date,
                                                   description=decoupage.abstract,
                                                   representation="here/content/parsed/title")
                    at.setMetaData(config.data.namespace, "color", decoupage.color)
                    self.atypes[tid]=at
                else:
                    at=self.atypes[tid]

                for el in decoupage.elements[0].element:
                    d={'id': el.id,
                       'type': at,
                       'begin': el.begin,
                       'duration': el.dur,
                       'author': el.author or self.author,
                       'date': el.date,
                       'content': "title=%s\nabstract=%s\nsrc=%s" % (
                            unicode(el.title).encode('utf-8').replace('\n', '\\n'),
                            unicode(el.abstract).encode('utf-8').replace('\n', '\\n'),
                            unicode(el.src).encode('utf-8').replace('\n', '\\n'),
                            )
                       }
                    yield d
                # process "views" elements to add attributes
                progress += incr
                if not self.progress(progress, _("Parsing views")):
                    break
                try:
                    views=decoupage.views[0].view
                except AttributeError:
                    # No defined views
                    views=[]
                for view in views:
                    if self.multiple_types:
                        tid=view.id
                        if not self.atypes.has_key(tid):
                            at=self.create_annotation_type(schema, tid,
                                                           mimetype='text/plain',
                                                           author=view.author or self.author,
                                                           title= view.title,
                                                           date = view.date,
                                                           description=view.abstract)
                            at.setMetaData(config.data.namespace, "color", decoupage.color)
                            self.atypes[tid]=at
                        else:
                            at=self.atypes[tid]
                    progress += incr
                    if not self.progress(progress, view.title):
                        break
                    print "     ", view.title.encode('latin1')
                    for ref in view.ref:
                        an = [a for a in self.package.annotations if a.id == ref.id ]
                        if not an:
                            print "Invalid id", ref.id
                        else:
                            an=an[0]
                            if self.multiple_types:
                                d={
                                   'type': at,
                                   'begin': an.fragment.begin,
                                   'end': an.fragment.end,
                                   'author': an.author,
                                   'date': an.date,
                                   'content': ref.type.encode('utf-8')
                                   }
                                yield d
                            else:
                                an.content.data += '\n%s=%s' % (view.id,
                                                                ref.type.encode('utf-8').replace('\n', '\\n'))

    def process_file(self, filename):
        iri=handyxml.xml(filename)

        self.progress(0.1, _("Initializing package"))
        p, at=self.init_package(filename=filename,
                                schemaid=None,
                                annotationtypeid=None)
        if self.package is None:
            self.package=p
        self.defaulttype=at

        # Get the video file.
        med=[ i for i in iri.body[0].medias[0].media  if i.id == 'video' ]
        if med:
            # Got a video file reference
            if not self.package.getMetaData(config.data.namespace, "mediafile"):
                self.package.setMetaData (config.data.namespace, "mediafile", med[0].video[0].src)

        # Metadata extraction
        meta=dict([ (m.name, m.content) for m in iri.head[0].meta ])
        try:
            self.package.title = meta['title']
        except KeyError:
            pass
        try:
            self.package.author = meta['contributor'] or self.author
        except KeyError:
            pass

        self.convert(self.iterator(iri))
        if self.duration != 0:
            if not self.package.getMetaData(config.data.namespace, "duration"):
                self.package.setMetaData (config.data.namespace, "duration", str(self.duration))

        self.progress(1.0)
        return self.package
register(IRIImporter)

class IRIDataImporter(GenericImporter):
    """IRIData importer.
    """
    name = _("IRIData importer")

    def __init__(self, **kw):
        super(IRIDataImporter, self).__init__(**kw)

    def can_handle(fname):
        if fname.endswith('.xml'):
            return 60
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def iterator(self, soundroot):
        progress = .1
        self.progress(progress, _("Parsing sound values"))
        data=[ float(value.attrib['c1max'])
            for value in soundroot
            if value.tag == 'value' ]
        m=max(data)
        # sample is the length of each sample in ms
        sample=int(float(soundroot.attrib['sampling']))
        n=len(data)
        # We store the values by packets of 50
        size=50
        incr = 1.0 / n
        progress = .1
        self.progress(progress, _("Creating annotations"))
        for c in range(0, n / size):
            progress += incr
            if not self.progress(progress, ''):
                break
            yield {
                'begin': c * size * sample,
                'end': (c + 1) * size * sample,
                # We write space-separated normalized values
                'content': " ".join([ str(v / m * 100.0) for v in data[c*size:(c+1)*size] ])
                }
        rest=data[(c+1)*size:]
        if rest:
            yield {
                'begin': (c+1) * size * sample,
                'duration': len(rest) * sample,
                'content': " ".join([ str(v / m * 100.0) for v in rest ])
                }

    def process_file(self, filename):
        root=ET.parse(filename).getroot()
        sound=root.find('sound')
        if root.tag != 'iri' or sound is None:
            self.log("Invalid file")
            return
        self.progress(0.1, _("Initializing package"))
        p, self.defaulttype=self.init_package(filename=filename,
                                              schemaid='s_converted',
                                              annotationtypeid='at_sound_sample')
        if self.package is None:
            self.package=p
        self.defaulttype.mimetype='application/x-advene-values'

        self.convert(self.iterator(sound))
        self.progress(1.0)
        return self.package
register(IRIDataImporter)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = get_importer(fname)
    if i is None:
        print "No importer for %s" % fname
        sys.exit(1)

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    print "Converting %s to %s using %s" % (fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    print i.statistics_formatted()


