#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2009 Mathieu BEN <mben@irisa.fr>
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

from gettext import gettext as _

import xml.dom

from advene.util.importer import GenericImporter
import advene.util.handyxml as handyxml

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
        try:
            for e in trs.Episode:
                nbsection += len(e.Section)
            incr=0.5 / nbsection
        except AttributeError:
            return

        b = { # dictionary for background information
            'type': None,
            'begin': None,
            'end': None,
            'content': None
            }
        for e in trs.Episode:
            try:
                s_begin = None
                s_end = None
                for s in e.Section:
                    self.progress(progress, _("Parsing section information"))
                    progress += incr

                    try:
                        s_begin=float(s.startTime) ## 'startTime' is a "Section" required attribute
                    except AttributeError, e:
                        print str(e)
                        continue

                    s_begin=int(s_begin*1000)

                    try:
                        s_end=float(s.endTime)    ## 'endTime' is a "Section" required attribute
                    except AttributeError, e:
                        print str(e)
                        continue

                    s_end=int(s_end*1000)

                    try:
                        typ = s.type              ## 'type' is a "Section" required attribute
                    except AttributeError, e:
                        print str(e)
                        continue

                    topic = ""  ## 'topic' is a "Section" optional  attribute
                    try :
                        topic = self.topics[s.topic].rstrip('[]')
                    except AttributeError:
                        pass


                    d={
                        'type': self.atypes['Section'],
                        'begin': s_begin,
                        'end': s_end,
                        'content': "%s [%s]" % (topic, typ),
                        }
                    yield d

                    try:
                        for t in s.Turn:

                            try:
                                t_begin=float(t.startTime) ## 'startTime' is a "Turn" required attribute
                            except AttributeError, e:
                                print str(e)
                                continue

                            t_begin=int(t_begin*1000)

                            try:
                                t_end=float(t.endTime)   ## 'endTime' is a "Turn" required attribute
                            except AttributeError, e:
                                print str(e)
                                continue

                            t_end=int(t_end*1000)

                            speaker = ""   ## 'speaker' is a "Turn" optional attribute
                            try:
                                speaker = self.speakers[t.speaker]
                            except AttributeError:
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

                            if t.hasChildNodes():
                                for node in t.childNodes:
                                    if node.nodeName == "Sync" :
                                        try:
                                            seg_time = float(node.getAttribute('time'))
                                        except AttributeError, e:
                                            print str(e)
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

                                    elif node.nodeType == xml.dom.Node.TEXT_NODE:
                                        text += node.data.replace("\n","")

                                    elif node.nodeName == 'Background':
                                        try:
                                            time = node.getAttribute('time')
                                        except AttributeError, e:
                                            print str(e)
                                            continue

                                        level = 'off'

                                        try:
                                            level =  node.getAttribute('level')
                                        except AttributeError:
                                            pass

                                        if level == 'high':
                                            n_begin = int(float(time)*1000)
                                            try :
                                                n_type = node.getAttribute('type')
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

                    except AttributeError,e: ## catch exception on s.Turn
                        print str(e)
                        continue

            except AttributeError,e:  ## catch exceptions on e.Section
                print str(e)
                continue

            if b['begin'] is not None:
                b['end'] = s_end
                yield b

    def process_file(self, filename):
        trs=handyxml.xml(filename)

        if trs.node.nodeName != 'Trans':
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
            self.schema.author = trs.scribe
        except AttributeError:
            pass
        try:
            self.schema.date = trs.version_date
        except AttributeError:
            pass

        self.progress(0.5, _("Parsing topic and speaker tables information"))

        # Handle 'Topics' table informations
        try:
            topiclist = trs.Topics[0].Topic
            for topic in topiclist:
                self.topics[topic.id] = topic.desc
        except AttributeError:
            pass

        # Handle 'Speakers' table informations
        try:
            spklist = trs.Speakers[0].Speaker
            for spk in spklist:
                self.speakers[spk.id] = spk.name
        except AttributeError:
            pass

        self.convert(self.iterator(trs))

        self.progress(1.0)

        return self.package

