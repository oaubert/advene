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


name="Shot detection importer"

from gettext import gettext as _

import os
import sys

try:
    # Needed for pimpy component
    import numpy
    import opencv.cv as cv
    import opencv.highgui as hg
except ImportError:
    numpy = cv = hg = None

import advene.core.config as config
from advene.util.importer import GenericImporter

def register(controller=None):
    if numpy and cv and hg:
        controller.register_importer(DelakisShotDetectImporter)
    return True

class DelakisShotDetectImporter(GenericImporter):
    name = _("Shot detection (Delakis version)")

    profiles = {
        'default': { 'ALPHA': 2.6, 'BETA': 0.05 },
        'safe': { 'ALPHA': 2.9, 'BETA': 0.06 },
        'aggressive': { 'ALPHA': 1.7, 'BETA': 0.05 },
        }

    def __init__(self, *p, **kw):
        super(DelakisShotDetectImporter, self).__init__(*p, **kw)

        self.cache_histogram = False
        self.profile = 'default'
        self.optionparser.add_option("-c", "--cache-histogram",
                                     action="store_true", dest="cache_histogram", default=self.cache_histogram,
                                     help=_("Cache histogram alongside video files."))
        self.optionparser.add_option("-p", "--profile",
                                     action="store", type="choice", dest="profile", choices=list(self.profiles.keys()), default=self.profile,
                                     help=_("Parameter profile: safe will detect less cuts, aggressive will detect more cuts (but more false ones too). default is a compromise."))

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in config.data.video_extensions:
            return 80
        return 0
    can_handle=staticmethod(can_handle)

    def process_file(self, filename):
        at = self.ensure_new_type('shot', title=_("Shot (%s profile)") % self.profile)
        at.setMetaData(config.data.namespace_prefix['dc'], "description", _("Detected shots"))

        #Compute or load histogram
        histofile = filename + '-histogram.npy'
        if os.path.exists(histofile):
            self.progress(0, _("Loading histogram"))
            histos = numpy.load(histofile)
            # FIXME: how to cache FPS ?
            fps = float(config.data.preferences['default-fps'])
        else :
            he = HistogramExtractor()
            histos, fps = he.process(filename, self.progress)
            if self.cache_histogram:
                try:
                    numpy.save(histofile, histos)
                except Exception as e:
                    self.controller.log("Cannot save histogram: %s" % e.message)

        sd = ShotDetector()
        for k, v in self.profiles[self.profile].items():
            setattr(sd, k, v)
        #Detect cut and dissolve
        self.convert(sd.process(histos, int(1000 / fps)))
        return self.package

# Code adapted from pimpy: http://pim.gforge.inria.fr/pimpy/

NB_CHANNELS = 1
NB_BINS = 255

K=10
T=70

MEAN_WINDOW = 3

class ShotDetector:
    """
    ShotDetector inspired by :
    @phdthesis{DelakisPhd,
    author = {Delakis, Manolis},
    school = {Universite de Rennes 1, France},
    title = {Multimodal Tennis Video Structure Analysis with Segment Models},
    month = {October},
    year = {2006},
    url = {ftp://ftp.irisa.fr/techreports/theses/2006/delakis.pdf }
    }
    """
    def __init__(self, progress=None):
        if progress is None:
            progress = self.dummy_progress
        self.progress = progress
        self.ALPHA = 1.8
        self.BETA = 0.10
        self.MOTION_THRESHOLD = 0.15
        self.SHOT_THRESHOLD     = 0.15
        self.HIGH_CUT_THRESHOLD = 0.8
        self.DISS_THRESHOLD = 0.4
        self.DISS_START_THRESHOLD = 0.16
        self.DISS_END_THRESHOLD = 0.26
        self.DISS_MIN_FRAMES = 3


    def dummy_progress(self, prg, label):
        pass

    def process(self, histos, mspf=40):
        self.progress(.1, _("Computing hdiff"))
        nbpixel = numpy.sum(histos[0])
        #compute various histogram variations
        hdiff = (numpy.abs(histos[:-1] - histos[1:])) / 2
        hdiffsumchannel = numpy.sum(hdiff, axis=1)
        histo_dist = hdiffsumchannel / nbpixel / NB_CHANNELS

        self.progress(.2, _("Detecting cuts"))
        #detect hard cut
        cuts = numpy.flatnonzero( histo_dist >= self.HIGH_CUT_THRESHOLD )

        #detect low cut
        for f in numpy.flatnonzero(
            (histo_dist < self.HIGH_CUT_THRESHOLD) &
            (histo_dist >= self.SHOT_THRESHOLD)
            ):
            if self.__cut_detection(f, histo_dist):
                cuts = numpy.append(cuts, f)

        cuts.sort()
        n = 1
        yield {
            'begin': 0,
            'end': cuts[0] * mspf,
            'content': str(n),
            }
        for b, e in zip(cuts[:-1], cuts[1:]):
            n += 1
            yield {
                'begin': b * mspf,
                'end': e * mspf,
                'content': str(n)
                }

        self.progress(.3, _("Detecting dissolves"))
        #detect dissolve
        hcumul = self.__histo_cumul(histos)
        hcumul = self.__filter_by_cut(cuts, hcumul)
        hpixelwise = self.__histo_pixelwise(hdiff)
        hpixelwise = hpixelwise / nbpixel / 100

        for diss in self.__detect_dissolve(hcumul, hpixelwise):
            yield {
                'begin': diss[0] * mspf,
                'end': diss[1] * mspf,
                'content': 'grad',
                }

    def __detect_dissolve(self, hcumul, hpixelwise):
        motion_frames = hpixelwise > self.MOTION_THRESHOLD
        start = end = -1
        for f in numpy.flatnonzero(hcumul > self.DISS_THRESHOLD):
            #new frame not in current dissolve, record dissolve
            if start > 0 and f > end:
                motion = numpy.sum(motion_frames[list(range(start,end))])
                if not motion and end - start > self.DISS_MIN_FRAMES:
                    yield (start,end)
                start = end = -1

            if start < 0 :
                start = end = f
                #find lower bound
                while start > 0 and hcumul[start] > self.DISS_START_THRESHOLD:
                    start -= 1
                #find upper bound
                while end+1 < len(hcumul) and hcumul[end+1] > self.DISS_END_THRESHOLD :
                    end += 1

        #add the last dissolve
        if start > 0 and end > 0 :
            motion = numpy.sum(motion_frames[list(range(start,end))])
            if not motion and end - start > self.DISS_MIN_FRAMES:
                yield (start,end)

    def __histo_pixelwise(self,hdiff):
        r = []
        for h in hdiff:
            s = 0
            for i in range(T, NB_BINS):
                s += (h[i] * (i-T-1))
            r.append(s)
        return numpy.array(r)

    def __histo_cumul(self, histos):
        nbpix = numpy.sum(histos[0])
        r = []
        for i in range(1, len(histos)):
            h = (histos[i] + histos[i-1]) / 2
            c = 0
            for k in range(1, K):
                if i - k < 0 :
                    break
                c += numpy.sum(numpy.abs(h - histos[i - k])) / nbpix
            r.append(c / K)
        return numpy.array(r)

    def __filter_by_cut(self, cuts, histo_cumul):
        for c in cuts:
            for i in range(K):
                try :
                    histo_cumul[c + i] = histo_cumul[c + i]/(K - i)
                except IndexError:
                    break
        return histo_cumul

    def __cut_detection(self, f, histo_dist):
        d = histo_dist[f]
        left_diff  = histo_dist[f - 1 - MEAN_WINDOW : f - 1] + self.BETA
        right_diff = histo_dist[f + 1 : f + 1 + MEAN_WINDOW] + self.BETA

        mean_left  = numpy.mean(left_diff)
        mean_rigth = numpy.mean(right_diff)
        mean_local = (mean_left + mean_rigth) / 2

        adapt_threshold =  self.ALPHA * mean_local  - self.BETA
        return d >= adapt_threshold

class HistogramExtractor:
    def process(self, videofile, progress):
        progress(0, _("Extracting histogram"))
        video = hg.cvCreateFileCapture(str(videofile).encode(sys.getfilesystemencoding()))
        if not video:
            raise Exception("Could not open video file")
        histo = cv.cvCreateHist([256],cv.CV_HIST_ARRAY,[[0,256]], 1)
        frame = hg.cvQueryFrame(video)
        frame_gray  = cv.cvCreateImage(cv.cvGetSize(frame), frame.depth, 1);
        hists    = []
        nbframes = 0

        fps = hg.cvGetCaptureProperty(video, hg.CV_CAP_PROP_FPS)
        while frame :
            if not progress(hg.cvGetCaptureProperty(video, hg.CV_CAP_PROP_POS_AVI_RATIO)):
                break
            hg.cvConvertImage(frame,frame_gray)
            cv.cvCalcHist(frame_gray,histo,0,None)
            h = [cv.cvGetReal1D(histo.bins,i) for i in range(255) ]
            h = numpy.array(h,dtype='int32')
            hists.append(h)
            frame = hg.cvQueryFrame(video)
            nbframes += 1

        hists = numpy.array(hists)
        return hists.reshape(nbframes, -1), fps
