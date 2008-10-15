from unittest import TestCase, main

from advene.model.core.Package import Package

class TestElements(TestCase):
    def setUp(self):
        self.p = Package.create("sqlite::memory:")
        self.m = self.p.create_media("m1", "http://example.com/m1.avi")

    def tearDown(self):
        self.p = None

    def test_relation_members(self):
        m, p = self.m, self.p
        a = [None,] * 20
        for i in xrange(20):
            a[i] = p.create_annotation("a%s" % i, m, i*10, i*10+19)

        r = p.create_relation("r1")
        self.assertEqual ([], list(r))
        r.append(a[2])
        self.assertEqual ([a[2],], list(r))
        r.insert(0,a[1])
        self.assertEqual ([a[1], a[2]], list(r))
        r.insert(2,a[4])
        self.assertEqual ([a[1], a[2], a[4]], list(r))
        r.insert(100,a[5])
        self.assertEqual ([a[1], a[2], a[4], a[5]], list(r))
        r.insert(-2,a[3])
        self.assertEqual (a[1:6], list(r))
        r.insert(-6,a[0])
        self.assertEqual (a[0:6], list(r))
        r.extend(a[6:9])
        self.assertEqual (a[0:9], list(r))

        for i in xrange(9):
            self.assertEqual (a[i], r[i])
            r[i] = a[i+10]
            self.assertEqual (a[i+10], r[i])

        del r[5]
        self.assertEqual(a[10:15]+a[16:19], list(r))
        r.insert(5,a[15])


        self.assertEqual (a[10:19], r[:])
        self.assertEqual (a[10:13], r[:3])
        self.assertEqual (a[12:19], r[2:])
        self.assertEqual (a[12:13], r[2:3])
        self.assertEqual (a[10:19:2], r[::2])
        self.assertEqual (a[15:11:-2], r[5:1:-2])

        b = r[:]

        r[2:4] = a[0:9]
        b[2:4] = a[0:9]
        self.assertEqual (b, list(r))

        r[:] = a[0:9]
        b[:] = a[0:9]
        self.assertEqual (b, list(r))

        r[9:0:-2] = a[19:10:-2]
        b[9:0:-2] = a[19:10:-2]
        self.assertEqual (b, list(r))

        del r[0::2]
        del b[0::2]
        self.assertEqual (a[1:6:2], list(r))

if __name__ == "__main__":
    main()
