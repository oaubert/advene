from unittest import TestCase, main
from threading import Event, Thread

from advene.util.session import session, get_session_defaults

class TestSession(TestCase):
    def setUp(self):
        for k in get_session_defaults():
            delattr(session, k)

    def tearDown(self):
        pass

    def testDir(self):
        ref = get_session_defaults().keys()
        self.assertEquals(frozenset(session._dir()), frozenset(ref))
        session.x_info = "more info"
        self.assertEquals(frozenset(session._dir()),
                          frozenset(ref + ["x_info",]))
        del session.x_info
        self.assertEquals(frozenset(session._dir()), frozenset(ref))

    def testSingleThreadRWD(self):
        for k,v in get_session_defaults().iteritems():
            self.assertEquals(getattr(session, k), v)
            setattr(session, k, "foobar")
            self.assertEquals(getattr(session, k), "foobar")
            delattr(session, k)
            self.assertEquals(getattr(session, k), v)

    def testSingleThreadRWDX(self):
        self.assertRaises(AttributeError, lambda: session.x_info)
        session.x_info = "more info"
        self.assertEquals(session.x_info, "more info")
        del session.x_info
        self.assertRaises(AttributeError, lambda: session.x_info)

    def testSingleThreadUnauthorized(self):
        def set_unauthorized():
            session.foobar = "this is not a valid session variable"
        self.assertRaises(AttributeError, set_unauthorized)

    def testMultipleThread(self):
        e = Event()
        check = []
        def doit(v):
            session.user = v
            e.set(); e.wait()
            check.append(session.user)
            e.set()
        Thread(target=doit, args=["u42",]).start()
        e.wait()
        doit("u101")
        self.assertEquals(check, ["u42", "u101",])
        del session.user

    def testMultipleThreadX(self):
        e = Event()
        check = []
        def doit(v):
            session.x_info = v
            e.set(); e.wait()
            check.append(session.x_info)
            e.set()
        Thread(target=doit, args=["u42",]).start()
        e.wait()
        doit("u101")
        self.assertEquals(check, ["u42", "u101",])
        del session.x_info

    def testMultipleThreadUndefined(self):
        e = Event()
        check = []
        def doit():
            session.x_info = "more info"
            e.set(); e.wait()
            check.append("x_info" in session._dir())
            e.set()
        Thread(target=doit).start()
        e.wait()
        check.append("x_info" in session._dir())
        self.assertEquals(check, [True, False,])

if __name__ == "__main__":
    main()
