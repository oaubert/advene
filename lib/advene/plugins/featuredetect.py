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
name="Feature detection importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

import os

try:
    import cv2
except ImportError:
    cv2 = None

import advene.core.config as config
from advene.util.importer import GenericImporter
import advene.util.helper as helper

def register(controller=None):
    if cv2:
        controller.register_importer(FeatureDetectImporter)
    return True

class FeatureDetectImporter(GenericImporter):
    name = _("Feature detection (face...)")

    def __init__(self, *p, **kw):
        super(FeatureDetectImporter, self).__init__(*p, **kw)

        self.neighbors = 5
        self.scale = 2
        classifiers = [ n.replace('.xml', '') for n in os.listdir(config.data.advenefile('haars')) ]
        self.classifier = classifiers[0]

        # Detect that a shape has moved
        self.motion_threshold = 10

        self.optionparser.add_option("-n", "--min-neighbors",
                                     action="store", type="int", dest="neighbors", default=self.neighbors,
                                     help=_("Min neighbors."))
        self.optionparser.add_option("-m", "--motion-threshold",
                                     action="store", type="int", dest="motion_threshold", default=self.motion_threshold,
                                     help=_("Motion threshold."))
        self.optionparser.add_option("-s", "--scale",
                                     action="store", type="int", dest="scale", default=self.scale,
                                     help=_("Scale. Original image size will be divided by this factor, in order to speed up detection."))
        self.optionparser.add_option("-c", "--classifier",
                                     action="store", type="choice", dest="classifier", choices=classifiers, default=self.classifier,
                                     help=_("Classifier"))

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.

        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in config.data.video_extensions:
            return 80
        return 0

    def process_file(self, filename):
        at = self.ensure_new_type('feature',
                                  title=_("Feature %s") % self.classifier,
                                  mimetype='image/svg+xml',
                                  description=_("Detected %s") % self.classifier)

        self.progress(0, _("Detection started"))
        video = cv2.VideoCapture(str(filename))

        if not video:
            raise "Cannot read video file:"
        self.convert(self.iterator(video))
        return self.package

    def iterator(self, video):
        def svg_rect(x, y , w, h):
            return

        if not video.isOpened():
            return

        framecount = video.get(cv2.CAP_PROP_FRAME_COUNT)
        pos = 0
        # Take the first frame to get width/height
        ret, frame = video.read()
        width, height, depth = frame.shape
        scaled_width, scaled_height = int(width / self.scale), int(height / self.scale)
        logger.warning("Video dimensions %dx%d - scaled to %dx%d", width, height, scaled_width, scaled_height)

        cascade = cv2.CascadeClassifier(config.data.advenefile( ('haars', self.classifier + '.xml') ))
        count = 0

        svg_template = """<svg xmlns='http://www.w3.org/2000/svg' version='1' viewBox="0 0 %(scaled_width)d %(scaled_height)d" x='0' y='0' width='%(scaled_width)d' height='%(scaled_height)d'>%%s</svg>""" % locals()
        def objects2svg(objs, threshold=-1):
            """Convert a object-list into SVG.
            """
            return svg_template % "\n".join("""<rect style="fill:none;stroke:green;stroke-width:4;" width="%(w)d" height="%(h)s" x="%(x)s" y="%(y)s"></rect>""" % locals()
                                            for (x, y, w, h) in objs)

        start_pos = None

        while ret:

            gray = cv2.cvtColor(cv2.resize(frame, (scaled_width, scaled_height)), cv2.COLOR_RGB2GRAY)

            objects = cascade.detectMultiScale(gray, 1.2, self.neighbors) # scale_factor=1.2, min_neighbors=2

            def distance(v1, v2):
                d = max( abs(a - b)
                         for obj, sto in zip(objects, stored_objects)
                         for a, b in zip(obj, sto) )
                logger.debug("distance %d", d)
                return d

            if len(objects):
                logger.debug("Detected object %s", objects)
                # Detected face.
                if start_pos is None:
                    # Only create a new annotation if above threshold
                    stored_objects = objects[:]
                    start_pos = pos
                    count += 1
                else:
                    # A detection already occurred. Check if it not too different.
                    if (len(objects) != len(stored_objects)
                        or distance(objects, stored_objects) > self.motion_threshold):
                        logger.debug("------------------------------------ generate annotation ---------------------")
                        yield {
                            'begin': start_pos,
                            'end': pos,
                            'content': objects2svg(stored_objects),
                            }
                        stored_objects = objects[:]
                        start_pos = pos
                        count += 1
            elif start_pos is not None:
                 #End of feature(s)
                logger.debug("------------------------------------ generate annotation ---------------------")
                yield {
                    'begin': start_pos,
                    'end': pos,
                    'content': objects2svg(stored_objects),
                    }
                start_pos = None

            if not self.progress(video.get(cv2.CAP_PROP_POS_FRAMES) / framecount,
                                 _("Detected %(count)d feature(s) until %(time)s") % { 'count': count,
                                                                                       'time': helper.format_time(pos) }):
                break

            pos = video.get(cv2.CAP_PROP_POS_MSEC)
            ret, frame = video.read()

        # Last frame
        if start_pos is not None:
            yield {
                'begin': start_pos,
                'end': pos,
                'content': objects2svg(stored_objects),
                }
