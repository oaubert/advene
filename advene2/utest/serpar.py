"""Unit test for serialization and parsing."""

from os import fdopen, path, unlink
from tempfile import mkstemp
from unittest import TestCase, main
from urllib import pathname2url

import advene.model.backends.sqlite as backend_sqlite
from advene.model.consts import PACKAGED_ROOT
from advene.model.core.diff import diff_packages
from advene.model.core.package import Package
from advene.model.parsers.exceptions import ParserError
import advene.model.serializers.advene_xml as xml
import advene.model.serializers.advene_zip as zip

from core_diff import fill_package_step_by_step


backend_sqlite._set_module_debug(True) # enable assert statements

class TestAdveneXml(TestCase):
    parser = xml

    def setUp(self):
        fd1, self.filename1 = mkstemp(suffix=self.parser.EXTENSION)
        fd2 , self.filename2 = mkstemp(suffix=self.parser.EXTENSION)
        fdopen(fd1).close()
        fdopen(fd2).close()
        self.url = "file:" + pathname2url(self.filename2)
        self.p1 = Package("file:" + pathname2url(self.filename1), create=True)

    def tearDown(self):
        self.p1.close()
        unlink(self.filename1)
        try:
            unlink(self.filename2)
        except OSError:
            pass

    def fix_diff(self, diff):
        """
        Used to remove differences that are not relevant to the test.
        """
        # nothing to do here
        return diff

    def test_each_step(self):
        p1 = self.p1
        for i in fill_package_step_by_step(p1, empty=True):
            f = open(self.filename2, "w")
            self.parser.serialize_to(p1, f)
            f.close()
            try:
                p2 = Package(self.url)
            except ParserError, e:
                self.fail("ParserError: %s (%s)" % (e.args[0], self.filename2))
            diff = self.fix_diff(diff_packages(p1, p2))
            self.assertEqual([], diff, (i, diff, self.filename2))
            p2.close()

    def test_forward_reference_in_list_items(self):
        p1 = self.p1
        r1 = p1.create_resource("r1", "text/plain")
        r2 = p1.create_resource("r2", "text/plain")
        L1 = p1.create_list("L1")
        L2 = p1.create_list("L2")
        L1[:] = [r1, L2, r2, L2,]
        L2[:] = [r1, L1, r2, L1,]
        # one of the two list will necessarily have forward-references in the
        # serialization

        f = open(self.filename2, "w")
        self.parser.serialize_to(p1, f)
        f.close()
        try:
            p2 = Package(self.url)
        except ParserError, e:
            self.fail("ParserError: %s (%s)" % (e.args[0], self.filename2))
        diff = self.fix_diff(diff_packages(p1, p2))
        self.assertEqual([], diff, (diff, self.filename2))
        p2.close()
        unlink(self.filename2)

class TestAdveneZip(TestAdveneXml):
    parser = zip

    def fix_diff(self, diff):
        # the packages do not have the same package_root,
        # hence we remove that metadata
        return [ d for d in diff
                 if not ( d[0] == "set_meta" and d[3] ==  PACKAGED_ROOT ) ]

    
        

if __name__ == "__main__":
    main()
