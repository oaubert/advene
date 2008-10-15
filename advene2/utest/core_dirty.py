from unittest import TestCase, main
from weakref import ref

from advene.model.core.dirty import DirtyMixin
from advene.utils.autoproperties import AutoPropertiesMetaclass

class C(object, DirtyMixin):
    __metaclass__ = AutoPropertiesMetaclass

    def __init__(self, ref_ab, ref_xy):
        self.ref_ab = ref_ab
        self.ref_xy = ref_xy
        self.cache_ab = ref_ab.copy()
        self.cache_xy = ref_xy.copy()
        self.dirty_ab = {}
        self.dirty_xy = {}

    def _get_a(self):
        return self.cache_ab["a"]

    def _set_a(self, val):
        self.cache_ab["a"] = self.dirty_ab["a"] = val
        self.add_cleaning_operation(self.clean_ab)

    def _get_b(self):
        return self.cache_ab["b"]

    def _set_b(self, val):
        self.cache_ab["b"] = self.dirty_ab["b"] = val
        self.add_cleaning_operation(self.clean_ab)

    def _get_x(self):
        return self.cache_xy["x"]

    def _set_x(self, val):
        self.cache_xy["x"] = self.dirty_xy["x"] = val
        self.add_cleaning_operation(self.clean_xy)

    def _get_y(self):
        return self.cache_xy["y"]

    def _set_y(self, val):
        self.cache_xy["y"] = self.dirty_xy["y"] = val
        self.add_cleaning_operation(self.clean_xy)

    def clean_ab(self):
        self.ref_ab.update(self.cache_ab)

    def clean_xy(self):
        self.ref_xy.update(self.cache_xy)

    @property
    def consistent(self):
        return (self.ref_ab == self.cache_ab and self.ref_xy == self.cache_xy)

class TestDirty(TestCase):
    def setUp(self):
        self.o = C({"a":"A", "b":"B"}, {"x":None, "y":None})

    def testC(self):
        self.assertEquals(self.o.a, "A")
        self.assertEquals(self.o.b, "B")
        self.assertEquals(self.o.x, None)
        self.assertEquals(self.o.y, None)
        self.o.a = None
        self.o.b = None
        self.o.x = "X"
        self.o.y = "Y"
        self.assertEquals(self.o.a, None)
        self.assertEquals(self.o.b, None)
        self.assertEquals(self.o.x, "X")
        self.assertEquals(self.o.y, "Y")

    def testNotDirty(self):
        self.assert_(not self.o.dirty)

    def testCleanNothing(self):
        self.o.clean()

    def testDirtyOnA(self):
        self.o.a = "foo"
        self.assert_(self.o.dirty)
        self.assert_(not self.o.consistent)
        self.o.clean()
        self.assert_(not self.o.dirty)
        self.assert_(self.o.consistent)

    def testDirtyOnB(self):
        self.o.b = "foo"
        self.assert_(self.o.dirty)
        self.assert_(not self.o.consistent)
        self.o.clean()
        self.assert_(not self.o.dirty)
        self.assert_(self.o.consistent)

    def testDirtyOnX(self):
        self.o.x = "foo"
        self.assert_(self.o.dirty)
        self.assert_(not self.o.consistent)
        self.o.clean()
        self.assert_(not self.o.dirty)
        self.assert_(self.o.consistent)

    def testDirtyOnY(self):
        self.o.y = "foo"
        self.assert_(self.o.dirty)
        self.assert_(not self.o.consistent)
        self.o.clean()
        self.assert_(not self.o.dirty)
        self.assert_(self.o.consistent)

    def testDirtyEvenIfConsistent(self):
        self.o.a = "A"
        self.assert_(self.o.dirty)
        self.assert_(self.o.consistent)
        self.o.clean()
        self.assert_(not self.o.dirty)
        self.assert_(self.o.consistent)

    def testCleanDuplicateOperation(self):
        self.o.a = "foo"
        self.o.a = "bar"
        self.assertEquals(len(self.o._DirtyMixin__pending), 1)
        self.assert_(self.o.dirty)
        self.assert_(not self.o.consistent)
        self.o.clean()
        self.assert_(not self.o.dirty)
        self.assert_(self.o.consistent)

    def testCleanSeveralOperations(self):
        self.o.a = "foo"
        self.o.x = "bar"
        self.assertEquals(len(self.o._DirtyMixin__pending), 2)
        self.assert_(self.o.dirty)
        self.assert_(not self.o.consistent)
        self.o.clean()
        self.assert_(not self.o.dirty)
        self.assert_(self.o.consistent)

    def testException(self):
        self.o.add_cleaning_operation(lambda: 1/0)
        self.assertRaises(ZeroDivisionError, self.o.clean)
        self.assertEquals(len(self.o._DirtyMixin__pending), 1)

    def testNoLastChanceIfUnchanged(self):
        wo = ref(self.o)
        del self.o
        self.assertEquals(wo(), None)

    def testLastChance(self):
        wo = ref(self.o)
        self.o.a = "foo"
        del self.o
        self.assertNotEqual(wo(), None)
        self.assert_(wo().dirty)
        wo().clean()
        self.assertEquals(wo(), None)

if __name__ == "__main__":
    main()
