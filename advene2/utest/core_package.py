import gc
from os import tmpnam, unlink
from os.path import abspath, split
from unittest import TestCase, main
from urllib import pathname2url
from warnings  import filterwarnings

from advene.model.core.package import Package
from advene.model.backends.sqlite import _set_module_debug

filterwarnings("ignore", "tmpnam is a potential security risk to your program")
_set_module_debug(True) # enable all asserts in backend_sqlite



class TestCreation(TestCase):
    # TODO this is not complete

    def test_create_transient(self):
        # use invalid URL scheme to force the package to be transient
        p = Package("x-invalid-scheme:xyz", create=True)
        p.close()
        # if the second times woirks (with create=True), then transient works
        p = Package("x-invalid-scheme:xyz", create=True)
        p.close()
        

class TestImports(TestCase):
    def setUp(self):
        self.db = tmpnam()
        self.url = "sqlite:%s" % pathname2url(self.db)
        self.p1 = Package(self.url+";p1", create=True)
        self.p2 = Package(self.url+";p2", create=True)
        self.p3 = Package(self.url+";p3", create=True)
        self.p4 = Package(self.url+";p4", create=True)

        self.d1 = frozenset(((self.p1._backend, self.p1._id),))
        self.d2 = frozenset(((self.p2._backend, self.p2._id),))
        self.d3 = frozenset(((self.p3._backend, self.p3._id),))
        self.d4 = frozenset(((self.p4._backend, self.p4._id),))

    def _dependencies(self, p):
        return frozenset(
            (be, pid) for be, pdict in p._backends_dict.items()
                      for pid in pdict
        )

    def test_dependancies(self):
        p1, p2, p3, p4 = self.p1, self.p2, self.p3, self.p4
        d1, d2, d3, d4 = self.d1, self.d2, self.d3, self.d4
        dall = d1.union(d2).union(d3).union(d4)
        _dependencies = self._dependencies

        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2, _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p2.create_import("p4", self.p4)
        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1.create_import("p2", self.p2)
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p3.create_import("p4", self.p4)
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1.create_import("p3", self.p3)
        self.assertEqual(dall, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p4.create_import("p1", self.p1)
        self.assertEqual(dall, _dependencies(p1))
        self.assertEqual(dall, _dependencies(p2))
        self.assertEqual(dall, _dependencies(p3))
        self.assertEqual(dall, _dependencies(p4))

        self.p4["p1"].delete()
        self.assertEqual(dall, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1["p3"].delete()
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3.union(d4), _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p3["p4"].delete()
        self.assertEqual(d1.union(d2).union(d4), _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p1["p2"].delete()
        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2.union(d4), _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

        self.p2["p4"].delete()
        self.assertEqual(d1, _dependencies(p1))
        self.assertEqual(d2, _dependencies(p2))
        self.assertEqual(d3, _dependencies(p3))
        self.assertEqual(d4, _dependencies(p4))

    def test_close_unimported(self):
        self.p1.create_import("p2", self.p2)
        self.p1.close()
        self.assert_(self.p1.closed)
        self.assert_(not self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_simply_imported(self):
        self.p1.create_import("p2", self.p2)
        self.assertRaises(ValueError, self.p2.close)
        self.assert_(not self.p1.closed)
        self.assert_(not self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_cycle(self):
        self.p1.create_import("p2", self.p2)
        self.p2.create_import("p1", self.p1)
        self.p1.create_import("p3", self.p3)
        self.p2.create_import("p4", self.p4)
        self.p1.close()
        self.assert_(self.p1.closed)
        self.assert_(self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_imported_cycle(self):
        self.p1.create_import("p2", self.p2)
        self.p2.create_import("p1", self.p1)
        self.p3.create_import("p1", self.p1)
        self.assertRaises(ValueError, self.p1.close)
        self.assert_(not self.p1.closed)
        self.assert_(not self.p2.closed)
        self.assert_(not self.p3.closed)
        self.assert_(not self.p4.closed)

    def test_close_multiple_cycles(self):
        self.p1.create_import("p2", self.p2)
        self.p1.create_import("p3", self.p3)
        self.p2.create_import("p4", self.p4)
        self.p3.create_import("p4", self.p4)
        self.p4.create_import("p1", self.p1)
        self.p2.close()
        self.assert_(self.p1.closed)
        self.assert_(self.p2.closed)
        self.assert_(self.p3.closed)
        self.assert_(self.p4.closed)

    def tearDown(self):
        unlink(self.db)

if __name__ == "__main__":
    main()

