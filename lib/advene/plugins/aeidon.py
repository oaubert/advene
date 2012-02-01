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

# AEIDON importer
# See http://home.gna.org/gaupol/
# Install python-aeidon on Debian

name="AEIDON importer"

from gettext import gettext as _
import os

from advene.util.importer import GenericImporter
try:
    import aeidon
except ImportError:
    aeidon = None

# Reset textdomain. aeidon/gaupol improperly overwrites textdomain
# with its own. It should follow
# http://www.python.org/doc//current/library/gettext.html#localizing-your-module
# instead.
import advene.core.config as config
config.init_gettext()

def register(controller=None):
    if aeidon is not None:
        controller.register_importer(AeidonImporter)
    return True

class AeidonImporter(GenericImporter):
    name = _("Aeidon (subtitles) importer")

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in [ f.extension for f in aeidon.formats ]:
            return 90
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename, dest=None):
        project = aeidon.Project()
        try:
            try:
                project.open_main(filename, encoding='utf-8')
            except UnicodeError:
                try:
                    project.open_main(filename, encoding='latin1')
                except UnicodeError:
                    return
        except Exception, e:
            print "AEIDON: ", unicode(e)
            return
        p, at = self.init_package(filename=dest,
                                  schemaid='subtitle', annotationtypeid=project.main_file.format.name)
        self.annotationtype=at

        if len(project.subtitles) > 0:
            self.convert(self.iterator(project))
        self.progress(1.0)
        return self.package

    def iterator(self, project):
        progress=0.01
        self.progress(progress)
        incr=0.98/len(project.subtitles)
        for s in project.subtitles:
            progress += incr
            if not self.progress(progress):
                break
            yield {
                'type': self.annotationtype,
                'content': s.main_text,
                'begin': long(s.start_seconds * 1000),
                'duration': long(s.duration_seconds * 1000)
                }
        self.progress(1.0)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print "Should provide a file name and a package name"
        sys.exit(1)

    fname=sys.argv[1]
    pname=sys.argv[2]

    i = AeidonImporter()

    # FIXME: i.process_options()
    i.process_options(sys.argv[1:])
    # (for .sub conversion for instance, --fps, --offset)
    print "Converting %s to %s using %s" % (fname, pname, i.name)
    p=i.process_file(fname)
    p.save(pname)
    print i.statistics_formatted()
