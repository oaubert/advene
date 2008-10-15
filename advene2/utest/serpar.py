"""Unit test for serialization and parsing."""

from os import fdopen, path, unlink
from tempfile import mkstemp
from unittest import TestCase, main
from urllib import pathname2url
import warnings

import advene.model.backends.sqlite as backend_sqlite
from advene.model.cam.exceptions import UnsafeUseWarning
from advene.model.cam.package import Package as CamPackage
from advene.model.consts import PACKAGED_ROOT, DC_NS_PREFIX, \
                                RDFS_NS_PREFIX, PARSER_META_PREFIX
from advene.model.core.diff import diff_packages
from advene.model.core.package import Package
from advene.model.parsers.exceptions import ParserError
import advene.model.serializers.advene_xml as xml
import advene.model.serializers.advene_zip as zip
import advene.model.serializers.cinelab_xml as cxml
import advene.model.serializers.cinelab_zip as czip

from core_diff import fill_package_step_by_step

warnings.filterwarnings("ignore", category=UnsafeUseWarning,
                        module="advene.model.core.diff")
#warnings.filterwarnings("ignore", category=UnsafeUseWarning,
#                        module="core_diff")
warnings.filterwarnings("ignore", category=UnsafeUseWarning, module=__name__)



backend_sqlite._set_module_debug(True) # enable assert statements

class TestAdveneXml(TestCase):
    """
    This TestCase is not specific to AdveneXml. It can be reused for other
    serializer-parser pairs by simply overriding its class attributes: `serpar`,
    `pkgcls`.

    It may also be necessary to override the `fix_diff` and
    `fill_package_step_by_step` methods.
    """
    pkgcls = Package
    serpar = xml

    def setUp(self):
        fd1, self.filename1 = mkstemp(suffix=self.serpar.EXTENSION)
        fd2 , self.filename2 = mkstemp(suffix=self.serpar.EXTENSION)
        fdopen(fd1).close()
        fdopen(fd2).close()
        self.url = "file:" + pathname2url(self.filename2)
        self.p1 = self.pkgcls("file:" + pathname2url(self.filename1),
                              create=True)

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

    def fill_package_step_by_step(self):
        return fill_package_step_by_step(self.p1, empty=True)

    def test_each_step(self):
        p1 = self.p1
        for i in self.fill_package_step_by_step():
            f = open(self.filename2, "w")
            self.serpar.serialize_to(p1, f)
            f.close()
            try:
                p2 = self.pkgcls(self.url)
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
        self.serpar.serialize_to(p1, f)
        f.close()
        try:
            p2 = self.pkgcls(self.url)
        except ParserError, e:
            self.fail("ParserError: %s (%s)" % (e.args[0], self.filename2))
        diff = self.fix_diff(diff_packages(p1, p2))
        self.assertEqual([], diff, (diff, self.filename2))
        p2.close()
        unlink(self.filename2)

    def test_forward_reference_in_tagged_imports(self):
        p1 = self.p1
        i1 = p1.create_import("i1", self.pkgcls("urn:123", 1))
        i2 = p1.create_import("i2", self.pkgcls("urn:456", 1))
        p1.associate_tag(i1, "i2:t")
        p1.associate_tag(i2, "i1:t")
        # one of the two imports will necessarily have forward-references in the
        # serialization

        f = open(self.filename2, "w")
        self.serpar.serialize_to(p1, f)
        f.close()
        try:
            p2 = self.pkgcls(self.url)
        except ParserError, e:
            self.fail("ParserError: %s (%s)" % (e.args[0], self.filename2))
        diff = self.fix_diff(diff_packages(p1, p2))
        self.assertEqual([], diff, (diff, self.filename2))
        p2.close()
        unlink(self.filename2)

class TestAdveneZip(TestAdveneXml):
    serpar = zip

    def fix_diff(self, diff):
        # the packages do not have the same package_root,
        # hence we remove that metadata
        return [ d for d in diff
                 if not ( d[0] == "set_meta" and d[3] ==  PACKAGED_ROOT ) ]

class TestCinelabXml(TestAdveneXml):
    pkgcls = CamPackage
    serpar = cxml

    def fill_package_step_by_step(self):
        dc_creator = DC_NS_PREFIX + "creator"
        dc_description = DC_NS_PREFIX + "description"
        rdfs_seeAlso = RDFS_NS_PREFIX + "seeAlso"
        p = self.p1
        yield "empty"
        p3 = self.pkgcls("urn:xyz", create=True)
        m3  = p3.create_media("m3", "http://example.com/m3.ogm")
        at3 = p3.create_annotation_type("at3")
        a3  = p3.create_annotation("a3", m3, 123, 456, "text/plain", type=at3)
        rt3 = p3.create_relation_type("rt3")
        r3  = p3.create_relation("r3", "text/plain", members=[a3,], type=rt3)
        s3  = p3.create_schema("s3", items=[at3, rt3,])
        L3  = p3.create_user_list("L3", items=[a3, m3, r3,])
        t3  = p3.create_user_tag("t3")
        v3  = p3.create_view("v3", "text/html+tag")
        q3  = p3.create_query("q3", "x-advene/rules")
        R3  = p3.create_resource("R3", "text/css")

        p.uri = "http://example.com/my-package"; yield 1
        i = p.create_import("i", p3); yield 2
        at = p.create_annotation_type("at"); yield 2.1
        rt = p.create_relation_type("rt"); yield 2.2
        m = p.create_media("m", "http://example.com/m.ogm"); yield 3
        m.set_meta(rdfs_seeAlso, m3); yield 4
        Rb = p.create_resource("Rb", "x-advene/regexp"); yield 5
        Rb.content_data = "g.*g"; yield 6
        a = p.create_annotation("a", m, 123, 456,
                                "text/plain", Rb, type=at); yield 7
        a.content_data = "goog moaning"; yield 8
        a2 = p.create_annotation("a2", m3, 123, 456,
                                "text/plain", Rb, type=at3); yield 8.1
        r = p.create_relation("r", members=[a, a3], type=rt); yield 9
        r2 = p.create_relation("r2", "text/plain", type=rt3); yield 10
        s = p.create_schema("s", items=[at, rt, at3, rt3,]); yield 10.1
        L = p.create_user_list("L", items=[a, m, r, m3]); yield 11
        t = p.create_user_tag("t"); yield 12
        v = p.create_view("v", "text/html+tag"); yield 13
        v.content_url = "http://example.com/a-tal-view.html"; yield 14
        q = p.create_query("q", "text/x-python"); yield 15
        q.content_url = "file:%s" % pathname2url(__file__); yield 16
        Ra = p.create_resource("Ra", "text/css"); yield 17
        sorted_p_own = list(p.own); sorted_p_own.sort(key=lambda x: x._id)
        for e in sorted_p_own:
            e.set_meta(dc_creator, "pchampin"); yield 18, e.id
            p.associate_user_tag(e, t); yield 19, e.id
            p.associate_user_tag(e, t3); yield 20, e.id
        sorted_p3_own = list(p3.own); sorted_p3_own.sort(key=lambda x: x._id)
        for e in sorted_p3_own:
            p.associate_user_tag(e, t); yield 21, e.id
            p.associate_user_tag(e, t3); yield 22, e.id
        p.set_meta(dc_creator, "pchampin"); yield 23, e.id
        p.set_meta(dc_description, "a package used for testing diff"); yield 24
        p.set_meta(PARSER_META_PREFIX+"namespaces",
                   "dc http://purl.org/dc/elements/1.1/")
        yield "done"

class TestCinelabZip(TestCinelabXml, TestAdveneZip):
    serpar = czip

if __name__ == "__main__":
    main()
