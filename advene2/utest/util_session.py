from unittest import TestCase, main
from threading import Event, Thread

from advene.util.session import session

class TestSession(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testDir(self):
        ref = ["package", "user"]
        self.assertEquals(frozenset(session._dir()), frozenset(ref))
        session.x_info = "more info"
        self.assertEquals(frozenset(session._dir()),
                          frozenset(ref + ["x_info",]))
        del session.x_info
        self.assertEquals(frozenset(session._dir()), frozenset(ref))

    def testSingleThreadRWD(self):
        self.assertEquals(session.user, None)
        session.user = "pchampin"
        self.assertEquals(session.user, "pchampin")
        del session.user
        self.assertEquals(session.user, None)

    def testSingleThreadClean(self):
        session.user = "pchampin"
        session._clean()
        self.assertEquals(session.user, None)

    def testSingleThreadRWDX(self):
        self.assertRaises(KeyError, lambda: session.x_info)
        session.x_info = "more info"
        self.assertEquals(session.x_info, "more info")
        del session.x_info
        self.assertRaises(KeyError, lambda: session.x_info)

    def testSingleThreadCleanX(self):
        session.x_info = "more info"
        session._clean()
        self.assertRaises(KeyError, lambda: session.x_info)

    def testSingleThreadUnauthorized(self):
        def set_unauthorized():
            session.foobar = "this is not a valid session variable"
        self.assertRaises(KeyError, set_unauthorized)

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
