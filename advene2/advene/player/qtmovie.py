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

# This is mostly based and expanded on code downloaded from
# http://visionegg.org/trac/file/trunk/visionegg/VisionEgg/qtmovie.py
# which is LGPL

"""Higher level QuickTime Movie wrapper"""

import qtlowlevel
import ctypes

qtlowlevel.InitializeQTML(0)
qtlowlevel.EnterMovies()

class Rect:
    def __init__(self,top=0,left=0,bottom=0,right=0):
        self.top = top
        self.left = left
        self.bottom = bottom
        self.right = right

class Movie:
    """An encapsulated QuickTime Movie.

    See
    http://developer.apple.com/documentation/QuickTime/Reference/QTRef_MovieManager/Reference/reference.html
    for most functions.

    See
    http://developer.apple.com/documentation/QuickTime/RM/QTforWindows/QTforWindows/C-Chapter/chapter_1000_section_1.html
    for win32 specific programming
    """
    def __init__(self):
        self.theMovie = None
        self.aspect_ratio = 133
        self.duration=0

    def set_visual(self, hwnd):
        """Set the windows HWND attribute.
        """
        qtlowlevel.CreatePortAssociation(hwnd, 0, 0)
        self.gworld = qtlowlevel.GetNativeWindowPort(hwnd)
        if self.theMovie:
            qtlowlevel.SetMovieGWorld( self.theMovie, self.gworld, 0 )

    def open(self, filename):
        """Open a new movie from a filename.
        """
        if self.theMovie:
            self.StopMovie()
            self.DisposeMovie()

        movieProps = (qtlowlevel.QTNewMoviePropertyElement * 5)()
        filename = unicode(filename)

        movieFilePathRef = qtlowlevel.CFStringRef()
        movieFilePathRef.value = qtlowlevel.CFStringCreateWithCharacters(qtlowlevel.kCFAllocatorDefault,
                                                                         filename,
                                                                         len(filename))

        moviePropCount = 0

        movieProps[moviePropCount].propClass = qtlowlevel.kQTPropertyClass_DataLocation
        movieProps[moviePropCount].propID = qtlowlevel.kQTDataLocationPropertyID_CFStringWindowsPath
        movieProps[moviePropCount].propValueSize = ctypes.sizeof(ctypes.c_void_p)
        movieProps[moviePropCount].propValueAddress = ctypes.cast(ctypes.byref(movieFilePathRef),ctypes.c_void_p)
        movieProps[moviePropCount].propStatus = 0

        moviePropCount += 1

        boolTrue = ctypes.c_ubyte(1)
        movieProps[moviePropCount].propClass = qtlowlevel.kQTPropertyClass_MovieInstantiation
        movieProps[moviePropCount].propID = qtlowlevel.kQTMovieInstantiationPropertyID_DontAskUnresolvedDataRefs
        movieProps[moviePropCount].propValueSize = ctypes.sizeof(boolTrue)
        movieProps[moviePropCount].propValueAddress = ctypes.cast(ctypes.pointer(boolTrue),ctypes.c_void_p)
        movieProps[moviePropCount].propStatus = 0

        moviePropCount += 1

        movieProps[moviePropCount].propClass = qtlowlevel.kQTPropertyClass_NewMovieProperty
        movieProps[moviePropCount].propID = qtlowlevel.kQTNewMoviePropertyID_Active
        movieProps[moviePropCount].propValueSize = ctypes.sizeof(boolTrue)
        movieProps[moviePropCount].propValueAddress = ctypes.cast(ctypes.pointer(boolTrue),ctypes.c_void_p)
        movieProps[moviePropCount].propStatus = 0

        moviePropCount += 1

        movieProps[moviePropCount].propClass = qtlowlevel.kQTPropertyClass_NewMovieProperty
        movieProps[moviePropCount].propID = qtlowlevel.kQTNewMoviePropertyID_DontInteractWithUser
        movieProps[moviePropCount].propValueSize = ctypes.sizeof(boolTrue)
        movieProps[moviePropCount].propValueAddress = ctypes.cast(ctypes.pointer(boolTrue),ctypes.c_void_p)
        movieProps[moviePropCount].propStatus = 0

        moviePropCount += 1

        self.theMovie = qtlowlevel.Movie()
        qtlowlevel.NewMovieFromProperties( moviePropCount, movieProps, 0, None, ctypes.byref(self.theMovie))

        self.duration=self.GetMovieDuration()
        rect=self.GetMovieBox()
        width=rect.right-rect.left
        height=rect.bottom-rect.top
        self.aspect_ratio=100*width/height
        return True

    def GetMovieBox(self):
        """Return the movie box
        """
        movieBounds = qtlowlevel.Rect()
        qtlowlevel.GetMovieBox(self.theMovie, ctypes.byref(movieBounds))
        return Rect(top=movieBounds.top,
                    left=movieBounds.left,
                    bottom=movieBounds.bottom,
                    right=movieBounds.right)

    def SetMovieBox(self,bounds):
        """Set the movie box (Rect structure).
        """
        if not isinstance(bounds,Rect):
            raise ValueError('bounds argument must be instance of VisionEgg.qtmovie.Rect')
        b = qtlowlevel.Rect()
        (b.top, b.left, b.bottom, b.right) = (bounds.top, bounds.left,
                                              bounds.bottom, bounds.right)
        qtlowlevel.SetMovieBox(self.theMovie, ctypes.byref(b))

    def StartMovie(self):
        qtlowlevel.StartMovie(self.theMovie)

    def MoviesTask(self,value):
        """Process the movie.

        value is a delay, generally 0. It indicates the maximum time
        allowed for movie processing.
        """
        qtlowlevel.MoviesTask(self.theMovie, value)

    def DisposeMovie(self):
        qtlowlevel.DisposeMovie(self.theMovie)

    def IsMovieDone(self):
        return qtlowlevel.IsMovieDone(self.theMovie)

    def GoToBeginningOfMovie(self):
        qtlowlevel.GoToBeginningOfMovie(self.theMovie)

    def SetMovieRate(self, r):
        qtlowlevel.SetMovieRate(self.theMovie, r)

    def GetMovieRate(self):
        return qtlowlevel.GetMovieRate(self.theMovie)

    def SetMovieVolume(self, r):
        qtlowlevel.SetMovieVolume(self.theMovie, r)

    def GetMovieVolume(self):
        return qtlowlevel.GetMovieVolume(self.theMovie)

    def GetMovieTime(self):
        rec=qtlowlevel.TimeRecord()
        qtlowlevel.GetMovieTime(self.theMovie, rec)
        return rec

    def GetMovieDuration(self):
        return qtlowlevel.GetMovieDuration(self.theMovie)

    def SetMovieTime(self, t):
        """Set the movie time (in ms).
        """
        if False:
            # Building TimeRecord from scratch
            rec=qtlowlevel.TimeRecord()
            rec.scale=qtlowlevel.GetMovieTimeScale(self.theMovie)
            rec.base=qtlowlevel.GetMovieTimeBase(self.theMovie)
            rec.value=t * rec.scale / 1000
        else:
            # Using current TimeRecord
            rec=self.GetMovieTime()
            rec.value=t * rec.scale / 1000
        qtlowlevel.SetMovieTime(self.theMovie, rec)
