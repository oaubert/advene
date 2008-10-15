"""
Unstable and experimental parser implementation.

See `advene.model.parsers.advene_xml` for the reference implementation.
"""

from tempfile import mkdtemp
from os import path, tmpfile
from zipfile import BadZipfile, ZipFile

from advene.model.consts import PACKAGED_ROOT
import advene.model.parsers.advene_xml as advene_xml
import advene.model.serializers.advene_zip as serializer
from advene.util.files import get_path, recursive_mkdir



class Parser(object):

    NAME = serializer.NAME
    EXTENSION = serializer.EXTENSION
    MIMETYPE = serializer.MIMETYPE
    SERIALIZER = serializer # may be None for some parsers

    @classmethod
    def claims_for_parse(cls, file_):
        """Is this parser likely to parse that file-like object?

        `file_` is a readable file-like object. It is the responsability of the
        caller to close it.
        """
        r = 0

        if hasattr(file_, "seek"):
            # try to open it as zip file and get the mimetype from archive
            t = file_.tell()
            try:
                z = ZipFile(file_, "r")
            except BadZipfile:
                return 0
            else:
                if "mimetype" in z.namelist():
                    if z.read("mimetype").startswith(cls.MIMETYPE):
                        return 80
                    else:
                        return 0
                elif "content.xml" in z.nameslit():
                    r = 20
                    # wait for other information to make up our mind
                else:
                    return 0
                z.close()
            file_.seek(t)
            
        info = getattr(file_, "info", lambda: {})()
        mimetype = info.get("content-type", "")
        if mimetype.startswith(cls.MIMETYPE):
            r = 80 # overrides extension
        elif mimetype.startswith("application/x-zip"):
            r += 30
            fpath = get_path(file_)
            raise Exception
            if fpath.endswith(cls.EXTENSION):
                r += 40
            elif fpath.endswith(".zip"):
                r += 20
        print "+++", r
        return r

    @classmethod
    def make_parser(cls, file_, package):
        """Return a parser that will parse `url` into `package`.

        `file_` is a writable file-like object. It is the responsability of the
        caller to close it.

        The returned object must implement the interface for which
        :class:`_Parser` is the reference implementation.
        """
        return cls(file_, package)

    @classmethod
    def parse_into(cls, file_, package):
        """A shortcut for ``make_parser(url, package).parse()``.

        See also `make_parser`.
        """
        cls(file_, package).parse()

    def parse(self):
        "Do the actual parsing."
        backend = self.package._backend
        pid = self.package._id
        backend.set_meta(pid, "", "", PACKAGED_ROOT, self.dir, False)
        # TODO use notification to clean it when package is closed
        f = open(self.content)
        self._XML_PARSER.parse_into(f, self.package)
        f.close()

    # end of public interface

    _XML_PARSER = advene_xml.Parser

    def __init__(self, file_, package):
        assert self.claims_for_parse(file_) > 0
        self.dir = d = mkdtemp()

        if hasattr(file_, "seek"):
            g = None
            z = ZipFile(file_, "r")
        else:
            # ZipFile requires seekable file, dump it in tmpfile
            g = tmpfile()
            g.write(file_.read())
            g.seek(0)
            z = ZipFile(g, "r")
        names = z.namelist()
        for zname in names:
            seq = zname.split("/")
            dirname = recursive_mkdir(d, seq[:-1])
            if seq[-1]:
                fname = path.join(dirname, seq[-1])
                h = open(fname, "w")
                h.write(z.read(zname))
                h.close()
        z.close()
        if g is not None:
            g.close()

        self.content = path.join(d, "content.xml")
        self.package = package

