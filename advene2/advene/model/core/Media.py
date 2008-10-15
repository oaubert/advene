"""
I define the class of medias.
"""

from advene.model.core.PackageElement import PackageElement, MEDIA

class Media(PackageElement):

    ADVENE_TYPE = MEDIA

    def __init__(self, owner, id, url):
        PackageElement.__init__(self, owner, id)
        self._url = url

    def _get_url(self):
        return self._url

    def _set_url(self, url):
        o = self._owner
        o._backend.update_media(o._id, self.id, url)
        self._url = url
