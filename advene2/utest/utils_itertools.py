from unittest import TestCase, main

from advene.utils.itertools import *
from advene.utils.itertools import _IterHead

class TestIterHead (TestCase):
    def test1 (self):
        ih = _IterHead (iter ([1,2,3,4]))
        self.assertEquals (ih.head, 1)
        ih.fetch_next()
        self.assertEquals (ih.head, 2)
        ih.fetch_next()
        self.assertEquals (ih.head, 3)
        ih.fetch_next()
        self.assertEquals (ih.head, 4)
        ih.fetch_next()
        self.assertEquals (ih.head, None)

class TestInterclass (TestCase):
    def setUp (self):
        self.l1 = [1,3,5,7,9,11,13,15,17,19]
        self.l2 = [2,6,10]
        self.l3 = [4,8,12,16]
        self.l4 = []

    def test1 (self):
        self.assertEquals (
            list (interclass (self.l1)),
            self.l1,
        )

    def test2 (self):
        self.assertEquals (
            list (interclass (self.l2, self.l3)),
            [2,4,6,8,10,12,16],
        )

    def test3 (self):
        self.assertEquals (
            list (interclass (self.l1, self.l2, self.l3)),
            [1,2,3,4,5,6,7,8,9,10,11,12,13,15,16,17,19],
        )

    def test4 (self):
        self.assertEquals (
            list (interclass (self.l1, self.l2, self.l3, self.l4)),
            [1,2,3,4,5,6,7,8,9,10,11,12,13,15,16,17,19],
        )

    def test_no_doublons (self):
        self.assertEquals (
            list (interclass (self.l1, self.l1)),
            self.l1,
        )

if __name__ == "__main__":
     main()
     print list (interclass (l1, l2, l3, l4))
