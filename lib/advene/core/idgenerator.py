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
"""Identifier generator module."""

import re
import uuid

import advene.core.config as config

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.view import View
from advene.model.query import Query
import advene.util.helper as helper

class Generator:
    """Identifier generator.

    It keeps a track of ids for all elements from the package.
    """
    prefix = {
        Package: "p",
        Annotation: "a",
        Relation: "r",
        Schema: "schema_",
        AnnotationType: "at_",
        RelationType: "rt_",
        View: "view_",
        Query: "query_",
        Resources: "dir_",
        ResourceData: "res_",
        }

    def __init__(self, package=None):
        self.last_used={}
        self.existing=[]
        for k in self.prefix:
            self.last_used[k]=0
        if package is not None:
            self.init(package)

    def exists(self, id_):
        """Check if an id already exists.
        """
        return id_ in self.existing

    def add(self, id_):
        """Add a new known id.
        """
        self.existing.append(id_)

    def remove(self, id_):
        """Remove an id from the existing set.
        """
        try:
            self.existing.remove(id_)
        except ValueError:
            pass

    def init(self, package):
        """Initialize the indexes for the given package."""
        prefixes = list(self.prefix.values())
        re_id = re.compile("^(" + "|".join(prefixes) + ")([0-9]+)")
        last_id = {}
        for k in prefixes:
            last_id[k] = 0

        # FIXME: find all package ids
        for elements in (package.annotations, package.relations,
                         package.schemas,
                         package.annotationTypes, package.relationTypes,
                         package.views, package.queries):
            for i in elements.ids():
                self.existing.append(i)
                m = re_id.match(i)
                if m:
                    n = int(m.group(2))
                    k = m.group(1)
                    if last_id[k] < n:
                        last_id[k] = n
        # last_id contains the last index used for each prefix
        self.last_used = dict(last_id)

    def get_id(self, elementtype):
        """Return a not-yet used id.
        """
        if config.data.preferences['use-uuid']:
            id_ = str(uuid.uuid1())
        else:
            prefix=self.prefix[elementtype]
            index=self.last_used[prefix] + 1
            self.last_used[prefix]=index
            id_ = prefix + str(index)
            # Do not append yet.
            #self.existing.append(id_)
        return id_

    def new_from_title(self, title):
        """Generate a new (title, identifier) from a given title.
        """
        root=helper.title2id(title)
        index=1
        i="%s%d" % (root, index)
        while i in self.existing:
            index += 1
            i="%s%d" % (root, index)
        if index != 1:
            title="%s%d" % (title, index)
        return title, i
