#! /usr/bin/env python

import sys
import ORBit, CORBA
import Image
import os
import time
import advene.core.config as config
import advene.util.vlclib as vlclib
import advene.core.mediacontrol
import atexit
import signal

print "Chargement de l'IDL"
ORBit.load_typelib (config.data.typelib)
import VLC

def create_position (value=0, key=VLC.MediaTime,
		     origin=VLC.AbsolutePosition):
        """
        Returns a VLC.Position object initialized to the right value. By
        default using a MediaTime in AbsolutePosition.
        """
        p = VLC.Position ()
        p.origin = origin
        p.key = key
        p.value = value
        return p

def snapshot (file="/tmp/snapshot.png"):
	global a, pos
	print "Taking a snapshot to %s" % file
	a = mc.snapshot (pos)
	vlclib.snapshot2png (a, file)
	raw = open(file + ".raw", "w")
	raw.write(a.data)
	raw.close()
	print "done."

def capture():
	l = []
	n = 50
	print "Taking %d snapshots" % n
	for i in range(0, n):
		a = mc.snapshot (pos)
		l.append(a)
	print "Done"
	print "Saving %d snapshots" % n
	for i in range(len(l)):
		vlclib.snapshot2png (l[i], "/tmp/snapshot%02d.png" % i)
	print "Done"

def dvd (title=1, chapter=1):
	mc.playlist_add_item("dvd:/dev/dvd@%d,%d" % (title, chapter))
	mc.start(pos)
	
def quit ():
	global player,mc
	print "Stopping player"
	try:
		if player.is_active ():
			print "Calling player.stop"
			player.stop () 
	except:
		print "Not doing anything"
		pass
	mc.exit()
	return True

def test (file="/tmp/k.mpg"):
	mc.playlist_add_item (file)
	print "%s added..." % file

def save (data, file="/tmp/data.raw"):
	f = open(file, "w")
	f.write (data)
	f.close ()
	print "Data saved in %s" % file

def init ():
	global pos, rpos, apos, p, player, mc
	global begin, end
	global svg
	
	print "Initialisation de l'ORB"
	player=advene.core.mediacontrol.PlayerLauncher(config.data)
	orb,mc=player.init()

	print "Objet mc %s" % mc
	pos = create_position (value=0,
			       origin=VLC.RelativePosition,
			       key=VLC.MediaTime)
	print "pos is the current position (relative)"
	apos = create_position (0)
	
	print "rpos is a relative position (+5000 ms)"
	rpos = create_position (value=20000,
				origin=VLC.RelativePosition,
				key=VLC.MediaTime)
	
	print "apos is an AbsolutePosition in MediaTime units"
	begin = create_position (value=1000, key=VLC.MediaTime)
	end = create_position (value=3000, key=VLC.MediaTime)

	#print "svg contains SVG code"
	#svg = open('/extra/archive/oaubert/tmp/download/klipart/maps and flags/worldmap.svg', 'r').read()
	#svg = open('/home/oaubert/test.svg', 'r').read()

atexit.register (quit)

init ()
if len(sys.argv) > 1:
	# Arguments were given. Execute them
	s = " ".join(sys.argv[1:])
	print "Executing %s" % s
	eval (s)
	sys.exit (0)
	    
try:
    __IPYTHON__
except NameError:
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed()
    # Now ipshell() will open IPython anywhere in the code
else:
    # Define a dummy ipshell() so the same code doesn't crash inside an
    # interactive IPython
    def ipshell(): pass

ipshell()
