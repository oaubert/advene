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
import os
import re

class CachedString:
    """String cached in a file.
    """
    def __init__(self, filename):
        self._filename=filename
        self.contenttype='text/plain'
        ts=re.findall('(\d+).png$', filename)
        if ts:
            self.timestamp=int(ts[0])
        else:
            self.timestamp=-1

    def __bytes__(self):
        try:
            with open(self._filename, 'rb') as f:
                data=f.read()
            return data
        except (IOError, OSError):
            return b''

    def __repr__(self):
        return "Cached content from " + self._filename

class TypedString(bytes):
    """String with a mimetype and a timestamp attribute.
    """
    def __new__(cls, value=b""):
        s=bytes.__new__(cls, value)
        s.contenttype='text/plain'
        s.timestamp=-1
        return s

    def __bytes__(self):
        return self

class ImageCache(object):
    """ImageCache class.

    It interacts with the player to return annotation snapshots. It approximates
    key values to a given precision (20 by default).

    @ivar not_yet_available_image: the image returned for not-yet-captured images
    @type not_yet_available_image: PNG data
    @ivar epsilon: the precision for key values
    @type epsilon: integer
    @ivar _modified: the modified status of the cache
    @type _modified: boolean
    @ivar name: id of the ImageCache (used when saving)
    @type name: string
    @ivar autosync: if True, directly store snapshots on disk
    @type autosync: boolean
    """
    # The content of the not_yet_available_file file. We could use
    # CachedString but as it is frequently used, let us keep it in memory.
    f=open(config.data.advenefile( ( 'pixmaps', 'notavailable.png' ) ), 'rb')
    not_yet_available_image = TypedString(f.read(10000))
    f.close()
    not_yet_available_image.contenttype='image/png'
    not_yet_available_image.timestamp=-1

    def __init__ (self, name=None, epsilon=35):
        """Initialize the Imagecache

        @param name: id of a previously saved ImageCache.
        @type name: string
        @param epsilon: value of the precision
        @type epsilon: integer
        """
        # It is a dictionary whose keys are the positions
        # (in ms) and values the snapshot in PNG format.
        # value = self.not_yet_available_image if the image has
        # not yet been updated.
        self._dict = defaultdict(lambda: self.not_yet_available_image)

        self._modified=False

        self.name=None
        # If autosync, then data will automatically be stored on disk
        # (provided that self.name is properly initialized)
        self.autosync=False

        self.epsilon = epsilon
        if name is not None:
            self.load (name)

    def init_value (self, key):
        """Initialize a key if needed.

        @param key: the tested key
        @type key: long
        """
        if key is None:
            return
        if key not in self._dict:
            # Accessing it will initialize its value
            self._dict[key]

    def clear(self):
        self._dict.clear()

    def __contains__(self, key):
        if key is None:
            return True
        try:
            self.approximate(key)
            return True
        except ValueError:
            return False
        return False

    def __getitem__ (self, key):
        """Return a snapshot for the image corresponding to the position pos.

        The snapshot can be ImageCache.not_yet_available_image.

        @param key: the key
        @type key: long
        @return: an image
        @rtype: PNG data
        """
        if key is None:
            return self.not_yet_available_image
        key = self.approximate(key)
        return self._dict[key]


    def __delitem__(self, key):
        self._dict.__delitem(key)

    def __iter__(self):
        return self._dict.__iter__()

    def __len__(self):
        return self._dict.__len__()

    def get(self, key, epsilon=None):
        """Return a snapshot for the image corresponding to the position pos.

        The snapshot can be ImageCache.not_yet_available_image.

        @param key: the key
        @type key: long
        @return: an image
        @rtype: PNG data
        """
        if key is None:
            return self.not_yet_available_image
        key = self.approximate(key, epsilon)
        return self._dict[key]

    def __setitem__ (self, key, value):
        """Set the snapshot for the image corresponding to the position key.

        @param key: the key
        @type key: long
        @param value: an image
        @type value: PNG data
        """
        if key is None:
            return value
        if value != self.not_yet_available_image:
            if self.autosync and self.name is not None:
                d=os.path.join(config.data.path['imagecache'], self.name)
                if not os.path.isdir(d):
                    os.mkdir (d)
                filename=os.path.join(d, "%010d.png" % key)
                with open(filename, 'wb') as f:
                    f.write (value)
                value=CachedString(filename)
                value.contenttype='image/png'
            elif isinstance(value, (str, bytes)):
                self._modified=True
                value=TypedString(value)
                value.timestamp=key
                value.contenttype='image/png'
            self._dict[key] = value
            return value
        else:
            return self.not_yet_available_image

    def approximate (self, key, epsilon=None):
        """Return an approximate key value for key.

        If there is an existing key no further than self.epsilon, then return it.
        Else, initialize data for key and return key.
        """
        if key is None:
            return None
        key=int(key)
        if self._dict.get(key, self.not_yet_available_image) != self.not_yet_available_image:
            return key

        if epsilon is None:
            epsilon=self.epsilon
        valids = [ (pos, abs(pos-key))
                   for pos in self._dict
                   if abs(pos - key) <= epsilon
                   and self._dict.get(pos, self.not_yet_available_image) != self.not_yet_available_image ]
        valids.sort(key=operator.itemgetter(1))

        if valids:
            key = valids[0][0]
        else:
            self.init_value (key)

        return key

    def invalidate(self, key, epsilon=None):
        """Invalidate the given key.

        This method is used when the player has some trouble getting
        an accurate screenshot.
        """
        if key is None:
            return
        if epsilon is None:
            epsilon=self.epsilon
        key = self.approximate(key, epsilon)
        self._dict[key] = self.not_yet_available_image
        return key

    def missing_snapshots (self):
        """Return a list of positions of missing snapshots.

        @return: a list of keys
        """
        return [ pos
                 for pos in self._dict
                 if self._dict.get(pos) == self.not_yet_available_image ]

    def valid_snapshots (self):
        """Return the list of positions of valid snapshots.

        @return: a list of keys
        """
        return [ pos
                 for pos in self._dict
                 if self._dict.get(pos) != self.not_yet_available_image ]

    def is_initialized (self, key, epsilon=None):
        """Return True if the given key is initialized.

        @return: True if the given key is initialized.
        @rtype: boolean
        """
        if key is None:
            return False
        key = self.approximate(key, epsilon)
        return self._dict[key] != self.not_yet_available_image

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

    def reset(self):
        """Reset imagecache.
        """
        for pos in self._dict:
            self._dict[pos] = self.not_yet_available_image

    def ids (self):
        """Return the list of currents ids.
        """
        return [ str(k) for k in self._dict ]

    def __str__ (self):
        return "ImageCache object (%d images)" % len(self._dict)

    def __repr__ (self):
        return "ImageCache object (%d images)" % len(self._dict)
