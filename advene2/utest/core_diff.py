from unittest import TestCase, main
from urllib import pathname2url

from advene.model.consts import PARSER_META_PREFIX, DC_NS_PREFIX, RDFS_NS_PREFIX
from advene.model.core.diff import diff_packages
from advene.model.core.package import Package

dc_creator = DC_NS_PREFIX + "creator"
dc_description = DC_NS_PREFIX + "description"
rdfs_seeAlso = RDFS_NS_PREFIX + "seeAlso"

def fill_package_step_by_step(p, empty=False):
    if empty:
        yield "empty"
    p3 = Package("urn:xyz", create=True)
    m3 = p3.create_media("m3", "http://example.com/m3.ogm")
    a3 = p3.create_annotation("a3", m3, 123, 456, "text/plain")
    r3 = p3.create_relation("r3", "text/plain", members=[a3,])
    L3 = p3.create_list("L3", items=[a3, m3, r3,])
    t3 = p3.create_tag("t3")
    v3 = p3.create_view("v3", "text/html+tag")
    q3 = p3.create_query("q3", "x-advene/rules")
    R3 = p3.create_resource("R3", "text/css")

    p.uri = "http://example.com/my-package"; yield 1
    i = p.create_import("i", p3); yield 2
    m = p.create_media("m", "http://example.com/m.ogm"); yield 3
    m.set_meta(rdfs_seeAlso, m3); yield 4
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
        e.set_meta(dc_creator, "pchampin"); yield 18, e.id
        p.associate_tag(e, t); yield 19, e.id
        p.associate_tag(e, t3); yield 20, e.id
    sorted_p3_own = list(p3.own); sorted_p3_own.sort(key=lambda x: x._id)
    for e in sorted_p3_own:
        p.associate_tag(e, t); yield 21, e.id
        p.associate_tag(e, t3); yield 22, e.id
    p.set_meta(dc_creator, "pchampin"); yield 23, e.id
    p.set_meta(dc_description, "a package used for testing diff"); yield 24
    p.set_meta(PARSER_META_PREFIX+"namespaces",
               "dc http://purl.org/dc/elements/1.1/")
    yield "done"

class TestDiffPackage(TestCase):
    def setUp(self):
        self.p1 = Package("file:/tmp/p1", create=True)
        self.p2 = Package("file:/tmp/p2", create=True)

    def tearDown(self):
        self.p1.close()
        self.p2.close()

    def test_empty(self):
        p1, p2 = self.p1, self.p2
        self.assertEqual([], diff_packages(p1, p2))
        self.assertEqual([], diff_packages(p2, p1))
   
    def test_step_by_step(self):
        p1, p2 = self.p1, self.p2
        fill_p2 = fill_package_step_by_step(p2)
        for i in fill_package_step_by_step(p1):
            diff = diff_packages(p1, p2)
            self.assertEqual(1, len(diff), (i, diff))
            diff = diff_packages(p2, p1)
            self.assertEqual(1, len(diff), (i, diff))
            fill_p2.next()
            diff = diff_packages(p1, p2)
            self.assertEqual([], diff, "%s\n%r" % (i, diff))
            diff = diff_packages(p2, p1)
            self.assertEqual([], diff, "%s\n%r" % (i, diff))

    def test_several_steps(self):
        p1, p2 = self.p1, self.p2
        for i in fill_package_step_by_step(p1):
            self.assertNotEqual([], diff_packages(p1, p2), i)
            self.assertNotEqual([], diff_packages(p2, p1), i)

if __name__ == "__main__":
    main()
