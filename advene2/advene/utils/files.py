from os import mkdir, path
from os.path import exists
from urllib import url2pathname
from urllib2 import urlopen
from urlparse import urlparse

def recursive_mkdir(dir, sequence):
    """Make a sequence of embeded dirs in `dir`, and return the path.

    E.g. ``recursive_mkdir('/tmp', ['a', 'b', 'c'])`` will create ``/tmp/a``,
    ``/tmp/a/b`` and ``/tmp/a/b/c``, and return the latter.

    Note that it is not an error for some of the directories to already exist.
    It is not an error either for sequence to be empty, in which case dir will
    simply be returned.
    """
    if len(sequence) > 0:
        newdir = path.join(dir, sequence[0])
        if not exists(newdir):
            mkdir(newdir)
        return recursive_mkdir(newdir, sequence[1:])
    else:
        return dir

def smart_urlopen(url):
    """Opens a URL, using builtin `open` for local files."""
    p = urlparse(url)
    if p.scheme == "file":
        return open(url2pathname(p.path))
    else:
        return urlopen(url)

def get_path(f):
    """Extract the path of file-like object `f`.

    This works for objects returned either by `open` or `urlopen`.
    """
    url = getattr(f, "url", None)
    if url is not None:
        path = urlparse(url).path
    else:
        path = getattr(f, "name", "")
    return path

def is_local(f):
    """Return True if file-like object `f` is a local file.

    This works for objects returned either by `open` or `urlopen`.
    """
    url = getattr(f, "url", None)
    if url is not None:
        return urlparse(url).scheme == "file"
    else:
        return isinstance(f, file)
 
