#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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

from gettext import gettext as _
import os
import sys
import re
import shutil
import tempfile

import gobject
import subprocess
import threading

import advene.util.helper as helper

import advene.core.config as config
if config.data.os == 'win32':
    import win32process

from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(ShotdetectAppImporter)
    return True

class ShotdetectAppImporter(GenericImporter):
    name = _("ShotdetectApp importer")

    def __init__(self, *p, **kw):
        super(ShotdetectAppImporter, self).__init__(*p, **kw)

        self.process = None
        self.temporary_resources = []
        self.sensitivity = 60

        # Duration of the processed movie (used to correctly compute
        # progress value)
        self.duration = 0

        self.optionparser.add_option("-s", "--sensitivity",
                                     action="store", type="int", dest="sensitivity", default=self.sensitivity,
                                     help=_("Sensitivity of the algorithm. It should typically be between 50 and 80. If too many shots are detected, try to increase its value."))

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in config.data.video_extensions:
            return 80
        return 0
    can_handle=staticmethod(can_handle)

    def async_process_file(self, filename, end_callback):
        if not os.path.exists(config.data.path['shotdetect']):
            raise Exception(_("The <b>shotdetect</b> application does not seem to be installed. Please check that it is present and that its path is correctly specified in preferences." ))
        if not os.path.exists(filename):
            raise Exception(_("The movie %s does not seem to exist.") % filename)

        if filename == self.controller.get_default_media():
            # We know the duration
            self.duration = self.controller.cached_duration

        tempdir = unicode(tempfile.mkdtemp('', 'shotdetect'), sys.getfilesystemencoding())
        self.temporary_resources.append(tempdir)

        argv = [ config.data.path['shotdetect'],
                 '-i', gobject.filename_from_utf8(filename.encode('utf8')),
                 '-o', gobject.filename_from_utf8(tempdir.encode('utf8')),
                 '-s', str(self.sensitivity) ]
        flags = 0
        if config.data.os == 'win32':
            flags = win32process.CREATE_NO_WINDOW

        try:
            self.process = subprocess.Popen( argv,
                                             bufsize=0,
                                             shell=False,
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE,
                                             creationflags = flags)
        except OSError, e:
            self.cleanup()
            raise Exception(_("Could not run shotdetect: %s") % unicode(e))

        self.ensure_new_type('shots', title=_("Detected shots"), schemaid='detected')
        self.progress(.01, _("Detecting shots from %s") % gobject.filename_display_name(filename))

        def execute_process():
            self.convert(self.iterator())
            self.progress(.95, _("Cleaning up..."))
            self.cleanup()
            self.progress(1.0)
            end_callback()
            return True

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

    def iterator(self):
        """Process input data.
        """
        shot_re=re.compile('Shot log\s+::\s+(.+)')
        exp_re = re.compile('(\d*\.\d*)e\+(\d+)')

        num = 1
        begin = 0
        while True:
            l = self.process.stderr.readline()
            if not l:
                break
            ms = shot_re.findall(l)
            if ms:
                ts = 0
                try:
                    ts = long(ms[0])
                except ValueError:
                    m = exp_re.match(ms[0])
                    if m:
                        ts = long(float(m.group(1)) * 10 ** int(m.group(2)))
                if ts == 0:
                    continue
                yield {
                    'content': str(num),
                    'begin': begin,
                    'end': ts,
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
