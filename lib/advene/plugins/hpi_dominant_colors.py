# Dominant Color Extractor plugin for advene to quantize pixels in a video segment into a list of predefined colors.
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

import logging

from gettext import gettext as _

import cv2
import numpy as np
import json

import scipy.spatial
from scipy.cluster.vq import vq

from advene.util.gstimporter import GstImporter

name = "Dominant color extraction"

logger = logging.getLogger(__name__)

__SUPPORTED_COLORS_RGB__ = {'darkred': (139, 0, 0), 'firebrick': (178, 34, 34), 'crimson': (220, 20, 60),
                            'red': (255, 0, 0), 'tomato': (255, 99, 71), 'salmon': (250, 128, 114),
                            'darkorange': (255, 140, 0), 'gold': (255, 215, 0), 'darkkhaki': (189, 183, 107),
                            'yellow': (255, 255, 0), 'darkolivegreen': (85, 107, 47), 'olivedrab': (107, 142, 35),
                            'greenyellow': (173, 255, 47), 'darkgreen': (0, 100, 0), 'aquamarine': (127, 255, 212),
                            'steelblue': (70, 130, 180), 'skyblue': (135, 206, 235), 'darkblue': (0, 0, 139),
                            'blue': (0, 0, 255), 'royalblue': (65, 105, 225),
                            'violet': (238, 130, 238), 'deeppink': (255, 20, 147), 'pink': (255, 192, 203),
                            'antiquewhite': (250, 235, 215), 'saddlebrown': (139, 69, 19), 'sandybrown': (244, 164, 96),
                            'ivory': (255, 255, 240), 'dimgrey': (105, 105, 105),
                            'lightgrey': (211, 211, 211), 'black': (0, 0, 0),
                            'white': (255, 255, 255), 'khaki': (240, 230, 140), 'goldenrod': (218, 165, 32),
                            'orange': (255, 165, 0), 'coral': (255, 127, 80), 'magenta': (255, 0, 255),
                            'cyan': (0, 255, 255),
                            'darkcyan': (0, 139, 139), 'green': (0, 255, 0),
                            'wheat1': (245, 222, 179),
                            'purple': (160, 32, 240),
                            'grey': (190, 190, 190),
                            'silver': (208, 208, 208),
                            'purple4': (85, 26, 139),
                            }


class DomCol(object):
    def __init__(self, named_colors):
        self.named_centroids = named_colors

    def map_color_name(self, color_rgb):
        dists = dict()
        for c in self.named_centroids:
            dists[c] = scipy.spatial.distance.sqeuclidean(self.named_centroids[c], color_rgb)

        # sort dists ascending - color with smallest dist to query color is the most likely hit
        sorted_dists = sorted(dists.items(), key=lambda kv: kv[1])

        return sorted_dists[0][0], sorted_dists[0][1]

    def cluster_colors(self, pixmaps):
        if len(pixmaps.shape) != 4 or pixmaps.shape[2] != 3:
            raise ValueError(
                "Invalid pixamps definition - color array of shape 'channels x width x height x sample' required. "
                "Shape: {0}".format(pixmaps.shape)
            )

        # extract a samples x channels array of all pixels in pixmaps:
        pixels = pixmaps.transpose((2, 0, 1, 3))
        pixels = pixels.reshape((pixels.shape[0], pixels.shape[1] * pixels.shape[2] * pixels.shape[3])).T

        centroids = np.zeros((len(self.named_centroids), pixels.shape[1]))
        for i, c in enumerate(self.named_centroids):
            centroids[i][:] = self.named_centroids[c]

        # assign codes, nns: row index of nearest centroid, dist: distance of pixel to nearest centroid:
        nns, dist = vq(pixels, centroids)

        # return sorted unique nns, i.e. the unique row indices in centroids and the frequencies
        idx, cnts = np.unique(nns, return_counts=True)

        dom_col_size = [cnts[c] / pixels.shape[0] for c in np.argsort(cnts)[::-1]]
        dom_cols = [centroids[c] for c in idx[np.argsort(cnts)[::-1]]]

        return zip(dom_cols, dom_col_size)


class DomColExtractor(GstImporter):
    name = _("Dominant Color Extractor")
    annotation_filter = False

    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        return 80

    can_handle = staticmethod(can_handle)

    def __init__(self, author=None, package=None, defaulttype=None,
                 controller=None, callback=None, source_type=None):
        super().__init__(author=author,
                         package=package,
                         defaulttype=defaulttype,
                         controller=controller,
                         callback=callback,
                         source_type=source_type)

        if self.source_type is None:
            self.source_type = self.controller.package.annotationTypes[0]
        self.source_type_id = self.source_type.id

        if source_type is not None:
            # A source_type was specified at instantiation. Update the
            # preferences now since we will use this info to update
            # the filter options.
            self.get_preferences().update({'source_type_id': self.source_type_id})

        ##################################
        self.frame_width = 240
        self.offset = 40     # the segment offset - added/subtracted from segment boundaries
        self.stepsize = 500  # every stepsize milliseconds, a frame is considered for color extraction
        self.cur_ann_begin = None
        self.cur_ann_end = None
        self.cur_ann_pixbufs = []
        self.last_considered_ts = None
        self.annotations = []

        self.rel_cluster_size = 0.05
        self.cluster_compactness = 0.8
        self.colorspace = 'cie-lab'
        self.colors = json.dumps(__SUPPORTED_COLORS_RGB__)
        self.dc = None
        #################################

        self.optionparser.add_option(
            "-t", "--source-type-id", action="store", type="choice", dest="source_type_id",
            choices=[at.id for at in self.controller.package.annotationTypes],
            default=self.source_type_id,
            help=_("Type of annotation to analyze"),
        )
        self.optionparser.add_option(
            "--colorspace", action="store", type="choice", dest="colorspace",
            choices=['rgb', 'hsv', 'cie-lab'],
            default='cie-lab',
            help=_("defines the colorspace that is used by color extractor"),
        )
        self.optionparser.add_option(
            "--cluster_size", action="store", type="float",
            dest="rel_cluster_size", default=0.05,
            help=_(
                "A color is ignored if the fraction of all assigned pixels of a segment is below the given threshold."),
        )
        self.optionparser.add_option(
            "--cluster_compactness", action="store", type="float",
            dest="cluster_compactness", default=0.8,
            help=_(
                "A color is ignored if the mean distance between all assigned pixels and the color value is below "
                "the given threshold."),
        )

        self.optionparser.add_option(
            "--colors", action="store", type=str,
            dest="colors", default=json.dumps(__SUPPORTED_COLORS_RGB__),
            help=_(
                "Defines the colors that are used for color extraction. " +
                "Format is { 'color1': [R,G,B], 'color2': [R,G,B], ... }."),
        )

    def check_requirements(self):
        """Check if external requirements for the importers are met.

        It returns a list of strings describing the unmet
        requirements. If the list is empty, then all requirements are
        met.
        """
        unmet_requirements = []

        if self.colorspace not in ["rgb", "hsv", "cie-lab"]:
            unmet_requirements.append(_("Unsupported color space: {cs}".format(
                cs=self.colorspace)))

        if self.rel_cluster_size <= 0 or self.rel_cluster_size >= 1.0:
            unmet_requirements.append(_("Relative cluster size must be > 0.0 and < 1.0."))

        if self.cluster_compactness <= 0 or self.cluster_compactness >= 1.0:
            unmet_requirements.append(_("Cluster compactness must be > 0.0 and < 1.0."))

        colors = dict()
        try:
            colors = json.loads(self.colors)
        except Exception:
            unmet_requirements.append(_("Invalid color format: {colors}".format(
                colors=str(self.colors))))

        # parse and convert selected color values into selected colorspace
        for col in colors:
            r, g, b = colors[col]
            if not 0 <= r <= 255 or not 0 <= g <= 255 or not 0 <= b <= 255:
                unmet_requirements.append(_("Invalid RGB value for color {color}: ({r},{g},{b})".format(
                                            color=col, r=r, g=g, b=b)))
                continue

            rgb = np.asarray(colors[col], dtype='float32').reshape((1, 1, 3))

            if self.colorspace == 'rgb':
                color_val = rgb
            elif self.colorspace == 'hsv':
                color_val = cv2.cvtColor(rgb / 255., cv2.COLOR_RGB2HSV)
            elif self.colorspace == 'cie-lab':
                color_val = cv2.cvtColor(rgb / 255., cv2.COLOR_RGB2LAB)
            else:
                continue

            if col in colors:
                colors[col] = color_val

        self.dc = DomCol(named_colors=colors)

        return unmet_requirements

    def do_finalize(self):
        if len(self.cur_ann_pixbufs):
            cnames = self.extract_dominant_colors(self.cur_ann_pixbufs)
            self.annotations.append({
                'begin': self.cur_ann_begin,
                'end': self.cur_ann_end,
                'content': ",".join(cnames)
            })

        self.convert(f for f in self.annotations)

    def extract_dominant_colors(self, frame_list):
        if type(frame_list) is list:
            pixmaps = np.stack(frame_list, axis=3)
        elif type(frame_list) is np.ndarray:
            pixmaps = frame_list
        else:
            raise ValueError("Invalid frame list!")

        if len(pixmaps.shape) != 4 or pixmaps.shape[2] != 3:
            raise ValueError("Invalid frame list!")

        dom_cols = self.dc.cluster_colors(pixmaps=pixmaps)

        cnames = list()
        for col in dom_cols:
            logger.debug("{0} ({1})".format(self.dc.map_color_name(col[0])[0], col[1]))
            if col[1] >= self.rel_cluster_size:
                cnames.append("{col} ({si})".format(col=self.dc.map_color_name(col[0])[0], si=col[1]))

        return cnames

    def process_frame(self, frame):
        cur_ts = int(frame['date'])

        for i, anno in enumerate(self.source_type.annotations):
            if anno.fragment.begin + self.offset <= cur_ts <= anno.fragment.end - self.offset:
                if self.cur_ann_begin != anno.fragment.begin or self.cur_ann_end != anno.fragment.end:
                    if len(self.cur_ann_pixbufs):
                        # we have a new annotation - need to extract dominant colors from previous one
                        cnames = self.extract_dominant_colors(self.cur_ann_pixbufs)
                        self.annotations.append({
                            'begin': self.cur_ann_begin,
                            'end': self.cur_ann_end,
                            'content': ",".join(cnames)
                        })
                        self.cur_ann_pixbufs = list()

                    self.cur_ann_begin = anno.fragment.begin
                    self.cur_ann_end = anno.fragment.end
                    self.last_considered_ts = None

                # current timestamp lies within an annotation - check if we need to consider the frame:
                if self.last_considered_ts is None or self.last_considered_ts + self.stepsize <= cur_ts <= anno.fragment.end:
                    channels = 3
                    width = int(self.frame_width)
                    height = int(len(frame['data']) / channels / width)
                    cur_pixbuf = np.frombuffer(frame['data'], dtype=np.uint8).reshape((height, width, channels))
                    cur_pixbuf = np.asarray(cur_pixbuf, dtype=np.float32)
                    if self.colorspace == 'rgb':
                        pass
                    elif self.colorspace == 'hsv':
                        cur_pixbuf = cv2.cvtColor(cur_pixbuf / 255., cv2.COLOR_RGB2HSV)
                    elif self.colorspace == 'cie-lab':
                        cur_pixbuf = cv2.cvtColor(cur_pixbuf / 255., cv2.COLOR_RGB2LAB)
                    else:
                        raise ValueError("unknown colorspace!")

                    self.cur_ann_pixbufs.append(cur_pixbuf)
                    self.last_considered_ts = cur_ts
        return True

    def setup_importer(self, filename):
        self.source_type = self.controller.package.get_element_by_id(self.source_type_id)
        self.ensure_new_type('domcols',
                             title=_("Dominant Color Extractor"),
                             mimetype='text/plain',
                             description=_("Quantizes pixel RGB values into list of named colors."))

        return "videoconvert ! videoscale ! video/x-raw,width={frame_width},pixel-aspect-ratio=(fraction)1/1," \
               "format=RGB".format(frame_width=self.frame_width)


def register(controller=None):
    controller.register_importer(DomColExtractor)
    return True
