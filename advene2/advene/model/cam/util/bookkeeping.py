from advene.model.consts import DC_NS_PREFIX
from advene.util.session import session

from datetime import datetime
from os import getlogin

def _make_bookkeeping_data():
    return datetime.now().isoformat(), session.user or getlogin()

CREATOR = DC_NS_PREFIX + "creator"
CREATED = DC_NS_PREFIX + "created"
CONTRIBUTOR = DC_NS_PREFIX + "contributor"
MODIFIED = DC_NS_PREFIX + "modified"

def init(package, obj):
    d,u = _make_bookkeeping_data()
    obj.enter_no_event_section(); \
        obj.set_meta(CREATOR, u); \
        obj.set_meta(CREATED, d); \
        obj.set_meta(CONTRIBUTOR, u); \
        obj.set_meta(MODIFIED, d)
    obj.exit_no_event_section()
    if obj is not package:
        package.enter_no_event_section(); \
            package.set_meta(CONTRIBUTOR, u); \
            package.set_meta(MODIFIED, d)
        package.exit_no_event_section()

def update(obj, *args):
    d,u = _make_bookkeeping_data()
    #d = "%s %s" % (d, args) # debug
    obj.enter_no_event_section(); \
        obj.set_meta(CONTRIBUTOR, u); \
        obj.set_meta(MODIFIED, d)
    obj.exit_no_event_section()

def update_owner(obj, *args):
    d,u = _make_bookkeeping_data()
    #d = "%s %s" % (d, args) # debug
    package = obj._owner
    package.enter_no_event_section(); \
        package.set_meta(CONTRIBUTOR, u); \
        package.set_meta(MODIFIED, d)
    package.exit_no_event_section()

def update_element(obj, *args):
    # actually a copy of both update and update_owner
    # but this is more efficient this way,
    # and since it is going to be called *many* times...
    d,u = _make_bookkeeping_data()
    #d = "%s %s" % (d, args) # debug
    #if obj._id == "at": import pydb; pydb.set_trace()
    obj.enter_no_event_section(); \
        obj.set_meta(CONTRIBUTOR, u); \
        obj.set_meta(MODIFIED, d)
    obj.exit_no_event_section()
    package = obj._owner
    package.enter_no_event_section(); \
        package.set_meta(CONTRIBUTOR, u); \
        package.set_meta(MODIFIED, d)
    package.exit_no_event_section()
