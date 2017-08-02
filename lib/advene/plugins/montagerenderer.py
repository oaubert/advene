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
"""Montage export module.
"""

import os
import sys

try:
    import gst
except ImportError:
    gst = None

from gettext import gettext as _

name = 'montagerenderer'

def register(controller):
    if ( gst is not None
         and gst.element_factory_find('gnlcomposition')
         and gst.element_factory_find('gnlfilesource')
         and gst.element_factory_find('theoraenc')
         and gst.element_factory_find('vorbisenc')
         and gst.element_factory_find('oggmux') ):
        controller.register_generic_feature(name, MontageRenderer)
    else:
        controller.log(_("Cannot register montage renderer: Gnonlin plugins are not present."))

if gst is not None:
    CAPS_VIDEO_STRING = 'video/x-raw-yuv'
    CAPS_VIDEO = gst.caps_from_string(CAPS_VIDEO_STRING)
    CAPS_AUDIO_STRING = 'audio/x-raw-int;audio/x-raw-float'
    CAPS_AUDIO = gst.caps_from_string(CAPS_AUDIO_STRING)

class MontageRenderer(object):
    def __init__(self, controller, elements=None):
        self.controller = controller
        # self.elements is a list of annotations
        if elements is None:
            elements = []
        self.elements = elements
        self.encoding_pipe = None

    def render(self, outputfile, progress_callback = None):
        sourcefile = 'file:///' + self.controller.get_default_media()
        if not sourcefile:
            return
        pipedef = "gnlcomposition name=videocomp caps=%s ! queue ! progressreport name=progress silent=true update-freq=1 ! identity single-segment=true ! ffmpegcolorspace ! videorate ! theoraenc ! multiqueue name=muxqueue ! oggmux name=mux ! filesink name=sink gnlcomposition name=audiocomp caps=%s ! queue ! identity single-segment=true ! audioconvert ! audiorate ! vorbisenc ! muxqueue." % (CAPS_VIDEO_STRING, CAPS_AUDIO_STRING)
        pipe = gst.parse_launch(pipedef)
        videocomp = pipe.get_by_name('videocomp')
        audiocomp = pipe.get_by_name('audiocomp')
        sink = pipe.get_by_name('sink')
        bus = pipe.get_bus()
        bus.enable_sync_message_emission()

        def filesource(a, pos, caps):
            """Create a filesource.
            """
            e = gst.element_factory_make('gnlfilesource')
            e.set_property("location", sourcefile)
            e.set_property("caps", caps)
            e.set_property("start", pos * gst.MSECOND)
            e.set_property("duration", a.fragment.duration * gst.MSECOND)
            e.set_property("media-start", a.fragment.begin * gst.MSECOND)
            e.set_property("media-duration", a.fragment.duration * gst.MSECOND)
            return e

        pos = 0
        for a in self.elements:
            e = filesource(a, pos, CAPS_VIDEO)
            videocomp.add(e)
            e = filesource(a, pos, CAPS_AUDIO)
            audiocomp.add(e)
            pos += a.fragment.duration

        sink.set_property("location", outputfile)

        def on_bus_message(bus, message):
            s = message.get_structure()
            if message.type == gst.MESSAGE_STATE_CHANGED:
                old, new, pending = message.parse_state_changed()
                logger.warn("STATE %s %s %s", old.value_nick, new.value_nick, pending.value_nick)
            elif message.type == gst.MESSAGE_EOS:
                logger.warn(" EOS")
                pipe.set_state(gst.STATE_NULL)
                progress_callback(None)
            elif s:
                logger.warn("MSG %s %s", bus.get_name(), s.to_string())
                if s.get_name() == 'progress' and progress_callback is not None:
                    progress_callback(s['percent-double'] / 100)
            return True

        bus.add_signal_watch()
        bus.connect('message', on_bus_message)
        pipe.set_state(gst.STATE_PLAYING)
        self.encoding_pipe = pipe
        return True

    def finalize(self):
        if self.encoding_pipe is not None:
            self.encoding_pipe.set_state(gst.STATE_NULL)
            self.encoding_pipe = None

    # relpath, dump_bin and dump_element implementation based on Daniel Lenski <dlenski@gmail.com>
    # posted on gst-dev mailing list on 20070913
    def relpath(self, p1, p2):
        sep = os.path.sep

        # get common prefix (up to a slash)
        common = os.path.commonprefix((p1, p2))
        common = common[:common.rfind(sep)]

        # remove common prefix
        p1 = p1[len(common)+1:]
        p2 = p2[len(common)+1:]

        # number of seps in p1 is # of ..'s needed
        return "../" * p1.count(sep) + p2

    def dump_bin(self, bin, depth=0, recurse=-1, showcaps=True):
        return [ l  for e in reversed(list(bin)) for l in self.dump_element(e, depth, recurse - 1) ]

    def dump_element(self, e, depth=0, recurse=-1, showcaps=True):
        ret=[]
        indentstr = depth * 8 * ' '

        # print element path and factory
        path = e.get_path_string() + (isinstance(e, gst.Bin) and '/' or '')
        factory = e.get_factory()
        if factory is not None:
            ret.append( '%s%s (%s)' % (indentstr, path, factory.get_name()) )
        else:
            ret.append( '%s%s (No factory)' % (indentstr, path) )

        # print info about each pad
        for p in e.pads():
            name = p.get_name()

            # negotiated capabilities
            caps = p.get_negotiated_caps()
            if caps: capsname = caps[0].get_name()
            elif showcaps: capsname = '; '.join(s.to_string() for s in set(p.get_caps()))
            else: capsname = None

            # flags
            flags = []
            if not p.is_active(): flags.append('INACTIVE')
            if p.is_blocked(): flags.append('BLOCKED')

            # direction
            direc = (p.get_direction() is gst.PAD_SRC) and "=>" or "<="

            # peer
            peer = p.get_peer()
            if peer: peerpath = self.relpath(path, peer.get_path_string())
            else: peerpath = None

            # ghost target
            if isinstance(p, gst.GhostPad):
                target = p.get_target()
                if target: ghostpath = target.get_path_string()
                else: ghostpath = None
            else:
                ghostpath = None

            line=[ indentstr, "    " ]
            if flags: line.append( ','.join(flags) )
            line.append(".%s" % name)
            if capsname: line.append( '[%s]' % capsname )
            if ghostpath: line.append( "ghosts %s" % self.relpath(path, ghostpath) )
            line.append( "%s %s" % (direc, peerpath) )

            #if peerpath and peerpath.find('proxy')!=-1: print peer
            ret.append( ''.join(line) )
        if recurse and isinstance(e, gst.Bin):
            ret.extend( self.dump_bin(e, depth+1, recurse) )
        return ret

    def str_element(self, element):
        return "\n".join(self.dump_element(element))

