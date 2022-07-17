#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2022 Olivier Aubert <contact@olivieraubert.net>
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
name="VOSK speech recognition"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import json

from vosk import Model, KaldiRecognizer, SetLogLevel
SetLogLevel(0)

from advene.util.gstimporter import GstImporter

def register(controller=None):
    controller.register_importer(VoskImporter)
    return True

class VoskImporter(GstImporter):
    name = _("VOSK speech recognition")

    def __init__(self, *p, **kw):
        super(VoskImporter, self).__init__(*p, **kw)

        ## Setup attributes
        self.sample_rate = 16000
        self.model_name = "vosk-model-small-en-gb-0.15"
        self.recognize_words = True

        ## Corresponding optionparser object definition
        self.optionparser.add_option("-m", "--model",
                                     action="store",
                                     type="choice",
                                     dest="model_name",
                                     # FIXME: Get full list from MODEL_LIST_URL
                                     # or just specify a language
                                     choices=(
                                         "vosk-model-small-cn-0.22",
                                         "vosk-model-small-de-0.15",
                                         "vosk-model-small-en-gb-0.15",
                                         "vosk-model-small-en-us-0.15",
                                         "vosk-model-small-es-0.22",
                                         "vosk-model-small-fr-0.22",
                                         "vosk-model-small-it-0.22",
                                     ), default=self.model_name,
                                     help=_("Model name."))
        self.optionparser.add_option("-r", "--rate",
                                     action="store", type="int", dest="sample_rate", default=self.sample_rate,
                                     help=_("Sampling rate (in Hz)"))
        self.optionparser.add_option("-w", "--words",
                                     action="store_true", dest="recognize_words", default=self.recognize_words,
                                     help=_("Add timing for single words"))

        ## Internal data structures
        self.buffer = []
        self.last_above = None

    def do_finalize(self):
        logger.debug("final %s", self.recognizer.FinalResult())

        self.convert( { 'begin': begin * 1000,
                        'end': end * 1000,
                        'type': type_,
                        'content': word }
                      for begin, end, type_, word, conf in self.buffer )

    def process_frame(self, frame):
        data = frame['data']
        if len(data) == 0:
            logger.debug("0 length data")
        elif self.recognizer.AcceptWaveform(data):
            res = json.loads(self.recognizer.Result())
            if res.get('result'):
                self.buffer.append( (res['result'][0]['start'],
                                     res['result'][-1]['end'],
                                     'sentence',
                                     res['text'],
                                     sum(r['conf'] for r in res['result']) / len(res['result'])) )
                if self.recognize_words:
                    for r in res.get('result'):
                        self.buffer.append( (r['start'], r['end'], 'word', r['word'], r['conf']) )
        else:
            pass
            # logger.warning("partial %s", self.recognizer.PartialResult())
        return True

    def setup_importer(self, filename):
        if self.recognize_words:
            self.ensure_new_type('word',
                                 title=_("Word"),
                                 description=_("Recognized word"))
        self.ensure_new_type('sentence',
                             title=_("Sentence"),
                             description=_("Recognized sentence"))

        model = Model(model_name=self.model_name)
        self.recognizer = KaldiRecognizer(model, self.sample_rate)
        self.recognizer.SetWords(True)

        return f"audioconvert ! audiorate ! audioresample ! audio/x-raw,format=S16LE,rate={self.sample_rate},channels=1"
