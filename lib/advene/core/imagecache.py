"""
Imagecache module for advene
"""

import advene.core.config as config

import os
import cStringIO

import Image

class ImageCache(dict):
    """ImageCache class.

    It interacts with the player to return annotation snapshots.
    
    @ivar not_yet_available_image: the image returned for not-yet-captured images
    @type not_yet_available_image: PNG data
    """
    def __init__ (self, name=None):
        """Initialize the Imagecache

        @param name: id of a previously saved ImageCache.
        @type name: string
        """
        # It is a dictionary whose keys are the positions
        # (in ms) and values the snapshot in PNG format.
        # value = self.not_yet_available_image if the image has
        # not yet been updated.
        dict.__init__ (self)

        # The content of the not_yet_available_file file
        i = Image.new ('RGB', (160,100), color=255)
        ostream = cStringIO.StringIO ()
        i.save (ostream, 'png')
        self.not_yet_available_image = ostream.getvalue()
        ostream.close ()

        if name is not None:
            self.load (name)

    def init_value (self, key):
        """Initialize a key if needed.

        @param key: the tested key
        @type key: long
        """
        if not dict.has_key (self, key):
            self[key] = self.not_yet_available_image
        
    def has_key (self, key):
        try:
            key = long(key)
            self.init_value (key)
            return True
        except:
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
        key = long(key)
        self.init_value (key)

        return dict.__getitem__(self, key)

    def missing_snapshots (self):
        """Return a list of positions of missing snapshots.

        @return: a list of keys
        """
        return [ pos for pos in self.keys() if dict.__getitem__(self, pos) == self.not_yet_available_image ]

    def is_initialized (self, key):
        """Return True if the given key is initialized.

        @return True if the given key is initialized.
        @rtype boolean
        """
        self.init_value (key)
        if self[key] == self.not_yet_available_image:
            return False
        else:
            return True
        
    def save (self, name):
        """Save the content of the cache under a specified name (id).

        The method creates a directory in some other directory
        (config.data.path['imagecache']) and saves the content.

        @param name: the name
        @type name: string
        """
        directory=config.data.path['imagecache']
        print "Request to save %s" % name
        if not os.path.isdir (directory):
            if os.path.exists (directory):
                # File exists, but is not a directory.
                raise "Fatal error: %s should be a directory" % directory
            else:
                os.mkdir (directory)

        d = os.sep.join ([directory, name])
        
        if not os.path.isdir (d):
            if os.path.exists (d):
                # File exists, but is not a directory.
                raise "Fatal error: %s should be a directory" % d
            else:
                os.mkdir (d)

        for k in self.keys():
            f = open(os.sep.join ([d, str(k)]), "w")
            f.write (self[k])
            f.close ()

        return

    def load (self, name):
        """Add new images to an ImageCache, from the specified imagecache id.

        @param name: the name of the origin imagecache directory.
        @type name: string
        """
        d = os.sep.join ([config.data.path['imagecache'], name])
        
        if not os.path.isdir (d):
            # The cache directory does not exist
            return
        else:
            for n in os.listdir (d):
                f = open(os.sep.join ([d, n]), "r")
                self[long(n)] = f.read ()
                f.close ()

    def ids (self):
        return self.keys ()

    def __str__ (self):
        return "ImageCache object (%d images)" % len(self)
    
    def __repr__ (self):
        return "ImageCache object (%d images)" % len(self)
