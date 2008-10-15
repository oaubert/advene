"""
Unstable and experimental parser implementation.

See `advene.model.parsers.advene_xml` for the reference implementation.
"""

import advene.model.parsers.cinelab_xml as cinelab_xml
import advene.model.parsers.advene_zip as advene_zip
import advene.model.serializers.cinelab_zip as serializer

class Parser(advene_zip.Parser):

    NAME = serializer.NAME
    EXTENSION = serializer.EXTENSION
    MIMETYPE = serializer.MIMETYPE
    SERIALIZER = serializer # may be None for some parsers

    _XML_PARSER = cinelab_xml.Parser
