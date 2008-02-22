#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Identifier generator module."""

import re

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.resources import Resources, ResourceData
from advene.model.view import View
from advene.model.query import Query

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
        for k in self.prefix.keys():
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

    def init(self, package):
        """Initialize the indexes for the given package."""
        prefixes=self.prefix.values()
        re_id = re.compile("^(" + "|".join(prefixes) + ")([0-9]+)")
        last_id={}
        for k in prefixes:
            last_id[k]=0

        # FIXME: find all package ids
        for l in (package.annotations, package.relations,
                  package.schemas,
                  package.annotationTypes, package.relationTypes,
                  package.views, package.queries):
            for i in l.ids():
                self.existing.append(i)
                m=re_id.match(i)
                if m:
                    n=long(m.group(2))
                    k=m.group(1)
                    if last_id[k] < n:
                        last_id[k] = n
        # last_id contains the last index used for each prefix
        self.last_used = dict(last_id)

    def get_id(self, elementtype):
        """Return a not-yet used id.
        """
        prefix=self.prefix[elementtype]
        index=self.last_used[prefix] + 1
        self.last_used[prefix]=index
        id_ = prefix + str(index)
        # Do not append yet.
        #self.existing.append(id_)
        return id_
