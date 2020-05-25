#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2018 Olivier Aubert <contact@olivieraubert.net>
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

name="Keyword extraction plugin"

import logging
logger = logging.getLogger(__name__)

from gettext import gettext as _

try:
    import nltk
except ImportError:
    nltk = None

import operator
import string

from advene.util.importer import GenericImporter

def register(controller=None):
    if nltk is None:
        logger.warning("nltk module is not available. Keyword extract plugin is disabled.")
    else:
        controller.register_importer(KeywordImporter)
    return True


class KeywordImporter(GenericImporter):
    name = _("Keyword extraction")
    annotation_filter = True

    def __init__(self, author=None, package=None, defaulttype=None,
                 controller=None, callback=None, source_type=None):
        GenericImporter.__init__(self,
                                 author=author,
                                 package=package,
                                 defaulttype=defaulttype,
                                 controller=controller,
                                 callback=callback,
                                 source_type=source_type)
        if self.source_type is None:
            self.source_type = self.controller.package.annotationTypes[0]
        self.source_type_id = self.source_type.id

        if source_type is not None:
            # A source_type was specified at instanciation. Update the
            # preferences now since we will use this info to update
            # the filter options.
            self.get_preferences().update({'source_type_id': self.source_type_id})

        self.confidence = 0.0

        self.optionparser.add_option(
            "-t", "--source-type-id", action="store", type="choice", dest="source_type_id",
            choices=[at.id for at in self.controller.package.annotationTypes],
            default=self.source_type_id,
            help=_("Type of annotation to analyze"),
            )
        self.optionparser.add_option(
            "-c", "--min-confidence", action="store", type="float",
            dest="confidence", default=0.0,
            help=_("Minimum confidence level (between 0.0 and 1.0)"),
            )

    def process_file(self, _filename):
        self.convert(self.iterator())

    def iterator(self):
        """I iterate over the created annotations.
        """
        rake = RakeKeywordExtractor()
        logger.warning("Detection keywords")
        self.source_type = self.controller.package.get_element_by_id(self.source_type_id)

        new_atype = self.ensure_new_type("%s_keywords" % self.source_type.id,
                                         mimetype = "text/x-advene-keyword-list")
        self.progress(.1, "Sending request to server")
        for a in self.source_type.annotations:
            keywords = rake.extract(a.content.data)
            if keywords:
                an = yield {
                    'type': new_atype,
                    'begin': a.fragment.begin,
                    'end': a.fragment.end,
                    'content': ",".join(keywords)
                }

# Downloaded from http://sujitpal.blogspot.fr/2013/03/implementing-rake-algorithm-with-nltk.html
# Adapted from: github.com/aneesha/RAKE/rake.py

def isPunct(word):
    return len(word) == 1 and word in string.punctuation

def isNumeric(word):
    try:
        float(word) if '.' in word else int(word)
        return True
    except ValueError:
        return False

class RakeKeywordExtractor:
    def __init__(self):
        self.stopwords = set(nltk.corpus.stopwords.words())
        self.top_fraction = 1 # consider top third candidate keywords by score

    def _generate_candidate_keywords(self, sentences):
        phrase_list = []
        for sentence in sentences:
            words = map(lambda x: "|" if x in self.stopwords else x,
                        nltk.word_tokenize(sentence.lower()))
            phrase = []
            for word in words:
                if word == "|" or isPunct(word):
                    if len(phrase) > 0:
                        phrase_list.append(phrase)
                        phrase = []
                    else:
                        phrase.append(word)
        return phrase_list

    def _calculate_word_scores(self, phrase_list):
        word_freq = nltk.FreqDist()
        word_degree = nltk.FreqDist()
        for phrase in phrase_list:
            degree = len(list(filter(lambda x: not isNumeric(x), phrase))) - 1
        for word in phrase:
            word_freq.update([word])
            word_degree.update([word, degree]) # other words
        for word in word_freq.keys():
            word_degree[word] = word_degree[word] + word_freq[word] # itself
            # word score = deg(w) / freq(w)
        word_scores = {}
        for word in word_freq.keys():
            word_scores[word] = word_degree[word] / word_freq[word]
        return word_scores

    def _calculate_phrase_scores(self, phrase_list, word_scores):
        phrase_scores = {}
        for phrase in phrase_list:
            phrase_score = 0
            for word in phrase:
                phrase_score += word_scores[word]
            phrase_scores[" ".join(phrase)] = phrase_score
        return phrase_scores

    def extract(self, text, incl_scores=False):
        sentences = nltk.sent_tokenize(text)
        phrase_list = self._generate_candidate_keywords(sentences)
        word_scores = self._calculate_word_scores(phrase_list)
        phrase_scores = self._calculate_phrase_scores(
            phrase_list, word_scores)
        sorted_phrase_scores = sorted(phrase_scores.items(),
                                      key=operator.itemgetter(1), reverse=True)
        n_phrases = len(sorted_phrase_scores)
        if incl_scores:
            return sorted_phrase_scores[0:int(n_phrases/self.top_fraction)]
        else:
            return map(lambda x: x[0],
                       sorted_phrase_scores[0:int(n_phrases/self.top_fraction)])
