"""
I define the class of medias.
"""

from advene.model.consts import ADVENE_NS_PREFIX
from advene.model.core.element import PackageElement, MEDIA
from advene.utils.autoproperty import autoproperty

FOREF_PREFIX = "%s%s" % (ADVENE_NS_PREFIX, "frame_of_reference/")
DEFAULT_FOREF = FOREF_PREFIX + "ms;o=0"

class Media(PackageElement):

    ADVENE_TYPE = MEDIA

    def __init__(self, owner, id, url, frame_of_reference=DEFAULT_FOREF):
        PackageElement.__init__(self, owner, id)
        self._url = url
        self._frame_of_reference = frame_of_reference
        self._update_unit_and_origin()

    @autoproperty
    def _get_url(self):
        """
        The URL from which the media can be fetched.
        """
        return self._url

    @autoproperty
    def _set_url(self, url):
        self.emit("pre-changed::url", "url", url)
        self._url = url
        self.__store()
        self.emit("changed::url", "url", url)

    @autoproperty
    def _get_frame_of_reference(self):
        return self._frame_of_reference

    @autoproperty
    def _set_frame_of_reference(self, frame_of_reference):
        self.emit("pre-changed::frame_of_reference",
                  "frame_of_reference", frame_of_reference)
        self._frame_of_reference = frame_of_reference
        self.__store()
        self._update_unit_and_origin()
        self.emit("changed::frame_of_reference",
                  "frame_of_reference", frame_of_reference)

    @autoproperty
    def _get_unit(self):
        """The time-unit of this media if known, else None.

        The unit is known if the frame of reference is in the default Advene
        namespace.

        NB: this is specific to the cinelab application model.
        """
        return self._unit

    @autoproperty
    def _get_origin(self):
        """The time-origin of this media if known, else None.

        The origin is known if the frame of reference is in the default Advene
        namespace.

        NB: this is specific to the cinelab application model.
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
        

    def __store(self):
        o = self._owner
        o._backend.update_media(o._id, self.id, self._url,
                                self._frame_of_reference)
