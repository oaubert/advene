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

name="Speech recognition"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import os
from gi.repository import GObject
from gi.repository import Gst

import advene.core.config as config
from advene.util.importer import GenericImporter
import advene.util.helper as helper

def register(controller=None):
    if (Gst.ElementFactory.find('vader')
        and Gst.ElementFactory.find('pocketsphinx')):
        controller.register_importer(PocketSphinxImporter)
    else:
        controller.log(_("Cannot register speech recognition: Pocketsphinx plugins not found. See http://cmusphinx.sourceforge.net/wiki/gstreamer for details."))
    return True

class PocketSphinxImporter(GenericImporter):
    name = _("Speech recognition (PocketSphinx)")

    def __init__(self, *p, **kw):
        super(PocketSphinxImporter, self).__init__(*p, **kw)

        # Noise level [0..1]
        self.noise = 1.0 / 128
        # Silence duration (in ms)
        self.silence = 300
        # Use default model
        self.use_default_model = True
        # Acoustic model (directory)
        self.acoustic_model = "/usr/share/pocketsphinx/model/hmm/en_US/hub4wsj_sc_8k"
        # Phonetic dictionary
        self.phonetic_dict = "/usr/share/pocketsphinx/model/lm/en_US/cmu07a.dic"
        # Lang model (lm)
        self.lang_model = "/usr/share/pocketsphinx/model/lm/en_US/hub4.5000.DMP"

        self.optionparser.add_option("-n", "--noise",
                                     action="store", type="float", dest="noise", default=self.noise,
                                     help=_("Filtering noise level [0..1]."))

        self.optionparser.add_option("-s", "--silence",
                                     action="store", type="int", dest="silence", default=self.silence,
                                     help=_("Minimum amount (in milliseconds) of silence required to terminate the current annotation and start a new one. Decreasing this length will result in a large amount of short annotations and increasing this length will result in a small amount of long annotations."))

        self.optionparser.add_option("-d", "--default-model",
                                     action="store_true", dest="use_default_model", default= self.use_default_model,
                                     help=_("Use default acoustic and language models."))

        self.optionparser.add_option("-a", "--acoustic-model",
                                     action="store", type="string", dest="acoustic_model", default=self.acoustic_model,
                                     help=_("Acoustic model (directory)") + '[D]')

        self.optionparser.add_option("-p", "--phonetic-dict",
                                     action="store", type="string", dest="phonetic_dict", default=self.phonetic_dict,
                                     help=_("Phonetic dictionary (.dic file)") + '[F]')

        self.optionparser.add_option("-l", "--language-model",
                                     action="store", type="string", dest="lang_model", default=self.lang_model,
                                     help=_("Language model (.DMP file)") + '[F]')

        self.buffer_list = []
        self.start_position = 0
        self.text = None

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in config.data.video_extensions:
            return 80
        return 0

    def on_vader_start(self, vader, pos):
        """Store start position.
        """
        self.start_position = pos / Gst.MSECOND
        return True

    def on_vader_stop(self, vader, pos):
        """Store stop position.
        """
        if self.start_position and self.text:
            self.buffer_list.append( (self.start_position, pos / Gst.MSECOND, self.text) )
            self.text = None
            self.start_position = 0
        return True

    def on_pocketsphinx_result(self, sphinx, text, uttid):
        self.text = text
        return True

    def generate_annotations(self):
        n = 1.0 * len(self.buffer_list)
        self.progress(0, _("Generating annotations"))
        for i, tup in enumerate(self.buffer_list):
            self.progress(i / n)
            self.convert( [ {
                'begin': tup[0],
                'end': tup[1],
                'content': tup[2],
            } ])

    def on_bus_message(self, bus, message):
        def finalize():
            """Finalize data creation.
            """
            GObject.idle_add(lambda: self.pipeline.set_state(Gst.State.NULL) and False)
            self.generate_annotations()
            if self.end_callback:
                self.end_callback()
            return False

        s = message.get_structure()
        if message.type == Gst.MessageType.EOS:
            finalize()
        elif s:
            logger.debug("MSG %s %s", s.get_name(), s.to_string())
            if s.get_name() == 'progress' and self.progress is not None:
                if not self.progress(s['percent-double'] / 100, _("%(count)d utterances until %(time)s") % {
                        'count': len(self.buffer_list),
                        'time': helper.format_time(s['current'] * 1000) }):
                    finalize()
        return True

    def async_process_file(self, filename, end_callback=None):
        self.end_callback = end_callback

        self.ensure_new_type('speech', title=_("Speech"),
                             mimetype='text/plain',
                             description=_("Recognized speech"))

        if self.use_default_model:
            args = ""
        else:
            args = 'hmm="%s" dict="%s" lm="%s" ' % (
                self.acoustic_model,
                self.phonetic_dict,
                self.lang_model)

        # Build pipeline
        self.pipeline = Gst.parse_launch('uridecodebin name=decoder ! audioconvert ! audioresample ! progressreport silent=true update-freq=1 name=report  ! vader name=vader auto-threshold=false threshold=%(noise).9f run-length=%(silence)d ! pocketsphinx name=pocketsphinx %(pocketsphinxargs)s ! fakesink' % ( {
            'noise': self.noise,
            'silence': self.silence * Gst.MSECOND,
            'pocketsphinxargs': args }))
        self.decoder = self.pipeline.get_by_name('decoder')

        vader = self.pipeline.get_by_name("vader")
        vader.connect("vader-start", self.on_vader_start)
        vader.connect("vader-stop", self.on_vader_stop)
        sphinx = self.pipeline.get_by_name("pocketsphinx")
        sphinx.connect("result", self.on_pocketsphinx_result)
        sphinx.set_property("configured", True)

        bus = self.pipeline.get_bus()
        # Enabling sync_message_emission will in fact force the
        # self.progress call from a thread other than the main thread,
        # which surprisingly works better ATM.
        bus.enable_sync_message_emission()
        bus.add_signal_watch()
        bus.connect('sync-message', self.on_bus_message)

        if config.data.os == 'win32':
            self.decoder.props.uri = 'file:///' + os.path.abspath(str(filename))
        else:
            self.decoder.props.uri = 'file://' + os.path.abspath(filename)
        self.progress(0, _("Recognizing speech"))
        self.pipeline.set_state(Gst.State.PLAYING)
        return self.package
