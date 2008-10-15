"""
I define the class of views.
"""

from advene.model.core.element import PackageElement, VIEW
from advene.model.core.content import WithContentMixin
from advene.model.exceptions import NoContentHandlerError
from advene.model.view.register import iter_view_handlers

class View(PackageElement, WithContentMixin):

    ADVENE_TYPE = VIEW

    def __init__(self, owner, id, mimetype, model, url):
        """FIXME: missing docstring.
        """
        PackageElement.__init__(self, owner, id)
        self._handler = None
        self._set_content_mimetype(mimetype, _init=True)
        self._set_content_model(model, _init=True)
        self._set_content_url(url, _init=True)

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
