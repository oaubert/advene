from unittest import TestCase, main
from threading import Thread
from time import sleep

from advene.util.synchronized import enter_cs, exit_cs, synchronized

class Dummy(object):
    def hello(self, who="world"):
        return "hello %s" % who

class TestSynchronize(TestCase):



    def test_sc(self):
        d = Dummy()
        shared = [0,]
        def func(use_cs):
            for i in xrange(10):
                if use_cs: enter_cs(d)
                try:
                    i = shared[0]
                    sleep(.001)
                    shared[0] = i+1
                finally:
                    if use_cs: exit_cs(d)
        t1 = Thread(target=func, args=[False])
        t2 = Thread(target=func, args=[False])
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # control test: it should not work without critical sections
        self.assertNotEqual(shared, [20])

        shared[0] = 0
        t1 = Thread(target=func, args=[True])
        t2 = Thread(target=func, args=[True])
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # actual test: it should work with critical sections
        self.assertEqual(shared, [20])

    def test_decorator(self):
        class DummySync(Dummy):
            a = 0
            def plain_method(self):
                i = self.a
                sleep(.001)
                self.a = i+1
            @synchronized
            def synced_method(self):
                self.plain_method()
        d = DummySync()
        def f(d, method_name):
            for i in xrange(10):
                getattr(d, method_name)()
        t1 = Thread(target=f, args=[d, "plain_method"])
        t2 = Thread(target=f, args=[d, "plain_method"])
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # control test: it should not work without critical sections
        self.assertNotEqual(d.a, 20)

        d.a = 0
        t1 = Thread(target=f, args=[d, "synced_method"])
        t2 = Thread(target=f, args=[d, "synced_method"])
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # actual test: it should work with critical sections
        self.assertEqual(d.a, 20)



if __name__ == "__main__":
    main()
