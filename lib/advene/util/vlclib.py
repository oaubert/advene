#! /usr/bin/python
"""VLC library functions."""

import advene.core.config as config
import os
import sys
import time
import Image

import spawn

from gettext import gettext as _

import gtk

import StringIO

import ORBit, CORBA

def fourcc2rawcode (code):
    """VideoLan to PIL code conversion.
    
    Converts the FOURCC used by VideoLan into the corresponding
    rawcode specification used by the python Image module.

    @param code: the FOURCC code from VideoLan
    @type code: string
    @return: the corresponding PIL code
    @rtype: string
    """
    conv = { 'RV32' : 'BGRX' }
    fourcc = "%c%c%c%c" % (code & 0xff,
                           code >> 8 & 0xff,
                           code >> 16 & 0xff,
                           code >> 24)
    return conv[fourcc]

def image_to_pixbuf (image):
    file = StringIO.StringIO ()
    image.save (file, 'ppm')
    contents = file.getvalue()
    file.close ()
    loader = gtk.gdk.PixbufLoader ('pnm')
    loader.write (contents, len (contents))
    pixbuf = loader.get_pixbuf ()
    loader.close ()
    return pixbuf


def png_to_pixbuf (png_data):
    loader = gtk.gdk.PixbufLoader ('png')
    loader.write (png_data, len (png_data))
    pixbuf = loader.get_pixbuf ()
    loader.close ()
    return pixbuf

def snapshot2png (image, output=None):
    """Convert a VLC RGBPicture to PNG.
    
    output is either a filename or a stream. If not given, the image
    will be returned as a buffer.

    @param image: a VLC.RGBPicture
    @param output: the output stream or filename (optional)
    @type output: filename or stream
    @return: an image buffer (optional)
    @rtype: string
    """
    if image.height == 0:
        print "Error : %s" % a.data
        return ""
    i = Image.fromstring ("RGB", (image.width, image.height), image.data,
                          "raw", fourcc2rawcode(image.type))
    if output is not None:
        i.save (output, 'png')
        return ""
    else:
        ostream = StringIO.StringIO ()
        i.save(ostream, 'png')
        return ostream.getvalue()

def mediafile2id (mediafile):
    """Returns an id (with encoded /) corresponding to the mediafile.

    @param mediafile: the name of the mediafile
    @type mediafile: string
    @return: an id
    @rtype: string
    """
    return mediafile.replace ('/', '%2F')

def package2id (p):
    """Return the id of the package's mediafile.

    Return the id (with encoded /) corresponding to the mediafile
    defined in the package. Returns "undefined" if no mediafile is
    defined.

    @param p: the package
    @type p: advene.Package

    @return: the corresponding id
    @rtype: string
    """
    mediafile = p.getMetaData (config.data.namespace, "mediafile")
    if mediafile is not None and mediafile != "":
        return mediafile2id (mediafile)
    else:
        return "undefined"

def format_time (val=0):
    """Formats a value (in milliseconds) into a time string.

    @param val: the value
    @type val: int
    @return: the formatted string
    @rtype: string
    """ 
    t = long(val)
    # Format: HH:MM:SS.mmm
    return "%s.%03d" % (time.strftime("%H:%M:%S", time.gmtime(t / 1000)),
                       t % 1000)
       

class VLCPlayer:
    # FIXME: this class should move to some place more appropriate
    """MediaController class used by mediacontrol.Player.

    @ivar orb: the CORBA ORB
    @ivar mc: the VLC.MediaControl object
    @ivar launcher: the launcher object
    @type launcher: spawn.ProcessLauncher
    @ivar ior: the MediaControl's IOR
    @type ior: string
    """
    def __init__ (self, config=None):
        """Initialize the player."""
        if config is None:
            raise Exception ("VLCPlayer needs a Config object")
        self.config=config
        if config.os == 'win32':
            self.launcher=None
        else:
            self.launcher = spawn.ProcessLauncher (name=config.player['name'],
                                                   args=config.player_args,
                                                   path=config.path['vlc'])
        self.orb=None
        self.mc=None
        self.ior=None

    def is_active (self):
        """Check if a VLC player is active.

        @return: True if the player if active."""
        if self.mc is None:
            return False
        
        if self.launcher and not self.launcher.is_running():
            return False

        try:
            if self.mc._non_existent ():
                return False
        except:
            pass
        
        # The process is active, but the CORBA plugin may not be
        # active.
        if os.access (self.config.iorfile, os.R_OK):
            return True
        return False

    def _start (self):
        """Run the VLC player and wait for the iorfile creation.

        @raise Exception: exception raised if the IOR file cannot be read
                          after config.data.orb_max_tries tries
        @return: the IOR of the VLC player
        @rtype: string
        """
        if not self.launcher:
            return "Dummy IOR (for the moment)"
        if not self.launcher.start (self.config.player_args):
            raise Exception(_("Cannot start the player"))
        ior=""
        iorfile=self.config.iorfile
        tries=0
        while tries < self.config.orb_max_tries:
            try:
                #print "Try %d" % tries
                ior = open(iorfile).readline()
                break
            except: 
                tries=tries+1
                time.sleep(1)
        if ior == "":
            raise Exception (_("Cannot read the IOR file %s") % iorfile)
        return ior

    def init (self):
        """Initialize the ORB and the VLC.MediaControl.
        
        Return a tuple (orb, mc) once the player is initialized. We
        try multiple times to access the iorfile before quitting.
        
        @raise Exception: exception raised if we could not get a valid
                          VLC.MediaControl
        @return: (orb, mc)
        @rtype: tuple
        """

        iorfile=self.config.iorfile
        
        if self.orb is None:
            self.orb = CORBA.ORB_init()

        # First try: the player may already be active
        ior=""
        try:
            ior = open(iorfile).readline()
        except:
            pass

        if ior == "":
            # No IOR file was present. We try to launch the player
            ior = self._start ()

        mc = self.orb.string_to_object(ior)

        if mc._non_existent ():
            # The remote object is not available.
            # We remove the obsolete iorfile and try again
            try:
                os.unlink (iorfile)
            except:
                pass
            ior=self._start ()
            
            mc = self.orb.string_to_object(ior)
            if mc._non_existent ():
                raise Exception (_("Unable to get a MediaControl object."))

        self.mc=mc
        self.ior=ior
        return (self.orb, self.mc)

    def stop(self):
        """Cleanly stop the player."""
        if self.mc is not None:
            try:
                self.mc.exit ()
            except:
                pass
        self.mc=None
        self.ior=None

    def restart (self):
        """Cleanly restart the player."""
        self.stop ()
        time.sleep (1)
        return self.init ()
