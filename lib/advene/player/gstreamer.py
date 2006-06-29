#
# This file is part of Advene.
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
# along with Foobar; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
"""Gstreamer player interface.

Based on gst >= 0.10 API
"""

import pygst
pygst.require('0.10')
import gst
import gst.interfaces
import os

class StreamInformation:
    def __init__(self):
        self.streamstatus=None
        self.url=""
        self.position=0
        self.length=0

class Position:
    def __init__(self, value=0):
	self.value=value
	# See Player attributes below...
	self.origin=0
	self.key=2

class PositionKeyNotSupported(Exception):
    pass

class PositionOrigin(Exception):
    pass

class InvalidPosition(Exception):
    pass

class PlaylistException(Exception):
    pass

class InternalException(Exception):
    pass

class Player:
    # Class attributes
    AbsolutePosition=0
    RelativePosition=1
    ModuloPosition=2

    ByteCount=0
    SampleCount=1
    MediaTime=2

    # Status
    PlayingStatus=0
    PauseStatus=1
    ForwardStatus=2
    BackwardStatus=3
    InitStatus=4
    EndStatus=5
    UndefinedStatus=6

    PositionKeyNotSupported=Exception()
    PositionOriginNotSupported=Exception()
    InvalidPosition=Exception()
    PlaylistException=Exception()
    InternalException=Exception()

#    statusmapping = {
#	#gst.STATE_ASYNC: UndefinedStatus,
#	gst.STATE_PAUSED: PauseStatus,
#        #gst.STATE_SUCCESS: UndefinedStatus,
#	#gst.STATE_FAILURE: UndefinedStatus,
#	gst.STATE_PLAYING: PlayingStatus,
#	gst.STATE_VOID_PENDING: UndefinedStatus,
#	gst.STATE_NULL: UndefinedStatus,
#	gst.STATE_READY: UndefinedStatus,
#	}

    def __init__(self):
        self.player = gst.element_factory_make("playbin", "player")
        self.imagesink = gst.element_factory_make('xvimagesink')
        self.player.set_property('video-sink', self.imagesink)

        self.videofile=None
        self.status=Player.UndefinedStatus
        self.relative_position=self.create_position(0, 
						    origin=self.RelativePosition)
        self.position_update()

    def position2value(self, p):
	"""Returns a position in ms.
	"""
	if isinstance(p, Position):
	    v=p.value
	    if p.key != self.MediaTime:
		print "gstreamer: unsupported key ", p.key
		return 0
	    if p.origin == self.AbsolutePosition:
		v=p.value
	    else:
		v=self.current_position() + p.value
	else:
	    v=long(p)
	return v

    def current_status(self):
	st=self.player.get_state()
	#rint repr(st)
	if gst.STATE_PLAYING in st:
	    return self.PlayingStatus
	elif gst.STATE_PAUSED in st:
	    return self.PauseStatus
	else:
	    return self.UndefinedStatus

    def current_position(self):
        """Returns the current position in ms.
	"""
        try:
            ret = self.player.query_position(gst.FORMAT_TIME)
        except:
            position = 0
        else:
            position = ret[0] / 1000
	
    def dvd_uri(self, title=None, chapter=None):
        return "dvd@%s:%s" % (str(title),
                              str(chapter))

    def log(self, *p):
        print "gstreamer player: %s" % p
        
    def get_media_position(self, origin, key):
	return self.current_position()

    def set_media_position(self, position):
	position = self.position2value(position) * 1000
        event = gst.event_new_seek(1.0, gst.FORMAT_TIME,
				   gst.SEEK_FLAG_FLUSH,
				   gst.SEEK_TYPE_SET, position,
				   gst.SEEK_TYPE_NONE, 0)
        res = self.player.send_event(event)
        if not res:
	    raise InternalException
    
    def start(self, position):
        self.player.set_state(gst.STATE_PLAYING)

    def pause(self, position): 
        if self.status == Player.PlayingStatus:
	    self.player.set_state(gst.STATE_PAUSED)
        else:
	    self.player.set_state(gst.STATE_PLAYING)
	    
    def resume(self, position):
	self.pause(position)

    def stop(self, position): 
        self.player.set_state(gst.STATE_READY)

    def exit(self):
	# FIXME
	pass
    
    def playlist_add_item(self, item):
	self.videofile=item
	if os.path.exists(item):
	    item="file://" + os.path.abspath(item)
        self.player.set_property('uri', item)

    def playlist_clear(self):
	self.videofile=None
	self.player.set_property('uri', '')

    def playlist_get_list(self):
        return [ self.videofile ]

    def snapshot(self, position):
        self.log("snapshot %s" % str(position))
        return None

    def all_snapshots(self):
        self.log("all_snapshots %s")
        return [ None ]
    
    def display_text (self, message, begin, end):
        self.log("display_text %s" % str(message))

    def get_stream_information(self):
        s=StreamInformation()
	if self.videofile:
	    s.url=''
	else:
	    s.url=self.videofile

        try:
            ret = self.player.query_duration(gst.FORMAT_TIME)
        except:
            duration = 0
        else:
            duration = ret[0] / 1000

	s.length=duration
	s.position=self.current_position()
	s.status=self.current_status()
        return s

    def sound_get_volume(self):
	# FIXME
        return 0

    def sound_set_volume(self, v):
	# FIXME
	return 0

    # Helper methods
    def create_position (self, value=0, key=None, origin=None):
        """Create a Position.
        """
	if key is None:
	    key=self.MediaTime
	if origin is None:
	    origin=self.AbsolutePosition
	
	p=Position()
	p.value = value
	p.origin = origin
	p.key = key
        return p

    def update_status (self, status=None, position=None):
        """Update the player status.

        Defined status:
           - C{start}
           - C{pause}
           - C{resume}
           - C{stop}
           - C{set}

        If no status is given, it only updates the value of self.status

        If C{position} is None, it will be considered as zero for the
        "start" action, and as the current relative position for other
        actions.

        @param status: the new status
        @type status: string
        @param position: the position
        @type position: long
        """
	if position is None:
	    position=0
	else:
	    position=self.position2value(position)

        if status == "start" or status == "set":
            self.position_update()
            if self.status in (self.EndStatus, self.UndefinedStatus):
                self.start(position)
            else:
                self.set_media_position(position)
        else:
            if status == "pause":
                self.position_update()
                if self.status == self.PauseStatus:
                    self.resume (position)
                else:
                    self.pause(position)
            elif status == "resume":
                self.resume (position)
            elif status == "stop":
                self.stop (position)
            elif status == "" or status == None:
                pass
            else:
                print "******* Error : unknown status %s in gstreamer player" % status
        self.position_update ()

    def is_active(self):
        return True

    def check_player(self):
        print "check player"
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.streamstatus or Player.UndefinedStatus
        self.stream_duration = s.length
        self.current_position_value = s.position

    def set_visual(self, xid):
        self.imagesink.set_xwindow_id(xid)
        return True

    def restart_player(self):
	# FIXME
	print "gstreamer: restart player"
	return True
