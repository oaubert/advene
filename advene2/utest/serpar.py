"""Unit test for serialization and parsing."""

from os import tmpnam, unlink, path
from unittest import TestCase, main
from urllib import pathname2url
from warnings  import filterwarnings

import advene.model.backends.sqlite as backend_sqlite
from advene.model.core.diff import diff_packages
from advene.model.core.package import Package
from advene.model.parsers.exceptions import ParserError
import advene.model.serializers.advene_xml as xml
import advene.model.serializers.advene_zip as zip

from core_diff import fill_package_step_by_step


backend_sqlite._set_module_debug(True) # enable assert statements
filterwarnings("ignore", "tmpnam is a potential security risk to your program")

class TestAdveneXml(TestCase):
    def setUp(self):
        self.filename = tmpnam() + ".bxp"
        self.url = "file:" + pathname2url(self.filename)
        self.p1 = Package("file:/tmp/p1", create=True)

    def tearDown(self):
        self.p1.close()

    def test_each_step(self):
        p1 = self.p1
        for i in fill_package_step_by_step(p1, empty=True):
            f = open(self.filename, "w")
            xml.serialize_to(p1, f)
            f.close()
            try:
                p2 = Package(self.url)
            except ParserError, e:
                self.fail("ParserError: %s (%s)" % (e.args[0], self.filename))
            diff = diff_packages(p1, p2)
            self.assertEqual([], diff, (i, diff, self.filename))
            p2.close()
        unlink(self.filename)

class TestAdveneZip(TestCase):
    def setUp(self):
        self.filename = tmpnam() + ".bzp"
        self.url = "file:" + pathname2url(self.filename)
        self.p1 = Package("file:/tmp/p1", create=True)

    def tearDown(self):
        self.p1.close()

    def test_each_step(self):
        p1 = self.p1
        for i in fill_package_step_by_step(p1, empty=True):
            f = open(self.filename, "w")
            zip.serialize_to(p1, f)
            f.close()
            try:
                p2 = Package(self.url)
            except ParserError, e:
                self.fail("ParserError: %s (%s)" % (e.args[0], self.filename))
            diff = diff_packages(p1, p2)
            self.assertEqual(1, len(diff), (i, diff, self.filename))
            # NB: the package root differs from both packages,
            # hence len(diff) == 1
            p2.close()
        unlink(self.filename)
    
        

if __name__ == "__main__":
    main()
