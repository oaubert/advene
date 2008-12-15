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
"""Quicktime player interface (through ctypes)
"""

import sys
import gtk
import gobject

try:
    import qtmovie
except ImportError:
    qtmovie=None

name="Quicktime video player"

def register(controller=None):
    if qtmovie is None:
        return False
    controller.register_player(Player)
    return True

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
    InitStatus=2
    EndStatus=3
    UndefinedStatus=4

    PositionKeyNotSupported=Exception()
    PositionOriginNotSupported=Exception()
    InvalidPosition=Exception()
    PlaylistException=Exception()
    InternalException=Exception()

    def __init__(self):
        self.playlist=[]
        self.movie=qtmovie.Movie()
        self.relative_position=0
        self.status=Player.UndefinedStatus
        self.stream_duration = 0
        self.position_update()

        def update_movie():
            if self.movie:
                self.movie.MoviesTask(0)
            return True
        gobject.timeout_add (25, update_movie)

    def log(self, *m):
        print "quicktime plugin:", " ".join([str(i) for i in m])

    def position2value(self, p):
        if isinstance(p, Position):
            v=p.value
            if p.key != self.MediaTime:
                self.log("unsupported key ", p.key)
                return 0
            if p.origin == self.AbsolutePosition:
                v=p.value
            else:
                v=self.current_position() + p.value
        else:
            v=long(p)
        return v

    def current_position(self):
        # FIXME: if performance is too low, it could maybe help to shortcut
        # directly to qtlowlevel functions.
        if self.movie:
            rec=self.movie.GetMovieTime()
            if rec.scale:
                ms=1000 * rec.value / rec.scale
            else:
                # It so happens that rec.scale == 0, so let us just
                # consider that rec.value is in microseconds (to confirm ?)
                ms=rec.value / 1000
        else:
            ms=-1
        return ms

    def dvd_uri(self, title=None, chapter=None):
        return "dvd@%s:%s" % (str(title),
                              str(chapter))

    def get_media_position(self, origin=None, key=None):
        """FIXME: Handle origin, key values.
        """
        return self.current_position()

    def set_media_position(self, position=0):
        if self.movie:
            position = self.position2value(position)
            self.movie.SetMovieTime(position)

    def start(self, position=0):
        if self.movie:
            self.movie.StartMovie()
            self.status=Player.PlayingStatus
            if position:
                self.set_media_position(position)

    def pause(self, position=0):
        if self.status == Player.PlayingStatus:
            self.movie.SetMovieRate(0)
            self.status=Player.PauseStatus
        else:
            self.movie.SetMovieRate(1)
            self.status=Player.PlayingStatus

    def resume(self, position=0):
        self.pause(position)

    def stop(self, position=0):
        if self.movie:
            self.movie.StopMovie()
        self.status=Player.UndefinedStatus

    def exit(self):
        # FIXME: cleanly exit the player (DisposeMovie + ExitMovies + TerminateQTML)
        self.log("exit")

    def playlist_add_item(self, item):
        self.playlist=[item]
        self.movie.open(item)
        self.set_widget()
        self.stream_duration=self.movie.duration
        self.status=Player.UndefinedStatus

    def playlist_clear(self):
        del self.playlist[:]

    def playlist_get_list(self):
        return self.playlist[:]

    def snapshot(self, position):
        # FIXME: to implement (GetMoviePict)
        self.log("snapshot %s" % str(position))
        return None

    def display_text (self, message, begin, end):
        # FIXME: to implement (cf http://developer.apple.com/documentation/QuickTime/Reference/QTRef_MovieManager/Reference/reference.html#//apple_ref/c/func/TextMediaAddTextSample)
        self.log("display_text %s" % str(message))

    def get_stream_information(self):
        s=StreamInformation()
        s.url=''
        if self.playlist:
            s.url=self.playlist[0]
        s.length=self.stream_duration
        s.position=self.current_position()
        s.streamstatus=self.status
        return s

    def sound_get_volume(self):
        # FIXME: normalize in 0..100
        if self.movie:
            return self.movie.GetMovieVolume()
        else:
            return 0

    def sound_set_volume(self, v):
        # FIXME: normalize in 0..100
        if self.movie:
            self.movie.SetMovieVolume(v)

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
        self.log("update_status %s" % status)

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
                self.log("******* Error : unknown status %s" % status)
        self.position_update ()

    def is_active(self):
        return True

    def check_player(self):
        self.log("check player")
        return True

    def position_update(self):
        s = self.get_stream_information ()
        self.status = s.streamstatus
        self.stream_duration = s.length
        self.current_position_value = s.position

    def set_widget(self, widget=None):
        """Set the widget for the video output.

        If this method is defined, it should be called in priority to
        set_visual.
        """
        if widget is None:
            widget=self.widget
            reuse=True
        else:
            self.widget=widget
            reuse=False

        if sys.platform == 'win32':
            visual_id=widget.window.handle
        else:
            visual_id=widget.window.xid
        if self.movie:
            self.movie.set_visual(visual_id)
            # Resize widget to match movie size
            rect=self.movie.GetMovieBox()
            width=rect.right-rect.left
            height=rect.bottom-rect.top
            widget.set_size_request( width, height )

        if not reuse:
            def resize(w, alloc):
                """Handle resize of DrawingArea.

                Resize the video, keeping its aspect ratio.
                """
                if not self.movie:
                    return True
                if 100 * alloc.width / alloc.height > self.movie.aspect_ratio:
                    w=alloc.height * self.movie.aspect_ratio / 100
                    h=alloc.height
                else:
                    w=alloc.width
                    h=w * 100 / self.movie.aspect_ratio
                self.movie.SetMovieBox( qtmovie.Rect(alloc.y + (alloc.height - h) / 2,
                                                     alloc.x + (alloc.width -w) / 2,
                                                     alloc.y + h,
                                                     alloc.x + w))
                return True

            widget.connect('size-allocate', resize)
        return True

    def restart_player(self):
        self.log("restart player")
        return True

def test(fname):
    """Old code, for historical purpose.
    """
    w=gtk.Window()
    d=gtk.DrawingArea()
    w.add(d)
    w.show_all()
    hwnd=d.window.handle
    movie=qtmovie.new_movie_from_filename(fname, MAX_PATH=255)

    w.connect('destroy', lambda w: gtk.main_quit())

    movie.set_widget(d)
    movie.StartMovie()

    def update_movie(movie):
        movie.MoviesTask(0)
        if movie.IsMovieDone():
            movie.GoToBeginningOfMovie()
        return True

    gobject.timeout_add (25, update_movie, movie)
    gtk.main ()

if __name__ == '__main__':
    test(sys.argv[1])
