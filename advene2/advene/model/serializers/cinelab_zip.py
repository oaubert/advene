"""
Cinelab serializer implementation.
"""

from advene.model.serializers.advene_zip import _Serializer as _BaseSerializer
import advene.model.serializers.cinelab_xml as cinelab_xml

NAME = "Cinelab Advene Zipped Package"

EXTENSION = ".czp" # Cinelab Zipped Package

MIMETYPE = "application/x-cinelab-zip-package"

def make_serializer(package, file_):
    """Return a serializer that will serialize `package` to `file_`.

    `file_` is a writable file-like object. It is the responsability of the
    caller to close it.
    """
    return _Serializer(package, file_)

def serialize_to(package, file_):
    """A shortcut for ``make_serializer(package, file).serialize()``.

    See also `make_serializer`.
    """
    return _Serializer(package, file_).serialize()

class _Serializer(_BaseSerializer):

    _xml_serializer = cinelab_xml
    mimetype = MIMETYPE
