"""
Unstable and experimental parser implementation.

See `advene.model.parsers.advene_xml` for the reference implementation.
"""

from os import mkdir, path, tmpfile
import sys
from tempfile import mkdtemp
from urllib import url2pathname, pathname2url
from urlparse import urlparse, urljoin
from zipfile import BadZipfile, ZipFile

from advene.model.consts import PACKAGED_ROOT
import advene.model.parsers.cinelab_xml as cinelab_xml
import advene.model.parsers.advene_zip as advene_zip
import advene.model.serializers.cinelab_zip as serializer
from advene.utils.files import get_path, recursive_mkdir 

class Parser(advene_zip.Parser):

    NAME = serializer.NAME
    EXTENSION = serializer.EXTENSION
    MIMETYPE = serializer.MIMETYPE
    SERIALIZER = serializer # may be None for some parsers

    _XML_PARSER = cinelab_xml.Parser
