import gc
from unittest import TestCase, main

from advene.model.core.package import Package

class TestElements(TestCase):
    def setUp(self):
        self.p = Package("sqlite::memory:", create=True)
        try:
            self.p.create_media("m1", "http://example.com/m1.avi")
        except Exception:
            pass

    def tearDown(self):
        self.p.close()

    def test_annotation(self):
        p = self.p
        m = p["m1"]
        a = p.create_annotation("a1", m, 10, 20)
        self.assertEqual( m, a.media)
        self.assertEqual(10, a.begin)
        self.assertEqual(20, a.end)
        a.begin += 5
        self.assertEqual(15, a.begin)
        a.end += 10
        self.assertEqual(30, a.end)
        m2 = p.create_media("m2", "http://example.com/m2.avi")
        a.media = m2
        self.assertEqual(m2, a.media)

    def _test_list_like(self, L, a):
        # L is the list-like element to test
        # a is a list of 2O potential items for L
        p = self.p

        self.assertEqual([], list(L))
        L.append(a[2])
        self.assertEqual([a[2],], list(L))
        L.insert(0,a[1])
        self.assertEqual([a[1], a[2]], list(L))
        L.insert(2,a[4])
        self.assertEqual([a[1], a[2], a[4]], list(L))
        L.insert(100,a[5])
        self.assertEqual([a[1], a[2], a[4], a[5]], list(L))
        L.insert(-2,a[3])
        self.assertEqual(a[1:6], list(L))
        L.insert(-6,a[0])
        self.assertEqual(a[0:6], list(L))
        L.extend(a[6:9])
        self.assertEqual(a[0:9], list(L))

        for i in xrange(9):
            self.assertEqual(a[i], L[i])
            L[i] = a[i+10]
            self.assertEqual(a[i+10], L[i])

        del L[5]
        self.assertEqual(a[10:15]+a[16:19], list(L))
        L.insert(5,a[15])


        self.assertEqual(a[10:19], L[:])
        self.assertEqual(a[10:13], L[:3])
        self.assertEqual(a[12:19], L[2:])
        self.assertEqual(a[12:13], L[2:3])
        self.assertEqual(a[10:19:2], L[::2])
        self.assertEqual(a[15:11:-2], L[5:1:-2])

        b = L[:]

        L[2:4] = a[0:9]
        b[2:4] = a[0:9]
        self.assertEqual(b, list(L))

        L[:] = a[0:10]
        b[:] = a[0:10]
        self.assertEqual(b, list(L))

        L[9:0:-2] = a[19:10:-2]
        b[9:0:-2] = a[19:10:-2]
        self.assertEqual(b, list(L))

        del L[0::2]
        del b[0::2]
        self.assertEqual(b, list(L))

    def test_relation_members(self):
        p = self.p
        m = p["m1"]
        a = []
        for i in xrange(20):
            a.append(p.create_annotation("a%s" % i, m, i*10, i*10+19))

        r = p.create_relation("r1")

        self._test_list_like(r,a)

    def test_list_items(self):
        p = self.p

        a = []
        for i in xrange(10):
            a.append(p.create_relation("r%s" % i))
        for i in xrange(10):
            a.append(p.create_list("x%s" % i))

        L = p.create_list("l1")

        self._test_list_like(L, a)


if __name__ == "__main__":
    main()
