"""
This file should contain unit tests for cam.package.
Specific features of cam.package must obviously be tested here.

A lot of things informally tested in test/test1-cam.py should be transposed
here.
"""
from unittest import TestCase, main

class TestReferences(TestCase):
    def setUp(self):
        from advene.model.cam.package import Package
        p = self.p = Package("transient:1", create=True)
        q = self.q = Package("transient:2", create=True)

        m1 = q.create_media("m1", "http://example.com/m1.avi")
        at1 = q.create_annotation_type("at1")
        rt1 = q.create_relation_type("rt1")
        a1 = q.create_annotation("a1", m1, 0, 42, "text/plain", type=at1)
        r1 = q.create_relation("r1", type=rt1, members=[a1,])
        L1 = q.create_user_list("L1", items=[m1, a1, r1,])
        t1 = q.create_user_tag("t1")
        R1 = q.create_resource("R1", "text/plain")
        a1.content_model = R1

        p.create_import("i", q)
        m2 = p.create_media("m2", "http://example.com/m2.avi")
        at2 = p.create_annotation_type("at2")
        rt2 = p.create_relation_type("rt2")
        a2 = p.create_annotation("a2", m2, 0, 42, "text/plain", type=at2)
        r2 = p.create_relation("r2", type=rt2, members=[a2,])
        L2 = p.create_user_list("L2", items=[m2, a2, r2,])
        t2 = p.create_user_tag("t2")
        R2 = p.create_resource("R2", "text/plain")
        a2.content_model = R2

        a3 = p.create_annotation("a3", m1, 1, 2, "text/plain", type=at1)
        a3.content_model=R1
        r3 = p.create_relation("r3", members=[a2, a1,], type=rt2)
        L3 = p.create_user_list("L3", items=[a1, m1,])

        p.meta["key"] = a1
        p.associate_user_tag(a1, t1)

    def tearDown(self):
        self.p.close()
        self.q.close()

    def test_iter_references(self):
        def check(it1, it2=None):
            if it2 is None: print list(it1) # debugging
            else:
                #self.assertEqual(frozenset(it1), frozenset(it2))
                try:
                    s1 = frozenset(it1)
                    s2 = frozenset(it2)
                    self.assertEqual(s1, s2)
                except AssertionError, e:
                    print "+++", s1.difference(s2)
                    print "---", s2.difference(s1)
                    raise e

        p = self.p
        q = self.q
        at1 = q.get("at1")
        m1 = q.get("m1")
        a1 = q.get("a1")
        a3 = p.get("a3")
        r1 = q.get("r1")
        r3 = p.get("r3")
        t1 = q.get("t1")
        L1 = q.get("L1")
        L3 = p.get("L3")
        R1 = q.get("R1")

        from advene.model.cam.consts import CAM_TYPE as ct
        check(at1.iter_references(), [
            ("tagging", q, a1), ("tagging", p, a3),
            ("meta", a1, ct), ("meta", a3, ct),
        ])

        check(a1.iter_references(), [
            ("tagged", q, at1), ("tagged", p, t1),
            ("item", L1), ("item", L3),
            ("member", r1), ("member", r3),
            ("meta", p, "key"),
        ])

        check(m1.iter_references(), [
            ("media", a1), ("media", a3),
            ("item", L1), ("item", L3),
        ])


        check(R1.iter_references(), [
            ("content_model", a1), ("content_model", a3),
        ])

    def test_rename(self):
        p = self.p
        q = self.q

        m01 = q.get("m1")
        m01.id = "m01"
        assert not q.has_element("m1")
        assert q.get("m01") is m01
        assert q.get("a1").media is m01
        assert p.get("a3").media is m01

        at01 = q.get("at1")
        at01.id = "at01"
        assert not q.has_element("at1")
        assert q.get("at01") is at01
        assert q.get("a1").type is at01
        assert p.get("a3").type is at01
        assert at01 in list(q.get("a1").iter_my_tags(q, _guard=0))
        assert at01 in list(p.get("a3").iter_my_tags(p, _guard=0))

        a01 = q.get("a1")
        a01.id = "a01"
        assert not q.has_element("a1")
        assert q.get("a01") is a01
        assert a01 is p.meta["key"]
        assert a01 in list(q.get("at01").iter_elements(q))
        assert a01 is q.get("r1")[0]
        assert a01 is p.get("r3")[1]
        assert a01 is q.get("L1")[1]
        assert a01 in p.get("L3")

        R01 = q.get("R1")
        R01.id = "R01"
        assert not q.has_element("R1")
        assert q.get("R01") is R01
        assert q.get("a01").content_model is R01
        assert p.get("a3").content_model is R01

        # fake name clash
        a2 = q.get("a01")
        a2.id = "a2"
        assert not q.has_element("a01")
        assert q.get("a2") is a01
        assert a2 is p.meta["key"]
        assert a2 in list(q.get("at01").iter_elements(q))
        assert a2 is q.get("r1")[0]
        assert a2 is p.get("r3")[1]
        assert a2 is q.get("L1")[1]
        assert a2 in p.get("L3")

        # real name clash
        self.assertRaises(AssertionError, setattr, p.get("a2"), "id", "a3")


if __name__ == "__main__":
    main()
