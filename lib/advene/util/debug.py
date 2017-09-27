#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008-2017 Olivier Aubert <contact@olivieraubert.net>
#
# Advene is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Advene is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Advene; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Debug functions/utilities."""
import logging
logger = logging.getLogger(__name__)

from collections import Mapping, Container
import datetime
try:
    import objgraph
except ImportError:
    objgraph = None
import resource
from sys import getsizeof

# We should use the logging API, but some packages (like objgraph)
# take an open file as parameter, so let's accomodate this
DEBUGFILENAME = '/tmp/advene-debug-%s.log' % datetime.datetime.now().isoformat()[:19]
logger.warn("Logging additional debug information to %s" % DEBUGFILENAME)
DEBUGFILE = open(DEBUGFILENAME, 'w')

def debug_log(*args):
    """Log information to a specific logfile.
    """
    DEBUGFILE.write("%s - %s\n" % (datetime.datetime.now().isoformat(),
                                 " ".join(str(a) for a in args)))

def deep_getsizeof(o, ids=None):
    """Find the memory footprint of a Python object

    Source: https://code.tutsplus.com/tutorials/understand-how-much-memory-your-python-objects-use--cms-25609

    This is a recursive function that drills down a Python object graph
    like a dictionary holding nested dictionaries with lists of lists
    and tuples and sets.

    The sys.getsizeof function does a shallow size of only. It counts each
    object inside a container as pointer only regardless of how big it
    really is.

    :param o: the object
    :param ids:
    :return:
    """
    if ids is None:
        ids = set()
    d = deep_getsizeof
    if id(o) in ids:
        return 0

    r = getsizeof(o)
    ids.add(id(o))

    if isinstance(o, str) or isinstance(o, bytes):
        return r

    if isinstance(o, Mapping):
        return r + sum(d(k, ids) + d(v, ids) for k, v in o.items())

    if isinstance(o, Container):
        return r + sum(d(x, ids) for x in o)

    return r

last_mem = None
def log_global_memory_usage():
    global last_mem
    mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if mem != last_mem:
        debug_log("Memory usage: %s" % mem)
        logger.warn("Memory usage: %s" % mem)
        last_mem = mem

last_imagecache_size = None
def log_imagecache_size(controller):
    global last_imagecache_size
    size = deep_getsizeof(controller.package.imagecache)
    if size != last_imagecache_size:
        debug_log("Imagecache usage: %s" % size)
        last_imagecache_size = size

def debug_slow_update_hook(controller):
    """Debug method.

    This method will be regularly called (from the
    slow_update_display) when -d (debug) option is given.
    """
    log_global_memory_usage()
    log_imagecache_size(controller)
    if objgraph is not None:
        debug_log("------------ Object growth ---------------")
        objgraph.show_growth(shortnames=False, limit=30, file=DEBUGFILE)
