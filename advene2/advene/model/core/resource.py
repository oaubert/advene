"""
I define the class of resources.
"""

from advene.model.core.element import PackageElement, RESOURCE
from advene.model.core.content import WithContentMixin

class Resource(PackageElement, WithContentMixin):

    ADVENE_TYPE = RESOURCE

    @classmethod
    def instantiate(cls, owner, id, mimetype, model, url, *args):
        r = super(Resource, cls) \
                .instantiate(owner, id, mimetype, model, url, *args)
        r._instantiate_content(mimetype, model, url)
        return r

    @classmethod
    def create_new(cls, owner, id, mimetype, model, url):
        model_id = PackageElement._check_reference(owner, model, RESOURCE)
        cls._check_content_cls(mimetype, model_id, url)
        owner._backend.create_resource(owner._id, id, mimetype, model_id, url)
        r = cls.instantiate(owner, id, mimetype, model_id, url)
        return r

#
