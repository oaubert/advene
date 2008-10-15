"""
Unstable and experimental parser implementation.

See `advene.model.parsers.advene_xml` for the reference implementation.
"""

from os import mkdir, path, tmpnam
from os.path import exists
import sys
from urllib import url2pathname, pathname2url
from urlparse import urlparse, urljoin
from urllib2 import urlopen, URLError
from warnings import filterwarnings
from zipfile import ZipFile

from advene.model.consts import PACKAGED_ROOT
import advene.model.parsers.advene_xml as advene_xml

NAME = "Generic Advene Zipped Package"

MIMETYPE = "application/x-advene-bzp"

def claims_for_parse(url):
    """Is this parser likely to parse that URL?"""
    r = 0
    if not url.startswith("file:"):
        return 0 # ZipFile class requires seekable object
    try:
        f = urlopen(url)
    except URLError:
        return 0
    mimetype = f.info()["content-type"]
    f.close()
    pathname = url2pathname(urlparse(url).path)

    r = 0
    if mimetype.startswith("application/x-zip"):
        r = 30
        z = ZipFile(pathname, "r")
        if "mimetype" in z.namelist():
            mimetype = z.read("mimetype")
    if mimetype.startswith(MIMETYPE):
        r = 80
    else:
        if pathname.endswith(".bzp"):
            r += 40
        elif pathname.endswith(".zip"):
            r += 20
    f.close()
    return r

def make_parser(url, package):
    """Return a parser that will parse `url` into `package`.

    The returned object must implement the interface for which
    :class:`_Parser` is the reference implementation.
    """
    return _Parser(url, package)

def parse_into(url, package):
    """A shortcut for ``make_parser(url, package).parse()``.

    See also `make_parser`.
    """
    _Parser(url, package).parse()


class _Parser(object):

    def parse(self):
        "Do the actual parsing."
        backend = self.package._backend
        pid = self.package._id
        backend.set_meta(pid, "", "", PACKAGED_ROOT, self.dir_url, False)
        # TODO use notification to clean it when package is closed
        advene_xml.parse_into(self.file_url, self.package)

    # end of public interface

    def __init__(self, url, package):
        assert claims_for_parse(url) > 0
        filterwarnings("ignore",
            "tmpnam is a potential security risk to your program")
        self.dir = dir = tmpnam()
        mkdir(dir)

        f = open(url2pathname(urlparse(url).path))
        z = ZipFile(f, "r")
        names = z.namelist()
        for zname in names:
            fname = _recursive_mkdir(dir, zname.split("/"))
            #print "=== extracting", zname, "to", fname
            if fname:
                g = open(fname, "w")
                g.write(z.read(zname))
                g.close()
        f.close()

        self.dir_url = dir_url = "file:" + pathname2url(dir) + "/"
        self.file_url = urljoin(self.dir_url, "content.xml")
        self.package = package
        self.file = file

def _recursive_mkdir(dir, elems):
    if len(elems) > 1:
        newdir = path.join(dir, elems[0])
        if not exists(newdir):
            mkdir(newdir)
        return _recursive_mkdir(newdir, elems[1:])
    elif elems[0]: # the last item may be empty
        return path.join(dir, elems[0])
    else: # empty last item, was only a directory name
        return None
