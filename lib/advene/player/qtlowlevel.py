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
# http://visionegg.org/trac/file/trunk/visionegg/VisionEgg/qtlowlevel.py
# which is LGPL

import os
import ctypes

# FIXME: use registry to locate DLL
try:
    QTMLClient = ctypes.CDLL(r'C:\Program Files\QuickTime\QTSystem\QTMLClient.dll')
except:
    QTMLClient=None
if QTMLClient is None:
    raise ImportError("Cannot find Quicktime DLL")

# OSErr SInt16 MacTypes.h
# OSStatus SInt32 MacTypes.h
# ItemCount UInt32 MacTypes.h
# FourCharCode SInt32 MacTypes.h
# OSType FourCharCode MacTypes.h
# QTNewMoviePropertyElement struct Movies.h
# QTPropertyClass OSType Movies.h
# QTPropertyID OSType Movies.h
# ByteCount UInt32 MacTypes.h
# QTPropertyValuePtr void* Movies.h
# Movie

# QT data types: cf http://developer.apple.com/documentation/QuickTime/Reference/QTRef_DataTypes/Reference/reference.html

OSErr = ctypes.c_short
OSStatus = ctypes.c_int
ItemCount = ctypes.c_uint
FourCharCode = ctypes.c_int
OSType = FourCharCode
QTPropertyClass = OSType
QTPropertyID = OSType
ByteCount = ctypes.c_uint
QTPropertyValuePtr = ctypes.c_void_p
QTVisualContextRef = ctypes.c_void_p
TimeValue = ctypes.c_long
TimeScale = ctypes.c_long
# FIXME:
PicHandle = ctypes.c_void_p

class Rect(ctypes.Structure):
    _fields_ = [("top",   ctypes.c_short),
                ("left",  ctypes.c_short),
                ("bottom",ctypes.c_short),
                ("right", ctypes.c_short)]

Movie = ctypes.c_void_p # not done
MovieController = ctypes.c_void_p

class TimeBaseRecord(ctypes.Structure):
    _fields_ = [("data", ctypes.c_long * 2)]

TimeBase = ctypes.POINTER(TimeBaseRecord)

class TimeRecord(ctypes.Structure):
    """TimeRecord structure.

    value: time value (absolute or duration)
    scale: time scale (number of units of time that pass each second.)
    base: If the time structure defines a duration, set this field to nil. Otherwise, this field must refer to a valid time base.

    doc: http://developer.apple.com/documentation/QuickTime/RM/MovieInternals/MTTimeSpace/B-Chapter/chapter_1000_section_4.html
    """
    _fields_ = [("value", ctypes.c_long),
                ("scale", TimeScale),
                ("base", TimeBase)]

class QTNewMoviePropertyElement(ctypes.Structure):
    _fields_ = [("propClass",QTPropertyClass),
                ("propID",QTPropertyID),
                ("propValueSize",ByteCount),
                ("propValueAddress",QTPropertyValuePtr),
                ("propStatus",OSStatus)]

def FOUR_CHAR_CODE(code):
    assert isinstance(code,str)
    assert len(code)==4
    val = 0
    for i in range(4):
        c = code[i]
        ordc = ord(c)
        addval = ordc << (3-i)*8
        #print '%d: %s %x %x'%(i,c,ordc,addval)
        val += addval
    #print '%x\n'%val
    return val

if True:
    kQTPropertyClass_DataLocation = FOUR_CHAR_CODE('dloc')
    kQTDataLocationPropertyID_DataReference = FOUR_CHAR_CODE('dref') # DataReferenceRecord (for semantics of NewMovieFromDataRef)
    kQTDataLocationPropertyID_CFStringNativePath = FOUR_CHAR_CODE('cfnp')
    kQTDataLocationPropertyID_CFStringPosixPath = FOUR_CHAR_CODE('cfpp')
    kQTDataLocationPropertyID_CFStringHFSPath = FOUR_CHAR_CODE('cfhp')
    kQTDataLocationPropertyID_CFStringWindowsPath = FOUR_CHAR_CODE('cfwp')
    kQTDataLocationPropertyID_CFURL = FOUR_CHAR_CODE('cfur')
    kQTDataLocationPropertyID_QTDataHandler = FOUR_CHAR_CODE('qtdh') # for semantics of NewMovieFromStorageOffset
    kQTDataLocationPropertyID_Scrap = FOUR_CHAR_CODE('scrp')
    kQTDataLocationPropertyID_LegacyMovieResourceHandle = FOUR_CHAR_CODE('rezh') # QTNewMovieUserProcInfo * (for semantics of NewMovieFromHandle)
    kQTDataLocationPropertyID_MovieUserProc = FOUR_CHAR_CODE('uspr') # for semantics of NewMovieFromUserProc
    kQTDataLocationPropertyID_ResourceFork = FOUR_CHAR_CODE('rfrk') # for semantics of NewMovieFromFile
    kQTDataLocationPropertyID_DataFork = FOUR_CHAR_CODE('dfrk') # for semantics of NewMovieFromDataFork64
    kQTPropertyClass_Context      = FOUR_CHAR_CODE('ctxt') # Media Contexts
    kQTContextPropertyID_AudioContext = FOUR_CHAR_CODE('audi')
    kQTContextPropertyID_VisualContext = FOUR_CHAR_CODE('visu')
    kQTPropertyClass_MovieResourceLocator = FOUR_CHAR_CODE('rloc')
    kQTMovieResourceLocatorPropertyID_LegacyResID = FOUR_CHAR_CODE('rezi') # (input/result property)
    kQTMovieResourceLocatorPropertyID_LegacyResName = FOUR_CHAR_CODE('rezn') # (result property)
    kQTMovieResourceLocatorPropertyID_FileOffset = FOUR_CHAR_CODE('foff') # NewMovieFromDataFork[64]
    kQTMovieResourceLocatorPropertyID_Callback = FOUR_CHAR_CODE('calb') # NewMovieFromUserProc(getProcrefcon)
                                        # Uses kQTMovieDefaultDataRefPropertyID for default dataref
    kQTPropertyClass_MovieInstantiation = FOUR_CHAR_CODE('mins')
    kQTMovieInstantiationPropertyID_DontResolveDataRefs = FOUR_CHAR_CODE('rdrn')
    kQTMovieInstantiationPropertyID_DontAskUnresolvedDataRefs = FOUR_CHAR_CODE('aurn')
    kQTMovieInstantiationPropertyID_DontAutoAlternates = FOUR_CHAR_CODE('aaln')
    kQTMovieInstantiationPropertyID_DontUpdateForeBackPointers = FOUR_CHAR_CODE('fbpn')
    kQTMovieInstantiationPropertyID_AsyncOK = FOUR_CHAR_CODE('asok')
    kQTMovieInstantiationPropertyID_IdleImportOK = FOUR_CHAR_CODE('imok')
    kQTMovieInstantiationPropertyID_DontAutoUpdateClock = FOUR_CHAR_CODE('aucl')
    kQTMovieInstantiationPropertyID_ResultDataLocationChanged = FOUR_CHAR_CODE('dlch') # (result property)
    kQTPropertyClass_NewMovieProperty = FOUR_CHAR_CODE('mprp')
    kQTNewMoviePropertyID_DefaultDataRef = FOUR_CHAR_CODE('ddrf') # DataReferenceRecord
    kQTNewMoviePropertyID_Active  = FOUR_CHAR_CODE('actv')
    kQTNewMoviePropertyID_DontInteractWithUser = FOUR_CHAR_CODE('intn')

class qtlowlevelError(RuntimeError):
    pass

noErr = 0
paramErr = -50
movieToolboxUninitialized = -2020
def GetErrorString(value):
    if value == paramErr:
        return 'paramErr'
    elif value == movieToolboxUninitialized:
        return 'movieToolboxUninitialized'
    elif value != noErr:
        return 'error value: %d'%value
    else:
        return 'noErr'

def CheckOSStatus(value):
    if value != noErr:
        raise qtlowlevelError(GetErrorString(value))
    return value

NewMovieFromFile = QTMLClient.NewMovieFromFile

NewMovieFromProperties = QTMLClient.NewMovieFromProperties
#NewMovieFromProperties.restype = OSStatus
NewMovieFromProperties.restype = CheckOSStatus
NewMovieFromProperties.argtypes = [ItemCount,
                                   ctypes.POINTER(QTNewMoviePropertyElement),
                                   ItemCount,
                                   ctypes.POINTER(QTNewMoviePropertyElement),
                                   ctypes.POINTER(Movie)]

InitializeQTML = QTMLClient.InitializeQTML
EnterMovies = QTMLClient.EnterMovies

QTGetCFConstant = QTMLClient.QTGetCFConstant

GetMovieBox = QTMLClient.GetMovieBox
GetMovieBox.argtypes = [Movie,
                        ctypes.POINTER(Rect)]
SetMovieBox = QTMLClient.SetMovieBox
SetMovieBox.argtypes = [Movie,
                        ctypes.POINTER(Rect)]

StartMovie = QTMLClient.StartMovie
StartMovie.argtypes = [Movie]

DisposeMovie = QTMLClient.DisposeMovie
DisposeMovie.argtypes = [Movie]

MoviesTask = QTMLClient.MoviesTask
MoviesTask.argtypes = [Movie,ctypes.c_long]

IsMovieDone = QTMLClient.IsMovieDone
IsMovieDone.argtypes = [Movie]

GoToBeginningOfMovie = QTMLClient.GoToBeginningOfMovie
GoToBeginningOfMovie.argtypes = [Movie]

FSSpec = ctypes.c_void_p
CFStringRef = ctypes.c_void_p
CFStringEncoding = ctypes.c_uint
CFAllocatorRef = ctypes.c_void_p
CFIndex = ctypes.c_int

GetMovieLoadState = QTMLClient.GetMovieLoadState
GetMovieLoadState.argtypes = [Movie]
GetMovieLoadState.restype = ctypes.c_long

# Cf http://developer.apple.com/documentation/QuickTime/Reference/QTRef_MovieManager/Reference/reference.html#//apple_ref/c/func/GetMovieTime

GetMovieTime = QTMLClient.GetMovieTime
GetMovieTime.argtypes = [Movie, ctypes.POINTER(TimeRecord)]
GetMovieTime.restype = TimeValue

SetMovieTime = QTMLClient.SetMovieTime
SetMovieTime.argtypes = [Movie, ctypes.POINTER(TimeRecord)]

GetMovieTimeScale = QTMLClient.GetMovieTimeScale
GetMovieTimeScale.argtypes = [Movie]
GetMovieTimeScale.restype = TimeScale

GetMovieTimeBase = QTMLClient.GetMovieTimeBase
GetMovieTimeBase.argtypes = [Movie]
GetMovieTimeBase.restype = TimeBase

SetMovieRate = QTMLClient.SetMovieRate
SetMovieRate.argtypes = [Movie, ctypes.c_int32]

GetMovieRate = QTMLClient.GetMovieRate
GetMovieRate.argtypes = [Movie]
GetMovieRate.restype = ctypes.c_int32

GetMovieDuration = QTMLClient.GetMovieDuration
GetMovieDuration.argtypes = [Movie]
GetMovieDuration.restype = TimeValue

SetMovieVolume = QTMLClient.SetMovieVolume
SetMovieVolume.argtypes = [Movie, ctypes.c_short]

GetMovieVolume = QTMLClient.GetMovieVolume
GetMovieVolume.argtypes = [Movie]
GetMovieVolume.restype = ctypes.c_short

GetMoviePict = QTMLClient.GetMoviePict
GetMoviePict.argtypes = [Movie, TimeValue]
GetMoviePict.restype = PicHandle

# Cf http://developer.apple.com/documentation/QuickTime/Reference/QTRef_MovieToolkit/Reference/reference.html#//apple_ref/c/func/NewMovieController
NewMovieController = QTMLClient.NewMovieController
NewMovieController.argtypes = [Movie, ctypes.POINTER(Rect), ctypes.c_long]
NewMovieController.restype = MovieController

# To associate a Win32 HWND to a graphics port
# http://developer.apple.com/documentation/QuickTime/RM/QTforWindows/QTforWindows/C-Chapter/chapter_1000_section_4.html
CreatePortAssociation = QTMLClient.CreatePortAssociation
CreatePortAssociation.argtypes = [ ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long ]
#        (void  *theWnd,          Ptr   storage (usually NULL),  long  flags);

SetMovieGWorld = QTMLClient.SetMovieGWorld
SetMovieGWorld.argtypes = [ Movie, ctypes.c_void_p, ctypes.c_void_p ]

SetGWorld = QTMLClient.SetGWorld
SetGWorld.argtypes = [ ctypes.c_void_p, ctypes.c_void_p ]

GetNativeWindowPort = QTMLClient.GetNativeWindowPort
GetNativeWindowPort.argtypes = [ ctypes.c_void_p ]
GetNativeWindowPort.restype = ctypes.c_void_p

if 1:
    CFStringCreateWithCharacters = QTMLClient.CFStringCreateWithCharacters
    CFStringCreateWithCharacters.restype = CFStringRef
    CFStringCreateWithCharacters.argtypes = [CFAllocatorRef,
                                             ctypes.c_wchar_p,
                                             CFIndex]

    CFStringCreateWithCString = QTMLClient.CFStringCreateWithCString
    CFStringCreateWithCString.restype = CFStringRef
    CFStringCreateWithCString.argtypes = [CFAllocatorRef,
                                          ctypes.c_char_p,
                                          CFStringEncoding]

    CFStringGetCString = QTMLClient.CFStringGetCString
    CFStringGetCStringPtr = QTMLClient.CFStringGetCStringPtr
    CFStringGetCStringPtr.restype = ctypes.c_char_p

    NativePathNameToFSSpec = QTMLClient.NativePathNameToFSSpec
    NativePathNameToFSSpec.restype = OSErr
    NativePathNameToFSSpec.argtypes = [ctypes.c_char_p,
                                       ctypes.POINTER(FSSpec),
                                       ctypes.c_long]

    OpenMovieFile = QTMLClient.OpenMovieFile

if 1:
    kCFAllocatorDefault = 0
    kCFStringEncodingMacRoman = 0 # CoreFoundation/CFString.h
