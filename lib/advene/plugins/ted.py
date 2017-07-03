#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2009-2017 Olivier Aubert <contact@olivieraubert.net>
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

name="TED transcription importer"

from gettext import gettext as _

import re
import urllib.request, urllib.parse, urllib.error
try:
    # json is standard in python 2.6
    import json
except ImportError:
    import simplejson as json

from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(TEDImporter)
    return True

class TEDImporter(GenericImporter):
    name = _("TED importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        if fname.startswith('http://www.ted.com'):
            return 100
        elif fname.endswith('.html'):
            return 60
        return 0

    def process_file(self, filename):
        self.progress(0.1, "Fetching " + filename)
        if filename.startswith('http://www.ted.com'):
            filename=filename.strip('#/')
            f=urllib.request.urlopen(filename)
        else:
            f=open(filename, 'r', encoding='utf-8')
        data='\n'.join(f.readlines())
        f.close()

        p, at=self.init_package(filename=filename, schemaid='ted')
        if self.package is None:
            self.package=p

        offset=re.findall('introDuration\s*:\s*(\d+)', data)
        if offset:
            offset=int(offset[0])
        else:
            offset=0
        m = re.findall('/talks/subtitles/id/(\d+)', data, re.MULTILINE)
        if m:
            ident=m[0]
        else:
            self.log("Cannot find talk id")
            ident=None
        podcast=re.findall('(itpc://[^"]+)', data, re.MULTILINE)
        if podcast:
            podcast=podcast[0]
            self.progress(0.2, "Fetching podcast information")
            podcast=urllib.request.urlopen(podcast.replace('itpc:', 'http:'))
            data=podcast.read()
            podcast.close()
            title=re.findall('<title>(.+?)</title>', data)
            if title:
                self.package.title=title[0]
            moviepath=re.findall('<media:content\s+url="(.+?)"', data)
            if moviepath:
                self.controller.set_default_media(moviepath[0])
        else:
            title=re.findall('<title>(.+?)</title>', data)
            if title:
                self.package.title=title[0]
            # Try to find a reference to a .mp4 file
            movieurl=re.findall('(http://download.ted.com/.+?\.mp4)', data, re.MULTILINE)
            if movieurl:
                self.controller.set_default_media(movieurl[0])

        self.progress(0.3, "Converting data")
        if ident is not None:
            self.convert(self.json_iterator(ident, offset))
        else:
            self.convert(self.html_iterator(data, offset))

        self.progress(1.0)
        return self.package

    def html_iterator(self, data, offset):
        at=self.create_annotation_type(self.package.get_element_by_id('ted'), 'transcription')
        start=None
        text=None
        yield {
            'type': at,
            'content': "Introduction",
            'begin': 0,
            'end': offset,
            }
        for timestamp, buf in re.findall('seekVideo.(\d+).+?>(.+?)</a>', data):
            t=int(timestamp) + offset
            if start is not None:
                yield {
                    'type': at,
                    'content': text,
                    'begin': start,
                    'end': t,
                    }
            start=t
            text=buf
        # Last item
        if start is not None:
            yield {
                'content': text,
                'begin': start,
                'end': start + 2000, # FIXME: find out duration
                }

    def json_iterator(self, ident, offset=0):
        urlbase='http://www.ted.com/talks/subtitles/id/%s' % ident
        for lang in ('eng_en', 'fre_fr', ):
            self.progress(0.1, "Converting %s subtitles" % lang)
            at=self.create_annotation_type(self.package.get_element_by_id('ted'), lang)
            url=urlbase+'/lang/'+lang
            f=urllib.request.urlopen(url)
            data=f.read()
            f.close()
            data=json.loads(data)
            if not 'captions' in data:
                # Language not present
                continue
            step=1.0 / len(data['captions'])
            prg=0.1
            yield {
                'type': at,
                'content': "Introduction",
                'begin': 0,
                'end': offset,
                }
            for d in data['captions']:
                self.progress(prg)
                prg += step
                yield {
                    'type': at,
                    'content': d['content'],
                    'begin': d['startTime'] + offset,
                    'duration': d['duration'],
                    }

