from unittest import TestCase, main
from urllib import pathname2url

from advene.model.core.cmp import *
from advene.model.core.element import PackageElement
from advene.model.core.media import FOREF_PREFIX
from advene.model.core.package import Package

foref = FOREF_PREFIX+"ms;o=0"
dc_creator = "http://purl.org/dc/elements/1.1/creator"
dc_description = "http://purl.org/dc/elements/1.1/description"
rdfs_seeAlso = "http://www.w3.org/1999/02/22-rdf-syntax-ns#seeAlso"

Package.make_metadata_property(dc_creator, "dc_creator")
Package.make_metadata_property(dc_description, "dc_description")
Package.make_metadata_property(rdfs_seeAlso, "rdfs_seeAlso")
PackageElement.make_metadata_property(dc_creator, "dc_creator")
PackageElement.make_metadata_property(dc_description, "dc_description")
PackageElement.make_metadata_property(rdfs_seeAlso, "rdfs_seeAlso")

class TestCmpPackage(TestCase):
    def setUp(self):
        self.p1 = Package("sqlite::memory:;p1", create=True, _transient=True)
        self.p2 = Package("sqlite::memory:;p2", create=True, _transient=True)
        self.p3 = Package("sqlite::memory:;p3", create=True, _transient=True)

    def tearDown(self):
        self.p1.close()
        self.p2.close()
        self.p3.close()

    def test_cmp_empty(self):
        self.assertEqual(0, cmp_packages(self.p1, self.p2))
        self.assertEqual(0, cmp_packages(self.p2, self.p1))

    def test_cmp_full(self):
        m3 = self.p3.create_media("m3", "http://example.com/m3.ogm", foref)
        a3 = self.p3.create_annotation("a3", m3, 123, 456, "text/plain")
        r3 = self.p3.create_relation("r3", "text/plain", members=[a3,])
        L3 = self.p3.create_list("L3", items=[a3, m3, r3,])
        t3 = self.p3.create_tag("t3")
        v3 = self.p3.create_view("v3", "text/html+tag")
        q3 = self.p3.create_query("q3", "x-advene/rules")
        R3 = self.p3.create_resource("R3", "text/css")

        for i in self._fill_package(self.p1, self.p2):
            self.assertNotEqual(0, cmp_packages(self.p1, self.p2), i)
            self.assertNotEqual(0, cmp_packages(self.p2, self.p1), i)
        for i in self._fill_package(self.p2, self.p1):
            if i != "done":
                self.assertNotEqual(0, cmp_packages(self.p1, self.p2), i)
                self.assertNotEqual(0, cmp_packages(self.p2, self.p1), i)
        self.assertEqual(0, cmp_packages(self.p1, self.p2))
        self.assertEqual(0, cmp_packages(self.p2, self.p1))

    def _fill_package(self, p1, p2):
        p3 = self.p3
        p1.uri = "http://example.com/my-package"; yield
        i = p1.create_import("i", p3); yield
        m = p1.create_media("m", "http://example.com/m.ogm", foref); yield
        m.rdfs_seeAlso = p3["m3"]; yield
        Rb = p1.create_resource("Rb", "x-advene/regexp"); yield
        Rb.content_data = "g.*g"; yield
        a = p1.create_annotation("a", m, 123, 456, "text/plain", Rb); yield
        r = p1.create_relation("r", "text/plain", members=[a, p3["a3"]]); yield
        L = p1.create_list("L", items=[a, m, r, p3["m3"]]); yield
        t = p1.create_tag("t"); yield
        v = p1.create_view("v", "text/html+tag"); yield
        v.content_url = "http://example.com/a-tal-view.html"; yield
        q = p1.create_query("q", "text/x-python"); yield
        q.content_url = "file:%s" % pathname2url(__file__)
        Ra = p1.create_resource("Ra", "text/css"); yield
        for e in p1.own:
            e.dc_creator = "pchampin"; yield
            p1.associate_tag(e, t); yield
            p1.associate_tag(e, p3["t3"]); yield
        for e in p3.own:
            p1.associate_tag(e, t); yield
            p1.associate_tag(e, p3["t3"]); yield
        p1.dc_creator = "pchampin"; yield
        p1.dc_description = "this is a package used for testing comparison"
        yield "done"
        

if __name__ == "__main__":
    main()
