"""
I define the class of medias.
"""

from advene.model.core.element import PackageElement, MEDIA

class Media(PackageElement):

    ADVENE_TYPE = MEDIA

    def __init__(self, owner, id, url, frame_of_reference):
        PackageElement.__init__(self, owner, id)
        self._url = url
        self._frame_of_reference = frame_of_reference

    def _get_url(self):
        return self._url

    def _set_url(self, url):
        self._url = url
        self.add_cleaning_operation_once(self.__clean)

    def _get_frame_of_reference(self):
        return self._frame_of_reference

    def _set_frame_of_reference(self, frame_of_reference):
        self._frame_of_reference = frame_of_reference
        self.add_cleaning_operation_once(self.__clean)

    def __clean(self):
        o = self._owner
        o._backend.update_media(o._id, self.id, self._url,
                                self._frame_of_reference)
