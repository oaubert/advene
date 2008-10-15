from unittest import TestCase, main

from advene.model.core.package import Package as CorePackage
from advene.model.cam.package import Package as CamPackage
from advene.model.tales import AdveneContext, register_global_method, \
                               unregister_global_method, \
                               tales_full_path_function, tales_path1_function,\
                               tales_context_function, tales_property, \
                               tales_use_as_context

class WithCheckPathMixin(object):
    def check_path(self, path, expected_result):
        t1 = self.c.evaluate(path)
        t2 = expected_result
        try:
            if isinstance(t1, basestring) or isinstance(t2, basestring):
                raise Exception # do not iter
            t1_ = iter(t1)
            t2_ = iter(t2)
            t1 = frozenset(t1_)
            t2 = frozenset(t2_)
        except:
            pass
        self.assertEqual(t1, t2)


class TestTales(TestCase, WithCheckPathMixin):
    def setUp(self):
        class Foo(object):
            msg = 'hello world'
            dict = {"a": "A", "b": "B"}
            list = ["a", "b", "c",]
            @tales_full_path_function
            def full_path(self, path):
                return path
            @tales_path1_function
            def path1(self, path):
                return path
            @tales_context_function
            def context(self, context):
                return context
            @tales_property
            def property1(self, context):
                return context
            @tales_property
            @tales_use_as_context("here")
            def property2(self, here):
                return here
        self.h = Foo()
        self.c = AdveneContext(self.h)

    def tearDown(self):
        pass

    def test_misc(self):
        c = self.c
        h = self.h
        self.check_path("here", h)
        self.check_path("here/msg", h.msg)
        self.check_path("here/dict", h.dict)
        self.check_path("here/dict/a", h.dict["a"])
        self.check_path("here/list", h.list)
        self.check_path("here/list/0", h.list[0])
        self.check_path("nocall:here/full_path", h.full_path)
        self.check_path("here/full_path", [])
        self.check_path("here/full_path/a/b/c", ["a", "b", "c"])
        self.check_path("nocall:here/path1", h.path1)
        self.check_path("here/path1/abc", "abc")
        self.check_path("here/path1/abc/0", "a")
        self.check_path("nocall:here/context", h.context)
        self.check_path("here/context", c)
        self.check_path("nocall:here/property1", c)
        self.check_path("here/property1", c)
        self.check_path("nocall:here/property2", h)
        self.check_path("here/property2", h)

    def test_repr_global_method(self):
        h = self.h
        self.check_path("here/repr", repr(h))
        self.check_path("here/msg", h.msg)
        self.check_path("here/msg/repr", repr(h.msg))

    def test_registered_global_method(self):
        def my_global_method(obj, context):
            return (obj, context)
        register_global_method(my_global_method)
        c = self.c
        h = self.h
        try:
            self.check_path("here/my_global_method", (h,c))
            self.check_path("here/msg/my_global_method", (h.msg,c))
        finally:
            unregister_global_method(my_global_method)

    def test_aliased_global_method(self):
        def my_global_method(obj, context):
            return (obj, context)
        register_global_method(my_global_method, "aliased_global_method")
        c = self.c
        h = self.h
        try:
            self.check_path("here/aliased_global_method", (h,c))
            self.check_path("here/msg/aliased_global_method", (h.msg,c))
        finally:
            unregister_global_method("aliased_global_method")


class TestTalesWithCore(TestCase, WithCheckPathMixin):
    def setUp(self):
        self.p = p = CorePackage("tmp", create=True)
        p.uri = "urn:1234"
        p.create_media("m1", "http://media.org/m1")
        p.create_annotation("a1", p.get("m1"), 42, 101, "text/plain")
        p.create_tag("t1")
        p.associate_tag(p["a1"], p["t1"])

        self.c = AdveneContext(p)
        self.c.addGlobal("package", p)

    def tearDown(self):
        pass

    def test_misc(self):
        p = self.p
        self.check_path("here", p)
        self.check_path("here/a1", p["a1"])
        self.check_path("here/a1/media", p["a1"].media)
        self.check_path("here/a1/begin", p["a1"].begin)
        self.check_path("here/a1/my_tags", p["a1"].iter_my_tags(p))
        self.check_path("here/a1/my_tags/0", p["a1"].iter_my_tags(p).next())
        assert self.c.evaluate("foo|string:") is ""

    def test_absolute_url(self):
        p = self.p; c = self.c
        p1 = CorePackage("tmp1", create=True)
        p2 = CorePackage("tmp2", create=True)
        p3 = CorePackage("tmp3", create=True)
        t = p.create_tag("t")
        t1 = p1.create_tag("t1")
        t2 = p2.create_tag("t2")
        t3 = p3.create_tag("t3")
        p.create_import("i1", p1)
        p1.create_import("i2", p2)
        options = { "packages": {"p": p, "p1": p1},
                    "p": p, "p1": p1, "p2": p2, "p3": p3,
                  }
        c.addGlobal("options", options)

        # check on package
        self.check_path("options/p/absolute_url", "/p")
        self.check_path("options/p1/absolute_url", "/p1")
        try:
            self.check_path("options/p2/absolute_url", "/p/i1:i2/package")
            # it is either one or the other, we can't predict
        except AssertionError:
            self.check_path("options/p2/absolute_url", "/p1/i2/package")
        self.check_path("options/p/absolute_url/a/b/c", "/p/a/b/c")
        base = options["base_url"] = "http://localhost:1234/packages"
        self.check_path("options/p/absolute_url/a/b/c", base+"/p/a/b/c")
        self.check_path("options/p3/absolute_url|nothing", None)
        del options["base_url"]

        # check on element
        self.check_path("options/p/t/absolute_url", "/p/t")
        self.check_path("options/p1/t1/absolute_url", "/p1/t1")
        try:
            self.check_path("options/p2/t2/absolute_url", "/p/i1:i2:t2")
            # it is either one or the other, we can't predict
        except AssertionError:
            self.check_path("options/p2/t2", "/p1/i2:t2")
        self.check_path("options/p/t/absolute_url/a/b/c", "/p/t/a/b/c")
        base = options["base_url"] = "http://localhost:1234/packages"
        self.check_path("options/p/t/absolute_url/a/b/c", base+"/p/t/a/b/c")
        self.check_path("options/p3/t3/absolute_url|nothing", None)


class TestTalesWithCam(TestCase, WithCheckPathMixin):
    def setUp(self):
        self.p = p = CamPackage("tmp", create=True)
        p.uri = "urn:1234"
        p.create_annotation_type("at1")
        p.create_annotation_type("at2")
        p.create_relation_type("rt1")
        p.create_relation_type("rt2")
        p.create_schema("s1", items=[p.get("at1"), p.get("at2"), p.get("rt1")])
        p.create_schema("s2", items=[p.get("at1"), p.get("rt2")])
        p.create_media("m1", "http://media.org/m1")
        p.create_annotation("a1", p.get("m1"), 42, 101, "text/plain",
                            type=p.get("at2"))
        p.create_user_tag("t1")
        p.create_user_list("l1", items=[p.get("a1"), p.get("at1")])
        p.associate_user_tag(p.get("a1"), p.get("t1"))
        p.associate_user_tag(p.get("m1"), p.get("t1"))

        self.c = AdveneContext(p)
        self.c.addGlobal("regpkg", p)

    def tearDown(self):
        pass

    def test_misc(self):
        p = self.p
        self.check_path("here/at1", p.get("at1"))
        self.check_path("here/annotation_types", p.all.annotation_types)
        self.check_path("here/relation_types", p.all.relation_types)
        self.check_path("here/schemas", p.all.schemas)
        self.check_path("here/user_tags", p.all.user_tags)
        self.check_path("here/user_lists", p.all.user_lists)
        self.check_path("here/a1/type", p["a1"].type)

if __name__ == "__main__":
    main()
