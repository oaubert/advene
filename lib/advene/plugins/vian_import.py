#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2020 Olivier Aubert <contact@olivieraubert.net>
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

# VIAN importer

name="VIAN importer"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _
import json
import os

import advene.core.config as config
from advene.util.importer import GenericImporter

def register(controller=None):
    controller.register_importer(VIANImporter)
    return True

class VIANImporter(GenericImporter):
    """Import a VIAN file.
    """
    name = _("VIAN importer")

    @staticmethod
    def can_handle(fname):
        """Return a score between 0 and 100.
        100 is for the best match (specific extension), 0 is for no match at all.
        """
        ext = os.path.splitext(fname)[1]
        if ext in [ '.eext' ]:
            return 90
        return 0

    def process_file(self, filename, dest=None):
        with open(filename, 'r') as f:
            vian = json.load(f)
        hdfname = os.path.join(os.path.dirname(filename), 'data', 'analyses.hdf5')
        if not os.path.exists(hdfname):
            hdfname = None
        p, at = self.init_package(filename=dest)
        p.setMetaData(config.data.namespace_prefix['dc'],
                      'description',
                      _("Converted from %s") % filename)
        self.convert(self.iterator(vian, hdfname))
        self.progress(1.0)
        return self.package

    def iterator(self, vian, hdf5_path = None):
        """Iterate through the loaded JSON
        """
        progress=0.01

        self.progress(progress, "Starting conversion")

        self.package.setMedia(vian['movie_descriptor']['movie_path'])
        duration = vian['movie_descriptor']['duration']
        self.package.setMetaData(config.data.namespace, "duration", str(duration))
        self.controller.notify('DurationUpdate', duration=duration)

        incr = 0.05
        ntypes = len(vian['segmentation']) + len(vian['experiments'])
        if ntypes > 0:
            incr = 1 / ntypes

        annotation_cache = {}

        # Map segments to annotations and keep a dict of segments
        for segmentation in vian['segmentation']:
            progress += incr

            self.progress(progress, f"Converting segmentation {segmentation['name']}")
            new_atype = self.ensure_new_type(segmentation['unique_id'],
                                             title = segmentation['name'],
                                             # FIXME: should get it from first segment?
                                             mimetype = 'text/plain',
                                             description = segmentation['notes'])

            for segment in segmentation['segments']:
                an = {
                    "type": new_atype,
                    "begin": segment['start_ms'],
                    "end": segment['end_ms'],
                    "id": segment['unique_id'],
                    # FIXME: we lose the segment['name'] here
                    "content": segment['annotation_body'][0]['content'],
                }
                annotation_cache[an['id']] = an
                yield an

        # We also have to collect the screenshots to map to the classification
        new_atype = self.ensure_new_type('screenshot',
                                         title='Screenshot')
        for scr in vian['screenshots']:
            annotation_cache[scr['unique_id']] = {
                "type": new_atype,
                "begin": scr['start_ms'],
                "end": scr['end_ms'],
                "id": scr['unique_id'],
                "content": scr['name'],
            }

        # VIAN Keywords are a composite of VocabularyWord and ClassificationObject
        # We first have to collect all vocabularies from the project, before we can unpack the experiment.
        # These are stored globally in the project root, and referenced in the experiments
        vocabulary_words = {}
        for voc in vian['vocabularies']:
            for word in voc['words']:
                advene_word = dict(
                    id = word['unique_id'],
                    vocabulary = voc['name'],
                    word = word['name']
                )
                vocabulary_words[word['unique_id']] = advene_word

        # To resolve the classification within an experiment we have
        # to collect the classification objects in a map

        # Because the analyses currently reference the
        # ClassificationObject and not the semantic segmentation
        # labels, we have to keep them globally, this will likely
        # change in VIAN in the future.
        all_classification_objects = {}

        # Map classification results to annotations
        for expe in vian['experiments']:
            progress += incr

            self.progress(progress, f"Converting experiment {expe['name']}")
            new_atype = self.ensure_new_type(expe['unique_id'],
                                             title = f"Experiment {expe['name']}",
                                             mimetype = 'text/x-advene-keyword-list')

            # Again, VIAN keywords are composites of a VocabularyWord and a ClassificationObject
            # We now collect the classification objects from this experiment, an store them globally
            # dereferencing them in the later analyses

            # The keywords for each ClassificationObject are store within it.
            experiment_keywords = {}

            for cl_obj in expe['classification_objects']:

                # First extract the classification object
                all_classification_objects[cl_obj['unique_id']] = dict(
                    id = cl_obj['unique_id'],
                    name=cl_obj['name'],
                    semantic_segmentation = cl_obj['semantic_segmentation_labels'],
                )

                # Then we assemble all keywords which are stored within the classification object:
                for kwd in cl_obj['unique_keywords']:
                    experiment_keywords[kwd['unique_id']] = dict(
                        id=kwd['unique_id'],
                        voc_word = vocabulary_words[kwd['word_obj']],
                        classification_obj = all_classification_objects[cl_obj['unique_id']]
                    )

            new_atype.setMetaData(config.data.namespace, "value_metadata", json.dumps(dict(
                (data['voc_word']['word'], {
                    "uid": data['id'],
                    "voc_word": data['voc_word'],
                })
                for kwuid, data in experiment_keywords.items())))
            new_atype.setMetaData(config.data.namespace, "completions", ",".join(kw['voc_word']['word']
                                                                                 for kw in experiment_keywords.values()))

            for result in expe['classification_results']:
                target = annotation_cache.get(result['target'])
                keyword = experiment_keywords.get(result['keyword'])

                if target is None:
                    logger.warning("Cannot find segment for %s", result['target'])
                elif keyword is None:
                    logger.warning("Cannot find keyword for %s", result['keyword'])
                else:
                    yield {
                        "type": new_atype,
                        "begin": target['begin'],
                        "end": target['end'],
                        "content": keyword['voc_word']['word'],
                    }

        # Extract the HDF5-stored analyses results.
        # I just import them by example including the values from the hdf5 file, so you know how to access them
        if hdf5_path is not None:
            import h5py
            import numpy as np
            hdf5_file = h5py.File(hdf5_path, mode="r")
            # data tables: hdf5_file.keys()
            for an in vian['analyses']:
                # If the analysis is not one of the following serialization types, it is probably not important for Advene
                # there is also the ColorimetryAnalysis, which contains a continous dataset, we can discuss this later
                if an['vian_serialization_type'] not in ['SemanticSegmentationAnalysisContainer', 'IAnalysisJobAnalysis']:
                    continue

                # Find the annotation which this analysis has been computed on
                target = annotation_cache.get(an['container'])
                if target is None:
                    logger.warning("Cannot find target for %s", an['container'])
                    continue

                hdf5_dataset = an['hdf5_location']['hdf5_dataset']
                hdf5_index = an['hdf5_location']['hdf5_index']

                analysis = dict(
                    id = an['unique_id'],
                    begin = target['begin'],
                    end = target['end'],
                    type = an['vian_analysis_type'],
                    vian_analysis_type = an['vian_analysis_type'],
                    hdf5_dataset = hdf5_dataset,
                    hdf5_index = hdf5_index,
                    # Use HDF5 URI syntax from https://github.com/taurus-org/h5file-scheme
                    uri = f'h5file:{os.path.abspath(hdf5_path)}::{hdf5_dataset}/{hdf5_index}'
                )

                # Semantic segmentations have the vian_analysis_type SemanticSegmentationAnalysis
                if an['vian_analysis_type'] == "SemanticSegmentationAnalysis":
                    # This is the same as in ClassificationObject.semantic_segmentation_labels.model
                    analysis['semantic_segmentation_dataset'] = an['dataset']

                    # A mask of labels referencing corresponding to
                    # ClassificationObject.semantic_segmentation_labels.labels.label
                    analysis['mask'] = hdf5_file[hdf5_dataset][hdf5_index]
                    analysis['content'] = analysis['uri']

                else:
                    # if the classification object is not -1, a semantic segmentation has been used with this
                    # analysis.
                    cl_obj = an['classification_obj']
                    if cl_obj != -1:
                        cl_obj = all_classification_objects.get(cl_obj)
                    else:
                        cl_obj = None
                    analysis['classification_object'] = cl_obj
                    analysis['content'] = cl_obj

                    # Extract the color features
                    if an['vian_analysis_type'] == "ColorFeatureAnalysis":
                        # See feature vector memory layout here
                        # https://www.vian.app/static/manual/dev_guide/analyses/color_features.html#module-core.analysis.color_feature_extractor

                        analysis['lab'] = hdf5_file[hdf5_dataset][hdf5_index][:3]
                        analysis['rgb'] = hdf5_file[hdf5_dataset][hdf5_index][3:6][::-1]

                        analysis['content'] = analysis['rgb'].tolist()
                        analysis['mimetype'] = 'application/json'

                    elif an['vian_analysis_type'] == "ColorPaletteAnalysis":
                        # See feature vector memory layout here
                        # https://www.vian.app/static/manual/dev_guide/analyses/color_features.html#module-core.analysis.palette_analysis
                        merge_depth = 6
                        total_palette = hdf5_file[hdf5_dataset][hdf5_index]
                        merge_depth_indices = np.where(total_palette[:, 1] == merge_depth)[0]
                        total_num_pixel = np.sum(total_palette[merge_depth_indices, 5])
                        analysis['palette'] = []
                        for j in merge_depth_indices.tolist():
                            analysis['palette'].append(dict(
                                color_rgb = total_palette[j,2:5][::-1].tolist(),
                                relative_size = (total_palette[j,5].astype(np.float32) / total_num_pixel).tolist()
                            ))
                        analysis['content'] = analysis['palette']
                        analysis['mimetype'] = 'application/json'

                    elif an['vian_analysis_type'] == "ColorHistogramAnalysis":
                        # See feature vector memory layout here
                        # https://www.vian.app/static/manual/dev_guide/analyses/color_features.html#module-core.analysis.histogram_analysis
                        analysis['color_histogram'] = hdf5_file[hdf5_dataset][hdf5_index]
                        analysis['content'] = analysis['color_histogram'].tolist()
                        analysis['mimetype'] = 'application/json'
                yield analysis

        self.progress(1.0)
