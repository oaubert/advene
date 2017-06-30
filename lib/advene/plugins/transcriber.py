#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2009-2012 Mathieu BEN <mben@irisa.fr>
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
"""Transcriber importer.

    Cf http://trans.sourceforge.net/en/presentation.php
"""

name="Transcriber importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

from advene.util.importer import GenericImporter
import xml.etree.ElementTree as ETree

def register(controller=None):
    controller.register_importer(TrsImporter)
    return True

class TrsImporter(GenericImporter):
    """Transcriber importer.

    Cf http://trans.sourceforge.net/en/presentation.php
    """
    name=_("Transcriber importer")

    def __init__(self, **kw):
        super(TrsImporter, self).__init__(**kw)
        self.atypes={}
        self.schema=None
        self.topics = {
            '': ""}
        self.speakers = {
            '': ""}

    def can_handle(fname):
        if fname.endswith('.trs'):
            return 100
        elif fname.endswith('.xml'):
            return 50
        else:
            return 0
    can_handle=staticmethod(can_handle)

    def iterator(self, trs):
        # Parse  information

        progress=0.5
        nbsection = 0

        Episode = trs.findall('Episode')
        try:
            for e in Episode:
                nbsection += len(e.findall('Section'))
            incr=0.5 / nbsection
        except AttributeError:
            return

        b = { # dictionary for background information
            'type': None,
            'begin': None,
            'end': None,
            'content': None
            }
        for e in Episode:
            try:
                s_begin = None
                s_end = None
                Section = e.findall('Section')
                for s in Section:
                    self.progress(progress, _("Parsing section information"))
                    progress += incr

                    try:
                        s_begin=float(s.get('startTime')) ## 'startTime' is a "Section" required attribute
                    except:
                        logger.error("startTime Conversion", exc_info=True)
                        continue

                    s_begin=int(s_begin*1000)

                    try:
                        s_end=float(s.get('endTime'))    ## 'endTime' is a "Section" required attribute
                    except:
                        logger.error("endTime Conversion", exc_info=True)
                        continue

                    s_end=int(s_end*1000)

                    try:
                        typ = s.get('type')              ## 'type' is a "Section" required attribute
                    except:
                        logger.error("type Conversion", exc_info=True)
                        continue

                    topic = ""  ## 'topic' is a "Section" optional  attribute
                    try :
                        if s.get('topic') is not None:
                            topic = self.topics[s.get('topic')].rstrip('[]')
                    except AttributeError as KeyError:
                        pass


                    d={
                        'type': self.atypes['Section'],
                        'begin': s_begin,
                        'end': s_end,
                        'content': "%s [%s]" % (topic, typ),
                        }
                    yield d

                    try:
                        for t in s.findall('Turn'):

                            try:
                                t_begin=float(t.get('startTime')) ## 'startTime' is a "Turn" required attribute
                            except:
                                logger.error("startTime Conversion", exc_info=True)
                                continue

                            t_begin=int(t_begin*1000)

                            try:
                                t_end=float(t.get('endTime'))   ## 'endTime' is a "Turn" required attribute
                            except:
                                logger.error("endTime Conversion", exc_info=True)
                                continue

                            t_end=int(t_end*1000)

                            speaker = ""   ## 'speaker' is a "Turn" optional attribute
                            try:
                                if t.get('speaker') is not None:
                                    speaker = self.speakers[t.get('speaker')]
                            except (AttributeError, KeyError):
                                pass

                            d={
                                'type': self.atypes['Turn'],
                                'begin': t_begin,
                                'end': t_end,
                                'content': "%s" % speaker
                                }
                            yield d

                            text = ""

                            seg = None

                            for elem in t.getchildren():

                                if elem.tag == "Sync" :
                                    try:
                                        seg_time = float(elem.get('time'))
                                    except:
                                        logger.error("time Conversion", exc_info=True)
                                        continue

                                    seg_time = int(seg_time*1000)

                                    if seg is not None:
                                        seg['end'] = seg_time
                                        seg['content'] = text+"\n"
                                        yield seg
                                        text = ""

                                    seg = {
                                        'type': self.atypes['Transcription'],
                                        'begin': seg_time,
                                        'end': None,
                                        'content': "%s" % text
                                       }

                                    text = elem.tail.replace("\n","")

                                elif elem.tag == 'Background':
                                    try:
                                        time = elem.get('time')
                                    except:
                                        logger.error("time Conversion", exc_info=True)
                                        continue

                                    level = 'off'

                                    try:
                                        level =  elem.get('level')
                                    except AttributeError:
                                        pass

                                    if level == 'high':
                                        n_begin = int(float(time)*1000)
                                        try :
                                            n_type = elem.get('type')
                                        except AttributeError:
                                            continue
                                        b ={
                                            'type': self.atypes['Background'],
                                            'begin': n_begin,
                                            'end': None,
                                            'content': "%s" % n_type
                                            }
                                    elif  level == 'off'and b['begin'] is not None:
                                        n_end = int(float(time)*1000)
                                        b['end'] = n_end
                                        yield b
                                        b = {
                                            'type': None,
                                            'begin': None,
                                            'end': None,
                                            'content': None
                                            }

                            if seg is not None:
                                seg['end'] = t_end
                                seg['content'] = text+"\n"
                                yield seg

                    except AttributeError: ## catch exception on Turn elements
                        logger.error("Exception on Turn element", exc_info=True)
                        continue

            except AttributeError:  ## catch exceptions on Section elements
                logger.error("Exception on Section element", exc_info=True)
                continue

            if b['begin'] is not None:
                b['end'] = s_end
                yield b

    def process_file(self, filename):
        trstree=ETree.parse(filename)
        trs = trstree.getroot()

        if trs.tag != 'Trans':
            self.log("This does not look like a Transcriber file.")
            return

        if self.package is None:
            self.progress(0.1, _("Creating package"))
            self.init_package(filename=filename, schemaid=None, annotationtypeid=None)

        self.schema=self.create_schema('trs', title="Transcriber converted schema")

        # Create the 4 default types : Section, Turn, Transcription, Background
        self.progress(0.3, _("Creating annotation types"))
        for n in ('Section', 'Turn', 'Transcription', 'Background'):
            self.atypes[n]=self.create_annotation_type(self.schema, n)

        # Handle heading information
        self.progress(0.4, _("Parsing header information"))

        try:
            self.schema.author = trs.get('scribe')
        except AttributeError:
            pass
        try:
            self.schema.date = trs.get('version_date')
        except AttributeError:
            pass

        self.progress(0.5, _("Parsing topic and speaker tables information"))

        # Handle 'Topics' table informations
        Topics = trs.find('Topics')
        try:
            topiclist = Topics.findall('Topic')
            for topic in topiclist:
                self.topics[topic.get('id')] = topic.get('desc')
        except AttributeError:
            pass

        # Handle 'Speakers' table informations
        Speakers = trs.find('Speakers')
        try:
            spklist = Speakers.findall('Speaker')
            for spk in spklist:
                self.speakers[spk.get('id')] = spk.get('name')
        except AttributeError:
            pass

        self.convert(self.iterator(trs))

        self.progress(1.0)

        return self.package

