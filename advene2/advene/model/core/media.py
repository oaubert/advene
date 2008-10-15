"""
I define the class of medias.
"""

from advene.model import ADVENE_NS_PREFIX
from advene.model.core.element import PackageElement, MEDIA

FOREF_PREFIX = "%s%s" % (ADVENE_NS_PREFIX, "frame_of_reference/")

class Media(PackageElement):

    ADVENE_TYPE = MEDIA

    def __init__(self, owner, id, url, frame_of_reference):
        PackageElement.__init__(self, owner, id)
        self._url = url
        self._frame_of_reference = frame_of_reference
        self._update_unit_and_origin()

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

    @property
    def unit(self):
        """Return the time-unit of this media if known, else None.

        The unit is known if the frame of reference is in the default Advene
        namespace.

        NB: this is specifid to the cinelab application model.
        """
        return self._unit

    @property
    def origin(self):
        """Return the time-origin of this media if known, else None.

        The origin is known if the frame of reference is in the default Advene
        namespace.

        NB: this is specifid to the cinelab application model.
        """
        return self._origin

    def _update_unit_and_origin(self):
        foref = self._frame_of_reference
        if foref.startswith(FOREF_PREFIX):
            foref = foref[len(FOREF_PREFIX):]
            self._unit, params = foref.split(";")
            params = dict( i.split("=") for i in params.split("&") )
            self._origin = params.get("o", 0)
        else:
            self._unit = None
            self._origin = None
        

    def __clean(self):
        o = self._owner
        o._backend.update_media(o._id, self.id, self._url,
                                self._frame_of_reference)
