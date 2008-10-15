#
# Advene: Annotate Digital Videos, Exchange on the NEt
# Copyright (C) 2008 Olivier Aubert <olivier.aubert@liris.cnrs.fr>
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

import advene.core.config as config
import operator

import os

class CachedString:
    """String cached in a file.
    """
    def __init__(self, filename):
        self._filename=filename
        self.contenttype='text/plain'

    def __str__(self):
        try:
            return open(self._filename).read()
        except (IOError, OSError):
            return ''

    def __repr__(self):
        return "Cached content from " + self._filename

class TypedString(str):
    """String with a mimetype attribute.
    """
    def __init__(self, *p, **kw):
        super(TypedString, self).__init__(*p, **kw)
        self.contenttype='text/plain'

class ImageCache(dict):
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
    not_yet_available_image = TypedString(open(config.data.advenefile( ( 'pixmaps', 
                                                                         'notavailable.png' ) ), 'rb').read())
    not_yet_available_image.contenttype='image/png'

    def __init__ (self, name=None, epsilon=20):
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
        dict.__init__ (self)


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
        if not dict.has_key (self, key):
            dict.__setitem__(self, key, self.not_yet_available_image)

    def has_key (self, key):
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
        return dict.__getitem__(self, key)

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
        return dict.__getitem__(self, key)

    def __setitem__ (self, key, value):
        """Set the snapshot for the image corresponding to the position key.

        @param key: the key
        @type key: long
        @param value: an image
        @type value: PNG data
        """
        if key is None:
            return value
        key = self.approximate(key)
        if value != self.not_yet_available_image:
            self._modified=True
            if self.autosync and self.name is not None:
                d=os.path.join(config.data.path['imagecache'], self.name)
                if not os.path.isdir(d):
                    os.mkdir (d)
                filename=os.path.join(d, "%010d.png" % key)
                f = open(filename, 'wb')
                f.write (value)
                f.close ()
                value=CachedString(filename)
                value.contenttype='image/png'
        return dict.__setitem__(self, key, value)

    def approximate (self, key, epsilon=None):
        """Return an approximate key value for key.

        If there is an existing key no further than self.epsilon, then return it.
        Else, initialize data for key and return key.
        """
        if key is None:
            return None
        key=long(key)
        if dict.has_key(self, key):
            return key

        if epsilon is None:
            epsilon=self.epsilon
        valids = [ (pos, abs(pos-key))
                   for pos in self.keys()
                   if abs(pos - key) <= epsilon ]
        valids.sort(key=operator.itemgetter(1))

        if valids:
            key = valids[0][0]
#            print "Approximate key: %d (%d)" % valids[0]
##             if len(valids) > 1:
##                 print "Imagecache: more than 1 valid snapshot for %d: %s" % (key,
##                                                                              valids)
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
        if dict.__getitem__(self, key) != self.not_yet_available_image:
            dict.__setitem__(self, key, self.not_yet_available_image)
        return

    def missing_snapshots (self):
        """Return a list of positions of missing snapshots.

        @return: a list of keys
        """
        return [ pos
                 for pos in self.keys()
                 if dict.__getitem__(self, pos) == self.not_yet_available_image ]

    def valid_snapshots (self):
        """Return the list of positions of valid snapshots.

        @return: a list of keys
        """
        return [ pos
                 for pos in self.keys()
                 if dict.__getitem__(self, pos) != self.not_yet_available_image ]

    def is_initialized (self, key, epsilon=None):
        """Return True if the given key is initialized.

        @return: True if the given key is initialized.
        @rtype: boolean
        """
        if key is None:
            return False
        key = self.approximate(key, epsilon)
        if dict.__getitem__(self, key) == self.not_yet_available_image:
            return False
        else:
            return True

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

        for k in self.iterkeys():
            i=dict.__getitem__(self, k)
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
                        i=long(n)
                    except ValueError:
                        print "Invalid filename in imagecache: " + name
                        continue
                    s=CachedString(os.path.join (d, name))
                    s.contenttype='image/png'
                    dict.__setitem__(self, i, s)
        self._modified=False

    def ids (self):
        """Return the list of currents ids.
        """
        return [ str(k) for k in self.keys () ]

    def __str__ (self):
        return "ImageCache object (%d images)" % len(self)

    def __repr__ (self):
        return "ImageCache object (%d images)" % len(self)
