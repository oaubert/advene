"""
Unstable and experimental serializer implementation.

See `advene.model.serializers.advene_xml` for the reference implementation.
"""

from os import listdir, mkdir, path, tmpnam
from os.path import exists, isdir
from urllib import pathname2url, url2pathname
from urlparse import urlparse
from warnings import filterwarnings
from zipfile import ZipFile, ZIP_DEFLATED

from advene.model.consts import PACKAGED_ROOT
import advene.model.serializers.advene_xml as advene_xml

NAME = "Generic Advene Zipped Package"

SUGGESTED_EXTENSION = "bzp" # Advene-2 Zipped Package

def make_serializer(package, file):
    """Return a serializer that will serialize `package` to `file`.

    `file` is a writable file-like object.
    """
    return _Serializer(package, file)

def serialize_to(package, file):
    """A shortcut for ``make_serializer(package, file).serialize()``.

    See also `make_serializer`.
    """
    return _Serializer(package, file).serialize()

class _Serializer(object):

    def serialize(self):
        """Perform the actual serialization."""
        #print "=== serializing directory", self.dir
        f = open(path.join(self.dir, "content.xml"), "w")
        advene_xml.serialize_to(self.package, f)
        f.close()

        z = ZipFile(self.file, "w", self.compression)
        _recurse(z, self.dir)
        z.close()

    def __init__(self, package, file, compression=None):
        if compression is None:
            self.compression = ZIP_DEFLATED
        else:
            self.compression = compression
        root = package.get_meta(PACKAGED_ROOT, None)
        if root is None:
            filterwarnings("ignore",
                "tmpnam is a potential security risk to your program")
            self.dir = dir = tmpnam()
            mkdir(dir)
            url = "file:" + pathname2url(dir) + "/"
            package.set_meta(PACKAGED_ROOT, url)
            # TODO use notification to clean it when package is closed
        else:
            assert root.startswith("file:")
            self.dir = dir = url2pathname(urlparse(root).path)

        if not exists(path.join(dir, "mimetype")):
            f = open(path.join(dir, "mimetype"), "w")
            f.write("application/x-advene-bzp")
            f.close()
        if not exists(path.join(dir, "data")):
            mkdir(path.join(dir, "data"))

            
        self.package = package
        self.file = file


def _recurse(z, dir, base=""):
    for f in listdir(dir):
        abs = path.join(dir, f)
        if isdir(abs):
            _recurse(z, abs, path.join(base, f))
        else:
            #print "=== zipping", path.join(base, f)
            z.write(abs, path.join(base, f))


if __name__ == "__main__":
    # example of using ZIP serialization and parsing
    from advene.model.core.package import Package
    p = Package("file:/tmp/foo.bzp", create=True)

    # prepare directories
    if not exists("/tmp/foo"): mkdir("/tmp/foo")
    if not exists("/tmp/foo/data"): mkdir("/tmp/foo/data")

    # it is now safe to define the packaged-root of the package...
    p.set_meta(PACKAGED_ROOT, "file:/tmp/foo")
    # ... and to create packaged contents
    r = p.create_resource("R1", "text/plain", None, "packaged:/data/R1.txt")
    # this actually writes in /tmp/foo/data/R1.txt
    r.content_data = "good moaning\n"

    # let us serialize it...
    f = open("/tmp/foo.bzp", "w")
    serialize_to(p, f)
    f.close()
    # ... and parse it again
    q = Package("file:/tmp/foo.bzp")

    # note that advene_xml is smart enough to set the packaged-root if
    # needed, so as to allow to open manually-unzipped packages
    r = Package("file:/tmp/foo/content.xml")
    print r.get_meta(PACKAGED_ROOT)
