"""Id generator."""

import sre

from advene.model.package import Package
from advene.model.annotation import Annotation, Relation
from advene.model.schema import Schema, AnnotationType, RelationType
from advene.model.view import View
from advene.model.query import Query

class Generator:
    prefix = {
        Package: "p",
        Annotation: "a",
        Relation: "r",
        Schema: "schema_",
        AnnotationType: "at_",
        RelationType: "rt_",
        View: "view_",
        Query: "query_",
        }
    
    def __init__(self):
        self.last_used={}
        for k in self.prefix.keys():
            self.last_used[k]=0

    def init(self, package):
        """Initialize the indexes for the given package."""
        prefixes=self.prefix.values()
        re_id = sre.compile("^(" + "|".join(prefixes) + ")([0-9]+)")
        last_id={}
        for k in prefixes:
            last_id[k]=0

        # FIXME: find all package ids
        for l in (package.annotations, package.relations,
                  package.schemas,
                  package.annotationTypes, package.relationTypes,
                  package.views, package.queries):
            for i in l.ids():
                m=re_id.match(i)
                if m:
                    n=long(m.group(2))
                    k=m.group(1)
                    if last_id[k] < n:
                        last_id[k] = n
        # last_id contains the last index used for each prefix
        self.last_used = dict(last_id)

    def get_id(self, elementtype):
        prefix=self.prefix[elementtype]
        index=self.last_used[prefix] + 1
        self.last_used[prefix]=index
        return prefix + str(index)

