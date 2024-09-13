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

name="ShotDetectApp importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import re
import tempfile

import advene.util.helper as helper

import advene.core.config as config

from advene.util.importer import ExternalAppImporter

def register(controller=None):
    controller.register_importer(ShotdetectAppImporter)
    return True

class ShotdetectAppImporter(ExternalAppImporter):
    """Shot detection.

    The threshold parameter is used to specify the sensitivity of the
    algorithm, and should typically be between 50 and 80. If too many
    shots are detected, try to increase its value.
    """

    name = _("ShotdetectApp importer")

    def __init__(self, *p, **kw):
        super(ShotdetectAppImporter, self).__init__(*p, **kw)
        self.app_path = str(config.data.path['shotdetect'])
        # Duration of the processed movie (used to correctly compute progress value)
        self.duration = 0
        self.sensitivity = 60

        self.optionparser.add_option("-s", "--sensitivity",
                                     action="store", type="int", dest="sensitivity", default=self.sensitivity,
                                     help=_("Sensitivity of the algorithm. It should typically be between 50 and 80. If too many shots are detected, try to increase its value."))

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if helper.is_video_file(fname):
            return 80
        return 0

    def app_setup(self, filename, end_callback):
        """Setup various attributes/parameters.

        You can for instance create temporary directories here. Add
        them to self.temporary_resources so that they are cleaned up
        in the end.
        """
        logger.debug("Checking duration %s %s", filename, self.controller.get_default_media())
        if helper.path2uri(filename) == helper.path2uri(self.controller.get_default_media()):
            # We know the duration
            self.duration = self.controller.cached_duration
        # FIXME: else we should get it somehow through GstDiscoverer

        self.tempdir = tempfile.mkdtemp('', 'shotdetect')
        self.temporary_resources.append(self.tempdir)

        self.ensure_new_type('shots', title=_("Detected shots"), schemaid='detected')

    def get_process_args(self, filename):
        """Get the process args.

        Return the process arguments (the app_path, argv[0], will be
        prepended in async_process_file and should not be included here).
        """
        args = [ '-i', filename,
                 '-o', self.tempdir,
                 '-s', str(self.sensitivity) ]
        return args

    def iterator(self):
        """Process input data.

        You can read the output from self.process.stdout or
        self.process.stderr, or any other communication means provided
        by the external application.

        This method should yield dictionaries containing data (see
        GenericImporter for details).
        """
        shot_re=re.compile(r'Shot log\s+::\s+(.+)')
        exp_re = re.compile(r'(\d*\.\d*)e\+(\d+)')

        num = 1
        begin = 0
        while True:
            line = self.process.stderr.readline()
            line = line.decode('utf-8')
            if not line:
                break
            logger.debug("Read line %s", line)
            ms = shot_re.findall(line)
            if ms:
                ts = 0
                try:
                    ts = int(ms[0])
                except ValueError:
                    m = exp_re.match(ms[0])
                    if m:
                        ts = int(float(m.group(1)) * 10 ** int(m.group(2)))
                if ts == 0:
                    continue
                logger.debug("Decoded %d timestamp", ts)
                yield {
                    'content': str(num),
                    'begin': begin,
                    'end': ts
                    }
                begin = ts
                num += 1
                if self.duration > 0:
                    prg = 1.0 * ts / self.duration
                else:
                    prg = None
                if not self.progress(prg, _("Detected shot #%(num)d at %(pos)s ") % {
                        'num': num,
                        'pos': helper.format_time_reference(ts)
                }):
                    break
        # Generate last shot
        yield {
            'content': str(num),
            'begin': begin,
            'end': self.duration or (begin + 5000),
            }
