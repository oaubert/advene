from unittest import TestCase, main
from urllib import pathname2url

from advene.model.core.diff import *
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


def fill_package_step_by_step(p, empty=False, p3=None):
    if empty:
        yield "empty"
    if p3 is None:
        p3 = Package("file:/tmp/p3", create=True)
        m3 = p3.create_media("m3", "http://example.com/m3.ogm", foref)
        a3 = p3.create_annotation("a3", m3, 123, 456, "text/plain")
        r3 = p3.create_relation("r3", "text/plain", members=[a3,])
        L3 = p3.create_list("L3", items=[a3, m3, r3,])
        t3 = p3.create_tag("t3")
        v3 = p3.create_view("v3", "text/html+tag")
        q3 = p3.create_query("q3", "x-advene/rules")
        R3 = p3.create_resource("R3", "text/css")
    else:
        m3 = p3["m3"]
        a3 = p3["a3"]
        r3 = p3["r3"]
        L3 = p3["L3"]
        t3 = p3["t3"]
        v3 = p3["v3"]
        q3 = p3["q3"]
        R3 = p3["R3"]
    p.uri = "http://example.com/my-package"; yield 1
    i = p.create_import("i", p3); yield 2
    m = p.create_media("m", "http://example.com/m.ogm", foref); yield 3
    m.rdfs_seeAlso = m3; yield 4
    Rb = p.create_resource("Rb", "x-advene/regexp"); yield 5
    Rb.content_data = "g.*g"; yield 6
    a = p.create_annotation("a", m, 123, 456, "text/plain", Rb); yield 7
    a.content_data = "goog moaning"; yield 8
    r = p.create_relation("r", members=[a, a3]); yield 9
    r2 = p.create_relation("r2", "text/plain"); yield 10
    L = p.create_list("L", items=[a, m, r, m3]); yield 11
    t = p.create_tag("t"); yield 12
    v = p.create_view("v", "text/html+tag"); yield 13
    v.content_url = "http://example.com/a-tal-view.html"; yield 14
    q = p.create_query("q", "text/x-python"); yield 15
    q.content_url = "file:%s" % pathname2url(__file__); yield 16
    Ra = p.create_resource("Ra", "text/css"); yield 17
    sorted_p_own = list(p.own); sorted_p_own.sort(key=lambda x: x._id)
    for e in sorted_p_own:
        e.dc_creator = "pchampin"; yield 18, e.id
        p.associate_tag(e, t); yield 19, e.id
        p.associate_tag(e, t3); yield 20, e.id
    sorted_p3_own = list(p3.own); sorted_p3_own.sort(key=lambda x: x._id)
    for e in sorted_p3_own:
        p.associate_tag(e, t); yield 21, e.id
        p.associate_tag(e, t3); yield 22, e.id
    p.dc_creator = "pchampin"; yield 23, e.id
    p.dc_description = "this is a package used for testing comparison"
    yield "done"
    

class TestDiffPackage(TestCase):
    def setUp(self):
        self.p1 = Package("sqlite::memory:;p1", create=True, _transient=True)
        #self.p1 = Package("file:/tmp/p1", create=True)
        self.p2 = Package("sqlite::memory:;p2", create=True, _transient=True)
        #self.p2 = Package("file:/tmp/p2", create=True)
        self.p3 = p3 = Package("sqlite::memory:;p3", create=True,
                               _transient=True)
        m3 = p3.create_media("m3", "http://example.com/m3.ogm", foref)
        a3 = p3.create_annotation("a3", m3, 123, 456, "text/plain")
        r3 = p3.create_relation("r3", "text/plain", members=[a3,])
        L3 = p3.create_list("L3", items=[a3, m3, r3,])
        t3 = p3.create_tag("t3")
        v3 = p3.create_view("v3", "text/html+tag")
        q3 = p3.create_query("q3", "x-advene/rules")
        R3 = p3.create_resource("R3", "text/css")

    def tearDown(self):
        self.p1.close()
        self.p2.close()
        self.p3.close()

    def test_empty(self):
        p1, p2 = self.p1, self.p2
        self.assertEqual([], diff_packages(p1, p2))
        self.assertEqual([], diff_packages(p2, p1))
   
    def test_step_by_step(self):
        p1, p2 = self.p1, self.p2
        fill_p2 = fill_package_step_by_step(p2, p3=self.p3)
        for i in fill_package_step_by_step(p1, p3=self.p3):
            diff = diff_packages(p1, p2)
            self.assertEqual(1, len(diff), (i, diff))
            diff = diff_packages(p2, p1)
            self.assertEqual(1, len(diff), (i, diff))
            fill_p2.next()
            self.assertEqual([], diff_packages(p1, p2), i)
            self.assertEqual([], diff_packages(p2, p1), i)
 
    def test_several_steps(self):
        p1, p2 = self.p1, self.p2
        for i in fill_package_step_by_step(p1, p3=self.p3):
            self.assertNotEqual([], diff_packages(p1, p2), i)
            self.assertNotEqual([], diff_packages(p2, p1), i)

if __name__ == "__main__":
    main()
