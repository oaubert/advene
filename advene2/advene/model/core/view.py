"""
I define the class of views.
"""

from advene.model.core.element import PackageElement, VIEW, RESOURCE
from advene.model.core.content import WithContentMixin
from advene.model.exceptions import NoContentHandlerError
from advene.model.view.register import iter_view_handlers

class View(PackageElement, WithContentMixin):

    ADVENE_TYPE = VIEW

    # attributes that do not prevent views to be volatile
    _handler = None

    @classmethod
    def instantiate(cls, owner, id, mimetype, model, url):
        r = super(View, cls).instantiate(owner, id)
        r._instantiate_content(mimetype, model, url)
        return r

    @classmethod
    def create_new(cls, owner, id, mimetype, model, url):
        model_id = PackageElement._check_reference(owner, model, RESOURCE)
        cls._check_content_cls(mimetype, model_id, url)
        owner._backend.create_view(owner._id, id, mimetype, model_id, url)
        r = cls.instantiate(owner, id, mimetype, model_id, url)
        return r

    def _update_content_handler(self):
        "This overrides WithContentMixin._update_content_hanlder"
        m = self.content_mimetype
        cmax = 0; hmax = None
        for h in iter_view_handlers():
            c = h.claims_for_handle(m)
            if c > cmax:
                cmax, hmax = c, h
        if cmax > 0:
            self._handler = hmax
        else:
            # TODO issue a user warning ?
            self._handler = None
        super(View, self)._update_content_handler()

    def apply_to(self, obj):
        h = self._handler
        if  h is None:
            raise NoContentHandlerError(self._get_uriref())
        return h.apply_to(self, obj)

    @property
    def output_mimetype(self):
        h = self._handler
        if  h is None:
            raise NoContentHandlerError(self._get_uriref())
        return h.get_output_mimetype(self)
