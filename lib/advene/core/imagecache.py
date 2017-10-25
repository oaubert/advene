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
"""
Imagecache module for advene
"""
import logging
logger = logging.getLogger(__name__)

import advene.core.config as config
import operator

from collections import defaultdict
import math
import os
import re

class CachedString:
    """String cached in a file.
    """
    def __init__(self, filename):
        self._filename = filename
        self.contenttype = 'text/plain'
        self.is_default = False
        ts = re.findall('(\d+).png$', filename)
        if ts:
            self.timestamp = int(ts[0])
        else:
            self.timestamp = -1

    def size(self):
        return os.path.getsize(self._filename)

    def __bytes__(self):
        try:
            with open(self._filename, 'rb') as f:
                return f.read()
        except (IOError, OSError):
            return b''

    def __repr__(self):
        return "Cached content from " + self._filename

class TypedString(bytes):
    """String with a mimetype and a timestamp attribute.
    """
    def __new__(cls, value=b""):
        s = bytes.__new__(cls, value)
        s.contenttype = 'text/plain'
        s.timestamp = -1
        s.is_default = False
        return s

    def size(self):
        return len(self)

    def __bytes__(self):
        return self

class ImageCache(object):
    """ImageCache class.

    It interacts with the player to return annotation snapshots. It approximates
    key values to a given precision (20ms by default).

    @ivar not_yet_available_image: the image returned for not-yet-captured images
    @type not_yet_available_image: PNG data
    @ivar precision: the precision for key values
    @type precision: integer
    @ivar _modified: the modified status of the cache
    @type _modified: boolean
    @ivar name: id of the ImageCache (used when saving)
    @type name: string
    @ivar autosync: if True, directly store snapshots on disk
    @type autosync: boolean
    """
    # The content of the not_yet_available_file file. We could use
    # CachedString but as it is frequently used, let us keep it in memory.
    with open(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ), 'rb') as f:
        not_yet_available_image = TypedString(f.read(10000))
    not_yet_available_image.contenttype = 'image/png'
    not_yet_available_image.timestamp = -1
    not_yet_available_image.is_default = True

    def __init__ (self, uri=None, name=None, precision=20, framerate=None):
        """Initialize the Imagecache

        @param uri: URI of the media file
        @type uri: string
        @param name: id of a previously saved ImageCache.
        @type name: string
        @param precision: value of the precision
        @type precision: integer
        """
        # It is a dictionary whose keys are the positions
        # (in ms) and values the snapshot in PNG format. We store only
        # value = self.not_yet_available_image if the image has
        # not yet been updated.
        self.uri = uri

        self._dict = defaultdict(lambda: self.not_yet_available_image)

        self._modified=False

        self.name=None

        if framerate is None:
            framerate = 1 / config.data.prefix['default-fps']
            logger.warn("No framerate given. Using default value %.02f", framerate)
        self.framerate = framerate

        # If autosync, then data will automatically be stored on disk
        # (provided that self.name is properly initialized)
        self.autosync=False

        self.precision = precision
        if name is not None:
            self.load (name)

    def round_timestamp(self, t_in_ms):
        """Round the given timestamp to the appropriate value based on framerate.

        We assume a constant frame rate encoding. So
        math.ceil(t/1000/framerate) returns the frame number (starting
        at 1). We multiply it by framerate again to get the time of
        the end of the frame. We substract .1 framerate to ask the
        player to get just before the end of the frame.

        Since we deal with ms, return an integer.
        """
        if t_in_ms == 0:
            return int(500 * self.framerate)
        else:
            return int(1000 * self.framerate * max(0, math.ceil(t_in_ms / 1000 / self.framerate) - 0.5))

    def approximate (self, key, precision=None):
        """Return an approximate key value for key.

        If there is an existing key no further than precision, then return it.
        Else, initialize data for key and return key.
        """
        if key is None:
            return None
        key = self.round_timestamp(key)
        if key in self._dict or precision == 0:
            return key

        if precision is None:
            precision = self.precision
        best = min( ((pos, abs(pos - key))
                     for pos in self._dict.keys()
                     if abs(pos - key) <= precision),
                    key=operator.itemgetter(1),
                    default=(key, 0) )
        #logger.debug("approximate %d (%d) -> %d", key, precision or 0, best[0])
        return best[0]

    def clear(self):
        self._dict.clear()

    def __contains__(self, key):
        return self.round_timestamp(key) in self._dict

    def __getitem__ (self, key):
        """Return a snapshot for the image corresponding to the position pos.

        The snapshot can be ImageCache.not_yet_available_image.

        @param key: the key
        @type key: long
        @return: an image
        @rtype: PNG data
        """
        if key is None or key < 0:
            return self.not_yet_available_image
        return self._dict.get(self.round_timestamp(key), self.not_yet_available_image)

    def __delitem__(self, key):
        self._dict.__delitem__(key)

    def __iter__(self):
        return self._dict.__iter__()

    def __len__(self):
        return self._dict.__len__()

    def get(self, key, precision=None):
        """Return a snapshot for the image corresponding to the position pos with a given precision.

        The snapshot can be ImageCache.not_yet_available_image.

        @param key: the key
        @type key: long
        @return: an image
        @rtype: PNG data
        """
        if key is None or key < 0:
            return self.not_yet_available_image
        if precision:
            key = self.approximate(key, precision)
        else:
            key = self.round_timestamp(key)
        logger.debug("Getting key %d", key)
        return self._dict.get(key, self.not_yet_available_image)

    def __setitem__ (self, key, value):
        """Set the snapshot for the image corresponding to the position key.

        @param key: the key
        @type key: long
        @param value: an image
        @type value: PNG data
        """
        if key is None:
            return value
        key = self.round_timestamp(key)
        if value != self.not_yet_available_image:
            if self.autosync and self.name is not None:
                d = os.path.join(config.data.path['imagecache'], self.name)
                if not os.path.isdir(d):
                    os.mkdir (d)
                filename = os.path.join(d, "%010d.png" % key)
                with open(filename, 'wb') as f:
                    f.write (value)
                value = CachedString(filename)
                value.contenttype = 'image/png'
            elif isinstance(value, (str, bytes)):
                self._modified = True
                value = TypedString(value)
                value.timestamp = key
                value.contenttype = 'image/png'
            self._dict[key] = value
            return value
        else:
            return self.not_yet_available_image

    def invalidate(self, key, precision=None):
        """Invalidate the given key.

        This method is used when the player has some trouble getting
        an accurate screenshot.
        """
        if key is None:
            return
        key = self.round_timestamp(key)
        del self._dict[key]
        return key

    def valid_snapshots (self):
        """Return the list of positions of valid snapshots.

        @return: a list of keys
        """
        return list(self._dict.keys())

    def save (self, name):
        """Save the content of the cache under a specified name (id).

        The method creates a directory in some other directory
        (config.data.path['imagecache']) and saves the content.

        @param name: the name
        @type name: string
        @return: the created directory
        @rtype: string
        """
        directory=config.data.path['imagecache']
        if not os.path.isdir (directory):
            if os.path.exists (directory):
                # File exists, but is not a directory.
                raise Exception("Fatal error: %s should be a directory" % directory)
            else:
                os.mkdir (directory)

        d = os.path.join (directory, name)

        if not os.path.isdir (d):
            if os.path.exists (d):
                # File exists, but is not a directory.
                raise Exception("Fatal error: %s should be a directory" % d)
            else:
                os.mkdir (d)

        for k, i in self._dict.items():
            if i == self.not_yet_available_image:
                continue
            if isinstance(i, CachedString):
                continue
            f = open(os.path.join (d, "%010d.png" % k), 'wb')
            f.write (i)
            f.close ()

        self._modified=False
        return d

    def load (self, name):
        """Add new images to an ImageCache, from the specified imagecache id.

        @param name: the name of the origin imagecache directory.
        @type name: string
        """
        d = os.path.join (config.data.path['imagecache'], name)

        if not os.path.isdir (d):
            # The cache directory does not exist
            return
        else:
            self.name=name
            for name in os.listdir (d):
                (n, ext) = os.path.splitext(name)
                # We must do some checks, in case there are non-well
                # formatted filenames in the directory
                if ext.lower() == '.png':
                    try:
                        n=n.lstrip('0')
                        if n == '':
                            n=0
                        i=int(n)
                    except ValueError:
                        logger.error("Invalid filename in imagecache: %s", name)
                        continue
                    s=CachedString(os.path.join (d, name))
                    s.contenttype='image/png'
                    self._dict[i] = s
        self._modified=False

    def stats(self):
        memory_size = 0
        memory_count = 0
        disk_size = 0
        disk_count = 0
        for s in self._dict.values():
            if isinstance(s, TypedString):
                memory_count += 1
                memory_size += s.size()
            elif isinstance(s, CachedString):
                disk_count += 1
                disk_size += s.size()

        stats = {
            'name': self.name or "",
            'count': len(self._dict),
            'memory_count': memory_count,
            'memory_size': memory_size,
            'memory_size_mb': memory_size / 1024 / 1024,
            'disk_count': disk_count,
            'disk_size': disk_size,
            'disk_size_mb': disk_size / 1024 / 1024,
        }
        return stats

    def stats_repr(self):
        return "%(count)d values. Memory: %(memory_count)d (%(memory_size_mb).02f MB) - Disk [%(name)s]: %(disk_count)d (%(disk_size_mb).02f MB)" % self.stats()

    def reset(self):
        """Reset imagecache.
        """
        for pos in self._dict:
            self._dict[pos] = self.not_yet_available_image

    def ids(self):
        """Return the list of currents ids.
        """
        return [ str(k) for k in self._dict ]

    def __str__(self):
        return "ImageCache object (%d images)" % len(self._dict)

    def __repr__(self):
        return "ImageCache object (%d images)" % len(self._dict)
