"""VLC library functions."""

import advene.core.config as config
import os
import sys
import time
import Image

from gettext import gettext as _

import StringIO

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
