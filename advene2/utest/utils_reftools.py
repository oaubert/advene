from unittest import TestCase, main

from advene.utils.reftools import WeakValueDictWithCallback

class A(object):
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return "A(%r)" % self.name

class TestWeakValueDictWithCallback(TestCase):
    def setUp(self):
        self.a = A("a")
        self.b = A("b")
        self.c = A("c")
        self.k = ["a", "b",]
        self.w = WeakValueDictWithCallback(self._remove)
        self.w.update({"a":self.a, "b":self.b})

    def _remove(self, key):
        self.k.remove(key)

    def tearDown(self):
        del self.w

    def _testEqual(self):
        self.assertEquals(frozenset(self.k), frozenset(self.w.keys()))

    def testInit(self):
        self._testEqual()

    def testRemove(self):
        del self.b
        self._testEqual()
        del self.a
        self._testEqual()

    def testSetItemThenRemove(self):
        self.w["c"] = self.c
        self.k.append("c")
        self._testEqual()
        self.testRemove()
        del self.c
        self._testEqual()

if __name__ == "__main__":
    main()
