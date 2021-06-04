# Motion Dynamics Extractor plugin for advene to estimate perceived motion changes ins a video based on optical flow
# computation.
#    Copyright (C) 2021  Christian Hentschel (christian.hentschel@hpi.de), Jacob Löbkens (jcbl423@gmail.com)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import numpy as np
from gettext import gettext as _

import cv2

from advene.util.gstimporter import GstImporter

name = "Motion Dynamics Extractor"


def register(controller=None):
    controller.register_importer(MotionDynamicsExtractor)
    return True


class MotionDynamicsExtractor(GstImporter):
    name = _("Motion Dynamics Extractor")
    annotation_filter = True

    def __init__(self, *p, **kw):
        super(MotionDynamicsExtractor, self).__init__(*p, **kw)

        self.frame_width = 240
        self.begin_timestamps = []
        self.end_timestamps = []
        self.begin_frame_pixbufs = []
        self.end_frame_pixbuf = None
        self.last_frame_pixbuf = None
        self.last_frame_timestamp = 0
        self.magnitudes = []

        self.step_size = 500
        self.window_size = 500
        self.clip_percentile = 100
        self.segment_timestamps = list()

        self.optionparser.add_option(
            "--step_size", action="store", type="int",
            dest="step_size", default=500,
            help=_(
                "The start frames for optical flow computation are extracted at `stepsize` intervals (in ms)."),
        )
        self.optionparser.add_option(
            "--window_size", action="store", type="int",
            dest="window_size", default=500,
            help=_("The end frames for optical flow computation are extracted at "
                   "`stepsize+windowsize` intervals (in ms)."),
        )
        self.optionparser.add_option(
            "--clip_percentile", action="store", type=int,
            dest="clip_percentile", default=100,
            help=_("Magnitudes above the given percentile are clipped before scaling."),
        )

    def check_requirements(self):
        """Check if external requirements for the importers are met.

        It returns a list of strings describing the unmet
        requirements. If the list is empty, then all requirements are
        met.
        """
        unmet_requirements = []

        if self.step_size <= 0:
            unmet_requirements.append(_("stepsize must be > 0"))

        if self.window_size <= 0:
            unmet_requirements.append(_("windowsize must be > 0"))

        if self.clip_percentile <= 0 or self.clip_percentile > 100:
            unmet_requirements.append(_("clip_percentile must be in ]0;100]"))
        return unmet_requirements

    def normalize_and_clip(self):
        segment_scores = list()

        for i, start in enumerate(self.begin_timestamps):
            end = start + self.step_size
            idx = np.logical_or(
                np.logical_and(np.asarray(self.begin_timestamps) >= start, np.asarray(self.begin_timestamps) < end),
                np.logical_and(np.asarray(self.end_timestamps) >= start, np.asarray(self.end_timestamps) < end))
            segment_scores.append(np.mean(np.asarray(self.magnitudes)[idx]))

        # normalize
        scores = segment_scores / np.percentile(segment_scores, self.clip_percentile)
        scores = np.clip(scores, a_min=0, a_max=1) * 100.
        scores = list(np.round(scores, decimals=2))

        self.convert([{'begin': self.begin_timestamps[0],
                       'end': self.end_timestamps[-1],
                       'content': " ".join(["{s:.2f}".format(s=s) for s in scores])}])

    # def generate_normalized_annotations(self):
    #     segment_scores = list()
    #
    #     self.progress(0, _("Generating annotations"))
    #     for i, start in enumerate(self.begin_timestamps):
    #         self.progress(i / len(self.begin_timestamps))
    #         end = start + self.step_size
    #         idx = np.logical_or(
    #             np.logical_and(np.asarray(self.begin_timestamps) >= start, np.asarray(self.begin_timestamps) < end),
    #             np.logical_and(np.asarray(self.end_timestamps) >= start, np.asarray(self.end_timestamps) < end))
    #         segment_scores.append(np.mean(np.asarray(self.magnitudes)[idx]))
    #
    #     # normalize
    #     segment_scores /= np.max(segment_scores)
    #     segment_scores *= 100.
    #
    #     self.convert([{'begin': self.begin_timestamps[0],
    #                    'end': self.end_timestamps[-1],
    #                    'content': " ".join(["{s:.2f}".format(s=s) for s in segment_scores])}])

    def do_finalize(self):
        while len(self.end_timestamps) < len(self.begin_timestamps):
            begin_frame = self.begin_frame_pixbufs[len(self.end_timestamps)]
            flow = cv2.calcOpticalFlowFarneback(begin_frame, self.last_frame_pixbuf,
                                                flow=None,
                                                pyr_scale=0.5,
                                                levels=3,
                                                winsize=15,
                                                iterations=3,
                                                poly_n=5,
                                                poly_sigma=1.2,
                                                flags=0)
            # mag and ang are matrices with the shape of the frame
            mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            self.magnitudes.append(np.sum(mag))
            self.end_timestamps.append(self.last_frame_timestamp)

        assert len(self.begin_timestamps) == len(self.end_timestamps) == len(self.magnitudes)
        self.normalize_and_clip()
        return True

    def process_frame(self, frame):
        cur_ts = int(frame['date'])
        self.last_frame_timestamp = cur_ts

        channels = 1
        width = int(self.frame_width)
        height = int(len(frame['data']) / channels / width)
        cur_pixbuf = np.frombuffer(frame['data'], dtype=np.uint8).reshape((height, width, channels))
        # always keep the last frame in the video in order to compute the last chunks:
        self.last_frame_pixbuf = cur_pixbuf

        if not len(self.begin_timestamps):
            self.begin_timestamps.append(cur_ts)
            self.begin_frame_pixbufs.append(cur_pixbuf)
        elif cur_ts >= self.begin_timestamps[-1] + self.step_size:
            self.begin_timestamps.append(cur_ts)
            self.begin_frame_pixbufs.append(cur_pixbuf)

        if len(self.begin_timestamps) > len(self.end_timestamps):
            if cur_ts >= self.begin_timestamps[len(self.end_timestamps)] + self.window_size:
                begin_frame = self.begin_frame_pixbufs[len(self.end_timestamps)]
                flow = cv2.calcOpticalFlowFarneback(begin_frame, cur_pixbuf,
                                                    flow=None,
                                                    pyr_scale=0.5,
                                                    levels=3,
                                                    winsize=15,
                                                    iterations=3,
                                                    poly_n=5,
                                                    poly_sigma=1.2,
                                                    flags=0)
                # mag and ang are matrices with shape of the frame
                mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
                self.magnitudes.append(np.sum(mag))
                self.end_timestamps.append(cur_ts)

        return True

    def setup_importer(self, filename):
        self.ensure_new_type('motiondynamics',
                             title=_("Motion Dynamics Extractor"),
                             mimetype='application/x-advene-values',
                             description=_("Motion dynamics from optical flow extraction"))

        return "videoconvert ! videoscale ! video/x-raw,width={frame_width},pixel-aspect-ratio=(fraction)1/1,format=GRAY8".format(
            frame_width=self.frame_width)
