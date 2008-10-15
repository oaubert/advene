"""
This file should contain unit tests for cam.package.
Specific features of cam.package must obviously be tested here.

A lot of things informally tested in test/test1-cam.py should be transposed
here.
"""
from unittest import TestCase, main

from advene.model.cam.package import Package
from advene.model.core.package import Package as CorePackage


class TestInherit(TestCase):
    def test_inherit(self):
        self.assert_(issubclass(Package, CorePackage))
        # this makes all tests for CorePackage considered valid for Package
        # (assuming of course that *all* differing behaviours are otherwise
        # tested here)

if __name__ == "__main__":
    main()
