"""
I define the class Filter.
"""
from advene.model.core.element import PackageElement, QUERY, RESOURCE
from advene.model.core.content import WithContentMixin

class Query(PackageElement, WithContentMixin):

    ADVENE_TYPE = QUERY 

    @classmethod
    def instantiate(cls, owner, id, mimetype, model, url, *args):
        r = super(Query, cls) \
                .instantiate(owner, id, id, mimetype, model, url, *args)
        r._instantiate_content(mimetype, model, url)
        return r

    @classmethod
    def create_new(cls, owner, id, mimetype, model, url):
        model_id = PackageElement._check_reference(owner, model, RESOURCE)
        cls._check_content_cls(mimetype, model_id, url)
        owner._backend.create_query(owner._id, id, mimetype, model_id, url)
        r = cls.instantiate(owner, id, mimetype, model_id, url)
        return r

#
