"""Dummy CORBA package."""

import VLC

class COMM_FAILURE(Exception):
    pass

class ORB:
    def string_to_object (self, ior):
        return VLC.MediaControl()

def ORB_init (*p, **kw):
    print "ORB_init"
    return ORB()

