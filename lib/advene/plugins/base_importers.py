#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2020 Olivier Aubert <contact@olivieraubert.net>
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

import logging
logger = logging.getLogger(__name__)

name="Base importer collection"

from gettext import gettext as _

import gzip
import os
import re
import sys
import urllib
import xml.dom
import xml.etree.ElementTree as ET

import advene.core.config as config
import advene.util.handyxml as handyxml
from advene.util.importer import GenericImporter
import advene.util.helper as helper

def register(controller=None):
    controller.register_importer(TextImporter)
    controller.register_importer(LsDVDImporter)
    controller.register_importer(ChaplinImporter)
    controller.register_importer(XiImporter)
    controller.register_importer(SubtitleImporter)
    controller.register_importer(PraatImporter)
    controller.register_importer(CmmlImporter)
    controller.register_importer(IRIImporter)
    controller.register_importer(IRIDataImporter)
    return True

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
            encoding = 'utf-8'
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


    @staticmethod
    def can_handle(fname):
        ext = os.path.splitext(fname)[1].lower()
        if ext in ('.txt', '.log'):
            return 100
        elif ext == '.gz':
            return 50
        elif ext in config.data.video_extensions:
            return 0
        else:
            # It may handle any type of file ?
            return 1

    def log(self, *p):
        self.controller.log(self.name + " error: " + " ".join(p))

    def iterator(self, f):
        filesize = float(os.path.getsize(f.name))
        # We cannot simply use string.split() since we want to be able
        # to specify the number of splits() while keeping the
        # flexibility of having any blank char as separator
        whitespace_re = re.compile(r'\s+')
        stored_begin = 0
        stored_data = None
        index = 1
        while True:
            l = f.readline()
            if not l or not self.progress(f.tell() / filesize):
                break
            l = l.strip()
            data = whitespace_re.split(l, 2)

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
            if len(data) == 2:
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
            f = gzip.open(filename, 'r', encoding='utf-8')
        elif filename.startswith('http'):
            f = urllib.request.urlopen(filename)
        else:
            f = open(filename, 'r', encoding='utf-8')
        if self.package is None:
            self.init_package(filename=filename)
        self.ensure_new_type()
        self.convert(self.iterator(f))
        self.progress(1.0)
        f.close()
        return self.package

class LsDVDImporter(GenericImporter):
    """lsdvd importer.
    """
    name = _("lsdvd importer")

    def __init__(self, regexp=None, encoding='utf-8', **kw):
        super(LsDVDImporter, self).__init__(**kw)
        lsdvd=helper.find_in_path('lsdvd')
        if lsdvd is None:
            raise Exception("Cannot find lsdvd")
        self.command=self.lsdvd + " -c"
        # FIXME: handle Title- lines
        #Chapter: 01, Length: 00:01:16, Start Cell: 01
        self.regexp="^\s*Chapter:\s*(?P<chapter>\d+),\s*Length:\s*(?P<duration>[0-9:]+)"
        self.encoding=encoding

    @staticmethod
    def can_handle(fname):
        if 'dvd' in fname:
            return 100
        else:
            return 0

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
            l=str(l, self.encoding).encode('utf-8')
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
        if not self.package.media:
            # We created a new package. Set the mediafile
            self.package.setMedia("dvd@1,1")
        self.progress(0.1, _("Launching lsdvd..."))
        f=os.popen(self.command, "r")
        self.convert(self.iterator(f))
        f.close()
        self.progress(1.0)
        return self.package

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

    @staticmethod
    def can_handle(fname):
        if 'dvd' in fname:
            return 100
        else:
            return 0

    def iterator(self, f):
        reg=re.compile(self.regexp)
        begin=1
        end=1
        chapter=None
        for l in f:
            l=l.rstrip()
            l=str(l, self.encoding).encode('utf-8')
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
        if not self.package.media:
            # We created a new package. Set the mediafile
            self.package.setMedia("dvd@1,1")
        self.convert(self.iterator(f))
        f.close()
        self.progress(1.0)
        return self.package

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

    @staticmethod
    def can_handle(fname):
        if fname.endswith('.xi'):
            return 100
        elif fname.endswith('.xml'):
            return 50
        else:
            return 0

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
            self.anchors[a.id] = int(float(a.offset.replace(',','.')) * self.factors[a.unit])
            if filename is None:
                filename = self.signals[a.refSignal]
            elif filename != self.signals[a.refSignal]:
                logger.error("Erreur: many source files, not supported")
                sys.exit(1)

        if not self.package.media:
            self.package.setMedia(filename)

        self.convert(self.iterator(xi))
        self.progress(1.0)
        return self.package

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

    @staticmethod
    def can_handle(fname):
        if fname.lower().endswith('.srt') or fname.lower().endswith('.webvtt'):
            return 100
        else:
            return 0

    def srt_iterator(self, f):
        base=r'\d+:\d+:\d+[,\.:]\d+'
        pattern=re.compile('(' + base + ').+(' + base + ')')
        tc=None
        content=[]
        # 10000 lines should be a reasonable max.
        max_lines = 10000
        for index, line in enumerate(f):
            if not self.progress(index / max_lines):
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
                        logger.warning("Strange error: no timestamp was found for content %s", "".join(content))
                        content = []
                else:
                    d={'begin': tc[0],
                       'end': tc[1],
                       'content': "\n".join(content)}
                    tc=None
                    content=[]
                    yield d
            else:
                if tc is not None:
                    content.append(line)
                    # else We could check line =~ /^\d+$/
        # End of for-loop: if there is a last item, convert it.
        if tc is not None:
            d={'begin': tc[0],
               'end': tc[1],
               'content': "\n".join(content)}
            yield d

    def process_file(self, filename):
        f = open(filename, 'r', encoding=self.encoding or 'utf-8')
        p, at = self.init_package(filename=filename, annotationtypeid='subtitle')
        at.title = _("Subtitles from %s") % os.path.basename(filename)
        # FIXME: implement subtitle type detection
        try:
            self.convert(self.srt_iterator(f))
        except UnicodeDecodeError:
            self.output_message = _("Cannot decode subtitle file. Try to specify an encoding (latin1 perhaps?).")
        f.close()
        self.progress(1.0)
        return self.package

class PraatImporter(GenericImporter):
    """PRAAT importer.

    """
    name = _("PRAAT importer")

    def __init__(self, **kw):
        super(PraatImporter, self).__init__(**kw)
        self.atypes={}
        self.schema=None

    @staticmethod
    def can_handle(fname):
        if fname.endswith('.praat') or fname.endswith('.textgrid'):
            return 100
        else:
            return 0

    def iterator(self, f):
        l=f.readline()
        if not 'ooTextFile' in l:
            logger.error("Invalid PRAAT file")
            return

        name_re=re.compile(r'^(\s+)name\s*=\s*"(.+)"')
        boundary_re=re.compile(r'^(\s+)(xmin|xmax)\s*=\s*([\d\.]+)')
        text_re=re.compile(r'^(\s+)text\s*=\s*"(.*)"')

        current_type=None
        type_align=0

        begin=None
        end=None

        while True:
            l=f.readline()
            if not l:
                break
            l=str(l, 'iso-8859-1').encode('utf-8')
            m=name_re.match(l)
            if m:
                ws, current_type=m.group(1, 2)
                type_align=len(ws)
                if current_type not in self.atypes:
                    self.atypes[current_type]=self.create_annotation_type(self.schema, current_type)
                continue
            m=boundary_re.match(l)
            if m:
                ws, name, t = m.group(1, 2, 3)
                if len(ws) <= type_align:
                    # It is either the xmin/xmax for the current type
                    # or a upper-level xmin. Ignore.
                    continue
                v=int(float(t) * 1000)
                if name == 'xmin':
                    begin=v
                else:
                    end=v
                continue
            m=text_re.match(l)
            if m:
                ws, text = m.group(1, 2)
                if len(ws) <= type_align:
                    logger.error("Error: invalid alignment for %s", l)
                    continue
                if begin is None or end is None or current_type is None:
                    logger.error("Error: found text tag before xmin or xmax info: %s", l)
                    continue
                yield {
                    'type': self.atypes[current_type],
                    'begin': begin,
                    'end': end,
                    'content': text,
                    }

    def process_file(self, filename):
        f=open(filename, 'rb')

        self.init_package(filename)
        self.schema=self.create_schema('praat',
                                       title="PRAAT converted schema")
        self.convert(self.iterator(f))
        f.close()
        self.progress(1.0)
        return self.package

class CmmlImporter(GenericImporter):
    """CMML importer.

    Cf http://www.annodex.net/
    """
    name=_("CMML importer")

    def __init__(self, **kw):
        super(CmmlImporter, self).__init__(**kw)
        self.atypes={}
        self.schema=None

    @staticmethod
    def can_handle(fname):
        if fname.endswith('.cmml'):
            return 100
        elif fname.endswith('.xml'):
            return 50
        else:
            return 0

    def npt2time(self, npt):
        """Convert a NPT timespec into a milliseconds time.

        Cf http://www.annodex.net/TR/draft-pfeiffer-temporal-fragments-03.html#anchor5
        """
        if isinstance(npt, (int, float)):
            return npt

        if npt.startswith('npt:'):
            npt=npt[4:]

        try:
            msec=helper.parse_time(npt)
        except Exception as e:
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
            except AttributeError:
                logger.error("Error in CMML importer", exc_info=True)
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
            except AttributeError:
                logger.error("CMML - link error", exc_info=True)
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
                    if meta.name not in self.atypes:
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
            self.init_package(filename=filename)

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
                t=int(t)
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
        self.package.setMedia(src)

        self.convert(self.iterator(cm))

        self.progress(1.0)

        return self.package

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

    @staticmethod
    def can_handle(fname):
        if fname.endswith('.iri'):
            return 100
        elif fname.endswith('.xml'):
            return 60
        else:
            return 0

    def iterator(self, iri):
        schema = None
        ensembles=iri.body[0].ensembles[0].ensemble
        progress=0.1
        incr=0.02
        for ensemble in ensembles:
            sid=ensemble.id
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
                # Update self.duration
                self.duration=max(int(decoupage.dur), self.duration)

                # Create the type
                if tid not in self.atypes:
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
                           str(el.title).encode('utf-8').replace('\n', '\\n'),
                           str(el.abstract).encode('utf-8').replace('\n', '\\n'),
                           str(el.src).encode('utf-8').replace('\n', '\\n'),
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
                        if tid not in self.atypes:
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
                    for ref in view.ref:
                        an = [a for a in self.package.annotations if a.id == ref.id ]
                        if not an:
                            logger.error("IRIImporter: Invalid id %s", ref.id)
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
            if not self.package.media:
                self.package.setMedia(med[0].video[0].src)

        # Metadata extraction
        meta=dict((m.name, m.content) for m in iri.head[0].meta)
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

class IRIDataImporter(GenericImporter):
    """IRIData importer.
    """
    name = _("IRIData importer")

    def __init__(self, **kw):
        super(IRIDataImporter, self).__init__(**kw)

    @staticmethod
    def can_handle(fname):
        if fname.endswith('.xml'):
            return 60
        else:
            return 0

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
        for c in range(0, int(n / size)):
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
